"""Config flow for Jira Filters integration."""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    _LOGGER.error("requests library is not available. Please ensure it's installed.")
    raise

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

def _extract_basename_from_url(url: str) -> str:
    """Extract basename from URL for default connection name."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # Extract subdomain (e.g., "raptortech1" from "raptortech1.atlassian.net")
        if "." in hostname:
            return hostname.split(".")[0]
        return hostname
    except Exception:
        return "Jira"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("base_url"): str,
        vol.Required("email"): str,
        vol.Required("api_token"): str,
        vol.Optional("name"): str,
        vol.Optional("max_results", default=100): int,
        vol.Optional("refresh_minutes", default=5): int,
    }
)

STEP_FILTER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("filter_id"): str,
        vol.Optional("filter_name"): str,
    }
)

STEP_OPTIONS_SERVER_SCHEMA = vol.Schema(
    {
        vol.Required("base_url"): str,
        vol.Required("email"): str,
        vol.Required("api_token"): str,
        vol.Optional("name"): str,
        vol.Optional("max_results", default=100): int,
        vol.Optional("refresh_minutes", default=5): int,
    }
)

STEP_OPTIONS_FILTER_SCHEMA = vol.Schema(
    {
        vol.Required("filter_id"): str,
        vol.Optional("filter_name"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    base_url = data["base_url"].rstrip("/")
    email = data["email"]
    api_token = data["api_token"]

    # Test connection to Jira API
    try:
        response = await hass.async_add_executor_job(
            _test_jira_connection, base_url, email, api_token
        )
        if not response:
            raise CannotConnect

        return {"title": f"Jira ({base_url})"}

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Error connecting to Jira: %s", err)
        raise CannotConnect from err


def _test_jira_connection(base_url: str, email: str, api_token: str) -> bool:
    """Test connection to Jira API."""
    try:
        session = requests.Session()
        session.auth = (email, api_token)
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        # Test with a simple API call to get current user
        response = session.get(
            f"{base_url}/rest/api/3/myself",
            timeout=30,
            verify=True
        )
        response.raise_for_status()
        
        user_data = response.json()
        _LOGGER.info("Successfully connected to Jira as: %s", user_data.get('displayName', email))
        return True

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Failed to connect to Jira: %s", err)
        return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jira Filters."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}
        self._filters = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Set default name if not provided
            if not user_input.get("name"):
                user_input["name"] = _extract_basename_from_url(user_input["base_url"])
            
            self._data = user_input
            return await self.async_step_filter()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_filter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a Jira filter."""
        if user_input is None:
            return self.async_show_form(
                step_id="filter", data_schema=STEP_FILTER_DATA_SCHEMA
            )

        # Validate filter exists and get filter name
        try:
            # First validate the filter exists
            filter_valid, jira_filter_name = await self.hass.async_add_executor_job(
                _validate_filter,
                self._data["base_url"],
                self._data["email"],
                self._data["api_token"],
                user_input["filter_id"]
            )
            if not filter_valid:
                return self.async_show_form(
                    step_id="filter",
                    data_schema=STEP_FILTER_DATA_SCHEMA,
                    errors={"base": "invalid_filter"}
                )
            
            # Add filter to list - use provided name or Jira name
            filter_name = user_input.get("filter_name") or jira_filter_name
            self._filters.append({
                "filter_id": user_input["filter_id"],
                "filter_name": filter_name
            })
            
            _LOGGER.info("Filter added successfully: %s", filter_name)
            
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception validating filter")
            return self.async_show_form(
                step_id="filter",
                data_schema=STEP_FILTER_DATA_SCHEMA,
                errors={"base": "unknown"}
            )

        # Ask if user wants to add more filters
        return await self.async_step_add_more()

    async def async_step_add_more(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add more filters."""
        if user_input is None:
            return self.async_show_form(
                step_id="add_more",
                data_schema=vol.Schema({
                    vol.Required("add_more", default=False): bool
                })
            )

        if user_input["add_more"]:
            return await self.async_step_filter()

        # Create the entry with connection name in title
        title = f"Jira Filters - {self._data.get('name', 'Jira')}"
        
        return self.async_create_entry(
            title=title,
            data={
                **self._data,
                "filters": self._filters
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Jira Filters."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._data = dict(config_entry.data)
        self._filters = list(config_entry.data.get("filters", []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is None:
            return self.async_show_menu(
                step_id="init",
                menu_options={
                    "server_settings": "Edit Server Settings",
                    "manage_filters": "Manage Filters"
                }
            )

        return await getattr(self, f"async_step_{user_input['next_step_id']}")()

    async def async_step_server_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle server settings configuration."""
        if user_input is None:
            # Create schema with current values as defaults
            schema = vol.Schema({
                vol.Required("base_url", default=self._data.get("base_url", "")): str,
                vol.Required("email", default=self._data.get("email", "")): str,
                vol.Required("api_token", default=self._data.get("api_token", "")): str,
                vol.Optional("name", default=self._data.get("name", "")): str,
                vol.Optional("max_results", default=self._data.get("max_results", 100)): int,
                vol.Optional("refresh_minutes", default=self._data.get("refresh_minutes", 5)): int,
            })
            
            return self.async_show_form(
                step_id="server_settings",
                data_schema=schema,
                description_placeholders={
                    "current_url": self._data.get("base_url", ""),
                    "current_email": self._data.get("email", "")
                }
            )

        errors = {}

        try:
            # Test the new connection settings
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Set default name if not provided
            if not user_input.get("name"):
                user_input["name"] = _extract_basename_from_url(user_input["base_url"])
            
            # Update the data with new settings
            self._data.update(user_input)
            
            # Update the config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self._data
            )
            
            # Reload the integration to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            
            return self.async_create_entry(title="", data={})

        # Create schema with current values as defaults for error form
        schema = vol.Schema({
            vol.Required("base_url", default=self._data.get("base_url", "")): str,
            vol.Required("email", default=self._data.get("email", "")): str,
            vol.Required("api_token", default=self._data.get("api_token", "")): str,
            vol.Optional("max_results", default=self._data.get("max_results", 100)): int,
            vol.Optional("refresh_minutes", default=self._data.get("refresh_minutes", 5)): int,
        })
        
        return self.async_show_form(
            step_id="server_settings",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "current_url": self._data.get("base_url", ""),
                "current_email": self._data.get("email", "")
            }
        )

    async def async_step_manage_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle filter management."""
        if user_input is None:
            # Show current filters and options
            filter_list = "\n".join([
                f"• {f['filter_name']} (ID: {f['filter_id']})"
                for f in self._filters
            ]) if self._filters else "No filters configured"
            
            return self.async_show_form(
                step_id="manage_filters",
                data_schema=vol.Schema({
                    vol.Required("action", default="add"): vol.In({
                        "add": "Add New Filter",
                        "edit": "Edit Existing Filter", 
                        "remove": "Remove Filter"
                    })
                }),
                description_placeholders={
                    "current_filters": filter_list
                }
            )

        if user_input["action"] == "add":
            return await self.async_step_add_filter()
        elif user_input["action"] == "edit":
            return await self.async_step_edit_filter()
        elif user_input["action"] == "remove":
            return await self.async_step_remove_filter()

    async def async_step_add_filter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a new filter."""
        if user_input is None:
            return self.async_show_form(
                step_id="add_filter",
                data_schema=STEP_OPTIONS_FILTER_SCHEMA
            )

        # Validate filter exists and get filter name
        try:
            # First validate the filter exists
            filter_valid, jira_filter_name = await self.hass.async_add_executor_job(
                _validate_filter,
                self._data["base_url"],
                self._data["email"],
                self._data["api_token"],
                user_input["filter_id"]
            )
            if not filter_valid:
                return self.async_show_form(
                    step_id="add_filter",
                    data_schema=STEP_OPTIONS_FILTER_SCHEMA,
                    errors={"base": "invalid_filter"}
                )
            
            # Add filter to list - use provided name or Jira name
            filter_name = user_input.get("filter_name") or jira_filter_name
            self._filters.append({
                "filter_id": user_input["filter_id"],
                "filter_name": filter_name
            })
            
            _LOGGER.info("Filter added successfully: %s", filter_name)
            
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception validating filter")
            return self.async_show_form(
                step_id="add_filter",
                data_schema=STEP_OPTIONS_FILTER_SCHEMA,
                errors={"base": "unknown"}
            )

        # Update the config entry with new filters
        self._data["filters"] = self._filters
        _LOGGER.info("Updating config entry with filters: %s", self._filters)
        
        # Update the config entry data
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._data
        )

        # Force a reload by calling the unload and setup functions
        _LOGGER.info("Forcing integration reload to apply filter changes")
        try:
            # Unload the current integration
            await self.hass.config_entries.async_unload(self.config_entry.entry_id)
            # Set it up again with the new data
            await self.hass.config_entries.async_setup(self.config_entry.entry_id)
        except Exception as e:
            _LOGGER.error("Error reloading integration: %s", e)
            # Fallback to the standard reload
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        return self.async_create_entry(title="", data={})

    async def async_step_edit_filter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle editing an existing filter."""
        if not self._filters:
            return self.async_show_form(
                step_id="edit_filter",
                data_schema=vol.Schema({}),
                errors={"base": "no_filters"},
                description_placeholders={
                    "message": "No filters configured. Please add a filter first."
                }
            )
            
        if user_input is None:
            # Show list of filters to edit
            filter_options = {
                f["filter_id"]: f"{f['filter_name']} (ID: {f['filter_id']})"
                for f in self._filters
            }
            
            return self.async_show_form(
                step_id="edit_filter",
                data_schema=vol.Schema({
                    vol.Required("filter_to_edit"): vol.In(filter_options)
                })
            )

        # Find the filter to edit
        filter_to_edit = next(
            f for f in self._filters if f["filter_id"] == user_input["filter_to_edit"]
        )
        
        # Store the filter to edit in the flow data
        self._filter_to_edit = filter_to_edit
        
        return await self.async_step_edit_filter_details()

    async def async_step_edit_filter_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle editing filter details."""
        if user_input is None:
            filter_to_edit = getattr(self, '_filter_to_edit', None)
            if not filter_to_edit:
                return self.async_abort(reason="no_filter_selected")
                
            return self.async_show_form(
                step_id="edit_filter_details",
                data_schema=vol.Schema({
                    vol.Required("filter_id", default=filter_to_edit["filter_id"]): str,
                    vol.Required("filter_name", default=filter_to_edit["filter_name"]): str,
                })
            )

        # Get the filter to edit
        filter_to_edit = getattr(self, '_filter_to_edit', None)
        if not filter_to_edit:
            return self.async_abort(reason="no_filter_selected")

        # Validate filter exists and get filter name
        try:
            # First validate the filter exists
            filter_valid, jira_filter_name = await self.hass.async_add_executor_job(
                _validate_filter,
                self._data["base_url"],
                self._data["email"],
                self._data["api_token"],
                user_input["filter_id"]
            )
            if not filter_valid:
                return self.async_show_form(
                    step_id="edit_filter_details",
                    data_schema=vol.Schema({
                        vol.Required("filter_id", default=filter_to_edit["filter_id"]): str,
                        vol.Required("filter_name", default=filter_to_edit["filter_name"]): str,
                    }),
                    errors={"base": "invalid_filter"}
                )
            
            # Update the filter in the list - use provided name or Jira name
            filter_name = user_input.get("filter_name") or jira_filter_name
            for i, filter_item in enumerate(self._filters):
                if filter_item["filter_id"] == filter_to_edit["filter_id"]:
                    self._filters[i] = {
                        "filter_id": user_input["filter_id"],
                        "filter_name": filter_name
                    }
                    break
            
            _LOGGER.info("Filter updated successfully: %s", filter_name)
            
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception validating filter")
            return self.async_show_form(
                step_id="edit_filter_details",
                data_schema=vol.Schema({
                    vol.Required("filter_id", default=filter_to_edit["filter_id"]): str,
                    vol.Required("filter_name", default=filter_to_edit["filter_name"]): str,
                }),
                errors={"base": "unknown"}
            )

        # Update the config entry
        self._data["filters"] = self._filters
        _LOGGER.info("Updating config entry with edited filters: %s", self._filters)
        
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._data
        )

        # Force a reload by calling the unload and setup functions
        _LOGGER.info("Forcing integration reload to apply filter edit changes")
        try:
            # Unload the current integration
            await self.hass.config_entries.async_unload(self.config_entry.entry_id)
            # Set it up again with the new data
            await self.hass.config_entries.async_setup(self.config_entry.entry_id)
        except Exception as e:
            _LOGGER.error("Error reloading integration: %s", e)
            # Fallback to the standard reload
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        return self.async_create_entry(title="", data={})

    async def async_step_remove_filter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle removing a filter."""
        if not self._filters:
            return self.async_show_form(
                step_id="remove_filter",
                data_schema=vol.Schema({}),
                errors={"base": "no_filters"},
                description_placeholders={
                    "message": "No filters configured. Please add a filter first."
                }
            )
            
        if user_input is None:
            # Show list of filters to remove
            filter_options = {
                f["filter_id"]: f"{f['filter_name']} (ID: {f['filter_id']})"
                for f in self._filters
            }
            
            return self.async_show_form(
                step_id="remove_filter",
                data_schema=vol.Schema({
                    vol.Required("filter_to_remove"): vol.In(filter_options)
                })
            )

        # Remove the filter
        self._filters = [
            f for f in self._filters if f["filter_id"] != user_input["filter_to_remove"]
        ]

        # Update the config entry
        self._data["filters"] = self._filters
        _LOGGER.info("Updating config entry with removed filters: %s", self._filters)
        
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._data
        )

        # Force a reload by calling the unload and setup functions
        _LOGGER.info("Forcing integration reload to apply filter removal changes")
        try:
            # Unload the current integration
            await self.hass.config_entries.async_unload(self.config_entry.entry_id)
            # Set it up again with the new data
            await self.hass.config_entries.async_setup(self.config_entry.entry_id)
        except Exception as e:
            _LOGGER.error("Error reloading integration: %s", e)
            # Fallback to the standard reload
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

        return self.async_create_entry(title="", data={})


def _validate_filter(base_url: str, email: str, api_token: str, filter_id: str) -> tuple[bool, str]:
    """Validate that a Jira filter exists and is accessible. Returns (is_valid, filter_name)."""
    try:
        session = requests.Session()
        session.auth = (email, api_token)
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        response = session.get(
            f"{base_url}/rest/api/3/filter/{filter_id}",
            timeout=30,
            verify=True
        )
        response.raise_for_status()
        
        # Extract filter name from response
        filter_data = response.json()
        filter_name = filter_data.get('name', f'Filter {filter_id}')
        
        return True, filter_name

    except requests.exceptions.RequestException:
        return False, ""


def _test_filter_count(base_url: str, email: str, api_token: str, filter_id: str, max_results: int = 100) -> dict[str, Any]:
    """Test a filter and return the count and basic info."""
    try:
        session = requests.Session()
        session.auth = (email, api_token)
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        # Get filter details
        filter_response = session.get(
            f"{base_url}/rest/api/3/filter/{filter_id}",
            timeout=30,
            verify=True
        )
        filter_response.raise_for_status()
        filter_data = filter_response.json()
        
        jql = filter_data.get("jql", "")
        filter_name = filter_data.get("name", f"Filter {filter_id}")
        
        # Search for issues using the filter's JQL
        search_payload = {
            'jql': jql,
            'maxResults': max_results,
            'fields': ['summary', 'status', 'assignee', 'priority', 'issuetype', 'updated', 'created'],
        }

        # Try the new JQL endpoint first
        try:
            jql_response = session.post(
                f"{base_url}/rest/api/3/search/jql",
                json=search_payload,
                timeout=30,
                verify=True,
            )
            jql_response.raise_for_status()
            search_response = jql_response
        except requests.exceptions.HTTPError:
            # Fall back to legacy endpoints
            try:
                post_response = session.post(
                    f"{base_url}/rest/api/3/search",
                    json=search_payload,
                    timeout=30,
                    verify=True,
                )
                post_response.raise_for_status()
                search_response = post_response
            except requests.exceptions.HTTPError:
                get_response = session.get(
                    f"{base_url}/rest/api/3/search",
                    params={
                        'jql': jql,
                        'maxResults': max_results,
                        'fields': 'summary,status,assignee,priority,issuetype,updated,created',
                    },
                    timeout=30,
                    verify=True,
                )
                get_response.raise_for_status()
                search_response = get_response
        
        search_data = search_response.json()
        issues = search_data.get("issues", [])
        
        return {
            "success": True,
            "filter_name": filter_name,
            "jql": jql,
            "total_count": len(issues),
            "max_results": max_results,
            "sample_issues": [
                {
                    "key": issue.get("key"),
                    "summary": issue.get("fields", {}).get("summary", ""),
                    "status": issue.get("fields", {}).get("status", {}).get("name", ""),
                }
                for issue in issues[:5]  # Show first 5 issues as sample
            ]
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "filter_name": f"Filter {filter_id}",
            "jql": "",
            "total_count": 0
        }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
