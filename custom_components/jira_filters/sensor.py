"""Sensor platform for Jira Filters integration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    _LOGGER.error("requests library is not available. Please ensure it's installed.")
    raise

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    ATTR_FILTER_ID,
    ATTR_FILTER_NAME,
    ATTR_JQL,
    ATTR_TOTAL_COUNT,
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
    """Set up Jira Filters sensor based on a config entry."""
    try:
        coordinator = JiraFiltersCoordinator(hass, config_entry)
        
        # Fetch initial data so we have data when entities are added
        await coordinator.async_config_entry_first_refresh()

        # Create a sensor for each filter
        entities = []
        for filter_config in config_entry.data.get("filters", []):
            entities.append(
                JiraFilterSensor(
                    coordinator,
                    filter_config["filter_id"],
                    filter_config["filter_name"]
                )
            )

        async_add_entities(entities)
    except Exception as err:
        _LOGGER.error("Error setting up Jira Filters sensors: %s", err)
        raise


class JiraFiltersCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Jira API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.base_url = config_entry.data["base_url"].rstrip("/")
        self.email = config_entry.data["email"]
        self.api_token = config_entry.data["api_token"]
        self.max_results = config_entry.data.get("max_results", 100)
        self.refresh_minutes = config_entry.data.get("refresh_minutes", 5)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=self.refresh_minutes),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self.hass.async_add_executor_job(
                self._fetch_jira_data
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Jira API: {err}") from err

    def _fetch_jira_data(self) -> dict[str, Any]:
        """Fetch data from Jira API."""
        try:
            session = requests.Session()
            session.auth = (self.email, self.api_token)
            session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })

            results = {}
        except Exception as e:
            _LOGGER.error("Failed to create requests session: %s", e)
            raise
        
        for filter_config in self.config_entry.data.get("filters", []):
            filter_id = filter_config["filter_id"]
            filter_name = filter_config["filter_name"]
            
            try:
                # Get filter details
                filter_response = session.get(
                    f"{self.base_url}/rest/api/3/filter/{filter_id}",
                    timeout=30,
                    verify=True
                )
                filter_response.raise_for_status()
                filter_data = filter_response.json()
                
                jql = filter_data.get("jql", "")
                
                # Search for issues using the filter's JQL
                search_payload = {
                    'jql': jql,
                    'maxResults': self.max_results,
                    'fields': [
                        'summary',
                        'status',
                        'assignee',
                        'priority',
                        'issuetype',
                        'updated',
                        'created',
                        'parent',
                        'labels',
                        'project',
                        'components',
                        'issuelinks',
                    ],
                }

                # Prefer GET (legacy behavior) for widest compatibility; fall back to POST and newer endpoints if needed
                try:
                    _LOGGER.debug("Using GET /rest/api/3/search for filter %s", filter_id)
                    get_response = session.get(
                        f"{self.base_url}/rest/api/3/search",
                        params={
                            'jql': jql,
                            'maxResults': self.max_results,
                            'fields': 'summary,status,assignee,priority,issuetype,updated,created,parent,labels,project,components,issuelinks',
                        },
                        timeout=30,
                        verify=True,
                    )
                    get_response.raise_for_status()
                    search_response = get_response
                except requests.exceptions.HTTPError:
                    status = getattr(get_response, 'status_code', None)
                    try:
                        body = get_response.text
                    except Exception:
                        body = None
                    _LOGGER.warning(
                        "GET /rest/api/3/search failed (status %s) for filter %s; body: %s. Trying POST",
                        status,
                        filter_id,
                        body,
                    )
                    try:
                        _LOGGER.debug("Using POST /rest/api/3/search for filter %s", filter_id)
                        post_response = session.post(
                            f"{self.base_url}/rest/api/3/search",
                            json=search_payload,
                            timeout=30,
                            verify=True,
                        )
                        post_response.raise_for_status()
                        search_response = post_response
                    except requests.exceptions.HTTPError:
                        post_status = getattr(post_response, 'status_code', None)
                        try:
                            post_body = post_response.text
                        except Exception:
                            post_body = None
                        # Jira says to migrate to /rest/api/3/search/jql; try that next
                        _LOGGER.warning(
                            "Switching to POST /rest/api/3/search/jql for filter %s after status %s; body: %s",
                            filter_id,
                            post_status,
                            post_body,
                        )
                        jql_response = session.post(
                            f"{self.base_url}/rest/api/3/search/jql",
                            json=search_payload,
                            timeout=30,
                            verify=True,
                        )
                        try:
                            jql_body = jql_response.text if jql_response.status_code >= 400 else None
                        except Exception:
                            jql_body = None
                        jql_response.raise_for_status()
                        search_response = jql_response
                search_data = search_response.json()
                
                issues = search_data.get("issues", [])
                simplified_issues = [self._simplify_issue(issue) for issue in issues]
                
                # Find most recent ticket
                most_recent_ticket = None
                if simplified_issues:
                    sorted_issues = sorted(simplified_issues, key=lambda x: x.get('updated', ''), reverse=True)
                    most_recent = sorted_issues[0]
                    most_recent_ticket = {
                        'key': most_recent.get('key'),
                        'summary': most_recent.get('summary'),
                        'updated': most_recent.get('updated'),
                        'updated_human': self._format_human_time(most_recent.get('updated')) if most_recent.get('updated') else None
                    }
                
                results[filter_id] = {
                    'filter_id': filter_id,
                    'filter_name': filter_name,
                    'jql': jql,
                    'total_count': len(simplified_issues),
                    'issues': simplified_issues,
                    'most_recent_ticket': most_recent_ticket,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }
                
            except requests.exceptions.RequestException as e:
                _LOGGER.error(f"Error fetching data for filter {filter_id}: {e}")
                results[filter_id] = {
                    'filter_id': filter_id,
                    'filter_name': filter_name,
                    'jql': '',
                    'total_count': 0,
                    'issues': [],
                    'most_recent_ticket': None,
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                    'error': str(e)
                }

        return results

    def _simplify_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Simplify Jira issue data for Home Assistant."""
        fields = issue.get('fields', {})
        status = fields.get('status') or {}
        assignee = fields.get('assignee') or {}
        priority = fields.get('priority') or {}
        issue_type = fields.get('issuetype') or {}
        parent = fields.get('parent') or {}

        return {
            'id': issue.get('id'),
            'key': issue.get('key'),
            'summary': fields.get('summary'),
            'status': {
                'name': status.get('name'),
                'category': (status.get('statusCategory') or {}).get('name') if isinstance(status.get('statusCategory'), dict) else None
            },
            'assignee': {
                'accountId': assignee.get('accountId'),
                'displayName': assignee.get('displayName'),
                'emailAddress': assignee.get('emailAddress')
            } if assignee else None,
            'priority': priority.get('name') if priority else None,
            'issueType': issue_type.get('name') if issue_type else None,
            'parent': {
                'key': parent.get('key'),
                'id': parent.get('id'),
                'summary': (parent.get('fields') or {}).get('summary') if isinstance(parent.get('fields'), dict) else None
            } if parent else None,
            'labels': fields.get('labels', []),
            'created': fields.get('created'),
            'updated': fields.get('updated')
        }

    def _format_human_time(self, timestamp_str: str) -> str:
        """Convert ISO timestamp to human-readable relative time."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            diff = now - dt
            
            if diff.days > 0:
                if diff.days == 1:
                    return "1 day ago"
                elif diff.days < 7:
                    return f"{diff.days} days ago"
                elif diff.days < 30:
                    weeks = diff.days // 7
                    return f"{weeks} week{'s' if weeks != 1 else ''} ago"
                else:
                    months = diff.days // 30
                    return f"{months} month{'s' if months != 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                return "just now"
        except Exception:
            return "unknown time"


class JiraFilterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Jira Filter sensor."""

    def __init__(
        self,
        coordinator: JiraFiltersCoordinator,
        filter_id: str,
        filter_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._filter_id = filter_id
        self._filter_name = filter_name
        self._attr_name = f"Jira Filter {filter_name}"
        self._attr_unique_id = f"jira_filter_{filter_id}"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if not self.coordinator.data or self._filter_id not in self.coordinator.data:
            return 0
        
        filter_data = self.coordinator.data[self._filter_id]
        return filter_data.get('total_count', 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or self._filter_id not in self.coordinator.data:
            return {}

        filter_data = self.coordinator.data[self._filter_id]
        
        attributes = {
            ATTR_FILTER_ID: filter_data.get('filter_id'),
            ATTR_FILTER_NAME: filter_data.get('filter_name'),
            ATTR_JQL: filter_data.get('jql'),
            ATTR_TOTAL_COUNT: filter_data.get('total_count', 0),
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
