"""Sensor platform for Jira Filters integration."""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import JiraFiltersCoordinator

from .const import (
    DOMAIN,
    ATTR_FILTER_ID,
    ATTR_FILTER_NAME,
    ATTR_JQL,
    ATTR_TOTAL_COUNT,
    ATTR_MORE_ISSUES_AVAILABLE,
    ATTR_ISSUES,
    ATTR_MOST_RECENT_TICKET,
    ATTR_LAST_UPDATED,
    ATTR_ISSUE_KEY,
    ATTR_ISSUE_SUMMARY,
    ATTR_ISSUE_STATUS,
    ATTR_ISSUE_PRIORITY,
    ATTR_ISSUE_ASSIGNEE,
    ATTR_ISSUE_UPDATED,
    ATTR_ISSUE_CREATED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one sensor per configured Jira filter."""
    coordinator: JiraFiltersCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    async_add_entities(
        JiraFilterSensor(
            coordinator,
            config_entry.entry_id,
            filter_config["filter_id"],
            filter_config["filter_name"],
        )
        for filter_config in config_entry.data.get("filters", [])
    )


class JiraFilterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Jira Filter sensor."""

    def __init__(
        self,
        coordinator: JiraFiltersCoordinator,
        entry_id: str,
        filter_id: str,
        filter_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._filter_id = filter_id
        self._filter_name = filter_name
        self._attr_name = f"Jira Filter {filter_name}"
        # Scoped to the config entry so the same filter ID on two Jira sites doesn't clash
        self._attr_unique_id = f"{entry_id}_{filter_id}"

    @property
    def _filter_data(self) -> dict[str, Any] | None:
        """Return this filter's data from the last update, if any."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._filter_id)

    @property
    def available(self) -> bool:
        """Unavailable when the last update failed for this filter."""
        filter_data = self._filter_data
        return super().available and filter_data is not None and "error" not in filter_data

    @property
    def native_value(self) -> int | None:
        """Return the number of issues matching the filter."""
        filter_data = self._filter_data
        if filter_data is None or "error" in filter_data:
            return None
        return filter_data.get('total_count', 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        filter_data = self._filter_data
        if filter_data is None or "error" in filter_data:
            return {}
        
        attributes = {
            ATTR_FILTER_ID: filter_data.get('filter_id'),
            ATTR_FILTER_NAME: filter_data.get('filter_name'),
            ATTR_JQL: filter_data.get('jql'),
            ATTR_TOTAL_COUNT: filter_data.get('total_count', 0),
            ATTR_MORE_ISSUES_AVAILABLE: filter_data.get('total_count', 0) > min(10, len(filter_data.get('issues', []))),
            ATTR_LAST_UPDATED: filter_data.get('last_updated'),
        }

        # Add issues data (limited to avoid huge attributes)
        issues = filter_data.get('issues', [])
        if issues:
            # Limit to first 10 issues to avoid huge attributes
            limited_issues = issues[:10]
            attributes[ATTR_ISSUES] = [
                {
                    ATTR_ISSUE_KEY: issue.get('key'),
                    ATTR_ISSUE_SUMMARY: issue.get('summary'),
                    ATTR_ISSUE_STATUS: issue.get('status', {}).get('name'),
                    ATTR_ISSUE_PRIORITY: issue.get('priority'),
                    ATTR_ISSUE_ASSIGNEE: issue.get('assignee', {}).get('displayName') if issue.get('assignee') else None,
                    ATTR_ISSUE_UPDATED: issue.get('updated'),
                    ATTR_ISSUE_CREATED: issue.get('created'),
                }
                for issue in limited_issues
            ]

        # Add most recent ticket info
        most_recent = filter_data.get('most_recent_ticket')
        if most_recent:
            attributes[ATTR_MOST_RECENT_TICKET] = {
                'key': most_recent.get('key'),
                'summary': most_recent.get('summary'),
                'updated': most_recent.get('updated'),
                'updated_human': most_recent.get('updated_human')
            }

        return attributes

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:jira"
