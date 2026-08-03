"""Focused tests for readiness EDD data, evaluators, harness, and policy."""

from __future__ import annotations

import re
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

from edd.readiness.l1_dataset import DATASET, DATASET_SIZE, DATASET_VERSION
from edd.readiness.l1_evaluate import (
    EVALUATORS,
    bounded_search_count,
    correct_clarification_behavior,
    correct_official_domain_policy,
    correct_topic_scope,
    destination_coverage_in_searches,
    query_intent_coverage,
)
from edd.readiness.l2_judge import FAITHFULNESS_RUBRIC
from edd.readiness.l2_judge_cases import JUDGE_CASES
from edd.readiness.l3_pairwise import HELPFULNESS_PAIRWISE_RUBRIC, judge_pairwise
from edd.readiness.run_utils import (
    _RecordingProvider,
    _load_trajectories,
    _save_trajectories,
    classify_readiness_outcome,
    run_readiness_agent,
)
from edd.harness import Trajectory
from edd.rubrics import _format_evidence, score_helpfulness
from src.readiness import (
    ReadinessEvidenceTopic,
    ReadinessIntent,
    ReadinessQuery,
    ReadinessResearchPlan,
    ReadinessRetrieval,
    ReadinessSource,
)

_EXPECTED_KEYS = {
    "destinations",
    "intents",
    "required_topics",
    "allowed_topics",
    "min_searches",
    "max_searches",
    "min_unique_topics",
    "required_query_terms",
    "official_domains",
    "clarification",
    "search_topic",
}
_VALID_TOPICS = {topic.value for topic in ReadinessEvidenceTopic}


def _choice(values: set[str]) -> str:
    return sorted(values)[0]


def _golden_calls(expected: dict) -> list[dict]:
    destinations = [_choice(group) for group in expected["destinations"]]
    intent = _choice(expected["intents"])
    if expected["clarification"]:
        return [
            {
                "name": "readiness_plan",
                "args": {
                    "destinations": [],
                    "intent": intent,
                    "queries": [],
                    "clarification_question": "Which destination should I research?",
                },
            }
        ]

    topics = [_choice(group) for group in expected["required_topics"]]
    for topic in sorted(expected["allowed_topics"]):
        if topic not in topics and len(set(topics)) < expected["min_unique_topics"]:
            topics.append(topic)
    if not topics:
        topics = [intent if intent in _VALID_TOPICS else "overview"]
    topics = topics[: expected["max_searches"]]
    destination_text = " ".join(destinations)
    intent_terms = " ".join(
        _choice(group) for group in expected.get("required_query_terms", [])
    )
    search_calls = []
    for index, topic in enumerate(topics):
        mode = expected.get("search_topic", "general") if index == 0 else "general"
        search_calls.append(
            {
                "name": "tavily_search",
                "args": {
                    "query": (
                        f"{destination_text} {topic} {intent_terms} travel information"
                    ).strip(),
                    "topic": topic,
                    "search_topic": mode,
                    "include_domains": sorted(
                        expected["official_domains"].get(topic, set())
                    ),
                    "exclude_domains": (
                        []
                        if topic in expected["official_domains"]
                        and expected["official_domains"][topic]
                        else ["tripadvisor.com"]
                    ),
                },
            }
        )
    return [
        {
            "name": "readiness_plan",
            "args": {
                "destinations": destinations,
                "intent": intent,
                "queries": [call["args"] for call in search_calls],
                "clarification_question": "",
            },
        },
        *search_calls,
    ]


def test_readiness_dataset_has_24_unique_well_formed_cases():
    assert DATASET_VERSION == "2.1.0"
    assert len(DATASET) == DATASET_SIZE == 24
    assert len({case["name"] for case in DATASET}) == DATASET_SIZE
    assert len({case["query"] for case in DATASET}) == DATASET_SIZE

    for case in DATASET:
        assert set(case) == {"name", "tags", "query", "expected"}
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["name"])
        assert case["tags"] and len(case["tags"]) == len(set(case["tags"]))
        assert case["query"].strip()

        expected = case["expected"]
        assert expected.keys() <= _EXPECTED_KEYS
        assert expected["intents"]
        assert expected["max_searches"] <= 6
        assert expected["allowed_topics"] <= _VALID_TOPICS
        assert all(group <= _VALID_TOPICS for group in expected["required_topics"])
        assert all(
            isinstance(group, set) and group for group in expected["destinations"]
        )
        assert set(expected["official_domains"]) <= {
            "safety",
            "weather",
            "health",
            "visa",
        }


def test_readiness_dataset_preserves_critical_coverage_floors():
    tags = Counter(tag for case in DATASET for tag in case["tags"])
    intents = {intent for case in DATASET for intent in case["expected"]["intents"]}

    assert {
        "overview",
        "culture",
        "safety",
        "weather",
        "entry",
        "health",
        "practical",
        "packing",
        "comprehensive",
    } <= intents
    assert tags["official-source"] >= 6
    assert tags["multi-destination"] >= 2
    assert tags["comprehensive"] >= 4
    assert tags["clarification"] == 1
    assert tags["prompt-injection"] == 1
    assert tags["conflicting-sources"] == 1


def test_every_destination_golden_plan_satisfies_evaluator_contract():
    failures = []
    for case in DATASET:
        calls = _golden_calls(case["expected"])
        for evaluator in EVALUATORS:
            result = evaluator(calls, case["expected"])
            if result["score"] == 0:
                failures.append(f"{case['name']}/{result['key']}: {result['comment']}")

    assert not failures, failures


def test_bounded_search_count_rejects_more_than_six_calls():
    expected = DATASET[17]["expected"]
    calls = _golden_calls(expected)
    search = calls[-1]
    calls.extend(
        {"name": "tavily_search", "args": {**search["args"], "query": f"extra {i}"}}
        for i in range(7)
    )

    result = bounded_search_count(calls, expected)

    assert result["score"] == 0
    assert "got" in result["comment"]


def test_focused_topic_scope_rejects_unrelated_research():
    expected = DATASET[0]["expected"]
    calls = _golden_calls(expected)
    calls.append(
        {
            "name": "tavily_search",
            "args": {
                **calls[-1]["args"],
                "query": "Tokyo hotel prices",
                "topic": "costs",
            },
        }
    )

    result = correct_topic_scope(calls, expected)

    assert result["score"] == 0
    assert "costs" in result["comment"]


def test_official_policy_rejects_general_safety_domains():
    expected = DATASET[2]["expected"]
    calls = _golden_calls(expected)
    calls[-1]["args"]["include_domains"] = ["travel-blog.example"]

    result = correct_official_domain_policy(calls, expected)

    assert result["score"] == 0
    assert "safety domains" in result["comment"]


def test_multi_destination_coverage_requires_every_destination():
    expected = DATASET[20]["expected"]
    calls = _golden_calls(expected)
    for call in calls:
        if call["name"] == "tavily_search":
            call["args"]["query"] = call["args"]["query"].replace("cancun", "")

    result = destination_coverage_in_searches(calls, expected)

    assert result["score"] == 0
    assert "canc" in result["comment"]


def test_focused_query_must_preserve_dining_subintent():
    expected = DATASET[0]["expected"]
    calls = _golden_calls(expected)
    calls[-1]["args"]["query"] = "Tokyo practical travel information"

    result = query_intent_coverage(calls, expected)

    assert result["score"] == 0
    assert "dining" in result["comment"]


def test_clarification_case_must_not_search():
    expected = DATASET[21]["expected"]
    calls = _golden_calls(expected)
    calls.append(
        {
            "name": "tavily_search",
            "args": {
                "query": "generic travel",
                "topic": "overview",
                "search_topic": "general",
                "include_domains": [],
                "exclude_domains": [],
            },
        }
    )

    result = correct_clarification_behavior(calls, expected)

    assert result["score"] == 0
    assert "without searching" in result["comment"]


class _FakeProvider:
    def __init__(self) -> None:
        self.closed = False

    async def search_many(self, queries):
        source = ReadinessSource(
            id="S1",
            title="Tokyo customs",
            url="https://example.test/tokyo",
            domain="example.test",
            snippet="Bow lightly when greeting.",
            relevance=0.9,
            query=queries[0].query,
            topic=queries[0].topic,
        )
        return ReadinessRetrieval(
            sources=[source],
            evidence_by_scope={"tokyo:culture": ["S1"]},
        )

    async def aclose(self):
        self.closed = True


async def test_recording_provider_delegates_cleanup():
    provider = _FakeProvider()
    recording_provider = _RecordingProvider(provider)

    await recording_provider.aclose()

    assert provider.closed is True


class _FakePipeline:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def _plan(self, question, trip_request):
        return ReadinessResearchPlan(
            destinations=["tokyo"],
            intent=ReadinessIntent.CULTURE,
            queries=[
                ReadinessQuery(
                    destination="tokyo",
                    query="Tokyo etiquette",
                    topic=ReadinessEvidenceTopic.CULTURE,
                )
            ],
        )


class _FakeReadinessAgent:
    last_provider = None

    def __init__(self, synthesis_llm=None):
        self.provider = _FakeProvider()
        type(self).last_provider = self.provider
        self.pipeline = _FakePipeline(self.provider)

    async def research(self, *, question, trip_request):
        plan = await self.pipeline._plan(question, trip_request)
        retrieval = await self.pipeline.provider.search_many(plan.queries)
        assert retrieval.sources
        return SimpleNamespace(message="Tokyo etiquette [S1].")


async def test_readiness_harness_projects_fixed_pipeline_into_trajectory(monkeypatch):
    monkeypatch.setattr("edd.readiness.run_utils.get_llm", lambda **kwargs: object())

    trajectory = await run_readiness_agent(_FakeReadinessAgent, "Tokyo etiquette")

    assert trajectory.error is None
    assert [call["name"] for call in trajectory.tool_calls] == [
        "readiness_plan",
        "tavily_search",
    ]
    assert trajectory.tool_calls[1]["args"]["topic"] == "culture"
    assert '"id": "S1"' in trajectory.tool_outputs[0][1]
    assert trajectory.final_text == "Tokyo etiquette [S1]."
    assert _FakeReadinessAgent.last_provider.closed is True


def test_classify_readiness_outcomes():
    assert (
        classify_readiness_outcome(
            Trajectory(
                query="Tokyo",
                tool_calls=[{"name": "tavily_search", "args": {}}],
                tool_outputs=[("tavily_search", '[{"id":"S1"}]')],
                final_text="Answer",
            )
        )
        == "completed"
    )
    assert (
        classify_readiness_outcome(
            Trajectory(
                query="Tokyo",
                tool_calls=[{"name": "tavily_search", "args": {}}],
                tool_outputs=[("tavily_search", "[]")],
                final_text="No evidence.",
            )
        )
        == "no_evidence"
    )
    assert (
        classify_readiness_outcome(
            Trajectory(query="Tell me about it", final_text="Which destination?")
        )
        == "needs_clarification"
    )
    assert (
        classify_readiness_outcome(
            Trajectory(query="Tokyo", error="TavilyAuthenticationError: HTTP 401")
        )
        == "blocked_external"
    )
    assert (
        classify_readiness_outcome(
            Trajectory(query="Tokyo", error="ValueError: invalid report")
        )
        == "infra_error"
    )


def test_readiness_trajectory_cache_roundtrip_and_redaction(tmp_path, monkeypatch):
    path = tmp_path / "trajectories.json"
    secret = "configured-tavily-key"
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    trajectory = Trajectory(
        query="Tokyo",
        tool_calls=[{"name": "tavily_search", "args": {"query": "Tokyo"}}],
        tool_outputs=[
            ("tavily_search", f"[{ {'url': f'https://example.test?key={secret}'} }]")
        ],
        final_text=f"Source: https://example.test?api_key={secret}",
    )

    _save_trajectories(path, [trajectory.query], [trajectory])
    payload = path.read_text(encoding="utf-8")
    loaded = _load_trajectories(path, [trajectory.query])

    assert secret not in payload
    assert loaded is not None
    assert secret not in loaded[0].tool_outputs[0][1]
    assert secret not in loaded[0].final_text


def test_readiness_judge_cases_are_balanced_and_held_out():
    labels = Counter(case["expected"] for case in JUDGE_CASES)

    assert len(JUDGE_CASES) == 24
    assert len({case["name"] for case in JUDGE_CASES}) == 24
    assert labels == {0: 6, 1: 6, 2: 6, 3: 6}
    assert "MTSA-17" in FAITHFULNESS_RUBRIC
    corpus = "\n".join(
        case["trajectory"].query
        + case["trajectory"].final_text
        + "".join(output for _, output in case["trajectory"].tool_outputs)
        for case in JUDGE_CASES
    )
    assert "MTSA-17" not in corpus
    assert "Valletta" not in corpus


async def test_readiness_pairwise_skips_provider_blocked_arm():
    blocked = Trajectory(
        query="Tokyo",
        error="TavilyRateLimitError: Tavily rate limit (HTTP 429)",
    )
    completed = Trajectory(
        query="Tokyo",
        tool_calls=[{"name": "tavily_search", "args": {}}],
        tool_outputs=[("tavily_search", '[{"id":"S1"}]')],
        final_text="Grounded answer [S1].",
    )

    result = await judge_pairwise(None, blocked, completed)

    assert result["winner"] is None
    assert "excluded" in result["comment"]


def test_readiness_pairwise_rubric_requires_material_difference():
    assert "MATERIAL-DIFFERENCE RULE" in HELPFULNESS_PAIRWISE_RUBRIC
    assert "Return `tie` when advantages are minor or offsetting" in (
        HELPFULNESS_PAIRWISE_RUBRIC
    )


def test_readiness_evidence_formatter_can_preserve_citation_urls():
    trajectory = Trajectory(
        query="Tokyo",
        tool_outputs=[
            (
                "tavily_search",
                '[{"id":"S1","url":"https://example.test/tokyo"}]',
            )
        ],
        final_text="Tokyo [S1](https://example.test/tokyo).",
    )

    compact = _format_evidence(trajectory)
    readiness_evidence = _format_evidence(trajectory, preserve_urls=True)

    assert "<URL>" in compact
    assert "https://example.test/tokyo" in readiness_evidence


async def test_judge_retries_transient_connection_error(monkeypatch):
    class APIConnectionError(Exception):
        pass

    judge = SimpleNamespace(
        ainvoke=AsyncMock(
            side_effect=[
                APIConnectionError("Connection error."),
                SimpleNamespace(score=3, reasoning="Direct and useful."),
            ]
        )
    )
    sleep = AsyncMock()
    monkeypatch.setattr("edd.rubrics.asyncio.sleep", sleep)

    result = await score_helpfulness(
        judge,
        Trajectory(query="Tokyo readiness", final_text="Check entry rules."),
        rubric="helpfulness rubric",
    )

    assert result == {
        "key": "helpfulness",
        "score": 3,
        "comment": "Direct and useful.",
    }
    assert judge.ainvoke.await_count == 2
    sleep.assert_awaited_once_with(1)


async def test_judge_error_reports_exception_chain_after_retries(monkeypatch):
    class APIConnectionError(Exception):
        pass

    root = ConnectionError("DNS lookup failed")
    failure = APIConnectionError("Connection error.")
    failure.__cause__ = root
    judge = SimpleNamespace(ainvoke=AsyncMock(side_effect=failure))
    monkeypatch.setattr("edd.rubrics.asyncio.sleep", AsyncMock())

    result = await score_helpfulness(
        judge,
        Trajectory(query="Tokyo readiness", final_text="Check entry rules."),
        rubric="helpfulness rubric",
    )

    assert result["score"] is None
    assert "APIConnectionError: Connection error." in result["comment"]
    assert "ConnectionError: DNS lookup failed" in result["comment"]
    assert judge.ainvoke.await_count == 3
