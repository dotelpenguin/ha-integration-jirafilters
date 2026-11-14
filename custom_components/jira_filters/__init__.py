"""The Jira Filters integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LEGACY_UNIQUE_ID_PREFIX, make_entry_unique_id

_LOGGER = logging.getLogger(__name__)

# This integration is config-entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Jira Filters component."""
    return True


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move pre-1.2.0 sensor unique IDs to the entry-scoped format.

    Entity IDs (sensor.xxx) are kept, so dashboards and automations keep working.
    """
    registry = er.async_get(hass)

    @callback
    def _migrate(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        if not entity_entry.unique_id.startswith(LEGACY_UNIQUE_ID_PREFIX):
            return None
        filter_id = entity_entry.unique_id[len(LEGACY_UNIQUE_ID_PREFIX):]
        new_unique_id = f"{entry.entry_id}_{filter_id}"
        if registry.async_get_entity_id(entity_entry.domain, DOMAIN, new_unique_id):
            return None
        _LOGGER.debug(
            "Migrating %s unique_id %s -> %s",
            entity_entry.entity_id,
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)


@callback
def _async_backfill_entry_unique_id(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Give entries created before 1.2.0 a unique ID so duplicates are blocked."""
    if entry.unique_id is not None:
        return
    unique_id = make_entry_unique_id(entry.data["base_url"], entry.data["email"])
    taken = any(
        other.unique_id == unique_id
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    )
    if taken:
        _LOGGER.warning(
            "Jira Filters entry '%s' duplicates another entry for the same Jira site and account; "
            "consider removing one of them",
            entry.title,
        )
        return
    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jira Filters from a config entry."""
    try:
        _async_backfill_entry_unique_id(hass, entry)
        await _async_migrate_unique_ids(hass, entry)

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {
            "data": entry.data,
            "coordinator": None
        }

        # Forward the setup to the sensor platform.
        try:
            # Try newer API first
            await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
        except AttributeError:
            # Fallback to older API
            await hass.config_entries.async_forward_entry_setup(entry, "sensor")
        
        # Register services with connection name
        connection_name = entry.data.get("name", "Jira")
        service_name = f"refresh_{connection_name.lower().replace(' ', '_')}"
        
        async def handle_refresh_service(call: ServiceCall) -> None:
            """Handle refresh service call."""
            coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
            if coordinator:
                await coordinator.async_request_refresh()
                _LOGGER.info("Manually refreshed Jira Filters data for %s", connection_name)
            else:
                _LOGGER.warning("No coordinator available for %s", connection_name)
        
        # Register the service
        hass.services.async_register(
            DOMAIN,
            service_name,
            handle_refresh_service,
            schema=vol.Schema({}),
        )
        
        _LOGGER.info("Registered service: %s.%s", DOMAIN, service_name)
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
        # Unregister services
        connection_name = entry.data.get("name", "Jira")
        service_name = f"refresh_{connection_name.lower().replace(' ', '_')}"
        
        try:
            hass.services.async_remove(DOMAIN, service_name)
            _LOGGER.info("Unregistered service: %s.%s", DOMAIN, service_name)
        except ValueError:
            # Service might not exist, which is fine
            pass
        
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
