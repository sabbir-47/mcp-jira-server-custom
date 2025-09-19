#!/usr/bin/env python3
"""
MCP JIRA Server
===============

A Model Context Protocol (MCP) server for interacting with JIRA.
This server provides tools for creating issues, searching, updating, and managing JIRA projects.

Requirements:
- mcp (Model Context Protocol library)
- jira (Python JIRA library)
- asyncio for async operations
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource,
    )
except ImportError:
    print("MCP library not found. Install with: pip install mcp")
    exit(1)

try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    print("JIRA library not found. Install with: pip install jira")
    exit(1)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPJiraServer:
    """MCP Server for JIRA integration."""
    
    def __init__(self):
        self.server = Server("mcp-jira-server")
        self.jira_client: Optional[JIRA] = None
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.jira_token = os.getenv("JIRA_TOKEN")  # API token or password
        
        # Register handlers
        self.register_handlers()
    
    def register_handlers(self):
        """Register MCP handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available JIRA tools."""
            return [
                Tool(
                    name="jira_search_issues",
                    description="Search for JIRA issues using JQL (JIRA Query Language)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "jql": {
                                "type": "string",
                                "description": "JQL query string (e.g., 'project = TEST AND status = Open')"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 50)",
                                "default": 50
                            }
                        },
                        "required": ["jql"]
                    }
                ),
                Tool(
                    name="jira_get_issue",
                    description="Get detailed information about a specific JIRA issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "JIRA issue key (e.g., 'TEST-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="jira_create_issue",
                    description="Create a new JIRA issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_key": {
                                "type": "string",
                                "description": "Project key (e.g., 'TEST')"
                            },
                            "issue_type": {
                                "type": "string",
                                "description": "Issue type (e.g., 'Bug', 'Task', 'Story')"
                            },
                            "summary": {
                                "type": "string",
                                "description": "Issue summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Issue description"
                            },
                            "priority": {
                                "type": "string",
                                "description": "Priority (e.g., 'High', 'Medium', 'Low')",
                                "default": "Medium"
                            },
                            "assignee": {
                                "type": "string",
                                "description": "Assignee username (optional)"
                            }
                        },
                        "required": ["project_key", "issue_type", "summary", "description"]
                    }
                ),
                Tool(
                    name="jira_update_issue",
                    description="Update an existing JIRA issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "JIRA issue key (e.g., 'TEST-123')"
                            },
                            "summary": {
                                "type": "string",
                                "description": "New summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "New description"
                            },
                            "status": {
                                "type": "string",
                                "description": "New status (e.g., 'In Progress', 'Done')"
                            },
                            "assignee": {
                                "type": "string",
                                "description": "New assignee username"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="jira_add_comment",
                    description="Add a comment to a JIRA issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "JIRA issue key (e.g., 'TEST-123')"
                            },
                            "comment": {
                                "type": "string",
                                "description": "Comment text"
                            }
                        },
                        "required": ["issue_key", "comment"]
                    }
                ),
                Tool(
                    name="jira_find_stale_issues",
                    description="Find issues with assignees where the latest comment is older than specified days",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_key": {
                                "type": "string",
                                "description": "Project key to search in (e.g., 'TEST')"
                            },
                            "days_threshold": {
                                "type": "integer",
                                "description": "Number of days to consider comments stale (default: 14)",
                                "default": 14
                            },
                            "include_no_comments": {
                                "type": "boolean",
                                "description": "Include issues with no comments at all (default: true)",
                                "default": true
                            },
                            "status_filter": {
                                "type": "string",
                                "description": "Filter by status (e.g., 'Open', 'In Progress', or leave empty for all)"
                            },
                            "affects_versions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by Affects Version/s (e.g., ['1.0', '2.0'] or leave empty for all)"
                            }
                        },
                        "required": ["project_key"]
                    }
                ),
                Tool(
                    name="jira_comment_on_stale_issues",
                    description="Find stale issues and add comments tagging assignees with flexible targeting options",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_key": {
                                "type": "string",
                                "description": "Project key to search in (e.g., 'TEST'). Not required if specific_issues is provided."
                            },
                            "days_threshold": {
                                "type": "integer",
                                "description": "Number of days to consider comments stale (default: 14)",
                                "default": 14
                            },
                            "exclude_statuses": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Status names to exclude (e.g., ['Closed', 'Done', 'On QA'])",
                                "default": ["Closed", "Release Pending", "On_QA", "Verified"]
                            },
                            "comment_template": {
                                "type": "string",
                                "description": "Comment template with {assignee} placeholder",
                                "default": "{assignee} Do you have any recent updates on this bug?"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["dry_run", "live"],
                                "description": "Operation mode: 'dry_run' (preview only) or 'live' (actually post comments)",
                                "default": "dry_run"
                            },
                            "target_scope": {
                                "type": "string",
                                "enum": ["all_stale", "specific_issues"],
                                "description": "Comment on all found stale issues or only specific issues",
                                "default": "all_stale"
                            },
                            "specific_issues": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific issue keys to comment on (e.g., ['TEST-123', 'TEST-456']). Used when target_scope is 'specific_issues'"
                            },
                            "affects_versions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by Affects Version/s when searching (e.g., ['1.0', '2.0'])"
                            }
                        },
                        "required": []
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                # Initialize JIRA client if not already done
                if not self.jira_client:
                    await self.init_jira_client()
                
                if name == "jira_search_issues":
                    return await self.search_issues(arguments)
                elif name == "jira_get_issue":
                    return await self.get_issue(arguments)
                elif name == "jira_create_issue":
                    return await self.create_issue(arguments)
                elif name == "jira_update_issue":
                    return await self.update_issue(arguments)
                elif name == "jira_add_comment":
                    return await self.add_comment(arguments)
                elif name == "jira_find_stale_issues":
                    return await self.find_stale_issues(arguments)
                elif name == "jira_comment_on_stale_issues":
                    return await self.comment_on_stale_issues(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {str(e)}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def init_jira_client(self):
        """Initialize JIRA client."""
        if not all([self.jira_url, self.jira_username, self.jira_token]):
            raise ValueError(
                "JIRA credentials not provided. Please set JIRA_URL, JIRA_USERNAME, and JIRA_TOKEN environment variables."
            )
        
        try:
            self.jira_client = JIRA(
                server=self.jira_url,
                basic_auth=(self.jira_username, self.jira_token)
            )
            logger.info("JIRA client initialized successfully")
        except JIRAError as e:
            logger.error(f"Failed to initialize JIRA client: {str(e)}")
            raise
    
    async def search_issues(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search for JIRA issues using JQL."""
        jql = arguments.get("jql")
        max_results = arguments.get("max_results", 50)
        
        try:
            issues = self.jira_client.search_issues(jql, maxResults=max_results)
            
            if not issues:
                return [TextContent(type="text", text="No issues found matching the JQL query.")]
            
            result = f"Found {len(issues)} issue(s):\n\n"
            for issue in issues:
                result += f"**{issue.key}**: {issue.fields.summary}\n"
                result += f"  Status: {issue.fields.status.name}\n"
                result += f"  Assignee: {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}\n"
                result += f"  Priority: {getattr(issue.fields.priority, 'name', 'None')}\n"
                result += f"  Created: {issue.fields.created}\n\n"
            
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
    
    async def get_issue(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get detailed information about a JIRA issue."""
        issue_key = arguments.get("issue_key")
        
        try:
            issue = self.jira_client.issue(issue_key)
            
            result = f"**Issue: {issue.key}**\n\n"
            result += f"**Summary:** {issue.fields.summary}\n"
            result += f"**Status:** {issue.fields.status.name}\n"
            result += f"**Assignee:** {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}\n"
            result += f"**Reporter:** {getattr(issue.fields.reporter, 'displayName', 'Unknown')}\n"
            result += f"**Priority:** {getattr(issue.fields.priority, 'name', 'None')}\n"
            result += f"**Issue Type:** {issue.fields.issuetype.name}\n"
            result += f"**Project:** {issue.fields.project.name}\n"
            result += f"**Created:** {issue.fields.created}\n"
            result += f"**Updated:** {issue.fields.updated}\n\n"
            
            if hasattr(issue.fields, 'description') and issue.fields.description:
                result += f"**Description:**\n{issue.fields.description}\n\n"
            
            # Get comments
            comments = self.jira_client.comments(issue)
            if comments:
                result += f"**Comments ({len(comments)}):**\n"
                for comment in comments[-5:]:  # Show last 5 comments
                    result += f"- {comment.author.displayName} ({comment.created}): {comment.body}\n"
            
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
    
    async def create_issue(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Create a new JIRA issue."""
        project_key = arguments.get("project_key")
        issue_type = arguments.get("issue_type")
        summary = arguments.get("summary")
        description = arguments.get("description")
        priority = arguments.get("priority", "Medium")
        assignee = arguments.get("assignee")
        
        try:
            issue_dict = {
                'project': {'key': project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type},
            }
            
            if priority:
                issue_dict['priority'] = {'name': priority}
            
            if assignee:
                issue_dict['assignee'] = {'name': assignee}
            
            new_issue = self.jira_client.create_issue(fields=issue_dict)
            
            result = f"✅ Issue created successfully!\n\n"
            result += f"**Issue Key:** {new_issue.key}\n"
            result += f"**Summary:** {summary}\n"
            result += f"**Project:** {project_key}\n"
            result += f"**Issue Type:** {issue_type}\n"
            result += f"**Priority:** {priority}\n"
            if assignee:
                result += f"**Assignee:** {assignee}\n"
            result += f"**URL:** {self.jira_url}/browse/{new_issue.key}\n"
            
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
    
    async def update_issue(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Update an existing JIRA issue."""
        issue_key = arguments.get("issue_key")
        
        try:
            issue = self.jira_client.issue(issue_key)
            update_fields = {}
            
            if "summary" in arguments:
                update_fields['summary'] = arguments["summary"]
            
            if "description" in arguments:
                update_fields['description'] = arguments["description"]
            
            if "assignee" in arguments:
                update_fields['assignee'] = {'name': arguments["assignee"]}
            
            if update_fields:
                issue.update(fields=update_fields)
            
            # Handle status transition separately
            if "status" in arguments:
                transitions = self.jira_client.transitions(issue)
                target_status = arguments["status"]
                
                for transition in transitions:
                    if transition['name'].lower() == target_status.lower():
                        self.jira_client.transition_issue(issue, transition['id'])
                        break
                else:
                    return [TextContent(type="text", text=f"Status '{target_status}' not available for this issue")]
            
            result = f"✅ Issue {issue_key} updated successfully!\n"
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
    
    async def add_comment(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Add a comment to a JIRA issue."""
        issue_key = arguments.get("issue_key")
        comment_text = arguments.get("comment")
        
        try:
            self.jira_client.add_comment(issue_key, comment_text)
            result = f"✅ Comment added to {issue_key} successfully!"
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
    
    
    async def find_stale_issues(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Find issues with assignees where the latest comment is older than specified days."""
        from datetime import datetime, timedelta
        
        project_key = arguments.get("project_key")
        days_threshold = arguments.get("days_threshold", 14)
        include_no_comments = arguments.get("include_no_comments", True)
        status_filter = arguments.get("status_filter")
        affects_versions = arguments.get("affects_versions")
        
        try:
            # Build JQL query
            jql_parts = [
                f'project = "{project_key}"',
                'assignee is not EMPTY'
            ]
            
            if status_filter:
                jql_parts.append(f'status = "{status_filter}"')
            
            # Add Affects Version filter if provided
            if affects_versions:
                if len(affects_versions) == 1:
                    jql_parts.append(f'affectedVersion = "{affects_versions[0]}"')
                else:
                    version_list = ", ".join([f'"{v}"' for v in affects_versions])
                    jql_parts.append(f'affectedVersion in ({version_list})')
            
            # First, get all issues with assignees
            base_jql = " AND ".join(jql_parts)
            issues = self.jira_client.search_issues(base_jql, maxResults=1000, expand='changelog')
            
            if not issues:
                return [TextContent(type="text", text=f"No issues found in project {project_key} with assignees.")]
            
            # Calculate the threshold date
            threshold_date = datetime.now() - timedelta(days=days_threshold)
            stale_issues = []
            
            for issue in issues:
                try:
                    # Get comments for this issue
                    comments = self.jira_client.comments(issue)
                    
                    is_stale = False
                    latest_comment_date = None
                    
                    if not comments:
                        # No comments at all
                        if include_no_comments:
                            is_stale = True
                            latest_comment_date = "No comments"
                    else:
                        # Get the latest comment
                        latest_comment = comments[-1]
                        # Parse the comment date (JIRA returns ISO format)
                        comment_date_str = latest_comment.created
                        # Remove timezone info and microseconds for parsing
                        if 'T' in comment_date_str:
                            comment_date_str = comment_date_str.split('T')[0] + 'T' + comment_date_str.split('T')[1][:19]
                        
                        try:
                            latest_comment_date = datetime.fromisoformat(comment_date_str.replace('Z', '+00:00'))
                            # Convert to naive datetime for comparison
                            if latest_comment_date.tzinfo:
                                latest_comment_date = latest_comment_date.replace(tzinfo=None)
                            
                            if latest_comment_date < threshold_date:
                                is_stale = True
                        except ValueError:
                            # If we can't parse the date, treat as stale
                            is_stale = True
                            latest_comment_date = comment_date_str
                    
                    if is_stale:
                        stale_issues.append({
                            'issue': issue,
                            'latest_comment_date': latest_comment_date,
                            'comments_count': len(comments)
                        })
                        
                except Exception as e:
                    logger.warning(f"Error processing issue {issue.key}: {str(e)}")
                    continue
            
            if not stale_issues:
                return [TextContent(type="text", text=f"✅ No stale issues found in project {project_key}. All assigned issues have recent activity!")]
            
            # Format results
            result = f"🔍 Found {len(stale_issues)} stale issue(s) in project {project_key}:\n"
            result += f"(Issues with assignees but no comments or comments older than {days_threshold} days)\n\n"
            
            for item in stale_issues:
                issue = item['issue']
                latest_date = item['latest_comment_date']
                comments_count = item['comments_count']
                
                result += f"**{issue.key}**: {issue.fields.summary}\n"
                result += f"  📋 Status: {issue.fields.status.name}\n"
                result += f"  👤 Assignee: {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}\n"
                result += f"  🏷️  Priority: {getattr(issue.fields.priority, 'name', 'None')}\n"
                result += f"  💬 Comments: {comments_count}\n"
                
                if latest_date == "No comments":
                    result += f"  🕒 Last Activity: No comments (Created: {issue.fields.created[:10]})\n"
                else:
                    if isinstance(latest_date, datetime):
                        days_old = (datetime.now() - latest_date).days
                        result += f"  🕒 Last Comment: {latest_date.strftime('%Y-%m-%d %H:%M')} ({days_old} days ago)\n"
                    else:
                        result += f"  🕒 Last Comment: {latest_date}\n"
                
                result += f"  🔗 URL: {self.jira_url}/browse/{issue.key}\n\n"
            
            # Add JQL query for manual use
            result += f"\n📝 **Manual JQL Query:**\n"
            result += f"```\n{base_jql}\n```\n"
            result += f"Note: The comment date filtering is done programmatically as JIRA's JQL has limited comment date filtering capabilities.\n"
            
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def comment_on_stale_issues(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Find stale issues and add comments tagging assignees with flexible targeting options."""
        from datetime import datetime, timedelta
        
        project_key = arguments.get("project_key")
        days_threshold = arguments.get("days_threshold", 14)
        exclude_statuses = arguments.get("exclude_statuses", ["Closed", "Release Pending", "On_QA", "Verified"])
        comment_template = arguments.get("comment_template", "{assignee} Do you have any recent updates on this bug?")
        mode = arguments.get("mode", "dry_run")
        target_scope = arguments.get("target_scope", "all_stale")
        specific_issues = arguments.get("specific_issues", [])
        affects_versions = arguments.get("affects_versions")
        
        try:
            issues_to_process = []
            
            if target_scope == "specific_issues":
                # Process specific issue keys
                if not specific_issues:
                    return [TextContent(type="text", text="❌ No specific issues provided. Please provide issue keys in 'specific_issues' parameter.")]
                
                result = f"🎯 Processing {len(specific_issues)} specific issue(s): {', '.join(specific_issues)}\n\n"
                
                for issue_key in specific_issues:
                    try:
                        issue = self.jira_client.issue(issue_key)
                        if issue.fields.assignee:  # Only process if has assignee
                            issues_to_process.append(issue)
                        else:
                            result += f"⚠️  Skipping {issue_key}: No assignee\n"
                    except JIRAError as e:
                        result += f"❌ Failed to fetch {issue_key}: {str(e)}\n"
                        
            else:
                # Find stale issues automatically
                if not project_key:
                    return [TextContent(type="text", text="❌ Project key is required when target_scope is 'all_stale'.")]
                
                # Build JQL query excluding specified statuses
                jql_parts = [
                    f'project = "{project_key}"',
                    'assignee is not EMPTY'
                ]
                
                # Add status exclusions
                if exclude_statuses:
                    status_exclusion = " AND ".join([f'status != "{status}"' for status in exclude_statuses])
                    jql_parts.append(f"({status_exclusion})")
                
                # Add Affects Version filter if provided
                if affects_versions:
                    if len(affects_versions) == 1:
                        jql_parts.append(f'affectedVersion = "{affects_versions[0]}"')
                    else:
                        version_list = ", ".join([f'"{v}"' for v in affects_versions])
                        jql_parts.append(f'affectedVersion in ({version_list})')
                
                base_jql = " AND ".join(jql_parts)
                all_issues = self.jira_client.search_issues(base_jql, maxResults=1000)
                
                if not all_issues:
                    return [TextContent(type="text", text=f"No active issues found in project {project_key} with assignees.")]
                
                # Calculate threshold date and find stale issues
                threshold_date = datetime.now() - timedelta(days=days_threshold)
                
                for issue in all_issues:
                    try:
                        comments = self.jira_client.comments(issue)
                        is_stale = False
                        
                        if not comments:
                            is_stale = True
                        else:
                            latest_comment = comments[-1]
                            comment_date_str = latest_comment.created
                            
                            try:
                                if 'T' in comment_date_str:
                                    comment_date_str = comment_date_str.split('T')[0] + 'T' + comment_date_str.split('T')[1][:19]
                                
                                latest_comment_date = datetime.fromisoformat(comment_date_str.replace('Z', '+00:00'))
                                if latest_comment_date.tzinfo:
                                    latest_comment_date = latest_comment_date.replace(tzinfo=None)
                                
                                if latest_comment_date < threshold_date:
                                    is_stale = True
                            except ValueError:
                                is_stale = True
                        
                        if is_stale:
                            issues_to_process.append(issue)
                            
                    except Exception as e:
                        logger.warning(f"Error processing issue {issue.key}: {str(e)}")
                        continue
                
                result = f"🔍 Found {len(issues_to_process)} stale issue(s) in project {project_key}\n"
                if exclude_statuses:
                    result += f"Excluding statuses: {', '.join(exclude_statuses)}\n"
                if affects_versions:
                    result += f"Filtering by versions: {', '.join(affects_versions)}\n"
                result += f"Staleness threshold: {days_threshold} days\n\n"
            
            if not issues_to_process:
                return [TextContent(type="text", text=f"✅ No stale issues found to comment on!")]
            
            # Format operation mode
            if mode == "dry_run":
                result += "🏃‍♂️ **DRY RUN MODE** - No actual comments will be posted\n\n"
            else:
                result += "💬 **LIVE MODE** - Comments will be posted to JIRA\n\n"
            
            commented_count = 0
            failed_count = 0
            skipped_count = 0
            
            for issue in issues_to_process:
                assignee = issue.fields.assignee
                
                if not assignee:
                    result += f"⚠️  **{issue.key}**: Skipping - no assignee\n\n"
                    skipped_count += 1
                    continue
                
                # Get comment info for context (if not specific issues mode)
                latest_date = "N/A"
                comments_count = 0
                if target_scope == "all_stale":
                    try:
                        comments = self.jira_client.comments(issue)
                        comments_count = len(comments)
                        if comments:
                            latest_comment = comments[-1]
                            comment_date_str = latest_comment.created
                            try:
                                if 'T' in comment_date_str:
                                    comment_date_str = comment_date_str.split('T')[0] + 'T' + comment_date_str.split('T')[1][:19]
                                latest_date = datetime.fromisoformat(comment_date_str.replace('Z', '+00:00'))
                                if latest_date.tzinfo:
                                    latest_date = latest_date.replace(tzinfo=None)
                            except ValueError:
                                latest_date = comment_date_str
                        else:
                            latest_date = "No comments"
                    except Exception:
                        latest_date = "Error retrieving"
                
                # Format the comment with assignee mention
                assignee_mention = f"[~{assignee.name}]" if hasattr(assignee, 'name') else f"@{assignee.displayName}"
                comment_text = comment_template.format(assignee=assignee_mention)
                
                result += f"📋 **{issue.key}**: {issue.fields.summary}\n"
                result += f"   👤 Assignee: {assignee.displayName}\n"
                result += f"   📊 Status: {issue.fields.status.name}\n"
                
                if target_scope == "all_stale":
                    result += f"   💬 Comments: {comments_count}\n"
                    if latest_date == "No comments":
                        result += f"   🕒 Last Activity: No comments\n"
                    elif isinstance(latest_date, datetime):
                        days_old = (datetime.now() - latest_date).days
                        result += f"   🕒 Last Comment: {latest_date.strftime('%Y-%m-%d')} ({days_old} days ago)\n"
                    else:
                        result += f"   🕒 Last Comment: {latest_date}\n"
                
                result += f"   💭 Comment to post: \"{comment_text}\"\n"
                
                if mode == "live":
                    try:
                        # Actually post the comment
                        self.jira_client.add_comment(issue.key, comment_text)
                        result += f"   ✅ Comment posted successfully!\n"
                        commented_count += 1
                    except JIRAError as e:
                        result += f"   ❌ Failed to post comment: {str(e)}\n"
                        failed_count += 1
                else:
                    result += f"   🔍 Would post comment (dry run mode)\n"
                
                result += f"   🔗 URL: {self.jira_url}/browse/{issue.key}\n\n"
            
            # Summary
            result += "=" * 50 + "\n"
            result += f"📊 **Summary:**\n"
            result += f"   Issues processed: {len(issues_to_process)}\n"
            
            if mode == "live":
                result += f"   ✅ Successfully commented: {commented_count}\n"
                if failed_count > 0:
                    result += f"   ❌ Failed to comment: {failed_count}\n"
                if skipped_count > 0:
                    result += f"   ⚠️  Skipped (no assignee): {skipped_count}\n"
            else:
                result += f"   🔍 Ready to comment: {len(issues_to_process) - skipped_count}\n"
                if skipped_count > 0:
                    result += f"   ⚠️  Would skip (no assignee): {skipped_count}\n"
                result += f"\n💡 **Tip:** Set 'mode': 'live' to actually post comments\n"
            
            return [TextContent(type="text", text=result)]
            
        except JIRAError as e:
            return [TextContent(type="text", text=f"JIRA Error: {str(e)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            # Create notification options
            notification_options = NotificationOptions()
            
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mcp-jira-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=notification_options,
                        experimental_capabilities={},
                    ),
                ),
            )


async def main():
    """Main function to run the MCP JIRA server."""
    try:
        # Check for required environment variables
        required_vars = ["JIRA_URL", "JIRA_USERNAME", "JIRA_TOKEN"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("❌ Missing required environment variables:")
            for var in missing_vars:
                print(f"  - {var}")
            print("\nPlease set these environment variables before running the server.")
            print("\nExample:")
            print("export JIRA_URL='https://your-domain.atlassian.net'")
            print("export JIRA_USERNAME='your-email@example.com'")
            print("export JIRA_TOKEN='your-api-token'")
            return
        
        print("🚀 Starting MCP JIRA Server...")
        print(f"JIRA URL: {os.getenv('JIRA_URL')}")
        print(f"Username: {os.getenv('JIRA_USERNAME')}")
        
        server = MCPJiraServer()
        await server.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        raise


def main_sync():
    """Synchronous wrapper for main function with better error handling."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Failed to start server: {str(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main_sync()
