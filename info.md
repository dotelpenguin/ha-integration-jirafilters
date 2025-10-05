# Jira Filters

A Home Assistant integration that connects to Jira Cloud instances to monitor filter results and display issue counts and details as sensors.

## Features

- Connect to Jira Cloud using V3 API
- Monitor multiple Jira filters simultaneously
- Real-time issue counts and details
- Configurable refresh intervals (minimum 5 minutes)
- Detailed issue information including status, priority, assignee, and timestamps
- Most recent ticket tracking with human-readable timestamps

## Installation

1. Install this integration via HACS
2. Restart Home Assistant
3. Add the integration via the UI (Settings > Devices & Services > Add Integration)
4. Search for "Jira Filters" and follow the setup wizard

## Configuration

### Required Information

- **Base URL**: Your Jira Cloud URL (e.g., `https://your-domain.atlassian.net`)
- **Email**: Your Jira email address
- **API Token**: Your Jira API token (create at https://id.atlassian.com/manage-profile/security/api-tokens)

### Optional Settings

- **Max Results**: Maximum issues to fetch per filter (default: 100)
- **Refresh Interval**: Update frequency in minutes (minimum: 5)

### Adding Filters

You'll need the Filter ID from Jira:
1. Go to Issues > Search for issues in Jira
2. Create or select a saved filter
3. The Filter ID is in the URL: `?filter=12345`

## Usage

For each configured filter, the integration creates a sensor entity with:

- **State**: Total count of issues in the filter
- **Attributes**: Detailed issue information, most recent ticket, JQL query, etc.

### Example Automation

```yaml
automation:
  - alias: "High Priority Issues Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.jira_filter_high_priority
      above: 0
    action:
      service: notify.mobile_app_your_phone
      data:
        message: "You have {{ states('sensor.jira_filter_high_priority') }} high priority issues!"
```

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/dotelpenguin/ha-integration-jirafilters).

