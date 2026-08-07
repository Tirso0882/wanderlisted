"""Intake-node regression tests for clarification and multi-turn merging."""

from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.agent.nodes.intake import intake_node
from src.agent.stage4_graph import route_after_intake
from src.agent.state import TravelAgentState
from src.models import (
    DateWindowPatch,
    RequestScope,
    RequestedCapability,
    TravelerPartyPatch,
    TripRequestPatch,
)


def _mock_llm(patch):
    llm = MagicMock()
    structured = AsyncMock()
    structured.ainvoke.return_value = patch
    llm.with_structured_output.return_value = structured
    return llm, structured


def test_intake_tool_schema_uses_provider_supported_decimal_number():
    schema = convert_to_openai_tool(TripRequestPatch)["function"]["parameters"]
    amount = schema["properties"]["known_costs"]["anyOf"][0]["items"]["properties"][
        "money"
    ]["properties"]["amount"]

    assert amount["type"] == "number"
    assert amount["minimum"] == 0.0
    assert "pattern" not in amount


async def test_polish_request_stops_before_fanout_for_required_fields():
    llm, _ = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            locale="pl",
            origin_country="Kolumbia",
            destinations=["krakow", "warszawa", "wroclaw"],
            requested_capabilities=list(RequestedCapability),
            date_window=DateWindowPatch(
                earliest_start="2026-08-20",
                latest_end="2026-09-20",
                duration_days=14,
                flexible=True,
            ),
        )
    )
    state = {
        "messages": [HumanMessage(content="Zorganizuj mi 14 dni w Polsce")],
        "trip_request": {},
    }

    result = await intake_node(state, llm=llm)

    assert result["workflow_status"] == "needs_user_input"
    assert result["pending_questions"] == [
        "passport_country",
        "origin_city",
        "adults",
    ]
    assert "paszport" in result["messages"][0].content
    assert "Z jakiego miasta" in result["messages"][0].content
    assert "Ile osób dorosłych" in result["messages"][0].content


async def test_short_answer_merges_pending_request_and_becomes_ready():
    first_llm, _ = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            locale="pl",
            origin_country="Kolumbia",
            destinations=["krakow", "warszawa", "wroclaw"],
            requested_capabilities=list(RequestedCapability),
            date_window=DateWindowPatch(
                earliest_start="2026-08-20",
                latest_end="2026-09-20",
                duration_days=14,
                flexible=True,
            ),
        )
    )
    first = await intake_node(
        {"messages": [HumanMessage(content="Podróż po Polsce")], "trip_request": {}},
        llm=first_llm,
    )

    second_llm, structured = _mock_llm(
        TripRequestPatch(
            locale="pl",
            passport_country="Kolumbia",
            origin_city="Bogota",
            travelers=TravelerPartyPatch(adults=1),
        )
    )
    second = await intake_node(
        {
            "messages": [
                HumanMessage(
                    content="Bogota, paszport kolumbijski, jedna dorosła osoba"
                )
            ],
            "trip_request": first["trip_request"],
            "request_revision": first["request_revision"],
            "pending_questions": first["pending_questions"],
        },
        llm=second_llm,
    )

    assert second["workflow_status"] == "ready"
    assert second["pending_questions"] == []
    assert "messages" not in second
    assert second["trip_request"]["origin_city"] == "Bogota"
    assert second["trip_request"]["travelers"]["adults"] == 1
    assert second["trip_request"]["date_window"]["duration_days"] == 14
    prompt = "\n".join(
        message.content for message in structured.ainvoke.await_args.args[0]
    )
    assert "Current canonical request" in prompt
    assert '"duration_days": 14' in prompt


async def test_extraction_failure_returns_recoverable_question():
    llm = MagicMock()
    structured = AsyncMock()
    structured.ainvoke.side_effect = ValueError("invalid structured response")
    llm.with_structured_output.return_value = structured

    result = await intake_node(
        {"messages": [HumanMessage(content="Plan something")], "trip_request": {}},
        llm=llm,
    )

    assert result["workflow_status"] == "needs_user_input"
    assert result["pending_questions"] == ["request_details"]
    assert "could not understand" in result["messages"][0].content.lower()


async def test_first_ambiguous_turn_uses_selected_polish_ui_for_clarification():
    llm, _ = _mock_llm(TripRequestPatch())

    result = await intake_node(
        {
            "messages": [HumanMessage(content="OK")],
            "trip_request": {},
            "ui_locale": "pl",
            "response_locale": "pl",
        },
        llm=llm,
    )

    assert result["trip_request"]["locale"] == "en"
    assert "Zanim rozpocznę" in result["messages"][0].content


async def test_city_break_asks_only_for_ambiguous_dates_not_booking_details():
    llm, structured = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            destinations=["wroclaw"],
            date_window=DateWindowPatch(exact_start="2026-10-08"),
        )
    )

    result = await intake_node(
        {
            "messages": [
                HumanMessage(
                    content="Plan a city break in Wroclaw this weekend 8 October"
                )
            ],
            "trip_request": {},
        },
        llm=llm,
    )

    assert result["pending_questions"] == [
        "service_scope_confirmation",
        "date_window",
    ]
    clarification = result["messages"][0].content
    assert "flights" in clarification
    assert "hotels" in clarification
    assert "exact dates" in clarification
    assert "passport" not in clarification
    assert "depart" not in clarification
    assert "adults" not in clarification

    prompt = "\n".join(
        message.content for message in structured.ainvoke.await_args.args[0]
    )
    assert "plan a city break" in prompt
    assert "Do NOT add flights, hotels" in prompt


async def test_named_services_are_offered_remaining_scope_before_fanout():
    llm, _ = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FOCUSED,
            destinations=["tokyo"],
            requested_capabilities=[
                RequestedCapability.FLIGHTS,
                RequestedCapability.HOTELS,
            ],
            origin_city="wroclaw",
            date_window=DateWindowPatch(
                exact_start="2026-10-08",
                exact_end="2026-10-10",
            ),
            travelers=TravelerPartyPatch(adults=2),
        )
    )

    result = await intake_node(
        {
            "messages": [HumanMessage(content="Find flights and hotels in Tokyo")],
            "trip_request": {},
        },
        llm=llm,
    )

    assert result["workflow_status"] == "needs_user_input"
    assert result["pending_questions"] == ["service_scope_confirmation"]
    assert result["service_scope_offer"]["selected_capabilities"] == [
        "flights",
        "hotels",
    ]
    assert "restaurants" in result["service_scope_offer"]["offered_capabilities"]
    assert "activities" in result["messages"][0].content


async def test_explicit_only_services_skip_scope_offer():
    llm, _ = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FOCUSED,
            destinations=["tokyo"],
            requested_capabilities=[
                RequestedCapability.FLIGHTS,
                RequestedCapability.HOTELS,
            ],
            declined_capabilities=[
                RequestedCapability.TRAVEL_READINESS,
                RequestedCapability.RESTAURANTS,
                RequestedCapability.ACTIVITIES,
                RequestedCapability.TRANSPORTATION,
                RequestedCapability.BUDGET,
                RequestedCapability.ITINERARY,
            ],
            capability_scope_confirmed=True,
            capability_scope_exclusive=True,
            origin_city="wroclaw",
            date_window=DateWindowPatch(
                exact_start="2026-10-08",
                exact_end="2026-10-10",
            ),
            travelers=TravelerPartyPatch(adults=2),
        )
    )

    result = await intake_node(
        {
            "messages": [
                HumanMessage(content="Only flights and hotels in Tokyo, nothing else")
            ],
            "trip_request": {},
        },
        llm=llm,
    )

    assert result["workflow_status"] == "ready"
    assert result["pending_questions"] == []
    assert result["service_scope_offer"] == {}


async def test_typed_scope_decision_is_applied_without_llm_call():
    first_llm, _ = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FOCUSED,
            destinations=["tokyo"],
            requested_capabilities=[RequestedCapability.HOTELS],
            origin_city="wroclaw",
            date_window=DateWindowPatch(
                exact_start="2026-10-08",
                exact_end="2026-10-10",
            ),
            travelers=TravelerPartyPatch(adults=2),
        )
    )
    first = await intake_node(
        {
            "messages": [HumanMessage(content="Find a hotel in Tokyo")],
            "trip_request": {},
        },
        llm=first_llm,
    )

    second_llm, structured = _mock_llm(TripRequestPatch())
    second = await intake_node(
        {
            "messages": [HumanMessage(content="Uwzględnij wszystkie usługi.")],
            "trip_request": first["trip_request"],
            "response_locale": "en",
            "last_clear_locale": "en",
            "ui_locale": "pl",
            "service_scope_decision": {
                "action": "include_all",
                "request_fingerprint": first["service_scope_offer"][
                    "request_fingerprint"
                ],
            },
        },
        llm=second_llm,
    )

    assert second["workflow_status"] == "ready"
    assert second["response_locale"] == "en"
    assert second["last_clear_locale"] == "en"
    assert second["service_scope_offer"] == {}
    assert second["trip_request"]["capability_scope_confirmed"] is True
    assert second["trip_request"]["capability_scope_exclusive"] is True
    assert set(second["trip_request"]["requested_capabilities"]) == {
        capability.value for capability in RequestedCapability
    }
    structured.ainvoke.assert_not_awaited()


async def test_free_text_current_scope_reply_converges_without_repeating_offer():
    llm, structured = _mock_llm(TripRequestPatch())
    state = {
        "messages": [HumanMessage(content="Continue with the current scope only")],
        "trip_request": {
            "scope": "full_itinerary",
            "destinations": ["tokyo"],
            "requested_capabilities": [
                "flights",
                "hotels",
                "restaurants",
                "activities",
                "transportation",
                "budget",
                "itinerary",
            ],
            "date_window": {
                "exact_start": "2026-10-08",
                "exact_end": "2026-10-10",
            },
            "travelers": {"adults": 2},
            "origin_city": "warsaw",
        },
        "pending_questions": ["service_scope_confirmation"],
        "request_revision": 1,
    }

    result = await intake_node(state, llm=llm)

    assert result["workflow_status"] == "ready"
    assert result["pending_questions"] == []
    assert result["service_scope_offer"] == {}
    assert result["request_revision"] == 2
    assert result["trip_request"]["capability_scope_confirmed"] is True
    assert result["trip_request"]["declined_capabilities"] == ["travel_readiness"]
    assert "messages" not in result
    structured.ainvoke.assert_not_awaited()


async def test_scope_choice_and_other_missing_details_merge_in_one_turn():
    llm, structured = _mock_llm(
        TripRequestPatch(
            date_window=DateWindowPatch(
                exact_start="2026-10-08",
                exact_end="2026-10-10",
            ),
            requested_capabilities=[RequestedCapability.TRAVEL_READINESS],
        )
    )
    state = {
        "messages": [
            HumanMessage(content="No thanks. Travel dates are October 8 to 10, 2026.")
        ],
        "trip_request": {
            "scope": "full_itinerary",
            "destinations": ["tokyo"],
            "requested_capabilities": [
                "flights",
                "hotels",
                "restaurants",
                "activities",
                "transportation",
                "budget",
                "itinerary",
            ],
            "travelers": {"adults": 2},
            "origin_city": "warsaw",
        },
        "pending_questions": ["service_scope_confirmation", "date_window"],
    }

    result = await intake_node(state, llm=llm)

    assert result["workflow_status"] == "ready"
    assert result["pending_questions"] == []
    assert result["trip_request"]["date_window"]["exact_start"] == "2026-10-08"
    assert result["trip_request"]["declined_capabilities"] == ["travel_readiness"]
    assert "travel_readiness" not in result["trip_request"]["requested_capabilities"]
    structured.ainvoke.assert_awaited_once()


async def test_checkpointed_scope_reply_reaches_supervisor_on_the_next_turn():
    llm, structured = _mock_llm(
        TripRequestPatch(
            scope=RequestScope.FULL_ITINERARY,
            destinations=["tokyo"],
            requested_capabilities=[
                "flights",
                "hotels",
                "restaurants",
                "activities",
                "transportation",
                "budget",
                "itinerary",
            ],
            origin_city="warsaw",
            date_window=DateWindowPatch(
                exact_start="2026-10-08",
                exact_end="2026-10-10",
            ),
            travelers=TravelerPartyPatch(adults=2),
        )
    )

    async def supervisor_reached(_state: TravelAgentState) -> dict:
        return {"current_agent": "supervisor:reached"}

    async def run_intake(state: TravelAgentState) -> dict:
        return await intake_node(state, llm=llm)

    builder = StateGraph(TravelAgentState)
    builder.add_node("intake", run_intake)
    builder.add_node("supervisor", supervisor_reached)
    builder.add_edge(START, "intake")
    builder.add_conditional_edges(
        "intake",
        route_after_intake,
        {"supervisor": "supervisor", END: END},
    )
    builder.add_edge("supervisor", END)
    checkpointed_graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "scope-convergence"}}

    first = await checkpointed_graph.ainvoke(
        {"messages": [HumanMessage(content="Plan my Tokyo trip")]},
        config,
    )
    second = await checkpointed_graph.ainvoke(
        {"messages": [HumanMessage(content="Continue with the current scope only")]},
        config,
    )

    assert first["pending_questions"] == ["service_scope_confirmation"]
    assert second["pending_questions"] == []
    assert second["current_agent"] == "supervisor:reached"
    assert structured.ainvoke.await_count == 1


async def test_explicit_route_delegation_resolves_recommendation_loop():
    llm, structured = _mock_llm(
        TripRequestPatch(
            overnight_cities=["zielona gora", "szczecin", "pobierowo"],
            route_scope_delegated=True,
        )
    )
    current_request = {
        "scope": "full_itinerary",
        "locale": "en",
        "origin_city": "wroclaw",
        "route_goal": "north along the german border to the baltic coast",
        "route_waypoints": ["szczecin", "lubuskie region"],
        "requested_capabilities": [
            "restaurants",
            "activities",
            "transportation",
            "budget",
            "itinerary",
        ],
        "declined_capabilities": ["flights", "hotels", "travel_readiness"],
        "capability_scope_confirmed": True,
        "capability_scope_exclusive": True,
        "primary_transport_mode": "drive",
        "date_window": {
            "exact_start": "2026-08-13",
            "exact_end": "2026-08-16",
        },
        "travelers": {"adults": 2, "children": 1, "child_ages": [15]},
        "budget_amount": 3000,
        "budget_currency": "PLN",
        "minimum_beach_days": 1,
    }

    result = await intake_node(
        {
            "messages": [
                HumanMessage(content="We don't know, what would you recommend to us?")
            ],
            "trip_request": current_request,
            "pending_questions": ["route_scope_confirmation"],
            "response_locale": "en",
            "last_clear_locale": "en",
            "request_revision": 2,
        },
        llm=llm,
    )

    assert result["workflow_status"] == "ready"
    assert result["pending_questions"] == []
    assert "messages" not in result
    assert result["trip_request"]["route_scope_delegated"] is True
    assert result["trip_request"]["route_scope_confirmed"] is False
    assert result["trip_request"]["overnight_cities"] == [
        "zielona gora",
        "szczecin",
        "pobierowo",
    ]
    assert result["trip_request"]["destinations"] == [
        "zielona gora",
        "szczecin",
        "pobierowo",
    ]
    prompt = "\n".join(
        message.content for message in structured.ainvoke.await_args.args[0]
    )
    assert "route-scope delegation" in prompt
    assert "north along the german border" in prompt
