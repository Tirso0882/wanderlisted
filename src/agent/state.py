from typing import Any

from langgraph.graph import MessagesState


class TravelAgentState(MessagesState):
    """State for the travel agent. Extends MessagesState with session tracking."""

    session_id: str = ""
    current_agent: str = "supervisor"  # Track which agent is active
    itinerary_components: dict[str, Any] = {}  # Accumulated results (flights, hotels, etc.)

    # Confirmed destination cities — used to scope RAG metadata filtering
    destinations: list[str] = []

    # User profiling — passed to every subagent for personalized results
    travel_style: str = ""          # e.g. "budget", "mid-range", "luxury"
    group_type: str = ""            # e.g. "solo", "couple", "family", "friends"
    accessibility_needs: list[str] = []  # e.g. ["wheelchair", "limited mobility"]
    dietary_restrictions: list[str] = []  # e.g. ["vegetarian", "halal", "gluten-free"]

    # Handbook output paths (populated by render_handbook node)
    handbook_paths: dict[str, str] = {}  # {"html": "outputs/handbook.html", ...}
