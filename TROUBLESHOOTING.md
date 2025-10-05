# Troubleshooting Guide

## Integration Setup Errors

If you're experiencing setup errors with the Jira Filters integration, follow these steps:

### 1. Clear Home Assistant Cache

The most common issue is that Home Assistant is loading a cached version of the integration. To fix this:

1. **Stop Home Assistant** completely
2. **Clear the cache** by deleting these directories (if they exist):
   - `/config/.storage/core.config_entries`
   - `/config/.storage/core.entity_registry`
   - `/config/custom_components/jira_filters/__pycache__/`
3. **Restart Home Assistant**

### 2. Manual Installation (if HACS fails)

If HACS is having issues downloading the integration:

1. **Download the integration manually**:
   ```bash
   cd /config/custom_components
   git clone https://github.com/dotelpenguin/ha-integration-jirafilters.git jira_filters
   ```

2. **Restart Home Assistant**

### 3. Check Home Assistant Version

This integration requires Home Assistant 2023.1.0 or later. Check your version in:
- **Settings** > **System** > **Info**

### 4. Verify Integration Files

Make sure all required files are present in `/config/custom_components/jira_filters/`:
- `__init__.py`
- `config_flow.py`
- `sensor.py`
- `const.py`
- `manifest.json`
- `strings.json`
- `translations/en.json`

### 5. Check Logs

Look for specific error messages in the Home Assistant logs:
- **Settings** > **System** > **Logs**

Common error patterns:
- `'ConfigEntries' object has no attribute 'async_forward_entry_setup'` - Cache issue, restart HA
- `requests library is not available` - Dependencies not installed
- `Error communicating with Jira API` - Check your Jira credentials

### 6. Reinstall Integration

If all else fails:

1. **Remove the integration** from Home Assistant UI
2. **Delete the custom_components/jira_filters directory**
3. **Restart Home Assistant**
4. **Reinstall via HACS** or manual installation
5. **Reconfigure the integration**

### 7. Dependencies

Make sure these Python packages are available:
- `requests>=2.25.0`
- `certifi>=2021.5.25`

These should be automatically installed by Home Assistant, but if you're having issues, you can install them manually in your Home Assistant environment.

## Still Having Issues?

If you're still experiencing problems:

1. **Check the GitHub repository** for the latest version
2. **Create an issue** on GitHub with:
   - Your Home Assistant version
   - Full error logs
   - Steps to reproduce the issue
3. **Join the Home Assistant community** for additional support
