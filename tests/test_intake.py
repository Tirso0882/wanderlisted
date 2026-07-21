"""Intake-node regression tests for clarification and multi-turn merging."""

from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import HumanMessage

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


async def test_polish_request_stops_before_fanout_for_two_missing_fields():
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
    assert result["pending_questions"] == ["origin_city", "adults"]
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
            origin_city="Bogota",
            travelers=TravelerPartyPatch(adults=1),
        )
    )
    second = await intake_node(
        {
            "messages": [HumanMessage(content="Bogota, jedna dorosła osoba")],
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
