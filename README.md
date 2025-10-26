# Jira Filters Home Assistant Integration

A Home Assistant integration that connects to Jira Cloud instances to monitor filter results and display issue counts and details as sensors.



## Developer Note

- This is my first Home Assistant integration. I have relied heavily on AI for the integration workflows and Home Assistant components. Feel free to make suggestions, merge requests, or fork this.

## Features

- Connect to Jira Cloud using V3 API
- Monitor multiple Jira filters simultaneously
- Real-time issue counts and details
- Configurable refresh intervals (minimum 5 minutes)
- Detailed issue information including status, priority, assignee, and timestamps
- Most recent ticket tracking with human-readable timestamps
- **NEW**: Multiple Jira instance support with custom connection names
- **NEW**: Automatic filter name detection from Jira
- **NEW**: Manual refresh services for each connection
- **NEW**: Enhanced error handling and validation
- **NEW**: Post-setup configuration management

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
   - **Connection Name**: Optional name for this Jira instance (e.g., "Production", "Dev"). If not provided, will use the URL basename (e.g., "your-domain" from the URL)
   - **Max Results**: Maximum number of issues to fetch per filter (default: 100)
   - **Refresh Interval**: How often to update data in minutes (minimum: 5)

### Adding Filters

After the initial setup, you can add Jira filters to monitor:

1. **Filter ID**: The numeric ID of your Jira filter
2. **Filter Name**: Optional display name for the filter. If not provided, the system will automatically use the filter name from Jira

You can add multiple filters during setup or add more later through the integration options.

### Post-Setup Configuration

After the initial setup, you can manage your Jira Filters integration through the integration options:

1. Go to **Settings** > **Devices & Services**
2. Find your "Jira Filters - {connection_name}" integration
3. Click **Configure** to access the options menu
4. Available options:
   - **Edit Server Settings**: Update connection details, credentials, and refresh settings
   - **Manage Filters**: Add, edit, or remove filters
   - **Add Filter**: Add new filters to monitor
   - **Edit Filter**: Modify existing filter details
   - **Remove Filter**: Delete filters you no longer need

All changes take effect immediately without requiring a Home Assistant restart.

### Multiple Jira Instances

You can monitor multiple Jira instances by creating separate integration instances:

1. Each integration instance connects to one Jira Cloud instance
2. Each instance gets a unique name (e.g., "Jira Filters - Production", "Jira Filters - Dev")
3. Each instance has its own sensors and services
4. Services are named per instance (e.g., `jira_filters.refresh_production`, `jira_filters.refresh_dev`)

### Optimizing Filter Results

Since the integration only shows the first 10 issues in the sensor attributes, it's important to configure your Jira filters to return the most relevant results first:

#### Filter Configuration Best Practices

1. **Sort by Relevance**: Configure your Jira filter to sort by the most important criteria:
   - **Priority**: Sort by priority (High to Low) to see critical issues first
   - **Last Updated**: Sort by "Updated" (Newest first) to see recently modified issues
   - **Created Date**: Sort by "Created" (Newest first) to see new issues
   - **Due Date**: Sort by "Due Date" (Earliest first) to see overdue issues

2. **Use Specific Criteria**: Make your filters as specific as possible:
   - **Status**: Include specific statuses (e.g., "In Progress", "To Do", "Blocked")
   - **Assignee**: Filter by specific users or teams
   - **Project**: Focus on specific projects
   - **Labels**: Use relevant labels to narrow results

3. **Example Filter Configurations**:
   ```
   High Priority Issues:
   - Status: "In Progress", "To Do", "Blocked"
   - Priority: "High", "Highest"
   - Sort: Priority (High to Low), then Updated (Newest first)
   
   Recently Updated Issues:
   - Updated: "Last 7 days"
   - Sort: Updated (Newest first)
   
   Overdue Issues:
   - Due Date: "Overdue"
   - Sort: Due Date (Earliest first)
   ```

4. **Test Your Filters**: Before adding to Home Assistant:
   - Test the filter in Jira to ensure it returns relevant results
   - Check that the first 10 results are the most important ones
   - Adjust sorting and criteria as needed

#### Why This Matters

- The `more_issues_available` attribute will show `true` if there are more than 10 issues
- Only the first 10 issues appear in the `issues` attribute
- The `most_recent_ticket` shows the most recently updated issue from the results
- Proper sorting ensures the most critical/recent issues are visible in Home Assistant

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
  - `more_issues_available`: Boolean indicating if there are more than 10 issues (more than shown in attributes)
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

## Services

Each Jira Filters integration instance provides a manual refresh service:

- **Service Name**: `jira_filters.refresh_{connection_name}`
- **Description**: Manually refresh all filters for this Jira instance
- **Parameters**: None required

### Service Examples

**For a connection named "Production":**
```yaml
service: jira_filters.refresh_production
```

**For a connection named "Dev":**
```yaml
service: jira_filters.refresh_dev
```

**For a connection with URL basename "mycompany":**
```yaml
service: jira_filters.refresh_mycompany
```

### Service Usage in Automations

```yaml
automation:
  - alias: "Refresh Jira Data Daily"
    trigger:
      platform: time
      at: "09:00:00"
    action:
      - service: jira_filters.refresh_production
```

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

## Known Issues

### Current Limitations

1. **API Rate Limiting**: Jira Cloud has rate limits that may cause temporary failures during high usage; recommend refresh of 5 minutes or longer
2. **Large Filter Performance**: Filters with thousands of issues may cause timeouts or slow responses
3. **Authentication Token Expiry**: API tokens may expire and need to be regenerated periodically
4. **Network Connectivity**: Requires stable internet connection to Jira Cloud
5. **Filter Permissions**: Users must have appropriate permissions to access configured filters
6. **Non-standard Jira projects**: Integration assumes you are using a fairly standard project configuration


## FAQ

### General Questions

**Q: Can I use this with Jira Server (on-premises) instead of Jira Cloud?**
A: No, this integration is specifically designed for Jira Cloud using the v3 REST API. Jira Server uses different authentication methods and API endpoints. The v2 API is EOL, and I do not have access to any on‑premises installations for testing.

**Q: How many filters can I monitor?**
A: There's no hard limit, but performance may degrade with many filters. We recommend monitoring 10-20 filters maximum for optimal performance.

**Q: Can I monitor filters from different Jira instances?**
A: Yes! Each integration instance connects to one Jira Cloud instance. Create a new integration instance for each Jira instance you wish to monitor. Each instance will have a unique name like "Jira Filters - Production" and "Jira Filters - Dev".

**Q: What happens if my Jira instance is down?**
A: The sensors will show "unavailable" state and log errors. They will automatically recover when Jira is back online.

**Q: Why use a Jira Filter and not JQL?**
A: JQL requires significantly more parsing, validation, and error handling. Filters are managed and validated by Jira’s API, simplifying the integration while remaining flexible.

### Configuration Questions

**Q: What's the minimum refresh interval and why?**
A: The minimum is 5 minutes to respect Jira's API rate limits and prevent excessive API calls.


**Q: What's the maximum number of issues I can fetch per filter?**
A: The default is 100, but you can increase this. However, very large numbers may cause timeouts or performance issues.

**Q: Do I need to restart Home Assistant after adding new filters?**
A: No, you can add new filters through the integration configuration without restarting.

### New Features Questions

**Q: What is the connection name used for?**
A: The connection name helps you identify different Jira instances in Home Assistant. It appears in the integration title (e.g., "Jira Filters - Production") and in service names (e.g., `jira_filters.refresh_production`).

**Q: Do I have to provide a connection name?**
A: No, it's optional. If you don't provide one, the system will automatically extract the basename from your Jira URL (e.g., "mycompany" from "https://mycompany.atlassian.net").

**Q: Do I have to provide filter names?**
A: No, filter names are optional. If you don't provide one, the system will automatically fetch the filter name from Jira.

**Q: How do I manually refresh my Jira data?**
A: Each integration instance provides a refresh service. For a connection named "Production", use `jira_filters.refresh_production`. You can call this service from automations, scripts, or the Developer Tools.

**Q: Can I edit my integration settings after setup?**
A: Yes! Go to Settings > Devices & Services, find your integration, and click Configure. You can edit server settings, add/remove filters, and modify existing filters without restarting Home Assistant.

**Q: Why are only the first 10 issues shown in the attributes?**
A: To keep the sensor attributes manageable and prevent performance issues. The `more_issues_available` attribute indicates if there are additional issues. Configure your Jira filters with proper sorting to ensure the most relevant issues appear first.

**Q: How can I make sure I see the most important issues?**
A: Configure your Jira filters to sort by priority, due date, or last updated. This ensures the most critical or recent issues appear in the first 10 results that are shown in Home Assistant.

### Troubleshooting Questions

**Q: My sensor shows "unknown" state - what should I do?**
A: Check the Home Assistant logs for error messages. Common causes include invalid credentials, network issues, or incorrect filter IDs.

**Q: I'm getting authentication errors - what's wrong?**
A: Verify your email address and API token are correct. Make sure the API token hasn't expired and has the necessary permissions.

**Q: The integration worked before but stopped working - what changed?**
A: Your API token may have expired, or there may be network connectivity issues. Check the logs and verify your credentials.

**Q: Can I see more detailed error information?**
A: Yes, enable debug logging in Home Assistant for the `custom_components.jira_filters` logger to see detailed error messages.

**Q: Why are some issue details missing or showing as "None"?**
A: This depends on your Jira project configuration. Some fields may not be enabled or may not have values for certain issues.

### Performance Questions

**Q: The integration is slow - how can I improve performance?**
A: Reduce the number of filters, decrease `max_results`, or increase the refresh interval. Also ensure you have a stable internet connection.

**Q: Will this integration impact my Jira instance performance?**
A: The integration makes minimal API calls and respects rate limits, so it should have negligible impact on your Jira instance.

**Q: Can I run multiple instances of this integration?**
A: Yes, but each instance will make separate API calls, so consider the total impact on your Jira instance.


### Requirements

- `requests>=2.25.0`
- `certifi>=2021.5.25`

## License

This project is licensed under the MIT License.
