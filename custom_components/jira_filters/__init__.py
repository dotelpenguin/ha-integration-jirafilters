"""The Jira Filters integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN, LEGACY_UNIQUE_ID_PREFIX, SERVICE_REFRESH, make_entry_unique_id
from .coordinator import JiraFiltersCoordinator

_LOGGER = logging.getLogger(__name__)

# This integration is config-entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR]

REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the integration-wide refresh action."""
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _async_handle_refresh, schema=REFRESH_SCHEMA
    )
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
    _async_backfill_entry_unique_id(hass, entry)
    await _async_migrate_unique_ids(hass, entry)

    coordinator = JiraFiltersCoordinator(hass, entry)
    # Raises ConfigEntryNotReady if Jira can't be reached, so Home Assistant retries setup
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_legacy_service(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        legacy_service = entry_data.get("legacy_service")
        if legacy_service and hass.services.has_service(DOMAIN, legacy_service):
            hass.services.async_remove(DOMAIN, legacy_service)
    return unload_ok


def _legacy_service_name(entry: ConfigEntry) -> str:
    """Per-connection action name kept for existing automations."""
    return f"refresh_{slugify(entry.data.get('name') or 'jira')}"


@callback
def _async_register_legacy_service(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the deprecated jira_filters.refresh_<connection> action."""
    service_name = _legacy_service_name(entry)
    if service_name == SERVICE_REFRESH or hass.services.has_service(DOMAIN, service_name):
        _LOGGER.debug("Not registering %s.%s: name already in use", DOMAIN, service_name)
        return

    async def _handle(call: ServiceCall) -> None:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_refresh()

    hass.services.async_register(DOMAIN, service_name, _handle, schema=vol.Schema({}))
    hass.data[DOMAIN][entry.entry_id]["legacy_service"] = service_name


async def _async_handle_refresh(call: ServiceCall) -> None:
    """Refresh one connection, or all connections when none is given."""
    hass = call.hass
    entries = hass.data.get(DOMAIN, {})
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)

    if entry_id:
        if entry_id not in entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"entry_id": entry_id},
            )
        targets = [entries[entry_id]]
    else:
        targets = list(entries.values())

    for entry_data in targets:
        await entry_data["coordinator"].async_refresh()
