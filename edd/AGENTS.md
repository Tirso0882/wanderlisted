# Evaluation-driven development scope

Read `docs/testing/AI_EVALUATION.md`, `docs/testing/TEST_DATA.md`, and `.agents/skills/agent-evaluation/SKILL.md`.

Layer 1 deterministic evaluation is the default. Cached trajectories are evidence only when fingerprints match. Cache miss may trigger live capture in some runners: inspect the runner before execution.

Separate task completion, deterministic policy, groundedness, helpfulness, pairwise comparison, and human calibration. Exclude `blocked_external` and infrastructure failures from model-quality denominators. Do not claim judge alignment without labeled calibration.

Never set `EDD_REFRESH=1`, run a paid judge/model, or call a provider without explicit approval and a disclosed case/call/cost budget.
