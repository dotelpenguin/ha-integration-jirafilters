# Jira Filters for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/dotelpenguin/ha-integration-jirafilters)](https://github.com/dotelpenguin/ha-integration-jirafilters/releases)
[![HACS Validation](https://github.com/dotelpenguin/ha-integration-jirafilters/actions/workflows/hacs.yml/badge.svg)](https://github.com/dotelpenguin/ha-integration-jirafilters/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/dotelpenguin/ha-integration-jirafilters/actions/workflows/hassfest.yml/badge.svg)](https://github.com/dotelpenguin/ha-integration-jirafilters/actions/workflows/hassfest.yml)
[![License: MIT](https://img.shields.io/github/license/dotelpenguin/ha-integration-jirafilters)](LICENSE)

Turn your saved **Jira Cloud filters** into Home Assistant sensors. Each sensor shows how many issues match the filter, with the top issues, their status, priority and assignee available as attributes — ready for dashboards, notifications and automations.

<!-- Screenshot: add an image of a sensor / dashboard card here, e.g. ![Jira Filters dashboard](docs/images/dashboard.png) -->

## Features

- One sensor per saved Jira filter, with the true total issue count
- Multiple filters per connection, and multiple Jira sites or accounts
- Filter names fetched from Jira automatically (or set your own)
- Top 10 issues and the most recently updated ticket as attributes
- Add, edit and remove filters from the UI — no restart needed
- Manual refresh action per connection

## Installation

### HACS (recommended)

Jira Filters is in the HACS default store.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dotelpenguin&repository=ha-integration-jirafilters&category=integration)

1. Click the button above, or search HACS for **Jira Filters**.
2. Click **Download**, then restart Home Assistant.

### Manual

Copy `custom_components/jira_filters` into your Home Assistant `config/custom_components/` folder and restart. See [MANUAL_INSTALL.md](MANUAL_INSTALL.md) for details.

## Setup

[![Open your Home Assistant instance and start setting up Jira Filters.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=jira_filters)

Or go to **Settings → Devices & services → Add integration → Jira Filters**.

### 1. Connection

| Field | Description |
| --- | --- |
| **Jira Base URL** | Your Jira Cloud URL, e.g. `https://your-domain.atlassian.net` |
| **Email Address** | The email of your Atlassian account |
| **API Token** | An Atlassian API token — [create one here](https://id.atlassian.com/manage-profile/security/api-tokens) |
| **Connection Name** | Optional. Defaults to the first part of the URL (`your-domain`) |
| **Max Results** | Issues fetched per filter for the attributes (default 100) |
| **Refresh Interval** | Minutes between updates (default 5) |

### 2. Filters

Enter the **Filter ID** of a saved filter. You'll find it in the filter's URL:
`https://your-domain.atlassian.net/issues/?filter=12345` → `12345`.

Leave **Filter Name** empty to use the name from Jira. Add as many filters as you like.

### Changing settings later

Go to **Settings → Devices & services → Jira Filters → Configure** to edit the connection or to add, edit and remove filters. Changes apply immediately.

To monitor another Jira site or account, add the integration again. Each site + email combination can be added once.

## Sensors

Each filter creates a sensor, e.g. `sensor.jira_filter_my_open_issues`.

**State:** total number of issues matching the filter.

| Attribute | Description |
| --- | --- |
| `filter_id` / `filter_name` | The Jira filter |
| `jql` | The filter's JQL query |
| `total_count` | Total issues matching the filter |
| `issues` | The first 10 issues: `key`, `summary`, `status`, `priority`, `assignee`, `created`, `updated` |
| `more_issues_available` | `true` when there are more issues than shown in `issues` |
| `most_recent_ticket` | The most recently updated issue: `key`, `summary`, `updated`, `updated_human` |
| `last_updated` | When the data was last refreshed |

> **Tip:** `issues` holds the first 10 results in the filter's own sort order. Sort your filter in Jira (by priority, updated or due date) so the issues that matter most come first.

## Actions

Each connection gets a refresh action named after the connection, for example `jira_filters.refresh_production` for a connection named "Production".

```yaml
action: jira_filters.refresh_production
```

## Examples

**Notify when high-priority issues appear**

```yaml
automation:
  - alias: "Jira: high priority issues"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.jira_filter_high_priority
        above: 0
    actions:
      - action: notify.mobile_app_your_phone
        data:
          message: "{{ states('sensor.jira_filter_high_priority') }} high priority Jira issues"
```

**Show the most recent ticket**

```yaml
template:
  - sensor:
      - name: "Latest Jira ticket"
        state: >
          {{ (state_attr('sensor.jira_filter_my_filter', 'most_recent_ticket') or {}).get('key', 'none') }}
```

## Troubleshooting

- **Cannot connect / authentication failed** — check the URL, that the email matches your Atlassian account, and that the API token hasn't expired.
- **Filter not found** — check the Filter ID and that your account can view the filter.
- **Search errors** — Jira's search API rejects queries with no conditions (for example only `ORDER BY created`). Add at least one condition such as `project = ABC`.

For more detail, enable debug logging:

```yaml
logger:
  logs:
    custom_components.jira_filters: debug
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more.

## FAQ

**Does this work with Jira Server / Data Center?**
No. It supports Jira Cloud only (REST API v3).

**Why saved filters instead of raw JQL?**
Jira validates and manages filters, so you can change a query in Jira without touching Home Assistant.

**How many filters can I add?**
There's no hard limit. Each filter costs a few API calls per refresh, so keep the interval at 5 minutes or more if you have many.

**Why are only 10 issues in the attributes?**
To keep Home Assistant's state and database small. The sensor state and `total_count` always show the full count.

## Contributing

Issues and pull requests are welcome — please use the [issue tracker](https://github.com/dotelpenguin/ha-integration-jirafilters/issues).

This is my first Home Assistant integration, and I've used AI tools to help build it. Suggestions, merge requests and forks are all welcome.

## License

[MIT](LICENSE)
