# Infrastructure scope

Read `docs/architecture/DEPLOYMENT_VIEW.md`, `docs/operations/CONFIGURATION.md`, `docs/operations/DEPLOYMENT.md`, and `docs/operations/RELEASE_CHECKLIST.md`.

Infrastructure is Bicep for Azure Container Apps, ACR, Log Analytics, API, frontend, and Redis, with test and production parameter files. Preserve environment separation, OIDC, secret boundaries, health probes, and production approvals.

Static validation must not create or update Azure/GitHub resources. Any `az`, `gh`, deployment workflow, image push, secret mutation, or environment change requires explicit user authorization and a stated target. Never expose resolved secrets in command output.
