#!/usr/bin/env python3
"""
FastMCP JIRA Server
==================

A FastMCP server for interacting with JIRA.
This server provides tools for creating issues, searching, updating, and managing JIRA projects.

Requirements:
- fastmcp (FastMCP library)
- jira (Python JIRA library)
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP library not found. Install with: pip install fastmcp", file=sys.stderr)
    exit(1)

try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    print("JIRA library not found. Install with: pip install jira", file=sys.stderr)
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP app
app = FastMCP("JIRA Server")

# Global JIRA client and rate limiting
jira_client: Optional[JIRA] = None
last_api_call = 0
api_call_delay = 1.0  # 1 second between API calls (reduced from 2.0)
burst_count = 0
burst_limit = 10  # Allow more burst calls (increased from 5)
burst_reset_time = 60  # Reset burst counter after 1 minute


async def init_jira_client():
    """Initialize JIRA client with Bearer token authentication."""
    global jira_client
    
    jira_url = os.getenv("JIRA_URL")
    jira_token = os.getenv("JIRA_TOKEN")
    
    if not all([jira_url, jira_token]):
        raise ValueError(
            "JIRA credentials not provided. Please set JIRA_URL and JIRA_TOKEN (Bearer token) environment variables."
        )
    
    try:
        # Use Bearer token authentication
        jira_client = JIRA(
            server=jira_url,
            token_auth=jira_token
        )
        logger.info("JIRA client initialized successfully with Bearer token")
    except JIRAError as e:
        logger.error(f"Failed to initialize JIRA client: {str(e)}")
        raise


async def rate_limit():
    """Ensure we don't exceed rate limits with burst protection."""
    global last_api_call, burst_count
    
    current_time = time.time()
    time_since_last_call = current_time - last_api_call
    
    # Reset burst counter if enough time has passed
    if time_since_last_call > burst_reset_time:
        burst_count = 0
    
    # Calculate sleep time based on burst count
    base_delay = api_call_delay
    
    # If we've made too many consecutive calls, add exponential backoff
    if burst_count >= burst_limit:
        # Exponential backoff: 2^(burst_count - burst_limit) * base_delay
        backoff_multiplier = 2 ** min(burst_count - burst_limit, 2)  # Cap at 4x (reduced from 16x)
        sleep_time = base_delay * backoff_multiplier
        # Cap maximum sleep time at 8 seconds to prevent timeouts
        sleep_time = min(sleep_time, 8.0)
        logger.info(f"Rate limiting: Burst limit reached, sleeping for {sleep_time:.1f}s")
    else:
        # Regular rate limiting
        if time_since_last_call < base_delay:
            sleep_time = base_delay - time_since_last_call
        else:
            sleep_time = 0
    
    if sleep_time > 0:
        await asyncio.sleep(sleep_time)
    
    # Update tracking variables
    last_api_call = time.time()
    burst_count += 1


@app.tool()
async def jira_search_issues(jql: str, max_results: int = 50) -> str:
    """Search for JIRA issues using JQL (JIRA Query Language)."""
    if not jira_client:
        await init_jira_client()
    
    try:
        await rate_limit()
        issues = jira_client.search_issues(jql, maxResults=max_results)
        
        if not issues:
            return "No issues found matching the JQL query."
        
        result = f"Found {len(issues)} issue(s):\n\n"
        for issue in issues:
            result += f"**{issue.key}**: {issue.fields.summary}\n"
            result += f"  Status: {issue.fields.status.name}\n"
            result += f"  Assignee: {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}\n"
            result += f"  Priority: {getattr(issue.fields.priority, 'name', 'None')}\n"
            result += f"  Created: {issue.fields.created}\n\n"
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"


@app.tool()
async def jira_get_issue(issue_key: str) -> str:
    """Get detailed information about a specific JIRA issue."""
    if not jira_client:
        await init_jira_client()
    
    try:
        await rate_limit()
        issue = jira_client.issue(issue_key)
        
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
        await rate_limit()
        comments = jira_client.comments(issue)
        if comments:
            result += f"**Comments ({len(comments)}):**\n"
            for comment in comments[-5:]:  # Show last 5 comments
                result += f"- {comment.author.displayName} ({comment.created}): {comment.body}\n"
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"


@app.tool()
async def jira_create_issue(
    project_key: str,
    issue_type: str,
    summary: str,
    description: str,
    priority: str = "Medium",
    assignee: Optional[str] = None
) -> str:
    """Create a new JIRA issue."""
    if not jira_client:
        await init_jira_client()
    
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
        
        await rate_limit()
        new_issue = jira_client.create_issue(fields=issue_dict)
        
        result = f"✅ Issue created successfully!\n\n"
        result += f"**Issue Key:** {new_issue.key}\n"
        result += f"**Summary:** {summary}\n"
        result += f"**Project:** {project_key}\n"
        result += f"**Issue Type:** {issue_type}\n"
        result += f"**Priority:** {priority}\n"
        if assignee:
            result += f"**Assignee:** {assignee}\n"
        result += f"**URL:** {os.getenv('JIRA_URL')}/browse/{new_issue.key}\n"
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"


@app.tool()
async def jira_update_issue(
    issue_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None
) -> str:
    """Update an existing JIRA issue."""
    if not jira_client:
        await init_jira_client()
    
    try:
        await rate_limit()
        issue = jira_client.issue(issue_key)
        update_fields = {}
        
        if summary:
            update_fields['summary'] = summary
        
        if description:
            update_fields['description'] = description
        
        if assignee:
            update_fields['assignee'] = {'name': assignee}
        
        if update_fields:
            issue.update(fields=update_fields)
        
        # Handle status transition separately
        if status:
            await rate_limit()
            transitions = jira_client.transitions(issue)
            target_status = status
            
            for transition in transitions:
                if transition['name'].lower() == target_status.lower():
                    jira_client.transition_issue(issue, transition['id'])
                    break
            else:
                return f"Status '{target_status}' not available for this issue"
        
        return f"✅ Issue {issue_key} updated successfully!"
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"


@app.tool()
async def jira_add_comment(
    issue_key: str, 
    comment: str, 
    mention_assignee: bool = True,
    custom_mention_user: Optional[str] = None,
    mode: str = "dry_run"
) -> str:
    """Add a comment to a JIRA issue with optional assignee mentioning and preview mode.
    
    Args:
        issue_key: The JIRA issue key (e.g., OCPBUGS-123)
        comment: The comment text to add
        mention_assignee: Whether to mention the current assignee (default: True)
        custom_mention_user: Optional username to mention instead of assignee
        mode: "dry_run" (preview only) or "live" (actually post comment)
    """
    if not jira_client:
        await init_jira_client()
    
    try:
        # Validate mode parameter
        if mode not in ["dry_run", "live"]:
            return f"❌ Invalid mode '{mode}'. Use 'dry_run' or 'live'."
        
        # Get issue details to find assignee if needed
        final_comment = comment
        mentioned_user = None
        issue_summary = "Unknown"
        current_assignee = "Unassigned"
        
        if mention_assignee or custom_mention_user or mode == "dry_run":
            await rate_limit()
            issue = jira_client.issue(issue_key)
            issue_summary = issue.fields.summary
            current_assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
            
            if custom_mention_user:
                # Use custom user for mention
                final_comment = f"[~{custom_mention_user}] {comment}"
                mentioned_user = custom_mention_user
            elif mention_assignee and issue.fields.assignee:
                # Use assignee for mention
                assignee_name = issue.fields.assignee.name
                final_comment = f"[~{assignee_name}] {comment}"
                mentioned_user = issue.fields.assignee.displayName
            elif mention_assignee and not issue.fields.assignee:
                # Issue has no assignee, add note about it
                final_comment = f"{comment}\n\n_Note: This issue is currently unassigned._"
        
        # Handle dry run mode
        if mode == "dry_run":
            preview_msg = f"🔍 **COMMENT PREVIEW for {issue_key}**\n"
            preview_msg += f"📋 **Issue**: {issue_summary}\n"
            preview_msg += f"👤 **Current Assignee**: {current_assignee}\n"
            preview_msg += f"💬 **Comment Mode**: {'Mention assignee' if mention_assignee else 'No mention'}\n"
            if custom_mention_user:
                preview_msg += f"🎯 **Custom Mention**: {custom_mention_user}\n"
            preview_msg += f"\n📝 **Final Comment Text**:\n"
            preview_msg += f"```\n{final_comment}\n```\n"
            preview_msg += f"\n💡 **To post this comment, use mode='live'**"
            if mentioned_user:
                preview_msg += f"\n📧 **Will notify**: {mentioned_user}"
            return preview_msg
        
        # Live mode - actually post the comment
        await rate_limit()
        jira_client.add_comment(issue_key, final_comment)
        
        # Build success message
        success_msg = f"✅ Comment posted to {issue_key} successfully!"
        success_msg += f"\n📋 Issue: {issue_summary}"
        if mentioned_user:
            success_msg += f"\n👤 Mentioned: {mentioned_user}"
            success_msg += f"\n📧 Notification sent to: {mentioned_user}"
        elif mention_assignee and not mentioned_user:
            success_msg += f"\n⚠️  No assignee to mention (issue is unassigned)"
        success_msg += f"\n🔗 View: {os.getenv('JIRA_URL')}/browse/{issue_key}"
            
        return success_msg
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"


@app.tool()
async def jira_find_stale_issues(
    days_threshold: int = 14,
    include_no_comments: bool = True,
    affects_versions: List[str] = [],
    max_results: int = 50,
    additional_components: List[str] = [],
    additional_projects: List[str] = [],
    override_projects: List[str] = [],
    strict_bugs_only: bool = True
) -> str:
    """Find stale Telco priority bugs with no recent comments.
    
    Args:
        days_threshold: Days threshold for staleness (default: 14)
        include_no_comments: Include issues with no comments (default: True)
        affects_versions: Filter by specific versions (default: [])
        max_results: Maximum number of results (default: 50)
        additional_components: Additional components to include (default: [])
        additional_projects: Additional projects to include with defaults (default: [])
        override_projects: If specified, search ONLY these projects (ignores defaults) (default: [])
        strict_bugs_only: Only include bug-type issues, exclude stories/epics/tasks (default: True)
    """
    if not jira_client:
        await init_jira_client()
    
    try:
        # PROJECT HANDLING: Flexible project selection
        if override_projects:
            # User wants to search ONLY specific projects
            project_list = ", ".join(override_projects)
            project_clause = f'project in ({project_list})'
        else:
            # Use default projects + any additional ones
            default_projects = ["OCPBUGS"]
            all_projects = default_projects + additional_projects
            project_list = ", ".join(all_projects)
            project_clause = f'project in ({project_list})'
        
        # BASE JQL with flexible projects and strict bug filtering
        jql_parts = [
            project_clause,
            'status not in (Verified, ON_QA, Closed, "Release Pending")',
            'assignee is not EMPTY'
        ]
        
        jql_parts.append('cf[12323649] in ("Telco:Priority-1", "Telco:Priority-2", "Telco:Priority-3")')
        
        # STRICT BUG FILTERING: Only include bug-type issues
        if strict_bugs_only:
            jql_parts.append('issuetype = Bug')
        
        # HARDCODED DIRECTIVE 2: Default components
        default_components = [
            "GitOps ZTP",
            "Bare Metal Hardware Provisioning / baremetal-operator", 
            "Networking / SR-IOV",
            "oc"
        ]
        
        # Combine default and additional components
        all_components = default_components + additional_components
        if all_components:
            component_list = ", ".join([f'"{comp}"' for comp in all_components])
            jql_parts.append(f'component in ({component_list})')
        
        # HARDCODED DIRECTIVE 3: Affects Version expansion (e.g., 4.18 -> 4.18, 4.18.z)
        if affects_versions:
            expanded_versions = []
            for version in affects_versions:
                # Add the base version
                expanded_versions.append(f'"{version}"')
                # Add the .z version  
                expanded_versions.append(f'"{version}.z"')
            
            version_list = ", ".join(expanded_versions)
            jql_parts.append(f'affectedVersion in ({version_list})')
        
        # Build and execute JQL query
        base_jql = " AND ".join(jql_parts)
        max_results = min(max_results, 25)  # Cap at 25 for faster processing and less timeouts
        
        logger.info(f"Executing JQL: {base_jql}")
        await rate_limit()
        # Single optimized call: get issues with comments and all needed fields
        issues = jira_client.search_issues(
            base_jql, 
            maxResults=max_results, 
            expand='changelog,comments',  # Get comments in the same call!
            fields='summary,status,assignee,reporter,priority,issuetype,project,created,updated,components,versions,comment,customfield_12323649'
        )
        
        if not issues:
            return "✅ No Telco priority issues found matching the criteria."
        
        # Calculate the threshold date
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        stale_issues = []
        
        # Build search summary
        if override_projects:
            projects_used = override_projects
            project_mode = f"🎯 Override mode: ONLY {', '.join(override_projects)}"
        else:
            projects_used = ["OCPBUGS", "MGMT"] + additional_projects
            if additional_projects:
                project_mode = f"📦 Default projects (OCPBUGS, MGMT) + {', '.join(additional_projects)}"
            else:
                project_mode = f"📦 Default projects: OCPBUGS, MGMT"
        
        result_preview = f"🔍 **Telco Priority Stale Issues Search**\n"
        result_preview += f"📊 Found {len(issues)} issues (limited to {max_results} for performance)\n"
        result_preview += f"⏰ Staleness threshold: {days_threshold} days\n"
        result_preview += f"{project_mode}\n"
        result_preview += f"🐛 Issue types: {'Bugs only' if strict_bugs_only else 'All types'}\n"
        result_preview += f"⚡ Optimized: Single API call with expanded fields\n"
        if affects_versions:
            result_preview += f"🎯 Affects versions: {', '.join(affects_versions)} (including .z variants)\n"
        if additional_components:
            result_preview += f"🔧 Additional components: {', '.join(additional_components)}\n"
        result_preview += f"\n"
        
        for idx, issue in enumerate(issues):
            try:
                # Get comments from the already-loaded issue (no additional API call needed!)
                comments = getattr(issue.fields, 'comment', None)
                if comments and hasattr(comments, 'comments'):
                    comments = comments.comments
                else:
                    comments = []
                
                # Log progress every 5 issues (now much faster since no API calls in loop)
                if (idx + 1) % 5 == 0:
                    logger.info(f"Analyzed {idx + 1}/{len(issues)} Telco priority issues (no API calls needed)")
                
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
            return "✅ No stale Telco priority issues found! All assigned issues have recent activity."
        
        # Format results
        result = result_preview
        result += f"🚨 **Found {len(stale_issues)} stale Telco priority issue(s):**\n"
        result += f"(Issues with assignees but no comments or comments older than {days_threshold} days)\n\n"
        
        for item in stale_issues:
            issue = item['issue']
            latest_date = item['latest_comment_date']
            comments_count = item['comments_count']
            
            # Get component info
            components = getattr(issue.fields, 'components', [])
            component_names = [comp.name for comp in components] if components else ['No component']
            
            # Get affected versions
            affected_versions = getattr(issue.fields, 'versions', [])
            version_names = [ver.name for ver in affected_versions] if affected_versions else ['No version']
            
            # Get Telco priority from custom field cf[12323649]
            telco_priority = "None"
            try:
                # Access the custom field that contains Telco priority
                custom_field_value = getattr(issue.fields, 'customfield_12323649', None)
                if custom_field_value:
                    if isinstance(custom_field_value, list):
                        # If it's a list, join the values
                        telco_priority = ', '.join([str(val) for val in custom_field_value])
                    else:
                        telco_priority = str(custom_field_value)
            except Exception:
                telco_priority = "Unable to retrieve"
            
            result += f"🐛 **{issue.key}**: {issue.fields.summary}\n"
            result += f"   📋 Status: {issue.fields.status.name}\n"
            result += f"   👤 Assignee: {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}\n"
            result += f"   🏷️  Priority: {getattr(issue.fields.priority, 'name', 'None')}\n"
            result += f"   🎯 Telco Priority: {telco_priority}\n"
            result += f"   🔧 Components: {', '.join(component_names[:3])}{'...' if len(component_names) > 3 else ''}\n"
            result += f"   📦 Affects Versions: {', '.join(version_names[:3])}{'...' if len(version_names) > 3 else ''}\n"
            result += f"   💬 Comments: {comments_count}\n"
            
            if latest_date == "No comments":
                result += f"   🕒 Last Activity: No comments (Created: {issue.fields.created[:10]})\n"
            else:
                if isinstance(latest_date, datetime):
                    days_old = (datetime.now() - latest_date).days
                    result += f"   🕒 Last Comment: {latest_date.strftime('%Y-%m-%d %H:%M')} ({days_old} days ago)\n"
                else:
                    result += f"   🕒 Last Comment: {latest_date}\n"
            
            result += f"   🔗 URL: {os.getenv('JIRA_URL')}/browse/{issue.key}\n\n"
        
        # Add JQL query for manual use
        result += f"\n📝 **JQL Query Used:**\n"
        result += f"```\n{base_jql}\n```\n"
        result += f"\n💡 **Note:** Comment date filtering is done programmatically after JQL search.\n"
        result += f"🎯 **Search Criteria:**\n"
        result += f"   • Projects: {', '.join(projects_used)}\n"
        result += f"   • Issue Types: {'Bugs only' if strict_bugs_only else 'All types'}\n"
        result += f"   • Telco Priority: 1, 2, 3\n"
        result += f"   • Status: Excluding Verified, ON_QA, Closed, Release Pending\n"
        result += f"   • Assignment: Only assigned issues\n"
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


async def main():
    """Main function to run the FastMCP JIRA server."""
    try:
        # Check for required environment variables
        required_vars = ["JIRA_URL", "JIRA_TOKEN"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("❌ Missing required environment variables:", file=sys.stderr)
            for var in missing_vars:
                print(f"  - {var}", file=sys.stderr)
            print("\nPlease set these environment variables before running the server.", file=sys.stderr)
            print("\nExample:", file=sys.stderr)
            print("export JIRA_URL='https://your-domain.atlassian.net'", file=sys.stderr)
            print("export JIRA_TOKEN='your-bearer-token'", file=sys.stderr)
            return
        
        print("🚀 Starting FastMCP JIRA Server...", file=sys.stderr)
        print(f"JIRA URL: {os.getenv('JIRA_URL')}", file=sys.stderr)
        print(f"Authentication: Bearer Token", file=sys.stderr)
        
        # Try using stdio mode instead
        await app.run_stdio_async()
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"❌ Server error: {str(e)}", file=sys.stderr)
        import traceback
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc()
        raise


def main_sync():
    """Synchronous wrapper for main function with better error handling."""
    try:
        # Check if there's already an event loop running
        try:
            loop = asyncio.get_running_loop()
            print("❌ AsyncIO loop already running. Please run from command line or restart your environment.", file=sys.stderr)
            return
        except RuntimeError:
            # No loop running, safe to start
            pass
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"❌ Failed to start server: {str(e)}", file=sys.stderr)
        import traceback
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc()


if __name__ == "__main__":
    main_sync()
