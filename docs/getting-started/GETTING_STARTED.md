# Wanderlisted — Getting Started Guide

## Overview

Wanderlisted is a **multi-stage LangGraph travel agent** that evolves from simple chains to complex multi-agent architectures. This guide walks you through all stages and helps you get started.

## Architecture Stages

### Stage 1: Simple Chain (Foundations)
**File:** [src/agent/stage1_simple_chain.py](../src/agent/stage1_simple_chain.py)

A basic sequential pipeline:
```
User Query → LLM → Travel Formatter → HTML Output
```

**When to use:** Learning LangChain basics, prototyping single-turn queries

**Key Components:**
- `SimpleChainAgent`: Sequential chain without state
- No persistence or message history
- Direct API calls without tools

**Example:**
```python
from src.agent.stage1_simple_chain import create_simple_travel_chain
chain = create_simple_travel_chain()
output = chain.invoke({"query": "Plan a Tokyo trip"})
print(output)
```

---

### Stage 2: Stateful Graph (Persistence)
**File:** [src/agent/stage2_stateful_graph.py](../src/agent/stage2_stateful_graph.py)

Adds state management and multi-turn conversations:
```
START → Process Query → Build Itinerary → Format → END
  ↑                                            ↓
  └─ Conversation History & Session Memory ───┘
```

**When to use:** Multi-turn conversations, session persistence, split logic

**Key Components:**
- `TravelAgentState`: TypedDict for shared state
- `StateGraph`: LangGraph with typed state
- `InMemorySaver`: Checkpointer for conversation memory
- Message history preservation

**Example:**
```python
from src.agent.stage2_stateful_graph import create_stateful_travel_graph
graph = create_stateful_travel_graph()

# First query
result1 = graph.invoke({
    "messages": [HumanMessage("Plan Tokyo trip")],
    "session_id": "user_123"
}, {"configurable": {"thread_id": "conversation_1"}})

# Follow-up (state persisted)
result2 = graph.invoke({
    "messages": [HumanMessage("Show me under-$100 hotels")],
    "session_id": "user_123"
}, {"configurable": {"thread_id": "conversation_1"}})
```

---

### Stage 3: Agentic Loop (Tool Use)
**File:** [src/agent/stage3_agentic_loop.py](../src/agent/stage3_agentic_loop.py)

Adds tool binding and ReAct-style loops:
```
START → Supervisor → Agent Loop:
          ↓            - Reason about task
        TOOLS          - Call tools
          ↓            - Observe results
        LOOP           - Decide next action
          ↓
        Format
          ↓
        END
```

**When to use:** Complex reasoning, API integrations, iterative refinement

**Key Components:**
- `Tool` definitions (search, book, compare)
- `create_agent()` with tool binding
- Agentic loop (ReAct pattern)
- Message-based tool communication

**Tools Available:**
- Flight search and booking
- Hotel discovery and comparison
- Destination exploration
- Budget calculation

**Example:**
```python
from src.agent.stage3_agentic_loop import create_agentic_travel_agent
agent = create_agentic_travel_agent()

result = agent.invoke({
    "messages": [HumanMessage("Find flights to Tokyo under $800")],
    "session_id": "user_123"
})
# Agent reasons: "I need flights to Tokyo", calls tool, processes results
```

---

### Stage 4: Multi-Agent Supervisor (Specialization)
**File:** [src/agent/stage4_graph.py](../src/agent/stage4_graph.py) 
**Docs:** [docs/STAGE4_MULTIAGENT_SUPERVISOR.md](./STAGE4_MULTIAGENT_SUPERVISOR.md)

Specialized agents coordinated by supervisor:
```
User Query
    ↓
Supervisor (Routing)
    ├→ FlightsAgent (booking, prices)
    ├→ HotelsAgent (accommodations)
    ├→ DestinationAgent (attractions, culture)
    └→ BudgetAgent (costs, optimization)
    ↓
Consolidated Itinerary
```

**When to use:** Production systems, domain specialization, horizontal scaling

**Key Components:**
- `SupervisorAgent`: Query classification and routing
- `FlightsAgent`: Flight-specific tools and reasoning
- `HotelsAgent`: Accommodation search and comparison
- `DestinationAgent`: POI, attractions, local info
- `BudgetAgent`: Cost analysis and optimization
- Multi-agent coordination via LangGraph

**Example:**
```python
from src.agent.stage4_graph import create_multiagent_travel_graph
graph = create_multiagent_travel_graph()

result = graph.invoke({
    "messages": [HumanMessage(
        "Plan 5-day Tokyo trip with flights from NYC, "
        "budget $3000, show hotels and attractions"
    )],
    "session_id": "user_123",
    "metadata": {
        "start_date": "2024-04-01",
        "budget": 3000
    }
})

# Returns consolidated itinerary with all components
print(result["itinerary_components"])
```

---

## Quick Start

### 1. Environment Setup

```bash
# Clone repository
cd wanderlisted

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI credentials:
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_ENDPOINT=...
# AZURE_OPENAI_DEPLOYMENT_NAME=...
```

### 2. Run Your First Agent

Start with **Stage 1** for basics:

```python
# test_stage1.py
from langchain_core.messages import HumanMessage
from src.agent.stage1_simple_chain import create_simple_travel_chain

chain = create_simple_travel_chain()
result = chain.invoke({"query": "3-day Tokyo itinerary"})
print(result)
```

Run it:
```bash
python test_stage1.py
```

### 3. Enable Multi-Turn with Stage 2

```python
# test_stage2.py
from langchain_core.messages import HumanMessage
from src.agent.stage2_stateful_graph import create_stateful_travel_graph

graph = create_stateful_travel_graph()
config = {"configurable": {"thread_id": "chat_1"}}

# Query 1
r1 = graph.invoke({
    "messages": [HumanMessage("Tokyo trip")],
    "session_id": "user"
}, config)

# Query 2 (state persists)
r2 = graph.invoke({
    "messages": [HumanMessage("Cheaper options?")],
    "session_id": "user"
}, config)

print(r2["itinerary"])
```

### 4. Add Tools with Stage 3

```python
# test_stage3.py
from langchain_core.messages import HumanMessage
from src.agent.stage3_agentic_loop import create_agentic_travel_agent

agent = create_agentic_travel_agent()

result = agent.invoke({
    "messages": [HumanMessage("Find cheap flights to Paris next month")],
    "session_id": "user"
})

# Agent uses tools to search, book, compare
print(result)
```

### 5. Scale with Stage 4

```python
# test_stage4.py
from langchain_core.messages import HumanMessage
from src.agent.stage4_graph import create_multiagent_travel_graph

graph = create_multiagent_travel_graph()

result = graph.invoke({
    "messages": [HumanMessage(
        "5-day Tokyo trip, direct flights from NYC, "
        "4+ star hotels, budget $5000"
    )],
    "session_id": "user",
    "metadata": {
        "home_city": "NYC",
        "budget": 5000,
        "hotel_rating": 4
    }
})

# Get consolidated results from all agents
flights = result["itinerary_components"]["flights"]
hotels = result["itinerary_components"]["hotels"]
attractions = result["itinerary_components"]["destination"]
costs = result["itinerary_components"]["budget"]

print(f"Flights: {len(flights)} options")
print(f"Hotels: {len(hotels)} options")
print(f"Attractions: {len(attractions)} options")
print(f"Total cost: ${costs['total']}")
```

---

## File Structure

```
wanderlisted/
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py              # TravelAgentState definition
│   │   ├── tools.py              # Tool definitions
│   │   ├── agents.py             # Agent classes (all stages)
│   │   │
│   │   ├── stage1_simple_chain.py   # Simple chain (no graph)
│   │   ├── stage2_stateful_graph.py # Graph with state
│   │   ├── stage3_agentic_loop.py   # Graph with tools
│   │   └── stage4_graph.py          # Multi-agent supervisor
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── supervisor_routing.txt  # Routing prompt
│   │   └── agent_system_prompts.txt # Agent instructions
│   │
│   └── utils/
│       ├── formatters.py          # Output formatting
│       └── validators.py          # Input validation
│
├── docs/
│   ├── GETTING_STARTED.md                    # This file
│   ├── LANGCHAIN_FUNDAMENTALS_REFERENCE.md   # Core concepts
│   ├── LANGGRAPH_COMPLETE_REFERENCE.md       # Graph patterns
│   ├── STAGE4_MULTIAGENT_SUPERVISOR.md       # Stage 4 deep dive
│   ├── BUILDING_RELIABLE_AGENTS.md           # Production patterns
│   └── prompts/
│       ├── main_travel_task.md
│       ├── orchestrator_system.md
│       └── orchestrator_dev.md
│
├── tests/
│   ├── test_stage1.py
│   ├── test_stage2.py
│   ├── test_stage3.py
│   └── test_stage4.py
│
├── .env.example
├── requirements.txt
├── README.md
└── LICENSE
```

---

## Key Concepts

### State

All stages share `TravelAgentState`:

```python
from typing import TypedDict
from langchain_core.messages import BaseMessage

class TravelAgentState(TypedDict):
    messages: list[BaseMessage]        # Conversation history
    current_agent: str                 # Active agent
    session_id: str                    # User session
    itinerary_components: dict         # Domain results
    metadata: dict                     # User context
```

**Flows through graph** → each node reads/modifies → returned to next node

### Message History

```python
# Type 1: HumanMessage
HumanMessage("Find flights to Tokyo")

# Type 2: AIMessage (from LLM)
AIMessage("I'll search for flights...", tool_calls=[...])

# Type 3: ToolMessage (tool results)
ToolMessage("Flight XYZ: NYC→NRT, $750", tool_call_id="call_123")
```

**Always append, never overwrite** → preserves context

### Tools

Each agent has callable tools:

```python
@tool
def search_flights(origin: str, destination: str, date: str) -> list[dict]:
    """Search for available flights."""
    # API call, returns structured data
    return [{"flight_id": "AA123", "price": 750, ...}]

agent.tools = [search_flights, book_flight, compare_prices]
```

### Sessions

Persist state across requests:

```python
# Thread ID enables checkpointing
config = {"configurable": {"thread_id": "user_123_chat_1"}}

result1 = graph.invoke(input1, config)  # Saved to checkpointer
result2 = graph.invoke(input2, config)  # Loads previous state
```

---

## Common Tasks

### Connect to Real APIs

Update `src/agent/tools.py`:

```python
from skyscanner_scraper_api import FlightSearch

@tool
def search_flights_real(origin: str, dest: str, date: str) -> list:
    """Search real flights via Skyscanner."""
    api = FlightSearch()
    results = api.search(origin, dest, date)
    return results
```

### Add Custom Tools

Create new tool in `tools.py`:

```python
@tool
def get_restaurant_recommendations(city: str, cuisine: str) -> list:
    """Get top restaurants by cuisine."""
    # Call your API
    return restaurants
```

Add to agent:

```python
agent.tools.append(get_restaurant_recommendations)
```

### Persist Sessions to Database

Replace `InMemorySaver` with database checkpointer:

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver("postgresql://user:pass@localhost/langgraph")
graph = graph_builder.compile(checkpointer=checkpointer)
```

### Deploy to Azure

Create `infra/main.bicep`:

```bicep
resource appService 'Microsoft.Web/sites@2021-02-01' = {
  name: 'wanderlisted-${environment}'
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
  }
}
```

Deploy:

```bash
az deployment group create \
  --resource-group travel-rg \
  --template-file infra/main.bicep
```

---

## Troubleshooting

### Issue: "Missing AZURE_OPENAI_API_KEY"

**Solution:**
```bash
# Copy template
cp .env.example .env

# Edit .env with your keys
nano .env

# Verify
python -c "import os; print(os.getenv('AZURE_OPENAI_API_KEY'))"
```

### Issue: Graph times out

**Solution:**
- Add `timeout` parameter to `invoke()`
- Implement tool timeouts
- Use `stream()` for long operations

```python
# Timeout after 30s
result = graph.invoke(input, config, timeout=30)

# Or stream intermediate results
for event in graph.stream(input, config):
    print(event)
```

### Issue: Tools not calling correctly

**Solution:**
- Verify tool signatures match `@tool` decorator
- Check tool descriptions are clear
- Ensure LLM has `tool_choice` enabled

```python
# Tool signature must match LLM tool schema
@tool
def search_flights(origin: str, destination: str, date: str) -> list:
    """Search flights from origin to destination on date."""
    # Must return structured data
    return [...]
```

### Issue: State not persisting

**Solution:**
- Use same `thread_id` in config
- Check checkpointer is provided to `compile()`

```python
# This should work (same thread_id)
config = {"configurable": {"thread_id": "chat_123"}}
result1 = graph.invoke(input1, config)  # Saved
result2 = graph.invoke(input2, config)  # Loaded from save
```

---

## Learning Path

1. **Day 1-2:** Study [LANGCHAIN_FUNDAMENTALS_REFERENCE.md](./LANGCHAIN_FUNDAMENTALS_REFERENCE.md)
   - Chains, prompts, tools, parsers

2. **Day 2-3:** Study [LANGGRAPH_COMPLETE_REFERENCE.md](./LANGGRAPH_COMPLETE_REFERENCE.md)
   - StateGraph, nodes, edges, checkpointing

3. **Day 3-4:** Run Stage 1 & 2
   - Simple chain → stateful graph
   - Understand state flow

4. **Day 4-5:** Run Stage 3
   - Add tools and ReAct loop
   - Debug message flow

5. **Day 5-6:** Run Stage 4
   - Multi-agent coordination
   - Supervisor routing

6. **Day 6-7:** Implement custom tools
   - Connect real APIs
   - Build domain specialist

7. **Week 2:** Deploy to Azure
   - Container setup
   - Environment configuration
   - Monitoring and logging

---

## Resources

- **LangChain Docs:** https://python.langchain.com/docs/
- **LangGraph Docs:** https://github.com/langchain-ai/langgraph
- **Agent Patterns:** https://github.com/langchain-ai/langgraph/tree/main/examples/multi_agent/
- **Azure OpenAI:** https://learn.microsoft.com/en-us/azure/ai-services/openai/
- **LangSmith Debugging:** https://smith.langchain.com/

---

## Contributing

To add a new stage or feature:

1. Create feature branch: `git checkout -b feature/stage5_websearch`
2. Add stage file: `src/agent/stage5_*.py`
3. Document patterns: `docs/STAGE5_*.md`
4. Add tests: `tests/test_stage5.py`
5. Submit PR

---

## License

MIT License — See [LICENSE](../LICENSE)

---

**Next Steps:**

→ [Set up your environment and run Stage 1](../src/agent/stage1_simple_chain.py)

→ [Read LangChain Fundamentals](./LANGCHAIN_FUNDAMENTALS_REFERENCE.md)

→ [Explore our prompt templates](./prompts/)

Questions? Check the docs or open an issue!
