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
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

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
            
            # Display analysis results
            result += f"📊 **Analysis Summary:**\n"
            result += f"   • Total Comments: {analysis['total_comments']}\n"
            result += f"   • Unique Authors: {analysis['unique_authors']}\n"
            result += f"   • Activity Pattern: {analysis['activity_pattern']}\n"
            result += f"   • Last Activity: {analysis['last_activity']}\n"
            
            if analysis['keywords_found']:
                result += f"   • Keywords Found: {', '.join(analysis['keywords_found'][:5])}\n"
            
            if analysis['escalation_indicators']:
                result += f"   • 🚨 Escalation Indicators: {', '.join(analysis['escalation_indicators'])}\n"
            
            result += "\n**Recent Comments:**\n"
            for comment_data in analysis['recent_comments']:
                result += f"- **{comment_data['author']}** ({comment_data['date']}): {comment_data['preview']}\n"
                
        elif not include_comment_analysis:
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
        
        result += f"📊 **Analysis Overview:**\n"
        result += f"   • Total Comments: {analysis['total_comments']}\n"
        result += f"   • Unique Authors: {analysis['unique_authors']}\n"
        result += f"   • Activity Pattern: {analysis['activity_pattern']}\n"
        result += f"   • Last Activity: {analysis['last_activity']}\n"
        result += f"   • Analysis Threshold: {days_threshold} days\n\n"
        
        # Keywords Analysis
        if analysis['keywords_found']:
            result += f"🔑 **Keywords Detected:**\n"
            urgency_keywords = [k for k in analysis['keywords_found'] if k.startswith('URGENT:')]
            status_keywords = [k for k in analysis['keywords_found'] if k.startswith('STATUS:')]
            problem_keywords = [k for k in analysis['keywords_found'] if k.startswith('PROBLEM:')]
            
            if urgency_keywords:
                result += f"   🚨 Urgency: {', '.join([k.split(':')[1] for k in urgency_keywords])}\n"
            if status_keywords:
                result += f"   ✅ Status: {', '.join([k.split(':')[1] for k in status_keywords])}\n"
            if problem_keywords:
                result += f"   ⚠️ Problems: {', '.join([k.split(':')[1] for k in problem_keywords])}\n"
            result += "\n"
        
        # Escalation Indicators
        if analysis['escalation_indicators']:
            result += f"🚨 **Escalation Indicators:**\n"
            for indicator in analysis['escalation_indicators']:
                result += f"   • {indicator}\n"
            result += "\n"
        
        # Recent Comments Analysis
        if analysis['recent_comments']:
            result += f"💬 **Recent Comments Analysis:**\n"
            for i, comment_data in enumerate(analysis['recent_comments'], 1):
                result += f"   **{i}. {comment_data['author']}** ({comment_data['date']})\n"
                result += f"      Length: {comment_data['length']} chars\n"
                result += f"      Preview: {comment_data['preview']}\n\n"
        
        # AI Assistant Recommendations
        result += f"🤖 **AI Assistant Insights:**\n"
        
        if analysis['escalation_indicators']:
            result += f"   • ⚠️ This issue shows escalation patterns - may need management attention\n"
        
        if 'URGENT' in str(analysis['keywords_found']):
            result += f"   • 🚨 Urgency keywords detected - prioritize this issue\n"
        
        if analysis['unique_authors'] > 5:
            result += f"   • 👥 High collaboration ({analysis['unique_authors']} authors) - complex issue\n"
        
        if analysis['total_comments'] > 15:
            result += f"   • 💬 High activity ({analysis['total_comments']} comments) - active discussion\n"
        
        if analysis['activity_pattern'] == 'Single comment':
            result += f"   • 📝 Single comment - may need triage or follow-up\n"
        
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
    while i < len(lines):
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
                while j < len(lines) and not lines[j].strip().startswith("🐛 **"):
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
                    
                    j += 1
                
                # Organize by priority and release
                priority = current_issue['telco_priority']
                for version in current_issue['versions']:
                    # Extract major version (e.g., "4.16.0" -> "4.16")
                    major_version = re.match(r'(\d+\.\d+)', version)
                    if major_version:
                        release = major_version.group(1)
                        if release not in issues_by_priority[priority]:
                            issues_by_priority[priority][release] = []
                        issues_by_priority[priority][release].append(current_issue)
                
                # If no versions found, put in "Unknown" release
                if not current_issue['versions']:
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
                            <th style="width: 28%;">Summary</th>
                            <th style="width: 8%;">Status</th>
                            <th style="width: 10%;">Assignee</th>
                            <th style="width: 10%;">Comment Age</th>
                            <th style="width: 36%;">Analysis</th>
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
                    
                    priority_sections += f'''
                        <tr>
                            <td><a href="https://issues.redhat.com/browse/{issue['key']}" class="issue-link" target="_blank">{issue['key']}</a></td>
                            <td>{issue['summary']}</td>
                            <td><span class="status-badge status-{status_class}">{issue['status']}</span></td>
                            <td>{issue['assignee']}</td>
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
    """Analyze comments for rich insights that AI can process."""
    if not comments:
        return {
            'total_comments': 0,
            'unique_authors': 0,
            'recent_comments': [],
            'keywords_found': [],
            'escalation_indicators': [],
            'activity_pattern': 'No comments',
            'last_activity': 'Never'
        }
    
    # Keywords that indicate urgency, blockers, or important status
    urgency_keywords = ['urgent', 'critical', 'blocker', 'asap', 'immediately', 'escalate']
    status_keywords = ['fixed', 'resolved', 'workaround', 'patch', 'solution', 'closed']
    problem_keywords = ['broken', 'failing', 'error', 'issue', 'problem', 'bug', 'regression']
    
    analysis = {
        'total_comments': len(comments),
        'unique_authors': len(set(getattr(c.author, 'displayName', 'Unknown') for c in comments)),
        'recent_comments': [],
        'keywords_found': [],
        'escalation_indicators': [],
        'activity_pattern': '',
        'last_activity': '',
        'comment_frequency': []
    }
    
    # Analyze recent comments (last 5)
    recent_comments = comments[-5:] if len(comments) > 5 else comments
    for comment in recent_comments:
        comment_text = getattr(comment, 'body', '').lower()
        author = getattr(comment.author, 'displayName', 'Unknown') if hasattr(comment, 'author') else 'Unknown'
        created = getattr(comment, 'created', '')
        
        analysis['recent_comments'].append({
            'author': author,
            'date': created,
            'preview': comment_text[:150] + '...' if len(comment_text) > 150 else comment_text,
            'length': len(comment_text)
        })
        
        # Keyword analysis
        found_keywords = []
        for keyword in urgency_keywords:
            if keyword in comment_text:
                found_keywords.append(f"URGENT:{keyword}")
        for keyword in status_keywords:
            if keyword in comment_text:
                found_keywords.append(f"STATUS:{keyword}")
        for keyword in problem_keywords:
            if keyword in comment_text:
                found_keywords.append(f"PROBLEM:{keyword}")
        
        analysis['keywords_found'].extend(found_keywords)
    
    # Activity pattern analysis
    if len(comments) == 1:
        analysis['activity_pattern'] = 'Single comment'
    elif len(comments) < 5:
        analysis['activity_pattern'] = 'Low activity'
    elif len(comments) < 15:
        analysis['activity_pattern'] = 'Moderate activity'
    else:
        analysis['activity_pattern'] = 'High activity'
    
    # Last activity
    if comments:
        latest_comment = comments[-1]
        analysis['last_activity'] = getattr(latest_comment, 'created', 'Unknown')
        
        # Check for escalation indicators
        latest_text = getattr(latest_comment, 'body', '').lower()
        if any(word in latest_text for word in ['escalate', 'urgent', 'critical', 'manager', 'leadership']):
            analysis['escalation_indicators'].append('Recent escalation language detected')
    
    # Remove duplicates from keywords
    analysis['keywords_found'] = list(set(analysis['keywords_found']))
    
    return analysis


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
    include_comment_analysis: bool = True
) -> str:
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
        
        # COMPONENT HANDLING: Flexible component selection
        if override_components:
            # User wants to search ONLY specific components
            component_list = ", ".join([f'"{comp}"' for comp in override_components])
            jql_parts.append(f'component in ({component_list})')
        else:
            # Use default components + any additional ones
            default_components = [
                "GitOps ZTP",
                "Bare Metal Hardware Provisioning / baremetal-operator", 
                "Bare Metal Hardware Provisioning / ironic",
                "Bare Metal Hardware Provisioning",
                "Networking / SR-IOV",
                "Installer / Assisted Installer",
                "oc / cluster-compare"
            ]
            
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
        base_jql = " AND ".join(jql_parts)
        # Add ORDER BY to get consistent, predictable results
        # Order by updated ASC to prioritize oldest/most stale issues first
        base_jql += " ORDER BY updated ASC"

        # Increase cap to allow more results (100 max for better coverage)
        max_results = min(max_results, 100)

        logger.info(f"Executing JQL: {base_jql}")
        await rate_limit()
        # Single optimized call: get issues with comments and all needed fields
        issues = jira_client.search_issues(
            base_jql, 
            maxResults=max_results, 
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
        result_preview += f"📊 Found {len(issues)} issues (limited to {max_results} for performance)\n"
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
                result += f"   💬 Comments: {comments_count} ({analysis['unique_authors']} authors, {analysis['activity_pattern'].lower()})\n"
                
                # Last activity with context
                if latest_date == "No comments":
                    result += f"   🕒 Last Activity: No comments (Created: {issue.fields.created[:10]})\n"
                else:
                    if isinstance(latest_date, datetime):
                        days_old = (datetime.now() - latest_date).days
                        result += f"   🕒 Last Comment: {latest_date.strftime('%Y-%m-%d')} ({days_old} days ago)\n"
                    else:
                        result += f"   🕒 Last Comment: {latest_date}\n"
                
                # Compact keywords and indicators
                insights = []
                if analysis['keywords_found']:
                    insights.append(f"Keywords: {', '.join(analysis['keywords_found'][:3])}")
                if analysis['escalation_indicators']:
                    insights.append(f"🚨 ESCALATION DETECTED")
                
                if insights:
                    result += f"   🔍 AI Insights: {' | '.join(insights)}\n"
                
                # Most recent comment for context
                if analysis['recent_comments']:
                    latest_comment = analysis['recent_comments'][-1]
                    preview = latest_comment['preview'][:120] + "..." if len(latest_comment['preview']) > 120 else latest_comment['preview']
                    result += f"   💭 Latest: [{latest_comment['author']}] {preview}\n"
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
        result += f"```\n{base_jql}\n```\n"
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
        result += f"🔢 **STALE ISSUES COUNT: {len(stale_issues)}**\n"
        result += f"📋 Total issues analyzed: {len(issues)}\n"
        result += f"⏰ Staleness criteria: Comments older than {days_threshold} days\n"
        result += f"="*60 + "\n"
        
        return result
        
    except JIRAError as e:
        return f"JIRA Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


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
    include_comment_analysis: bool = True
) -> str:
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
    return await _find_stale_issues_core(
        days_threshold=days_threshold,
        include_no_comments=include_no_comments,
        affects_versions=affects_versions,
        max_results=max_results,
        additional_components=additional_components,
        override_components=override_components,
        additional_projects=additional_projects,
        override_projects=override_projects,
        strict_bugs_only=strict_bugs_only,
        include_comment_analysis=include_comment_analysis
    )


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
    report_filename: str = "stale_issues_report.html"
) -> str:
    """
    Generate a comprehensive HTML report for stale JIRA issues using the enhanced template.
    
    This tool combines jira_find_stale_issues data with a professional HTML template
    to create executive-ready reports that can be shared with stakeholders.
    
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
    
    Returns:
        Status message with report location and summary
    """
    try:
        # First, get the stale issues data using the core helper function
        stale_data = await _find_stale_issues_core(
            days_threshold=days_threshold,
            include_no_comments=include_no_comments,
            affects_versions=affects_versions,
            additional_projects=additional_projects,
            override_projects=override_projects,
            strict_bugs_only=strict_bugs_only,
            additional_components=additional_components,
            override_components=override_components,
            max_results=max_results,
            include_comment_analysis=include_comment_analysis
        )
        
        # Parse the stale data using the helper function
        parsed_data = parse_stale_issues_data(stale_data)
        
        # Extract parsed metrics
        total_stale = parsed_data['total_stale']
        total_analyzed = parsed_data['total_analyzed']
        stale_rate = parsed_data['stale_rate']
        non_stale_count = parsed_data['non_stale_count']
        issues_by_priority = parsed_data['issues_by_priority']
        
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
            'projects_text': ', '.join(override_projects) if override_projects else 'Default projects' + (' + ' + ', '.join(additional_projects) if additional_projects else ''),
            'issue_types_text': 'Bugs only' if strict_bugs_only else 'All types',
            'components_text': ', '.join(override_components) if override_components else 'Default components' + (' + ' + ', '.join(additional_components) if additional_components else ''),
            'comment_analysis_text': 'Enabled' if include_comment_analysis else 'Disabled',
            'stale_data': stale_data,
            'max_results': max_results,
            'priority_sections': priority_sections
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
        return f"❌ Error generating HTML report: {str(e)}"


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
