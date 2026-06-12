#!/usr/bin/env python3
"""
Team-specific configurations for JIRA stale issues analysis.

Each team has its own configuration for:
- Projects to monitor
- Components to track
- Custom fields (like priority fields)
- Report titles and branding
"""

import re
from typing import List, Dict, Any, Optional

# =============================================================================
# GLOBAL CONSTANTS
# =============================================================================

# Common report title template used across all teams
DEFAULT_REPORT_TITLE_TEMPLATE = "{team} Stale Issues Analysis"

# Common Telco priority field ID used by most teams
TELCO_PRIORITY_FIELD_ID = "customfield_12323649"

# Common Telco priority values
TELCO_PRIORITY_VALUES = [
    "Telco:Priority-1",
    "Telco:Priority-2",
    "Telco:Priority-3"
]

# JQL-formatted strings for reuse in custom queries
BUG_TYPES_JQL = "Type in (Bug, Weakness, Vulnerability)"
TELCO_PRIORITY_JQL = 'cf[12323649] in (Telco:Priority-1, Telco:Priority-2, Telco:Priority-3)'
EXCLUDED_STATUSES_JQL = 'status not in (Closed, Verified, "Release Pending", Done)'

DEFAULT_EPIC_PROJECTS = ["CNF"]
RELEASE_WORK_ISSUE_TYPES_JQL = "issuetype in (Epic, Story)"


def normalize_openshift_version(version: str) -> str:
    """Normalize version input to openshift-X.x format (e.g. 5.0 -> openshift-5.0)."""
    version = version.strip()
    if version.lower().startswith("openshift-"):
        return version
    if re.match(r"^\d+\.\d+", version):
        return f"openshift-{version}"
    return version


class TeamConfig:
    """Configuration for a specific team's JIRA monitoring."""
    
    def __init__(
        self,
        team_name: str,
        team_id: str,
        default_projects: List[str],
        default_components: List[str],
        priority_field_id: str = TELCO_PRIORITY_FIELD_ID,
        priority_values: List[str] = None,
        report_title_template: str = DEFAULT_REPORT_TITLE_TEMPLATE,
        description: str = "",
        custom_jql_base: Optional[str] = None,
        epic_projects: Optional[List[str]] = None,
        epic_components: Optional[List[str]] = None,
        epic_labels: Optional[List[str]] = None,
        epic_summary_pattern: Optional[str] = None,
    ):
        """
        Initialize team configuration.
        
        Args:
            team_name: Display name of the team (e.g., "Deployment Team")
            team_id: Unique identifier for the team (e.g., "deployment")
            default_projects: List of default JIRA projects (e.g., ["OCPBUGS", "MGMT"])
            default_components: List of default components to monitor
            priority_field_id: Custom field ID for priority (e.g., "customfield_12323649")
            priority_values: List of priority values to filter (e.g., ["Telco:Priority-1"])
            report_title_template: Template for report title (e.g., "{components} Stale Issues Analysis")
            description: Team description
            custom_jql_base: Optional custom JQL base query. If provided, this overrides the default 
                           project/component/priority filtering. Use placeholders: {affects_versions}
            epic_projects: Projects for OpenShift release epic queries (default: CNF)
            epic_components: CNF components for OpenShift release epic/story queries (Fix Version)
            epic_labels: Optional labels to scope epic queries per team
            epic_summary_pattern: Optional summary ~ pattern for epic queries per team
        """
        self.team_name = team_name
        self.team_id = team_id
        self.default_projects = default_projects
        self.default_components = default_components
        self.priority_field_id = priority_field_id
        self.priority_values = priority_values if priority_values is not None else []
        self.report_title_template = report_title_template
        self.description = description
        self.custom_jql_base = custom_jql_base
        self.use_custom_jql = custom_jql_base is not None
        self.epic_projects = epic_projects if epic_projects is not None else list(DEFAULT_EPIC_PROJECTS)
        self.epic_components = epic_components if epic_components is not None else []
        self.epic_labels = epic_labels if epic_labels is not None else []
        self.epic_summary_pattern = epic_summary_pattern
    
    def get_full_jql(self, components: Optional[List[str]] = None,
                     projects: Optional[List[str]] = None,
                     priority: bool = True) -> str:
        """
        Generate complete JQL query for this team.

        Args:
            components: Optional list to override default components
            projects: Optional list to override default projects
            priority: Include telco priority filtering (default: True)
                     - True: include telco priority filter
                     - False: no telco priority filter (non-telco bugs)

        Returns:
            Complete JQL query string with placeholders replaced, or None for default query building
        """
        if self.use_custom_jql and self.custom_jql_base:
            # Use custom JQL with placeholders
            jql = self.custom_jql_base
            
            # Replace component placeholder
            if components:
                comp_list = ', '.join([f'"{c}"' for c in components])
            else:
                comp_list = ', '.join([f'"{c}"' for c in self.default_components])
            jql = jql.replace('{components}', comp_list)
            
            # Replace project placeholder
            if projects:
                proj_list = ', '.join(projects)
            else:
                proj_list = ', '.join(self.default_projects)
            jql = jql.replace('{projects}', proj_list)
            
            # Replace priority_clause placeholder
            if '{priority_clause}' in jql:
                if not priority:
                    # User wants non-telco bugs - remove priority clause entirely
                    jql = jql.replace('AND {priority_clause}', '')
                    jql = jql.replace('{priority_clause} AND', '')
                    jql = jql.replace('{priority_clause}', '')
                else:
                    # User wants telco priority filtering
                    priority_clause = self.get_jql_priority_clause()
                    if not priority_clause:
                        # Team has no priority values configured - remove the clause
                        jql = jql.replace('AND {priority_clause}', '')
                        jql = jql.replace('{priority_clause} AND', '')
                        jql = jql.replace('{priority_clause}', '')
                    else:
                        jql = jql.replace('{priority_clause}', priority_clause)
            
            return jql
        
        # Return None for teams without custom JQL (fallback to default query building)
        return None
    
    def get_jql_priority_clause(self) -> str:
        """
        Generate JQL clause for priority filtering.
        
        Returns:
            JQL clause string for priority filtering, or empty string if no priority filtering needed
        """
        if not self.priority_values:
            return f'{self.priority_field_id} is EMPTY)'
        
        priority_list = ', '.join([f'"{p}"' for p in self.priority_values])
        return f'{self.priority_field_id} in ({priority_list})'
    
    def get_report_title(self, components: Optional[List[str]] = None) -> str:
        """
        Generate report title based on team name.
        
        Args:
            components: Optional list of components (not used, for compatibility)
        
        Returns:
            Report title string
        """
        return self.report_title_template.format(team=self.team_name)

    def get_epic_jql(
        self,
        openshift_version: str,
        components: Optional[List[str]] = None,
    ) -> str:
        """
        Build JQL for OpenShift release epics/stories scoped to this team.

        Epics and stories only, CNF project, fixVersion = openshift-X.x, no telco priority.
        Release targeting uses Fix Version (not Affects Version).
        """
        version = normalize_openshift_version(openshift_version)
        comps = components if components is not None else self.epic_components
        if not comps:
            raise ValueError(
                f"No epic_components configured for team {self.team_id!r}. "
                "OpenShift release queries require CNF epic components."
            )
        comp_list = ", ".join([f'"{c}"' for c in comps])

        jql_parts = [
            "project = CNF",
            RELEASE_WORK_ISSUE_TYPES_JQL,
            f'fixVersion = "{version}"',
            f"component in ({comp_list})",
            EXCLUDED_STATUSES_JQL,
        ]

        if self.epic_labels:
            label_list = ", ".join([f'"{label}"' for label in self.epic_labels])
            jql_parts.append(f"labels in ({label_list})")

        if self.epic_summary_pattern:
            jql_parts.append(f'summary ~ "{self.epic_summary_pattern}"')

        return " AND ".join(jql_parts) + " ORDER BY key DESC"


# =============================================================================
# TEAM CONFIGURATIONS
# =============================================================================

# Deployment Team (GitOps ZTP, Bare Metal, etc.)
DEPLOYMENT_TEAM = TeamConfig(
    team_name="Deployment Team",
    team_id="deployment",
    default_projects=["OCPBUGS"],
    default_components=[
        "GitOps ZTP",
        "Bare Metal Hardware Provisioning / baremetal-operator",
        "Bare Metal Hardware Provisioning / ironic",
        "Bare Metal Hardware Provisioning",
        "Bare Metal Hardware Provisioning / cluster-baremetal-operator",
        "Baremetal Operator", 
        "Networking / SR-IOV",
        "Installer / Assisted Installer",
        "oc / cluster-compare"
    ],
    priority_values=TELCO_PRIORITY_VALUES,
    report_title_template=DEFAULT_REPORT_TITLE_TEMPLATE,
    description="Deployment and lifecycle management components",
    custom_jql_base=f"""{BUG_TYPES_JQL} AND {TELCO_PRIORITY_JQL} AND Component in ({{components}}) AND {EXCLUDED_STATUSES_JQL}""",
    epic_components=[
        "Deployment and Lifecycle",
        "Hub RDS",
        "Edge",
    ],
)

# PTP Team (Precision Time Protocol)
# Uses custom JQL base query that includes both backport stories and bugs
PTP_TEAM = TeamConfig(
    team_name="PTP Team",
    team_id="ptp",
    default_projects=["CNF"],
    default_components=[
        "Cloud Native Events / Cloud Event Proxy",
        "Cloud Native Events / Hardware Event Proxy",
        "Networking / ptp",
        "Telco Edge / HW Event Operator"
    ], # CNF project doesn't use Telco Priority custom field
    priority_values=[],  # No priority filtering for PTP team
    report_title_template=DEFAULT_REPORT_TITLE_TEMPLATE,
    description="Precision Time Protocol components",
    custom_jql_base=f"""((project in ({{projects}}) AND summary ~ "Telco PTP Release" AND issuetype = Story AND labels = telco-backport AND status != Closed) OR ({BUG_TYPES_JQL} AND Component in ({{components}}) AND {EXCLUDED_STATUSES_JQL}))""",
    epic_components=["Precision Timing"],
)

# Networking Team (Kernel Networking, OVN, SR-IOV, multus, nmstate, etc.)
NETWORKING_TEAM = TeamConfig(
    team_name="Networking Team",
    team_id="networking",
    default_projects=["OCPBUGS"],
    default_components=[
        "kernel / Networking",
        "Networking / On-Prem Host Networking",
        "Networking / multus",
        "Networking / ovn-kubernetes",
        "Networking / SR-IOV",
        "nmstate",
        "dpdk",
        "Networking / runtime-cfg",
        "Networking / Metal LB",
        "Networking / kubernetes-nmstate-operator",
        "Networking / kubernetes-nmstate",
        "Networking / FRR-K8s",
        "Networking / cloud-network-config-controller",
        "NetworkManager",
        "Networking",
        "Networking / DNS",
        "CNV Network"
    ],
    priority_field_id=TELCO_PRIORITY_FIELD_ID,
    priority_values=TELCO_PRIORITY_VALUES,
    report_title_template=DEFAULT_REPORT_TITLE_TEMPLATE,
    description="Networking team components",
    custom_jql_base=f"""{BUG_TYPES_JQL} AND {{priority_clause}} AND Component in ({{components}}) AND {EXCLUDED_STATUSES_JQL}""",
    epic_components=["CNF Network"],
)

# Compute Team — OpenShift release planning (CNF epics/stories only)
COMPUTE_TEAM = TeamConfig(
    team_name="Compute Team",
    team_id="compute",
    default_projects=[],
    default_components=[],
    priority_values=[],
    description="CNF Compute — OpenShift release planning",
    epic_components=["CNF Compute"],
)

# ORAN Team — OpenShift release planning (CNF epics/stories only)
ORAN_TEAM = TeamConfig(
    team_name="ORAN Team",
    team_id="oran",
    default_projects=[],
    default_components=[],
    priority_values=[],
    description="CNF vRAN / Far Edge — OpenShift release planning",
    epic_components=["CNF vRAN / Far Edge"],
)

# Security Team — OpenShift release planning (CNF epics/stories only)
SECURITY_TEAM = TeamConfig(
    team_name="Security Team",
    team_id="security",
    default_projects=[],
    default_components=[],
    priority_values=[],
    description="CNF Security — OpenShift release planning",
    epic_components=["CNF Security"],
)


# =============================================================================
# TEAM REGISTRY
# =============================================================================

# Central registry of all teams
TEAM_REGISTRY: Dict[str, TeamConfig] = {
    "deployment": DEPLOYMENT_TEAM,
    "compute": COMPUTE_TEAM,
    "networking": NETWORKING_TEAM,
    "ptp": PTP_TEAM,
    "oran": ORAN_TEAM,
    "security": SECURITY_TEAM,
}


def get_epic_team_ids() -> List[str]:
    """Return team IDs that have epic_components configured for OpenShift release queries."""
    return [tid for tid, cfg in TEAM_REGISTRY.items() if cfg.epic_components]


def resolve_team_ids(names_or_ids: List[str]) -> List[str]:
    """
    Resolve team display names or IDs to team_id values.

    Accepts team_id (e.g. networking), team_name (e.g. Networking Team),
    or short names (e.g. Networking, ORAN, PTP).
    """
    resolved: List[str] = []

    for raw in names_or_ids:
        key = raw.strip()
        if not key:
            continue
        key_lower = key.lower()

        if key_lower in TEAM_REGISTRY:
            if key_lower not in resolved:
                resolved.append(key_lower)
            continue

        matched = None
        for tid, config in TEAM_REGISTRY.items():
            name_lower = config.team_name.lower()
            short_name = name_lower.replace(" team", "")
            if key_lower in (tid, name_lower, short_name):
                matched = tid
                break

        if matched:
            if matched not in resolved:
                resolved.append(matched)
        else:
            available = ", ".join(
                f"{cfg.team_name} ({cfg.team_id})" for cfg in TEAM_REGISTRY.values()
            )
            raise ValueError(f"Unknown team: {raw!r}. Available teams: {available}")

    if not resolved:
        raise ValueError("No team names or IDs provided.")

    return resolved


def get_default_team() -> TeamConfig:
    """Return the default team configuration (Deployment)."""
    return DEPLOYMENT_TEAM


def get_team_config(team_id: str) -> TeamConfig:
    """
    Get configuration for a specific team.
    
    Args:
        team_id: Team identifier (e.g., "deployment", "ptp", "networking")
    
    Returns:
        TeamConfig object
    
    Raises:
        ValueError: If team_id is not found
    """
    if team_id not in TEAM_REGISTRY:
        available_teams = ', '.join(TEAM_REGISTRY.keys())
        raise ValueError(
            f"Unknown team ID: {team_id}. "
            f"Available teams: {available_teams}"
        )
    
    return TEAM_REGISTRY[team_id]


def list_available_teams() -> List[Dict[str, str]]:
    """
    List all available teams with their descriptions.
    
    Returns:
        List of dictionaries with team info
    """
    return [
        {
            'team_id': config.team_id,
            'team_name': config.team_name,
            'description': config.description,
            'default_projects': ', '.join(config.default_projects) or '(none — epic planning only)',
            'default_components': ', '.join(config.default_components) or '(none — epic planning only)',
            'epic_components': ', '.join(config.epic_components) or '(not configured)',
        }
        for config in TEAM_REGISTRY.values()
    ]

