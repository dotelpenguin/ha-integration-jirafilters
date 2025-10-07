"""The Jira Filters integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# This integration is config-entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Jira Filters component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jira Filters from a config entry."""
    try:
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = entry.data

        # Forward the setup to the sensor platform.
        try:
            # Try newer API first
            await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
        except AttributeError:
            # Fallback to older API
            await hass.config_entries.async_forward_entry_setup(entry, "sensor")
        return True
    except Exception as err:
        _LOGGER.error("Error setting up Jira Filters integration: %s", err)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Try newer API first
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    except AttributeError:
        # Fallback to older API
        unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
