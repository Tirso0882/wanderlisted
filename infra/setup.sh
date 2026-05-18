#!/usr/bin/env bash
# ─── Initial Azure setup (run once) ───────────────────────────────
# Creates resource group, configures OIDC for GitHub Actions, and
# deploys the base infrastructure for both environments.
#
# Prerequisites:
#   - Azure CLI installed and logged in (`az login`)
#   - GitHub CLI installed and logged in (`gh auth login`)
#
# Usage:
#   chmod +x infra/setup.sh
#   ./infra/setup.sh
# ───────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────────
AZURE_RG="wanderlisted-rg"
LOCATION="eastus2"
APP_NAME="wanderlisted"
GITHUB_ORG_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

echo "==> Setting up Azure deployment for: $GITHUB_ORG_REPO"

# ─── 1. Create Resource Group ─────────────────────────────────────
echo "==> Creating resource group: $AZURE_RG"
az group create --name "$AZURE_RG" --location "$LOCATION" --output none

# ─── 2. Create Service Principal with Federated Credentials ───────
echo "==> Creating Azure AD app registration for OIDC..."
APP_ID=$(az ad app create --display-name "${APP_NAME}-github-cd" --query appId -o tsv)
SP_OBJECT_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

# Assign Contributor role on the resource group
az role assignment create \
  --assignee "$SP_OBJECT_ID" \
  --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$AZURE_RG" \
  --output none

# Federated credential for main branch (test deploys)
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$GITHUB_ORG_REPO"':ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}' --output none

# Federated credential for test environment
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-env-test",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$GITHUB_ORG_REPO"':environment:test",
  "audiences": ["api://AzureADTokenExchange"]
}' --output none

# Federated credential for production environment
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-env-production",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$GITHUB_ORG_REPO"':environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}' --output none

echo "==> Setting GitHub repository secrets..."
gh secret set AZURE_CLIENT_ID --body "$APP_ID"
gh secret set AZURE_TENANT_ID --body "$TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID"

# ─── 3. Deploy Test Environment ───────────────────────────────────
echo "==> Deploying test environment infrastructure..."
az deployment group create \
  --resource-group "$AZURE_RG" \
  --template-file infra/main.bicep \
  --parameters infra/parameters.test.bicepparam \
  --output none

# ─── 4. Deploy Prod Environment ───────────────────────────────────
echo "==> Deploying prod environment infrastructure..."
az deployment group create \
  --resource-group "$AZURE_RG" \
  --template-file infra/main.bicep \
  --parameters infra/parameters.prod.bicepparam \
  --output none

# ─── 5. Print summary ─────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " Resource Group:   $AZURE_RG"
echo " Subscription:     $SUBSCRIPTION_ID"
echo " App Registration: $APP_ID"
echo ""
echo " Next steps:"
echo "  1. Add your API key secrets to GitHub:"
echo "     gh secret set AZURE_OPENAI_API_KEY --body <key>"
echo "     gh secret set AZURE_OPENAI_ENDPOINT --body <endpoint>"
echo "     gh secret set DUFFEL_ACCESS_TOKEN --body <token>"
echo "     gh secret set GOOGLE_MAPS_API_KEY --body <key>"
echo "     gh secret set PINECONE_API_KEY --body <key>"
echo "     gh secret set TAVILY_API_KEY --body <key>"
echo "     gh secret set HOTELBEDS_API_KEY --body <key>"
echo "     gh secret set HOTELBEDS_API_SECRET --body <secret>"
echo ""
echo "  2. Add GitHub environment variables:"
echo "     gh variable set AZURE_OPENAI_DEPLOYMENT_NAME --body <name>"
echo "     gh variable set AZURE_OPENAI_API_VERSION --body 2024-12-01-preview"
echo "     gh variable set PINECONE_INDEX_NAME --body <index>"
echo ""
echo "  3. Create GitHub environments with protection rules:"
echo "     - 'test': no approval required"
echo "     - 'production': require 1 reviewer approval"
echo ""
echo "  4. Push to main to trigger first test deployment!"
echo "============================================================"
