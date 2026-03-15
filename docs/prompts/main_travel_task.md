Please read and analyze the three documents: LANGCHAIN_FUNDAMENTALS_REFERENCE.md, LANGGRAPH_COMPLETE_REFERENCE.md, and LANGSMITH_COMPLETE_REFERENCE.md.md.

Using these as conceptual foundations, develop a complete and thoughtful plan for building a multi-agent orchestration system whose purpose is to produce high-quality travel itineraries.

**Part 1 — Agent Analysis**
Evaluate whether it makes sense to create separate specialized agents for:
• FlightSearchTool
• FlightBookingTool
• HotelSearchTool
• WeatherTool
• CurrencyTool
• ActivitiesTool
• SafetyTool
• BudgetCalculationTool
And consider whether an IATALookupTool is beneficial or redundant.

For each possible agent, explain:
• its purpose
• what value it adds
• required inputs and outputs
• the tools or APIs it should use
• how it interacts with other agents
• whether it should exist as a separate agent

**Part 2 — Multi-Agent Architecture & Orchestration**
Design a cohesive architecture using LangChain, LangGraph, and LangSmith:
• Describe the orchestration model (supervisor, router, workflow graph, etc.)
• Explain state management, transitions, and agent communication
• Include failure-handling and fallback behavior
• Show how LangSmith would be used for tracing, debugging, and evaluation
• Ensure the architecture is extensible for future agents and tools

**Part 3 — Development Roadmap**
Create a staged learning-driven roadmap (4–6 phases). For each phase, define:
• the learning objective
• what to build
• how it contributes to understanding multi-agent patterns
• expected outcomes
• how to test or measure progress

**Part 4 — Improved Itinerary Output Format**
Propose an improved version of the itinerary system output based on japan_travel_handbook.html:
• clearer structure
• better visual hierarchy
• day-by-day breakdown
• cost summaries
• weather notes
• safety tips
• maps or location summaries
• print and mobile-friendly layout

The goal is to help me understand how to build multi-agent systems deeply enough that I can create thousands of them over time, recognizing patterns, architectures, and best practices.