# Deployment Guide — Wanderlisted

## Architecture

Two **Azure Container Apps** environments, deployed via Bicep + GitHub Actions:

```
┌──────────────────────────────────────────────────────────┐
│                    GitHub Actions CI/CD                   │
│   push main → test    │   release/manual → production    │
└───────────┬───────────┴───────────────┬──────────────────┘
            │                           │
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────────┐
│  Container Apps: test │   │  Container Apps: prod     │
│  ┌─────────────────┐  │   │  ┌─────────────────────┐  │
│  │ wanderlisted-api │  │   │  │  wanderlisted-api   │  │
│  │   (scale 0→2)   │  │   │  │    (scale 1→3)      │  │
│  └─────────────────┘  │   │  └─────────────────────┘  │
│  ┌─────────────────┐  │   │  ┌─────────────────────┐  │
│  │ frontend (0→1)  │  │   │  │  frontend (1→2)     │  │
│  └─────────────────┘  │   │  └─────────────────────┘  │
│  ┌─────────────────┐  │   │  ┌─────────────────────┐  │
│  │ redis (1 fixed) │  │   │  │  redis (1 fixed)    │  │
│  └─────────────────┘  │   │  └─────────────────────┘  │
└───────────────────────┘   └───────────────────────────┘
```

### Key Differences Between Environments

| Aspect | Test | Production |
|--------|------|------------|
| API scale | 0–2 replicas | 1–3 replicas |
| Frontend scale | 0–1 replica | 1–2 replicas |
| Deploys on | Push to `main` | Release tag / manual |
| Approval | None | 1 reviewer (GitHub env) |
| Cost (idle) | ~$0 (scale to zero) | ~$15/month (always-on) |

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed
- [GitHub CLI](https://cli.github.com/) installed
- Azure subscription with Contributor access
- GitHub repository with Actions enabled

## Initial Setup (One-Time)

### 1. Run the setup script

```bash
az login
gh auth login
./infra/setup.sh
```

This creates:
- Azure resource group `wanderlisted-rg`
- Azure AD app with OIDC federated credentials (passwordless)
- GitHub repository secrets for Azure auth
- Both test and prod Container Apps environments

### 2. Add API key secrets

```bash
# Required secrets (set each one)
gh secret set AZURE_OPENAI_API_KEY --body "<your-key>"
gh secret set AZURE_OPENAI_ENDPOINT --body "https://<resource>.openai.azure.com"
gh secret set DUFFEL_ACCESS_TOKEN --body "<token>"
gh secret set GOOGLE_MAPS_API_KEY --body "<key>"
gh secret set PINECONE_API_KEY --body "<key>"
gh secret set TAVILY_API_KEY --body "<key>"
gh secret set HOTELBEDS_API_KEY --body "<key>"
gh secret set HOTELBEDS_API_SECRET --body "<secret>"
```

### 3. Add environment variables

```bash
gh variable set AZURE_OPENAI_DEPLOYMENT_NAME --body "gpt-4o"
gh variable set AZURE_OPENAI_API_VERSION --body "2024-12-01-preview"
gh variable set PINECONE_INDEX_NAME --body "wanderlisted"
```

### 4. Configure GitHub environments

Go to **Settings → Environments** in your GitHub repo:

1. Create `test` environment — no protection rules
2. Create `production` environment — add **Required reviewers** (1 person)

### 5. Set environment-specific FQDNs

After first deploy, get the environment FQDNs:

```bash
# Get test FQDN
az containerapp env show --name wanderlisted-env-test \
  --resource-group wanderlisted-rg --query properties.defaultDomain -o tsv

# Get prod FQDN
az containerapp env show --name wanderlisted-env \
  --resource-group wanderlisted-rg --query properties.defaultDomain -o tsv
```

```bash
gh secret set TEST_ENV_FQDN --body "<test-fqdn>"
gh secret set PROD_ENV_FQDN --body "<prod-fqdn>"
```

## Daily Workflow

### Deploy to Test
Simply push to `main`:
```bash
git push origin main
# → Automatically builds + deploys to test environment
```

### Deploy to Production
Create a GitHub release:
```bash
gh release create v0.3.0 --title "v0.3.0" --notes "Release notes"
# → Triggers prod deploy (requires approval)
```

Or manually via GitHub Actions UI → "Deploy to Production" → "Run workflow"

### Check Deployment Status
```bash
# View running containers
az containerapp list --resource-group wanderlisted-rg -o table

# View API logs
az containerapp logs show \
  --name wanderlisted-api-test \
  --resource-group wanderlisted-rg \
  --follow

# View frontend URL
az containerapp show --name wanderlisted-frontend-test \
  --resource-group wanderlisted-rg \
  --query properties.configuration.ingress.fqdn -o tsv
```

## Cost Estimate (10–20 Users)

| Resource | Test env | Prod env |
|----------|----------|----------|
| Container Apps (API) | ~$5/month* | ~$15/month |
| Container Apps (Frontend) | ~$3/month* | ~$8/month |
| Container Apps (Redis) | ~$5/month | ~$5/month |
| ACR Basic | $5/month (shared) | — |
| Log Analytics | ~$2/month | ~$2/month |
| **Total** | **~$20/month** | **~$30/month** |

*Test scales to zero when not in use — actual cost depends on usage.

## Sharing with Test Users

After deployment, share the frontend URL:
```
https://wanderlisted-frontend-test.<env-fqdn>
```

No user auth is currently configured — anyone with the URL can access. For restricting access to your 10–20 testers, consider adding:
- **Easy**: Azure Container Apps auth (built-in Entra ID login)
- **Simple**: HTTP basic auth via a reverse proxy sidecar

## Troubleshooting

### Container won't start
```bash
az containerapp logs show --name wanderlisted-api-test \
  --resource-group wanderlisted-rg --type system
```

### Scale-to-zero too aggressive
Increase `minReplicas` in `infra/main.bicep`:
```bicep
scale: { minReplicas: 1, maxReplicas: 2 }
```

### Environment variables not taking effect
Container Apps caches env vars per revision. Force a new revision:
```bash
az containerapp revision restart \
  --name wanderlisted-api-test \
  --resource-group wanderlisted-rg \
  --revision <revision-name>
```
