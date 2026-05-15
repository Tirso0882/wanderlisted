# Wanderlisted: Stage Progression Summary

## Complete Implementation Overview

This document summarizes all four stages of the Wanderlisted multi-agent travel planning system, how to run them, and what to expect at each level.

---

## Stage Comparison Table

| Aspect | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|--------|---------|---------|---------|---------|
| **Architecture** | Simple chain | Stateful graph | Agentic loop | Multi-agent supervisor |
| **Graph?** | No | Yes | Yes | Yes |
| **State** | None | TypedDict | TypedDict | TypedDict |
| **Persistence** | None | InMemorySaver | InMemorySaver | InMemorySaver |
| **Tools** | None | None | Yes | Yes (specialized) |
| **ReAct Loop** | No | No | Yes | Yes (per agent) |
| **Multi-turn** | No | Yes | Yes | Yes |
| **Session Support** | No | Yes | Yes | Yes |
| **Specialization** | N/A | None | Single agent | Multiple agents (Supervisor + 4 specialists) |
| **Scalability** | Low | Medium | Medium | High |
| **Complexity** | Beginner | Intermediate | Advanced | Expert |

---

## Stage 1: Simple Chain

### File Location
[src/agent/stage1_simple_chain.py](../src/agent/stage1_simple_chain.py)

### What It Does
Sequential pipeline without graph structure:
```
Query → LLM → Format → Output
```

### Key Features
✅ Single-turn queries only  
✅ No state management  
✅ Simple prompt engineering  
✅ Direct LLM invocation  

### When to Use
- Learning LangChain basics
- Quick prototypes
- One-shot queries

### Example Command
```bash
python -c "
from src.agent.stage1_simple_chain import create_simple_travel_chain
from langchain_core.messages import HumanMessage

chain = create_simple_travel_chain()
result = chain.invoke({'query': 'Plan a 3-day Tokyo trip'})
print(result)
"
```

### Output Format
```
{
  'query': 'Plan a 3-day Tokyo trip',
  'itinerary': '...',
  'html_output': '<html>...</html>'
}
```

### Next: Advance to Stage 2
When you need multi-turn conversations and session persistence.

---

## Stage 2: Stateful Graph

### File Location
[src/agent/stage2_stateful_graph.py](../src/agent/stage2_stateful_graph.py)

### What It Does
Graph-based architecture with state and checkpointing:
```
START → Supervisor → Agent Loop → Format → END
  ↑                                      ↓
  └─── Session Memory (InMemorySaver) ───┘
```

### Key Features
✅ Multi-turn conversations  
✅ State persistence via checkpointing  
✅ Message history tracking  
✅ Session support (thread_id)  
✅ Conversation context across turns  

### New Concepts
- **TravelAgentState**: Typed state dictionary
- **StateGraph**: LangGraph with state management
- **Checkpointer**: Persistence layer (InMemorySaver)
- **Thread ID**: Session identifier

### Example Command
```bash
python -c "
from src.agent.stage2_stateful_graph import create_stateful_travel_graph
from langchain_core.messages import HumanMessage

graph = create_stateful_travel_graph()
config = {'configurable': {'thread_id': 'chat_1'}}

# Turn 1
r1 = graph.invoke({
    'messages': [HumanMessage('Plan Tokyo trip')],
    'session_id': 'user_123'
}, config)

# Turn 2 (state persists)
r2 = graph.invoke({
    'messages': [HumanMessage('Show me cheaper options')],
    'session_id': 'user_123'
}, config)

print(r2['itinerary'])
"
```

### State Flow
```
Input State
    ↓
[turns_loop]
    ↓
Supervisor Node (processes message)
    ↓
Agent Node (builds itinerary)
    ↓
Format Node (HTML output)
    ↓
Output State (with all message history)
```

### Output Format
```
{
  'messages': [
    HumanMessage('...'),
    AIMessage('...'),
    HumanMessage('...'),
    AIMessage('...')
  ],
  'current_agent': 'formatter',
  'session_id': 'user_123',
  'itinerary': {...},
  'itinerary_components': {}
}
```

### Next: Advance to Stage 3
When you need tool integration and iterative reasoning.

---

## Stage 3: Agentic Loop

### File Location
[src/agent/stage3_agentic_loop.py](../src/agent/stage3_agentic_loop.py)

### What It Does
Adds tool binding and ReAct-style reasoning loop:
```
START → Supervisor → Agent Execution:
          ↓            ├─ Reason about task
        TOOLS          ├─ Choose tool or finish
        ↓              ├─ Call tool
        LOOP           ├─ Observe results
        ↓              └─ (repeat until done)
      Format
       ↓
      END
```

### Key Features
✅ Tool definitions and binding  
✅ ReAct loop (Reasoning + Acting)  
✅ Multi-step tool sequences  
✅ API integrations  
✅ Error recovery  

### New Concepts
- **@tool decorator**: Define callable tools
- **Tool schemas**: LLM understands tool APIs
- **Tool calling**: LLM decides which tools to use
- **ToolMessage**: Capture tool results
- **Agentic loop**: Reason → act → observe → repeat

### Available Tools
```python
# Flights
- search_flights(origin, dest, date) → [Flight]
- compare_flight_prices(flights) → [Flight]
- book_flight(flight_id, passenger_info) → BookingConfirmation

# Hotels
- search_hotels(city, check_in, check_out) → [Hotel]
- filter_hotels_by_rating(hotels, min_rating) → [Hotel]
- get_hotel_amenities(hotel_id) → Amenities

# Destination
- search_attractions(city) → [POI]
- get_weather(city, date) → Weather
- get_transportation_info(city) → TransitInfo

# Budget
- calculate_trip_cost(flights, hotels, activities) → Cost
- find_budget_alternatives(trip, max_budget) → Trip
```

### Example Command
```bash
python -c "
from src.agent.stage3_agentic_loop import create_agentic_travel_agent
from langchain_core.messages import HumanMessage

agent_executor = create_agentic_travel_agent()

result = agent_executor.invoke({
    'messages': [HumanMessage(
        'Find direct flights to Tokyo from NYC on April 1st, '
        'then find hotels near Shibuya'
    )],
    'session_id': 'user_123'
})

# Agent:
# 1) Reasons: 'I need to search for flights'
# 2) Calls search_flights(NYC, Tokyo, 2024-04-01)
# 3) Observes results
# 4) Reasons: 'Now I need hotels near Shibuya'
# 5) Calls search_hotels(Shibuya, 2024-04-01, 2024-04-05)
# 6) Observes results
# 7) Concludes with final answer

print(result['messages'])
"
```

### Tool Calling Flow
```
User: "Find flights to Tokyo"
  ↓
Agent LLM: "I'll search for flights" 
           tool_calls=[{name: 'search_flights', args: {...}}]
  ↓
Tool Execution: search_flights(NYC, Tokyo, 2024-04-01)
               → Returns [Flight1, Flight2, ...]
  ↓
ToolMessage: "Found 10 flights, cheapest is $450"
  ↓
Agent LLM: "Found flights! Results: ..." (with tool results)
  ↓
Final Answer
```

### Output Format
```
{
  'messages': [
    HumanMessage('Find flights...'),
    AIMessage('I'll search...', tool_calls=[...]),
    ToolMessage('Found 10 flights...'),
    AIMessage('Here are the options...')
  ],
  'current_agent': 'travel_agent',
  'session_id': 'user_123',
  'output': 'Final itinerary with hotel and flight details'
}
```

### Next: Advance to Stage 4
When you need domain specialization and parallel/coordinated execution.

---

## Stage 4: Multi-Agent Supervisor

### File Location
[src/agent/stage4_graph.py](../src/agent/stage4_graph.py)

### Documentation
[docs/STAGE4_MULTIAGENT_SUPERVISOR.md](./STAGE4_MULTIAGENT_SUPERVISOR.md)

### What It Does
Specialized agents coordinated by a supervisor:
```
User Query → Supervisor Routing
               ├→ FlightsAgent (booking, pricing)
               ├→ HotelsAgent (accommodation search)
               ├→ DestinationAgent (attractions, POI)
               └→ BudgetAgent (cost analysis)
                ↓
            Consolidated Itinerary
```

### Key Features
✅ Supervisor classification routing  
✅ Specialized agents per domain  
✅ Parallel execution potential  
✅ Independent agent tools  
✅ Coordinated result consolidation  
✅ Production-ready architecture  

### New Concepts
- **SupervisorAgent**: Routes queries to specialists
- **Domain agents**: FlightsAgent, HotelsAgent, DestinationAgent, BudgetAgent
- **Agent isolation**: Each agent runs independently
- **Result consolidation**: All results merged in final state
- **Resilience**: Failure in one agent doesn't block others

### Four Specialist Agents

#### 1. FlightsAgent
**Tools:**
- `search_flights` - Find available flights
- `compare_flight_prices` - Price comparison
- `book_flight` - Flight booking

**Output:**
```python
{
  "flights": [
    {
      "id": "AA123",
      "origin": "NYC",
      "destination": "NRT",
      "departure": "2024-04-01T10:30",
      "arrival": "2024-04-02T14:15",
      "price": 750,
      "airline": "American Airlines"
    },
    ...
  ]
}
```

#### 2. HotelsAgent
**Tools:**
- `search_hotels` - Hotel discovery
- `filter_hotels_by_rating` - Quality filtering
- `get_hotel_amenities` - Amenity details

**Output:**
```python
{
  "hotels": [
    {
      "id": "hotel_456",
      "name": "Park Hyatt Tokyo",
      "location": "Shinjuku",
      "rating": 4.8,
      "price_per_night": 280,
      "amenities": ["wifi", "gym", "breakfast"],
      "availability": "2024-04-01 to 2024-04-05"
    },
    ...
  ]
}
```

#### 3. DestinationAgent
**Tools:**
- `search_attractions` - Find POI
- `get_weather` - Weather forecast
- `get_transportation_info` - Public transit

**Output:**
```python
{
  "attractions": [
    {"name": "Senso-ji Temple", "type": "temple", "rating": 4.6},
    {"name": "Shibuya Crossing", "type": "landmark", "rating": 4.8}
  ],
  "weather": {
    "date": "2024-04-01",
    "temp": 15,
    "condition": "partly cloudy"
  },
  "transportation": "Tokyo Metro, JR Lines available"
}
```

#### 4. BudgetAgent
**Tools:**
- `calculate_trip_cost` - Total cost estimation
- `find_budget_alternatives` - Cost optimization
- Currency conversion

**Output:**
```python
{
  "total": 2850,
  "breakdown": {
    "flights": 750,
    "hotels": 1400,
    "activities": 400,
    "food_transport": 300
  },
  "currency": "USD"
}
```

### Supervisor Routing Logic

SupervisorAgent classifies queries:

```
Query: "Find flights to Tokyo from NYC"
→ Classification: ["FlightsAgent"]

Query: "I need a 5-day Tokyo trip with flights, hotels, and budget"
→ Classification: ["FlightsAgent", "HotelsAgent", "DestinationAgent", "BudgetAgent"]

Query: "What are attractions in Tokyo?"
→ Classification: ["DestinationAgent"]
```

### Example Command
```bash
python -c "
from src.agent.stage4_graph import create_multiagent_travel_graph
from langchain_core.messages import HumanMessage

graph = create_multiagent_travel_graph()

# Comprehensive query
result = graph.invoke({
    'messages': [HumanMessage(
        'Plan a 5-day Tokyo trip. I want direct flights from NYC '
        'costing under $800, 4+ star hotels, attractions to visit, '
        'and total budget optimization'
    )],
    'session_id': 'user_123',
    'metadata': {
        'start_date': '2024-04-01',
        'end_date': '2024-04-05',
        'home_city': 'NYC',
        'budget': 3000,
        'hotel_stars': 4
    }
})

# Access consolidated results
components = result['itinerary_components']
print('Flights:', len(components.get('flights', [])))
print('Hotels:', len(components.get('hotels', [])))
print('Attractions:', len(components.get('destination', {}).get('attractions', [])))
print('Total Cost:', components.get('budget', {}).get('total', 'N/A'))
"
```

### State Flow
```
Input State
    ↓
Supervisor Node
  └─ Route: ["FlightsAgent", "HotelsAgent", "DestinationAgent", "BudgetAgent"]
    ↓
FlightsAgent Node ─┐
HotelsAgent Node ──┼─→ Merge Results
DestinationAgent ──┤
BudgetAgent Node ──┘
    ↓
Output State (with all components)
```

### Output Format
```
{
  'messages': [...],
  'current_agent': 'supervisor',
  'session_id': 'user_123',
  'itinerary_components': {
    'flights': [Flight...],
    'hotels': [Hotel...],
    'destination': {
      'attractions': [...],
      'weather': {...},
      'transportation': '...'
    },
    'budget': {
      'total': 2850,
      'breakdown': {...}
    }
  },
  'routing': ['FlightsAgent', 'HotelsAgent', 'DestinationAgent', 'BudgetAgent']
}
```

### When to Use Each Stage

| Use Case | Stage |
|----------|-------|
| Learning LangChain | 1 |
| Multi-turn bot | 2 |
| Tool-using agent | 3 |
| Production travel planner | 4 |
| Research/prototype | 1-2 |
| Tool integration | 3 |
| Multi-domain system | 4 |
| Scalable platform | 4 |

---

## Running All Stages

### Quick Test Script
```bash
#!/bin/bash

echo "=== Stage 1: Simple Chain ==="
python -c "from src.agent.stage1_simple_chain import create_simple_travel_chain; print('Stage 1 OK')"

echo "=== Stage 2: Stateful Graph ==="
python -c "from src.agent.stage2_stateful_graph import create_stateful_travel_graph; print('Stage 2 OK')"

echo "=== Stage 3: Agentic Loop ==="
python -c "from src.agent.stage3_agentic_loop import create_agentic_travel_agent; print('Stage 3 OK')"

echo "=== Stage 4: Multi-Agent Supervisor ==="
python -c "from src.agent.stage4_graph import create_multiagent_travel_graph; print('Stage 4 OK')"

echo "✅ All stages loaded successfully!"
```

### Individual Stage Tests
```bash
# Stage 1
python tests/test_stage1.py

# Stage 2
python tests/test_stage2.py

# Stage 3
python tests/test_stage3.py

# Stage 4
python tests/test_stage4.py
```

---

## Learning Progression

**Week 1:**
- Read [LANGCHAIN_FUNDAMENTALS_REFERENCE.md](./LANGCHAIN_FUNDAMENTALS_REFERENCE.md)
- Run Stage 1 examples
- Understand chains and prompts

**Week 2:**
- Read [LANGGRAPH_COMPLETE_REFERENCE.md](./LANGGRAPH_COMPLETE_REFERENCE.md)
- Run Stage 2 examples
- Understand state and graphs

**Week 3:**
- Study tool definitions
- Run Stage 3 examples
- Debug message flows

**Week 4:**
- Read [STAGE4_MULTIAGENT_SUPERVISOR.md](./STAGE4_MULTIAGENT_SUPERVISOR.md)
- Run Stage 4 examples
- Plan production deployment

---

## Common Extensions

### Add a New Specialist Agent
1. Create new agent class in `agents.py`
2. Add tools to the new agent
3. Update supervisor routing
4. Add node to graph in `stage4_graph.py`
5. Test routing and execution

### Connect Real APIs
1. Replace tool implementations in `tools.py`
2. Add error handling for API failures
3. Implement rate limiting
4. Cache responses

### Deploy to Production
1. Use PostgresSaver instead of InMemorySaver
2. Add monitoring/logging
3. Configure Azure Container Apps
4. Set up CI/CD pipeline

---

## Next Steps

1. **Start with Stage 1:** Run the simple chain example
2. **Understand the concepts:** Read the reference documents
3. **Progress through stages:** Each builds on the previous
4. **Add your own tools:** Integrate real APIs
5. **Deploy:** Push to Azure or your hosting platform

**Quick Start:**
```bash
cd wanderlisted
python -c "from src.agent.stage1_simple_chain import create_simple_travel_chain; print('Ready!')"
```

---

## Support Resources

- 📖 [GETTING_STARTED.md](./GETTING_STARTED.md) - Setup and first run
- 📚 [LANGCHAIN_FUNDAMENTALS_REFERENCE.md](./LANGCHAIN_FUNDAMENTALS_REFERENCE.md) - Core concepts
- 🔗 [LANGGRAPH_COMPLETE_REFERENCE.md](./LANGGRAPH_COMPLETE_REFERENCE.md) - Graph patterns
- 🏗️ [STAGE4_MULTIAGENT_SUPERVISOR.md](./STAGE4_MULTIAGENT_SUPERVISOR.md) - Production architecture
- 🛡️ [BUILDING_RELIABLE_AGENTS.md](./BUILDING_RELIABLE_AGENTS.md) - Best practices

---

## Summary

**Wanderlisted demonstrates a complete progression:**

Stage 1 → Stage 2 → Stage 3 → Stage 4

Simple → Stateful → Agentic → Multi-Agent

Each stage adds capabilities while maintaining compatibility with previous concepts.

Start simple, understand deeply, scale confidently.

🚀 **Ready to build your multi-agent system?** Start with [Stage 1](../src/agent/stage1_simple_chain.py)!
