# Diagnostic boundary

- Factory and tier fallback: `src/agent/llm.py`.
- Current concurrency limits and wrappers: `src/agent/concurrency.py`.
- Production graph consumers: `create_multiagent_travel_graph` in `src/agent/stage4_graph.py`.
- Content extraction: `_extract_text_content` in the graph and API modules.
- Factory tests: `tests/test_llm_factory.py`.
- Provider-independent graph tests: fake executors/models in `tests/test_nodes.py`.

Model names, supported reasoning levels, API restrictions, and SDK behavior can drift. Read current code and official documentation for the configured provider instead of encoding a version-specific claim in this skill.
