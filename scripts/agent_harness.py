#!/usr/bin/env python3
"""Agent Test Harness — run any specialist agent in isolation and produce HTML reports.

Usage:
    # Run all agents:
    python scripts/agent_harness.py

    # Run specific agents:
    python scripts/agent_harness.py --agents flights hotels

    # Custom prompt:
    python scripts/agent_harness.py --agents destination --prompt "Research safety in Colombia"

    # Custom destination/dates:
    python scripts/agent_harness.py --agents flights --dest "Paris" --origin "LAX" --dates "2026-06-01 to 2026-06-08"

    # List available agents:
    python scripts/agent_harness.py --list

    # Auto-open HTML report in browser:
    python scripts/agent_harness.py --open
"""

import argparse
import asyncio
import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src.agent.agents import (
    ActivitiesAgent,
    BudgetAgent,
    DestinationAgent,
    FlightsAgent,
    HotelsAgent,
    ItineraryAgent,
    RestaurantsAgent,
    SpecializedAgent,
    TransportationAgent,
)
from src.agent.llm import get_llm

# ── Agent registry ────────────────────────────────────────────────────────
# Maps CLI name → (AgentClass, LLM tier).  Add new agents here.
AGENT_REGISTRY: dict[str, tuple[type[SpecializedAgent], str]] = {
    "flights": (FlightsAgent, "fast"),
    "hotels": (HotelsAgent, "fast"),
    "destination": (DestinationAgent, "reasoning"),
    "restaurants": (RestaurantsAgent, "fast"),
    "activities": (ActivitiesAgent, "fast"),
    "transportation": (TransportationAgent, "fast"),
    "budget": (BudgetAgent, "fast"),
    "itinerary": (ItineraryAgent, "reasoning"),
}

OUTPUT_DIR = Path("outputs/agent_reports")


# ── Extraction helper ─────────────────────────────────────────────────────

def _extract_text(content: Any) -> str:
    """Extract text from Chat Completions (str) or Responses API (list) content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    parts.append(text)
        return " ".join(parts)
    return str(content or "")


# ── Default test prompts per agent ────────────────────────────────────────

def _default_prompt(agent_name: str, dest: str, origin: str, dates: str) -> str:
    """Return a sensible test prompt for each agent type."""
    prompts = {
        "flights": (
            f"Find the best flight options from {origin} to {dest} for {dates}. "
            "A couple traveling, mid-range budget around $3000."
        ),
        "hotels": (
            f"Find hotels in {dest} for {dates}. "
            "Mid-range budget, couple, prefer central location."
        ),
        "destination": (
            f"Research {dest} as a travel destination. "
            "Cover culture, safety, weather, local tips, and hidden gems."
        ),
        "restaurants": (
            f"Find the best restaurants in {dest}. "
            "Mix of local cuisine and fine dining, mid-range to upscale."
        ),
        "activities": (
            f"Find top attractions and experiences in {dest}. "
            "Include cultural sites, outdoor activities, and unique experiences."
        ),
        "transportation": (
            f"Plan local transportation in {dest}. "
            "Cover getting from airport, public transit, and day-trip routes."
        ),
        "budget": (
            f"Calculate a detailed budget for a 7-day trip to {dest} for 2 people. "
            "Mid-range travel style, include flights ($800pp), hotels, food, activities."
        ),
        "itinerary": (
            f"Create a day-by-day itinerary for 5 days in {dest}. "
            "Balance sightseeing, food, rest. Optimize routes to minimize travel time."
        ),
    }
    return prompts.get(agent_name, f"Help me plan a trip to {dest}.")


# ── Core harness ──────────────────────────────────────────────────────────


async def run_agent_harness(
    agent_name: str,
    *,
    prompt: str | None = None,
    dest: str = "Tokyo",
    origin: str = "JFK",
    dates: str = "2026-07-10 to 2026-07-17",
) -> dict[str, Any]:
    """Run a single agent in isolation and capture all messages + timing.

    Returns a dict with:
        agent_name, tier, tools, system_prompt, prompt,
        messages (list of dicts), tool_calls (list of dicts),
        final_output, elapsed_s, error
    """
    if agent_name not in AGENT_REGISTRY:
        return {"agent_name": agent_name, "error": f"Unknown agent: {agent_name}"}

    cls, tier = AGENT_REGISTRY[agent_name]
    prompt = prompt or _default_prompt(agent_name, dest, origin, dates)

    result: dict[str, Any] = {
        "agent_name": agent_name,
        "tier": tier,
        "tools": [],
        "system_prompt": "",
        "prompt": prompt,
        "messages": [],
        "tool_calls": [],
        "final_output": "",
        "elapsed_s": 0.0,
        "error": None,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        llm = get_llm(tier=tier)
        agent = cls(llm)
        result["tools"] = [t.name for t in agent.tools]
        result["system_prompt"] = agent.system_prompt

        executor = create_agent(
            model=llm,
            tools=agent.tools,
            system_prompt=agent.system_prompt,
        )

        profile = SystemMessage(
            content=(
                "USER PROFILE:\n"
                f"Destinations: {dest}\n"
                "Travel style: mid-range\n"
                "Group type: couple"
            )
        )
        user_msg = HumanMessage(content=prompt)

        t0 = time.perf_counter()
        run_result = await executor.ainvoke({"messages": [profile, user_msg]})
        result["elapsed_s"] = round(time.perf_counter() - t0, 2)

        # Parse messages
        for msg in run_result.get("messages", []):
            entry: dict[str, Any] = {"role": type(msg).__name__, "content": ""}

            if isinstance(msg, SystemMessage):
                entry["content"] = _extract_text(msg.content)
            elif isinstance(msg, HumanMessage):
                entry["content"] = _extract_text(msg.content)
            elif isinstance(msg, AIMessage):
                entry["content"] = _extract_text(msg.content)
                # Capture tool calls
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_entry = {
                            "tool": tc.get("name", "unknown"),
                            "args": tc.get("args", {}),
                        }
                        result["tool_calls"].append(tool_entry)
                        entry.setdefault("tool_calls", []).append(tool_entry)
            elif isinstance(msg, ToolMessage):
                entry["content"] = _extract_text(msg.content)[:2000]  # Truncate large API responses
                entry["tool_name"] = getattr(msg, "name", "")

            result["messages"].append(entry)

        # Extract final AI output
        ai_msgs = [
            m for m in run_result.get("messages", [])
            if isinstance(m, AIMessage) and m.content
        ]
        if ai_msgs:
            result["final_output"] = _extract_text(ai_msgs[-1].content)

    except Exception as exc:
        import traceback
        # Dig into chained exceptions for HTTP details
        error_parts = [f"{type(exc).__name__}: {exc}"]
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        while cause:
            error_parts.append(f"  Caused by: {type(cause).__name__}: {cause}")
            # httpx.HTTPStatusError has .response
            resp = getattr(cause, "response", None)
            if resp is not None:
                error_parts.append(f"  HTTP {resp.status_code}: {resp.text[:500]}")
            cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
        result["error"] = "\n".join(error_parts)
        result["traceback"] = traceback.format_exc()
        try:
            result["elapsed_s"] = round(time.perf_counter() - t0, 2)
        except NameError:
            pass

    return result


# ── Flight card parser ─────────────────────────────────────────────────────

import re


def _parse_flights_from_tool_response(messages: list[dict]) -> list[dict]:
    """Parse structured flight data from the search_flights tool response text."""
    flights = []
    tool_msg = None
    for msg in messages:
        if msg.get("role") == "ToolMessage" and msg.get("tool_name") == "search_flights":
            tool_msg = msg.get("content", "")
            break
    if not tool_msg:
        return flights

    # Split by numbered entries (e.g., "  1. ZZ0660 ...")
    entries = re.split(r"\n\s*\d+\.\s+", tool_msg)
    for entry in entries[1:]:  # skip the header
        flight: dict[str, Any] = {}
        lines = entry.strip().split("\n")
        if not lines:
            continue

        # First line: "ZZ0660 (Duffel Airways) — EUR 281.56"
        header_match = re.match(
            r"(\w+)\s+\((.+?)\)\s+[—–-]+\s+(\w+)\s+([\d.]+)", lines[0]
        )
        if header_match:
            flight["flight_number"] = header_match.group(1)
            flight["airline_name"] = header_match.group(2)
            flight["currency"] = header_match.group(3)
            flight["price"] = float(header_match.group(4))
        else:
            continue

        # Extract carrier code
        carrier_match = re.search(r"Carrier:\s*(\w+)", entry)
        flight["carrier_code"] = carrier_match.group(1) if carrier_match else flight["flight_number"][:2]

        # Departure/arrival airports
        dep_match = re.search(r"Departure airport:\s*(\w+)", entry)
        arr_match = re.search(r"Arrival airport:\s*(\w+)", entry)
        flight["origin"] = dep_match.group(1) if dep_match else "???"
        flight["destination"] = arr_match.group(1) if arr_match else "???"

        # Times
        time_match = re.search(r"Depart:\s*(\S+)\s*→\s*Arrive:\s*(\S+)", entry)
        if time_match:
            flight["departure_time"] = time_match.group(1)
            flight["arrival_time"] = time_match.group(2)

        # Duration and stops
        dur_match = re.search(r"Duration:\s*(\S+(?:\s+\d+m)?)\s*\((\d+)\s*minutes\)\s*·\s*(.+)", entry)
        if dur_match:
            flight["duration_str"] = dur_match.group(1)
            flight["duration_mins"] = int(dur_match.group(2))
            stops_text = dur_match.group(3).strip()
            flight["stops"] = 0 if "non-stop" in stops_text.lower() else int(re.search(r"(\d+)", stops_text).group(1)) if re.search(r"(\d+)", stops_text) else 1

        # Cabin
        cabin_match = re.search(r"Cabin:\s*(.+?)(?:\n|$)", entry)
        flight["cabin"] = cabin_match.group(1).strip() if cabin_match else "Economy"

        # Baggage
        bags_match = re.search(r"Bags included:\s*(.+?)(?:\n|$)", entry)
        flight["baggage"] = bags_match.group(1).strip() if bags_match else "Unknown"

        # Conditions (change/refund)
        change_match = re.search(r"Change:\s*(.+?)(?:\s*\||\n|$)", entry)
        refund_match = re.search(r"Refund:\s*(.+?)(?:\n|$)", entry)
        flight["change_policy"] = change_match.group(1).strip() if change_match else "Unknown"
        flight["refund_policy"] = refund_match.group(1).strip() if refund_match else "Unknown"

        # Return flight
        ret_match = re.search(
            r"Return:\s*(\w+)\s*→\s*(\w+)\s*\n\s*Return depart:\s*(\S+)\s*→\s*Return arrive:\s*(\S+)\s*\n\s*Return duration:\s*(\S+(?:\s+\d+m)?)\s*·\s*(.+)",
            entry,
        )
        if ret_match:
            flight["return_origin"] = ret_match.group(1)
            flight["return_destination"] = ret_match.group(2)
            flight["return_departure"] = ret_match.group(3)
            flight["return_arrival"] = ret_match.group(4)
            flight["return_duration"] = ret_match.group(5)
            ret_stops_text = ret_match.group(6).strip()
            flight["return_stops"] = 0 if "non-stop" in ret_stops_text.lower() else int(re.search(r"(\d+)", ret_stops_text).group(1)) if re.search(r"(\d+)", ret_stops_text) else 1

        flights.append(flight)

    return flights


def _render_flights_cards(flights: list[dict], final_output: str) -> str:
    """Render interactive flight cards HTML."""
    if not flights:
        return ""

    cards_html = []
    for i, f in enumerate(flights):
        carrier = f.get("carrier_code", "XX")
        airline = html.escape(f.get("airline_name", "Unknown"))
        flight_num = html.escape(f.get("flight_number", ""))
        price = f.get("price", 0)
        currency = f.get("currency", "EUR")
        origin = f.get("origin", "???")
        dest = f.get("destination", "???")
        dep_time = f.get("departure_time", "")
        arr_time = f.get("arrival_time", "")
        duration = f.get("duration_str", "N/A")
        duration_mins = f.get("duration_mins", 0)
        stops = f.get("stops", 0)
        cabin = html.escape(f.get("cabin", "Economy"))
        baggage = html.escape(f.get("baggage", "Unknown"))
        change = html.escape(f.get("change_policy", "Unknown"))
        refund = html.escape(f.get("refund_policy", "Unknown"))

        # Format times nicely
        dep_display = dep_time.split("T")[1][:5] if "T" in dep_time else dep_time
        arr_display = arr_time.split("T")[1][:5] if "T" in arr_time else arr_time
        dep_date = dep_time.split("T")[0] if "T" in dep_time else ""

        # Stops badge
        stops_badge = '<span class="flight-badge badge-nonstop">Non-stop</span>' if stops == 0 else f'<span class="flight-badge badge-stops">{stops} stop{"s" if stops > 1 else ""}</span>'

        # Return flight info
        return_html = ""
        if f.get("return_departure"):
            ret_dep = f["return_departure"].split("T")[1][:5] if "T" in f["return_departure"] else f["return_departure"]
            ret_arr = f["return_arrival"].split("T")[1][:5] if "T" in f.get("return_arrival", "") else f.get("return_arrival", "")
            ret_date = f["return_departure"].split("T")[0] if "T" in f["return_departure"] else ""
            ret_dur = f.get("return_duration", "N/A")
            ret_stops = f.get("return_stops", 0)
            ret_stops_badge = '<span class="flight-badge badge-nonstop">Non-stop</span>' if ret_stops == 0 else f'<span class="flight-badge badge-stops">{ret_stops} stop{"s" if ret_stops > 1 else ""}</span>'
            return_html = f"""
            <div class="flight-leg return-leg">
              <div class="leg-label">↩ Return · {html.escape(ret_date)}</div>
              <div class="leg-route">
                <div class="route-endpoint">
                  <div class="route-time">{html.escape(ret_dep)}</div>
                  <div class="route-airport">{html.escape(f.get('return_origin', dest))}</div>
                </div>
                <div class="route-connector">
                  <div class="route-duration">{html.escape(ret_dur)}</div>
                  <div class="route-line"></div>
                  {ret_stops_badge}
                </div>
                <div class="route-endpoint">
                  <div class="route-time">{html.escape(ret_arr)}</div>
                  <div class="route-airport">{html.escape(f.get('return_destination', origin))}</div>
                </div>
              </div>
            </div>"""

        # Recommended badge (first flight is cheapest/best)
        rec_badge = '<div class="recommended-badge">★ Recommended</div>' if i == 0 else ""
        rec_class = " flight-card-recommended" if i == 0 else ""

        # Booking link (Google Flights search — deep link)
        booking_url = f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{dest}+on+{dep_date}"

        cards_html.append(f"""
        <div class="flight-card{rec_class}" data-price="{price}" data-duration="{duration_mins}" data-stops="{stops}">
          {rec_badge}
          <div class="flight-card-header">
            <div class="airline-info">
              <img src="https://assets.duffel.com/img/airlines/for-light-background/full-color-lockup/{html.escape(carrier)}.svg"
                   alt="{airline}" class="airline-logo"
                   onerror="this.onerror=null;this.src='https://assets.duffel.com/img/airlines/for-light-background/full-color-logo/{html.escape(carrier)}.svg'">
              <div>
                <div class="airline-name">{airline}</div>
                <div class="flight-number">{flight_num}</div>
              </div>
            </div>
            <div class="flight-price">
              <div class="price-amount">{currency} {price:.2f}</div>
              <div class="price-label">per person</div>
            </div>
          </div>

          <div class="flight-leg outbound-leg">
            <div class="leg-label">✈ Outbound · {html.escape(dep_date)}</div>
            <div class="leg-route">
              <div class="route-endpoint">
                <div class="route-time">{html.escape(dep_display)}</div>
                <div class="route-airport">{html.escape(origin)}</div>
              </div>
              <div class="route-connector">
                <div class="route-duration">{html.escape(duration)}</div>
                <div class="route-line"></div>
                {stops_badge}
              </div>
              <div class="route-endpoint">
                <div class="route-time">{html.escape(arr_display)}</div>
                <div class="route-airport">{html.escape(dest)}</div>
              </div>
            </div>
          </div>

          {return_html}

          <div class="flight-details-toggle" onclick="this.parentElement.querySelector('.flight-details').classList.toggle('open'); this.classList.toggle('open');">
            <span class="toggle-icon">▸</span> Flight details
          </div>
          <div class="flight-details">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-icon">💺</span>
                <span class="detail-label">Cabin</span>
                <span class="detail-value">{cabin}</span>
              </div>
              <div class="detail-item">
                <span class="detail-icon">🧳</span>
                <span class="detail-label">Baggage</span>
                <span class="detail-value">{baggage}</span>
              </div>
              <div class="detail-item">
                <span class="detail-icon">🔄</span>
                <span class="detail-label">Changes</span>
                <span class="detail-value">{change}</span>
              </div>
              <div class="detail-item">
                <span class="detail-icon">💰</span>
                <span class="detail-label">Refund</span>
                <span class="detail-value">{refund}</span>
              </div>
            </div>
          </div>

          <div class="flight-card-footer">
            <div class="total-price">Total for 2: <strong>{currency} {price * 2:.2f}</strong></div>
            <a href="{html.escape(booking_url)}" target="_blank" rel="noopener" class="book-button">
              Search & Book →
            </a>
          </div>
        </div>
        """)

    return f"""
    <div class="flights-section">
      <div class="flights-header">
        <h3>✈ Flight Options</h3>
        <div class="sort-controls">
          <span class="sort-label">Sort by:</span>
          <button class="sort-btn active" data-sort="price" onclick="sortFlights('price')">Price</button>
          <button class="sort-btn" data-sort="duration" onclick="sortFlights('duration')">Duration</button>
          <button class="sort-btn" data-sort="stops" onclick="sortFlights('stops')">Stops</button>
        </div>
      </div>
      <div class="flights-grid" id="flights-grid">
        {''.join(cards_html)}
      </div>
    </div>
    """


# ── HTML report generation ────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Report — {title}</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922; --purple: #bc8cff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6; padding: 24px;
  }}
  h1 {{ font-size: 24px; margin-bottom: 8px; }}
  h2 {{ font-size: 18px; color: var(--accent); margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  h3 {{ font-size: 15px; color: var(--muted); margin: 16px 0 8px; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
  .header .meta {{ color: var(--muted); font-size: 13px; }}
  .badge {{
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 12px; font-weight: 600; margin-right: 6px;
  }}
  .badge-green {{ background: rgba(63,185,80,0.15); color: var(--green); }}
  .badge-red {{ background: rgba(248,81,73,0.15); color: var(--red); }}
  .badge-yellow {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
  .badge-purple {{ background: rgba(188,140,255,0.15); color: var(--purple); }}
  .badge-blue {{ background: rgba(88,166,255,0.15); color: var(--accent); }}

  .summary-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .summary-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; text-align: center;
  }}
  .summary-card .value {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
  .summary-card .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}

  .agent-section {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; margin-bottom: 16px;
  }}
  .agent-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px; flex-wrap: wrap; gap: 8px;
  }}
  .agent-header h2 {{ margin: 0; border: none; padding: 0; }}

  .tool-tag {{
    display: inline-block; background: rgba(188,140,255,0.12); color: var(--purple);
    padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px;
    font-family: 'SF Mono', 'Fira Code', monospace;
  }}

  .message-flow {{ margin-top: 16px; }}
  .msg {{
    padding: 12px 16px; border-radius: 8px; margin-bottom: 8px;
    font-size: 14px; position: relative;
  }}
  .msg-system {{ background: rgba(88,166,255,0.08); border-left: 3px solid var(--accent); }}
  .msg-human {{ background: rgba(63,185,80,0.08); border-left: 3px solid var(--green); }}
  .msg-ai {{ background: rgba(188,140,255,0.08); border-left: 3px solid var(--purple); }}
  .msg-tool {{ background: rgba(210,153,34,0.08); border-left: 3px solid var(--yellow); font-family: monospace; font-size: 12px; }}
  .msg-label {{
    font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 4px;
  }}
  .msg-system .msg-label {{ color: var(--accent); }}
  .msg-human .msg-label {{ color: var(--green); }}
  .msg-ai .msg-label {{ color: var(--purple); }}
  .msg-tool .msg-label {{ color: var(--yellow); }}
  .msg-content {{ white-space: pre-wrap; word-break: break-word; }}
  .msg-content.truncated {{ max-height: 400px; overflow-y: auto; }}

  .tool-call-box {{
    background: rgba(210,153,34,0.06); border: 1px solid rgba(210,153,34,0.2);
    border-radius: 6px; padding: 10px 14px; margin: 6px 0; font-size: 13px;
  }}
  .tool-call-box code {{ color: var(--yellow); font-weight: 600; }}
  .tool-call-box pre {{
    background: var(--bg); border-radius: 4px; padding: 8px; margin-top: 6px;
    overflow-x: auto; font-size: 12px; color: var(--muted);
  }}

  .final-output {{
    background: var(--surface); border: 2px solid var(--green); border-radius: 8px;
    padding: 20px; margin-top: 16px;
  }}
  .final-output h3 {{ color: var(--green); margin-bottom: 8px; }}
  .final-output .content {{ white-space: pre-wrap; word-break: break-word; max-height: 600px; overflow-y: auto; }}

  .error-box {{
    background: rgba(248,81,73,0.08); border: 2px solid var(--red); border-radius: 8px;
    padding: 20px; margin-top: 12px; color: var(--red);
  }}

  .prompt-box {{
    background: rgba(63,185,80,0.06); border: 1px solid rgba(63,185,80,0.2);
    border-radius: 6px; padding: 12px; font-size: 14px; margin: 8px 0;
  }}

  .collapsible {{ cursor: pointer; user-select: none; }}
  .collapsible::before {{ content: "▸ "; transition: transform 0.2s; }}
  .collapsible.open::before {{ content: "▾ "; }}
  .collapsible-content {{ display: none; }}
  .collapsible-content.open {{ display: block; }}

  nav {{ position: sticky; top: 0; background: var(--bg); padding: 12px 0; z-index: 10; border-bottom: 1px solid var(--border); margin-bottom: 16px; }}
  nav a {{ color: var(--accent); text-decoration: none; margin-right: 16px; font-size: 14px; }}
  nav a:hover {{ text-decoration: underline; }}

  .toc {{ display: flex; flex-wrap: wrap; gap: 8px; }}

  /* ── Flight Cards ─────────────────────────────────────────── */
  .flights-section {{ margin-top: 20px; }}
  .flights-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }}
  .flights-header h3 {{ color: var(--accent); font-size: 18px; margin: 0; }}
  .sort-controls {{ display: flex; align-items: center; gap: 8px; }}
  .sort-label {{ font-size: 12px; color: var(--muted); }}
  .sort-btn {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    color: var(--muted); padding: 4px 12px; font-size: 12px; cursor: pointer;
    transition: all 0.2s;
  }}
  .sort-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .sort-btn.active {{ background: rgba(88,166,255,0.12); border-color: var(--accent); color: var(--accent); font-weight: 600; }}

  .flights-grid {{ display: flex; flex-direction: column; gap: 16px; }}
  .flight-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; transition: all 0.2s; position: relative; overflow: hidden;
  }}
  .flight-card:hover {{ border-color: var(--accent); box-shadow: 0 4px 20px rgba(88,166,255,0.1); }}
  .flight-card-recommended {{ border-color: var(--green); }}
  .flight-card-recommended:hover {{ border-color: var(--green); box-shadow: 0 4px 20px rgba(63,185,80,0.15); }}
  .recommended-badge {{
    position: absolute; top: 12px; right: 12px;
    background: rgba(63,185,80,0.15); color: var(--green);
    padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
  }}

  .flight-card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
  .airline-info {{ display: flex; align-items: center; gap: 12px; }}
  .airline-logo {{
    width: auto; height: 36px; max-width: 110px;
    object-fit: contain;
  }}
  .airline-name {{ font-weight: 600; font-size: 15px; }}
  .flight-number {{ font-size: 12px; color: var(--muted); font-family: 'SF Mono', monospace; }}
  .flight-price {{ text-align: right; }}
  .price-amount {{ font-size: 20px; font-weight: 700; color: var(--green); }}
  .price-label {{ font-size: 11px; color: var(--muted); }}

  .flight-leg {{ margin: 12px 0; padding: 12px; background: var(--bg); border-radius: 8px; }}
  .leg-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; font-weight: 600; }}
  .leg-route {{ display: flex; align-items: center; gap: 16px; justify-content: center; }}
  .route-endpoint {{ text-align: center; min-width: 60px; }}
  .route-time {{ font-size: 20px; font-weight: 700; }}
  .route-airport {{ font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: 0.5px; }}
  .route-connector {{ flex: 1; text-align: center; position: relative; min-width: 120px; }}
  .route-duration {{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
  .route-line {{
    height: 2px; background: linear-gradient(to right, var(--accent), var(--purple));
    border-radius: 1px; margin: 0 auto; position: relative;
  }}
  .route-line::before, .route-line::after {{
    content: ''; position: absolute; top: -3px; width: 8px; height: 8px;
    border-radius: 50%; border: 2px solid var(--accent); background: var(--bg);
  }}
  .route-line::before {{ left: -4px; }}
  .route-line::after {{ right: -4px; border-color: var(--purple); }}
  .flight-badge {{
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 10px; font-weight: 600; margin-top: 6px;
  }}
  .badge-nonstop {{ background: rgba(63,185,80,0.12); color: var(--green); }}
  .badge-stops {{ background: rgba(210,153,34,0.12); color: var(--yellow); }}

  .return-leg {{ border-left: 3px solid var(--purple); }}

  .flight-details-toggle {{
    padding: 8px 0; color: var(--muted); font-size: 13px; cursor: pointer;
    user-select: none; transition: color 0.2s; border-top: 1px solid var(--border); margin-top: 12px;
  }}
  .flight-details-toggle:hover {{ color: var(--accent); }}
  .flight-details-toggle .toggle-icon {{ display: inline-block; transition: transform 0.2s; }}
  .flight-details-toggle.open .toggle-icon {{ transform: rotate(90deg); }}
  .flight-details {{
    max-height: 0; overflow: hidden; transition: max-height 0.3s ease;
  }}
  .flight-details.open {{ max-height: 200px; padding-top: 12px; }}
  .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .detail-item {{ display: flex; align-items: center; gap: 8px; font-size: 13px; }}
  .detail-icon {{ font-size: 16px; }}
  .detail-label {{ color: var(--muted); min-width: 70px; }}
  .detail-value {{ font-weight: 500; }}

  .flight-card-footer {{
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border);
  }}
  .total-price {{ font-size: 14px; color: var(--muted); }}
  .total-price strong {{ color: var(--text); font-size: 16px; }}
  .book-button {{
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    color: white; padding: 10px 20px; border-radius: 8px;
    text-decoration: none; font-weight: 600; font-size: 14px;
    transition: all 0.2s; box-shadow: 0 2px 8px rgba(88,166,255,0.3);
  }}
  .book-button:hover {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgba(88,166,255,0.4); }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🧪 Agent Test Report</h1>
    <div class="meta">{timestamp} &middot; Wanderlisted Agent Harness</div>
  </div>
  <div>
    <span class="badge badge-blue">{agent_count} agent(s)</span>
    <span class="badge {status_badge}">{status_label}</span>
  </div>
</div>

<div class="summary-grid">
  <div class="summary-card"><div class="value">{agent_count}</div><div class="label">Agents Tested</div></div>
  <div class="summary-card"><div class="value">{total_tools}</div><div class="label">Tool Calls</div></div>
  <div class="summary-card"><div class="value">{total_time}s</div><div class="label">Total Time</div></div>
  <div class="summary-card"><div class="value">{pass_count}/{agent_count}</div><div class="label">Passed</div></div>
</div>

<nav>
  <div class="toc">{nav_links}</div>
</nav>

{agent_sections}

<script>
document.querySelectorAll('.collapsible').forEach(el => {{
  el.addEventListener('click', () => {{
    el.classList.toggle('open');
    const target = el.nextElementSibling;
    if (target) target.classList.toggle('open');
  }});
}});

function sortFlights(criteria) {{
  const grid = document.getElementById('flights-grid');
  if (!grid) return;
  const cards = Array.from(grid.querySelectorAll('.flight-card'));
  cards.sort((a, b) => {{
    const aVal = parseFloat(a.dataset[criteria]) || 0;
    const bVal = parseFloat(b.dataset[criteria]) || 0;
    return aVal - bVal;
  }});
  cards.forEach(card => grid.appendChild(card));
  document.querySelectorAll('.sort-btn').forEach(btn => {{
    btn.classList.toggle('active', btn.dataset.sort === criteria);
  }});
}}
</script>
</body>
</html>
"""


def _render_message_html(msg: dict) -> str:
    """Render a single message dict as HTML."""
    role = msg.get("role", "Unknown")
    content = html.escape(msg.get("content", "") or "")
    tool_name = msg.get("tool_name", "")

    role_class = {
        "SystemMessage": "system",
        "HumanMessage": "human",
        "AIMessage": "ai",
        "ToolMessage": "tool",
    }.get(role, "system")

    label = role.replace("Message", "")
    if tool_name:
        label = f"Tool: {html.escape(tool_name)}"

    parts = [f'<div class="msg msg-{role_class}">']
    parts.append(f'<div class="msg-label">{label}</div>')

    # Tool calls within AI messages
    tool_calls = msg.get("tool_calls", [])
    if tool_calls:
        for tc in tool_calls:
            args_json = html.escape(json.dumps(tc.get("args", {}), indent=2, default=str))
            parts.append(
                f'<div class="tool-call-box">'
                f'🔧 <code>{html.escape(tc.get("tool", ""))}</code>'
                f'<pre>{args_json}</pre></div>'
            )

    if content:
        truncated = " truncated" if len(content) > 2000 else ""
        parts.append(f'<div class="msg-content{truncated}">{content}</div>')

    parts.append("</div>")
    return "\n".join(parts)


def _render_agent_section(data: dict) -> str:
    """Render one agent's results as an HTML section."""
    name = data["agent_name"]
    anchor = name.lower()
    error = data.get("error")
    elapsed = data.get("elapsed_s", 0)
    tier = data.get("tier", "?")
    tools = data.get("tools", [])
    tool_calls = data.get("tool_calls", [])
    messages = data.get("messages", [])
    final_output = data.get("final_output", "")
    prompt = data.get("prompt", "")

    status = "badge-red" if error else "badge-green"
    status_text = "FAIL" if error else "PASS"

    tools_html = "".join(f'<span class="tool-tag">{html.escape(t)}</span>' for t in tools)

    # Message flow (collapsible)
    msgs_html = "".join(_render_message_html(m) for m in messages)

    section = f"""
    <div class="agent-section" id="{anchor}">
      <div class="agent-header">
        <h2>{html.escape(name.replace('_', ' ').title())} Agent</h2>
        <div>
          <span class="badge badge-purple">{tier} tier</span>
          <span class="badge badge-yellow">{len(tool_calls)} tool calls</span>
          <span class="badge badge-blue">{elapsed}s</span>
          <span class="badge {status}">{status_text}</span>
        </div>
      </div>

      <div>
        <strong>Available tools:</strong> {tools_html or '<em>none</em>'}
      </div>

      <div class="prompt-box">
        <strong>Test prompt:</strong> {html.escape(prompt)}
      </div>
    """

    if error:
        section += f'<div class="error-box"><strong>Error:</strong> {html.escape(error)}</div>'

    # Message flow (collapsible)
    section += f"""
      <h3 class="collapsible">Message Flow ({len(messages)} messages)</h3>
      <div class="collapsible-content">
        <div class="message-flow">{msgs_html}</div>
      </div>
    """

    # System prompt (collapsible)
    sys_prompt = data.get("system_prompt", "")
    if sys_prompt:
        section += f"""
      <h3 class="collapsible">System Prompt</h3>
      <div class="collapsible-content">
        <div class="msg msg-system"><div class="msg-content truncated">{html.escape(sys_prompt)}</div></div>
      </div>
        """

    # Final output (always visible)
    if final_output:
        # Special rendering for flights agent
        flights_cards_html = ""
        if name == "flights":
            parsed_flights = _parse_flights_from_tool_response(messages)
            if parsed_flights:
                flights_cards_html = _render_flights_cards(parsed_flights, final_output)

        if flights_cards_html:
            section += flights_cards_html
            # AI analysis in a collapsible below the cards
            section += f"""
      <h3 class="collapsible open">Agent Analysis & Recommendation</h3>
      <div class="collapsible-content open">
        <div class="final-output">
          <div class="content">{html.escape(final_output)}</div>
        </div>
      </div>
            """
        else:
            section += f"""
      <div class="final-output">
        <h3>✅ Final Agent Output</h3>
        <div class="content">{html.escape(final_output)}</div>
      </div>
            """

    section += "</div>"
    return section


def generate_report(results: list[dict]) -> str:
    """Generate the full HTML report from a list of agent results."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    agent_count = len(results)
    pass_count = sum(1 for r in results if not r.get("error"))
    total_tools = sum(len(r.get("tool_calls", [])) for r in results)
    total_time = round(sum(r.get("elapsed_s", 0) for r in results), 1)

    all_pass = pass_count == agent_count
    status_badge = "badge-green" if all_pass else "badge-red"
    status_label = "ALL PASS" if all_pass else f"{agent_count - pass_count} FAILED"

    nav_links = "".join(
        f'<a href="#{r["agent_name"].lower()}">{r["agent_name"]}</a>'
        for r in results
    )

    agent_sections = "\n".join(_render_agent_section(r) for r in results)

    return _HTML_TEMPLATE.format(
        title=", ".join(r["agent_name"] for r in results),
        timestamp=timestamp,
        agent_count=agent_count,
        total_tools=total_tools,
        total_time=total_time,
        pass_count=pass_count,
        status_badge=status_badge,
        status_label=status_label,
        nav_links=nav_links,
        agent_sections=agent_sections,
    )


# ── CLI ───────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wanderlisted Agent Test Harness — run agents in isolation with HTML reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--agents", nargs="+", metavar="NAME",
        help=f"Agent(s) to test. Available: {', '.join(sorted(AGENT_REGISTRY))}",
    )
    parser.add_argument("--list", action="store_true", help="List available agents and exit")
    parser.add_argument("--prompt", type=str, help="Custom prompt (applied to all selected agents)")
    parser.add_argument("--dest", type=str, default="Tokyo", help="Destination city (default: Tokyo)")
    parser.add_argument("--origin", type=str, default="JFK", help="Origin airport/city (default: JFK)")
    parser.add_argument("--dates", type=str, default="2026-07-10 to 2026-07-17", help="Travel dates")
    parser.add_argument("--open", action="store_true", help="Auto-open HTML report in browser")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output HTML path (default: outputs/agent_reports/<agents>_<timestamp>.html)",
    )
    return parser.parse_args()


def _is_degraded(result: dict) -> bool:
    """Detect if an agent passed but got no real data (API errors in tool responses)."""
    api_error_keywords = ["API error", "temporarily unavailable", "search failed", "error (5"]
    for msg in result.get("messages", []):
        if msg.get("role") == "ToolMessage":
            content = msg.get("content", "")
            if any(kw.lower() in content.lower() for kw in api_error_keywords):
                return True
    return False


async def main() -> None:
    args = parse_args()

    if args.list:
        print("Available agents:\n")
        for name, (cls, tier) in sorted(AGENT_REGISTRY.items()):
            print(f"  {name:<20s}  tier={tier:<10s}  class={cls.name}")
        print(f"\nTotal: {len(AGENT_REGISTRY)} agents")
        print("\nUsage: python scripts/agent_harness.py --agents flights hotels destination")
        return

    # Default: run all agents
    agent_names = args.agents or sorted(AGENT_REGISTRY.keys())

    # Validate
    for name in agent_names:
        if name not in AGENT_REGISTRY:
            print(f"ERROR: Unknown agent '{name}'. Available: {', '.join(sorted(AGENT_REGISTRY))}")
            sys.exit(1)

    print(f"🧪 Agent Harness — testing {len(agent_names)} agent(s): {', '.join(agent_names)}")
    print(f"   Destination: {args.dest} | Origin: {args.origin} | Dates: {args.dates}")
    print()

    results = []
    for name in agent_names:
        print(f"  ▸ Running {name}...", end=" ", flush=True)
        result = await run_agent_harness(
            name,
            prompt=args.prompt,
            dest=args.dest,
            origin=args.origin,
            dates=args.dates,
        )
        status = "✗ FAIL" if result.get("error") else "✓"
        tool_count = len(result.get("tool_calls", []))
        print(f"{status}  ({result['elapsed_s']}s, {tool_count} tool calls)")
        results.append(result)

    # Generate HTML report
    report_html = generate_report(results)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = "_".join(agent_names[:3])
        if len(agent_names) > 3:
            slug += f"_+{len(agent_names) - 3}"
        out_path = OUTPUT_DIR / f"{slug}_{ts}.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_html, encoding="utf-8")

    # Also write JSON for programmatic use
    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(results, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    pass_count = sum(1 for r in results if not r.get("error"))
    degraded_count = sum(
        1 for r in results
        if not r.get("error") and _is_degraded(r)
    )
    print(f"\n{'=' * 60}")
    print(f"  Results: {pass_count}/{len(results)} passed")
    if degraded_count:
        print(f"  ⚠ Degraded: {degraded_count} agent(s) got API errors (external service issue)")
    print(f"  HTML:    {out_path}")
    print(f"  JSON:    {json_path}")
    print(f"{'=' * 60}")

    if args.open:
        import subprocess
        subprocess.Popen(["open", str(out_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    asyncio.run(main())
