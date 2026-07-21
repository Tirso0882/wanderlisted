from typing import Annotated, Any

from langgraph.graph import MessagesState


def _merge_components(existing: dict, update: dict) -> dict:
    """Shallow-merge two itinerary_components dicts.

    Used as a reducer so parallel Send() workers can each write their own key
    (e.g. ``{"flights": result}``) without overwriting each other's results.
    Sequential nodes that spread ``{**components, "key": value}`` continue to
    work unchanged — the reducer just merges their full copy back in.
    """
    merged = dict(existing)
    merged.update(update)
    return merged


def _last_value(existing: Any, new: Any) -> Any:
    """Reducer: accept the last written value (enables parallel writes)."""
    return new


class TravelAgentState(MessagesState):
    """State for the travel agent. Extends MessagesState with session tracking."""

    session_id: str = ""
    current_agent: Annotated[str, _last_value] = "supervisor"
    itinerary_components: Annotated[
        dict[str, Any], _merge_components
    ] = {}  # Accumulated results; merge reducer enables parallel Send() fan-out

    # Canonical conversational request and workflow lifecycle.
    trip_request: Annotated[dict[str, Any], _last_value] = {}
    workflow_status: Annotated[str, _last_value] = "new"
    pending_questions: Annotated[list[str], _last_value] = []
    request_revision: Annotated[int, _last_value] = 0
    start_date: Annotated[str, _last_value] = ""
    end_date: Annotated[str, _last_value] = ""

    # Machine-readable outcomes are separate from agent conversation transcripts.
    component_results: Annotated[dict[str, Any], _merge_components] = {}

    # Per-stay hotel fan-out uses unique keys, then aggregates into `hotels`.
    hotel_search_results: Annotated[dict[str, Any], _merge_components] = {}
    active_hotel_stay: Annotated[dict[str, Any], _last_value] = {}

    # Confirmed destination cities — used to scope RAG metadata filtering
    destinations: list[str] = []

    # User profiling — passed to every subagent for personalized results
    travel_style: str = ""  # e.g. "budget", "mid-range", "luxury"
    group_type: str = ""  # e.g. "solo", "couple", "family", "friends"
    accessibility_needs: list[str] = []  # e.g. ["wheelchair", "limited mobility"]
    dietary_restrictions: list[str] = []  # e.g. ["vegetarian", "halal", "gluten-free"]

    # Handbook output paths (populated by render_handbook node)
    handbook_paths: dict[str, str] = {}  # {"html": "outputs/handbook.html", ...}

    # Single-agent isolation: when set, bypass triage/supervisor
    # and route directly to this agent only
    target_agent: str = ""  # e.g. "FlightsAgent", "HotelsAgent"

    # HITL (Human-in-the-Loop) — Phase 4
    human_feedback: str = ""  # Free-text feedback from user
    hitl_action: str = ""  # Last HITL action: "approved", "rejected", "edited"
    safety_acknowledged: bool = False  # User acknowledged safety advisory
    budget_adjustment_accepted: bool = False  # User accepted budget adjustment
