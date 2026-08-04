---
id: adr-0011
doc_type: adr
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/api/clerk_auth.py, src/api/clerk_webhooks.py, src/api/session_registry.py, src/api/main.py, frontend/**]
load_when: [clerk, account, session-history, claiming, locale-preference, deletion, retention]
source_paths: [src/api/clerk_auth.py, src/api/clerk_webhooks.py, src/api/session_registry.py, src/api/main.py, frontend/src]
---

# ADR-0011: Clerk account overlay and opaque session registry

**ADR status:** Accepted — 2026-08-04

## Context

ADR-0010 established anonymous browser ownership for checkpointed conversations. The product now needs optional save/history across devices without making authentication a prerequisite for chat, treating a public session ID as authorization, or copying checkpoint messages and typed artifacts into a second store. It also needs persistent English/Polish account preference and verified account-deletion cleanup.

## Decision

Guest ownership remains authoritative when a conversation is created. Clerk is an optional account overlay enabled only by configuration. The Next.js server removes browser-supplied authorization and forwards only a token obtained from the active Clerk server session. FastAPI verifies token signature, issuer, expiry, and authorized party from cached JWKS, then derives a stable opaque account key with HMAC. Passwords, email addresses, bearer tokens, and raw Clerk subjects are never stored in the Wanderlisted registry.

A PostgreSQL registry stores only opaque browser/account owner keys, immutable checkpoint thread IDs, public session IDs, deterministic titles, timestamps, UI locale, and message count. LangGraph checkpoints remain authoritative for messages, interrupts, typed outcomes, evidence, and artifacts. Saving or importing explicitly claims selected sessions belonging to the current browser; sign-in never claims every browser conversation automatically. Account history is cursor-paginated and cross-device access requires the matching opaque account owner.

Individual deletion removes the accessible registry record and checkpoint. Saved sessions inactive for 12 months are purged during lifecycle cleanup. A verified Clerk `user.deleted` webhook deletes account preferences, all owned registry records, and their checkpoint threads. Locale preference precedence is account preference, locale cookie, Polish browser language, then English; changing UI language does not translate historical/provider evidence.

## Consequences

- Guests can chat immediately and retain browser-owned continuity without Clerk availability.
- Signing in exposes only sessions explicitly claimed by that browser and account.
- Cross-device history and locale preference use opaque account identity without creating a credential store.
- PostgreSQL and Clerk/JWKS/webhook availability become serving or lifecycle dependencies only when the account feature is enabled.
- Registry/checkpoint deletion must remain coordinated; operational backups and provider-side deletion policy are separate deployment responsibilities.

## Alternatives considered

- Require sign-in before chat: rejected because guest conversion is a product requirement and Clerk availability must not block planning.
- Use Clerk subject or email as the registry key: rejected because it unnecessarily persists provider identity and personal data.
- Store full conversations in the registry: rejected because it creates two authorities for messages, interrupts, and typed evidence.
- Auto-claim every conversation found in browser storage after sign-in: rejected because importing other browser chats requires explicit user action.

## Supersession

This decision extends ADR-0010. Anonymous signed-browser ownership and owner-scoped checkpoint IDs remain in force.

## Evidence

`tests/test_clerk_auth.py` covers JWT failures, JWKS caching, opaque owners, webhook signatures, and verified account deletion. `tests/test_session_registry.py` covers guest/account isolation, explicit claiming, cross-device access, pagination, deletion, 12-month retention, preferences, and localized snapshot restoration. Frontend unit and mocked Playwright tests cover bilingual catalogs, account gates, responsive history, and locale persistence without live Clerk calls.
