"""Per-message assistant response-language contracts."""

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


def test_response_language_normalization_accepts_iso_codes():
    assert normalize_locale("pl-PL") == "pl"
    assert normalize_locale("en_GB") == "en"
    assert normalize_locale("de-DE") == "de"
    assert normalize_locale("es-ES") == "es"


def test_clear_polish_and_english_are_detected_without_provider_names():
    assert detect_clear_language("Zaplanuj mi podróż do Polski") == "pl"
    assert detect_clear_language("Please plan a two week trip") == "en"
    assert detect_clear_language("WAW MEX 17/10") is None
    assert detect_clear_language("Add only selected services") == "en"
    assert detect_clear_language("Fix this immediately") == "en"


def test_message_language_uses_full_sentence_not_foreign_city_diacritics():
    screenshot_prompt = (
        "Create a 4-day car itinerary for 2 adults and a child starting from "
        "Wrocław. Drive north to the Baltic Sea coast and return efficiently."
    )

    assert detect_clear_language(screenshot_prompt) == "en"
    assert detect_clear_language("what's Travel readiness?") == "en"


def test_spanish_messages_select_spanish_responses():
    assert (
        detect_clear_language(
            "Crea un itinerario de cuatro días en coche para dos adultos y un niño."
        )
        == "es"
    )
    assert detect_clear_language("¿Qué es la preparación para el viaje?") == "es"
    assert detect_clear_language("Hola") == "es"
    assert detect_clear_language("Hi") == "en"


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


async def test_screenshot_english_turn_overrides_polish_conversation_locale():
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="deep")
    prompt = (
        "Create a 4-day car itinerary (August 13-16) for 2 adults and a "
        "15-year-old child starting from Wrocław. We want to drive north "
        "roughly along Poland's western/German border region up to the Baltic "
        "Sea coast, with kid-friendly stops near Szczecin or Lubuskie."
    )

    result = await triage_node(
        {
            "messages": [HumanMessage(content=prompt)],
            "ui_locale": "pl",
            "response_locale": "pl",
            "last_clear_locale": "pl",
        },
        llm=llm,
    )

    assert result["response_locale"] == "en"
    assert result["last_clear_locale"] == "en"


async def test_english_intake_clarification_overrides_polish_ui_locale():
    llm = MagicMock()
    structured = AsyncMock()
    structured.ainvoke.return_value = TripRequestPatch(
        scope=RequestScope.FULL_ITINERARY,
    )
    llm.with_structured_output.return_value = structured

    result = await intake_node(
        {
            "messages": [
                HumanMessage(
                    content="Create a family road trip from Wrocław to the Baltic coast."
                )
            ],
            "trip_request": {},
            "ui_locale": "pl",
        },
        llm=llm,
    )

    assert result["response_locale"] == "en"
    assert result["messages"][0].content.startswith(
        "Before I start searching, I still need:"
    )


async def test_spanish_intake_clarification_uses_spanish():
    llm = MagicMock()
    structured = AsyncMock()
    structured.ainvoke.return_value = TripRequestPatch(
        scope=RequestScope.FULL_ITINERARY,
    )
    llm.with_structured_output.return_value = structured

    result = await intake_node(
        {
            "messages": [
                HumanMessage(
                    content="Crea un itinerario familiar de cuatro días en coche."
                )
            ],
            "trip_request": {},
            "ui_locale": "en",
        },
        llm=llm,
    )

    assert result["response_locale"] == "es"
    assert result["messages"][0].content.startswith(
        "Antes de empezar la búsqueda, todavía necesito:"
    )


async def test_typed_scope_control_does_not_switch_english_conversation_to_polish():
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="deep")

    result = await triage_node(
        {
            "messages": [HumanMessage(content="Uwzględnij wszystkie usługi.")],
            "service_scope_decision": {
                "action": "include_all",
                "request_fingerprint": "scope-fingerprint",
            },
            "ui_locale": "pl",
            "response_locale": "en",
            "last_clear_locale": "en",
        },
        llm=llm,
    )

    assert result["response_locale"] == "en"
    assert result["last_clear_locale"] == "en"


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


def test_model_context_supports_spanish_beyond_ui_locale_catalogs():
    messages = build_context_messages(
        {
            "messages": [HumanMessage(content="¿Qué es la preparación para el viaje?")],
            "itinerary_components": {},
            "response_locale": "es",
        }
    )

    assert isinstance(messages[0], SystemMessage)
    assert "Spanish (es-ES)" in messages[0].content


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
