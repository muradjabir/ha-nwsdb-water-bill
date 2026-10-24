"""The NWSDB Water Bill integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ACCOUNT_NUMBER, CONF_CDP_HOST, CONF_CDP_PORT, DEFAULT_CDP_HOST, DEFAULT_CDP_PORT
from .coordinator import NWSDBBillCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NWSDB Water Bill from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    account_no = entry.data[CONF_ACCOUNT_NUMBER]
    cdp_host = entry.data.get(CONF_CDP_HOST, DEFAULT_CDP_HOST)
    cdp_port = entry.data.get(CONF_CDP_PORT, DEFAULT_CDP_PORT)

    coordinator = NWSDBBillCoordinator(hass, account_no, cdp_host, cdp_port)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
