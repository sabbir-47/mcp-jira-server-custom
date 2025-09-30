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
- 💬 **Add Comments** - Comment with assignee mentions, dry-run/live modes
- 🕒 **Find Stale Issues** - Identify old issues with flexible project/bug filtering


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

## 🎯 Usage

Ask Claude/Cursor in natural language:
```
"Find stale bugs in RHEL project with no comments in 5 days"
"Search only in OCPBUGS project for stale issues"
"Add comment to OCPBUGS-123 asking assignee for update"
"Find bugs (not stories) that are stale in ACM project"
```

## ⭐ Key Features

- **Stale bug detection** - Flexible project/bug filtering
- **Smart comments** - Assignee mentions, dry-run preview
- **Performance** - Single API call (96% fewer requests)
- **Safety** - Dry-run by default, bearer token auth

## 🔧 Configuration

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | JIRA instance URL |
| `JIRA_TOKEN` | Bearer token from JIRA settings |

## 🚀 MCP Integration

### Cursor
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "jira": {
      "command": "./bin/python",
      "args": ["mcp_jira_server.py"],
      "env": {
        "JIRA_URL": "your-jira-domain", 
        "JIRA_TOKEN": "your-token"
      }
    }
  }
}
```

## 🔍 Troubleshooting

- **Import errors**: `pip install -r requirements.txt`
- **Auth errors**: Check `JIRA_URL` and `JIRA_TOKEN` are set
- **No results**: Verify project names and issue assignees

---
*Keep your JIRA projects moving with AI-powered automation* 🚀
