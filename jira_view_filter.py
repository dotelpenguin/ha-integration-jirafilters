#!/usr/bin/env python3
"""
Jira script to get and output one or more Jira filter results to JSON using the JIRA V3 API.

- Accepts either a single filter ID or a list of filter IDs
- Fetches each filter's JQL and executes it using the v3 API with proper pagination
- Supports nextPageToken pagination for large result sets
- Outputs a combined JSON keyed by filter name (or ID if name unavailable)
- Includes progress tracking for large result sets

Usage examples:
  python jira_view_filter.py --filters 12345
  python jira_view_filter.py --filters 12345,67890 --pretty
  python jira_view_filter.py --config jira.conf --filters 12345 --max-results 200
"""

import sys
import json
import os
import logging
import sys as _sys
import configparser
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

import requests
import certifi


# Logging: default WARNING to keep stdout clean for JSON
logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def format_human_time(timestamp_str: str) -> str:
    """Convert ISO timestamp to human-readable relative time."""
    try:
        # Parse the ISO timestamp
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        if diff.days > 0:
            if diff.days == 1:
                return "1 day ago"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"{weeks} week{'s' if weeks != 1 else ''} ago"
            else:
                months = diff.days // 30
                return f"{months} month{'s' if months != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "just now"
    except Exception:
        return "unknown time"


class JiraClient:
    """Minimal Jira REST client for running saved filters."""

    def __init__(self, config_file: str = "jira.conf") -> None:
        self.config = self._load_config(config_file)
        self.base_url = self._require_key('base_url').rstrip('/')
        # Support `username` or `email` for Jira Cloud
        self.username = self._require_key('username', aliases=['email'])
        # Jira Cloud uses API token as password for basic auth
        self.api_token = self._require_key('api_token', allow_placeholder=False)
        self.verify_ssl = self._getboolean_key('verify_ssl', default=True)
        self.default_max_results = self._getint_key('max_results', default=100)

        # Prebuild session
        self.session = requests.Session()
        self.session.auth = (self.username, self.api_token)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

    def _load_config(self, config_file: str) -> configparser.ConfigParser:
        if not os.path.exists(config_file):
            logger.error(f"Configuration file {config_file} not found")
            sys.exit(1)

        cfg = configparser.ConfigParser()
        cfg.read(config_file)
        return cfg

    def _require_key(self, key: str, aliases: Optional[List[str]] = None, allow_placeholder: bool = False) -> str:
        search_keys = [key] + (aliases or [])
        search_sections = ['DEFAULT', 'jira']
        for section in search_sections:
            for k in search_keys:
                if self.config.has_option(section, k):
                    value = self.config.get(section, k).strip()
                    if not value:
                        logger.error(f"Empty configuration value for: {k}")
                        sys.exit(1)
                    if not allow_placeholder and (value.startswith('your_') or 'your-' in value or 'your ' in value):
                        logger.error(f"Configuration value for {k} looks like a placeholder; please update it in jira.conf")
                        sys.exit(1)
                    return value
        logger.error(f"Missing configuration key: one of {search_keys}")
        sys.exit(1)

    def _getboolean_key(self, key: str, default: bool = False) -> bool:
        for section in ['DEFAULT', 'jira']:
            if self.config.has_option(section, key):
                try:
                    return self.config.getboolean(section, key)
                except Exception:
                    logger.warning(f"Invalid boolean for {key}; using default {default}")
                    return default
        return default

    def _getint_key(self, key: str, default: int = 0) -> int:
        for section in ['DEFAULT', 'jira']:
            if self.config.has_option(section, key):
                try:
                    return self.config.getint(section, key)
                except Exception:
                    logger.warning(f"Invalid integer for {key}; using default {default}")
                    return default
        return default

    def _verify(self) -> Any:
        # Use certifi when verify_ssl is True; otherwise disable verification
        return certifi.where() if self.verify_ssl else False

    def _get(self, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        try:
            response = self.session.get(url, timeout=30, verify=self._verify(), **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise

    def get_filter(self, filter_id: str) -> Optional[Dict[str, Any]]:
        """Return filter object including name and JQL."""
        try:
            resp = self._get(f"/rest/api/3/filter/{filter_id}")
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"Filter not found: {filter_id}")
                return None
            logger.error(f"Failed to fetch filter {filter_id}: {e.response.status_code} {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for filter {filter_id}: {e}")
            return None

    def search_issues(self, jql: str, max_results: int) -> List[Dict[str, Any]]:
        """Run a JQL search and return simplified issues up to max_results using v3 API with pagination."""
        collected: List[Dict[str, Any]] = []
        next_page_token = None
        total_fetched = 0

        fields = [
            'summary', 'status', 'assignee', 'priority', 'issuetype',
            'updated', 'created', 'parent', 'labels', 'project', 'components', 'issuelinks'
        ]

        while total_fetched < max_results:
            remaining = max_results - total_fetched
            max_results_this_page = min(1000, remaining)  # v3 API supports up to 1000 per page
            
            params = {
                'jql': jql,
                'maxResults': max_results_this_page,
                'fields': ','.join(fields)
            }
            
            # Add nextPageToken if we have one
            if next_page_token:
                params['nextPageToken'] = next_page_token
            
            try:
                resp = self._get('/rest/api/3/search/jql', params=params)
                data = resp.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Search failed: {e}")
                break
            issues = data.get('issues', [])
            
            for issue in issues:
                if total_fetched >= max_results:
                    break
                collected.append(self._simplify_issue(issue))
                total_fetched += 1
            
            # Progress tracking for large result sets
            if total_fetched % 100 == 0 and total_fetched > 0:
                logger.info(f"  Fetched {total_fetched} issues...")
            
            # Check if this is the last page
            if data.get('isLast', True) or not issues:
                break
                
            # Get next page token
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break

        # Final progress message
        if total_fetched > 0:
            logger.info(f"  Total issues fetched: {total_fetched}")

        return collected

    def _simplify_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        fields = issue.get('fields', {})
        status = fields.get('status') or {}
        assignee = fields.get('assignee') or {}
        priority = fields.get('priority') or {}
        issue_type = fields.get('issuetype') or {}
        parent = fields.get('parent') or {}

        return {
            'id': issue.get('id'),
            'key': issue.get('key'),
            'summary': fields.get('summary'),
            'status': {
                'name': status.get('name'),
                'category': (status.get('statusCategory') or {}).get('name') if isinstance(status.get('statusCategory'), dict) else None
            },
            'assignee': {
                'accountId': assignee.get('accountId'),
                'displayName': assignee.get('displayName'),
                'emailAddress': assignee.get('emailAddress')
            } if assignee else None,
            'priority': priority.get('name') if priority else None,
            'issueType': issue_type.get('name') if issue_type else None,
            'parent': {
                'key': parent.get('key'),
                'id': parent.get('id'),
                'summary': (parent.get('fields') or {}).get('summary') if isinstance(parent.get('fields'), dict) else None
            } if parent else None,
            'labels': fields.get('labels', []),
            'created': fields.get('created'),
            'updated': fields.get('updated')
        }


def run_filters(client: JiraClient, filter_ids: List[str], max_results: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch each filter's JQL, run it, and return an array of results."""
    results: List[Dict[str, Any]] = []
    for filter_id in filter_ids:
        filter_obj = client.get_filter(filter_id)
        if not filter_obj:
            continue
        name = filter_obj.get('name') or f"filter_{filter_id}"
        jql = filter_obj.get('jql')
        if not jql:
            logger.error(f"Filter has no JQL: {filter_id}")
            continue
        limit = max_results if max_results is not None else client.default_max_results
        issues = client.search_issues(jql=jql, max_results=limit)
        
        # Find the most recent ticket and its update time
        most_recent_issue = None
        most_recent_time = None
        if issues:
            # Sort by updated time to find the most recent
            sorted_issues = sorted(issues, key=lambda x: x.get('updated', ''), reverse=True)
            most_recent_issue = sorted_issues[0]
            most_recent_time = most_recent_issue.get('updated')
        
        result = {
            'filter_id': str(filter_id),
            'filter_name': name,
            'jql': jql,
            'total_returned': len(issues),
            'issues': issues
        }
        
        # Add most recent ticket information
        if most_recent_issue:
            result['most_recent_ticket'] = {
                'key': most_recent_issue.get('key'),
                'summary': most_recent_issue.get('summary'),
                'updated': most_recent_time,
                'updated_human': format_human_time(most_recent_time) if most_recent_time else None
            }
        else:
            result['most_recent_ticket'] = None
            
        results.append(result)
    return results


def _print_pretty_results(results: List[Dict[str, Any]], use_color: bool = True) -> None:
    """Render human-readable tables to stdout for the provided results array.
    Shows a summary per filter and a compact issues table.
    """
    try:
        from shutil import get_terminal_size
    except Exception:
        get_terminal_size = None

    width = 120
    try:
        if get_terminal_size:
            width = max(80, min(160, get_terminal_size().columns))
    except Exception:
        pass

    # ANSI styles
    if use_color and not _sys.stdout.isatty():
        use_color = False
    def style(text: str, *codes: str) -> str:
        if not use_color:
            return text
        start = ''.join(codes)
        end = "\033[0m"
        return f"{start}{text}{end}"
    C_BOLD = "\033[1m"
    C_DIM = "\033[2m"
    C_RED = "\033[31m"
    C_GREEN = "\033[32m"
    C_YELLOW = "\033[33m"
    C_BLUE = "\033[34m"
    C_MAGENTA = "\033[35m"
    C_CYAN = "\033[36m"
    C_WHITE = "\033[37m"

    sep = "=" * width
    print(style(sep, C_CYAN))
    print(style("JIRA FILTER RESULTS", C_BOLD, C_CYAN))
    print(style(sep, C_CYAN))

    for idx, entry in enumerate(results, 1):
        filter_name = entry.get('filter_name') or entry.get('filter_id')
        header_line = f"[{idx}] {filter_name} (ID: {entry.get('filter_id')})"
        print(style(header_line, C_BOLD, C_MAGENTA))
        print(style("JQL:", C_BOLD), entry.get('jql', ''))
        print(style("Total Returned:", C_BOLD), entry.get('total_returned', 0))
        
        # Display most recent ticket information
        most_recent = entry.get('most_recent_ticket')
        if most_recent:
            print(style("Most Recent:", C_BOLD), f"{most_recent.get('key')} - {most_recent.get('summary')}")
            print(style("Last Updated:", C_BOLD), most_recent.get('updated_human', 'unknown'))
        else:
            print(style("Most Recent:", C_BOLD), "No tickets found")
            
        print(style("-" * width, C_CYAN))

        # Build a compact issues table
        issues: List[Dict[str, Any]] = entry.get('issues', [])
        if not issues:
            print("(no issues)")
            print(sep)
            continue

        # Columns: KEY, SUMMARY, STATUS, ASSIGNEE, PRIORITY, UPDATED
        headers = ["KEY", "SUMMARY", "STATUS", "ASSIGNEE", "PRIORITY", "UPDATED"]
        col_widths = [12, 50, 18, 22, 10, 20]

        # Adjust widths to terminal
        total_width = sum(col_widths) + len(col_widths) - 1
        if total_width > width:
            shrink = total_width - width
            # Shrink SUMMARY primarily
            col_widths[1] = max(20, col_widths[1] - shrink)

        def trunc(text: Optional[str], max_len: int) -> str:
            if text is None:
                return ''
            s = str(text).replace('\n', ' ').strip()
            return s[: max_len - 1] + '…' if len(s) > max_len else s

        # Print header (colored, but underline computed from plain text)
        header_plain = " | ".join(trunc(h, w).ljust(w) for h, w in zip(headers, col_widths))
        header_colored = " | ".join(style(trunc(h, w).ljust(w), C_BOLD, C_WHITE) for h, w in zip(headers, col_widths))
        print(header_colored)
        print(style("-" * len(header_plain), C_CYAN))

        for issue in issues:
            status = issue.get('status') or {}
            assignee = issue.get('assignee') or {}

            # Color mappings
            status_name = status.get('name') or ''
            priority_name = issue.get('priority') or ''
            def color_status(text: str) -> str:
                t = text.lower()
                if any(k in t for k in ["done", "closed", "resolved"]):
                    return style(text, C_GREEN, C_BOLD)
                if any(k in t for k in ["in progress", "in review", "qa", "testing"]):
                    return style(text, C_YELLOW, C_BOLD)
                if any(k in t for k in ["todo", "to do", "open", "backlog"]):
                    return style(text, C_BLUE, C_BOLD)
                if any(k in t for k in ["blocked", "failed", "error"]):
                    return style(text, C_RED, C_BOLD)
                return style(text, C_WHITE)

            def color_priority(text: str) -> str:
                t = text.lower()
                if "highest" in t:
                    return style(text, C_RED, C_BOLD)
                if "high" in t:
                    return style(text, C_RED)
                if "medium" in t or "mid" in t:
                    return style(text, C_YELLOW)
                if "low" in t:
                    return style(text, C_GREEN)
                if "lowest" in t:
                    return style(text, C_BLUE, C_DIM)
                return text if not use_color else style(text, C_WHITE)

            key_cell = trunc(issue.get('key'), col_widths[0]).ljust(col_widths[0])
            summary_cell = trunc(issue.get('summary'), col_widths[1]).ljust(col_widths[1])
            status_cell = trunc(status_name, col_widths[2]).ljust(col_widths[2])
            assignee_name = assignee.get('displayName') or assignee.get('emailAddress') or ''
            assignee_cell = trunc(assignee_name, col_widths[3]).ljust(col_widths[3])
            priority_cell = trunc(priority_name, col_widths[4]).ljust(col_widths[4])
            updated_cell = trunc(issue.get('updated'), col_widths[5]).ljust(col_widths[5])

            # Apply colors after padding to preserve alignment
            row = [
                style(key_cell, C_BOLD, C_WHITE),
                summary_cell,
                color_status(status_cell),
                style(assignee_cell, C_DIM),
                color_priority(priority_cell),
                style(updated_cell, C_DIM)
            ]
            print(" | ".join(row))

        print(style(sep, C_CYAN))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Fetch Jira filter results and output combined JSON keyed by filter name')
    parser.add_argument('--filters', '--filter', '-f', dest='filters', required=True,
                        help='Filter ID or comma-separated list of filter IDs (e.g., 12345 or 12345,67890)')
    parser.add_argument('--config', '-c', default='jira.conf', help='Configuration file path')
    parser.add_argument('--max-results', '-m', type=int, default=None,
                        help='Maximum issues per filter to return (overrides config max_results)')
    parser.add_argument('--pretty', '-p', action='store_true', help='Human-readable table output')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging to stderr')

    args = parser.parse_args()

    # Adjust logging level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if args.verbose else logging.WARNING)

    try:
        client = JiraClient(args.config)
        filter_ids = [fid.strip() for fid in args.filters.split(',') if fid.strip()]
        if not filter_ids:
            logger.error('No valid filter IDs provided')
            sys.exit(1)

        results = run_filters(client, filter_ids, max_results=args.max_results)
        if args.pretty:
            _print_pretty_results(results)
        else:
            if len(results) > 1:
                grouped = {
                    r['filter_id']: {
                        'filter_name': r.get('filter_name'),
                        'jql': r.get('jql'),
                        'total_returned': r.get('total_returned', 0),
                        'most_recent_ticket': r.get('most_recent_ticket'),
                        'issues': r.get('issues', [])
                    }
                    for r in results
                }
                print(json.dumps(grouped, separators=(",", ":")))
            else:
                # Preserve original array shape when a single filter is requested
                print(json.dumps(results, separators=(",", ":")))
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        error_output = {
            'error': str(exc),
            'source': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        print(json.dumps(error_output))
        sys.exit(1)


if __name__ == '__main__':
    main()
