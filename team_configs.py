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
    
    def get_jql_priority_clause(self) -> str:
        """Generate JQL clause for priority filtering."""
        if not self.priority_values:
            return ""
        
        priority_list = ', '.join([f'"{p}"' for p in self.priority_values])
        return f'{self.priority_field_id} in ({priority_list})'
    
    def get_report_title(self, components: Optional[List[str]] = None) -> str:
        """Generate report title based on components."""
        if components:
            component_text = ' + '.join(components)
        else:
            component_text = self.team_name
        
        return self.report_title_template.format(
            team=self.team_name,
            components=component_text
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            'team_name': self.team_name,
            'team_id': self.team_id,
            'default_projects': self.default_projects,
            'default_components': self.default_components,
            'priority_field_id': self.priority_field_id,
            'priority_values': self.priority_values,
            'report_title_template': self.report_title_template,
            'description': self.description
        }


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
        "Networking / SR-IOV",
        "Installer / Assisted Installer",
        "oc / cluster-compare"
    ],
    priority_field_id="customfield_12323649",
    priority_values=[
        "Telco:Priority-1",
        "Telco:Priority-2",
        "Telco:Priority-3"
    ],
    report_title_template="{components} Stale Issues Analysis",
    description="Deployment and lifecycle management components"
)

# PTP Team (Precision Time Protocol)
# Uses custom JQL base query that includes both backport stories and bugs
PTP_TEAM = TeamConfig(
    team_name="PTP Team",
    team_id="ptp",
    default_projects=["OCPBUGS"],
    default_components=[
        "Cloud Native Events / Cloud Event Proxy",
        "Cloud Native Events / Hardware Event Proxy",
        "Networking / ptp",
        "Telco Edge / HW Event Operator"
    ],
    priority_field_id="customfield_12323649",
    priority_values=[
        "Telco:Priority-1",
        "Telco:Priority-2",
        "Telco:Priority-3"
    ],
    report_title_template="PTP {components} Stale Issues Analysis",
    description="Precision Time Protocol components",
    custom_jql_base="""(
        (project = OCPBUGS AND summary ~ "Telco PTP Release" AND issuetype = Story AND labels = telco-backport AND status != Closed)
        OR
        (Type in (Bug, Weakness, Vulnerability) AND Component in ("Cloud Native Events / Cloud Event Proxy", "Cloud Native Events / Hardware Event Proxy", "Networking / ptp", "Telco Edge / HW Event Operator") AND resolution = Unresolved AND Status != Verified AND Status != Done)
    )"""
)

# Networking Team (Placeholder - to be configured later)
NETWORKING_TEAM = TeamConfig(
    team_name="Networking Team",
    team_id="networking",
    default_projects=[],  # To be configured
    default_components=[],  # To be configured
    priority_field_id="",  # To be configured
    priority_values=[],  # To be configured
    report_title_template="Networking {components} Stale Issues Analysis",
    description="Networking infrastructure components (configuration pending)",
    custom_jql_base=None  # To be configured with custom JQL if needed
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


def get_default_team() -> TeamConfig:
    """Get the default team configuration (Deployment Team)."""
    return DEPLOYMENT_TEAM

