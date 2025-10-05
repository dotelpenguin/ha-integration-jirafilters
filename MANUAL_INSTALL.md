# Manual Installation Guide

Since HACS is having issues downloading the integration, here's how to install it manually:

## Method 1: Git Clone (Recommended)

1. **SSH into your Home Assistant server** or use the Terminal add-on
2. **Navigate to the custom_components directory**:
   ```bash
   cd /config/custom_components
   ```
3. **Clone the repository**:
   ```bash
   git clone https://github.com/dotelpenguin/ha-integration-jirafilters.git jira_filters
   ```
4. **Restart Home Assistant**

## Method 2: Download and Extract

1. **Download the repository**:
   - Go to: https://github.com/dotelpenguin/ha-integration-jirafilters
   - Click the green "Code" button
   - Click "Download ZIP"
2. **Extract the files**:
   - Extract the downloaded ZIP file
   - Copy the `custom_components/jira_filters` folder to `/config/custom_components/`
3. **Restart Home Assistant**

## Method 3: Using Home Assistant Terminal Add-on

If you have the Terminal add-on installed:

1. **Open Terminal add-on**
2. **Run these commands**:
   ```bash
   cd /config/custom_components
   git clone https://github.com/dotelpenguin/ha-integration-jirafilters.git jira_filters
   ```
3. **Restart Home Assistant**

## Verify Installation

After installation, verify the files are in place:

```bash
ls -la /config/custom_components/jira_filters/
```

You should see these files:
- `__init__.py`
- `config_flow.py`
- `sensor.py`
- `const.py`
- `manifest.json`
- `strings.json`
- `translations/en.json`

## Configure the Integration

1. **Go to Settings** > **Devices & Services**
2. **Click "Add Integration"**
3. **Search for "Jira Filters"**
4. **Follow the setup wizard**

## Troubleshooting

If you still get errors:

1. **Check file permissions**:
   ```bash
   chmod -R 755 /config/custom_components/jira_filters/
   ```

2. **Clear Home Assistant cache**:
   - Stop Home Assistant
   - Delete `/config/.storage/core.config_entries`
   - Restart Home Assistant

3. **Check the logs** for specific error messages

## Why Manual Installation?

HACS sometimes has issues with:
- Repository structure changes
- GitHub API rate limits
- Network connectivity issues
- Cache problems

Manual installation bypasses these issues and gives you direct control over the integration files.
