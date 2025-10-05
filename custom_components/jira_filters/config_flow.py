"""Config flow for Jira Filters integration."""
from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("base_url"): str,
        vol.Required("email"): str,
        vol.Required("api_token"): str,
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

        # Validate filter exists and is accessible
        try:
            filter_valid = await self.hass.async_add_executor_job(
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
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception validating filter")
            return self.async_show_form(
                step_id="filter",
                data_schema=STEP_FILTER_DATA_SCHEMA,
                errors={"base": "unknown"}
            )

        # Add filter to list
        filter_name = user_input.get("filter_name") or f"Filter {user_input['filter_id']}"
        self._filters.append({
            "filter_id": user_input["filter_id"],
            "filter_name": filter_name
        })

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

        # Create the entry
        return self.async_create_entry(
            title=self._data.get("title", "Jira Filters"),
            data={
                **self._data,
                "filters": self._filters
            }
        )


def _validate_filter(base_url: str, email: str, api_token: str, filter_id: str) -> bool:
    """Validate that a Jira filter exists and is accessible."""
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
        return True

    except requests.exceptions.RequestException:
        return False


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
