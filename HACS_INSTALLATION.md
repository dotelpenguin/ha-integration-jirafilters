# HACS Installation Guide

## Installing via HACS

### Step 1: Add Custom Repository

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three dots menu (⋮) in the top right
4. Select **Custom repositories**
5. Add the repository:
   - **Repository**: `https://github.com/dotelpenguin/ha-integration-jirafilters`
   - **Category**: Integration
6. Click **Add**

### Step 2: Install the Integration

1. Search for "Jira Filters" in HACS
2. Click on the integration
3. Click **Download**
4. Restart Home Assistant

### Step 3: Configure the Integration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Jira Filters"
4. Follow the setup wizard

## Requirements

- Home Assistant 2023.1.0 or later
- HACS 1.6.0 or later
- Jira Cloud account with API token

## Getting Your Jira API Token

1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Give it a label (e.g., "Home Assistant")
4. Copy the generated token

## Finding Filter IDs

1. In Jira, go to **Issues** > **Search for issues**
2. Create or select a saved filter
3. The Filter ID is in the URL: `https://your-domain.atlassian.net/issues/?filter=12345`

## Troubleshooting

### Integration Not Found
- Ensure HACS is properly installed and updated
- Check that the repository was added correctly
- Restart Home Assistant after installation

### Connection Issues
- Verify your Jira URL is correct
- Check that your API token is valid and not expired
- Ensure your email matches your Jira account

### Filter Issues
- Verify the Filter ID is correct
- Check that you have permission to access the filter
- Ensure the filter is not empty

