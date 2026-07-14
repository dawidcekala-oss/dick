from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    CONF_URL_PATH,
    LOVELACE_DATA,
    ConfigNotFound,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DASHBOARD_ICON,
    DASHBOARD_STORAGE_ID,
    DASHBOARD_TITLE,
    DASHBOARD_URL_PATH,
    DOMAIN,
    FRONTEND_MODULE,
    FRONTEND_URL,
)

_LOGGER = logging.getLogger(__name__)

_STATIC_REGISTERED = f"{DOMAIN}_frontend_static_registered"
_RESOURCE_REGISTERED = f"{DOMAIN}_frontend_resource_registered"
_DASHBOARD_REGISTERED = f"{DOMAIN}_frontend_dashboard_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Expose the bundled card, add it to Lovelace resources and create the panel."""
    if not hass.data.get(_STATIC_REGISTERED):
        frontend_path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL, str(frontend_path), False)]
        )
        hass.data[_STATIC_REGISTERED] = True

    if not hass.data.get(_RESOURCE_REGISTERED):
        await _async_ensure_lovelace_resource(hass)

    if not hass.data.get(_DASHBOARD_REGISTERED):
        await _async_ensure_dashboard(hass)


async def _async_ensure_lovelace_resource(hass: HomeAssistant) -> None:
    lovelace_data = hass.data.get(LOVELACE_DATA)
    resource_collection = getattr(lovelace_data, "resources", None)
    if resource_collection is None:
        _LOGGER.debug("Lovelace resources are not ready yet")
        return

    if not hasattr(resource_collection, "async_create_item"):
        _LOGGER.debug("Lovelace resources are in YAML mode; skipping card registration")
        return

    await resource_collection.async_get_info()
    if any(_same_resource(item) for item in resource_collection.async_items()):
        hass.data[_RESOURCE_REGISTERED] = True
        return

    await resource_collection.async_create_item(
        {
            "url": FRONTEND_MODULE,
            CONF_RESOURCE_TYPE_WS: "module",
        }
    )
    hass.data[_RESOURCE_REGISTERED] = True


def _same_resource(item: dict[str, Any]) -> bool:
    url = str(item.get("url", "")).split("?", 1)[0]
    return url == FRONTEND_MODULE.split("?", 1)[0] or url.endswith(
        "/amperepoint-q22-card.js"
    )


async def _async_ensure_dashboard(hass: HomeAssistant) -> None:
    """Create the AmperePoint dashboard with the bundled card and register its panel."""
    if hass.config.recovery_mode:
        return

    lovelace_data = hass.data.get(LOVELACE_DATA)
    dashboards = getattr(lovelace_data, "dashboards", None)
    if dashboards is None:
        _LOGGER.debug("Lovelace dashboards are not ready yet")
        return

    if DASHBOARD_URL_PATH in dashboards:
        hass.data[_DASHBOARD_REGISTERED] = True
        return

    store = lovelace_dashboard.LovelaceStorage(
        hass,
        {"id": DASHBOARD_STORAGE_ID, CONF_URL_PATH: DASHBOARD_URL_PATH},
    )

    try:
        try:
            await store.async_load(False)
        except ConfigNotFound:
            await store.async_save(_default_dashboard_config())
    except HomeAssistantError as err:
        _LOGGER.warning("Could not prepare the AmperePoint dashboard: %s", err)
        return

    dashboards[DASHBOARD_URL_PATH] = store

    async_register_built_in_panel(
        hass,
        "lovelace",
        sidebar_title=DASHBOARD_TITLE,
        sidebar_icon=DASHBOARD_ICON,
        frontend_url_path=DASHBOARD_URL_PATH,
        config={"mode": "storage"},
        require_admin=False,
    )
    hass.data[_DASHBOARD_REGISTERED] = True


def _default_dashboard_config() -> dict[str, Any]:
    return {
        "views": [
            {
                "title": DASHBOARD_TITLE,
                "path": "charger",
                "icon": DASHBOARD_ICON,
                "cards": [{"type": "custom:amperepoint-q22-card"}],
            }
        ]
    }
