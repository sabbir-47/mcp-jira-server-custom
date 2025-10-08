# MCP JIRA Server

A comprehensive Model Context Protocol (MCP) server for JIRA integration, providing AI assistants with powerful JIRA automation capabilities including advanced comment analysis and professional HTML report generation.

## 🚀 Overview

This project provides a powerful **MCP JIRA Server** (`mcp_jira_server.py`) - a Model Context Protocol server for AI assistant integration with JIRA, featuring intelligent comment analysis, stale issue detection, and executive-ready HTML reports.

## 📋 Features

### 🏢 Multi-Team Support (NEW!)
- **Team Configurations** - Pre-configured settings for Deployment, PTP, and Networking teams
- **Custom JQL Queries** - Teams can define complex custom JQL (e.g., PTP's backport stories + bugs)
- **Team-Specific Defaults** - Each team has its own projects, components, and priority filters
- **Easy Extensibility** - Add new teams by updating `team_configs.py` only

### Core MCP Tools
- 🔍 **Search Issues** - JQL-based issue searching with flexible filters
- 📋 **Get Issue Details** - Comprehensive issue information with optional comment analysis
- 🧠 **Comment Analysis** - AI-powered comment analysis with keyword detection and sentiment insights
- ✨ **Create Issues** - New issue creation with full metadata support
- 📝 **Update Issues** - Modify existing issues and status transitions
- 💬 **Add Comments** - Smart commenting with assignee mentions and dry-run/live modes
- 🕒 **Find Stale Issues** - Advanced stale issue detection with **team-based filtering**
- 📊 **Generate Reports** - Professional HTML reports with interactive charts and executive summaries
- 🏢 **List Teams** - Discover available teams and their configurations


## 🛠️ Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export JIRA_URL="your-jira-domain"
export JIRA_TOKEN="your-bearer-token"  # Get from JIRA → Settings → Personal Access Tokens

# Run server
python mcp_jira_server.py
```

## 🏢 Multi-Team Configuration

The server supports multiple teams with their own configurations:

### Available Teams

| Team | ID | Configuration | JQL Type |
|------|----|--------------| ---------|
| **Deployment** | `deployment` | GitOps ZTP, Bare Metal, SR-IOV, oc components | Standard |
| **PTP** | `ptp` | PTP, Cloud Events, HW Event components | Custom JQL |
| **Networking** | `networking` | Placeholder (to be configured) | TBD |

### Using Team Configurations

**List Available Teams:**
```
"What teams are available?"
"Show me team configurations"
```

**Use Specific Team:**
```
"Find PTP stale bugs in 4.18"
"Generate deployment team report for 4.16"
```

**Add a New Team:**

Edit `team_configs.py`:
```python
NEW_TEAM = TeamConfig(
    team_name="Storage Team",
    team_id="storage",
    default_projects=["OCPBUGS"],
    default_components=["Storage / OCS", "Storage / Ceph"],
    priority_field_id="customfield_12323649",
    priority_values=["Telco:Priority-1", "Telco:Priority-2"],
    report_title_template="Storage {components} Analysis",
    description="Storage infrastructure components",
    custom_jql_base=None  # Optional: custom JQL like PTP team
)

# Add to registry
TEAM_REGISTRY["storage"] = NEW_TEAM
```

For detailed team configuration guide, see [`TEAM_CONFIGURATION.md`](TEAM_CONFIGURATION.md).

## 🎯 Usage Examples

### 📋 Single Issue Analysis

**Basic Issue Details:**
```
"Get details for OCPBUGS-12345"
```

**Issue with Comment Analysis:**
```
"Get details for OCPBUGS-12345 with comment analysis"
"Analyze the comments on OCPBUGS-12345 to understand the current status"
```

**Pure Comment Analysis:**
```
"Analyze comments on OCPBUGS-12345"
"What's the sentiment and activity on OCPBUGS-12345 comments?"
"Check OCPBUGS-12345 for escalation indicators in comments"
```

### 🕒 Stale Issues Detection

**Multi-Team Support:**
```
"List available teams"
"What teams can I monitor?"
"Find PTP stale bugs with no comments in last 7 days"
"Find deployment stale issues in 4.18 with no comments over 5 days"
"Show me networking team stale bugs"
```

**Basic Stale Issues (Deployment Team - Default):**
```
"Find stale bugs with no comments in the last 5 days"
"Show me issues that haven't been updated in 7 days"
```

**Project-Specific Analysis:**
```
"Find stale bugs in OCPBUGS project with no comments over 3 days"
"Search only in ACM project for stale issues over 10 days"
```

**Release-Specific Analysis:**
```
"Find stale issues in 4.14 and 4.16 releases with no comments over 5 days"
"Show me stale bugs in 4.18 release that need attention"
```

**Component-Specific Analysis:**
```
"Find stale issues only in GitOps ZTP component for 4.14 and 4.16 releases"
"Show me stale bugs in Networking SR-IOV component over 7 days"
```

### 📊 Professional Report Generation

**Basic Report Generation:**
```
"Generate a stale issues report for 4.14 and 4.16 releases with no comments over 5 days"
"Create an HTML report for stale bugs in GitOps ZTP component"
```

**Advanced Report Generation:**
```
"Generate executive report for stale issues in OCPBUGS project over 7 days with comment analysis"
"Create comprehensive report for 4.18 release bugs with no activity in 10 days"
```

**Custom Report Parameters:**
```
"Generate report for GitOps ZTP component in 4.14, 4.16, 4.18 releases, 
 bugs only, no comments over 5 days, save as 'gitops_analysis.html'"
```

### 💬 Smart Commenting

**Basic Comments:**
```
"Add comment to OCPBUGS-123 asking for status update"
"Comment on OCPBUGS-456 that this needs verification"
```

**Comments with Assignee Mentions:**
```
"Add comment to OCPBUGS-123 mentioning the assignee for update"
"Comment on OCPBUGS-456 asking assignee about timeline"
```

**Dry-Run Comments (Preview):**
```
"Show me how the comment would look for OCPBUGS-123 before posting"
"Preview comment for OCPBUGS-456 with assignee mention"
```

## 📊 HTML Report Generation

### Report Features
- **📊 Interactive Charts** - Issue status distribution, age analysis, release impact
- **📋 Detailed Tables** - Grouped by Telco priority and release version  
- **🔍 Issue Links** - Direct links to JIRA issues
- **🎨 Professional Styling** - Clean, modern design with color-coded status
- **💾 Export Ready** - Save as HTML for sharing with stakeholders
- **📈 Executive Summary** - Configurable high-level overview with AI-generated insights
- **🎯 Key Findings** - Customizable bullet points for quick takeaways

### Report Structure
- **Executive Summary** with configurable AI-generated content
- **Interactive Charts** (Status Distribution, Age Analysis, Release Impact)
- **Detailed Analysis** tables grouped by priority and release
- **Analysis Parameters** showing search criteria used

### Generated Report Location
Reports are saved to `report/` directory with timestamps and version info in filename.

**Example:** `report/stale_issues_4.16_4.18_report.html`

## ⭐ Key Features

- **🏢 Multi-Team Support** - Pre-configured teams with custom JQL queries
- **📊 Executive Reports** - Professional HTML reports with interactive charts
- **🕒 Advanced Stale Detection** - Team-based filtering with flexible project/component/release options
- **💬 Smart Comments** - Assignee mentions, dry-run preview, live posting
- **⚡ High Performance** - Optimized API calls with rate limiting
- **🛡️ Safety First** - Dry-run by default, secure bearer token authentication
- **🔧 Modular Design** - Easy extensibility via `team_configs.py`

## 🔧 Configuration

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | JIRA instance URL |
| `JIRA_TOKEN` | Bearer token from JIRA settings |

## 🚀 MCP Integration

### Claude-CLI
Add to the mcp server to claude:
```bash
claude mcp add "custom-jira" "./bin/python" "<PATH>/mcp_jira_server.py"
```

### Verification
Add to the mcp server to claude:
```bash
>> claude mcp get jira 
⏺ Bash(claude mcp get jira)
  ⎿  jira:                                                 
       Scope: Local config (private to you in this project)
       Status: ✓ Connected
     … +6 lines (ctrl+o to expand)

⏺ The jira MCP server is configured locally for this project, running ./bin/python 
  mcp_jira_server.py via stdio and is currently connected.
```

## 🛠️ Available MCP Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `jira_list_teams` | **NEW!** List configured teams | None |
| `jira_search_issues` | Search issues with JQL | `jql`, `max_results` |
| `jira_get_issue` | Get detailed issue info | `issue_key`, `include_comment_analysis` |
| `jira_analyze_issue_comments` | Pure comment analysis | `issue_key`, `days_threshold` |
| `jira_create_issue` | Create new issues | `project_key`, `summary`, `description` |
| `jira_update_issue` | Update existing issues | `issue_key`, `fields`, `transition` |
| `jira_add_comment` | Add comments with mentions | `issue_key`, `comment`, `mention_assignee`, `mode` |
| `jira_find_stale_issues` | Find stale issues | `days_threshold`, `affects_versions`, **`team_id`**, `override_components` |
| `jira_generate_stale_issues_report` | Generate HTML reports | `days_threshold`, `affects_versions`, **`team_id`**, `report_filename`, `executive_summary`, `key_findings` |


---
*Keep your JIRA projects moving with AI-powered automation and intelligent analysis* 🚀
