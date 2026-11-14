"""Data update coordinator for the Jira Filters integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=self.refresh_minutes),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data for all filters."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_jira_data)
        except requests.exceptions.HTTPError as err:
            status = err.response.status_code if err.response is not None else None
            if status == 401:
                raise UpdateFailed(
                    "Authentication failed. Check the email and API token in the integration settings."
                ) from err
            if status == 403:
                raise UpdateFailed("Access forbidden. Check your permissions for the Jira filters.") from err
            if status == 404:
                raise UpdateFailed("Not found. Check the Jira base URL and filter IDs.") from err
            raise UpdateFailed(f"Error communicating with the Jira API: {err}") from err
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Error communicating with the Jira API: {err}") from err

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
            last_error: requests.exceptions.RequestException | None = None
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

                # Fetch the issue details (up to max_results)
                search_response = session.post(
                    f"{self.base_url}/rest/api/3/search/jql",
                    json=search_payload,
                    timeout=30,
                    verify=True,
                )
                search_response.raise_for_status()
                search_data = search_response.json()

                issues = search_data.get("issues", [])
                simplified_issues = [self._simplify_issue(issue) for issue in issues]

                # /search/jql has no "total"; ask Jira for the full match count
                total_count = self._fetch_approximate_count(session, jql, filter_id)
                if total_count is None:
                    total_count = len(simplified_issues)
                
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
                    'total_count': total_count,
                    'returned_count': len(simplified_issues),
                    'issues': simplified_issues,
                    'most_recent_ticket': most_recent_ticket,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }
                
            except requests.exceptions.RequestException as e:
                last_error = e
                _LOGGER.warning("Error fetching data for filter %s: %s", filter_id, e)
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

        filters = self.config_entry.data.get("filters", [])
        if filters and last_error is not None and all("error" in r for r in results.values()):
            # Nothing could be fetched: treat it as a connection problem
            raise last_error

        return results

    def _fetch_approximate_count(
        self, session: requests.Session, jql: str, filter_id: str
    ) -> int | None:
        """Return the total number of issues matching the JQL, or None on failure."""
        try:
            response = session.post(
                f"{self.base_url}/rest/api/3/search/approximate-count",
                json={"jql": jql},
                timeout=30,
                verify=True,
            )
            response.raise_for_status()
            count = response.json().get("count")
            return int(count) if count is not None else None
        except (requests.exceptions.RequestException, ValueError, TypeError) as err:
            _LOGGER.debug(
                "approximate-count failed for filter %s, falling back to returned issue count: %s",
                filter_id,
                err,
            )
            return None

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
