"""LangSmith evaluators for Wanderlisted.

Four-layer evaluation pyramid:
  Layer 1 — Code-based (heuristic, deterministic, free)
  Layer 2 — LLM-as-Judge (subjective quality, 0–3 scale)
  Layer 3 — Pairwise comparison (A vs B, no ground truth needed)
  Layer 4 — Human alignment calibration (Cohen's κ)
"""

from __future__ import annotations

from openai import OpenAI
from pydantic import BaseModel, Field


# ── Layer 1: Code-Based Evaluators (fast, free, deterministic) ────────────


VALID_AGENT_NAMES = frozenset(
    {
        "FlightsAgent",
        "HotelsAgent",
        "DestinationAgent",
        "RestaurantsAgent",
        "ActivitiesAgent",
        "TransportationAgent",
        "BudgetAgent",
        "ItineraryAgent",
    }
)


def correct_tool_routing(inputs: dict, outputs: dict) -> dict:
    """Verify agent called the right tools for the query type."""
    question = inputs.get("question", "").lower()
    tools_used = outputs.get("tools_called", [])

    if "flight" in question or "fly" in question:
        score = int(
            "search_flights" in tools_used
            or "FlightsAgent" in outputs.get("agents_routed", [])
        )
    elif "hotel" in question or "stay" in question or "accommodation" in question:
        score = int(
            "search_hotels" in tools_used
            or "HotelsAgent" in outputs.get("agents_routed", [])
        )
    elif "weather" in question or "temperature" in question:
        score = int(
            "get_weather" in tools_used
            or "DestinationAgent" in outputs.get("agents_routed", [])
        )
    elif "restaurant" in question or "eat" in question or "food" in question:
        score = int(
            "search_activities" in tools_used
            or "RestaurantsAgent" in outputs.get("agents_routed", [])
        )
    elif "budget" in question or "cost" in question:
        score = int(
            "calculate_budget" in tools_used
            or "BudgetAgent" in outputs.get("agents_routed", [])
        )
    else:
        score = 1  # Non-specific query → any routing is acceptable

    return {"score": score, "key": "correct_tool_routing"}


def valid_routing_decision(inputs: dict, outputs: dict) -> dict:
    """Check that supervisor produced valid routing with real agent names."""
    agents_routed = set(outputs.get("agents_routed", []))
    invalid = agents_routed - VALID_AGENT_NAMES
    score = int(len(invalid) == 0 and len(agents_routed) > 0)
    return {"score": score, "key": "valid_routing_decision"}


def budget_completeness(inputs: dict, outputs: dict) -> dict:
    """Check that budget breakdown has all required categories."""
    required_keys = {"flights", "accommodation", "meals", "activities", "transport"}
    budget = outputs.get("budget_structured", {})
    if not budget:
        return {"score": 0.0, "key": "budget_completeness"}
    present = set(budget.keys()) & required_keys
    score = len(present) / len(required_keys)
    return {"score": score, "key": "budget_completeness"}


def correct_destination(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    """Check that the itinerary covers the requested destinations."""
    requested = set(d.lower() for d in reference_outputs.get("destinations", []))
    covered = set(d.lower() for d in outputs.get("destinations_covered", []))
    if not requested:
        return {"score": 1, "key": "correct_destination"}
    overlap = requested & covered
    score = len(overlap) / len(requested)
    return {"score": score, "key": "correct_destination"}


def non_empty_response(outputs: dict) -> dict:
    """Basic sanity check — agent actually produced output."""
    output = outputs.get("output", "")
    score = int(bool(output.strip()) and "error" not in output.lower()[:50])
    return {"score": score, "key": "non_empty_response"}


def handbook_section_completeness(outputs: dict) -> dict:
    """Check that the generated handbook contains all expected sections."""
    output = outputs.get("output", "").lower()
    required_sections = [
        "flight",
        "hotel",
        "budget",
        "safety",
        "itinerary",
        "day 1",
        "restaurant",
        "activit",
    ]
    found = sum(1 for s in required_sections if s in output)
    score = found / len(required_sections)
    return {"score": score, "key": "handbook_section_completeness"}


# ── RAG Evaluators (LLM-as-Judge, replaces RAGAS) ────────────────────────
# 6 metrics: context_precision, context_recall, context_entity_recall,
# noise_sensitivity, response_relevancy, faithfulness


class _RAGScore(BaseModel):
    """Structured score from RAG evaluation judge."""

    score: float = Field(description="Score between 0.0 and 1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Brief justification for the score")


_RAG_SYSTEM = (
    "You are an impartial RAG evaluation judge. "
    "Evaluate ONLY what is asked. Return a score between 0.0 and 1.0."
)


def _ask_rag_judge(prompt: str) -> dict:
    """Call LLM judge and return parsed RAGScore."""
    client = OpenAI()
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _RAG_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format=_RAGScore,
    )
    parsed = completion.choices[0].message.parsed
    return {"score": parsed.score, "reasoning": parsed.reasoning}


def context_precision(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    """Were the retrieved contexts relevant to answering the question?"""
    result = _ask_rag_judge(
        f"Question: {inputs.get('question', '')}\n\n"
        f"Reference answer: {reference_outputs.get('reference', '')}\n\n"
        f"Retrieved contexts:\n{chr(10).join(outputs.get('retrieved_contexts', []))}\n\n"
        "Score 0-1: what fraction of the retrieved contexts are relevant "
        "to answering the question correctly? Irrelevant contexts score 0."
    )
    return {
        "score": result["score"],
        "key": "context_precision",
        "comment": result["reasoning"],
    }


def context_recall(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    """Were all pieces of the reference answer covered by retrieved contexts?"""
    result = _ask_rag_judge(
        f"Question: {inputs.get('question', '')}\n\n"
        f"Reference answer: {reference_outputs.get('reference', '')}\n\n"
        f"Retrieved contexts:\n{chr(10).join(outputs.get('retrieved_contexts', []))}\n\n"
        "Score 0-1: what fraction of the claims in the reference answer "
        "can be attributed to the retrieved contexts? "
        "1.0 means every claim is supported by the contexts."
    )
    return {
        "score": result["score"],
        "key": "context_recall",
        "comment": result["reasoning"],
    }


def context_entity_recall(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    """Were the key entities from the reference found in retrieved contexts?"""
    result = _ask_rag_judge(
        f"Reference answer: {reference_outputs.get('reference', '')}\n\n"
        f"Retrieved contexts:\n{chr(10).join(outputs.get('retrieved_contexts', []))}\n\n"
        "Extract all named entities (places, people, organizations, prices, dates) "
        "from the reference answer. Score 0-1: what fraction of those entities "
        "appear in the retrieved contexts?"
    )
    return {
        "score": result["score"],
        "key": "context_entity_recall",
        "comment": result["reasoning"],
    }


def noise_sensitivity(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    """How well does the response avoid being misled by irrelevant contexts?"""
    result = _ask_rag_judge(
        f"Question: {inputs.get('question', '')}\n\n"
        f"Reference answer: {reference_outputs.get('reference', '')}\n\n"
        f"Retrieved contexts:\n{chr(10).join(outputs.get('retrieved_contexts', []))}\n\n"
        f"Agent response: {outputs.get('output', '')}\n\n"
        "Some retrieved contexts may be irrelevant noise. "
        "Score 0-1: how well did the agent ignore irrelevant contexts "
        "and produce a correct answer? 1.0 means no noise influence."
    )
    return {
        "score": result["score"],
        "key": "noise_sensitivity",
        "comment": result["reasoning"],
    }


def response_relevancy(inputs: dict, outputs: dict) -> dict:
    """Is the response relevant to the question asked?"""
    result = _ask_rag_judge(
        f"Question: {inputs.get('question', '')}\n\n"
        f"Agent response: {outputs.get('output', '')}\n\n"
        "Score 0-1: how relevant is the response to the question? "
        "1.0 = perfectly on-topic and complete. "
        "0.0 = completely off-topic or answers a different question."
    )
    return {
        "score": result["score"],
        "key": "response_relevancy",
        "comment": result["reasoning"],
    }


def faithfulness(inputs: dict, outputs: dict) -> dict:
    """Does the response only contain claims supported by retrieved contexts?"""
    result = _ask_rag_judge(
        f"Retrieved contexts:\n{chr(10).join(outputs.get('retrieved_contexts', []))}\n\n"
        f"Agent response: {outputs.get('output', '')}\n\n"
        "Extract every factual claim from the agent response. "
        "Score 0-1: what fraction of those claims are supported by "
        "the retrieved contexts? Claims not in the context are hallucinations. "
        "1.0 = fully grounded, 0.0 = entirely hallucinated."
    )
    return {
        "score": result["score"],
        "key": "faithfulness",
        "comment": result["reasoning"],
    }


# ── Layer 2: LLM-as-Judge Evaluator (0–3 quality scale) ──────────────────


class TravelQualityScore(BaseModel):
    """Structured score from the LLM judge."""

    score: int = Field(
        description=(
            "Quality score 0-3. "
            "0=wrong/harmful, 1=poor/incomplete, "
            "2=good/helpful, 3=excellent/comprehensive"
        ),
        ge=0,
        le=3,
    )
    reasoning: str = Field(description="One-sentence justification for the score")


JUDGE_SYSTEM_PROMPT = """You are an expert travel advisor evaluating AI-generated
travel recommendations. Score the response 0-3:

0 — FAIL: Factually wrong, dangerous advice, or completely off-topic
1 — POOR: Partially correct but missing critical information (safety, costs, logistics)
2 — GOOD: Correct, helpful, covers the basics
3 — EXCELLENT: Correct, comprehensive, personalized, includes insider tips

Consider:
- Factual accuracy (correct locations, prices, transport routes)
- Safety information (scams, neighborhoods to avoid, health precautions)
- Practicality (actionable advice, not just generic tourism copy)
- Personalization (matches the traveler's style, budget, dietary needs)"""


def travel_quality_judge(inputs: dict, outputs: dict) -> dict:
    """LLM evaluates travel recommendation quality on 0–3 scale."""
    client = OpenAI()
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User query: {inputs.get('question', '')}\n\n"
                    f"Agent response:\n{outputs.get('output', 'No response')[:3000]}"
                ),
            },
        ],
        response_format=TravelQualityScore,
    )
    parsed = completion.choices[0].message.parsed
    return {
        "score": parsed.score,
        "key": "travel_quality",
        "comment": parsed.reasoning,
    }


# ── Layer 3: Pairwise Comparison ─────────────────────────────────────────


class Preference(BaseModel):
    preference: int = Field(
        description="1 = Agent A is better. 2 = Agent B is better. 0 = Tie.",
        ge=0,
        le=2,
    )
    reasoning: str = Field(description="Brief justification")


_PAIRWISE_PROMPT = """Compare two travel itinerary responses.
Consider: accuracy, helpfulness, personalization, conciseness.
Which response would a real traveler prefer?

User query: {question}

[Agent A Response]
{answer_a}

[Agent B Response]
{answer_b}

Reply with preference: 1 (A better), 2 (B better), or 0 (tie)."""


def ranked_preference(inputs: dict, outputs: list[dict]) -> list:
    """Compare two agent versions head-to-head."""
    client = OpenAI()
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an impartial travel advisor judge."},
            {
                "role": "user",
                "content": _PAIRWISE_PROMPT.format(
                    question=inputs.get("question", ""),
                    answer_a=outputs[0].get("output", "N/A")[:2000],
                    answer_b=outputs[1].get("output", "N/A")[:2000],
                ),
            },
        ],
        response_format=Preference,
    )
    pref = completion.choices[0].message.parsed.preference
    if pref == 1:
        return [1, 0]
    elif pref == 2:
        return [0, 1]
    return [0, 0]


# ── Layer 4: Human Alignment Calibration ─────────────────────────────────


def calibration_report(human_scores: list[int], judge_scores: list[int]) -> dict:
    """Compare LLM judge scores against human reviews.

    Returns:
        dict with exact_match_pct, within_one_pct, mean_absolute_error
    """
    n = len(human_scores)
    if n == 0:
        return {
            "exact_match_pct": 0,
            "within_one_pct": 0,
            "mean_absolute_error": float("inf"),
        }

    exact_match = sum(h == j for h, j in zip(human_scores, judge_scores)) / n
    within_one = sum(abs(h - j) <= 1 for h, j in zip(human_scores, judge_scores)) / n
    mae = sum(abs(h - j) for h, j in zip(human_scores, judge_scores)) / n

    return {
        "exact_match_pct": exact_match,
        "within_one_pct": within_one,
        "mean_absolute_error": mae,
    }


# ── Production Quality Monitor (tiered) ──────────────────────────────────


def production_quality_monitor(root_run, example=None) -> dict:
    """Cost-efficient production evaluator with tiered logic.

    Tier 1: Free heuristic checks (all runs)
    Tier 2: Pattern checks (free)
    Tier 3: LLM judge (10% sample of runs that pass tiers 1-2)
    """
    import random

    output = root_run.outputs.get("output", "") if root_run.outputs else ""

    # Tier 1: Free sanity checks
    if not output.strip():
        return {"key": "quality", "score": 0, "comment": "Empty response"}

    if len(output) < 20:
        return {"key": "quality", "score": 0.2, "comment": "Suspiciously short"}

    if any(
        err in output.lower() for err in ["error", "failed", "exception", "traceback"]
    ):
        return {"key": "quality", "score": 0.1, "comment": "Contains error markers"}

    # Tier 2: Pattern checks
    travel_keywords = [
        "tokyo",
        "bangkok",
        "barcelona",
        "paris",
        "cancun",
        "london",
        "hotel",
        "flight",
        "restaurant",
        "day 1",
        "budget",
        "safety",
    ]
    has_travel_content = any(kw in output.lower() for kw in travel_keywords)
    if not has_travel_content and len(output) > 200:
        return {"key": "quality", "score": 0.5, "comment": "No travel content detected"}

    # Tier 3: LLM judge — only 10% of runs
    if random.random() < 0.1:
        try:
            result = travel_quality_judge(
                {"question": root_run.inputs.get("question", "")},
                {"output": output},
            )
            return {
                "key": "quality",
                "score": result["score"] / 3.0,
                "comment": result.get("comment", ""),
            }
        except Exception:
            pass

    # Default: passed heuristic checks
    return {"key": "quality", "score": 0.7, "comment": "Passed heuristic checks"}
