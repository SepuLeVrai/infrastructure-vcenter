"""UI setup and credential renewal."""
import logging
import traceback
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers import selector
from homeassistant.core import callback

from .client import AuthenticationError
from .connection import VMwareConnection
from .endpoints import normalize_vmware_config
from .const import DEFAULT_INTERVAL, DOMAIN
from .connection_errors import connection_diagnostic

_LOGGER = logging.getLogger(__name__)


def connection_schema(values):
    return vol.Schema({
        vol.Optional(CONF_HOST, default=values.get(CONF_HOST, "")): str,
        vol.Optional("esx_hosts", default=values.get("esx_hosts", "")): str,
        vol.Required(CONF_USERNAME, default=values.get(CONF_USERNAME, vol.UNDEFINED)): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        vol.Required(CONF_PORT, default=values.get(CONF_PORT, 443)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_VERIFY_SSL, default=values.get(CONF_VERIFY_SSL, True)): bool,
        vol.Required("interval", default=values.get("interval", DEFAULT_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
    })


def report_connection_error(error, data):
    code, detail = connection_diagnostic(error, data)
    # Stack frames help identify SDK incompatibilities without logging exception
    # chains (which can contain an unredacted message) or local credentials.
    frames = " > ".join(f"{frame.name}:{frame.lineno}" for frame in traceback.extract_tb(error.__traceback__))
    _LOGGER.error("VCENTER_CONNECT [%s] %s; frames=%s", code, detail, frames)
    return code, detail


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()

    async def _validate(self, config, excluded=None):
        identity, endpoints = await self.hass.async_add_executor_job(VMwareConnection(config).validate)
        for other in self._async_current_entries():
            if other.entry_id != excluded and endpoints and set(endpoints).intersection(other.data.get("endpoint_ids", [])):
                raise ValueError("A direct ESXi endpoint is already configured")
        return identity, endpoints

    async def async_step_user(self, user_input=None):
        errors = {}
        detail = ""
        values = user_input or {}
        if user_input is not None:
            try:
                user_input = normalize_vmware_config(user_input)
                identity, endpoints = await self._validate(user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception as err:
                errors["base"], detail = report_connection_error(err, user_input)
            else:
                await self.async_set_unique_id(identity)
                self._abort_if_unique_id_configured(reload_on_update=False)
                user_input["endpoint_ids"] = endpoints
                return self.async_create_entry(title=user_input[CONF_HOST] or "ESXi directs", data=user_input)
        return self.async_show_form(step_id="user", data_schema=connection_schema(values), errors=errors, description_placeholders={"details": detail})

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors, detail = {}, ""
        values = {**entry.data, **entry.options, **(user_input or {})}
        if user_input is not None:
            try:
                data = normalize_vmware_config({**entry.data, **user_input})
                identity, endpoints = await self._validate(data, entry.entry_id)
                if data[CONF_HOST] and identity != entry.unique_id:
                    raise ValueError("Adding a different vCenter requires a separate integration entry")
                if bool(data[CONF_HOST]) != bool(entry.data.get(CONF_HOST)):
                    raise ValueError("Switching between vCenter and direct ESXi requires a separate entry")
                data["endpoint_ids"] = endpoints
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception as error:
                errors["base"], detail = report_connection_error(error, values)
            else:
                return self.async_update_and_abort(entry, data_updates=data,
                    options={**entry.options, "interval": data["interval"]}, reason="reconfigure_successful")
        return self.async_show_form(step_id="reconfigure", data_schema=connection_schema(values), errors=errors, description_placeholders={"details": detail})

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        detail = ""
        if user_input is not None:
            entry = self._get_reauth_entry()
            data = {**entry.data, **user_input}
            try:
                identity, endpoints = await self._validate(data, entry.entry_id)
                if not data.get(CONF_HOST) and set(endpoints) != set(entry.data.get("endpoint_ids", [])):
                    raise ValueError("The direct ESXi identities changed; reconfigure this entry")
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception as err:
                errors["base"], detail = report_connection_error(err, data)
            else:
                await self.async_set_unique_id(identity if data.get(CONF_HOST) else entry.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_and_abort(entry, data_updates=user_input, reason="reauth_successful")
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }), errors=errors, description_placeholders={"details": detail})


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        interval = self.config_entry.options.get("interval", self.config_entry.data.get("interval", DEFAULT_INTERVAL))
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required("interval", default=interval): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600))
        }))
