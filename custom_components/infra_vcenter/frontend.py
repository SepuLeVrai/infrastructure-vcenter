"""Install the bundled resource without editing dashboard/card configurations."""
import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA

from .const import VERSION

_LOGGER = logging.getLogger(__name__)
CARD_PATH = "/infra-vcenter/infrastructure-card.js"
CARD_URL = f"{CARD_PATH}?v={VERSION}"
LEGACY_PATH = "/local/infra-vcenter/infrastructure-card.js"


def is_our_resource(url):
    """Only migrate this integration's local URLs, never an external resource."""
    try:
        parts = urlsplit(url)
    except (TypeError, ValueError):
        return False
    return not parts.scheme and not parts.netloc and parts.path in (CARD_PATH, LEGACY_PATH)


async def async_sync_resources(resources):
    """Keep resource IDs and unrelated resources intact; never touch cards."""
    await resources.async_get_info()  # Loads storage resources before inspection.
    matches = [item for item in resources.async_items() if is_our_resource(item.get("url", ""))]
    if not matches:
        await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
        return
    for item in matches:
        if item.get("url") != CARD_URL or item.get("type") != "module":
            await resources.async_update_item(item["id"], {"url": CARD_URL, "res_type": "module"})


async def async_setup_frontend(hass):
    """Use HA's asynchronous static-path and Lovelace resource APIs."""
    asset = Path(__file__).parent / "frontend" / "infrastructure-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_PATH, str(asset), False)])
    data = hass.data[LOVELACE_DATA]
    if data.resource_mode != "storage":
        _LOGGER.warning("Lovelace resources use YAML; set the module resource URL to %s", CARD_URL)
        return
    try:
        await async_sync_resources(data.resources)
    except Exception as error:
        # A resource editor/storage failure must not stop VMware monitoring.
        _LOGGER.warning("Card resource registration failed (%s); add module %s manually",
                        type(error).__name__, CARD_URL)
