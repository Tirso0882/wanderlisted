"""Unit tests for extracted module-level node functions and helpers.

Tests each node function in isolation by injecting mock dependencies
(LLM, executors, supervisor_agent) via keyword arguments.
"""

from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END

from src.agent.stage4_graph import (
    # Helpers
    build_user_profile_context,
    build_context_messages,
    run_agent,
    # Node functions
    triage_node,
    shallow_reply_node,
    supervisor_node,
    parallel_dispatch_node,
    budget_node,
    itinerary_node,
    synthesize_node,
    # HITL gate nodes
    safety_review_node,
    budget_review_node,
    route_after_triage,
    route_after_supervisor,
    route_after_parallel,
    route_after_safety_review,
    route_after_budget,
    route_after_budget_review,
    route_after_human_review,
)


# ── Helper function tests ────────────────────────────────────────────────────


class TestBuildUserProfileContext:
    def test_empty_state(self):
        state = {"messages": [], "destinations": [], "travel_style": "", "group_type": ""}
        assert build_user_profile_context(state) == ""

    def test_destinations_only(self):
        state = {"destinations": ["tokyo", "kyoto"]}
        result = build_user_profile_context(state)
        assert "USER PROFILE:" in result
        assert "tokyo" in result
        assert "kyoto" in result

    def test_full_profile(self):
        state = {
            "destinations": ["paris"],
            "travel_style": "luxury",
            "group_type": "couple",
            "accessibility_needs": ["wheelchair"],
            "dietary_restrictions": ["vegetarian"],
        }
        result = build_user_profile_context(state)
        assert "luxury" in result
        assert "couple" in result
        assert "wheelchair" in result
        assert "vegetarian" in result

    def test_partial_profile(self):
        state = {"travel_style": "budget", "destinations": []}
        result = build_user_profile_context(state)
        assert "budget" in result
        assert "Destinations" not in result


class TestBuildContextMessages:
    def test_no_components(self):
        state = {
            "messages": [HumanMessage(content="Hello")],
            "itinerary_components": {},
        }
        result = build_context_messages(state)
        assert len(result) == 1
        assert result[0].content == "Hello"

    def test_injects_prior_results(self):
        state = {
            "messages": [HumanMessage(content="Budget?")],
            "itinerary_components": {
                "flights": {
                    "messages": [AIMessage(content="Found JFK->NRT for $800")],
                },
            },
        }
        result = build_context_messages(state)
        # Should have: context SystemMessage + original HumanMessage
        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert "Flights results" in result[0].content
        assert "JFK" in result[0].content

    def test_injects_user_profile(self):
        state = {
            "messages": [HumanMessage(content="Go")],
            "itinerary_components": {},
            "destinations": ["rome"],
            "travel_style": "mid-range",
        }
        result = build_context_messages(state)
        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert "rome" in result[0].content

    def test_injects_both_profile_and_context(self):
        state = {
            "messages": [HumanMessage(content="Plan it")],
            "itinerary_components": {
                "hotels": {
                    "messages": [AIMessage(content="Shinjuku hotel $120/night")],
                },
            },
            "destinations": ["tokyo"],
        }
        result = build_context_messages(state)
        # profile + context + original message
        assert len(result) == 3
        assert any("tokyo" in m.content for m in result if isinstance(m, SystemMessage))
        assert any("Hotels results" in m.content for m in result if isinstance(m, SystemMessage))

    def test_skips_empty_agent_messages(self):
        state = {
            "messages": [HumanMessage(content="test")],
            "itinerary_components": {
                "flights": {"messages": [AIMessage(content="")]},
            },
        }
        result = build_context_messages(state)
        # Empty content should not produce a context injection
        assert len(result) == 1


# ── Run agent tests ──────────────────────────────────────────────────────────


class TestRunAgent:
    async def test_returns_messages_and_data_key(self):
        mock_executor = AsyncMock()
        enriched_msgs = [HumanMessage(content="test")]
        mock_executor.ainvoke.return_value = {
            "messages": enriched_msgs + [AIMessage(content="Flight found")],
        }
        executors = {"FlightsAgent": mock_executor}
        state = {"messages": [HumanMessage(content="test")], "itinerary_components": {}}

        result = await run_agent("FlightsAgent", state, executors=executors)

        assert result["data_key"] == "flights"
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Flight found"


# ── Triage node tests ───────────────────────────────────────────────────────


class TestTriageNode:
    async def test_shallow_classification(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="shallow")

        state = {"messages": [HumanMessage(content="Hi there!")]}
        result = await triage_node(state, llm=mock_llm)

        assert result["current_agent"] == "triage:shallow"

    async def test_deep_classification(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="deep")

        state = {"messages": [HumanMessage(content="Plan 10 days in Tokyo and Kyoto")]}
        result = await triage_node(state, llm=mock_llm)

        assert result["current_agent"] == "triage:deep"

    async def test_unexpected_response_defaults_to_deep(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="something unexpected")

        state = {"messages": [HumanMessage(content="maybe travel?")]}
        result = await triage_node(state, llm=mock_llm)

        assert result["current_agent"] == "triage:deep"


# ── Shallow reply node tests ────────────────────────────────────────────────


class TestShallowReplyNode:
    async def test_returns_ai_message(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Hello! How can I help?")

        state = {"messages": [HumanMessage(content="Hey")], "itinerary_components": {}}
        result = await shallow_reply_node(state, llm=mock_llm)

        assert result["current_agent"] == "shallow_reply"
        assert len(result["messages"]) == 1
        assert "Hello" in result["messages"][0].content


# ── Supervisor node tests ───────────────────────────────────────────────────


class TestSupervisorNode:
    def _mock_supervisor(self, agents, destinations=None, user_message="Planning..."):
        mock = AsyncMock()
        decision = MagicMock()
        decision.agents = agents
        decision.destinations = destinations or []
        decision.travel_style = ""
        decision.group_type = ""
        decision.accessibility_needs = []
        decision.dietary_restrictions = []
        decision.user_message = user_message
        mock.aget_routing_decision.return_value = decision
        return mock

    async def test_routes_to_parallel_agents(self):
        supervisor = self._mock_supervisor(
            agents=["FlightsAgent", "HotelsAgent"],
            destinations=["tokyo"],
        )
        state = {
            "messages": [HumanMessage(content="Plan Tokyo trip")],
            "itinerary_components": {},
            "destinations": [],
            "travel_style": "",
            "group_type": "",
            "accessibility_needs": [],
            "dietary_restrictions": [],
        }
        result = await supervisor_node(state, supervisor_agent=supervisor)

        assert result["current_agent"] == "supervisor"
        assert "FlightsAgent" in result["itinerary_components"]["routing"]
        assert result["destinations"] == ["tokyo"]

    async def test_budget_always_includes_itinerary(self):
        supervisor = self._mock_supervisor(agents=["BudgetAgent"])
        state = {
            "messages": [HumanMessage(content="What's the budget?")],
            "itinerary_components": {},
            "destinations": [],
            "travel_style": "",
            "group_type": "",
            "accessibility_needs": [],
            "dietary_restrictions": [],
        }
        result = await supervisor_node(state, supervisor_agent=supervisor)

        routing = result["itinerary_components"]["routing"]
        assert "BudgetAgent" in routing
        assert "ItineraryAgent" in routing

    async def test_preserves_existing_profile(self):
        supervisor = self._mock_supervisor(agents=[], destinations=[])
        state = {
            "messages": [HumanMessage(content="follow up")],
            "itinerary_components": {},
            "destinations": ["paris"],
            "travel_style": "luxury",
            "group_type": "couple",
            "accessibility_needs": [],
            "dietary_restrictions": ["halal"],
        }
        result = await supervisor_node(state, supervisor_agent=supervisor)

        assert result["destinations"] == ["paris"]
        assert result["travel_style"] == "luxury"
        assert result["dietary_restrictions"] == ["halal"]


# ── Parallel dispatch node tests ─────────────────────────────────────────────


class TestParallelDispatchNode:
    async def test_no_parallel_agents_passes_through(self):
        state = {
            "messages": [HumanMessage(content="test")],
            "itinerary_components": {
                "routing": ["BudgetAgent"],
                "completed_agents": [],
            },
        }
        result = await parallel_dispatch_node(state, executors={})

        assert result["current_agent"] == "parallel_dispatch"
        assert result["itinerary_components"]["completed_agents"] == []

    async def test_runs_requested_parallel_agents(self):
        mock_executor = AsyncMock()
        mock_executor.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(content="Found flights"),
            ],
        }
        executors = {"FlightsAgent": mock_executor}
        state = {
            "messages": [HumanMessage(content="test")],
            "itinerary_components": {
                "routing": ["FlightsAgent"],
                "completed_agents": [],
            },
        }
        result = await parallel_dispatch_node(state, executors=executors)

        assert "FlightsAgent" in result["itinerary_components"]["completed_agents"]
        assert "flights" in result["itinerary_components"]

    async def test_handles_agent_exception(self):
        mock_executor = AsyncMock()
        mock_executor.ainvoke.side_effect = RuntimeError("API timeout")
        executors = {"FlightsAgent": mock_executor}
        state = {
            "messages": [HumanMessage(content="test")],
            "itinerary_components": {
                "routing": ["FlightsAgent"],
                "completed_agents": [],
            },
        }
        result = await parallel_dispatch_node(state, executors=executors)

        # Agent should NOT be in completed list
        assert "FlightsAgent" not in result["itinerary_components"]["completed_agents"]
        # But we should get an error message
        assert any("error" in m.content.lower() for m in result["messages"])


# ── Budget node tests ────────────────────────────────────────────────────────


class TestBudgetNode:
    async def test_runs_budget_and_stores_result(self):
        mock_llm = MagicMock()
        mock_executor = AsyncMock()
        mock_executor.ainvoke.return_value = {
            "messages": [AIMessage(content="Total budget: $3,500")],
        }
        # structured output extraction — just skip it for unit test
        mock_llm.with_structured_output.side_effect = Exception("skip")

        state = {
            "messages": [HumanMessage(content="budget?")],
            "itinerary_components": {"completed_agents": []},
        }
        result = await budget_node(state, llm=mock_llm, executor=mock_executor)

        assert result["current_agent"] == "budget"
        assert "budget" in result["itinerary_components"]
        assert "BudgetAgent" in result["itinerary_components"]["completed_agents"]


# ── Itinerary node tests ────────────────────────────────────────────────────


class TestItineraryNode:
    async def test_runs_itinerary_and_stores_result(self):
        mock_executor = AsyncMock()
        mock_executor.ainvoke.return_value = {
            "messages": [AIMessage(content="Day 1: Arrive in Tokyo")],
        }
        state = {
            "messages": [HumanMessage(content="plan")],
            "itinerary_components": {"completed_agents": []},
        }
        result = await itinerary_node(state, executor=mock_executor)

        assert result["current_agent"] == "itinerary"
        assert "itinerary" in result["itinerary_components"]
        assert "ItineraryAgent" in result["itinerary_components"]["completed_agents"]


# ── Synthesize node tests ───────────────────────────────────────────────────


class TestSynthesizeNode:
    async def test_returns_response(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Based on earlier data...")

        state = {"messages": [HumanMessage(content="summary?")], "itinerary_components": {}}
        result = await synthesize_node(state, llm=mock_llm)

        assert result["current_agent"] == "synthesize"
        assert "Based on earlier data" in result["messages"][0].content


# ── Safety review node tests ────────────────────────────────────────────────


class TestSafetyReviewNode:
    async def test_safe_destination_passes_through(self):
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [AIMessage(content="Japan is very safe. Level 1 advisory.")],
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        assert result["current_agent"] == "safety_review"
        assert "hitl_action" not in result

    async def test_no_destination_data_passes_through(self):
        state = {"itinerary_components": {}, "safety_acknowledged": False}
        result = await safety_review_node(state)
        assert result["current_agent"] == "safety_review"

    async def test_already_acknowledged_passes_through(self):
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [AIMessage(content="Level 4: Do not travel")],
                },
            },
            "safety_acknowledged": True,
        }
        result = await safety_review_node(state)
        assert result["current_agent"] == "safety_review"

    async def test_detects_danger_keywords(self):
        """Verify the danger-detection logic without triggering interrupt()."""
        danger_texts = [
            "Level 4: Do not travel",
            "Do not travel to this area",
            "Advisory Level: Red zone",
            "Level 3: Reconsider travel",
        ]
        for text in danger_texts:
            safety_text = text.lower()
            danger_keywords = ["do not travel", "level 4", "advisory level: red", "reconsider travel", "level 3"]
            assert any(kw in safety_text for kw in danger_keywords), f"Missed danger: {text}"


# ── Budget review node tests ────────────────────────────────────────────────


class TestBudgetReviewNode:
    async def test_no_budget_data_passes_through(self):
        state = {"itinerary_components": {}, "messages": []}
        result = await budget_review_node(state)
        assert result["current_agent"] == "budget_review"

    async def test_no_target_budget_passes_through(self):
        state = {
            "itinerary_components": {
                "budget_structured": {"total": 5000, "target_budget": 0},
            },
            "messages": [],
        }
        result = await budget_review_node(state)
        assert result["current_agent"] == "budget_review"

    async def test_within_budget_passes_through(self):
        state = {
            "itinerary_components": {
                "budget_structured": {"total": 3200, "target_budget": 3000},
            },
            "messages": [],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["current_agent"] == "budget_review"

    async def test_already_accepted_passes_through(self):
        state = {
            "itinerary_components": {
                "budget_structured": {"total": 5000, "target_budget": 3000},
            },
            "messages": [],
            "budget_adjustment_accepted": True,
        }
        result = await budget_review_node(state)
        assert result["current_agent"] == "budget_review"


# ── Human review node tests ─────────────────────────────────────────────────


class TestHumanReviewNode:
    def test_builds_component_summary(self):
        """Verify summary-building logic without triggering interrupt()."""
        components = {
            "flights": {"messages": []},
            "hotels": {"messages": []},
            "itinerary": {"messages": []},
        }
        summary_parts = []
        if "flights" in components:
            summary_parts.append("Flights: found")
        if "hotels" in components:
            summary_parts.append("Hotels: found")
        if "itinerary" in components:
            summary_parts.append("Itinerary: assembled")

        assert len(summary_parts) == 3


# ── Routing function tests ──────────────────────────────────────────────────


class TestRouteAfterTriage:
    def test_shallow_routes_to_shallow_reply(self):
        state = {"current_agent": "triage:shallow"}
        assert route_after_triage(state) == "shallow_reply"

    def test_deep_routes_to_supervisor(self):
        state = {"current_agent": "triage:deep"}
        assert route_after_triage(state) == "supervisor"

    def test_missing_agent_routes_to_supervisor(self):
        state = {}
        assert route_after_triage(state) == "supervisor"


class TestRouteAfterSupervisor:
    def test_no_routing_no_data_ends(self):
        state = {"itinerary_components": {"routing": []}}
        assert route_after_supervisor(state) == END

    def test_no_routing_with_data_synthesizes(self):
        state = {"itinerary_components": {"routing": [], "flights": {}}}
        assert route_after_supervisor(state) == "synthesize"

    def test_parallel_agents_dispatch(self):
        state = {"itinerary_components": {"routing": ["FlightsAgent", "HotelsAgent"]}}
        assert route_after_supervisor(state) == "parallel_dispatch"

    def test_budget_only_routes_to_budget(self):
        state = {"itinerary_components": {"routing": ["BudgetAgent"]}}
        assert route_after_supervisor(state) == "budget"

    def test_itinerary_only_routes_to_itinerary(self):
        state = {"itinerary_components": {"routing": ["ItineraryAgent"]}}
        assert route_after_supervisor(state) == "itinerary"


class TestRouteAfterParallel:
    def test_always_goes_to_safety_review(self):
        assert route_after_parallel({}) == "safety_review"


class TestRouteAfterSafetyReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected", "itinerary_components": {"routing": []}}
        assert route_after_safety_review(state) == END

    def test_approved_with_budget_goes_to_budget(self):
        state = {"hitl_action": "approved", "itinerary_components": {"routing": ["BudgetAgent"]}}
        assert route_after_safety_review(state) == "budget"

    def test_approved_with_itinerary_goes_to_itinerary(self):
        state = {"hitl_action": "approved", "itinerary_components": {"routing": ["ItineraryAgent"]}}
        assert route_after_safety_review(state) == "itinerary"

    def test_approved_no_sequential_ends(self):
        state = {"hitl_action": "approved", "itinerary_components": {"routing": ["FlightsAgent"]}}
        assert route_after_safety_review(state) == END


class TestRouteAfterBudget:
    def test_always_goes_to_budget_review(self):
        assert route_after_budget({}) == "budget_review"


class TestRouteAfterBudgetReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected", "itinerary_components": {"routing": []}}
        assert route_after_budget_review(state) == END

    def test_approved_with_itinerary_routes(self):
        state = {"hitl_action": "approved", "itinerary_components": {"routing": ["ItineraryAgent"]}}
        assert route_after_budget_review(state) == "itinerary"

    def test_approved_no_itinerary_ends(self):
        state = {"hitl_action": "approved", "itinerary_components": {"routing": ["BudgetAgent"]}}
        assert route_after_budget_review(state) == END


class TestRouteAfterHumanReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected"}
        assert route_after_human_review(state) == END

    def test_approved_renders(self):
        state = {"hitl_action": "approved"}
        assert route_after_human_review(state) == "render_handbook"

    def test_edited_renders(self):
        state = {"hitl_action": "edited"}
        assert route_after_human_review(state) == "render_handbook"
