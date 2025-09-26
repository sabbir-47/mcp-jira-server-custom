# MCP JIRA Server

A comprehensive Model Context Protocol (MCP) server for JIRA integration, providing AI assistants with powerful JIRA automation capabilities.

## 🚀 Overview

This project provides a powerful **MCP JIRA Server** (`mcp_jira_server.py`) - a Model Context Protocol server for AI assistant integration with JIRA.

## 📋 Features

### MCP Server Tools
- 🔍 **Search Issues** - JQL-based issue searching
- 📋 **Get Issue Details** - Comprehensive issue information
- ✨ **Create Issues** - New issue creation with full metadata
- 📝 **Update Issues** - Modify existing issues and transitions
- 💬 **Add Comments** - Comment on issues with mentions
- 🕒 **Find Stale Issues** - Identify issues with old comments (supports Affects Version filtering)
- 🤖 **Smart Comment on Issues** - Flexible commenting with dry-run/live modes and selective targeting


## 🛠️ Installation

### Prerequisites
- Python 3.8+
- JIRA instance with API access
- JIRA API token

### 1. Clone/Download the Project
```bash
cd /path/to/your/projects
# Files should be in: jira_mcp/
```

### 2. Install Dependencies
```bash
cd jira_mcp
pip install -r requirements.txt
[mac] pipx install -r requirements.txt
```

Or install manually:
```bash
pip install mcp jira python-dotenv
[mac] pipx install mcp jira python-dotenv
```

### 3. Setup Environment Variables
```bash
# Make setup script executable
chmod +x setup_env.sh

# Run setup (creates .env file)
./setup_env.sh
```

Or manually set:
```bash
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_TOKEN="your-bearer-token"
```

### 4. Get Your JIRA Bearer Token
1. Go to your JIRA instance → Settings → Personal Access Tokens
2. Create a new Bearer token with appropriate permissions
3. Copy the token and use it as `JIRA_TOKEN`

## 🎯 Usage

### MCP Server (AI Assistant Integration)

#### Starting the Server
```bash
python mcp_jira_server.py
```

#### Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `jira_search_issues` | Search with JQL | `jql`, `max_results` |
| `jira_get_issue` | Get issue details | `issue_key` |
| `jira_create_issue` | Create new issue | `project_key`, `issue_type`, `summary`, `description` |
| `jira_update_issue` | Update existing issue | `issue_key`, `summary`, `description`, `status`, `assignee` |
| `jira_add_comment` | Add comment | `issue_key`, `comment` |
| `jira_find_stale_issues` | Find stale issues | `project_key`, `days_threshold`, `affects_versions` |
| `jira_comment_on_stale_issues` | Smart comment on issues | `mode`, `target_scope`, `specific_issues`, `project_key` |

#### Example AI Interactions
```
User: "Find all open bugs in project TEST"
AI: Uses jira_search_issues with JQL: "project = TEST AND issuetype = Bug AND status = Open"

User: "Comment on stale issues in project DEV older than 2 weeks"
AI: Uses jira_comment_on_stale_issues with project_key="DEV", days_threshold=14, mode="dry_run"

User: "Actually post those comments now"
AI: Uses jira_comment_on_stale_issues with mode="live"
```

### AI Assistant Integration Examples

When using the MCP server with an AI assistant, you can make natural language requests:

```
"Find all open bugs in project TEST"
"Create a new bug report for login issues in project ABC"
"Comment on stale issues in project DEV older than 2 weeks"
"Find stale issues in version 2.0 of project XYZ"
"Comment on specific issues: TEST-123, TEST-456"
"Preview what comments would be posted without actually posting them"
```

The AI will automatically translate these requests into the appropriate MCP tool calls.

## 📊 Stale Issue Detection

### What Makes an Issue "Stale"?
- Has an assignee
- Latest comment is older than threshold (default: 14 days)
- OR has no comments at all
- NOT in excluded statuses (Closed, Done, Resolved, On QA, Release Pending, On_QA, Verified)

### Auto-Comment Features
- 🎯 **Smart Mentions**: Uses `[~username]` for proper JIRA notifications
- 🔒 **Safety First**: Dry-run mode by default
- 🚫 **Status Filtering**: Automatically excludes completed work
- 📝 **Custom Templates**: Customizable comment messages
- ✅ **Error Handling**: Continues on individual failures

## 🔧 Configuration

### Environment Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `JIRA_URL` | JIRA instance URL | `'https://issues.redhat.com'` |
| `JIRA_TOKEN` | JIRA Bearer token | `ATT3xFfGf0...` |

### MCP Tool Parameters

#### Find Stale Issues Tool
- `project_key`: JIRA project key (required)
- `days_threshold`: Days threshold (default: 14)
- `include_no_comments`: Include issues with no comments (default: true)
- `status_filter`: Filter by specific status
- `affects_versions`: Array of version names to filter by (e.g., ["4.16.z", "4.18"])

#### Smart Comment Tool
- `mode`: Operation mode - "dry_run" (default) or "live"
- `target_scope`: "all_stale" (default) or "specific_issues"
- `specific_issues`: Array of issue keys when using specific targeting
- `project_key`: Required for "all_stale" mode
- `days_threshold`: Days threshold for staleness (default: 14)
- `comment_template`: Custom template with {assignee} placeholder
- `exclude_statuses`: Array of status names to exclude
- `affects_versions`: Filter by specific versions

## 📋 AI Assistant Examples

### Example 1: Weekly Stale Issue Check
**User Request:**
> "Check project OCPBUGS for issues that haven't been updated in 7 days and add polite follow-up comments to their assignees"

**AI Response:**
The AI will use `jira_comment_on_stale_issues` with:
- `project_key="OCPBUGS"`
- `days_threshold=7`
- `comment_template="{assignee} Do you have any update on this issue?"`
- `mode="dry_run"` (for safety first)

Then if user approves: `mode="live"` to actually post comments

### Example 2: Finding Stale Issues
**User Request:**
> "Show me all assigned issues in project OCPBUGS that haven't had comments in 2 weeks in 4.18.z version"

**AI Response:**
The AI will use `jira_find_stale_issues` with:
- `project_key="ABC"`
- `days_threshold=14`
- `include_no_comments=true`
- `affects_versions=["4.18.z"]`

### Example 3: Version-Specific Stale Issues
**User Request:**
> "Find stale issues in project XYZ that affect version 4.18.z and comment on them urgently"

**AI Response:**
The AI will:
1. Use `jira_find_stale_issues` with `affects_versions=["4.18.z"]`
2. Use `jira_comment_on_stale_issues` with version filter and urgent template
3. Start in dry_run mode for user approval

### Example 4: Targeted Issue Comments
**User Request:**
> "Add follow-up comments to these specific issues: OCPBUGS-123, OCPBUGS-456, OCPBUGS-789"

**AI Response:**
The AI will use `jira_comment_on_stale_issues` with:
- `target_scope="specific_issues"`
- `specific_issues=[OCPBUGS-123, OCPBUGS-456, OCPBUGS-789"]`
- `mode="dry_run"` first for review

## 🚨 Safety Features

### Dry Run Mode
- **Default behavior**: All commenting operations are dry-run by default
- **Preview mode**: Shows exactly what comments would be posted
- **AI safety**: AI assistants will preview changes before applying

### Status Exclusions
Automatically excludes these statuses from commenting:
- Closed
- Release Pending
- On_QA  
- Verified

*Note: The exclude list is now more focused and can be customized via the `exclude_statuses` parameter.*

### Error Handling
- Continues processing if individual issues fail
- Detailed error reporting
- Graceful handling of missing permissions

## 🔍 Troubleshooting

### Common Issues

#### Import Errors
```bash
# Install missing dependencies
pip install mcp jira python-dotenv
```

#### Authentication Errors
```bash
# Check environment variables
echo $JIRA_URL
echo $JIRA_TOKEN

# Recreate .env file
./setup_env.sh
```

#### Permission Issues
- Ensure your JIRA token has appropriate permissions
- Check project access rights
- Verify you can comment on issues manually

#### No Issues Found
- Check project key spelling
- Verify JQL syntax in logs
- Ensure issues have assignees
- Check date thresholds

### Debug Mode
For detailed logging:
```bash
# Enable debug logging
export PYTHONPATH=$PYTHONPATH:.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
python mcp_jira_server.py
```

## 📁 Project Structure

```
jira_mcp/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── setup_env.sh                # Environment setup script
├── mcp_jira_server.py          # MCP protocol server
└── .env                        # Environment variables (created by setup)
```

## 🤝 Integration Examples

### Scheduled AI Assistant Tasks
You can set up regular AI assistant tasks to check for stale issues:

```
# Weekly automation prompt
"Every Monday at 9 AM, check project OCPBUGS for stale issues older than 7 days and preview comments"

# Version-specific checks
"Check for stale issues in version 4.20 every Friday and comment urgently"

# Targeted follow-ups
"Comment on these specific issues weekly: OCPBUGS-123, OCPBUGS-456"
```

### CI/CD Integration
You can integrate the MCP server with CI/CD workflows by having AI assistants automatically check for stale issues during deployments or on schedules.

### AI Assistant Configuration
```json
{
  "mcp_servers": {
    "jira": {
      "command": "python",
      "args": ["/path/to/jira_mcp/mcp_jira_server.py"],
      "env": {
        "JIRA_URL": "https://issues.redhat.com",
        "JIRA_TOKEN": "your-bearer-token"
      }
    }
  }
}
```

## 📈 Best Practices

### Comment Templates
You can customize comment templates when using the MCP server:

```
# Professional tone
"{assignee} Could you please provide a status update on this issue?"

# Urgent tone  
"{assignee} This issue is approaching its deadline. Please update ASAP."

# Weekly check-in
"{assignee} Weekly check-in: Any blockers or updates?"

# Version-specific
"{assignee} This v2.0 issue needs attention before release!"

# Specific follow-up
"{assignee} Following up on our discussion - any progress on this?"
```

### AI Automation Strategy
1. **Daily**: Ask AI to check issues > 3 days old
2. **Weekly**: Ask AI to check issues > 7 days old and post comments
---

🎉 **Happy JIRA Automating!** This tool helps keep your projects moving by ensuring no assigned work falls through the cracks.
