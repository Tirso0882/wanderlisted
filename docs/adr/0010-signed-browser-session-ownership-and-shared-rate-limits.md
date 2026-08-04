---
id: adr-0010
doc_type: adr
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/api/auth.py, src/api/rate_limit.py, src/api/main.py, infra/**]
load_when: [authentication, session, ownership, rate-limit, cors]
source_paths: [src/api/auth.py, src/api/rate_limit.py, src/api/main.py, tests/test_api_security.py]
---

# ADR-0010: Signed browser session ownership and shared Redis limits

**ADR status:** Accepted — 2026-08-04

## Context

Public session IDs previously became LangGraph thread IDs without an ownership check. Anyone who learned or guessed one could query its history or submit a resume decision. The same caller-controlled ID keyed an unbounded process-local limiter, which could be bypassed by changing IDs and could not coordinate workers or replicas. Wanderlisted currently has no traveler-account model.

## Decision

The API issues a random anonymous browser principal in an HMAC-signed HttpOnly SameSite cookie. Deployed cookies are Secure, the signing secret is stable across replicas, and startup fails when the key is absent or shorter than 32 bytes. Every state-bearing endpoint derives an opaque checkpoint `thread_id` from the principal and validated public session ID. A different principal therefore resolves to an unrelated thread and receives the same not-found behavior as an absent session.

Deployed environments require an atomic Redis fixed-window limiter shared by all workers and replicas. Redis connection or command failure denies protected requests. Direct development may use a bounded memory implementation. FastAPI and Container Apps CORS allow only the configured frontend origin and required methods/headers.

## Consequences

- Knowing a public session ID is insufficient to read or resume another browser's checkpoint.
- The same browser can continue and resume a durable thread across API workers and restarts while its cookie remains valid.
- API replicas share one limit decision and may scale horizontally.
- This is anonymous browser ownership, not a user account: it does not synchronize across devices, cookie deletion loses access, and it is not a complete bot/edge-abuse control.
- Redis becomes a serving dependency. The current internal single-replica container fails closed but is not a high-availability design.

## Alternatives considered

- Treat a random session ID as a bearer secret: rejected because IDs are exposed to browser storage/URLs and ownership remains unenforced.
- Require Entra or another account provider immediately: rejected because the product has no account contract and that would be a separate product decision.
- Keep process-local limits with one replica: rejected because it prevents safe horizontal scaling and still resets on restart.

## Evidence

`tests/test_api_security.py` covers same-owner continuity, cross-owner history/resume denial, signed-cookie tamper/expiry behavior, secure attributes, shared Redis decisions, and fail-closed Redis errors. `tests/test_deployment_contract.py` covers secure parameter injection, internal Redis ingress, restricted CORS, and restored replica limits.
