# MCP JIRA Server

A comprehensive Model Context Protocol (MCP) server for JIRA integration, providing AI assistants with powerful JIRA automation capabilities including advanced comment analysis and professional HTML report generation.

## 🚀 Overview

This project provides a powerful **MCP JIRA Server** (`mcp_jira_server.py`) - a Model Context Protocol server for AI assistant integration with JIRA, featuring intelligent comment analysis, stale issue detection, and executive-ready HTML reports.

## 📋 Features

### Core MCP Tools
- 🔍 **Search Issues** - JQL-based issue searching with flexible filters
- 📋 **Get Issue Details** - Comprehensive issue information with optional comment analysis
- 🧠 **Comment Analysis** - AI-powered comment analysis with keyword detection and sentiment insights
- ✨ **Create Issues** - New issue creation with full metadata support
- 📝 **Update Issues** - Modify existing issues and status transitions
- 💬 **Add Comments** - Smart commenting with assignee mentions and dry-run/live modes
- 🕒 **Find Stale Issues** - Advanced stale issue detection with component/project filtering
- 📊 **Generate Reports** - Professional HTML reports with interactive charts and executive summaries


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

**Basic Stale Issues:**
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

### Sample Report

**📊 Executive Dashboard View:**
```
┌─────────────────────────────────────────────────────────────┐
│  GitOps ZTP Stale Issues Analysis - Executive Dashboard     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📋 Executive Summary                                       │
│  Current State: 16 out of 20 issues (80%) in stale state  │
│  Critical Risk: 7 issues (44%) never triaged               │
│  Business Impact: 367-day abandoned issue needs closure    │
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │   16    │ │   80%   │ │   20    │ │   5+    │          │
│  │ Stale   │ │ Stale   │ │ Total   │ │ Days    │          │
│  │ Issues  │ │ Rate    │ │Analyzed │ │Threshold│          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                             │
│  📊 Interactive Charts: [Status] [Age] [Release Impact]    │
│                                                             │
│  🚨 Critical Actions Required:                             │
│  • Close OCPBUGS-42657 (367 days old)                     │
│  • Verify 3 MODIFIED issues (108+ days stale)             │
│  • Triage 7 issues with zero comments                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**📁 Report Location:** `report/stale_issues_report.html`  
**🌐 View:** Open in any web browser for full interactive experience  


## 🧠 AI-Powered Comment Analysis

The MCP server includes sophisticated comment analysis that provides actionable insights:

### Analysis Features
- **🔑 Keyword Detection** - Identifies urgency, status, and problem indicators
- **📊 Activity Patterns** - Categorizes comment frequency and engagement
- **🚨 Escalation Detection** - Flags issues requiring management attention
- **👥 Author Analysis** - Tracks unique contributors and collaboration patterns
- **⏰ Timeline Analysis** - Maps comment activity over time

### Sample Comment Analysis Output
```
🔍 Comment Analysis for OCPBUGS-12345
Issue: ZTP spoke cluster creation fails intermittently
Status: MODIFIED

📊 Analysis Overview:
   • Total Comments: 8
   • Unique Authors: 3
   • Activity Pattern: Moderate activity
   • Last Activity: 2024-10-01T14:30:00Z

🔑 Keywords Detected:
   🚨 Urgency: critical, blocker
   ✅ Status: workaround, patch
   ⚠️ Problems: failing, error

🚨 Escalation Indicators:
   • Recent escalation language detected

💬 Recent Comments Analysis:
   1. John Doe (2024-10-01): This is still failing after the patch...
   2. Jane Smith (2024-09-28): Applied workaround but need permanent fix...

🤖 AI Assistant Insights:
   • 🚨 Urgency keywords detected - prioritize this issue
   • ⚠️ This issue shows escalation patterns - may need management attention
   • 👥 High collaboration (3 authors) - complex issue
```

This analysis helps AI assistants and users quickly understand issue context, urgency levels, and required actions.

## ⭐ Key Features

- **🧠 AI-Powered Analysis** - Intelligent comment analysis with keyword detection
- **📊 Executive Reports** - Professional HTML reports with interactive charts
- **🕒 Advanced Stale Detection** - Flexible project/component/release filtering
- **💬 Smart Comments** - Assignee mentions, dry-run preview, live posting
- **⚡ High Performance** - Optimized API calls (96% fewer requests)
- **🛡️ Safety First** - Dry-run by default, secure bearer token authentication
- **🔧 Modular Design** - Reusable comment analysis across all tools

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
| `jira_search_issues` | Search issues with JQL | `jql`, `max_results` |
| `jira_get_issue` | Get detailed issue info | `issue_key`, `include_comment_analysis` |
| `jira_analyze_issue_comments` | Pure comment analysis | `issue_key`, `days_threshold` |
| `jira_create_issue` | Create new issues | `project_key`, `summary`, `description` |
| `jira_update_issue` | Update existing issues | `issue_key`, `fields`, `transition` |
| `jira_add_comment` | Add comments with mentions | `issue_key`, `comment`, `mention_assignee`, `mode` |
| `jira_find_stale_issues` | Find stale issues | `days_threshold`, `affects_versions`, `override_components` |
| `jira_generate_stale_issues_report` | Generate HTML reports | `days_threshold`, `affects_versions`, `report_filename` |


---
*Keep your JIRA projects moving with AI-powered automation and intelligent analysis* 🚀
