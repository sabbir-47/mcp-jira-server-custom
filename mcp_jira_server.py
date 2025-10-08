#!/usr/bin/env python3
"""
Assisted by: Cursor AI
FastMCP JIRA Server
==================

A FastMCP server for interacting with JIRA.
This server provides tools for creating issues, searching, updating, and managing JIRA projects.

Requirements:
- fastmcp (FastMCP library)
- jira (Python JIRA library)
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP library not found. Install with: pip install fastmcp", file=sys.stderr)
    exit(1)

# Import team configurations
try:
    from team_configs import (
        get_team_config,
        list_available_teams,
        get_default_team,
        TeamConfig,
        TEAM_REGISTRY
    )
except ImportError:
    print("Warning: team_configs module not found. Team-based configuration will not be available.", file=sys.stderr)

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
async def jira_list_teams() -> str:
    """
    List all available teams with their configurations.
    
    Each team has predefined:
    - Default projects to monitor
    - Default components to track
    - Priority field and values
    - Report title templates
    
    Returns:
        Formatted list of available teams with their configurations
    """
    try:
        teams = list_available_teams()
        
        result = "🏢 **Available Teams for JIRA Monitoring**\n"
        result += "="*60 + "\n\n"
        
        for team in teams:
            result += f"**Team:** {team['team_name']} (ID: `{team['team_id']}`)\n"
            result += f"**Description:** {team['description']}\n"
            result += f"**Default Projects:** {team['default_projects']}\n"
            result += f"**Default Components:**\n"
            components = team['default_components'].split(', ')
            for comp in components:
                result += f"  • {comp}\n"
            result += "\n" + "-"*60 + "\n\n"
        
        result += "\n💡 **Usage:** Pass `team_id` parameter to any stale issues function to use team-specific configuration.\n"
        result += "   Example: `jira_find_stale_issues(team_id='ptp', days_threshold=7)`\n"
        
        return result
        
    except Exception as e:
        return f"Error listing teams: {str(e)}"


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
async def jira_get_issue(issue_key: str, include_comment_analysis: bool = False) -> str:
    """
    Get detailed information about a specific JIRA issue.
    
    Args:
        issue_key: The JIRA issue key (e.g., 'OCPBUGS-12345')
        include_comment_analysis: Include AI-powered comment analysis (default: False)
    
    Returns:
        Detailed issue information with optional comment analysis
    """
    if not jira_client:
        await init_jira_client()
    
    try:
        await rate_limit()
        # Fetch issue with comments if analysis is requested
        if include_comment_analysis:
            issue = jira_client.issue(issue_key, expand='comments')
        else:
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
        result += f"**Updated:** {issue.fields.updated}\n"
        
        # Add Components and Versions info
        if hasattr(issue.fields, 'components') and issue.fields.components:
            components = [comp.name for comp in issue.fields.components]
            result += f"**Components:** {', '.join(components)}\n"
        
        if hasattr(issue.fields, 'versions') and issue.fields.versions:
            versions = [ver.name for ver in issue.fields.versions]
            result += f"**Affects Versions:** {', '.join(versions)}\n"
        
        # Add Telco Priority if available
        try:
            telco_priority = getattr(issue.fields, 'customfield_12323649', None)
            if telco_priority:
                if isinstance(telco_priority, list):
                    telco_priority = ', '.join([str(val) for val in telco_priority])
                result += f"**Telco Priority:** {telco_priority}\n"
        except Exception:
            pass
        
        result += "\n"
        
        if hasattr(issue.fields, 'description') and issue.fields.description:
            result += f"**Description:**\n{issue.fields.description}\n\n"
        
        # Handle comments with optional analysis
        if include_comment_analysis and hasattr(issue.fields, 'comment') and issue.fields.comment.comments:
            comments = issue.fields.comment.comments
            result += f"**Comments Analysis ({len(comments)} total):**\n"
            
            # Perform comment analysis
            threshold_date = datetime.now() - timedelta(days=5)  # Use 5-day threshold for analysis
            analysis = analyze_comments(comments, threshold_date)
            
            # Display AI-ready analysis results
            result += f"🧠 **AI-Ready Comment Analysis:**\n"
            result += f"   • Total Comments: {analysis['summary']['total_comments']}\n"
            result += f"   • Last 5 Available: {analysis['summary']['last_5_count']}\n"
            result += f"   • Unique Authors: {analysis['summary']['unique_authors']}\n"
            result += f"   • Activity Level: {analysis['summary']['activity_level']}\n"
            result += f"   • Last Activity: {analysis['summary']['last_activity']}\n"
            result += f"   • Participants: {', '.join(analysis['summary']['participant_list'])}\n"
            
            result += f"\n📝 **Last {len(analysis['raw_comments'])} Comments for AI Analysis:**\n"
            for comment in analysis['raw_comments']:
                content_preview = comment['content'][:200] + "..." if len(comment['content']) > 200 else comment['content']
                result += f"   {comment['position']}. [{comment['date']}] {comment['author']} ({comment['days_ago']} days ago):\n"
                result += f"      \"{content_preview}\"\n\n"
            
            result += f"💡 **Note:** {analysis['analysis_note']}"
        else:
            # Simple comment display without analysis
            await rate_limit()
            comments = jira_client.comments(issue)
            if comments:
                result += f"**Comments ({len(comments)}):**\n"
                for comment in comments[-5:]:  # Show last 5 comments
                    result += f"- {comment.author.displayName} ({comment.created}): {comment.body[:200]}{'...' if len(comment.body) > 200 else ''}\n"
            else:
                result += "**Comments:** No comments found.\n"
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"


@app.tool()
async def jira_analyze_issue_comments(issue_key: str, days_threshold: int = 5) -> str:
    """
    Perform detailed comment analysis on a specific JIRA issue.
    
    This is a standalone tool that focuses purely on comment analysis,
    providing rich insights that can be used by AI assistants for understanding
    issue context, urgency, and activity patterns.
    
    Args:
        issue_key: The JIRA issue key (e.g., 'OCPBUGS-12345')
        days_threshold: Number of days to consider for staleness analysis (default: 5)
    
    Returns:
        Detailed comment analysis with keywords, patterns, and insights
    """
    if not jira_client:
        await init_jira_client()
    
    try:
        await rate_limit()
        # Fetch issue with comments expanded
        issue = jira_client.issue(issue_key, expand='comments')
        
        if not hasattr(issue.fields, 'comment') or not issue.fields.comment.comments:
            return f"**Issue {issue_key}: No Comments Analysis**\n\nNo comments found for analysis."
        
        comments = issue.fields.comment.comments
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        
        # Perform detailed comment analysis
        analysis = analyze_comments(comments, threshold_date)
        
        # Build comprehensive analysis report
        result = f"**🔍 Comment Analysis for {issue_key}**\n"
        result += f"**Issue:** {issue.fields.summary}\n"
        result += f"**Status:** {issue.fields.status.name}\n\n"
        
        result += f"🧠 **AI-Ready Analysis Overview:**\n"
        result += f"   • Total Comments: {analysis['summary']['total_comments']}\n"
        result += f"   • Last 5 Available: {analysis['summary']['last_5_count']}\n"
        result += f"   • Unique Authors: {analysis['summary']['unique_authors']}\n"
        result += f"   • Activity Level: {analysis['summary']['activity_level']}\n"
        result += f"   • Last Activity: {analysis['summary']['last_activity']}\n"
        result += f"   • Analysis Threshold: {days_threshold} days\n"
        result += f"   • Participants: {', '.join(analysis['summary']['participant_list'])}\n\n"
        
        # Full Comment Thread for AI Analysis
        if analysis['raw_comments']:
            result += f"📝 **Complete Comment Thread (Last {len(analysis['raw_comments'])} Comments):**\n"
            result += f"*AI Assistant: Analyze these comments to provide insights about the issue status, progress, blockers, and next steps.*\n\n"
            
            for comment in analysis['raw_comments']:
                result += f"**Comment {comment['position']} - {comment['author']}** ({comment['date']} - {comment['days_ago']} days ago)\n"
                result += f"```\n{comment['content']}\n```\n\n"
        
        # AI Analysis Prompt
        result += f"🤖 **AI Analysis Prompt:**\n"
        result += f"Based on the above {len(analysis['raw_comments'])} comments, please analyze:\n"
        result += f"   • Current status and progress of the issue\n"
        result += f"   • Any blockers or dependencies mentioned\n"
        result += f"   • Urgency level and escalation needs\n"
        result += f"   • Recommended next steps\n"
        result += f"   • Key stakeholders and their roles\n\n"
        result += f"💡 **Analysis Ready:** {analysis['analysis_note']}\n"
        result += f"🎯 **AI Assistant:** Use the comment thread above to provide detailed insights about this issue."
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"
    except Exception as e:
        return f"Error analyzing comments: {str(e)}"


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


def parse_stale_issues_data(stale_data: str) -> Dict[str, Any]:
    """
    Parse the stale issues output data and organize it by Telco priority and release.
    
    Args:
        stale_data: The raw output from _find_stale_issues_core function
        
    Returns:
        Dictionary containing parsed metrics and organized issues
    """
    lines = stale_data.split('\n')
    
    # Extract summary information
    total_stale = 0
    total_analyzed = 0
    no_comments_count = 0
    
    # Parse the data to extract key metrics with improved error handling
    for line in lines:
        try:
            if "STALE ISSUES COUNT:" in line:
                # Extract number from line, handling various formats
                count_text = line.split(":")[-1].strip()
                # Remove any non-digit characters except for the number itself
                numbers = re.findall(r'\d+', count_text)
                if numbers:
                    total_stale = int(numbers[0])
            elif "Total issues analyzed:" in line:
                # Extract number from line, handling various formats
                count_text = line.split(":")[-1].strip()
                numbers = re.findall(r'\d+', count_text)
                if numbers:
                    total_analyzed = int(numbers[0])
            elif "No comments" in line and "📝" in line:
                no_comments_count += 1
        except (ValueError, IndexError) as e:
            # Skip lines that can't be parsed
            continue
    
    # If parsing failed to find the counts, try alternative parsing methods
    if total_stale == 0 and total_analyzed == 0:
        # Count stale issues directly from the output
        for line in lines:
            if line.strip().startswith("🐛 **") and ":" in line:
                total_stale += 1
            elif "Found" in line and "issues" in line and "analyzed" in line:
                # Try to extract from "Found X issues (limited to Y for performance)"
                numbers = re.findall(r'\d+', line)
                if numbers:
                    total_analyzed = int(numbers[0])
    
    # Calculate metrics
    stale_rate = int((total_stale / total_analyzed * 100)) if total_analyzed > 0 else 0
    non_stale_count = max(0, total_analyzed - total_stale)
    
    # Parse individual issues and organize by Telco priority and release
    issues_by_priority = {
        'Priority-1': {},
        'Priority-2': {},
        'Priority-3': {}
    }
    
    current_issue = None
    i = 0
    max_iterations = len(lines) * 2  # Safety limit
    iteration_count = 0
    while i < len(lines) and iteration_count < max_iterations:
        iteration_count += 1
        line = lines[i].strip()
        
        # Look for issue entries
        if line.startswith("🐛 **") and ":" in line:
            # Extract issue key and summary
            issue_match = re.match(r'🐛 \*\*([A-Z]+-\d+)\*\*: (.+)', line)
            if issue_match:
                issue_key = issue_match.group(1)
                summary = issue_match.group(2)
                
                # Initialize issue data
                current_issue = {
                    'key': issue_key,
                    'summary': summary,
                    'status': 'Unknown',
                    'assignee': 'Unassigned',
                    'telco_priority': 'Priority-3',  # default
                    'versions': [],
                    'comment_age': 'Unknown',
                    'analysis': 'No analysis available'
                }
                
                # Parse the following lines for issue details
                j = i + 1
                detail_line_count = 0
                max_detail_lines = 100  # Safety limit
                while j < len(lines) and detail_line_count < max_detail_lines and not lines[j].strip().startswith("🐛 **"):
                    detail_line_count += 1
                    detail_line = lines[j].strip()
                    
                    if detail_line.startswith("📋 Status:"):
                        current_issue['status'] = detail_line.split(":", 1)[1].strip()
                    elif detail_line.startswith("👤 Assignee:"):
                        current_issue['assignee'] = detail_line.split(":", 1)[1].strip()
                    elif detail_line.startswith("🎯 Telco Priority:"):
                        telco_text = detail_line.split(":", 1)[1].strip()
                        if "Priority-1" in telco_text:
                            current_issue['telco_priority'] = 'Priority-1'
                        elif "Priority-2" in telco_text:
                            current_issue['telco_priority'] = 'Priority-2'
                        else:
                            current_issue['telco_priority'] = 'Priority-3'
                    elif detail_line.startswith("📦 Affects Versions:"):
                        versions_text = detail_line.split(":", 1)[1].strip()
                        current_issue['versions'] = [v.strip() for v in versions_text.split(",")]
                    elif detail_line.startswith("🕒 Last Comment:") or detail_line.startswith("🕒 Last Activity:"):
                        current_issue['comment_age'] = detail_line.split(":", 1)[1].strip()
                    elif detail_line.startswith("🔍 AI Insights:"):
                        current_issue['analysis'] = detail_line.split(":", 1)[1].strip()
                    elif detail_line.startswith("📝 **Last") and "Comments" in detail_line:
                        # Found comment section - parse the detailed comments
                        comment_texts = []
                        j += 1
                        max_comment_lines = 50  # Safety limit to prevent infinite loops
                        comment_line_count = 0
                        while j < len(lines) and comment_line_count < max_comment_lines:
                            comment_line = lines[j].strip()
                            comment_line_count += 1
                            
                            # Stop if we hit the next issue or URL line or empty line
                            if not comment_line or comment_line.startswith("🐛 **") or comment_line.startswith("🔗 URL:") or comment_line.startswith("="*10):
                                j -= 1
                                break
                            # Parse comment lines (format: "1. [Author] (X days ago):")
                            if re.match(r'^\d+\.', comment_line):
                                # Extract just the content part
                                if j + 1 < len(lines):
                                    content_line = lines[j + 1].strip()
                                    if content_line and not content_line.startswith(("🐛", "🔗", "📝", "🔍", "💬", "🕒")):
                                        # Clean up and limit length
                                        clean_content = content_line[:200]
                                        comment_texts.append(clean_content)
                                        j += 1
                            j += 1
                        
                        # Override the simple "Low activity" analysis with actual comment content
                        if comment_texts:
                            # Format with line breaks for readability
                            formatted_comments = []
                            for comment_idx, text in enumerate(comment_texts[:3], 1):
                                # Clean up text
                                clean_text = text.strip()
                                formatted_comments.append(f"<strong>Recent comment {comment_idx}:</strong><br>{clean_text}")
                            current_issue['analysis'] = "<br><br>".join(formatted_comments)
                        j -= 1  # Back up since the outer loop will increment
                    
                    j += 1
                
                # Update i to skip all the lines we just parsed
                i = j - 1  # -1 because the outer loop will increment i at the end
                
                # Organize by priority and primary release
                # Each issue appears only once, grouped by its primary (first) release
                priority = current_issue['telco_priority']
                
                if current_issue['versions']:
                    # Use the first version as the primary release for grouping
                    first_version = current_issue['versions'][0]
                    major_version = re.match(r'(\d+\.\d+)', first_version)
                    if major_version:
                        release = major_version.group(1)
                        if release not in issues_by_priority[priority]:
                            issues_by_priority[priority][release] = []
                        issues_by_priority[priority][release].append(current_issue)
                    else:
                        # Couldn't extract version, put in Unknown
                        if "Unknown" not in issues_by_priority[priority]:
                            issues_by_priority[priority]["Unknown"] = []
                        issues_by_priority[priority]["Unknown"].append(current_issue)
                else:
                    # No versions found, put in "Unknown" release
                    if "Unknown" not in issues_by_priority[priority]:
                        issues_by_priority[priority]["Unknown"] = []
                    issues_by_priority[priority]["Unknown"].append(current_issue)
        
        i += 1
    
    return {
        'total_stale': total_stale,
        'total_analyzed': total_analyzed,
        'stale_rate': stale_rate,
        'non_stale_count': non_stale_count,
        'no_comments_count': no_comments_count,
        'issues_by_priority': issues_by_priority
    }


def generate_priority_sections_html(issues_by_priority: Dict[str, Dict[str, List[Dict]]]) -> str:
    """
    Generate HTML sections for each Telco priority with organized issues.
    
    Args:
        issues_by_priority: Dictionary of issues organized by priority and release
        
    Returns:
        HTML string containing all priority sections
    """
    priority_sections = ""
    
    for priority in ['Priority-1', 'Priority-2', 'Priority-3']:
        priority_class = priority.lower().replace('-', '_')
        priority_num = priority.split('-')[1]
        
        # Count total issues for this priority
        total_priority_issues = sum(len(issues) for issues in issues_by_priority[priority].values())
        
        priority_sections += f'''
            <!-- TELCO {priority.upper()} ISSUES -->
            <div class="section">
                <h2><span class="priority-badge priority-{priority_num}">Telco {priority}</span> Issues ({total_priority_issues} issues)</h2>
        '''
        
        if total_priority_issues == 0:
            priority_sections += f'<p style="color: #28a745; font-weight: 600;">No {priority} issues found in stale state.</p>'
        else:
            # Sort releases
            releases = sorted(issues_by_priority[priority].keys(), key=lambda x: x if x != "Unknown" else "0.0")
            
            for release in releases:
                issues = issues_by_priority[priority][release]
                priority_sections += f'''
                <h3>{release} Release ({len(issues)} issues)</h3>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 8%;">Issue</th>
                            <th style="width: 25%;">Summary</th>
                            <th style="width: 7%;">Status</th>
                            <th style="width: 10%;">Assignee</th>
                            <th style="width: 8%;">Versions</th>
                            <th style="width: 10%;">Comment Age</th>
                            <th style="width: 32%;">Analysis</th>
                        </tr>
                    </thead>
                    <tbody>
                '''
                
                for issue in issues:
                    # Determine status class
                    status_class = issue['status'].lower().replace(' ', '_').replace('-', '_')
                    
                    # Determine age class
                    age_class = "age-normal"
                    if "days" in issue['comment_age']:
                        days_match = re.search(r'(\d+) days', issue['comment_age'])
                        if days_match:
                            days = int(days_match.group(1))
                            if days > 30:
                                age_class = "age-critical"
                            elif days > 14:
                                age_class = "age-warning"
                    
                    # Format affected versions - extract major versions only
                    versions_display = []
                    for v in issue['versions']:
                        major_v = re.match(r'(\d+\.\d+)', v)
                        if major_v:
                            versions_display.append(major_v.group(1))
                    # Remove duplicates and sort
                    versions_display = sorted(set(versions_display))
                    versions_str = ', '.join(versions_display) if versions_display else 'N/A'
                    
                    priority_sections += f'''
                        <tr>
                            <td><a href="https://issues.redhat.com/browse/{issue['key']}" class="issue-link" target="_blank">{issue['key']}</a></td>
                            <td>{issue['summary']}</td>
                            <td><span class="status-badge status-{status_class}">{issue['status']}</span></td>
                            <td>{issue['assignee']}</td>
                            <td style="font-weight: 600; color: #667eea;">{versions_str}</td>
                            <td class="comment-age {age_class}">{issue['comment_age']}</td>
                            <td class="analysis-text">{issue['analysis']}</td>
                        </tr>
                    '''
                
                priority_sections += '''
                    </tbody>
                </table>
                '''
        
        priority_sections += '</div>'
    
    return priority_sections


def analyze_comments(comments: List[Any], threshold_date: datetime) -> Dict[str, Any]:
    """
    Fetch and structure the last 5 comments for AI analysis.
    
    Plan 2: Hybrid AI + Structured Analysis
    - Provides both structured summary AND raw comments for AI reasoning
    - AI assistant can use summary for quick insights or analyze raw comments
    - Optimized for both automated reports and interactive analysis
    """
    if not comments:
        return {
            'summary': {
                'total_comments': 0,
                'last_5_count': 0,
                'unique_authors': 0,
                'last_activity': 'No comments available',
                'activity_level': 'None',
                'has_recent_activity': False,
                'participant_list': []
            },
            'raw_comments': [],
            'ai_analysis_ready': True,
            'analysis_note': 'No comments to analyze'
        }
    
    # Sort comments by creation date (most recent first)
    sorted_comments = sorted(comments, key=lambda c: c.created, reverse=True)
    
    # Get last 5 comments for AI analysis
    last_5_comments = sorted_comments[:5]
    
    # Extract structured data for summary
    authors = set()
    comment_dates = []
    
    # Prepare raw comments for AI analysis
    raw_comments_for_ai = []
    
    for i, comment in enumerate(last_5_comments, 1):
        # Extract author info
        author_name = "Unknown"
        if hasattr(comment, 'author') and hasattr(comment.author, 'displayName'):
            author_name = comment.author.displayName
            authors.add(author_name)
        
        # Extract comment date with proper type handling
        comment_date = comment.created
        comment_dates.append(comment_date)
        
        # Convert comment date to datetime if it's a string
        if isinstance(comment_date, str):
            try:
                # Parse JIRA date format
                if 'T' in comment_date:
                    comment_date = comment_date.split('T')[0] + 'T' + comment_date.split('T')[1][:19]
                comment_date = datetime.fromisoformat(comment_date.replace('Z', '+00:00'))
                if comment_date.tzinfo:
                    comment_date = comment_date.replace(tzinfo=None)
            except ValueError:
                # If parsing fails, use current time as fallback
                comment_date = datetime.now()
        
        # Format comment for AI analysis
        comment_for_ai = {
            'position': i,  # 1 = most recent, 5 = oldest of the 5
            'date': comment_date.strftime('%Y-%m-%d %H:%M') if comment_date else 'Unknown',
            'author': author_name,
            'content': comment.body if hasattr(comment, 'body') and comment.body else "[No content]",
            'days_ago': (datetime.now() - comment_date).days if comment_date else None
        }
        
        raw_comments_for_ai.append(comment_for_ai)
    
    # Calculate activity metrics (need to convert dates for comparison)
    recent_comments = []
    for c in sorted_comments:
        comment_created = c.created
        # Convert to datetime if it's a string
        if isinstance(comment_created, str):
            try:
                if 'T' in comment_created:
                    comment_created = comment_created.split('T')[0] + 'T' + comment_created.split('T')[1][:19]
                comment_created = datetime.fromisoformat(comment_created.replace('Z', '+00:00'))
                if comment_created.tzinfo:
                    comment_created = comment_created.replace(tzinfo=None)
            except ValueError:
                # If parsing fails, skip this comment
                continue
        
        # Now we can safely compare datetime objects
        if isinstance(comment_created, datetime) and comment_created >= threshold_date:
            recent_comments.append(c)
    
    has_recent_activity = len(recent_comments) > 0
    
    if len(recent_comments) >= 3:
        activity_level = "High"
    elif len(recent_comments) >= 1:
        activity_level = "Moderate" 
    else:
        activity_level = "Low"
    
    # Get last activity info
    last_activity = "No recent activity"
    if sorted_comments:
        last_comment = sorted_comments[0]
        last_author = getattr(last_comment.author, 'displayName', 'Unknown') if hasattr(last_comment, 'author') else 'Unknown'
        
        # Handle last comment date with proper type checking
        last_comment_date = last_comment.created
        if isinstance(last_comment_date, str):
            try:
                if 'T' in last_comment_date:
                    last_comment_date = last_comment_date.split('T')[0] + 'T' + last_comment_date.split('T')[1][:19]
                last_comment_date = datetime.fromisoformat(last_comment_date.replace('Z', '+00:00'))
                if last_comment_date.tzinfo:
                    last_comment_date = last_comment_date.replace(tzinfo=None)
            except ValueError:
                last_comment_date = datetime.now()
        
        days_since = (datetime.now() - last_comment_date).days if last_comment_date else 0
        last_activity = f"{last_comment_date.strftime('%Y-%m-%d')} by {last_author} ({days_since} days ago)"
    
    return {
        'summary': {
            'total_comments': len(comments),
            'last_5_count': len(last_5_comments),
            'unique_authors': len(authors),
            'last_activity': last_activity,
            'activity_level': activity_level,
            'has_recent_activity': has_recent_activity,
            'participant_list': list(authors)
        },
        'raw_comments': raw_comments_for_ai,
        'ai_analysis_ready': True,
        'analysis_note': f"Last {len(last_5_comments)} comments available for AI analysis"
    }


async def _find_stale_issues_core(
    days_threshold: int = 14,
    include_no_comments: bool = True,
    affects_versions: List[str] = [],
    max_results: int = 50,
    additional_components: List[str] = [],
    override_components: List[str] = [],
    additional_projects: List[str] = [],
    override_projects: List[str] = [],
    strict_bugs_only: bool = True,
    include_comment_analysis: bool = True,
    team_id: Optional[str] = None
):
    """Find stale Telco priority bugs with no recent comments.
    
    Args:
        days_threshold: Days threshold for staleness (default: 14)
        include_no_comments: Include issues with no comments (default: True)
        affects_versions: Filter by specific versions (default: [])
        max_results: Maximum number of results (default: 50)
        additional_components: Additional components to include with defaults (default: [])
        override_components: If specified, search ONLY these components (ignores defaults) (default: [])
        additional_projects: Additional projects to include with defaults (default: [])
        override_projects: If specified, search ONLY these projects (ignores defaults) (default: [])
        strict_bugs_only: Only include bug-type issues, exclude stories/epics/tasks (default: True)
        include_comment_analysis: Include detailed comment analysis for AI processing (default: True)
    """
    if not jira_client:
        await init_jira_client()
    
    try:
        # TEAM CONFIGURATION: Load team-specific defaults if team_id provided
        team_config = None
        if team_id:
            try:
                team_config = get_team_config(team_id)
                print(f"🏢 Using configuration for: {team_config.team_name}", file=sys.stderr)
            except ValueError as e:
                return {
                    'formatted_output': f"Error: {str(e)}",
                    'total_issues_analyzed': 0,
                    'total_stale_issues': 0,
                    'stale_rate': 0
                }
        else:
            # Use default team (Deployment) if no team specified
            team_config = get_default_team()
        
        # Check if team uses custom JQL base
        if team_config and team_config.use_custom_jql:
            # Team has a custom JQL base query - use it directly
            print(f"🎯 Using custom JQL base for {team_config.team_name}", file=sys.stderr)
            jql_base = team_config.custom_jql_base
            
            # Add affects_versions filter if provided
            if affects_versions:
                version_variants = []
                for version in affects_versions:
                    version_variants.append(f'"{version}"')
                    version_variants.append(f'"{version}.z"')
                version_list = ", ".join(version_variants)
                jql = f'({jql_base}) AND affectedVersion in ({version_list})'
            else:
                jql = jql_base
            
            # Add ordering
            jql += ' ORDER BY updated ASC'
            
        else:
            # Standard JQL construction (for teams without custom JQL)
            # PROJECT HANDLING: Flexible project selection
            if override_projects:
                # User wants to search ONLY specific projects
                project_list = ", ".join(override_projects)
                project_clause = f'project in ({project_list})'
            else:
                # Use team's default projects + any additional ones
                default_projects = team_config.default_projects
                all_projects = default_projects + additional_projects
                project_list = ", ".join(all_projects)
                project_clause = f'project in ({project_list})'
            
            # BASE JQL with flexible projects and strict bug filtering
            jql_parts = [
                project_clause,
                'status not in (Verified, ON_QA, Closed, "Release Pending")',
                'assignee is not EMPTY'
            ]
            
            # Add team-specific priority filtering
            if team_config:
                priority_clause = team_config.get_jql_priority_clause()
                if priority_clause:
                    jql_parts.append(priority_clause)
            
            # STRICT BUG FILTERING: Only include bug-type issues
            if strict_bugs_only:
                jql_parts.append('issuetype = Bug')
        
            # COMPONENT HANDLING: Flexible component selection
            if override_components:
                # User wants to search ONLY specific components
                component_list = ", ".join([f'"{comp}"' for comp in override_components])
                jql_parts.append(f'component in ({component_list})')
            else:
                # Use team's default components + any additional ones
                default_components = team_config.default_components
                
                # Combine default and additional components
                all_components = default_components + additional_components
                if all_components:
                    # Filter out empty strings
                    all_components = [comp for comp in all_components if comp.strip()]
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
            
            # Build and execute JQL query with ordering
            jql = " AND ".join(jql_parts) + " ORDER BY updated ASC"
        
        # Increase cap to allow more results (100 max for better coverage)
        max_results_cap = min(max_results, 100)
        
        logger.info(f"Executing JQL: {jql}")
        await rate_limit()
        # Single optimized call: get issues with comments and all needed fields
        issues = jira_client.search_issues(
            jql,
            maxResults=max_results_cap,
            expand='changelog,comments',  # Get comments in the same call!
            fields='summary,status,assignee,reporter,priority,issuetype,project,created,updated,components,versions,comment,customfield_12323649'
        )
        
        logger.info(f"JQL returned {len(issues)} total issues for analysis")
        
        if not issues:
            return "✅ No issues found matching the JQL criteria."
        
        # Calculate the threshold date
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        stale_issues = []
        
        # Build search summary
        if override_projects:
            projects_used = override_projects
            project_mode = f"🎯 Override mode: ONLY {', '.join(override_projects)}"
        else:
            projects_used = ["OCPBUGS"] + additional_projects
            if additional_projects:
                project_mode = f"📦 Default projects (OCPBUGS) + {', '.join(additional_projects)}"
            else:
                project_mode = f"📦 Default projects: OCPBUGS"
        
        # Don't show confusing preview numbers - wait until we have actual stale count
        result_preview = f"🔍 **Telco Priority Stale Issues Search**\n"
        result_preview += f"📊 Analyzing {len(issues)} issues (limited to {max_results} for performance)\n"
        result_preview += f"⏰ Staleness threshold: {days_threshold} days\n"
        result_preview += f"{project_mode}\n"
        result_preview += f"🐛 Issue types: {'Bugs only' if strict_bugs_only else 'All types'}\n"
        result_preview += f"⚡ Optimized: Single API call with expanded fields\n"
        result_preview += f"🧠 Enhanced: AI-ready comment analysis {'enabled' if include_comment_analysis else 'disabled'}\n"
        if affects_versions:
            result_preview += f"🎯 Affects versions: {', '.join(affects_versions)} (including .z variants)\n"
        
        # Component display logic
        if override_components:
            result_preview += f"🔧 Components: ONLY {', '.join(override_components)} (override mode)\n"
        elif additional_components:
            result_preview += f"🔧 Components: Default + {', '.join(additional_components)}\n"
        else:
            result_preview += f"🔧 Components: Default Telco components\n"
        
        result_preview += f"📋 Results ordered by: Last updated (oldest first)\n\n"
        
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
                    # Parse the comment date (JIRA can return string or datetime)
                    comment_date = latest_comment.created
                    
                    # Normalize to datetime object if it's a string
                    if isinstance(comment_date, str):
                        comment_date_str = comment_date
                    # Remove timezone info and microseconds for parsing
                    if 'T' in comment_date_str:
                        comment_date_str = comment_date_str.split('T')[0] + 'T' + comment_date_str.split('T')[1][:19]
                    
                    try:
                        latest_comment_date = datetime.fromisoformat(comment_date_str.replace('Z', '+00:00'))
                        # Convert to naive datetime for comparison
                        if latest_comment_date.tzinfo:
                            latest_comment_date = latest_comment_date.replace(tzinfo=None)
                    except ValueError:
                        # If we can't parse the date, treat as stale
                        is_stale = True
                        latest_comment_date = comment_date_str
                    else:
                        # Already a datetime object
                        latest_comment_date = comment_date
                        # Convert to naive datetime for comparison
                        if latest_comment_date.tzinfo:
                            latest_comment_date = latest_comment_date.replace(tzinfo=None)
                    
                    # Compare dates
                    if isinstance(latest_comment_date, datetime) and latest_comment_date < threshold_date:
                        is_stale = True
                
                if is_stale:
                    issue_data = {
                        'issue': issue,
                        'latest_comment_date': latest_comment_date,
                        'comments_count': len(comments)
                    }
                    
                    # Add detailed comment analysis if requested
                    if include_comment_analysis:
                        issue_data['comment_analysis'] = analyze_comments(comments, threshold_date)
                    
                    stale_issues.append(issue_data)
                    
            except Exception as e:
                logger.warning(f"Error processing issue {issue.key}: {str(e)}")
                continue
        
        logger.info(f"Comment analysis complete: {len(stale_issues)} stale out of {len(issues)} total issues")
        
        if not stale_issues:
            return f"{result_preview}✅ **RESULT: 0 stale issues found!**\n📊 Analyzed {len(issues)} total issues - all have recent activity within {days_threshold} days."
        
        # Format results with clear summary
        result = result_preview
        result += f"🚨 **RESULT: {len(stale_issues)} STALE ISSUES FOUND**\n"
        result += f"📊 Analysis Summary: Found {len(stale_issues)} stale out of {len(issues)} total issues analyzed\n"
        result += f"📋 Criteria: No comments OR last comment older than {days_threshold} days\n\n"
        
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
            # Integrated comment analysis for AI consumption
            if include_comment_analysis and 'comment_analysis' in item:
                analysis = item['comment_analysis']
                
                # Compact comment info with analysis
                result += f"   💬 Comments: {comments_count} ({analysis['summary']['unique_authors']} authors, {analysis['summary']['activity_level'].lower()})\n"
                
                # Last activity with context
                if latest_date == "No comments":
                    result += f"   🕒 Last Activity: No comments (Created: {issue.fields.created[:10]})\n"
                else:
                    if isinstance(latest_date, datetime):
                        days_old = (datetime.now() - latest_date).days
                        result += f"   🕒 Last Comment: {latest_date.strftime('%Y-%m-%d')} ({days_old} days ago)\n"
                    else:
                        result += f"   🕒 Last Comment: {latest_date}\n"
                
                # AI-ready insights
                ai_insights = []
                if analysis['summary']['activity_level'] == 'High':
                    ai_insights.append("High activity")
                elif analysis['summary']['activity_level'] == 'Low':
                    ai_insights.append("Low activity")
                
                if analysis['summary']['has_recent_activity']:
                    ai_insights.append("Recent comments available")
                else:
                    ai_insights.append("No recent activity")
                
                if len(analysis['summary']['participant_list']) > 3:
                    ai_insights.append(f"{len(analysis['summary']['participant_list'])} participants")
                
                if ai_insights:
                    result += f"   🔍 AI Insights: {' | '.join(ai_insights)}\n"
                
                # Include full comment thread for AI analysis
                if analysis['raw_comments']:
                    result += f"\n   📝 **Last {len(analysis['raw_comments'])} Comments (for AI Analysis):**\n"
                    for idx, comment in enumerate(analysis['raw_comments'], 1):
                        content_preview = comment['content'][:300] if len(comment['content']) <= 300 else comment['content'][:300] + "..."
                        result += f"      {idx}. [{comment['author']}] ({comment['days_ago']} days ago):\n"
                        result += f"         {content_preview}\n\n"
            else:
                # Simple comment display without analysis
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
        result += f"```\n{jql}\n```\n"
        result += f"\n💡 **Note:** Comment date filtering is done programmatically after JQL search.\n"
        result += f"🎯 **Search Criteria:**\n"
        result += f"   • Projects: {', '.join(projects_used)}\n"
        result += f"   • Issue Types: {'Bugs only' if strict_bugs_only else 'All types'}\n"
        result += f"   • Telco Priority: 1, 2, 3\n"
        result += f"   • Status: Excluding Verified, ON_QA, Closed, Release Pending\n"
        result += f"   • Assignment: Only assigned issues\n"
        
        # Component criteria display
        if override_components:
            result += f"   • Components: ONLY {', '.join(override_components)} (override mode)\n"
        elif additional_components:
            default_components = ["GitOps ZTP", "Bare Metal Hardware Provisioning / baremetal-operator", "Bare Metal Hardware Provisioning / ironic", "Bare Metal Hardware Provisioning", "Networking / SR-IOV", "Installer / Assisted Installer", "oc / cluster-compare"]
            all_components = default_components + additional_components
            result += f"   • Components: Default + Additional ({', '.join(additional_components)})\n"
        else:
            result += f"   • Components: Default Telco components\n"
        
        result += f"   • Ordering: Last updated (oldest first)\n"
        result += f"   • Comment Counting: ALL comments (including bot/system comments)\n"
        
        # Clear final summary to avoid confusion
        result += f"\n" + "="*60 + "\n"
        result += f"📊 **FINAL SUMMARY:**\n"
        result += f"🔢 **STALE ISSUES FOUND: {len(stale_issues)} out of {len(issues)} analyzed**\n"
        result += f"📋 Total issues from JQL query: {len(issues)}\n"
        result += f"🎯 Issues meeting staleness criteria: {len(stale_issues)}\n"
        result += f"⏰ Staleness criteria: Comments older than {days_threshold} days\n"
        result += f"="*60 + "\n"
        
        # Return both the formatted string and raw metrics
        return {
            'formatted_output': result,
            'total_issues_analyzed': len(issues),
            'total_stale_issues': len(stale_issues),
            'stale_rate': int((len(stale_issues) / len(issues) * 100)) if len(issues) > 0 else 0
        }
        
    except JIRAError as e:
        return {
            'formatted_output': f"JIRA Error: {str(e)}",
            'total_issues_analyzed': 0,
            'total_stale_issues': 0,
            'stale_rate': 0
        }
    except Exception as e:
        return {
            'formatted_output': f"Error: {str(e)}",
            'total_issues_analyzed': 0,
            'total_stale_issues': 0,
            'stale_rate': 0
        }


@app.tool()
async def jira_find_stale_issues(
    days_threshold: int = 14,
    include_no_comments: bool = True,
    affects_versions: List[str] = [],
    max_results: int = 50,
    additional_components: List[str] = [],
    override_components: List[str] = [],
    additional_projects: List[str] = [],
    override_projects: List[str] = [],
    strict_bugs_only: bool = True,
    include_comment_analysis: bool = True,
    team_id: Optional[str] = None
) -> str:
    """Find stale priority bugs with no recent comments using team-specific configuration.
    
    Args:
        days_threshold: Days threshold for staleness (default: 14)
        include_no_comments: Include issues with no comments (default: True)
        affects_versions: Filter by specific versions (default: [])
        max_results: Maximum number of results (default: 50)
        additional_components: Additional components to include with team defaults (default: [])
        override_components: If specified, search ONLY these components (ignores team defaults) (default: [])
        additional_projects: Additional projects to include with team defaults (default: [])
        override_projects: If specified, search ONLY these projects (ignores team defaults) (default: [])
        strict_bugs_only: Only include bug-type issues, exclude stories/epics/tasks (default: True)
        include_comment_analysis: Include detailed comment analysis for AI processing (default: True)
        team_id: Team identifier (e.g., 'deployment', 'ptp', 'networking'). Use jira_list_teams() to see available teams. (default: None = deployment team)
    """
    result = await _find_stale_issues_core(
        days_threshold=days_threshold,
        include_no_comments=include_no_comments,
        affects_versions=affects_versions,
        max_results=max_results,
        additional_components=additional_components,
        override_components=override_components,
        additional_projects=additional_projects,
        override_projects=override_projects,
        strict_bugs_only=strict_bugs_only,
        include_comment_analysis=include_comment_analysis,
        team_id=team_id
    )
    # Return only the formatted string for the MCP tool
    return result['formatted_output']


@app.tool()
async def jira_generate_stale_issues_report(
    days_threshold: int = 5,
    include_no_comments: bool = True,
    affects_versions: List[str] = [],
    additional_projects: List[str] = [],
    override_projects: List[str] = [],
    strict_bugs_only: bool = True,
    additional_components: List[str] = [],
    override_components: List[str] = [],
    max_results: int = 100,
    include_comment_analysis: bool = True,
    report_filename: str = "stale_issues_report.html",
    custom_analysis: str = "",
    key_findings: str = "",
    executive_summary: str = "",
    team_id: Optional[str] = None
) -> str:
    """
    Generate a comprehensive HTML report for stale JIRA issues using the enhanced template.
    
    **WORKFLOW FOR AI-GENERATED ANALYSIS:**
    
    1. First, call jira_find_stale_issues to get issues with comments
    2. Analyze each issue and create a summary in this EXACT format:
    
    ```
    ISSUE: OCPBUGS-12345
    ANALYSIS: Brief summary of current status, blockers, and progress
    ---
    ISSUE: OCPBUGS-67890
    ANALYSIS: Another concise analysis
    ---
    ```
    
    3. Pass the entire analysis text as the 'custom_analysis' parameter
    4. The report will use your AI analysis in the Analysis column
    
    **If no custom_analysis is provided:**
    The report will show excerpts from the last 3 JIRA comments as fallback.
    
    Args:
        days_threshold: Number of days to consider an issue stale (default: 5)
        include_no_comments: Include issues with zero comments (default: True)
        affects_versions: List of specific versions to filter by (e.g., ["4.14", "4.16"])
        additional_projects: Additional projects to search beyond defaults
        override_projects: Override default projects with these specific projects
        strict_bugs_only: Only include Bug type issues (default: True)
        additional_components: Additional components to search beyond defaults
        override_components: Override default components with these specific components
        max_results: Maximum number of issues to analyze (default: 100)
        include_comment_analysis: Include AI-powered comment analysis (default: True)
        report_filename: Name of the generated HTML file (default: "stale_issues_report.html")
        custom_analysis: AI-generated analysis in the format: "ISSUE: KEY\nANALYSIS: text\n---" (default: "")
        key_findings: Key findings summary to display in the Executive Dashboard (newline-separated list) (default: "")
        executive_summary: AI-generated executive summary narrative (plain text or multiple paragraphs separated by double newlines) (default: "")
        team_id: Team identifier (e.g., 'deployment', 'ptp', 'networking'). Use jira_list_teams() to see available teams. (default: None = deployment team)

    Returns:
        Status message with report location and summary
    """
    try:
        # First, get the stale issues data using the core helper function
        result = await _find_stale_issues_core(
            days_threshold=days_threshold,
            include_no_comments=include_no_comments,
            affects_versions=affects_versions,
            additional_projects=additional_projects,
            override_projects=override_projects,
            strict_bugs_only=strict_bugs_only,
            additional_components=additional_components,
            override_components=override_components,
            max_results=max_results,
            include_comment_analysis=include_comment_analysis,
            team_id=team_id
        )
        
        # Extract raw metrics from the result dictionary
        total_issues_analyzed = result['total_issues_analyzed']
        total_stale = result['total_stale_issues']
        stale_rate = result['stale_rate']
        stale_data = result['formatted_output']
        
        # Parse the stale data using the helper function (for issue details)
        parsed_data = parse_stale_issues_data(stale_data)
        
        # Use accurate metrics from the core function
        total_analyzed = total_issues_analyzed
        non_stale_count = total_analyzed - total_stale
        issues_by_priority = parsed_data['issues_by_priority']
        
        # Apply custom AI analysis if provided
        if custom_analysis and custom_analysis.strip():
            custom_analysis_map = {}
            # Parse format: "ISSUE: KEY\nANALYSIS: text\n---"
            entries = custom_analysis.strip().split('---')
            for entry in entries:
                entry = entry.strip()
                if not entry:
                    continue
                lines = entry.split('\n')
                issue_key = None
                analysis_text = []
                for line in lines:
                    if line.startswith('ISSUE:'):
                        issue_key = line.replace('ISSUE:', '').strip()
                    elif line.startswith('ANALYSIS:'):
                        analysis_text.append(line.replace('ANALYSIS:', '').strip())
                    elif issue_key and line.strip():
                        # Continuation of analysis
                        analysis_text.append(line.strip())
                
                if issue_key and analysis_text:
                    custom_analysis_map[issue_key] = ' '.join(analysis_text)
            
            # Apply custom analysis to issues
            for priority in issues_by_priority:
                for release in issues_by_priority[priority]:
                    for issue in issues_by_priority[priority][release]:
                        if issue['key'] in custom_analysis_map:
                            issue['analysis'] = custom_analysis_map[issue['key']]
        
        # Generate HTML sections using the helper function
        priority_sections = generate_priority_sections_html(issues_by_priority)
        
        # Generate dynamic report title based on components
        if override_components:
            # User specified specific components only
            if len(override_components) == 1:
                report_title = f"{override_components[0]} Stale Issues Analysis"
            else:
                report_title = f"{', '.join(override_components)} Stale Issues Analysis"
        elif additional_components:
            # User added additional components to defaults
            report_title = "Deployment and Lifecycle + Custom Components Stale Issues Analysis"
        else:
            # Default components
            report_title = "Deployment and Lifecycle Stale Issues Analysis"
        
        # Calculate release impact data
        release_counts = {}
        for priority in issues_by_priority:
            for release in issues_by_priority[priority]:
                if release not in release_counts:
                    release_counts[release] = 0
                release_counts[release] += len(issues_by_priority[priority][release])
        
        # Sort releases and create chart data
        sorted_releases = sorted(release_counts.keys(), key=lambda x: x if x != "Unknown" else "0.0")
        release_labels = sorted_releases
        release_data = [release_counts[r] for r in sorted_releases]
        
        # Calculate age distribution data (buckets: 0-30, 31-60, 61-90, 91-180, 180+)
        # Count unique issues only, not per-release duplicates
        age_buckets = [0, 0, 0, 0, 0]  # Initialize counts for each bucket
        age_counted_issues = set()
        current_time = datetime.now()
        
        for priority in issues_by_priority:
            for release in issues_by_priority[priority]:
                for issue_data in issues_by_priority[priority][release]:
                    issue_key = issue_data.get('key')
                    # Only count each unique issue once
                    if issue_key and issue_key not in age_counted_issues:
                        age_counted_issues.add(issue_key)
                        # Parse comment age to calculate days
                        comment_age_text = issue_data.get('comment_age', '')
                        days_old = 0
                        
                        if 'days ago' in comment_age_text:
                            # Extract number of days from format like "2025-10-03 (5 days ago)"
                            match = re.search(r'\((\d+) days ago\)', comment_age_text)
                            if match:
                                days_old = int(match.group(1))
                        elif 'No comments' in comment_age_text:
                            # For issues with no comments, use creation date or set to max
                            days_old = 365  # Assume very old for no-comment issues
                        
                        # Categorize into buckets
                        if days_old <= 30:
                            age_buckets[0] += 1
                        elif days_old <= 60:
                            age_buckets[1] += 1
                        elif days_old <= 90:
                            age_buckets[2] += 1
                        elif days_old <= 180:
                            age_buckets[3] += 1
                        else:
                            age_buckets[4] += 1
        
        age_distribution_data = age_buckets
        
        # Calculate status distribution data (count unique issues only, not per-release duplicates)
        status_counts = {}
        counted_issues = set()  # Track unique issues by key
        for priority in issues_by_priority:
            for release in issues_by_priority[priority]:
                for issue_data in issues_by_priority[priority][release]:
                    issue_key = issue_data.get('key')
                    # Only count each unique issue once
                    if issue_key and issue_key not in counted_issues:
                        counted_issues.add(issue_key)
                        status = issue_data.get('status', 'Unknown')
                        if status not in status_counts:
                            status_counts[status] = 0
                        status_counts[status] += 1
        
        # Sort statuses by count (descending) and create chart data
        sorted_statuses = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
        status_labels = [f"{status} ({count})" for status, count in sorted_statuses]
        status_data = [count for status, count in sorted_statuses]
        
        # Format key findings as HTML list if provided
        key_findings_html = ""
        if key_findings and key_findings.strip():
            findings_list = [f.strip() for f in key_findings.strip().split('\n') if f.strip()]
            if findings_list:
                key_findings_html = "<ul style='margin-top: 15px;'>\n"
                for finding in findings_list:
                    # Remove leading bullet points or dashes if present
                    finding = finding.lstrip('•-* ').strip()
                    key_findings_html += f"                    <li>{finding}</li>\n"
                key_findings_html += "                </ul>"

        # Format executive summary as HTML paragraphs if provided
        executive_summary_html = ""
        if executive_summary and executive_summary.strip():
            # Split by double newlines for paragraph breaks
            paragraphs = [p.strip() for p in executive_summary.strip().split('\n\n') if p.strip()]
            if paragraphs:
                for para in paragraphs:
                    # Each paragraph gets wrapped in <p> tags with styling
                    executive_summary_html += f'                <p style="font-size: 1.1em; margin-bottom: 1.5rem; line-height: 1.6; color: #2c3e50;">{para}</p>\n'

        # Prepare template variables
        template_vars = {
            'report_title': report_title,
            'total_stale': total_stale,
            'total_analyzed': total_analyzed,
            'stale_rate': stale_rate,
            'non_stale_count': non_stale_count,
            'days_threshold': days_threshold,
            'issue_type_text': 'bug-type issues only' if strict_bugs_only else 'all issue types',
            'version_scope_text': ', '.join(affects_versions) if affects_versions else 'all releases',
            'component_scope_text': 'custom component filtering' if override_components or additional_components else 'standard component scope',
            'analysis_type_text': 'Advanced comment analysis enabled' if include_comment_analysis else 'Basic analysis performed',
            'generation_time': datetime.now().strftime('%B %d, %Y at %H:%M:%S'),
            'generation_date': datetime.now().strftime('%B %d, %Y'),
            'include_no_comments_text': 'Yes' if include_no_comments else 'No',
            'affects_versions_text': ', '.join(affects_versions) if affects_versions else 'All versions',
            'projects_text': ', '.join(override_projects) if override_projects else 'OCPBUGS' + (' + ' + ', '.join(additional_projects) if additional_projects else ''),
            'issue_types_text': 'Bugs only' if strict_bugs_only else 'All types',
            'components_text': ', '.join(override_components) if override_components else 'Default components' + (' + ' + ', '.join(additional_components) if additional_components else ''),
            'comment_analysis_text': 'Enabled' if include_comment_analysis else 'Disabled',
            'stale_data': stale_data,
            'max_results': max_results,
            'priority_sections': priority_sections,
            'release_labels': json.dumps(release_labels),
            'release_data': json.dumps(release_data),
            'age_distribution_data': json.dumps(age_distribution_data),
            'status_labels': json.dumps(status_labels),
            'status_data': json.dumps(status_data),
            'key_findings_content': key_findings_html,
            'executive_summary_content': executive_summary_html
        }
        
        # Load and populate the HTML template
        template_path = "templates/stale_issues_report_template.html"
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Replace template variables using string replacement
            for key, value in template_vars.items():
                placeholder = '{' + key + '}'
                html_content = html_content.replace(placeholder, str(value))
            
        except FileNotFoundError:
            return f"❌ Error: Template file not found at {template_path}. Please ensure the template exists."
        except Exception as e:
            return f"❌ Error loading template: {str(e)}"
        
        # Write the HTML file
        report_path = f"report/{report_filename}"
        os.makedirs("report", exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return f"""✅ **HTML Report Generated Successfully!**

📄 **Report Details:**
   • File: {report_path}
   • Total Issues Analyzed: {total_analyzed}
   • Stale Issues Found: {total_stale}
   • Stale Rate: {stale_rate}%
   • Staleness Threshold: {days_threshold}+ days

📊 **Report Features:**
   • Executive Dashboard with key metrics
   • Interactive charts and visualizations
   • Complete detailed analysis data
   • Professional formatting for stakeholders
   • Mobile-responsive design

🔗 **Access:** Open {report_path} in your web browser to view the interactive report.

💡 **Usage:** This report can be shared with executives, stakeholders, or team members for comprehensive stale issues analysis."""
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error generating HTML report: {str(e)}")
        logger.error(f"Traceback: {error_details}")
        return f"❌ Error generating HTML report: {str(e)}\n\nDetails:\n{error_details}"


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
