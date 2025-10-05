"""Constants for the Jira Filters integration."""

DOMAIN = "jira_filters"

# Configuration keys
CONF_BASE_URL = "base_url"
CONF_EMAIL = "email"
CONF_API_TOKEN = "api_token"
CONF_MAX_RESULTS = "max_results"
CONF_REFRESH_MINUTES = "refresh_minutes"
CONF_FILTERS = "filters"
CONF_FILTER_ID = "filter_id"
CONF_FILTER_NAME = "filter_name"

# Default values
DEFAULT_MAX_RESULTS = 100
DEFAULT_REFRESH_MINUTES = 5
MIN_REFRESH_MINUTES = 5

# Sensor attributes
ATTR_FILTER_ID = "filter_id"
ATTR_FILTER_NAME = "filter_name"
ATTR_JQL = "jql"
ATTR_TOTAL_COUNT = "total_count"
ATTR_ISSUES = "issues"
ATTR_MOST_RECENT_TICKET = "most_recent_ticket"
ATTR_LAST_UPDATED = "last_updated"

# Issue attributes
ATTR_ISSUE_KEY = "key"
ATTR_ISSUE_SUMMARY = "summary"
ATTR_ISSUE_STATUS = "status"
ATTR_ISSUE_PRIORITY = "priority"
ATTR_ISSUE_ASSIGNEE = "assignee"
ATTR_ISSUE_UPDATED = "updated"
ATTR_ISSUE_CREATED = "created"
