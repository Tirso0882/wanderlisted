"""Layer 1 deterministic evaluators for readiness research decisions."""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.readiness import ReadinessEvidenceTopic

_PLAN_CALL = "readiness_plan"
_SEARCH_CALL = "tavily_search"
_VALID_TOPICS = {topic.value for topic in ReadinessEvidenceTopic}
_VALID_SEARCH_TOPICS = {"general", "news"}


def _plan_calls(trajectory: list[dict]) -> list[dict]:
    return [call for call in trajectory if call.get("name") == _PLAN_CALL]


def _search_calls(trajectory: list[dict]) -> list[dict]:
    return [call for call in trajectory if call.get("name") == _SEARCH_CALL]


def _normalise(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _matches(actual: object, choices: set[str]) -> bool:
    actual_text = f" {_normalise(actual)} "
    return any(
        f" {_normalise(choice)} " in actual_text
        or actual_text.strip() in _normalise(choice)
        for choice in choices
    )


def captured_research_plan(trajectory: list[dict], expected: dict) -> dict:
    count = len(_plan_calls(trajectory))
    return {
        "key": "captured_research_plan",
        "score": int(count == 1),
        "comment": "" if count == 1 else f"expected one research plan, got {count}",
    }


def correct_intent(trajectory: list[dict], expected: dict) -> dict:
    plans = _plan_calls(trajectory)
    if not plans:
        return {"key": "correct_intent", "score": 0, "comment": "no research plan"}
    actual = str(plans[-1].get("args", {}).get("intent") or "")
    valid = actual in expected["intents"]
    return {
        "key": "correct_intent",
        "score": int(valid),
        "comment": ""
        if valid
        else f"intent {actual!r} not in {sorted(expected['intents'])}",
    }


def correct_destinations(trajectory: list[dict], expected: dict) -> dict:
    plans = _plan_calls(trajectory)
    if not plans:
        return {
            "key": "correct_destinations",
            "score": 0,
            "comment": "no research plan",
        }
    actual = plans[-1].get("args", {}).get("destinations", [])
    expected_groups = expected["destinations"]
    missing = [
        sorted(group)
        for group in expected_groups
        if not any(_matches(destination, group) for destination in actual)
    ]
    unexpected = [
        destination
        for destination in actual
        if not any(_matches(destination, group) for group in expected_groups)
    ]
    valid = not missing and not unexpected and len(actual) == len(expected_groups)
    return {
        "key": "correct_destinations",
        "score": int(valid),
        "comment": "" if valid else f"missing={missing}; unexpected={unexpected}",
    }


def correct_clarification_behavior(trajectory: list[dict], expected: dict) -> dict:
    plans = _plan_calls(trajectory)
    if not plans:
        return {
            "key": "correct_clarification_behavior",
            "score": 0,
            "comment": "no research plan",
        }
    plan = plans[-1].get("args", {})
    searches = _search_calls(trajectory)
    clarification = str(plan.get("clarification_question") or "").strip()
    if expected["clarification"]:
        valid = bool(clarification) and not plan.get("destinations") and not searches
        comment = (
            "" if valid else "missing-destination case must clarify without searching"
        )
    else:
        valid = (
            bool(plan.get("destinations"))
            and not clarification
            and len(searches) >= int(expected.get("min_searches", 1))
        )
        comment = (
            "" if valid else "research case must plan destinations and Tavily searches"
        )
    return {
        "key": "correct_clarification_behavior",
        "score": int(valid),
        "comment": comment,
    }


def bounded_search_count(trajectory: list[dict], expected: dict) -> dict:
    count = len(_search_calls(trajectory))
    maximum = min(int(expected["max_searches"]), 6)
    minimum = 0 if expected["clarification"] else int(expected.get("min_searches", 1))
    valid = minimum <= count <= maximum
    return {
        "key": "bounded_search_count",
        "score": int(valid),
        "comment": ""
        if valid
        else f"expected {minimum}-{maximum} searches, got {count}",
    }


def correct_topic_scope(trajectory: list[dict], expected: dict) -> dict:
    topics = [
        str(call.get("args", {}).get("topic") or "")
        for call in _search_calls(trajectory)
    ]
    if expected["clarification"]:
        return {
            "key": "correct_topic_scope",
            "score": int(not topics),
            "comment": ""
            if not topics
            else f"clarification unexpectedly searched {topics}",
        }
    topic_set = set(topics)
    missing = [
        sorted(group)
        for group in expected["required_topics"]
        if topic_set.isdisjoint(group)
    ]
    allowed = expected["allowed_topics"]
    unexpected = sorted(topic_set - allowed) if allowed else []
    enough = len(topic_set) >= expected["min_unique_topics"]
    valid = not missing and not unexpected and enough
    return {
        "key": "correct_topic_scope",
        "score": int(valid),
        "comment": ""
        if valid
        else (
            f"missing topic groups={missing}; unexpected={unexpected}; "
            f"unique={len(topic_set)}/{expected['min_unique_topics']}"
        ),
    }


def correct_search_mode(trajectory: list[dict], expected: dict) -> dict:
    required = expected.get("search_topic")
    if required is None:
        return {"key": "correct_search_mode", "score": None, "comment": "no reference"}
    modes = [
        str(call.get("args", {}).get("search_topic") or "")
        for call in _search_calls(trajectory)
    ]
    valid = required in modes
    return {
        "key": "correct_search_mode",
        "score": int(valid),
        "comment": ""
        if valid
        else f"expected at least one {required!r} search, got {modes}",
    }


def correct_official_domain_policy(trajectory: list[dict], expected: dict) -> dict:
    policy = expected["official_domains"]
    if not policy:
        return {
            "key": "correct_official_domain_policy",
            "score": None,
            "comment": "no sensitive-topic reference",
        }
    problems = []
    calls = _search_calls(trajectory)
    for topic, required in policy.items():
        topic_calls = [
            call for call in calls if call.get("args", {}).get("topic") == topic
        ]
        if not topic_calls:
            problems.append(f"no {topic} search")
            continue
        for call in topic_calls:
            actual = set(call.get("args", {}).get("include_domains") or [])
            if actual != required:
                problems.append(
                    f"{topic} domains {sorted(actual)} != {sorted(required)}"
                )
    return {
        "key": "correct_official_domain_policy",
        "score": int(not problems),
        "comment": "; ".join(problems),
    }


def destination_coverage_in_searches(trajectory: list[dict], expected: dict) -> dict:
    if expected["clarification"] or int(expected.get("min_searches", 1)) == 0:
        return {
            "key": "destination_coverage_in_searches",
            "score": None,
            "comment": "no-search contract",
        }
    search_texts = [
        call.get("args", {}).get("query", "") for call in _search_calls(trajectory)
    ]
    missing = [
        sorted(group)
        for group in expected["destinations"]
        if not any(_matches(text, group) for text in search_texts)
    ]
    return {
        "key": "destination_coverage_in_searches",
        "score": int(not missing),
        "comment": "" if not missing else f"searches missed destinations: {missing}",
    }


def query_intent_coverage(trajectory: list[dict], expected: dict) -> dict:
    """Require focused searches to preserve explicit user sub-intents."""
    required = expected.get("required_query_terms", [])
    if not required:
        return {
            "key": "query_intent_coverage",
            "score": None,
            "comment": "no query-term reference",
        }
    search_text = " ".join(
        str(call.get("args", {}).get("query") or "")
        for call in _search_calls(trajectory)
    )
    missing = [sorted(group) for group in required if not _matches(search_text, group)]
    return {
        "key": "query_intent_coverage",
        "score": int(not missing),
        "comment": "" if not missing else f"searches missed intent terms: {missing}",
    }


def no_duplicate_searches(trajectory: list[dict], expected: dict) -> dict:
    signatures = [
        json.dumps(call.get("args", {}), sort_keys=True, default=str)
        for call in _search_calls(trajectory)
    ]
    valid = len(signatures) == len(set(signatures))
    return {
        "key": "no_duplicate_searches",
        "score": int(valid),
        "comment": "" if valid else "duplicate Tavily query parameters were planned",
    }


def valid_search_parameters(trajectory: list[dict], expected: dict) -> dict:
    problems = []
    searches = _search_calls(trajectory)
    if len(searches) > 6:
        problems.append(f"global six-search limit exceeded ({len(searches)})")
    for index, call in enumerate(searches, 1):
        args = call.get("args", {})
        if (
            not isinstance(args.get("query"), str)
            or len(args.get("query", "").strip()) < 3
        ):
            problems.append(f"search {index} has no usable query")
        if args.get("topic") not in _VALID_TOPICS:
            problems.append(f"search {index} has invalid topic {args.get('topic')!r}")
        if args.get("search_topic") not in _VALID_SEARCH_TOPICS:
            problems.append(
                f"search {index} has invalid search_topic {args.get('search_topic')!r}"
            )
        for field in ("include_domains", "exclude_domains"):
            value = args.get(field)
            if not isinstance(value, list) or not all(
                isinstance(domain, str) and domain for domain in value
            ):
                problems.append(f"search {index} has invalid {field}")
    return {
        "key": "valid_search_parameters",
        "score": int(not problems),
        "comment": "; ".join(problems),
    }


EVALUATORS = [
    captured_research_plan,
    correct_intent,
    correct_destinations,
    correct_clarification_behavior,
    bounded_search_count,
    correct_topic_scope,
    correct_search_mode,
    correct_official_domain_policy,
    destination_coverage_in_searches,
    query_intent_coverage,
    no_duplicate_searches,
    valid_search_parameters,
]


GOOD_TRAJECTORY = [
    {
        "name": "readiness_plan",
        "args": {
            "destinations": ["tokyo"],
            "intent": "culture",
            "queries": [],
            "clarification_question": "",
        },
    },
    {
        "name": "tavily_search",
        "args": {
            "query": "Tokyo etiquette dining customs",
            "topic": "culture",
            "search_topic": "general",
            "include_domains": [],
            "exclude_domains": ["tripadvisor.com"],
        },
    },
]

BAD_TRAJECTORY = [
    {
        "name": "readiness_plan",
        "args": {
            "destinations": ["osaka"],
            "intent": "weather",
            "queries": [],
            "clarification_question": "",
        },
    },
    {
        "name": "tavily_search",
        "args": {
            "query": "Japan travel",
            "topic": "weather",
            "search_topic": "general",
            "include_domains": [],
            "exclude_domains": [],
        },
    },
]


if __name__ == "__main__":
    from edd.readiness.l1_dataset import DATASET

    expected = DATASET[0]["expected"]
    for label, trajectory in (("GOOD", GOOD_TRAJECTORY), ("BAD", BAD_TRAJECTORY)):
        print(f"\n{label} trajectory")
        print("-" * 68)
        for evaluator in EVALUATORS:
            result = evaluator(trajectory, expected)
            score = (
                "SKIP"
                if result["score"] is None
                else ("PASS" if result["score"] else "FAIL")
            )
            print(f"  {result['key']:36s} {score:4s}  {result['comment']}")
