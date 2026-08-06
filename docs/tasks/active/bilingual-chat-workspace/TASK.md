---
id: task-bilingual-chat-workspace
doc_type: task
status: active
authority: normative
owners: [travel-platform]
applies_to: [frontend/**, src/api/**, src/agent/**, tests/**, docs/**]
load_when: [chat-ui-v2, bilingual, locale, clerk, session-history]
source_paths: [frontend/src, src/api, src/agent, tests]
---

# Bilingual production chat workspace — 2026-08-04

## Outcome

Deliver the feature-gated Atlas Sunrise chat workspace in English and Polish. The
desktop layout has history, full-height chat, and typed trip results; mobile uses
a history drawer plus Chat/Trip navigation and a sticky composer. Preserve typed
component outcomes, evidence, limitations, checkpointed HITL, and external booking
boundaries.

## Behavioral decisions

- UI locale precedence is saved account preference, locale cookie, browser
  language (`pl*` selects Polish), then English. URLs are not locale-prefixed.
- A clearly detected user turn selects the assistant response language, including
  languages beyond the English/Polish UI catalogs. Ambiguous turns retain the last
  clear conversation language, then fall back to the selected UI locale. Intake
  changes `TripRequest.locale` only for a clear turn.
- Anonymous browser ownership remains valid. Clerk adds an account identity but
  never stores passwords, email addresses, bearer tokens, or raw Clerk subjects in
  the session registry.
- The PostgreSQL registry indexes opaque owners, immutable checkpoint thread IDs,
  deterministic titles, timestamps, locale, and message counts. LangGraph remains
  authoritative for messages, structured artifacts, and interrupts.
- Saving claims only explicitly selected guest sessions. Cross-device history is
  account-scoped; deleting a session removes its registry entry and checkpoint.
- Atlas Sunrise is the single frontend experience. Clerk remains behind
  `CLERK_ENABLED`; missing locale-specific consultation URLs hide the CTA.

## Protected work

The worktree already contains uncommitted checkpointing, signed browser ownership,
rate limiting, deployment, EDD, and documentation changes. Extend those contracts
without reverting or rewriting unrelated diffs. Do not add generated outputs,
screenshots, credentials, caches, or personal files.

## Implemented checkpoint

- Atlas Sunrise ships as a responsive desktop/mobile workspace with exactly three
  contextual suggestions, right-aligned user messages, truthful loading/stop,
  typed results, localized inline HITL, history/account gates, and EN/PL copy.
- Locale resolution, canonical prompt context, Clerk JWT/webhook validation,
  opaque guest/account ownership, PostgreSQL session metadata, preferences,
  claiming, pagination, snapshot/deletion, and retention are implemented.
- Next.js removes browser authorization before proxying and forwards only its
  server-obtained Clerk token. Both rollout flags remain disabled in Bicep
  parameter files; secret values and external resources were not created.

## Verification evidence

- Backend coverage includes deterministic locale resolution, mixed-language place
  names, English/Polish/Spanish turns, ambiguous turns, language switching, API
  `ui_locale`, JWT validation failures, guest/account isolation,
  claim/list/snapshot/delete, pagination, retention, webhook deletion, and localized
  HITL restoration.
- Frontend coverage includes catalog parity, locale persistence, Polish copy/diacritics, exactly
  three suggestions, message alignment, honest loading/stop behavior, responsive
  panes, history/auth gates, accessibility, and reduced motion.
- Verified locally: 82 focused backend tests; full Ruff check/format over 280
  Python files; 11 Vitest tests; 7 mocked Playwright passes plus one intentional
  desktop skip; TypeScript; lint with only three existing image warnings;
  production build; documentation contracts; and deployment contract tests.
- The wider offline suite passed 863 tests and deselected five integration tests.
  Two protected EDD baseline-freshness tests remain red because the existing
  flights manifest has a stale source list; this chat task did not rewrite that
  separate EDD work. Bicep CLI compilation was unavailable locally; static Bicep
  contract tests passed and no Azure validation was attempted.

## External rollout boundary

Clerk application creation, production keys, passwordless/Google dashboard setup,
DNS, secrets, Azure changes, deployment, and live provider/model tests require a
separate explicit approval. This task uses only hermetic mocks and local builds.
