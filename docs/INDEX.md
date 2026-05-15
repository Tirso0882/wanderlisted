# Wanderlisted Documentation

> Technical documentation for the Wanderlisted multi-agent AI travel itinerary planner.

## Quick Navigation

| I need to…                                | Go to                                                              |
| ----------------------------------------- | ------------------------------------------------------------------ |
| Set up the project from scratch           | [Getting Started](getting-started/GETTING_STARTED.md)              |
| Understand the architecture               | [Architecture Overview](architecture/ARCHITECTURE_OVERVIEW.md)     |
| Add a new external API tool               | [Tool Development Guide](tools/TOOL_DEVELOPMENT_GUIDE.md)         |
| Integrate a new API (like Hotelbeds)       | [API Integration Guide](tools/API_INTEGRATION_GUIDE.md)           |
| Deploy to production                      | [Docker Production Guide](operations/DOCKER_PRODUCTION_GUIDE.md)  |
| Understand the stage progression           | [Stage Progression](getting-started/STAGE_PROGRESSION_SUMMARY.md) |
| Read LangChain/LangGraph reference         | [Reference Docs](reference/)                                      |
| Understand an architectural decision       | [ADRs](adr/)                                                      |

---

## Directory Structure

```
docs/
├── INDEX.md                          ← You are here
│
├── getting-started/                  # Onboarding & setup
│   ├── GETTING_STARTED.md            # Prerequisites, setup, first run
│   └── STAGE_PROGRESSION_SUMMARY.md  # Stage 1→4 evolution overview
│
├── architecture/                     # System design & decisions
│   ├── ARCHITECTURE_OVERVIEW.md      # High-level architecture, agents, data flow
│   ├── STAGE4_MULTIAGENT_PLAN.md     # Stage 4 design document
│   ├── STAGE4_MULTIAGENT_SUPERVISOR.md
│   ├── CHUNKING_STRATEGY_RATIONALE.md
│   ├── NVIDIA_AIQ_BLUEPRINT_REFERENCE.md
│   └── LANGGRAPH_REPLICATION_PROMPT_TO_SWITCH_FROM_SEMANTIC_KERNEL_TO_LANGGRAPH.md
│
├── tools/                            # Tool & API integration docs
│   ├── TOOL_DEVELOPMENT_GUIDE.md     # How to add a new tool (template + checklist)
│   ├── API_INTEGRATION_GUIDE.md      # Patterns for integrating external APIs
│   ├── HOTELBEDS_INTEGRATION.md      # Hotelbeds Booking API deep dive
│   ├── TOOLS_REFERENCE.md            # All tools at a glance (quick reference)
│   └── APIs/                         # OpenAPI specs and raw API docs
│       └── hotelbeds/
│           └── OpenAPI-Hotel-BookingAPI-3.0.yaml
│
├── operations/                       # Deployment & infrastructure
│   ├── DOCKER_PRODUCTION_GUIDE.md    # Docker, Compose, CI/CD, K8s
│   └── MCP_SERVER.md                 # MCP protocol server setup
│
├── reference/                        # Framework & concept references
│   ├── LANGCHAIN_FUNDAMENTALS_REFERENCE.md
│   ├── LANGGRAPH_COMPLETE_REFERENCE.md
│   ├── LANGSMITH_COMPLETE_REFERENCE.md
│   ├── BUILDING_RELIABLE_AGENTS.md
│   ├── PROMPTS_AND_MULTIAGENT_GUIDE.md
│   ├── RAG_METRICS_IMPROVEMENT_GUIDE.md
│   └── RAG_METRICS_QUICK_REFERENCE.md
│
├── adr/                              # Architecture Decision Records
│   └── (future ADRs go here)
│
├── prompts/                          # Prompt development notes
│   ├── main_travel_task.md
│   ├── orchestrator_dev.md
│   └── orchestrator_system.md
│
└── study/                            # Personal study & interview prep (not project docs)
```

---

## Adding Documentation for a New Tool

When you add a new tool or API integration to Wanderlisted, update these files:

1. **`tools/TOOLS_REFERENCE.md`** — Add a row to the tools table
2. **`tools/<API_NAME>_INTEGRATION.md`** — Create a deep-dive doc for non-trivial APIs (use [Hotelbeds](tools/HOTELBEDS_INTEGRATION.md) as a template)
3. **`tools/APIs/<provider>/`** — Drop any OpenAPI specs or raw API docs here
4. **Architecture docs** — If the tool changes agent routing or state, update [Architecture Overview](architecture/ARCHITECTURE_OVERVIEW.md)
5. **README.md** — Update the Tools table in the root README

See the [Tool Development Guide](tools/TOOL_DEVELOPMENT_GUIDE.md) for the complete checklist.
