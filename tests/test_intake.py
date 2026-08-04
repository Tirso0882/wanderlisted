"""Intake-node regression tests for clarification and multi-turn merging."""

from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from src.agent.nodes.intake import intake_node
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

    assert result["pending_questions"] == ["date_window"]
    clarification = result["messages"][0].content
    assert "exact dates" in clarification
    assert "passport" not in clarification
    assert "depart" not in clarification
    assert "adults" not in clarification

    prompt = "\n".join(
        message.content for message in structured.ainvoke.await_args.args[0]
    )
    assert "plan a city break" in prompt
    assert "Do NOT add flights, hotels" in prompt
