"""Read-only vSphere inventory and monitoring."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError
from .connection import VMwareConnection
from .const import DEFAULT_INTERVAL, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = VMwareConnection(dict(entry.data), group_id=entry.unique_id)
    coordinator_options = {**entry.data, **entry.options}

    async def update():
        try:
            return await hass.async_add_executor_job(client.collect)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Identifiants vCenter refusés") from err
        except Exception as err:
            raise UpdateFailed(f"Collecte vCenter impossible ({type(err).__name__})") from err

    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(__name__),
        name=DOMAIN, config_entry=entry,
        update_method=update,
        update_interval=timedelta(seconds=coordinator_options.get("interval", DEFAULT_INTERVAL)),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)
