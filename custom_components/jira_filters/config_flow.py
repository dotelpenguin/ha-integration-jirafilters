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

from .const import DOMAIN, make_entry_unique_id

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

    Raises InvalidAuth for rejected credentials and CannotConnect for anything else.
    """
    base_url = data["base_url"].rstrip("/")
    display_name = await hass.async_add_executor_job(
        _test_jira_connection, base_url, data["email"], data["api_token"]
    )
    return {"title": f"Jira ({base_url})", "display_name": display_name}


def _test_jira_connection(base_url: str, email: str, api_token: str) -> str:
    """Call /myself and return the account's display name."""
    try:
        response = requests.get(
            f"{base_url}/rest/api/3/myself",
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except requests.exceptions.RequestException as err:
        _LOGGER.error("Failed to connect to Jira at %s: %s", base_url, err)
        raise CannotConnect from err

    if response.status_code in (401, 403):
        _LOGGER.warning("Jira rejected the credentials for %s (HTTP %s)", email, response.status_code)
        raise InvalidAuth
    try:
        response.raise_for_status()
        user_data = response.json()
    except (requests.exceptions.RequestException, ValueError) as err:
        _LOGGER.error("Unexpected response from Jira at %s: %s", base_url, err)
        raise CannotConnect from err

    _LOGGER.debug("Connected to Jira as %s", user_data.get("displayName", email))
    return user_data.get("displayName", email)


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
            await validate_input(self.hass, user_input)
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

            # Prevent adding the same Jira site + account twice
            await self.async_set_unique_id(
                make_entry_unique_id(user_input["base_url"], user_input["email"])
            )
            self._abort_if_unique_id_configured()

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

        # Reject a filter that is already configured
        if any(f["filter_id"] == user_input["filter_id"] for f in self._filters):
            return self.async_show_form(
                step_id="filter",
                data_schema=STEP_FILTER_DATA_SCHEMA,
                errors={"base": "duplicate_filter"}
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
            await validate_input(self.hass, user_input)
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
            new_unique_id = make_entry_unique_id(self._data["base_url"], self._data["email"])
            taken = any(
                e.unique_id == new_unique_id
                for e in self.hass.config_entries.async_entries(DOMAIN)
                if e.entry_id != self.config_entry.entry_id
            )
            if taken:
                errors["base"] = "already_configured"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=self._data,
                    unique_id=new_unique_id,
                )

        if not errors:
            # Reload the integration to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            
            return self.async_create_entry(title="", data={})

        # Create schema with current values as defaults for error form
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

        # Reject a filter that is already configured
        if any(f["filter_id"] == user_input["filter_id"] for f in self._filters):
            return self.async_show_form(
                step_id="add_filter",
                data_schema=STEP_OPTIONS_FILTER_SCHEMA,
                errors={"base": "duplicate_filter"}
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
