---
id: adr-0009
doc_type: adr
status: active
authority: normative
owners: [travel-platform]
applies_to: [.github/workflows/deploy-test.yml, .github/workflows/deploy-prod.yml, infra/main.bicep, frontend/**]
load_when: [release, image, promotion, digest, frontend-runtime]
source_paths: [.github/workflows/deploy-test.yml, .github/workflows/deploy-prod.yml, infra/main.bicep, frontend/Dockerfile]
---

# ADR-0009: Promote test-built images by immutable digest

**ADR status:** Accepted — 2026-08-04

## Context

The test workflow built commit-SHA images, while the release workflow looked for release-name API tags, created a different `prod-` tag, rebuilt the frontend with a production URL, and asked Bicep to deploy yet another unprefixed tag. The intended API artifact might not exist, and the frontend tested in one environment was not the artifact released to another.

## Decision

Test builds API and frontend exactly once, labels and tags both with the full commit SHA, resolves their ACR digests, and deploys by digest. Production resolves the release tag or required manual input to the same full SHA, verifies both artifacts exist, resolves their digests, and passes those digests to Bicep. Production never rebuilds, imports, or retags an image.

The frontend API proxy is a dynamic server Route Handler that reads the server-only `API_URL` at request time. No environment URL is embedded during `next build`, so one frontend artifact can move unchanged through environments.

## Consequences

- Test and production execute byte-identical container artifacts.
- Missing or mistyped release artifacts fail before Bicep deployment.
- Rollback references verified digests rather than rebuilding source.
- Each environment must set the frontend `API_URL` runtime value correctly.

## Alternatives considered

- Mutable release tags: rejected because the tag can drift and the prior workflow used inconsistent names.
- Rebuild the frontend for production: rejected because it invalidates test artifact provenance.
- Expose a browser `NEXT_PUBLIC_API_URL`: rejected because Next.js freezes public variables at build time.

## Evidence

Static workflow/Bicep contracts are in `tests/test_deployment_contract.py`. Frontend lint, type-check, and production build validate the runtime proxy route without contacting the backend.
