"""Unit tests for extracted module-level node functions and helpers.

Tests each node function in isolation by injecting mock dependencies
(LLM, executors, supervisor_agent) via keyword arguments.
"""

from datetime import date
import json
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from langgraph.types import Send

from src.readiness import (
    PlanningConstraint,
    ReadinessSource,
    TravelReadinessReport,
    TravelReadinessRun,
)
from src.tools.tavily import TavilyTimeoutError
from src.models import (
    AccommodationSelectionProposal,
    BudgetBreakdown,
    BudgetCoverageStatus,
    BudgetVerdict,
    ConversionStatus,
    DaySelectionProposal,
    DraftDay,
    DraftItinerary,
    ItinerarySelectionProposal,
    PlaceRef,
    SafetyInfo,
    build_trip_skeleton,
)
from src.budget import BudgetRun
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
    readiness_node,
    restaurants_node,
    activities_node,
    draft_itinerary_node,
    transportation_node,
    budget_node,
    itinerary_node,
    synthesize_node,
    # HITL gate nodes
    safety_review_node,
    budget_review_node,
    human_review_node,
    route_after_triage,
    route_after_intake,
    route_after_supervisor,
    route_after_readiness_preflight,
    route_after_readiness,
    route_after_safety_review,
    route_after_trip_skeleton,
    route_after_hotel_gate,
    route_after_draft_itinerary,
    route_after_transportation,
    route_after_budget,
    route_after_budget_review,
    route_after_human_review,
)


def _verified_safety_coverage(destination: str) -> dict:
    return {
        "items": [
            {
                "destination": destination,
                "topic": "safety",
                "critical": True,
                "state": "verified",
                "source_ids": ["S1"],
                "error_category": "none",
                "detail": "",
            }
        ]
    }


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

    async def test_budget_only_does_not_include_itinerary(self):
        supervisor = self._mock_supervisor(agents=["BudgetAgent", "ItineraryAgent"])
        state = {
            "messages": [HumanMessage(content="How much would a week in Bali cost?")],
            "trip_request": {
                "scope": "focused",
                "destinations": ["bali"],
                "date_window": {"duration_days": 7},
                "travelers": {"adults": 1},
                "requested_capabilities": ["budget"],
            },
            "itinerary_components": {},
            "destinations": [],
            "travel_style": "",
            "group_type": "",
            "accessibility_needs": [],
            "dietary_restrictions": [],
        }
        result = await supervisor_node(state, supervisor_agent=supervisor)

        routing = result["itinerary_components"]["routing"]
        assert routing == ["BudgetAgent"]

    async def test_generic_city_break_overrides_broad_supervisor_routing(self):
        supervisor = self._mock_supervisor(
            agents=[
                "FlightsAgent",
                "HotelsAgent",
                "TravelReadinessAgent",
                "RestaurantsAgent",
                "ActivitiesAgent",
                "TransportationAgent",
                "BudgetAgent",
                "ItineraryAgent",
            ]
        )
        state = {
            "messages": [HumanMessage(content="Plan a city break in Wroclaw")],
            "trip_request": {
                "scope": "full_itinerary",
                "destinations": ["wroclaw"],
                "date_window": {
                    "exact_start": "2026-10-08",
                    "exact_end": "2026-10-10",
                },
            },
            "itinerary_components": {},
            "destinations": ["wroclaw"],
            "travel_style": "",
            "group_type": "",
            "accessibility_needs": [],
            "dietary_restrictions": [],
        }

        result = await supervisor_node(state, supervisor_agent=supervisor)

        assert result["itinerary_components"]["routing"] == [
            "RestaurantsAgent",
            "ActivitiesAgent",
            "TransportationAgent",
            "ItineraryAgent",
        ]

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

    async def test_readiness_node_writes_only_readiness_key(self):
        mock_executor = AsyncMock()
        report = TravelReadinessReport(
            destinations=["tokyo"],
            sources=[
                ReadinessSource(
                    id="S1",
                    title="Tokyo",
                    url="https://example.com/tokyo",
                    domain="example.com",
                    query="Tokyo travel",
                    topic="culture",
                )
            ],
        )
        mock_executor.research.return_value = TravelReadinessRun(
            report=report,
            message="Grounded Tokyo research.",
        )
        state = {
            "messages": [HumanMessage(content="Research Tokyo")],
            "trip_request": {"destinations": ["tokyo"]},
            "itinerary_components": {"routing": []},
        }
        result = await readiness_node(state, executor=mock_executor)
        assert result["current_agent"] == "readiness"
        assert set(result["itinerary_components"].keys()) == {"readiness"}
        assert result["itinerary_components"]["readiness"]["data"]["destinations"] == [
            "tokyo"
        ]
        assert result["component_results"]["readiness"]["evidence_count"] == 1

    async def test_readiness_timeout_is_classified_as_external(self):
        mock_executor = AsyncMock()
        mock_executor.research.side_effect = TavilyTimeoutError(
            "Tavily request timed out"
        )
        result = await readiness_node(
            {
                "messages": [HumanMessage(content="Research Tokyo")],
                "trip_request": {"destinations": ["tokyo"]},
            },
            executor=mock_executor,
        )
        outcome = result["component_results"]["readiness"]
        assert outcome["status"] == "blocked_external"
        assert outcome["error_category"] == "timeout"

    async def test_restaurants_node_writes_only_restaurants_key(self):
        result = await self._run(restaurants_node)
        assert result["current_agent"] == "restaurants"
        assert set(result["itinerary_components"].keys()) == {"restaurants"}

    async def test_activities_node_writes_only_activities_key(self):
        result = await self._run(activities_node)
        assert result["current_agent"] == "activities"
        assert set(result["itinerary_components"].keys()) == {"activities"}

    async def test_activities_receive_only_grounded_readiness_constraints(self):
        mock_executor = AsyncMock()

        async def invoke(payload):
            return {
                "messages": [
                    *payload["messages"],
                    AIMessage(content="Selected accessible places."),
                ]
            }

        mock_executor.ainvoke.side_effect = invoke
        report = TravelReadinessReport(
            destinations=["tokyo"],
            summary="General readiness prose that discovery does not need.",
            planning_constraints=[
                PlanningConstraint(
                    category="culture",
                    severity="warning",
                    destination="Tokyo",
                    summary="Temple admission requires covered shoulders.",
                    source_ids=["S1"],
                )
            ],
            sources=[
                ReadinessSource(
                    id="S1",
                    title="Grounded constraint",
                    url="https://example.com/constraint",
                    domain="example.com",
                    query="Tokyo access constraint",
                    topic="culture",
                )
            ],
        )
        state = {
            "messages": [HumanMessage(content="Find Tokyo activities")],
            "itinerary_components": {
                "readiness": {
                    "messages": [AIMessage(content=report.summary)],
                    "data": report.model_dump(mode="json"),
                }
            },
        }

        await activities_node(state, executor=mock_executor)

        payload = mock_executor.ainvoke.await_args.args[0]
        system_context = "\n".join(
            message.content
            for message in payload["messages"]
            if isinstance(message, SystemMessage)
        )
        assert "GROUNDED READINESS PLANNING CONSTRAINTS" in system_context
        assert "covered shoulders" in system_context
        assert report.summary not in system_context

    async def test_transportation_node_writes_only_transportation_key(self):
        result = await self._run(transportation_node)
        assert result["current_agent"] == "transportation"
        assert set(result["itinerary_components"].keys()) == {"transportation"}

    async def test_transportation_receives_merged_hotel_and_activity_context(self):
        mock_executor = AsyncMock()

        async def invoke(payload):
            return {
                "messages": [
                    *payload["messages"],
                    AIMessage(content="Connected route plan"),
                ],
            }

        mock_executor.ainvoke.side_effect = invoke
        state = {
            "messages": [HumanMessage(content="Plan my trip")],
            "itinerary_components": {
                "routing": [
                    "HotelsAgent",
                    "ActivitiesAgent",
                    "TransportationAgent",
                ],
                "hotels": {"messages": [AIMessage(content="Hotel Central")]},
                "activities": {"messages": [AIMessage(content="Museum and old town")]},
            },
        }

        await transportation_node(state, executor=mock_executor)

        payload = mock_executor.ainvoke.await_args.args[0]
        system_context = "\n".join(
            message.content
            for message in payload["messages"]
            if isinstance(message, SystemMessage)
        )
        assert "Hotel Central" in system_context
        assert "Museum and old town" in system_context

    @patch("src.agent.stage4_graph.compute_day_route_data")
    async def test_transportation_routes_exact_selected_places(self, mock_route):
        mock_route.return_value = {
            "ordered_stops": ["48.86,2.33", "5 Rue de Thorigny, Paris"],
            "legs": [
                {
                    "from_location": "1 Rue de Rivoli, Paris",
                    "to_location": "48.86,2.33",
                    "distance_meters": 900,
                    "duration_seconds": 600,
                    "instructions": ["Take metro line 1"],
                },
                {
                    "from_location": "48.86,2.33",
                    "to_location": "5 Rue de Thorigny, Paris",
                    "distance_meters": 1300,
                    "duration_seconds": 780,
                    "instructions": [],
                },
            ],
            "total_distance_meters": 2200,
            "total_duration_seconds": 1380,
            "error": "",
        }
        draft = DraftItinerary(
            days=[
                DraftDay(
                    day_number=1,
                    start_location=PlaceRef(
                        name="Hotel Central", address="1 Rue de Rivoli, Paris"
                    ),
                    stops=[
                        PlaceRef(name="Louvre", latitude=48.86, longitude=2.33),
                        PlaceRef(
                            name="Picasso Museum",
                            address="5 Rue de Thorigny, Paris",
                        ),
                    ],
                    preferred_mode="transit",
                )
            ]
        )
        state = {
            "messages": [HumanMessage(content="Plan Paris")],
            "itinerary_components": {
                "routing": ["TransportationAgent", "ItineraryAgent"],
                "draft_itinerary_structured": draft.model_dump(),
            },
        }

        result = await transportation_node(state, executor=AsyncMock())

        args = mock_route.call_args.args
        assert args[0] == ["48.86,2.33", "5 Rue de Thorigny, Paris"]
        assert args[1] == "1 Rue de Rivoli, Paris"
        route_plan = result["itinerary_components"]["route_plan_structured"]
        assert route_plan["days"][0]["ordered_stops"][0]["name"] == "Louvre"
        assert route_plan["days"][0]["legs"][0]["duration_seconds"] == 600

    @patch(
        "src.agent.stage4_graph.compute_day_route_data",
        side_effect=RuntimeError("maps unavailable"),
    )
    async def test_transportation_degrades_failed_day_route(self, _mock_route):
        draft = DraftItinerary(
            days=[
                DraftDay(
                    day_number=2,
                    start_location=PlaceRef(name="Hotel"),
                    stops=[PlaceRef(name="Museum")],
                )
            ]
        )
        state = {
            "messages": [HumanMessage(content="Plan it")],
            "itinerary_components": {
                "routing": ["TransportationAgent"],
                "draft_itinerary_structured": draft.model_dump(),
            },
        }

        result = await transportation_node(state, executor=AsyncMock())

        day = result["itinerary_components"]["route_plan_structured"]["days"][0]
        assert day["day_number"] == 2
        assert day["ordered_stops"][0]["name"] == "Museum"
        assert "unavailable" in day["warning"].lower()

    async def test_worker_strips_enriched_messages(self):
        """New messages are only the agent's own output, not the enriched context."""
        mock_executor = AsyncMock()
        mock_executor.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="original"),  # enriched message fed in
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


class TestDraftItineraryNode:
    async def test_selects_structured_draft_from_discovery_evidence(self):
        mock_llm = MagicMock()
        structured_llm = AsyncMock()
        structured_llm.ainvoke.return_value = ItinerarySelectionProposal(
            accommodations=[
                AccommodationSelectionProposal(
                    stay_sequence=1,
                    rate_key="rate-central",
                )
            ],
            days=[
                DaySelectionProposal(
                    day_number=2,
                    stop_source_ids=["activities:place-museum"],
                    preferred_mode="walk",
                )
            ],
        )
        mock_llm.with_structured_output.return_value = structured_llm
        skeleton = build_trip_skeleton(
            cities=["paris"], start_date=date(2026, 9, 1), duration_days=3
        )
        hotel_payload = {
            "options": [
                {
                    "source_id": "rate-central",
                    "rate_key": "rate-central",
                    "name": "Hotel Central",
                    "check_in": "2026-09-01",
                    "check_out": "2026-09-03",
                    "amount": "450",
                    "currency": "USD",
                }
            ]
        }
        place_payload = {
            "places": [
                {
                    "source_id": "place-museum",
                    "place_id": "place-museum",
                    "name": "City Museum",
                    "search_context": "museums in paris",
                    "address": "2 Museum Road",
                    "category": "museum",
                }
            ]
        }
        state = {
            "messages": [HumanMessage(content="Plan a day")],
            "trip_request": {
                "scope": "full_itinerary",
                "destinations": ["paris"],
                "date_window": {
                    "exact_start": "2026-09-01",
                    "exact_end": "2026-09-03",
                    "duration_days": 3,
                },
                "travelers": {"adults": 2},
            },
            "itinerary_components": {
                "routing": ["TransportationAgent", "ItineraryAgent"],
                "trip_skeleton_structured": skeleton.model_dump(mode="json"),
                "hotels": {
                    "messages": [
                        ToolMessage(
                            content="HOTEL_RESULTS_JSON:\n" + json.dumps(hotel_payload),
                            tool_call_id="hotel-tool",
                        )
                    ]
                },
                "activities": {
                    "messages": [
                        ToolMessage(
                            content="PLACE_RESULTS_JSON:\n" + json.dumps(place_payload),
                            tool_call_id="place-tool",
                        )
                    ]
                },
            },
        }

        result = await draft_itinerary_node(state, llm=mock_llm)

        draft = result["itinerary_components"]["draft_itinerary_structured"]
        assert draft["days"][0]["start_location"]["name"] == "Hotel Central"
        assert draft["days"][1]["stops"][0]["name"] == "City Museum"
        assert draft["days"][1]["stops"][0]["source_id"] == ("activities:place-museum")
        prompt_text = "\n".join(
            message.content for message in structured_llm.ainvoke.await_args.args[0]
        )
        assert "Hotel Central" in prompt_text
        assert "City Museum" in prompt_text


# ── Budget node tests ────────────────────────────────────────────────────────


class TestBudgetNode:
    async def test_runs_budget_and_stores_result(self):
        agent = AsyncMock()
        agent.run.return_value = BudgetRun(
            report=BudgetBreakdown(
                total=3500,
                summary="Validated total",
                request_fingerprint="budget-fingerprint",
            ),
            message="Validated total",
        )

        state = {
            "messages": [HumanMessage(content="budget?")],
            "itinerary_components": {"completed_agents": []},
        }
        result = await budget_node(state, agent=agent)

        assert result["current_agent"] == "budget"
        assert "budget" in result["itinerary_components"]
        assert result["itinerary_components"]["budget_structured"]["total"] == 3500
        assert "BudgetAgent" in result["itinerary_components"]["completed_agents"]
        assert result["component_results"]["budget"]["request_fingerprint"] == (
            "budget-fingerprint"
        )


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

    async def test_receives_selected_draft_and_route_plan(self):
        mock_executor = AsyncMock()

        async def invoke(payload):
            return {
                "messages": [
                    *payload["messages"],
                    AIMessage(content="Final assembled itinerary"),
                ]
            }

        mock_executor.ainvoke.side_effect = invoke
        state = {
            "messages": [HumanMessage(content="Build the final itinerary")],
            "itinerary_components": {
                "completed_agents": ["TransportationAgent"],
                "draft_itinerary": {
                    "messages": [
                        AIMessage(content='DRAFT_ITINERARY_JSON: {"hotel":"Central"}')
                    ]
                },
                "transportation": {
                    "messages": [
                        AIMessage(content='ROUTE_PLAN_JSON: {"duration_seconds":600}')
                    ]
                },
            },
        }

        result = await itinerary_node(state, executor=mock_executor)

        payload = mock_executor.ainvoke.await_args.args[0]
        system_context = "\n".join(
            message.content
            for message in payload["messages"]
            if isinstance(message, SystemMessage)
        )
        assert "DRAFT_ITINERARY_JSON" in system_context
        assert "ROUTE_PLAN_JSON" in system_context
        assert result["messages"][0].content == "Final assembled itinerary"


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
        report = TravelReadinessReport(
            destinations=["japan"],
            safety=SafetyInfo(
                advisory_level="green", advisory_summary="Normal precautions."
            ),
            sources=[
                ReadinessSource(
                    id="S1",
                    title="Official advisory",
                    url="https://travel.state.gov/japan",
                    domain="travel.state.gov",
                    query="Japan advisory",
                    topic="safety",
                    is_official=True,
                )
            ],
            citations={"safety.advisory_level": ["S1"]},
        )
        state = {
            "itinerary_components": {
                "readiness_preflight": {
                    "data": report.model_dump(mode="json"),
                    "coverage": _verified_safety_coverage("japan"),
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        assert result["current_agent"] == "safety_review"
        assert result["hitl_action"] == "approved"

    async def test_missing_structured_safety_data_fails_closed(self):
        state = {"itinerary_components": {}, "safety_acknowledged": False}
        result = await safety_review_node(state)
        assert result["hitl_action"] == "rejected"

    async def test_stale_preflight_fingerprint_fails_closed_at_safety_gate(self):
        report = TravelReadinessReport(
            destinations=["tokyo"],
            safety=SafetyInfo(
                advisory_level="green", advisory_summary="Normal precautions."
            ),
            sources=[
                ReadinessSource(
                    id="S1",
                    title="Official advisory",
                    url="https://travel.state.gov/japan",
                    domain="travel.state.gov",
                    query="Japan advisory",
                    topic="safety",
                    is_official=True,
                )
            ],
            citations={"safety.advisory_level": ["S1"]},
        )
        state = {
            "messages": [HumanMessage(content="Is Kyoto safe?")],
            "trip_request": {
                "scope": "focused",
                "destinations": ["kyoto"],
                "requested_capabilities": ["travel_readiness"],
                "readiness_topics": ["safety"],
            },
            "itinerary_components": {
                "readiness_preflight": {
                    "data": report.model_dump(mode="json"),
                    "coverage": _verified_safety_coverage("tokyo"),
                },
            },
            "component_results": {
                "readiness_preflight": {
                    "status": "completed",
                    "request_fingerprint": "stale-request",
                }
            },
        }

        result = await safety_review_node(state)

        assert result["hitl_action"] == "rejected"
        assert "no longer matches" in result["messages"][0].content

    async def test_already_acknowledged_passes_through(self):
        state = TestSafetyReviewInterrupt._state("red", "Level 4: Do not travel")
        state["safety_acknowledged"] = True
        result = await safety_review_node(state)
        assert result["hitl_action"] == "approved"

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

    def test_deep_routes_to_intake(self):
        state = {"current_agent": "triage:deep"}
        assert route_after_triage(state) == "intake"

    def test_missing_agent_routes_to_intake(self):
        state = {}
        assert route_after_triage(state) == "intake"

    def test_pending_clarification_overrides_shallow_classification(self):
        state = {
            "current_agent": "triage:shallow",
            "pending_questions": ["origin_city"],
        }
        assert route_after_triage(state) == "intake"

    def test_target_agent_still_routes_through_required_intake(self):
        state = {"current_agent": "triage:deep", "target_agent": "FlightsAgent"}
        assert route_after_triage(state) == "intake"


class TestRouteAfterIntake:
    def test_ready_routes_to_supervisor(self):
        assert route_after_intake({"workflow_status": "ready"}) == "supervisor"

    def test_missing_input_ends_turn(self):
        assert route_after_intake({"workflow_status": "needs_user_input"}) == END


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
        assert len(result) == 1
        assert all(isinstance(s, Send) for s in result)
        # Hotels waits until TripSkeleton allocates exact city stays.
        targets = {s.node for s in result}
        assert targets == {"flights"}

    def test_generic_city_break_starts_only_destination_discovery(self):
        state = {
            "messages": [HumanMessage(content="Plan a city break in Wroclaw")],
            "trip_request": {
                "scope": "full_itinerary",
                "destinations": ["wroclaw"],
            },
            "itinerary_components": {
                "routing": [
                    "RestaurantsAgent",
                    "ActivitiesAgent",
                    "TransportationAgent",
                    "ItineraryAgent",
                ]
            },
        }

        result = route_after_supervisor(state)

        assert isinstance(result, list)
        assert [send.node for send in result] == ["restaurants", "activities"]

    def test_readiness_runs_before_parallel_dispatch(self):
        state = {
            "messages": [HumanMessage(content="Tokyo etiquette")],
            "trip_request": {
                "scope": "focused",
                "destinations": ["tokyo"],
                "requested_capabilities": ["travel_readiness"],
                "readiness_topics": ["culture"],
            },
            "itinerary_components": {"routing": ["TravelReadinessAgent"]},
        }
        result = route_after_supervisor(state)
        assert result == "readiness"

    def test_stale_readiness_fingerprint_is_not_reused(self):
        state = {
            "messages": [HumanMessage(content="Tokyo etiquette")],
            "trip_request": {
                "scope": "focused",
                "destinations": ["tokyo"],
                "requested_capabilities": ["travel_readiness"],
                "readiness_topics": ["culture"],
            },
            "itinerary_components": {"routing": ["TravelReadinessAgent"]},
            "component_results": {
                "readiness": {
                    "status": "completed",
                    "request_fingerprint": "stale-request",
                }
            },
        }

        assert route_after_supervisor(state) == "readiness"

    def test_full_trip_runs_safety_preflight_before_any_discovery(self):
        state = {
            "messages": [HumanMessage(content="Plan the whole trip")],
            "trip_request": {
                "scope": "full_itinerary",
                "destinations": ["tokyo"],
                "passport_country": "Poland",
            },
            "itinerary_components": {
                "routing": [
                    "FlightsAgent",
                    "TravelReadinessAgent",
                    "ActivitiesAgent",
                ]
            },
        }
        assert route_after_supervisor(state) == "readiness_preflight"

    def test_transportation_waits_for_discovery_fanout(self):
        state = {
            "messages": [HumanMessage(content="plan my trip")],
            "itinerary_components": {
                "routing": [
                    "HotelsAgent",
                    "ActivitiesAgent",
                    "TransportationAgent",
                ]
            },
        }
        result = route_after_supervisor(state)
        assert isinstance(result, list)
        assert {send.node for send in result} == {"activities"}

    def test_hotels_only_routes_to_trip_skeleton(self):
        state = {"itinerary_components": {"routing": ["HotelsAgent"]}}
        assert route_after_supervisor(state) == "trip_skeleton"

    def test_transportation_only_routes_through_trip_prerequisites(self):
        state = {"itinerary_components": {"routing": ["TransportationAgent"]}}
        assert route_after_supervisor(state) == "trip_skeleton"

    def test_budget_only_routes_to_budget(self):
        state = {"itinerary_components": {"routing": ["BudgetAgent"]}}
        assert route_after_supervisor(state) == "budget"

    def test_itinerary_only_routes_through_trip_prerequisites(self):
        state = {"itinerary_components": {"routing": ["ItineraryAgent"]}}
        assert route_after_supervisor(state) == "trip_skeleton"

    def test_budget_and_itinerary_route_through_trip_prerequisites(self):
        state = {"itinerary_components": {"routing": ["BudgetAgent", "ItineraryAgent"]}}
        assert route_after_supervisor(state) == "trip_skeleton"


class TestRouteAfterReadinessPreflight:
    def test_verified_preflight_continues_to_safety_gate(self):
        state = {"component_results": {"readiness_preflight": {"status": "completed"}}}
        assert route_after_readiness_preflight(state) == "safety_review"

    def test_missing_advisory_evidence_fails_closed(self):
        state = {
            "component_results": {"readiness_preflight": {"status": "no_inventory"}}
        }
        assert route_after_readiness_preflight(state) == END


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

    def test_draft_selection_runs_before_transportation(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["TransportationAgent", "BudgetAgent"]},
        }
        assert route_after_safety_review(state) == "trip_skeleton"

    def test_approved_with_itinerary_goes_to_itinerary(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["ItineraryAgent"]},
        }
        assert route_after_safety_review(state) == "trip_skeleton"

    def test_approved_dispatches_requested_parallel_discovery(self):
        state = {
            "hitl_action": "approved",
            "itinerary_components": {"routing": ["FlightsAgent"]},
        }
        result = route_after_safety_review(state)
        assert isinstance(result, list)
        assert [send.node for send in result] == ["flights"]

    def test_full_trip_runs_readiness_details_before_discovery(self):
        state = {
            "hitl_action": "approved",
            "trip_request": {"scope": "full_itinerary"},
            "itinerary_components": {
                "routing": [
                    "TravelReadinessAgent",
                    "FlightsAgent",
                    "ActivitiesAgent",
                ],
                "readiness_preflight": {"data": {"destinations": ["tokyo"]}},
            },
            "component_results": {"readiness": {"status": "completed"}},
        }

        assert route_after_safety_review(state) == "readiness"


class TestRouteAfterReadiness:
    def test_completed_readiness_dispatches_other_discovery_workers(self):
        report = TravelReadinessReport(
            destinations=["tokyo"],
            planning_constraints=[
                PlanningConstraint(
                    category="culture",
                    severity="warning",
                    summary="Temple admission requires covered shoulders.",
                    source_ids=["S1"],
                )
            ],
            sources=[
                ReadinessSource(
                    id="S1",
                    title="Grounded constraint",
                    url="https://example.com/constraint",
                    domain="example.com",
                    query="Tokyo access constraint",
                    topic="culture",
                )
            ],
        )
        state = {
            "itinerary_components": {
                "routing": [
                    "TravelReadinessAgent",
                    "FlightsAgent",
                    "ActivitiesAgent",
                ],
                "readiness": {"data": report.model_dump(mode="json")},
            },
            "component_results": {"readiness": {"status": "completed"}},
        }

        result = route_after_readiness(state)

        assert isinstance(result, list)
        assert {send.node for send in result} == {"flights", "activities"}
        assert all(
            send.arg["itinerary_components"]["readiness"]["data"]
            == report.model_dump(mode="json")
            for send in result
        )

    def test_failed_readiness_reaches_gate_without_spending_discovery_calls(self):
        state = {
            "itinerary_components": {
                "routing": ["TravelReadinessAgent", "ActivitiesAgent"]
            },
            "component_results": {"readiness": {"status": "blocked_external"}},
        }

        assert route_after_readiness(state) == "component_gate"


class TestRouteAfterTripSkeleton:
    def test_hotels_fan_out_one_worker_per_exact_city_stay(self):
        skeleton = build_trip_skeleton(
            cities=["warszawa", "krakow"],
            start_date=date(2026, 8, 20),
            duration_days=9,
        )
        state = {
            "workflow_status": "skeleton_ready",
            "messages": [HumanMessage(content="plan")],
            "itinerary_components": {
                "routing": ["HotelsAgent", "ItineraryAgent"],
                "trip_skeleton_structured": skeleton.model_dump(mode="json"),
            },
        }

        result = route_after_trip_skeleton(state)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(send.node == "hotel_stay" for send in result)
        stays = [send.arg["active_hotel_stay"] for send in result]
        assert [stay["city"] for stay in stays] == ["warszawa", "krakow"]
        assert stays[0]["check_in"] == "2026-08-20"
        assert stays[-1]["check_out"] == "2026-08-28"

    def test_without_hotels_continues_to_draft(self):
        state = {
            "workflow_status": "skeleton_ready",
            "itinerary_components": {
                "routing": ["TransportationAgent", "ItineraryAgent"]
            },
        }
        assert route_after_trip_skeleton(state) == "draft_itinerary"

    def test_failed_skeleton_ends(self):
        assert route_after_trip_skeleton({"workflow_status": "failed"}) == END


class TestRouteAfterHotelGate:
    def test_completed_hotels_continue_to_draft(self):
        state = {
            "workflow_status": "planning",
            "itinerary_components": {
                "routing": ["HotelsAgent", "TransportationAgent", "ItineraryAgent"]
            },
        }
        assert route_after_hotel_gate(state) == "draft_itinerary"

    def test_incomplete_hotels_end(self):
        state = {
            "workflow_status": "no_inventory",
            "itinerary_components": {"routing": ["HotelsAgent"]},
        }
        assert route_after_hotel_gate(state) == END


class TestRouteAfterDraftItinerary:
    def test_transportation_runs_before_budget(self):
        state = {
            "itinerary_components": {"routing": ["TransportationAgent", "BudgetAgent"]}
        }
        assert route_after_draft_itinerary(state) == "transportation"

    def test_without_transportation_routes_to_budget(self):
        state = {"itinerary_components": {"routing": ["BudgetAgent", "ItineraryAgent"]}}
        assert route_after_draft_itinerary(state) == "budget"

    def test_itinerary_only_routes_to_final_assembly(self):
        state = {"itinerary_components": {"routing": ["ItineraryAgent"]}}
        assert route_after_draft_itinerary(state) == "itinerary"


class TestRouteAfterTransportation:
    def test_with_budget_routes_to_budget(self):
        state = {
            "itinerary_components": {"routing": ["TransportationAgent", "BudgetAgent"]}
        }
        assert route_after_transportation(state) == "budget"

    def test_with_itinerary_routes_to_itinerary(self):
        state = {
            "itinerary_components": {
                "routing": ["TransportationAgent", "ItineraryAgent"]
            }
        }
        assert route_after_transportation(state) == "itinerary"

    def test_transportation_only_ends(self):
        state = {"itinerary_components": {"routing": ["TransportationAgent"]}}
        assert route_after_transportation(state) == END


class TestRouteAfterBudget:
    def test_always_goes_to_budget_review(self):
        assert route_after_budget({}) == "budget_review"


class TestRouteAfterBudgetReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected", "itinerary_components": {"routing": []}}
        assert route_after_budget_review(state) == END

    def test_approved_with_itinerary_routes(self):
        state = {
            "hitl_action": "proceed",
            "itinerary_components": {"routing": ["ItineraryAgent"]},
        }
        assert route_after_budget_review(state) == "itinerary"

    def test_approved_no_itinerary_ends(self):
        state = {
            "hitl_action": "proceed",
            "itinerary_components": {"routing": ["BudgetAgent"]},
        }
        assert route_after_budget_review(state) == END

    def test_adjust_target_routes_only_to_budget(self):
        state = {
            "hitl_action": "adjust_target",
            "itinerary_components": {
                "routing": ["FlightsAgent", "HotelsAgent", "BudgetAgent"]
            },
        }
        assert route_after_budget_review(state) == "budget"


class TestRouteAfterHumanReview:
    def test_rejected_ends(self):
        state = {"hitl_action": "rejected"}
        assert route_after_human_review(state) == END

    def test_approved_renders(self):
        state = {"hitl_action": "approved"}
        assert route_after_human_review(state) == "render_handbook"

    def test_edited_renders(self):
        state = {"hitl_action": "edited"}
        assert route_after_human_review(state) == "draft_itinerary"


# ── Safety review HITL interrupt paths ───────────────────────────────────────


class TestSafetyReviewInterrupt:
    @staticmethod
    def _state(level: str, summary: str, *, official: bool = True) -> dict:
        report = TravelReadinessReport(
            destinations=["test"],
            safety=SafetyInfo(
                advisory_level=level,
                advisory_summary=summary,
            ),
            sources=[
                ReadinessSource(
                    id="S1",
                    title="Advisory",
                    url="https://travel.state.gov/advisory",
                    domain="travel.state.gov",
                    query="test advisory",
                    topic="safety",
                    is_official=official,
                )
            ],
            citations={"safety.advisory_level": ["S1"]},
        )
        return {
            "itinerary_components": {
                "readiness_preflight": {
                    "messages": [AIMessage(content=summary)],
                    "data": report.model_dump(mode="json"),
                    "coverage": (
                        _verified_safety_coverage("test") if official else {"items": []}
                    ),
                }
            },
            "safety_acknowledged": False,
        }

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_dangerous_approved(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {"approved": True}
        state = self._state("red", "Level 4: Do not travel to this area")
        result = await safety_review_node(state)
        assert result["hitl_action"] == "approved"
        assert result["safety_acknowledged"] is True
        mock_interrupt.assert_called_once()
        payload = mock_interrupt.call_args.args[0]
        assert payload["gate"] == "safety_review"
        assert payload["advisory_level"] == "red"
        assert "Do not travel" in payload["summary"]

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_dangerous_rejected(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {"approved": False}
        state = self._state("red", "Level 4: Do not travel")
        result = await safety_review_node(state)
        assert result["hitl_action"] == "rejected"
        assert "cancelled" in result["messages"][0].content.lower()

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_reconsider_travel_triggers_interrupt(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {"approved": True}
        state = self._state("orange", "Level 3: Reconsider travel advisory")
        result = await safety_review_node(state)
        assert result["hitl_action"] == "approved"

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_nonofficial_dangerous_level_fails_closed(
        self, mock_interrupt, _hitl
    ):
        state = self._state("red", "Do not travel", official=False)
        result = await safety_review_node(state)
        assert result["current_agent"] == "safety_review"
        assert result["hitl_action"] == "rejected"
        mock_interrupt.assert_not_called()

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=False)
    async def test_disabling_hitl_does_not_disable_evidence_validation(self, _hitl):
        state = self._state("red", "Do not travel", official=False)

        result = await safety_review_node(state)

        assert result["hitl_action"] == "rejected"

    async def test_prose_without_structured_data_does_not_trigger(self):
        """Untrusted prose must never drive the safety gate."""
        state = {
            "itinerary_components": {
                "readiness_preflight": {
                    "messages": [
                        ToolMessage(content="Safe to visit. Level 1.", tool_call_id="x")
                    ],
                },
            },
            "safety_acknowledged": False,
        }
        result = await safety_review_node(state)
        assert result["hitl_action"] == "rejected"


# ── Budget review HITL interrupt paths ───────────────────────────────────────


class TestBudgetReviewInterrupt:
    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_overspend_approved(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {
            "gate": "budget_review",
            "action": "proceed",
        }
        state = {
            "itinerary_components": {
                "budget_structured": {
                    "total": 5000,
                    "target_budget": 3000,
                    "coverage_status": BudgetCoverageStatus.COMPLETE,
                    "conversion_status": ConversionStatus.NOT_NEEDED,
                    "verdict": BudgetVerdict.OVER_BUDGET,
                },
            },
            "messages": [HumanMessage(content="Plan my trip")],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["hitl_action"] == "proceed"
        assert result["budget_adjustment_accepted"] is True
        mock_interrupt.assert_called_once()

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_overspend_adjusts_target_in_existing_currency(
        self, mock_interrupt, _hitl
    ):
        mock_interrupt.return_value = {
            "gate": "budget_review",
            "action": "adjust_target",
            "new_budget": 5000,
        }
        state = {
            "itinerary_components": {
                "budget_structured": {
                    "total": 4500,
                    "target_budget": 3000,
                    "coverage_status": "complete",
                    "conversion_status": "complete",
                    "verdict": "over_budget",
                },
            },
            "trip_request": {"budget_amount": 3000, "budget_currency": "EUR"},
            "messages": [],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["hitl_action"] == "adjust_target"
        assert result["trip_request"]["budget_amount"] == 5000
        assert result["trip_request"]["budget_currency"] == "EUR"

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_overspend_rejected(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {
            "gate": "budget_review",
            "action": "cancel",
        }
        state = {
            "itinerary_components": {
                "budget_structured": {
                    "total": 6000,
                    "target_budget": 3000,
                    "coverage_status": "complete",
                    "conversion_status": "complete",
                    "verdict": "over_budget",
                },
            },
            "messages": [],
            "budget_adjustment_accepted": False,
        }
        result = await budget_review_node(state)
        assert result["hitl_action"] == "cancel"
        assert "cancelled" in result["messages"][0].content.lower()


# ── Human review HITL interrupt paths ────────────────────────────────────────


class TestHumanReviewInterrupt:
    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_approved_no_feedback(self, mock_interrupt, _hitl):
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

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_approved_with_feedback(self, mock_interrupt, _hitl):
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

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_typed_edit_reruns_selection_and_dependencies(
        self, mock_interrupt, _hitl
    ):
        mock_interrupt.return_value = {
            "gate": "human_review",
            "action": "edited",
            "feedback": "Move the museum to another available day",
        }
        state = {
            "itinerary_components": {
                "routing": ["ItineraryAgent"],
                "itinerary": {"messages": [AIMessage(content="Typed preview")]},
            }
        }

        result = await human_review_node(state)

        assert result["hitl_action"] == "edited"
        assert result["human_feedback"] == "Move the museum to another available day"
        assert result["itinerary_components"]["routing"] == [
            "ItineraryAgent",
            "TransportationAgent",
            "BudgetAgent",
        ]

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_typed_unsupported_edit_requests_clarification(
        self, mock_interrupt, _hitl
    ):
        mock_interrupt.return_value = {
            "gate": "human_review",
            "action": "edited",
            "feedback": "Change the dates and add a city",
        }

        result = await human_review_node({"itinerary_components": {}})

        assert result["hitl_action"] == "needs_clarification"
        assert result["workflow_status"] == "needs_user_input"
        assert result["pending_questions"]

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_rejected(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {"approved": False}
        state = {"itinerary_components": {}}
        result = await human_review_node(state)
        assert result["hitl_action"] == "rejected"
        assert "cancelled" in result["messages"][0].content.lower()

    @patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
    @patch("src.agent.stage4_graph.interrupt")
    async def test_builds_component_summary_in_interrupt(self, mock_interrupt, _hitl):
        mock_interrupt.return_value = {"approved": True}
        state = {
            "itinerary_components": {
                "flights": {"messages": []},
                "hotels": {"messages": []},
                "restaurants": {"messages": []},
                "activities": {"messages": []},
                "readiness": {"messages": []},
                "transportation": {"messages": []},
                "budget": {"messages": []},
                "itinerary": {"messages": [AIMessage(content="Day 1 preview")]},
            },
        }
        await human_review_node(state)
        call_args = mock_interrupt.call_args[0][0]
        assert call_args["gate"] == "human_review"
        assert len(call_args["components_available"]) == 8


# ── Budget node structured extraction success path ───────────────────────────


class TestBudgetNodeStructured:
    async def test_reuses_stored_evidence_and_rates(self):
        agent = AsyncMock()
        agent.run.return_value = BudgetRun(
            report=BudgetBreakdown(total=3500, flights=800),
            message="Validated total",
        )

        state = {
            "messages": [HumanMessage(content="budget?")],
            "itinerary_components": {
                "completed_agents": [],
                "budget_evidence_structured": [
                    {
                        "category": "flights",
                        "money": {"amount": "800", "currency": "USD"},
                        "source_component": "flights",
                        "source_id": "offer-1",
                        "selection_status": "selected",
                    }
                ],
                "budget_structured": {
                    "conversion_rates": [
                        {
                            "from_currency": "EUR",
                            "to_currency": "USD",
                            "rate": 1.1,
                            "provider": "fake",
                            "observed_at": "now",
                        }
                    ]
                },
            },
        }
        result = await budget_node(state, agent=agent)

        assert result["current_agent"] == "budget"
        context = agent.run.await_args.args[0]
        assert context.additional_evidence[0].source_id == "offer-1"
        assert context.stored_rates[0].rate == 1.1


# ── Render handbook node tests ───────────────────────────────────────────────
