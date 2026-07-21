"""Shared, PARAMETERIZED rubric scaffold for every component judge (all agents).

WHY THIS FILE EXISTS
    Layer 2/3 for the Flights agent proved a pattern: a single-dimension, anchored,
    isolation-aware rubric + a structured-output judge. We are now applying that
    SAME pattern to eight agents. Copy-pasting the rubric eight times would let the
    wording drift agent-to-agent — and a judge is only as trustworthy as its
    rubric. So the rubric TEXT lives here ONCE, as a template, and the ONLY thing
    that changes per agent is a small `AgentRubricSpec` (its CORE facts, its
    evidence source, what "helpful" means for it). One rubric, eight instantiations.

WHAT IS SHARED HERE
    • Verdict / Preference      — the structured outputs a judge must emit.
    • build_judge / build_pairwise_judge — the judge handles (a strong LLM +
                                  forced structured output).
    • faithfulness_rubric() / helpfulness_rubric() / pairwise_rubric()
                                — the rubric TEMPLATES, filled from a spec.
    • score_faithfulness / score_helpfulness / compare_pairwise
                                — the generic scorers (take an explicit rubric).
    • AGENT_SPECS               — the per-agent knowledge for ALL EIGHT agents.

WHAT STAYS PER-AGENT (in edd/<agent>/l2_judge.py)
    • the illustrative in-context EXAMPLES (kept next to that agent's calibration
      cases so they stay DISJOINT — see the leakage note on faithfulness_rubric).
    • the thin `judge_*` / `JUDGES` bindings and the runners.

THE RUBRIC-DESIGN RULES this scaffold bakes in (from the agent-evaluation skill's
metric-catalog "Rubric Construction" checklist):
    single-dimension · states its evidence · declares exclusions (isolation) ·
    anchors every 0/1/2/3 · reasoning-before-score · forces structured output ·
    supports a few borderline in-context examples.

Preview any agent's faithfulness rubric (hermetic — no LLM, just string-building):
    .venv/bin/python edd/rubrics.py hotels
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from dataclasses import dataclass
from typing import Literal

# Importable from anywhere in the tree, and runnable directly for the preview.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from edd.harness import Trajectory  # noqa: E402
from src.agent.llm import get_llm  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# 1. The structured verdicts — shared by EVERY agent's judge.
#    Forcing structured output is what turns an LLM's opinion into a MEASUREMENT:
#    a number we can average + a reason we can audit. `reasoning` is declared
#    BEFORE the verdict so the model justifies itself first and commits second
#    (cheap chain-of-thought that makes the score more stable and inspectable).
# ══════════════════════════════════════════════════════════════════════════════
class Verdict(BaseModel):
    """One judge's scored opinion of ONE dimension of ONE answer (pointwise)."""

    reasoning: str = Field(
        description="1–2 sentences justifying the score, citing the specific "
        "claim(s) or gap(s) that drove it."
    )
    score: int = Field(ge=0, le=3, description="0–3, per the rubric in the prompt.")


class Preference(BaseModel):
    """One judge's pairwise verdict comparing two answers on ONE dimension."""

    reasoning: str = Field(
        description="1–2 sentences naming the concrete difference that decided "
        "it, or why the two answers are equally good (a tie)."
    )
    winner: Literal["A", "B", "tie"] = Field(
        description="Which answer is better on THIS dimension: 'A', 'B', or 'tie' "
        "when they are equally good."
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. The per-agent spec — the ONLY thing that changes between agents.
#    Every field is a fragment the rubric templates below splice in. Writing a
#    judge for a new agent = writing ONE of these, not a new rubric.
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class AgentRubricSpec:
    """The agent-specific knowledge a rubric template needs to grade one agent."""

    agent: str  # display name, e.g. "Flights"
    evidence_source: str  # the tool(s) whose output is ground truth (a phrase)
    domain: str  # the CAPS noun for the graded facts, e.g. "FLIGHT DATA"
    request_fields: str  # what a REQUEST typically contains, for the judge's context
    request_echo: str  # examples of REQUEST params it's OK to restate (not invention)
    core_facts: str  # the facts that MUST be grounded (a booking would turn on them)
    noncore: str  # unsupported extras that are a minor slip, not a fabrication
    wrong_decision: str  # "...would NOT <book a wrong flight> over" — the stakes phrase
    minor_slip: str  # the score-2 boundary: what a forgivable slip looks like
    core_error: (
        str  # the score-1 boundary: what a materially misleading error looks like
    )
    surfaces: str  # helpfulness: what a good answer should surface for this agent


# ══════════════════════════════════════════════════════════════════════════════
# 3. The rubric TEMPLATES — one per dimension, filled from a spec.
#    These are deliberately near-identical in shape to the calibrated Flights
#    rubrics; the spec fields are the holes. Keep them single-dimension: a
#    faithfulness judge NEVER grades helpfulness and vice-versa.
# ══════════════════════════════════════════════════════════════════════════════
def faithfulness_rubric(spec: AgentRubricSpec, examples: str = "") -> str:
    """Groundedness rubric: is every CORE claim supported by the tool RESULTS?

    LEAKAGE WARNING — the `examples` you pass in MUST be disjoint from the
    agent's l2_judge_cases.py (the Layer-4 calibration set). If the judge is
    shown the very cases it is later scored on, κ is inflated by memorization,
    not agreement. Use different destinations/numbers in the examples.
    """
    ex = f"\n\n{examples.strip()}" if examples.strip() else ""
    return f"""You grade the FAITHFULNESS (groundedness) of a travel assistant's answer.

You will receive:
  • REQUEST — what the traveler asked for ({spec.request_fields}).
  • RESULTS — the raw output of {spec.evidence_source}: the source of truth for
    all {spec.domain}. Treat it as complete.
  • ANSWER  — the assistant's prose summary, written for the traveler.

Judge ONE thing: is every claim about {spec.domain} ({spec.core_facts}) supported
by the RESULTS?

Allowed — NOT fabrication: restating parameters from the REQUEST (e.g. {spec.request_echo}),
even if they do not appear in RESULTS. The traveler supplied those; echoing them
is context, not invention. Only NEW facts must come from RESULTS. Ignore style,
tone, and helpfulness — grade ONLY grounding.

CORE vs NON-CORE. The CORE facts are: {spec.core_facts}. Everything a traveler
would NOT {spec.wrong_decision} — {spec.noncore} — is NON-CORE. Grade the
grounding of the CORE facts; an unsupported NON-CORE extra is at most a minor
slip, never a fabrication.

Score:
  3 — every CORE fact is supported by RESULTS; nothing invented.
      (Restating REQUEST parameters is fine and does NOT lower the score.)
  2 — essentially grounded: at most one MINOR slip that would not change the
      traveler's decision — {spec.minor_slip}.
  1 — one materially misleading error in a CORE fact: {spec.core_error}.
  0 — largely fabricated, or SEVERAL core facts wrong / directly contradicting
      RESULTS.

Give brief reasoning that names the specific claim you checked, then the score.{ex}"""


def helpfulness_rubric(spec: AgentRubricSpec, examples: str = "") -> str:
    """Answer-relevance rubric: does the answer actually serve the request?"""
    ex = f"\n\n{examples.strip()}" if examples.strip() else ""
    return f"""You grade how HELPFUL a travel assistant's answer is for the traveler's REQUEST.

You will receive:
  • REQUEST — what the traveler asked for.
  • ANSWER  — the assistant's response.

Judge ONE thing: does the ANSWER directly serve the REQUEST — surface {spec.surfaces},
give the details a traveler needs to choose, and stay clear and concise?

IMPORTANT (isolation): the agent was run in isolation on ONLY this request, with
no access to the traveler's profile, budget, loyalty programs, or prior
conversation. Judge only what is answerable from THIS request. Do NOT penalize
the absence of information the agent was never given. (Constraints stated in the
REQUEST itself — dates, party size, a star/board/budget/diet ask — ARE fair game:
honoring them is helpful, ignoring them is not.)

IMPORTANT (verbosity): extra length is neutral at best and harmful when it buries
the answer. A longer answer is NOT automatically more helpful — reward the answer
that lets the traveler act fastest.

Score:
  3 — directly and clearly answers the request; a traveler could act on it now.
  2 — useful but with a gap: buries the answer, omits one asked-for detail, or
      is noticeably verbose.
  1 — partially relevant but hard to use, or misses most of the request.
  0 — does not address the request (empty, off-topic, or an error message).

Give brief reasoning, then the score.{ex}"""


def pairwise_rubric(spec: AgentRubricSpec) -> str:
    """Pairwise helpfulness rubric: which of TWO answers serves the request better?"""
    return f"""You compare TWO travel-assistant answers to the SAME request and pick the more HELPFUL one.

You will receive:
  • REQUEST — what the traveler asked for.
  • ANSWER A and ANSWER B — two responses to that same request.

Judge ONE thing: which answer better serves the REQUEST — surfaces {spec.surfaces},
gives the details a traveler needs to choose, and stays clear and concise?

IMPORTANT (isolation): both answers were produced with no access to the
traveler's profile, budget, loyalty programs, or prior conversation. Judge only
what is answerable from THIS request; do not reward or punish either answer for
context neither was given.

IMPORTANT (fairness): ignore superficial length and confidence. A longer or more
assertive answer is NOT automatically better. Answer 'tie' when the two are
equally useful — do not invent a winner.

Reply with:
  • reasoning — name the concrete difference that decided it, or why it's a tie.
  • winner — 'A', 'B', or 'tie'.
"""


# ══════════════════════════════════════════════════════════════════════════════
# 4. The judge handles — a strong LLM constrained to emit a Verdict/Preference.
#    RULE OF THUMB: the judge should be at least as capable as the thing it
#    grades, and IDEALLY a different model than the one(s) under test (kills
#    self-preference bias). Workers run on `fast`; we judge on `reasoning`.
# ══════════════════════════════════════════════════════════════════════════════
def build_judge(tier: str = "reasoning", effort: str | None = None, **overrides):
    """Pointwise grader → emits a `Verdict`. `method="function_calling"` is the
    codebase-standard structured-output path for the gpt-5.x reasoning models.
    `effort`/`**overrides` are forwarded to get_llm() (pin a specific deployment
    with azure_deployment=..., or a different provider with model=...)."""
    if effort:
        overrides["reasoning_effort"] = effort
    return get_llm(tier=tier, **overrides).with_structured_output(
        Verdict, method="function_calling"
    )


def build_pairwise_judge(
    tier: str = "reasoning", effort: str | None = None, **overrides
):
    """Pairwise grader → emits a `Preference`. Same model rules as build_judge;
    if one arm under test IS the reasoning-tier model, point the judge at a
    DIFFERENT strong model (pass tier=/effort=/azure_deployment=) so the judge
    doesn't share identity with a contestant. Position bias is handled separately
    by the order-swap inside compare_pairwise()."""
    if effort:
        overrides["reasoning_effort"] = effort
    return get_llm(tier=tier, **overrides).with_structured_output(
        Preference, method="function_calling"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 5. The generic scorers — take an explicit rubric so any agent reuses them.
#    Each returns the structured-feedback contract {"key", "score"|"winner",
#    "comment"} and captures a judge failure as DATA (score=None), never a crash.
# ══════════════════════════════════════════════════════════════════════════════
async def _run_judge(judge, rubric: str, payload: str, *, timeout: float = 60.0):
    """One judge call, with a timeout. Kept tiny so every scorer shares it."""
    return await asyncio.wait_for(
        judge.ainvoke([SystemMessage(content=rubric), HumanMessage(content=payload)]),
        timeout=timeout,
    )


_URL_RE = re.compile(r"https?://\S+")


def _truncate_middle(text: str, max_chars: int) -> str:
    """Bound one evidence block while retaining both its beginning and end."""
    if len(text) <= max_chars:
        return text
    marker = "\n...[middle truncated for judge context]...\n"
    remaining = max_chars - len(marker)
    head = remaining * 2 // 3
    return text[:head] + marker + text[-(remaining - head) :]


def _format_evidence(
    traj: Trajectory,
    *,
    max_chars_per_output: int = 20_000,
    max_total_chars: int = 80_000,
) -> str:
    """Format bounded evidence without starving later tool calls.

    Hotel runs commonly contain one 8k+ Hotelbeds result followed by several
    Google Places results. The old single 6k prefix silently removed later
    hotels and every enrichment call, making the judge report grounded hotels as
    fabricated. Compact URL payloads, bound each tool output independently, and
    if needed share the total budget across ALL blocks so every call remains
    represented.
    """
    blocks = [
        f"[{name}]\n{_truncate_middle(_URL_RE.sub('<URL>', out), max_chars_per_output)}"
        for name, out in traj.tool_outputs
    ]
    text = "\n\n".join(blocks)
    if len(text) <= max_total_chars or not blocks:
        return text

    fair_share = max(2_000, max_total_chars // len(blocks))
    return "\n\n".join(_truncate_middle(block, fair_share) for block in blocks)


async def score_faithfulness(
    judge, traj: Trajectory, *, rubric: str, key: str = "faithfulness"
) -> dict:
    """Grade whether the final answer is grounded in the tool RESULTS.

    SKIPs (score=None) when there is nothing to ground against — no tool output
    or no answer. (Layer 1's `called_*` check already flags a missing tool call;
    each layer checks its own thing.)
    """
    evidence = _format_evidence(traj)
    if not evidence.strip() or not traj.final_text.strip():
        return {
            "key": key,
            "score": None,
            "comment": "no tool output and/or no answer to check",
        }
    payload = (
        f"REQUEST:\n{traj.query}\n\n"
        f"RESULTS (source of truth):\n{evidence}\n\n"
        f"ANSWER (judge this):\n{traj.final_text}"
    )
    try:
        verdict = await _run_judge(judge, rubric, payload)
    except Exception as exc:  # noqa: BLE001 — a judge failure is data, not a crash
        return {"key": key, "score": None, "comment": f"judge error: {exc}"}
    return {"key": key, "score": verdict.score, "comment": verdict.reasoning}


async def score_helpfulness(
    judge, traj: Trajectory, *, rubric: str, key: str = "helpfulness"
) -> dict:
    """Grade whether the final answer actually serves the traveler's request."""
    if not traj.final_text.strip():
        return {"key": key, "score": 0, "comment": "no answer produced"}
    payload = f"REQUEST:\n{traj.query}\n\nANSWER (judge this):\n{traj.final_text}"
    try:
        verdict = await _run_judge(judge, rubric, payload)
    except Exception as exc:  # noqa: BLE001
        return {"key": key, "score": None, "comment": f"judge error: {exc}"}
    return {"key": key, "score": verdict.score, "comment": verdict.reasoning}


# Map a swapped-order verdict back to the ORIGINAL labels: in the swapped call
# "A" meant traj_b and "B" meant traj_a, so A<->B; 'tie' is symmetric.
_DESWAP = {"A": "B", "B": "A", "tie": "tie"}


def _pairwise_payload(request: str, answer_a: str, answer_b: str) -> str:
    return f"REQUEST:\n{request}\n\nANSWER A:\n{answer_a}\n\nANSWER B:\n{answer_b}"


async def compare_pairwise(
    judge,
    traj_a: Trajectory,
    traj_b: Trajectory,
    *,
    rubric: str,
    key: str = "helpfulness_pairwise",
) -> dict:
    """Compare A vs B on one dimension, controlling for POSITION BIAS.

    An LLM judge favors whichever answer sits in a given slot, so a single call
    is untrustworthy. We ask TWICE, swapping the slots, and only declare a winner
    when both orders agree:

        pass 1 (as-is)   : slot A = traj_a,  slot B = traj_b
        pass 2 (swapped) : slot A = traj_b,  slot B = traj_a

    De-swap pass 2 back to original labels, then reconcile:
      • both orders point to the SAME answer -> that answer wins (robust)
      • both say 'tie'                       -> genuine tie
      • they disagree (order-sensitive)      -> 'tie', flagged consistent=False

    Returns {"key", "winner": "A"|"B"|"tie"|None, "consistent": bool|None,
    "comment"} in terms of the ORIGINAL labels (traj_a = A, traj_b = B). Scored
    verdicts also preserve each order's original-label winner, raw slot winner,
    and reasoning. Inconsistent verdicts classify as `tie_boundary` (winner vs
    tie) or `winner_reversal` (A vs B). SKIPs (winner=None) when an answer is
    empty or the run errored.
    """
    if (
        traj_a.error
        or traj_b.error
        or not traj_a.final_text.strip()
        or not traj_b.final_text.strip()
    ):
        return {
            "key": key,
            "winner": None,
            "consistent": None,
            "comment": "an answer was empty or the run errored — nothing to compare",
        }

    request = traj_a.query  # both variants ran the SAME query
    payload_ab = _pairwise_payload(request, traj_a.final_text, traj_b.final_text)
    payload_ba = _pairwise_payload(request, traj_b.final_text, traj_a.final_text)

    try:
        v1, v2 = await asyncio.gather(
            _run_judge(judge, rubric, payload_ab),
            _run_judge(judge, rubric, payload_ba),
        )
    except Exception as exc:  # noqa: BLE001 — a judge failure is data, not a crash
        detail = str(exc).strip() or type(exc).__name__
        return {
            "key": key,
            "winner": None,
            "consistent": None,
            "comment": f"judge error: {detail}",
        }

    w1 = v1.winner  # already in original labels (A=traj_a, B=traj_b)
    w2 = _DESWAP[v2.winner]  # de-swapped back to original labels

    if w1 == w2:
        return {
            "key": key,
            "winner": w1,
            "consistent": True,
            "comment": v1.reasoning,
            "winner_forward": w1,
            "winner_reverse": w2,
            "slot_winner_forward": v1.winner,
            "slot_winner_reverse": v2.winner,
            "reasoning_forward": v1.reasoning,
            "reasoning_reverse": v2.reasoning,
        }
    return {
        "key": key,
        "winner": "tie",
        "consistent": False,
        "inconsistency_type": (
            "tie_boundary" if "tie" in {w1, w2} else "winner_reversal"
        ),
        "comment": (
            f"order-sensitive: shown one way -> {w1}, swapped -> {w2}; "
            f"counted as tie. Forward: {v1.reasoning} Reverse: {v2.reasoning}"
        ),
        "winner_forward": w1,
        "winner_reverse": w2,
        "slot_winner_forward": v1.winner,
        "slot_winner_reverse": v2.winner,
        "reasoning_forward": v1.reasoning,
        "reasoning_reverse": v2.reasoning,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. AGENT_SPECS — the per-agent knowledge for all EIGHT agents.
#    This is the "robust across every agent" payload: each spec encodes what that
#    worker must get RIGHT (its CORE facts) and where its ground truth comes from.
#    Wiring a new agent's judge = import its spec + write its in-context examples.
# ══════════════════════════════════════════════════════════════════════════════
AGENT_SPECS: dict[str, AgentRubricSpec] = {
    "flights": AgentRubricSpec(
        agent="Flights",
        evidence_source="the `search_flights` tool",
        domain="FLIGHT DATA",
        request_fields="airline, price, times, stops, route, dates, party size, cabin",
        request_echo='"for 1 adult", "economy", the travel date',
        core_facts="airlines, flight numbers, prices, times, durations, number of stops, and dates",
        noncore="baggage, meals, seat, lounge, the CITY a stop is in",
        wrong_decision="book a wrong flight over",
        minor_slip="a rounded price, a paraphrased time, or an unsupported NON-CORE "
        "extra (e.g. a free-baggage or meal claim, or a made-up layover city) not in RESULTS",
        core_error="a price, airline, route, or number of stops that is NOT in / "
        "contradicts RESULTS, or invented per-person/total math the tool did not return",
        surfaces="the most relevant flight option(s)",
    ),
    "hotels": AgentRubricSpec(
        agent="Hotels",
        evidence_source="the hotel tools (`search_hotels_hotelbeds`, "
        "`check_hotel_rate_hotelbeds`) for rate/board/policy facts and "
        "`search_places_text` for neighbourhood/location facts",
        domain="HOTEL DATA",
        request_fields="city/area, stay dates, guests, star rating, board, budget/nightly price",
        request_echo='"for 2 adults", "all-inclusive", the check-in date',
        core_facts="hotel name, nightly/total price, board basis (RO/BB/HB/FB/AI), "
        "star category, room type, cancellation terms (refundable vs non-refundable), and the city/area",
        noncore="specific amenities (pool, gym, spa, wifi), decor or view descriptions, "
        "distance-to-landmark estimates, and review sentiment",
        wrong_decision="book a wrong hotel over",
        minor_slip="a rounded price, a paraphrased distance, or an unsupported NON-CORE "
        "amenity/decor claim not in RESULTS",
        core_error="a price, board basis, star category, cancellation term, or hotel name "
        "that is NOT in / contradicts RESULTS, or review/rating facts matched to the WRONG hotel",
        surfaces="the most relevant hotel option(s) that fit any stars/board/budget stated in the request",
    ),
    "destination": AgentRubricSpec(
        agent="Destination",
        evidence_source="the research tools (`research_destination`, "
        "`search_destination_guides`, `search_web`, `search_hidden_gems`) plus "
        "`get_weather` and `get_safety_info`",
        domain="DESTINATION FACTS",
        request_fields="destination, dates/season, topic (culture, weather, safety, transport, food, events)",
        request_echo="the destination name, the month/season asked about",
        core_facts="safety/advisory level, weather/climate figures, visa/entry rules, "
        "currency, health requirements, and dated events",
        noncore="general cultural colour, subjective 'vibe' descriptions, and non-specific tips",
        wrong_decision="mis-plan a trip over",
        minor_slip="a paraphrased custom, a rounded temperature, or a soft cultural "
        "generalisation not stated verbatim in RESULTS",
        core_error="a safety/advisory level, visa/entry rule, currency, health requirement, "
        "or event date that is NOT in / contradicts RESULTS",
        surfaces="the destination facts and insider guidance the request asked for, "
        "clearly attributed to their source",
    ),
    "restaurants": AgentRubricSpec(
        agent="Restaurants",
        evidence_source="the `search_places_nearby` and `search_places_text` tools (Google Places)",
        domain="RESTAURANT DATA",
        request_fields="location, cuisine, dietary needs, price level, party/occasion",
        request_echo='"vegetarian", "near the Colosseum", the party size',
        core_facts="restaurant name, cuisine, price level, rating/review count, "
        "address/neighbourhood, and open/closed status",
        noncore="specific dish recommendations, ambience/decor descriptions, and estimated wait times",
        wrong_decision="pick the wrong restaurant over",
        minor_slip="a paraphrased cuisine label, a rounded rating, or an unsupported "
        "dish/ambience remark not in RESULTS",
        core_error="a restaurant name, price level, rating, address, or a DIETARY claim "
        "(e.g. 'vegan-friendly') that is NOT in / contradicts RESULTS",
        surfaces="the most relevant dining option(s) that fit the cuisine, budget and any dietary need",
    ),
    "activities": AgentRubricSpec(
        agent="Activities",
        evidence_source="the `search_places_nearby` and `search_places_text` tools (Google Places)",
        domain="ACTIVITY DATA",
        request_fields="location, interests, dates/opening hours, accessibility, party type",
        request_echo='"wheelchair accessible", "with kids", the interest asked for',
        core_facts="attraction name, type/category, rating/review count, address/area, "
        "price level, and opening hours",
        noncore="suggested visit duration, subjective 'must-see' emphasis, and general historical colour",
        wrong_decision="waste a day over",
        minor_slip="a paraphrased category, a rounded rating, or an unsupported "
        "duration/'#1 attraction' remark not in RESULTS",
        core_error="an attraction name, opening hours, price, address, or an ACCESSIBILITY "
        "claim that is NOT in / contradicts RESULTS",
        surfaces="the most relevant activities that fit the stated interests and any accessibility need",
    ),
    "transportation": AgentRubricSpec(
        agent="Transportation",
        evidence_source="the `compute_route` tool (Google Routes)",
        domain="ROUTE DATA",
        request_fields="origin, destination, mode, date/time, waypoints",
        request_echo='"by train", "from the hotel", the time of day',
        core_facts="distance, duration, travel mode, the transit lines/steps, and any transfer/stop counts",
        noncore="general 'it's walkable' impressions, comfort commentary, and fares the tool did not return",
        wrong_decision="miss a connection over",
        minor_slip="a rounded duration/distance, or a soft 'quick hop' remark not verbatim in RESULTS",
        core_error="a duration, distance, mode, transit line, or transfer count that is NOT in / "
        "contradicts RESULTS, or an invented fare",
        surfaces="the clearest route(s) with the distance, duration and steps the traveller needs",
    ),
    "budget": AgentRubricSpec(
        agent="Budget",
        evidence_source="the `calculate_budget` and `convert_currency` tools",
        domain="BUDGET FIGURES",
        request_fields="travellers, duration, destination, travel style, currency, component costs",
        request_echo='"for 2 people", "5 nights", the target currency',
        core_facts="the per-category and total costs, the currency, the conversion rate, "
        "and the traveller/night counts the totals are built from",
        noncore="general 'this is affordable' commentary and non-numeric saving tips",
        wrong_decision="mis-budget a trip over",
        minor_slip="a rounded subtotal or a paraphrased assumption, provided the math still reconciles",
        core_error="a total that does NOT reconcile with its components, a wrong currency or "
        "conversion rate, or a figure the tools never returned",
        surfaces="a clear cost breakdown whose total reconciles with its parts, with assumptions disclosed",
    ),
    "itinerary": AgentRubricSpec(
        agent="Itinerary",
        evidence_source="the day-plan components assembled from the other agents "
        "(flights, hotels, activities, restaurants, transport) plus `optimize_day_route`",
        domain="ITINERARY FACTS",
        request_fields="dates/day count, destinations, the components to assemble, pace",
        request_echo='"5-day trip", the destination, the dates',
        core_facts="the dates/day count, the specific flights, hotels, activities and "
        "restaurants placed on each day, and their locations/times",
        noncore="linking narration, general pacing advice, and subjective 'highlight' emphasis",
        wrong_decision="follow an impossible plan over",
        minor_slip="a paraphrased transition or a soft pacing remark that does not change any booked item",
        core_error="a flight, hotel, activity or restaurant that was NOT provided by the upstream "
        "components, a date/day-count that contradicts the request, or two items placed in "
        "physically impossible sequence",
        surfaces="a feasible day-by-day plan that uses the provided components and honours the dates",
    ),
}


# ── Preview: `python edd/rubrics.py [agent]` prints that agent's rubrics ──────
if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "flights"
    spec = AGENT_SPECS[which]
    print(f"\n================ {spec.agent} — FAITHFULNESS ================\n")
    print(faithfulness_rubric(spec))
    print(f"\n================ {spec.agent} — HELPFULNESS ================\n")
    print(helpfulness_rubric(spec))
    print(f"\n================ {spec.agent} — PAIRWISE ================\n")
    print(pairwise_rubric(spec))
    print()
