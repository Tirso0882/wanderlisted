# Stage 4: Multi-Agent Supervisor Architecture

## Overview

**From:** Single monolithic agent with all 9 tools  
**To:** Supervisor coordinating 5 specialized sub-agents + tool routing

```
┌──────────────────────────────────────────────────────────────┐
│                    USER QUERY                                 │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │    SUPERVISOR AGENT                 │
        │  (Routes to appropriate sub-agent)   │
        └─────┬──────────────┬────────┬────────┤
              │              │        │        │
    ┌─────────▼────┐ ┌──────▼────┐ ┌─▼─────┐ ┌──▼──────┐
    │ Flights      │ │ Hotels    │ │Budget │ │Destination
    │ Agent        │ │ Agent     │ │Agent  │ │Agent
    ├──────────────┤ ├───────────┤ ├───────┤ ├─────────┐
    │Tools:        │ │Tools:     │ │Tools: │ │Tools:   │
    │• IATA lookup │ │• Hotels   │ │• Calc │ │• RAG    │
    │• Flights API │ │• Activities│ │Budget │ │• Weather│
    │              │ │           │ │• Conv │ │• Safety │
    └──────────────┘ └───────────┘ │Curren │ └─────────┘
                                    │cy    │
                                    └──────┘
```

## Design Principles

### 1. **Specialization**
Each sub-agent is expert in its domain:
- **FlightsAgent**: Air travel, departure/arrival optimization
- **HotelsAgent**: Accommodation, local activities, dining
- **DestinationAgent**: Cultural context, safety, weather, insider tips
- **BudgetAgent**: Financial tracking, currency conversion, cost optimization
- **SupervisorAgent**: Query classification, routing logic

### 2. **State Management**
```python
class Stage4ConversationState:
    """Multi-agent state"""
    messages: list[BaseMessage]           # Conversation history
    current_agent: str                    # "supervisor", "flights", "hotels", etc.
    itinerary_components: dict            # Accumulated results (flights, hotels, etc.)
    session_id: str                       # For continuity
    user_preferences: dict                # Budget, dates, interests
```

### 3. **Routing Logic (Supervisor)**
```
Query → Classifier → Determine domain(s) → Route to agent(s)

Examples:
- "Find me flights to Tokyo" → FlightsAgent
- "Best hotels near Tokyo Tower" → HotelsAgent
- "Is Tokyo safe? Weather in March?" → DestinationAgent
- "Create a 5-day Tokyo itinerary with budget" → SupervisorAgent delegates all
```

### 4. **Tool Distribution**

| Agent | Tools |
|-------|-------|
| FlightsAgent | lookup_iata_code, search_flights |
| HotelsAgent | search_hotels, search_activities |
| DestinationAgent | search_destination_guides, get_weather, get_safety_info |
| BudgetAgent | calculate_budget, convert_currency |
| SupervisorAgent | (no direct tools, coordinates others) |

## Implementation Plan

### Phase 1: Define Agent Infrastructure (2 hours)
- [ ] Create `src/agent/agents/` directory
- [ ] Create `Supervisor` agent class
- [ ] Create specialized agent classes (Flights, Hotels, Destination, Budget)
- [ ] Update state management in `state.py`

### Phase 2: Implement Specialized Agents (4 hours)
- [ ] FlightsAgent with IATA + flights tools
- [ ] HotelsAgent with hotels + activities tools
- [ ] DestinationAgent with RAG + weather + safety tools
- [ ] BudgetAgent with budget calculation + currency conversion
- [ ] Write tests for each agent

### Phase 3: Build Supervisor Routing (3 hours)
- [ ] Create query classification logic
- [ ] Implement routing decision logic
- [ ] Handle multi-agent coordination (e.g., full itinerary)
- [ ] Implement fallback/error handling

### Phase 4: LangGraph Integration (3 hours)
- [ ] Create graph nodes for each agent
- [ ] Define state transitions
- [ ] Add checkpointer for persistence
- [ ] Test end-to-end flow with FastAPI

### Phase 5: Testing & Documentation (2 hours)
- [ ] Unit tests for each agent
- [ ] Integration tests for multi-agent flow
- [ ] Update API endpoints if needed
- [ ] Document routing decisions

---

## Agent Prompts (Summary)

### SupervisorAgent Prompt
```
You are the travel planning supervisor. Your role:
1. Analyze the user's request
2. Determine if it needs specialized attention or coordination
3. Route to appropriate sub-agent(s):
   - FlightsAgent: "Find flights", "Best airline", "When to book"
   - HotelsAgent: "Hotels near...", "Best neighborhoods", "Activities"
   - DestinationAgent: "Is it safe?", "Weather", "Culture", "Local tips"
   - BudgetAgent: "Total cost", "Breakdown", "Currency conversion"
4. Synthesize results and provide cohesive recommendations

When the user needs a full itinerary, YOU coordinate with all sub-agents.
```

### Specialized Agent Prompts (Example: FlightsAgent)
```
You are an expert flight specialist. Your responsibilities:
1. Search for flights using the search_flights tool
2. Optimize for: budget, timing, connections (based on preference)
3. Explain trade-offs (price vs. convenience)
4. Check airport codes with lookup_iata_code tool
5. Provide booking recommendations and timing advice
```

---

## Example Flow: Multi-Agent Coordination

**User:** "Plan a 5-day Tokyo trip for 2 people with a $5000 budget"

```
1. SupervisorAgent receives query
   ├─ Classifies as "full itinerary" (multi-domain)
   └─ Needs all agents

2. Supervisor asks user for:
   ├─ Travel dates
   ├─ Departure city
   └─ Interests (culture, food, nightlife, etc.)

3. Once clarified, Supervisor orchestrates:
   ├─ FlightsAgent: Search flights (NYC→Tokyo)
   │  └─ Returns: 3 flight options, total cost $600/person
   │
   ├─ HotelsAgent: Search hotels (3-4 star, central)
   │  └─ Returns: 5 hotels, ~$100/night = $1500 total
   │
   ├─ DestinationAgent: Gather context
   │  └─ Returns: "March is cherry blossom season, mild weather, safe"
   │
   ├─ HotelsAgent: Get activities (schedule)
   │  └─ Returns: Temple visits, museums, restaurants, costs
   │
   └─ BudgetAgent: Calculate total
      └─ Returns: $2100 flights + $1500 hotels + $1000 activities = $4600
                  (Under $5000 budget, $400 buffer)

4. SupervisorAgent synthesizes into itinerary:
   - Day 1: Arrival + check-in
   - Day 2: Temple district (Senso-ji)
   - Day 3: Modern Tokyo (Shibuya)
   - Day 4: Day trip (Mt. Fuji)
   - Day 5: Departure prep
   
   With all costs, times, recommendations
```

---

## Key Differences from Stage 2

| Aspect | Stage 2 (Current) | Stage 4 (Proposed) |
|--------|------|----------|
| Agent Count | 1 (monolithic) | 5 (supervisor + 4 specialists) |
| Tool Assignment | All tools in one agent | Distributed by domain |
| Routing | Implicit (LLM decides) | Explicit (supervisor routes) |
| Scalability | Hard to extend | Easy (add new agents) |
| Error handling | Single point of failure | Graceful fallback |
| Specialization | Generalist | Expert specialists |
| Latency | Single LLM call | Potentially parallel calls |
| Debugging | Hard (mixed responsibilites) | Easy (clear boundaries) |
| Testing | Monolithic tests | Unit + integration tests |

---

## Success Criteria

- [ ] All 9 tools work through sub-agents
- [ ] Supervisor correctly routes 95%+ of queries
- [ ] Full itinerary generation completes end-to-end
- [ ] Response time < 10s for simple queries, < 30s for full itineraries
- [ ] 8+ unit tests per agent
- [ ] Zero regression from Stage 2 functionality
- [ ] Clear log output showing agent transitions

---

## Timeline

- **Today:** Phases 1-2 (6 hours)
- **Tomorrow:** Phases 3-5 (8 hours)
- **Total:** ~14 hours implementation

Start with Phase 1 → Phase 2, validate with tests.
Then Phase 3 → 4 → 5.
