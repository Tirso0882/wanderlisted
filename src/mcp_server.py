"""
Wanderlisted MCP Server
========================
Exposes Wanderlisted's travel tools as an MCP server so external AI agents
(Claude Desktop, Cursor, VS Code Copilot, etc.) can use them.

Run:
    python -m src.mcp_server

Or with uvx (for Claude Desktop / Cursor config):
    uvx mcp run src/mcp_server.py

Architecture:
    External Agent (Claude, Cursor, etc.)
        │
        ├── MCP protocol (JSON-RPC over stdio)
        │
        ▼
    This MCP Server
        │
        ├── src/tools/flights.py       → Amadeus API
        ├── src/tools/hotels.py        → Amadeus API
        ├── src/tools/weather.py       → OpenWeatherMap API
        ├── src/tools/budget.py        → Local calculation
        ├── src/tools/destination_rag.py → Pinecone RAG
        ├── src/tools/google_maps.py   → Google Maps Platform
        ├── src/tools/web_search.py    → Tavily API
        ├── src/tools/safety.py        → REST Countries API
        ├── src/tools/currency.py      → ExchangeRate API
        └── src/tools/iata.py          → Local CSV lookup

Note: Your LangGraph agents STILL use @tool directly (no MCP overhead).
      This server is ONLY for external consumers.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import run_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

# -- Import your existing Wanderlisted tools ---------------------------------
from src.tools.flights import search_flights
from src.tools.hotels import search_hotels
from src.tools.weather import get_weather
from src.tools.budget import calculate_budget
from src.tools.destination_rag import search_destination_guides
from src.tools.google_maps import (
    get_directions,
    get_distance_matrix,
    get_timezone,
    optimize_day_route,
    search_places_nearby,
    search_places_text,
)
from src.tools.web_search import search_hidden_gems, search_web
from src.tools.safety import get_safety_info
from src.tools.currency import convert_currency
from src.tools.iata import lookup_iata_code

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("wanderlisted-travel")

# Registry: MCP tool name → (callable, is_async)
# This is the single source of truth — add new tools here.
_TOOL_REGISTRY: dict[str, tuple[Any, bool]] = {
    "search_flights": (search_flights, True),
    "search_hotels": (search_hotels, True),
    "get_weather": (get_weather, True),
    "calculate_budget": (calculate_budget, False),
    "search_destination_guides": (search_destination_guides, False),
    "search_places_nearby": (search_places_nearby, False),
    "search_places_text": (search_places_text, False),
    "get_directions": (get_directions, False),
    "get_distance_matrix": (get_distance_matrix, False),
    "get_timezone": (get_timezone, False),
    "optimize_day_route": (optimize_day_route, False),
    "search_web": (search_web, True),
    "search_hidden_gems": (search_hidden_gems, True),
    "get_safety_info": (get_safety_info, True),
    "convert_currency": (convert_currency, True),
    "lookup_iata_code": (lookup_iata_code, False),
}


# ---------------------------------------------------------------------------
# MCP: list_tools — agents call this to discover what we offer
# ---------------------------------------------------------------------------
@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all available Wanderlisted tools with schemas.

    Each LangChain @tool already has a name, description, and args_schema
    (auto-generated from the function signature + docstring). We convert
    those to MCP Tool objects.
    """
    tools: list[Tool] = []
    for name, (tool_fn, _) in _TOOL_REGISTRY.items():
        # LangChain @tool exposes .name, .description, .args_schema
        schema = tool_fn.args_schema.model_json_schema() if tool_fn.args_schema else {}
        tools.append(
            Tool(
                name=name,
                description=tool_fn.description or "",
                inputSchema=schema,
            )
        )
    return tools


# ---------------------------------------------------------------------------
# MCP: call_tool — agents call this to execute a tool
# ---------------------------------------------------------------------------
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a Wanderlisted tool and return the result."""
    entry = _TOOL_REGISTRY.get(name)
    if entry is None:
        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

    tool_fn, is_async = entry

    try:
        # LangChain tools accept arguments via .ainvoke() / .invoke()
        if is_async:
            result = await tool_fn.ainvoke(arguments)
        else:
            result = await asyncio.to_thread(tool_fn.invoke, arguments)

        # Ensure result is a string
        if not isinstance(result, str):
            result = json.dumps(result, default=str)

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error calling {name}: {e}")]


# ---------------------------------------------------------------------------
# MCP: list_resources — expose contextual travel data
# ---------------------------------------------------------------------------
@server.list_resources()
async def list_resources() -> list[Resource]:
    """Expose curated destination knowledge as browsable resources.

    This is what makes MCP more than a REST wrapper — agents can browse
    these resources to get context BEFORE making tool calls.
    """
    return [
        Resource(
            uri="wanderlisted://guides/destinations",
            name="Available Destination Guides",
            description=(
                "List of all curated travel guides in the knowledge base. "
                "Covers culture, food, transport, safety, hidden gems. "
                "Use search_destination_guides to query specific topics."
            ),
            mimeType="text/plain",
        ),
        Resource(
            uri="wanderlisted://tools/quick-reference",
            name="Tool Usage Quick Reference",
            description=(
                "How to use Wanderlisted tools effectively: which tools to "
                "call first, recommended workflows, and tips for getting "
                "the best results."
            ),
            mimeType="text/plain",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Return resource content by URI."""
    if uri == "wanderlisted://guides/destinations":
        return _get_destination_list()
    elif uri == "wanderlisted://tools/quick-reference":
        return _get_tool_reference()
    raise ValueError(f"Unknown resource: {uri}")


# ---------------------------------------------------------------------------
# Resource content helpers
# ---------------------------------------------------------------------------
def _get_destination_list() -> str:
    """List available destination guides from the knowledge base."""
    from pathlib import Path

    guides_dir = Path("knowledge_base/destination_guides")
    if not guides_dir.exists():
        return "No destination guides found."

    guides = sorted(p.stem for p in guides_dir.glob("*.md"))
    return (
        "Available destination guides:\n"
        + "\n".join(f"  - {g}" for g in guides)
        + "\n\nUse search_destination_guides(query, destinations=[slug]) "
        "to search within a specific guide."
    )


def _get_tool_reference() -> str:
    return """Wanderlisted Tool Usage Guide
=============================

RECOMMENDED WORKFLOW for trip planning:
1. lookup_iata_code("Tokyo") → get IATA code (e.g., "NRT")
2. search_flights(origin, destination, date) → flight options with pricing
3. search_hotels(city_code, check_in, check_out) → hotel options with pricing
4. search_destination_guides(query, destinations=["tokyo"]) → cultural tips, local knowledge
5. search_places_nearby(location, "restaurant") → nearby dining options
6. search_places_text("best ramen in Shinjuku") → specific place search
7. get_weather("Tokyo") → 5-day forecast
8. get_safety_info("Japan") → safety, visa, health info
9. calculate_budget(region, style, days, travelers, flight_cost, hotel_cost) → cost breakdown
10. convert_currency("USD", "JPY", 1000) → exchange rates
11. get_directions(origin, destination) → transit/driving directions
12. optimize_day_route(stops, start) → efficient stop ordering

TIPS:
- Always call lookup_iata_code BEFORE search_flights or search_hotels
- Always call search_destination_guides BEFORE search_web (guides are higher quality)
- search_web is best for CURRENT info: events, new restaurants, advisories
- search_hidden_gems finds off-the-beaten-path spots locals recommend
- calculate_budget works best AFTER you have flight and hotel prices
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    await run_server(server)


if __name__ == "__main__":
    asyncio.run(main())
