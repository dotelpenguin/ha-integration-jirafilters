# Jira Filters Home Assistant Integration

A Home Assistant integration that connects to Jira Cloud instances to monitor filter results and display issue counts and details as sensors.

## Features

- Connect to Jira Cloud using V3 API
- Monitor multiple Jira filters simultaneously
- Real-time issue counts and details
- Configurable refresh intervals (minimum 5 minutes)
- Detailed issue information including status, priority, assignee, and timestamps
- Most recent ticket tracking with human-readable timestamps

## Installation

### Via HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Install "Jira Filters" from HACS
3. Restart Home Assistant
4. Add the integration via the UI

### Manual Installation

1. Copy the `custom_components/jira_filters` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the integration via the UI

## Configuration

### Initial Setup

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Jira Filters"
4. Enter your Jira connection details:
   - **Base URL**: Your Jira Cloud URL (e.g., `https://your-domain.atlassian.net`)
   - **Email**: Your Jira email address
   - **API Token**: Your Jira API token (not your password)
   - **Max Results**: Maximum number of issues to fetch per filter (default: 100)
   - **Refresh Interval**: How often to update data in minutes (minimum: 5)

### Adding Filters

After the initial setup, you can add Jira filters to monitor:

1. **Filter ID**: The numeric ID of your Jira filter
2. **Filter Name**: Optional display name for the filter

You can add multiple filters during setup or add more later.

### Getting Your Jira API Token

1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Give it a label (e.g., "Home Assistant")
4. Copy the generated token

### Finding Filter IDs

1. In Jira, go to **Issues** > **Search for issues**
2. Create or select a saved filter
3. The Filter ID is in the URL: `https://your-domain.atlassian.net/issues/?filter=12345`

## Entities

For each configured filter, the integration creates a sensor entity with:

- **State**: Total count of issues in the filter
- **Attributes**:
  - `filter_id`: The Jira filter ID
  - `filter_name`: Display name of the filter
  - `jql`: The JQL query used by the filter
  - `total_count`: Number of issues returned
  - `issues`: Array of issue details (limited to first 10)
  - `most_recent_ticket`: Details of the most recently updated ticket
  - `last_updated`: When the data was last refreshed

### Issue Details

Each issue in the `issues` attribute includes:
- `key`: Issue key (e.g., "PROJ-123")
- `summary`: Issue summary/title
- `status`: Current status name
- `priority`: Priority level
- `assignee`: Assignee display name
- `updated`: Last update timestamp
- `created`: Creation timestamp

## Usage Examples

### Automation Example

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

### Template Example

```yaml
template:
  - sensor:
      - name: "Most Recent Jira Issue"
        state: >
          {{ state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket').key if state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket') else 'None' }}
        attributes:
          summary: >
            {{ state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket').summary if state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket') else 'None' }}
          updated: >
            {{ state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket').updated_human if state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket') else 'None' }}
```

## Troubleshooting

### Connection Issues

- Verify your Jira URL is correct and accessible
- Check that your API token is valid and not expired
- Ensure your email address matches your Jira account

### Filter Issues

- Verify the Filter ID is correct
- Ensure you have permission to access the filter
- Check that the filter is not empty

### Performance

- Large filters with many issues may take longer to load
- Consider reducing `max_results` if you experience timeouts
- Increase `refresh_minutes` to reduce API calls

## Development

This integration is based on the existing `jira_view_filter.py` script and extends it for Home Assistant integration.

### Requirements

- `requests>=2.25.0`
- `certifi>=2021.5.25`

## License

This project is licensed under the MIT License.
