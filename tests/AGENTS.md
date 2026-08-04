# Test scope

Read `docs/testing/STRATEGY.md`, `docs/testing/QUALITY_GATES.md`, and the rules for the feature under test.

Default tests are deterministic and offline. Mock HTTP/provider/model boundaries, assert typed outcomes and state transitions, and cover success, partial, invalid, stale, and external-blocked paths. Use integration markers for live services; never make a test silently spend credits.

Test at the owning layer, then add contract coverage where data crosses graph, API, frontend, or renderer boundaries. Do not weaken an existing invariant to accommodate a new implementation.

Run with `.venv/bin/pytest <focused-files> -q`; report deselected or skipped live tests.
