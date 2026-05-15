# Stage 4: Multi-Agent Supervisor Architecture

## Overview

Stage 4 implements a **supervisor-based multi-agent architecture** using LangGraph. This design separates concerns and allows specialized agents to handle specific domains while a supervisor coordinates the flow.

## Architecture Diagram

```
                        ┌─────────────────────┐
                        │  Supervisor Agent   │
                        │  (Routing Logic)    │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
        ┌───────────▼──────┐  ┌───▼────────────┐ │
        │  FlightsAgent    │  │ HotelsAgent    │ │
        │  - Booking       │  │ - Search       │ │
        │  - Price Compare │  │ - Compare      │ │
        │  - Availability  │  │ - Amenities    │ │
        └──────────────────┘  └────────────────┘ │
                                                  │
        ┌───────────────────────┬──────────────┐  │
        │                       │              │  │
    ┌───▼────────────┐    ┌────▼───────────┐  │  │
    │DestinationAgent│    │ BudgetAgent    │  │  │
    │ - Geography    │    │ - Cost Estimate│  │  │
    │ - Attractions  │    │ - Optimization │  │  │
    │ - Culture      │    │ - Comparison   │  │  │
    └────────────────┘    └────────────────┘  │  │
                                               │  │
                            ┌──────────────────┘  │
                            │                     │
                        ┌───▼──────────────────┐  │
                        │  Consolidated        │◄─┘
                        │  Itinerary           │
                        └──────────────────────┘
```

## Component Structure

### 1. State Management (`state.py`)

The `TravelAgentState` maintains shared context:

```python
class TravelAgentState(TypedDict):
    """Shared state across all agents."""
    messages: list[BaseMessage]           # Conversation history
    current_agent: str                    # Active agent name
    session_id: str                       # User session identifier
    itinerary_components: dict            # Domain-specific results
    metadata: dict                        # Extra context (dates, budget, etc.)
```

**Key Fields:**
- `messages`: Maintains full conversation history for LLM context
- `current_agent`: Tracks which agent last processed the request
- `itinerary_components`: Dict storing results from each domain agent
- `metadata`: Stores user preferences, constraints, and parameters

### 2. Supervisor Agent (`agents/supervisor.py`)

Routes queries to appropriate specialist agents:

```python
class SupervisorAgent:
    """Routes user queries to specialized agents."""
    
    def get_routing_decision(self, query: str) -> list[str]:
        """Classify query and return target agents.
        
        Returns:
            ["FlightsAgent"] if query about flights
            ["DestinationAgent"] if query about attractions
            ["HotelsAgent"] if query about accommodations
            ["BudgetAgent"] if query about costs
            [multiple agents] for complex queries
        """
```

**Decision Logic:**
- Natural language classification via LLM
- Keyword-based fallback
- Multi-agent routing for comprehensive queries
- Intent confidence scoring

### 3. Specialized Agents

#### FlightsAgent
- **Tools:** Flight booking, price comparison, availability search
- **Output:** Flight options with prices, durations, booking links
- **Integration:** Real flight APIs (Skyscanner, Google Flights, airlines)

#### HotelsAgent
- **Tools:** Hotel search, rate comparison, amenity filtering
- **Output:** Accommodation options with reviews, pricing, availability
- **Integration:** Booking.com API, Agoda, hotel networks

#### DestinationAgent
- **Tools:** POI (Points of Interest), weather, culture, transportation
- **Output:** Attractions, events, local insights, navigation context
- **Integration:** Google Places, OpenWeatherMap, local tourism APIs

#### BudgetAgent
- **Tools:** Cost estimation, currency conversion, budget optimization
- **Output:** Total trip cost breakdown, savings opportunities, alternatives
- **Integration:** XE Currency API, market data feeds

### 4. Multi-Agent Graph (`stage4_graph.py`)

LangGraph orchestration:

```python
def create_multiagent_travel_graph():
    """Builds and returns compiled graph."""
    
    # 1. Initialize LLM and agents
    supervisor = SupervisorAgent(llm)
    flights = FlightsAgent(llm)
    hotels = HotelsAgent(llm)
    destination = DestinationAgent(llm)
    budget = BudgetAgent(llm)
    
    # 2. Create graph builder
    graph_builder = StateGraph(TravelAgentState)
    
    # 3. Add nodes (supervisor + specialists)
    graph_builder.add_node("supervisor", supervisor_node)
    graph_builder.add_node("flights", flights_node)
    graph_builder.add_node("hotels", hotels_node)
    graph_builder.add_node("destination", destination_node)
    graph_builder.add_node("budget", budget_node)
    
    # 4. Define routing
    graph_builder.add_conditional_edges("supervisor", router)
    
    # 5. Connect entries/exits
    graph_builder.add_edge(START, "supervisor")
    graph_builder.add_edge("*", END)  # All paths lead to END
    
    # 6. Compile with persistence
    graph = graph_builder.compile(checkpointer=InMemorySaver())
    return graph
```

## Usage Examples

### Example 1: Single-Domain Query

```python
from langchain_core.messages import HumanMessage
from src.agent.stage4_graph import create_multiagent_travel_graph

graph = create_multiagent_travel_graph()

# Query about flights
result = graph.invoke({
    "messages": [HumanMessage("Find flights to Tokyo from NYC on April 1st")],
    "session_id": "user_123"
})

# Supervisor routes → FlightsAgent processes
# Returns: Flight options, prices, booking links
print(result["itinerary_components"]["flights"])
```

**Flow:**
1. Supervisor classifies intent → "FlightsAgent"
2. FlightsAgent queries flight APIs
3. Results stored in `itinerary_components["flights"]`
4. Graph terminates, returns full state

### Example 2: Multi-Domain Query

```python
# Comprehensive trip planning
result = graph.invoke({
    "messages": [HumanMessage(
        "Plan a 5-day Tokyo trip with flights from NYC, "
        "budget of $3000, show hotels and attractions"
    )],
    "session_id": "user_123",
    "metadata": {
        "start_date": "2024-04-01",
        "end_date": "2024-04-05",
        "budget": 3000,
        "home_city": "NYC"
    }
})

# Supervisor routes to multiple agents
# FlightsAgent → HotelsAgent → DestinationAgent → BudgetAgent
# Consolidated result includes all components
```

**Advanced Flow:**
1. Supervisor classifies → ["FlightsAgent", "HotelsAgent", "DestinationAgent", "BudgetAgent"]
2. Each agent executes according to routing priorities
3. Budget agent optimizes based on other components
4. Results integrated in `itinerary_components`

### Example 3: Follow-Up Refinement

```python
# Iteration within session
graph_config = {"configurable": {"thread_id": "user_123"}}

# First query
result1 = graph.invoke({
    "messages": [HumanMessage("Find 4-star hotels in Tokyo under $150/night")],
    "session_id": "user_123"
}, graph_config)

# Follow-up (session maintain state)
result2 = graph.invoke({
    "messages": [HumanMessage("Show me the top 3 with highest reviews")],
    "session_id": "user_123"
}, graph_config)

# Graph remembers previous context for refinement
```

## State Propagation

### How State Flows Through the Graph

1. **Input State** → START node
   - `messages`: [user query]
   - `session_id`: provided
   - `itinerary_components`: {}

2. **Supervisor Node** processes
   - Extracts intent from last message
   - Updates `current_agent` = "supervisor"
   - Adds routing decision to `itinerary_components["routing"]`

3. **Conditional Routing**
   - Router examines `itinerary_components["routing"]`
   - Directs to one or more specialist nodes
   - State passed to selected node(s)

4. **Specialist Nodes** execute
   - Each agent processes state
   - Appends results to `messages`
   - Stores output in `itinerary_components[agent_type]`
   - Returns modified state

5. **Output State** → END
   - Contains full conversation history
   - All domain results in `itinerary_components`
   - Ready for frontend rendering or export

## Error Handling & Resilience

### Per-Agent Isolation

Each agent runs independently, so failures don't cascade:

```python
def flights_node(state: TravelAgentState) -> TravelAgentState:
    try:
        result = flights_agent.invoke(state)
        state["itinerary_components"]["flights"] = result
    except APIError as e:
        state["itinerary_components"]["flights"] = {
            "error": str(e),
            "status": "failed"
        }
    return state
```

### Fallback Strategies

- **Flights unavailable?** Show alternative routes or train options
- **Weather API down?** Use cached forecast or general seasonal advice
- **Budget calculation error?** Provide UI with manual entry option

## Performance Optimization

### Parallel Execution (Future)

LangGraph's `Send` command enables parallel agent execution:

```python
from langgraph.types import Send

def supervisor_node_parallel(state: TravelAgentState):
    routing = state["routing"]
    return [
        Send("flights", state) if "FlightsAgent" in routing else None,
        Send("hotels", state) if "HotelsAgent" in routing else None,
    ]
```

### Caching

Store frequently accessed data:

```python
# Cache destination info
destination_cache = {
    "tokyo": {
        "attractions": [...],
        "weather": {...},
        "transport": {...}
    }
}

# Avoid re-querying for same destination in session
```

## Extension Points

### Adding a New Specialized Agent

```python
class ActivityAgent(BaseAgent):
    """Plans activities and experiences."""
    
    def __init__(self, llm):
        super().__init__(llm)
        self.tools = [
            search_activities,
            book_tickets,
            get_ratings
        ]
        self.system_prompt = "You plan engaging activities for travelers..."

# Add to supervisor's routing
def get_routing_decision(self, query: str):
    if "activity" in query.lower() or "entertainment" in query.lower():
        return ["ActivityAgent"]

# Add node to graph
graph_builder.add_node("activities", activities_node)
graph_builder.add_conditional_edges("supervisor", 
    lambda s: "activities" if "ActivityAgent" in s["routing"] else END
)
```

### Custom Tools

Each agent can extend with domain-specific tools:

```python
from langchain.tools import tool

@tool
def smart_hotel_filter(hotels: list, criteria: dict) -> list:
    """Filter hotels by multiple criteria."""
    filtered = hotels
    if criteria.get("wi_fi"):
        filtered = [h for h in filtered if h.get("wifi")]
    if criteria.get("min_rating"):
        filtered = [h for h in filtered if h["rating"] >= criteria["min_rating"]]
    return filtered

hotels_agent.tools.append(smart_hotel_filter)
```

## Testing Strategy

### Unit Tests

```python
def test_supervisor_routing():
    """Test supervisor decision logic."""
    supervisor = SupervisorAgent(mock_llm)
    routing = supervisor.get_routing_decision("Show me flights to Paris")
    assert "FlightsAgent" in routing

def test_flights_agent_produces_output():
    """Test FlightsAgent execution."""
    agent = FlightsAgent(mock_llm)
    result = agent.invoke(test_state)
    assert "flights" in result
    assert len(result["flights"]) > 0
```

### Integration Tests

```python
def test_full_multiagent_flow():
    """Test complete graph execution."""
    graph = create_multiagent_travel_graph()
    result = graph.invoke({
        "messages": [HumanMessage("Plan 5-day Tokyo trip")],
        "session_id": "test_123"
    })
    
    assert result["current_agent"] in ["flights", "hotels", "destination", "budget"]
    assert len(result["itinerary_components"]) > 0
```

## Deployment Considerations

### Container Deployment
- Each agent can run in separate containers
- Supervisor acts as lightweight coordinator
- Scales each agent independently based on demand

### API Gateway
- Supervisor endpoint: `/api/supervisor`
- Specialist endpoints: `/api/agents/{agent_name}`
- State sync via Redis/shared database

### Monitoring
- Track agent latency per domain
- Monitor failure rates by agent
- Log routing decisions for optimization

## Next Steps

1. **Implement real tool integrations** (Skyscanner, Booking.com APIs)
2. **Add parallel execution** using LangGraph's Send()
3. **Implement caching layer** for frequent queries
4. **Build frontend** to visualize multi-agent coordination
5. **Deploy to cloud** (Azure Container Apps, AKS)

## References

- [LangGraph State Graphs](https://github.com/langchain-ai/langgraph)
- [Multi-Agent Patterns](https://github.com/langchain-ai/langgraph/tree/main/examples)
- [Supervisor Pattern](https://github.com/langchain-ai/langgraph/blob/main/examples/multi_agent/agent_supervisor.py)
