# MCP JIRA Server

MCP server that connects Cursor or Claude Code to JIRA. Search issues, find stale bugs by team, fetch OpenShift release epics, and generate HTML reports.

## Installation

This project uses a virtual environment in the repo root (`bin/`, `lib/`). Install packages there, not into system Python.

```bash
cd /path/to/mcp-jira-server-custom

# Create the venv if bin/ does not exist yet
python3 -m venv .

# Optional: activate for the current shell
source bin/activate

# Install dependencies
./bin/python -m pip install -r requirements.txt
```

On macOS with Homebrew Python, running `python3 -m pip install` without a venv fails with `externally-managed-environment`. Always use `./bin/python -m pip` (or activate the venv first). Do not use `--break-system-packages`.

## Configuration

Set three environment variables before starting the server:

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | JIRA base URL, e.g. `https://redhat.atlassian.net` |
| `JIRA_USERNAME` | Your JIRA username (usually your email) |
| `JIRA_TOKEN` | API token from JIRA settings (Basic auth) |

```bash
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_USERNAME="your-email@example.com"
export JIRA_TOKEN="your-token-here"
```

The server does not read `.env` automatically. Set these via `export` in your shell or in the MCP config `env` block below.

## Running the server

The server communicates over stdio. In normal use, Cursor or Claude Code starts it for you. You rarely run it by hand.

### Cursor

Add or update [`.cursor/mcp.json`](.cursor/mcp.json):

```json
{
  "mcpServers": {
    "jira-server": {
      "command": "./bin/python",
      "args": ["mcp_jira_server.py"],
      "env": {
        "JIRA_URL": "https://redhat.atlassian.net",
        "JIRA_USERNAME": "your-email@example.com",
        "JIRA_TOKEN": "your-token-here"
      }
    }
  }
}
```

If `./bin/python` fails (wrong working directory), use absolute paths:

```json
"command": "/path/to/mcp-jira-server-custom/bin/python",
"args": ["/path/to/mcp-jira-server-custom/mcp_jira_server.py"]
```

Restart Cursor or reload MCP servers after changing the config.

### Claude Code CLI

```bash
cd /path/to/mcp-jira-server-custom

claude mcp add custom-jira \
  -e JIRA_URL="https://redhat.atlassian.net" \
  -e JIRA_USERNAME="your-email@example.com" \
  -e JIRA_TOKEN="your-token-here" \
  -- ./bin/python mcp_jira_server.py
```

Verify:

```bash
claude mcp list
claude mcp get custom-jira
```

A healthy server shows `Connected` in `claude mcp list`.

### Manual run (debug only)

```bash
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_USERNAME="your-email@example.com"
export JIRA_TOKEN="your-token-here"
./bin/python mcp_jira_server.py
```

The process waits on stdin. There is no HTTP port. Use this only to check that dependencies and credentials load correctly.

## Example prompts

Ask your assistant in plain language. It will call the matching MCP tool.

### Teams

```
What teams are configured?
List available JIRA teams
```

### Single issue

```
Get details for OCPBUGS-12345
Get OCPBUGS-12345 with comment analysis
```

### Comment analysis

```
Analyze comments on OCPBUGS-12345
What is the recent activity on OCPBUGS-12345 comments?
```

### Stale bugs

```
Find networking stale bugs in 4.18 with no comments in 7 days
Find deployment stale issues in 4.16 with no comments over 5 days
Find networking non-telco stale bugs in 4.18
```

Stale bug searches use team configs from `team_configs.py` (components, projects, telco priority). Pass `team_id` as `deployment`, `ptp`, or `networking`.

### OpenShift release work

Planned epics and stories in CNF by Fix Version (not stale bugs). Ask for all teams or name specific ones.

**All teams:**
```
Fetch openshift-X.0 epics for all teams grouped by team
List planned work for openshift-X.0 across every team
```

**Specific team(s) by name:**
```
Show openshift-5.0 epics for the Networking team
Fetch openshift-5.0 planned work for Deployment and ORAN
Get PTP team stories planned for openshift-4.18
```

These queries use CNF components per team (e.g. `CNF Network`, `Precision Timing`), filter by Fix Version (`openshift-5.0`), and return epics and stories only. No telco priority filter.

Available team names: Deployment, Compute, Networking, PTP, ORAN, Security (IDs: `deployment`, `compute`, `networking`, `ptp`, `oran`, `security`).

### HTML reports

```
Generate a stale issues report for deployment team in 4.18
Create an HTML report for networking stale bugs in 4.16 with no comments over 5 days
```

Reports are written to the `report/` directory (e.g. `report/stale_issues_report.html`).

### JQL search

```
Search JIRA: project = OCPBUGS AND status = Open
Find issues matching: component = "GitOps ZTP" AND status != Closed
```

### Comments

```
Preview a status-update comment on OCPBUGS-123
Add a comment to OCPBUGS-456 asking the assignee for an update
```

Comment tools support dry-run preview before posting.

## Teams

Stale bug searches use OCPBUGS components (`default_components`). OpenShift planned-work queries use separate CNF epic components (`epic_components`).

| Team | ID | Stale bugs (OCPBUGS) | OpenShift epics (CNF Fix Version) |
|------|----|----------------------|-----------------------------------|
| Deployment | `deployment` | GitOps ZTP, bare metal, installer, oc | Deployment and Lifecycle, Hub RDS, Edge, CNF vRAN / Far Edge |
| Compute | `compute` | (not configured) | CNF Compute |
| Networking | `networking` | Kernel, OVN, multus, nmstate, SR-IOV, etc. | CNF Network |
| PTP | `ptp` | PTP, cloud events, HW event operator | Precision Timing |
| ORAN | `oran` | (not configured) | CNF vRAN / Far Edge |
| Security | `security` | (not configured) | CNF Security |

## Tools reference

| Tool | Description | Key parameters |
|------|-------------|----------------|
| `jira_list_teams` | List configured teams | — |
| `jira_search_issues` | Search with JQL | `jql`, `max_results` |
| `jira_get_issue` | Issue details | `issue_key`, `include_comment_analysis` |
| `jira_analyze_issue_comments` | Comment thread analysis | `issue_key`, `days_threshold` |
| `jira_create_issue` | Create an issue | `project_key`, `summary`, `description` |
| `jira_update_issue` | Update or transition | `issue_key`, `fields`, `transition` |
| `jira_add_comment` | Add or preview a comment | `issue_key`, `comment`, `mention_assignee`, `mode` |
| `jira_find_stale_issues` | Stale bugs by team | `days_threshold`, `affects_versions`, `team_id`, `priority` |
| `jira_fetch_openshift_epics_by_team` | CNF epics/stories by Fix Version, grouped by team | `openshift_version`, `team_ids` (optional — all teams if omitted), `max_results` |
| `jira_generate_stale_issues_report` | HTML stale issues report | `days_threshold`, `affects_versions`, `team_id`, `report_filename` |

## Adding a team

Edit [`team_configs.py`](team_configs.py) and register the team:

```python
NEW_TEAM = TeamConfig(
    team_name="Storage Team",
    team_id="storage",
    default_projects=["OCPBUGS"],
    default_components=["Storage / OCS", "Storage / Ceph"],
    priority_values=["Telco:Priority-1", "Telco:Priority-2"],
    description="Storage infrastructure components",
)

TEAM_REGISTRY["storage"] = NEW_TEAM
```

See existing teams in that file for custom JQL examples (e.g. PTP backport stories).
