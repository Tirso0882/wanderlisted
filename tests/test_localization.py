"""English/Polish conversation-language contracts."""

from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.localization import (
    detect_clear_language,
    normalize_locale,
    resolve_response_locale,
)
from src.agent.nodes.intake import intake_node
from src.agent.stage4_graph import build_context_messages, triage_node
from src.models import RequestScope, TripRequestPatch


def test_locale_normalization_is_bounded_to_v1_languages():
    assert normalize_locale("pl-PL") == "pl"
    assert normalize_locale("en_GB") == "en"
    assert normalize_locale("de-DE") == "en"


def test_clear_polish_and_english_are_detected_without_provider_names():
    assert detect_clear_language("Zaplanuj mi podróż do Polski") == "pl"
    assert detect_clear_language("Please plan a two week trip") == "en"
    assert detect_clear_language("WAW MEX 17/10") is None


def test_ambiguous_turn_retains_last_clear_language_then_ui_locale():
    retained = resolve_response_locale("OK", ui_locale="en", last_clear_locale="pl")
    first_turn = resolve_response_locale("OK", ui_locale="pl", last_clear_locale=None)

    assert retained.locale == "pl"
    assert retained.clear_locale is None
    assert first_turn.locale == "pl"


def test_clear_turn_can_switch_conversation_language_and_ambiguous_turn_retains_it():
    polish = resolve_response_locale(
        "Zaplanuj mi podróż do Polski", ui_locale="en", last_clear_locale=None
    )
    english = resolve_response_locale(
        "Please plan a two week trip", ui_locale="pl", last_clear_locale=polish.locale
    )
    retained = resolve_response_locale(
        "OK", ui_locale="pl", last_clear_locale=english.clear_locale
    )

    assert polish.clear_locale == "pl"
    assert english.clear_locale == "en"
    assert retained.locale == "en"


async def test_triage_persists_resolved_locale_before_user_facing_nodes():
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="shallow")

    result = await triage_node(
        {
            "messages": [HumanMessage(content="OK")],
            "ui_locale": "en",
            "last_clear_locale": "pl",
        },
        llm=llm,
    )

    assert result["response_locale"] == "pl"
    assert result["last_clear_locale"] == "pl"


def test_model_context_contains_canonical_polish_response_contract():
    messages = build_context_messages(
        {
            "messages": [HumanMessage(content="OK")],
            "itinerary_components": {},
            "response_locale": "pl",
        }
    )

    assert isinstance(messages[0], SystemMessage)
    assert "Polish (pl-PL)" in messages[0].content
    assert "provider names" in messages[0].content


async def test_ambiguous_intake_does_not_overwrite_trip_request_locale():
    llm = MagicMock()
    structured = AsyncMock()
    structured.ainvoke.return_value = TripRequestPatch(
        scope=RequestScope.REFINEMENT,
        locale="en",
    )
    llm.with_structured_output.return_value = structured

    result = await intake_node(
        {
            "messages": [HumanMessage(content="OK")],
            "trip_request": {
                "scope": "refinement",
                "locale": "pl",
            },
            "request_revision": 1,
            "response_locale": "pl",
            "last_clear_locale": "pl",
        },
        llm=llm,
    )

    assert result["trip_request"]["locale"] == "pl"
    assert result["response_locale"] == "pl"
