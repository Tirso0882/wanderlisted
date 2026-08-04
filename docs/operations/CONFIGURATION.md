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
| API | `FRONTEND_URL`, `REQUEST_TIMEOUT_SECONDS`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`, `LOG_LEVEL` |
| Tracing | LangSmith/LangChain variables; tracing is optional and must not capture secrets/raw sensitive data |
| HITL | Per-gate environment overrides read by graph policy; production choices must be deliberate |

Read current code before adding a value: `.env.example` is onboarding aid, not proof that every current variable is listed.

## Committed policy

`config/config.yaml` owns API version/CORS defaults, routing, HITL flags, provider timeouts, readiness query/retry/cache limits and official-source policy, budget thresholds/reserve guidance, IATA data, and evaluation thresholds. Policy changes require focused tests and business-rule review.

## Validation

Use fake values for import/unit checks. Do not validate credentials by making a live request without approval. Production configuration is verified through secret-name presence, non-secret environment inventory, startup/ready probes, and separately approved provider smoke tests.
