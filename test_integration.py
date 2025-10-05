#!/usr/bin/env python3
"""
Test script to verify the Jira integration works with existing configuration.
This simulates what the Home Assistant integration would do.
"""

import json
import sys
import os
from datetime import datetime, timezone

# Add the custom_components directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from jira_filters.sensor import JiraFiltersCoordinator
from homeassistant.config_entries import ConfigEntry

class MockConfigEntry:
    """Mock ConfigEntry for testing."""
    def __init__(self, data):
        self.data = data

def test_jira_connection():
    """Test the Jira connection using existing configuration."""
    print("Testing Jira Filters Integration...")
    print("=" * 50)
    
    # Load existing configuration
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read('jira.conf')
        
        # Extract configuration
        base_url = config.get('jira', 'base_url')
        email = config.get('jira', 'email')
        api_token = config.get('jira', 'api_token')
        
        print(f"Base URL: {base_url}")
        print(f"Email: {email}")
        print(f"API Token: {api_token[:20]}...")
        print()
        
        # Create mock config entry
        config_data = {
            "base_url": base_url,
            "email": email,
            "api_token": api_token,
            "max_results": 10,  # Small number for testing
            "refresh_minutes": 5,
            "filters": [
                {
                    "filter_id": "12345",  # You'll need to replace with actual filter ID
                    "filter_name": "Test Filter"
                }
            ]
        }
        
        mock_entry = MockConfigEntry(config_data)
        
        # Test the coordinator
        print("Testing Jira API connection...")
        coordinator = JiraFiltersCoordinator(None, mock_entry)
        
        # Test the fetch method
        try:
            data = coordinator._fetch_jira_data()
            print("✅ Successfully connected to Jira API!")
            print()
            
            # Display results
            for filter_id, filter_data in data.items():
                print(f"Filter: {filter_data.get('filter_name', 'Unknown')} (ID: {filter_id})")
                print(f"  Total Issues: {filter_data.get('total_count', 0)}")
                print(f"  JQL: {filter_data.get('jql', 'N/A')}")
                
                most_recent = filter_data.get('most_recent_ticket')
                if most_recent:
                    print(f"  Most Recent: {most_recent.get('key')} - {most_recent.get('summary')}")
                    print(f"  Last Updated: {most_recent.get('updated_human', 'Unknown')}")
                else:
                    print("  Most Recent: No tickets found")
                
                print()
                
                # Show first few issues
                issues = filter_data.get('issues', [])
                if issues:
                    print("  Recent Issues:")
                    for issue in issues[:3]:  # Show first 3
                        print(f"    - {issue.get('key')}: {issue.get('summary')}")
                        print(f"      Status: {issue.get('status', {}).get('name', 'Unknown')}")
                        print(f"      Priority: {issue.get('priority', 'Unknown')}")
                        print(f"      Assignee: {issue.get('assignee', {}).get('displayName', 'Unassigned')}")
                        print()
                else:
                    print("  No issues found")
                print("-" * 30)
                
        except Exception as e:
            print(f"❌ Error connecting to Jira: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error reading configuration: {e}")
        return False
    
    print("✅ Integration test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_jira_connection()
    sys.exit(0 if success else 1)
