#!/usr/bin/env python3
"""
Team-specific configurations for JIRA stale issues analysis.

Each team has its own configuration for:
- Projects to monitor
- Components to track
- Custom fields (like priority fields)
- Report titles and branding
"""

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


class TeamConfig:
    """Configuration for a specific team's JIRA monitoring."""
    
    def __init__(
        self,
        team_name: str,
        team_id: str,
        default_projects: List[str],
        default_components: List[str],
        priority_field_id: str,
        priority_values: List[str],
        report_title_template: str,
        description: str = "",
        custom_jql_base: Optional[str] = None
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
        """
        self.team_name = team_name
        self.team_id = team_id
        self.default_projects = default_projects
        self.default_components = default_components
        self.priority_field_id = priority_field_id
        self.priority_values = priority_values
        self.report_title_template = report_title_template
        self.description = description
        self.custom_jql_base = custom_jql_base
        self.use_custom_jql = custom_jql_base is not None
    
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
            return ""
        
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
    priority_field_id=TELCO_PRIORITY_FIELD_ID, 
    priority_values=TELCO_PRIORITY_VALUES,
    report_title_template=DEFAULT_REPORT_TITLE_TEMPLATE,
    description="Deployment and lifecycle management components",
    custom_jql_base=f"""{BUG_TYPES_JQL} AND {TELCO_PRIORITY_JQL} AND Component in ({{components}}) AND {EXCLUDED_STATUSES_JQL}"""
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
    ],
    priority_field_id="",  # CNF project doesn't use Telco Priority custom field
    priority_values=[],  # No priority filtering for PTP team
    report_title_template=DEFAULT_REPORT_TITLE_TEMPLATE,
    description="Precision Time Protocol components",
    custom_jql_base=f"""((project in ({{projects}}) AND summary ~ "Telco PTP Release" AND issuetype = Story AND labels = telco-backport AND status != Closed) OR ({BUG_TYPES_JQL} AND Component in ({{components}}) AND {EXCLUDED_STATUSES_JQL}))"""
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
    custom_jql_base=f"""{BUG_TYPES_JQL} AND {{priority_clause}} AND Component in ({{components}}) AND {EXCLUDED_STATUSES_JQL}"""
)


# =============================================================================
# TEAM REGISTRY
# =============================================================================

# Central registry of all teams
TEAM_REGISTRY: Dict[str, TeamConfig] = {
    "deployment": DEPLOYMENT_TEAM,
    "ptp": PTP_TEAM,
    "networking": NETWORKING_TEAM
}


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
            'default_projects': ', '.join(config.default_projects),
            'default_components': ', '.join(config.default_components)
        }
        for config in TEAM_REGISTRY.values()
    ]

