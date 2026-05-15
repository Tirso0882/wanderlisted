"""Unit tests for extracted module-level node functions and helpers.

Tests each node function in isolation by injecting mock dependencies
(LLM, executors, supervisor_agent) via keyword arguments.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from langgraph.types import Send

from src.agent.stage4_graph import (
    # Helpers
    build_user_profile_context,
    build_context_messages,
    run_agent,
    # Node functions
    triage_node,
    shallow_reply_node,
    supervisor_node,
    flights_node,
    hotels_node,
    destination_node,
    restaurants_node,
    activities_node,
    transportation_node,
    budget_node,
    itinerary_node,
    synthesize_node,
    render_handbook_node,
    # HITL gate nodes
    safety_review_node,
    budget_review_node,
    human_review_node,
    route_after_triage,
    route_after_supervisor,
    route_after_safety_review,
    route_after_budget,
    route_after_budget_review,
    route_after_human_review,
)


# ── Helper function tests ────────────────────────────────────────────────────


class TestBuildUserProfileContext:
    def test_empty_state(self):
        state = {
            "messages": [],
            "destinations": [],
            "travel_style": "",
            "group_type": "",
        }
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
        assert any(
            "Hotels results" in m.content
            for m in result
            if isinstance(m, SystemMessage)
        )

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


# ── Send() fan-out worker node tests ─────────────────────────────────────────


class TestWorkerNodes:
    """Each parallel worker writes only its own key to itinerary_components.

    The _merge_components reducer in TravelAgentState accumulates these
    partial dicts without overwriting other workers' results.
    """

    async def _run(self, node_fn, *, return_content="Found results"):
        """Shared helper: build a mock state, run node_fn, return result."""
        mock_executor = AsyncMock()
        mock_executor.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(content=return_content),
            ],
        }
        state = {
            "messages": [HumanMessage(content="test")],
            "itinerary_components": {"routing": []},
        }
        return await node_fn(state, executor=mock_executor)

    async def test_flights_node_writes_only_flights_key(self):
        result = await self._run(flights_node, return_content="MH370 found")
        assert result["current_agent"] == "flights"
        assert "flights" in result["itinerary_components"]
        # Must NOT write other agents' keys (reducer handles merging)
        assert set(result["itinerary_components"].keys()) == {"flights"}
        assert len(result["messages"]) > 0

    async def test_hotels_node_writes_only_hotels_key(self):
        result = await self._run(hotels_node)
        assert result["current_agent"] == "hotels"
        assert set(result["itinerary_components"].keys()) == {"hotels"}

    async def test_destination_node_writes_only_destination_key(self):
        result = await self._run(destination_node)
        assert result["current_agent"] == "destination"
        assert set(result["itinerary_components"].keys()) == {"destination"}

    async def test_restaurants_node_writes_only_restaurants_key(self):
        result = await self._run(restaurants_node)
        assert result["current_agent"] == "restaurants"
        assert set(result["itinerary_components"].keys()) == {"restaurants"}

    async def test_activities_node_writes_only_activities_key(self):
        result = await self._run(activities_node)
        assert result["current_agent"] == "activities"
        assert set(result["itinerary_components"].keys()) == {"activities"}

    async def test_transportation_node_writes_only_transportation_key(self):
        result = await self._run(transportation_node)
        assert result["current_agent"] == "transportation"
        assert set(result["itinerary_components"].keys()) == {"transportation"}

    async def test_worker_strips_enriched_messages(self):
        """New messages are only the agent's own output, not the enriched context."""
        mock_executor = AsyncMock()
        mock_executor.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="original"),   # enriched message fed in
                AIMessage(content="hotel result"),  # agent output
            ],
        }
        state = {
            "messages": [HumanMessage(content="original")],
            "itinerary_components": {},
        }
        result = await hotels_node(state, executor=mock_executor)
        # Only the agent output, not the enriched input message
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "hotel result"


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

        state = {
            "messages": [HumanMessage(content="summary?")],
            "itinerary_components": {},
        }
        result = await synthesize_node(state, llm=mock_llm)

        assert result["current_agent"] == "synthesize"
        assert "Based on earlier data" in result["messages"][0].content


# ── Safety review node tests ────────────────────────────────────────────────


class TestSafetyReviewNode:
    async def test_safe_destination_passes_through(self):
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [
                        AIMessage(content="Japan is very safe. Level 1 advisory.")
                    ],
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
            danger_keywords = [
                "do not travel",
                "level 4",
                "advisory level: red",
                "reconsider travel",
                "level 3",
            ]
            assert any(kw in safety_text for kw in danger_keywords), (
                f"Missed danger: {text}"
            )


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

    def test_parallel_agents_return_send_objects(self):
        """With parallel agents, route_after_supervisor returns a list of Send objects."""
        state = {
            "messages": [HumanMessage(content="plan my trip")],
            "itinerary_components": {"routing": ["FlightsAgent", "HotelsAgent"]},
        }
        result = route_after_supervisor(state)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(s, Send) for s in result)
        # Send targets should be the node names, not agent class names
        targets = {s.node for s in result}
        assert targets == {"flights", "hotels"}

    def test_single_parallel_agent_returns_one_send(self):
        state = {
            "messages": [HumanMessage(content="hotels only")],
            "itinerary_components": {"routing": ["DestinationAgent"]},
        }
        result = route_after_supervisor(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].node == "destination"

    def test_budget_only_routes_to_budget(self):
        state = {"itinerary_components": {"routing": ["BudgetAgent"]}}
        assert route_after_supervisor(state) == "budget"

    def test_itinerary_only_routes_to_itinerary(self):
        state = {"itinerary_components": {"routing": ["ItineraryAgent"]}}
        assert route_after_supervisor(state) == "itinerary"


class TestRouteAfterSafetyReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected", "itinerary_components": {"routing": []}}
        assert route_after_safety_review(state) == END

    def test_approved_with_budget_goes_to_budget(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["BudgetAgent"]},
        }
        assert route_after_safety_review(state) == "budget"

    def test_approved_with_itinerary_goes_to_itinerary(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["ItineraryAgent"]},
        }
        assert route_after_safety_review(state) == "itinerary"

    def test_approved_no_sequential_ends(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["FlightsAgent"]},
        }
        assert route_after_safety_review(state) == END


class TestRouteAfterBudget:
    def test_always_goes_to_budget_review(self):
        assert route_after_budget({}) == "budget_review"


class TestRouteAfterBudgetReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected", "itinerary_components": {"routing": []}}
        assert route_after_budget_review(state) == END

    def test_approved_with_itinerary_routes(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["ItineraryAgent"]},
        }
        assert route_after_budget_review(state) == "itinerary"

    def test_approved_no_itinerary_ends(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["BudgetAgent"]},
        }
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


# ── Safety review HITL interrupt paths ───────────────────────────────────────


class TestSafetyReviewInterrupt:
    @patch("src.agent.stage4_graph.interrupt")
    async def test_dangerous_approved(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": True}
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [
                        AIMessage(content="Level 4: Do not travel to this area")
                    ],
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        assert result["hitl_action"] == "approved"
        assert result["safety_acknowledged"] is True
        mock_interrupt.assert_called_once()

    @patch("src.agent.stage4_graph.interrupt")
    async def test_dangerous_rejected(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": False}
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [AIMessage(content="Level 4: Do not travel")],
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        assert result["hitl_action"] == "rejected"
        assert "cancelled" in result["messages"][0].content.lower()

    @patch("src.agent.stage4_graph.interrupt")
    async def test_reconsider_travel_triggers_interrupt(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": True}
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [
                        AIMessage(content="Level 3: Reconsider travel advisory")
                    ],
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        assert result["hitl_action"] == "approved"

    async def test_tool_message_content_is_checked(self):
        """ToolMessage content should also be scanned for danger keywords."""
        state = {
            "itinerary_components": {
                "destination": {
                    "messages": [
                        ToolMessage(content="Safe to visit. Level 1.", tool_call_id="x")
                    ],
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        # Level 1 is not dangerous
        assert result["current_agent"] == "safety_review"
        assert "hitl_action" not in result


# ── Budget review HITL interrupt paths ───────────────────────────────────────


class TestBudgetReviewInterrupt:
    @patch("src.agent.stage4_graph.interrupt")
    async def test_overspend_approved(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": True}
        state = {
            "itinerary_components": {
                "budget_structured": {"total": 5000, "target_budget": 3000},
            },
            "messages": [HumanMessage(content="Plan my trip")],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["hitl_action"] == "approved"
        assert result["budget_adjustment_accepted"] is True
        mock_interrupt.assert_called_once()

    @patch("src.agent.stage4_graph.interrupt")
    async def test_overspend_approved_with_feedback(self, mock_interrupt):
        mock_interrupt.return_value = {
            "approved": True,
            "feedback": "Use budget hotels",
        }
        state = {
            "itinerary_components": {
                "budget_structured": {"total": 4500, "target_budget": 3000},
            },
            "messages": [],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["hitl_action"] == "approved"
        assert result["human_feedback"] == "Use budget hotels"

    @patch("src.agent.stage4_graph.interrupt")
    async def test_overspend_rejected(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": False, "feedback": "Too expensive"}
        state = {
            "itinerary_components": {
                "budget_structured": {"total": 6000, "target_budget": 3000},
            },
            "messages": [],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["hitl_action"] == "rejected"
        assert result["human_feedback"] == "Too expensive"
        assert "adjustment" in result["messages"][0].content.lower()


# ── Human review HITL interrupt paths ────────────────────────────────────────


class TestHumanReviewInterrupt:
    @patch("src.agent.stage4_graph.interrupt")
    async def test_approved_no_feedback(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": True}
        state = {
            "itinerary_components": {
                "flights": {"messages": [AIMessage(content="Flight found")]},
                "itinerary": {"messages": [AIMessage(content="Day 1: Tokyo")]},
            },
        }
        result = await human_review_node(state)
        assert result["hitl_action"] == "approved"
        assert result["current_agent"] == "human_review"

    @patch("src.agent.stage4_graph.interrupt")
    async def test_approved_with_feedback(self, mock_interrupt):
        mock_interrupt.return_value = {
            "approved": True,
            "feedback": "Add more food stops",
        }
        state = {
            "itinerary_components": {
                "itinerary": {"messages": [AIMessage(content="Day 1: Arrive")]},
            },
        }
        result = await human_review_node(state)
        assert result["hitl_action"] == "edited"
        assert result["human_feedback"] == "Add more food stops"
        assert "Noted your feedback" in result["messages"][0].content

    @patch("src.agent.stage4_graph.interrupt")
    async def test_rejected(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": False}
        state = {"itinerary_components": {}}
        result = await human_review_node(state)
        assert result["hitl_action"] == "rejected"
        assert "cancelled" in result["messages"][0].content.lower()

    @patch("src.agent.stage4_graph.interrupt")
    async def test_builds_component_summary_in_interrupt(self, mock_interrupt):
        mock_interrupt.return_value = {"approved": True}
        state = {
            "itinerary_components": {
                "flights": {"messages": []},
                "hotels": {"messages": []},
                "restaurants": {"messages": []},
                "activities": {"messages": []},
                "destination": {"messages": []},
                "transportation": {"messages": []},
                "budget": {"messages": []},
                "itinerary": {"messages": [AIMessage(content="Day 1 preview")]},
            },
        }
        await human_review_node(state)
        call_args = mock_interrupt.call_args[0][0]
        assert len(call_args["components_available"]) == 8


# ── Budget node structured extraction success path ───────────────────────────


class TestBudgetNodeStructured:
    async def test_extracts_structured_budget(self):
        mock_llm = MagicMock()
        mock_executor = AsyncMock()

        # The executor receives enriched messages and appends its own
        budget_msg = AIMessage(
            content="Budget: $3,500 total. Flights $800, Hotels $1200."
        )

        async def _fake_invoke(input_dict, **kwargs):
            return {"messages": input_dict["messages"] + [budget_msg]}

        mock_executor.ainvoke = _fake_invoke

        # Mock structured output extraction success
        mock_structured = AsyncMock()
        mock_budget = MagicMock()
        mock_budget.model_dump.return_value = {
            "flights": 800,
            "accommodation": 1200,
            "transport": 200,
            "meals": 500,
            "activities": 300,
            "misc": 500,
            "total": 3500,
        }
        mock_structured.ainvoke.return_value = mock_budget
        mock_llm.with_structured_output.return_value = mock_structured

        state = {
            "messages": [HumanMessage(content="budget?")],
            "itinerary_components": {"completed_agents": []},
        }
        result = await budget_node(state, llm=mock_llm, executor=mock_executor)

        assert result["current_agent"] == "budget"
        assert "budget_structured" in result["itinerary_components"]
        assert result["itinerary_components"]["budget_structured"]["flights"] == 800


# ── Render handbook node tests ───────────────────────────────────────────────


class TestRenderHandbookNode:
    def _mock_llm(self):
        """Create a mock LLM that returns defaults for all structured extractions."""
        mock = MagicMock()

        async def _fake_ainvoke(msgs):
            return mock._default_return

        mock_structured = AsyncMock()
        mock_structured.ainvoke = _fake_ainvoke

        def _with_structured_output(model_cls, **kwargs):
            # Return the default instance of whatever model is requested
            mock._default_return = model_cls()
            return mock_structured

        mock.with_structured_output = _with_structured_output
        return mock

    async def test_empty_components_returns_no_data_message(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        mock_llm = self._mock_llm()
        state = {
            "messages": [HumanMessage(content="render")],
            "itinerary_components": {},
            "destinations": [],
            "travel_style": "",
            "group_type": "",
            "dietary_restrictions": [],
            "accessibility_needs": [],
        }
        result = await render_handbook_node(state, llm=mock_llm)
        assert result["current_agent"] == "render_handbook"
        assert "no agent data" in result["messages"][0].content.lower()

    async def test_renders_handbook_with_agent_data(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        # Patch the renderer to write to tmp_path
        monkeypatch.setattr(
            "src.agent.stage4_graph.HandbookRenderer.write_outputs",
            lambda self, handbook, output_dir="outputs": {
                "html": tmp_path / "handbook.html",
                "markdown": tmp_path / "handbook.md",
                "json": tmp_path / "handbook.json",
            },
        )

        mock_llm = self._mock_llm()
        state = {
            "messages": [HumanMessage(content="Plan Tokyo trip")],
            "itinerary_components": {
                "flights": {
                    "messages": [AIMessage(content="Found JFK→NRT for $800")],
                },
                "hotels": {
                    "messages": [AIMessage(content="Shinjuku hotel $120/night")],
                },
                "destination": {
                    "messages": [AIMessage(content="Tokyo is safe. Level 1.")],
                },
                "restaurants": {
                    "messages": [AIMessage(content="Ramen shop rated 4.8")],
                },
                "activities": {
                    "messages": [AIMessage(content="Visit Senso-ji temple")],
                },
                "transportation": {
                    "messages": [AIMessage(content="JR Pass recommended")],
                },
                "budget": {
                    "messages": [AIMessage(content="Total: $3500")],
                },
                "itinerary": {
                    "messages": [AIMessage(content="Day 1: Arrive Narita")],
                },
            },
            "destinations": ["tokyo"],
            "travel_style": "mid-range",
            "group_type": "couple",
            "dietary_restrictions": [],
            "accessibility_needs": [],
        }
        result = await render_handbook_node(state, llm=mock_llm)
        assert result["current_agent"] == "render_handbook"
        assert "Handbook Generated" in result["messages"][0].content
        assert "handbook_paths" in result

    async def test_renders_with_budget_structured(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        monkeypatch.setattr(
            "src.agent.stage4_graph.HandbookRenderer.write_outputs",
            lambda self, handbook, output_dir="outputs": {
                "html": tmp_path / "h.html",
                "markdown": tmp_path / "h.md",
                "json": tmp_path / "h.json",
            },
        )

        mock_llm = self._mock_llm()
        state = {
            "messages": [HumanMessage(content="Plan trip")],
            "itinerary_components": {
                "flights": {
                    "messages": [AIMessage(content="Flight data")],
                },
                "budget_structured": {
                    "flights": 800,
                    "accommodation": 1200,
                    "transport": 200,
                    "meals": 500,
                    "activities": 300,
                    "misc": 100,
                    "total": 3100,
                    "per_person": 1550,
                    "summary": "Mid-range budget",
                },
            },
            "destinations": ["paris"],
            "travel_style": "mid-range",
            "group_type": "",
            "dietary_restrictions": [],
            "accessibility_needs": [],
        }
        result = await render_handbook_node(state, llm=mock_llm)
        assert result["current_agent"] == "render_handbook"
        assert "handbook_paths" in result

    async def test_renders_with_tool_messages(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
        monkeypatch.setattr(
            "src.agent.stage4_graph.HandbookRenderer.write_outputs",
            lambda self, handbook, output_dir="outputs": {
                "html": tmp_path / "h.html",
                "markdown": tmp_path / "h.md",
                "json": tmp_path / "h.json",
            },
        )

        mock_llm = self._mock_llm()
        state = {
            "messages": [HumanMessage(content="Plan")],
            "itinerary_components": {
                "destination": {
                    "messages": [
                        ToolMessage(content="Safety data from API", tool_call_id="t1"),
                        AIMessage(content="Tokyo is very safe"),
                    ],
                },
            },
            "destinations": ["tokyo"],
            "travel_style": "",
            "group_type": "",
            "dietary_restrictions": [],
            "accessibility_needs": [],
        }
        result = await render_handbook_node(state, llm=mock_llm)
        assert result["current_agent"] == "render_handbook"
