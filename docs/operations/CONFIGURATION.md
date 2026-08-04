---
id: operations-configuration
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [.env.example, config/config.yaml, src/agent/llm.py, src/api/main.py]
load_when: [configuration, environment, secret, provider]
source_paths: [.env.example, config/config.yaml, src/agent/llm.py, src/api/main.py]
---

# Configuration

## Sources and precedence

Runtime environment variables provide secrets/provider selection and override deployment-specific behavior. `config/config.yaml` provides committed non-secret defaults/policies. Code defaults are last-resort behavior and must be documented/tested. Never commit `.env` or resolved secrets.

`pyproject.toml` is the Python dependency manifest and `uv.lock` is the exact cross-platform resolution used by CI and container builds. `requirements.txt` is a generated compatibility export, not an independent source of dependency constraints. Frontend dependencies are fixed by `frontend/pnpm-lock.yaml` and installed with `--frozen-lockfile` in CI.

## Core environment groups

| Group | Variables |
|---|---|
| LLM selection | `LLM_PROVIDER`; provider base deployment/model plus optional `*_FAST_*` and `*_UTILITY_*`; per-tier `LLM_EFFORT_*` |
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, deployment names |
| Other supported LLMs | provider API key/model/base URL required by `src/agent/llm.py` |
| Flights | `DUFFEL_ACCESS_TOKEN`; optional base URL/supplier timeout |
| Hotels | `HOTELBEDS_API_KEY`, `HOTELBEDS_API_SECRET`; optional base URL |
| Places/routes | `GOOGLE_MAPS_API_KEY` |
| Readiness | `TAVILY_API_KEY` |
| Currency | `EXCHANGERATE_API_KEY` |
| API | `FRONTEND_URL`, `REQUEST_TIMEOUT_SECONDS`, `LOG_LEVEL` |
| Browser sessions | Secret `SESSION_SIGNING_KEY`; optional `SESSION_COOKIE_NAME`, `SESSION_COOKIE_MAX_AGE_SECONDS`, `SESSION_COOKIE_SECURE` |
| Rate limiting | `RATE_LIMIT_BACKEND`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`; `REDIS_URL` for the shared backend |
| Frontend runtime | Server-only `API_URL`; `CHAT_UI_V2_ENABLED`; locale-specific `CONSULTATION_URL_EN`/`CONSULTATION_URL_PL`; never bake environment URLs into the client image |
| Checkpoints | `CHECKPOINT_BACKEND`; secret `CHECKPOINT_DATABASE_URL`; optional `CHECKPOINT_AUTO_SETUP` |
| Session registry | `SESSION_REGISTRY_BACKEND`; secret `SESSION_REGISTRY_DATABASE_URL` (defaults to checkpoint URL); `SESSION_REGISTRY_AUTO_SETUP`; `SESSION_RETENTION_DAYS` |
| Clerk accounts | `CLERK_ENABLED`; publishable/server keys; issuer/JWKS URL; authorized parties; secret owner-hash and webhook-signing keys; cache/skew/tolerance settings |
| Localization | One-year `wanderlisted_locale` cookie; UI catalogs `en`/`pl`; request fallback `ui_locale`; no locale-prefixed URLs |
| Tracing | LangSmith/LangChain variables; tracing is optional and must not capture secrets/raw sensitive data |
| HITL | Per-gate environment overrides read by graph policy; production choices must be deliberate |

Read current code before adding a value: `.env.example` is onboarding aid, not proof that every current variable is listed.

## Committed policy

`config/config.yaml` owns API version/CORS defaults, routing, HITL flags, provider timeouts, readiness query/retry/cache limits and official-source policy, budget thresholds/reserve guidance, IATA data, and evaluation thresholds. Policy changes require focused tests and business-rule review.

## Validation

Use fake values for import/unit checks. Development defaults to memory checkpoints/registry and a bounded memory limiter. Deployed environments refuse to start without PostgreSQL checkpoints and registry, a database URL, a Redis limiter/`REDIS_URL`, or a signing key of at least 32 bytes; secure cookies cannot be disabled there. `CHAT_UI_V2_ENABLED` and `CLERK_ENABLED` default to false. Enabling Clerk additionally requires the publishable and Next.js server keys, HTTPS issuer/JWKS and authorized parties, an opaque-owner key (or the session key fallback), and a valid `whsec_` webhook secret. An empty consultation URL hides that locale's CTA. Do not validate credentials by making a live request without approval. Production configuration is verified through secret-name presence, non-secret environment inventory, startup/ready probes, owner-isolation and checkpoint-resume evidence, shared-limit evidence, and separately approved provider smoke tests.
