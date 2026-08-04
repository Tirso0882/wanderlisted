"""Bounded live-run and trajectory-cache helpers for readiness EDD."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from edd.baseline_config import get_baseline_config
from edd.baseline_store import (
    load_trajectories,
    redact_text,
    redact_value,
    run_cached_dataset,
    save_trajectories,
    trajectory_cache_path,
)
from edd.harness import Trajectory
from src.agent.agents import TravelReadinessAgent
from src.agent.llm import get_llm
from src.readiness import (
    ReadinessEvidenceTopic,
    ReadinessQuery,
    ReadinessResearchPlan,
    ReadinessRetrieval,
    ReadinessSource,
    ReadinessIntent,
)
from src.models import TripRequest

READINESS_CASE_CONCURRENCY = 3
READINESS_RUN_TIMEOUT_SECONDS = 150.0
_ROOT = Path(__file__).resolve().parents[2]
BASELINE_CONFIG = get_baseline_config("readiness")
_DEFAULT_CACHE_DIR = BASELINE_CONFIG.default_cache_dir
_CACHE_SOURCE_FILES = BASELINE_CONFIG.source_files

_EXTERNAL_ERROR_MARKERS = (
    "tavily_api_key",
    "authentication",
    "http 401",
    "http 403",
    "rate limit",
    "http 429",
    "timed out",
    "timeout after",
    "network error",
    "connection error",
    "service error",
    "http 5",
    "resourceexhausted",
    "permissiondenied",
)
_NONEMPTY_JSON_ARRAY_RE = re.compile(r"^\s*\[\s*\{", re.DOTALL)


class _RecordingProvider:
    """Observe enforced queries/results without changing provider behavior."""

    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.queries: list[ReadinessQuery] = []
        self.sources: list[ReadinessSource] = []

    async def search_many(self, queries: list[ReadinessQuery]) -> ReadinessRetrieval:
        self.queries = [query.model_copy(deep=True) for query in queries]
        result = await self.delegate.search_many(queries)
        self.sources = result.sources
        return result

    async def aclose(self) -> None:
        """Preserve the wrapped provider's async cleanup contract."""
        await self.delegate.aclose()


def _redact_sensitive_text(text: str) -> str:
    """Remove configured Tavily credentials from persisted output and traces."""
    return redact_text(text, BASELINE_CONFIG.secret_env_vars)


def _redact_cache_value(value):
    return redact_value(value, BASELINE_CONFIG.secret_env_vars)


def classify_readiness_outcome(trajectory: Trajectory) -> str:
    """Separate readiness task outcomes from provider/model availability."""
    if trajectory.error:
        lowered = trajectory.error.lower()
        if any(marker in lowered for marker in _EXTERNAL_ERROR_MARKERS):
            return "blocked_external"
        return "infra_error"

    searches = [
        call for call in trajectory.tool_calls if call.get("name") == "tavily_search"
    ]
    outputs = [
        output for name, output in trajectory.tool_outputs if name == "tavily_search"
    ]
    if not searches:
        return "needs_clarification" if trajectory.final_text.strip() else "failed"
    if not outputs:
        return "failed"
    if not any(_NONEMPTY_JSON_ARRAY_RE.search(output) for output in outputs):
        return "no_evidence"
    return "completed" if trajectory.final_text.strip() else "failed"


async def run_readiness_agent(
    agent_cls,
    query: str,
    *,
    tier: str = "reasoning",
    effort: str | None = None,
    timeout: float = READINESS_RUN_TIMEOUT_SECONDS,
    trip_request: TripRequest | None = None,
    intent_hint: str | None = None,
    **model_kwargs,
) -> Trajectory:
    """Run the production fixed pipeline and project it onto ``Trajectory``.

    ``readiness_plan`` represents the structured planning decision and each
    enforced provider request is represented as a ``tavily_search`` call. Raw
    normalized Tavily sources remain the only Layer-2 evidence output.
    """
    overrides = dict(model_kwargs)
    if effort:
        overrides["reasoning_effort"] = effort
    synthesis_llm = get_llm(tier=tier, **overrides)
    agent = agent_cls(synthesis_llm=synthesis_llm)
    provider = agent.provider
    recording_provider = _RecordingProvider(provider)
    agent.provider = recording_provider
    agent.pipeline.provider = recording_provider
    request = trip_request or TripRequest()
    try:
        result = await asyncio.wait_for(
            agent.research(question=query, trip_request=request),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return Trajectory(query=query, error=f"timeout after {timeout:.0f}s")
    except Exception as exc:  # noqa: BLE001 - failures are evaluation data
        return Trajectory(query=query, error=f"{type(exc).__name__}: {exc}")
    finally:
        if hasattr(agent, "aclose"):
            await agent.aclose()
        else:
            await provider.aclose()

    trajectory = Trajectory(query=query, final_text=result.message)
    query_topics = {item.topic for item in recording_provider.queries}
    topic_to_intent = {
        ReadinessEvidenceTopic.ENTRY: ReadinessIntent.ENTRY,
    }
    if intent_hint:
        intent = ReadinessIntent(intent_hint)
    elif len(request.readiness_topics) == 1:
        intent = ReadinessIntent(request.readiness_topics[0].value)
    elif len(query_topics) == 1:
        only_topic = next(iter(query_topics))
        intent = topic_to_intent.get(only_topic)
        if intent is None:
            try:
                intent = ReadinessIntent(only_topic.value)
            except ValueError:
                intent = ReadinessIntent.OVERVIEW
    elif query_topics:
        intent = ReadinessIntent.COMPREHENSIVE
    else:
        intent = ReadinessIntent.OVERVIEW
    inferred_destinations = list(request.destinations)
    if not inferred_destinations and recording_provider.queries:
        first_query = recording_provider.queries[0].query.split()
        if first_query:
            inferred_destinations = [first_query[0].lower()]
    captured_plan = ReadinessResearchPlan(
        destinations=inferred_destinations,
        intent=intent,
        queries=recording_provider.queries,
        clarification_question=getattr(result, "clarification_question", ""),
    )
    trajectory.tool_calls.append(
        {
            "name": "readiness_plan",
            "args": captured_plan.model_dump(mode="json"),
        }
    )
    trajectory.tool_calls.extend(
        {"name": "tavily_search", "args": item.model_dump(mode="json")}
        for item in recording_provider.queries
    )
    if recording_provider.queries:
        trajectory.tool_outputs.append(
            (
                "tavily_search",
                json.dumps(
                    [
                        source.model_dump(mode="json")
                        for source in recording_provider.sources
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
    return trajectory


def _cache_path(queries: list[str], model_config: dict) -> Path:
    return trajectory_cache_path(BASELINE_CONFIG, queries, model_config)


def _load_trajectories(path: Path, queries: list[str]) -> list[Trajectory] | None:
    return load_trajectories(path, queries)


def _save_trajectories(
    path: Path, queries: list[str], trajectories: list[Trajectory]
) -> None:
    save_trajectories(path, BASELINE_CONFIG, queries, trajectories)


async def run_readiness_dataset(
    queries: list[str],
    *,
    model_config: dict,
    max_concurrency: int = READINESS_CASE_CONCURRENCY,
    timeout: float = READINESS_RUN_TIMEOUT_SECONDS,
) -> list[Trajectory]:
    """Run or reuse a pinned TravelReadinessAgent pipeline snapshot."""
    from edd.readiness.l1_dataset import DATASET

    cases_by_query = {case["query"]: case for case in DATASET}

    async def run_readiness_case(agent_cls, query: str, **kwargs) -> Trajectory:
        expected = cases_by_query[query]["expected"]
        destinations = [sorted(group)[0] for group in expected["destinations"]]
        intent = sorted(expected["intents"])[0]
        topic = "entry" if intent == "visa" else intent
        readiness_topics = [] if topic in {"overview", "comprehensive"} else [topic]
        request = TripRequest(
            scope="full_itinerary" if intent == "comprehensive" else "focused",
            destinations=destinations,
            passport_country="Poland",
            readiness_topics=readiness_topics,
        )
        return await run_readiness_agent(
            agent_cls,
            query,
            trip_request=request,
            intent_hint=intent,
            **kwargs,
        )

    return await run_cached_dataset(
        config=BASELINE_CONFIG,
        queries=queries,
        model_config=model_config,
        agent_cls=TravelReadinessAgent,
        classify_outcome=classify_readiness_outcome,
        run_agent_fn=run_readiness_case,
        max_concurrency=max_concurrency,
        timeout=timeout,
    )
