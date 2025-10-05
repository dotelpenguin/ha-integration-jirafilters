# Installation Guide

## Quick Start

1. **Copy the integration to Home Assistant:**
   ```bash
   # Copy the custom_components folder to your Home Assistant
   cp -r custom_components/jira_filters /path/to/homeassistant/custom_components/
   ```

2. **Restart Home Assistant**

3. **Add the integration:**
   - Go to Settings > Devices & Services
   - Click "Add Integration"
   - Search for "Jira Filters"
   - Enter your Jira details

## Configuration Details

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

## Testing

Run the test script to verify your configuration:

```bash
python test_integration.py
```

Note: You'll need to update the filter ID in the test script to match your actual Jira filter.

## Troubleshooting

- **Connection issues**: Verify URL, email, and API token
- **Filter not found**: Check Filter ID and permissions
- **Performance**: Reduce max_results or increase refresh interval
