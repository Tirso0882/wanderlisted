<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Frontend scope

Read `docs/features/stage4-orchestration/CONTRACTS.md` plus the feature pack for the displayed artifact.

- Treat backend Pydantic/API shapes as the contract; keep TypeScript types, stores, HITL payloads, and result tabs aligned.
- Render typed status, evidence, limitations, stale state, and partial outcomes honestly. Never infer missing price, safety, route, or itinerary facts in the UI.
- Preserve session continuity and the discriminated safety, budget, and human-review resume decisions.
- Reuse existing components and design tokens. Check the installed Next.js documentation before using framework APIs.

Validate focused code with `pnpm lint` and `pnpm build` from `frontend/`. Do not start providers or deploy from frontend validation.
