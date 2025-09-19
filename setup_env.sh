#!/bin/bash

# Setup script for MCP JIRA Server
# This script helps you set up the environment variables needed for the JIRA server

echo "🔧 MCP JIRA Server Environment Setup"
echo "====================================="

# Check if .env file exists
if [ -f ".env" ]; then
    echo "📄 Found existing .env file"
    source .env
else
    echo "📝 Creating new .env file"
    touch .env
fi

# Function to prompt for variable if not set
prompt_for_var() {
    local var_name=$1
    local var_description=$2
    local current_value="${!var_name}"
    
    if [ -z "$current_value" ]; then
        echo ""
        echo "⚠️  $var_name is not set"
        echo "   $var_description"
        read -p "   Enter $var_name: " new_value
        
        if [ ! -z "$new_value" ]; then
            echo "export $var_name='$new_value'" >> .env
            export $var_name="$new_value"
            echo "✅ $var_name set successfully"
        fi
    else
        echo "✅ $var_name is already set: $current_value"
    fi
}

# Prompt for required environment variables
prompt_for_var "JIRA_URL" "Your JIRA instance URL (e.g., https://your-domain.atlassian.net)"
prompt_for_var "JIRA_TOKEN" "Your JIRA Bearer token (generate at: Settings > Personal Access Tokens)"

echo ""
echo "🎉 Environment setup complete!"
echo ""
echo "To use these variables in your current session, run:"
echo "   source .env"
echo ""
echo "To install dependencies, run:"
echo "   pip install -r requirements.txt"
echo ""
echo "To start the MCP JIRA server, run:"
echo "   python mcp_jira_server.py"
