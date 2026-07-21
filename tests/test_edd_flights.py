"""Focused tests for Flight EDD trajectory caching and outcome policy."""

from edd.harness import Trajectory
from edd.flights import run_utils
from edd.flights.run_utils import (
    _CACHE_SOURCE_FILES,
    _load_trajectories,
    _save_trajectories,
    classify_flight_outcome,
)
from edd.flights.l3_pairwise import judge_pairwise


def test_classify_flight_outcome_completed():
    trajectory = Trajectory(
        query="flights",
        tool_outputs=[("search_flights", "Top 2 flights from AMS -> LIS")],
        final_text="Two flight options",
    )

    assert classify_flight_outcome(trajectory) == "completed"


def test_classify_flight_outcome_no_inventory():
    trajectory = Trajectory(
        query="flights",
        tool_outputs=[
            ("search_flights", "No flights found from AMS to LIS on 2026-09-10.")
        ],
        final_text="No inventory was returned.",
    )

    assert classify_flight_outcome(trajectory) == "no_inventory"


def test_classify_flight_outcome_blocked_external():
    trajectory = Trajectory(
        query="flights",
        tool_outputs=[
            (
                "search_flights",
                "Flight search error: rate limit. Unable to search flights from AMS to LIS.",
            )
        ],
    )

    assert classify_flight_outcome(trajectory) == "blocked_external"


def test_classify_flight_outcome_infra_error():
    trajectory = Trajectory(query="flights", error="timeout after 150s")

    assert classify_flight_outcome(trajectory) == "infra_error"


def test_flight_trajectory_cache_roundtrip_and_redaction(tmp_path, monkeypatch):
    path = tmp_path / "trajectories.json"
    secret = "duffel_test_configured-secret"
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", secret)
    queries = ["flights from Amsterdam to Lisbon"]
    original = [
        Trajectory(
            query=queries[0],
            tool_calls=[{"name": "search_flights", "args": {"origin": "AMS"}}],
            tool_outputs=[
                (
                    "search_flights",
                    f"Top 1 flights from AMS -> LIS; debug_token={secret}",
                )
            ],
            final_text="One flight option",
        )
    ]

    _save_trajectories(path, queries, original)
    payload = path.read_text(encoding="utf-8")
    loaded = _load_trajectories(path, queries)

    assert secret not in payload
    assert loaded is not None
    assert loaded[0].tool_outputs == [
        ("search_flights", "Top 1 flights from AMS -> LIS; debug_token=<REDACTED>")
    ]


def test_flight_cache_fingerprints_iata_repository_data():
    relative_sources = {
        path.relative_to(run_utils._ROOT).as_posix() for path in _CACHE_SOURCE_FILES
    }

    assert {
        "src/tools/iata.py",
        "src/tools/iata_repository.py",
        "src/data/iata_codes.csv",
        "src/data/iata/aliases.csv",
        "src/data/iata/primary_airports.csv",
        "src/data/iata/countries.csv",
    } <= relative_sources


async def test_run_flight_dataset_reuses_identical_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("EDD_FLIGHT_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("EDD_REFRESH", raising=False)
    calls = 0

    async def fake_run_agent(agent_cls, query, **kwargs):
        nonlocal calls
        calls += 1
        return Trajectory(
            query=query,
            tool_outputs=[("search_flights", "Top 1 flights from AMS -> LIS")],
            final_text="One flight option",
        )

    monkeypatch.setattr(run_utils, "run_agent", fake_run_agent)
    queries = ["flights from Amsterdam to Lisbon"]
    model_config = {"tier": "fast", "azure_deployment": "test-flight-model"}

    first = await run_utils.run_flight_dataset(
        queries, model_config=model_config, max_concurrency=1
    )
    second = await run_utils.run_flight_dataset(
        queries, model_config=model_config, max_concurrency=1
    )

    assert calls == 1
    assert second == first


async def test_run_flight_dataset_does_not_cache_external_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("EDD_FLIGHT_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("EDD_REFRESH", raising=False)
    calls = 0

    async def fake_run_agent(agent_cls, query, **kwargs):
        nonlocal calls
        calls += 1
        return Trajectory(
            query=query,
            tool_outputs=[
                (
                    "search_flights",
                    "Flight search error: rate limit. Unable to search flights.",
                )
            ],
            final_text="The provider is unavailable.",
        )

    monkeypatch.setattr(run_utils, "run_agent", fake_run_agent)
    queries = ["flights from Amsterdam to Lisbon"]
    model_config = {"tier": "fast", "azure_deployment": "test-flight-model"}

    await run_utils.run_flight_dataset(
        queries, model_config=model_config, max_concurrency=1
    )
    await run_utils.run_flight_dataset(
        queries, model_config=model_config, max_concurrency=1
    )

    assert calls == 2
    assert not list(tmp_path.glob("trajectories-*.json"))


async def test_pairwise_skips_provider_blocked_arm():
    blocked = Trajectory(
        query="flights",
        tool_outputs=[
            (
                "search_flights",
                "Flight search error: unauthorized. Unable to search flights.",
            )
        ],
        final_text="The provider is unavailable.",
    )
    completed = Trajectory(
        query="flights",
        tool_outputs=[("search_flights", "Top 1 flights from AMS -> LIS")],
        final_text="One flight option",
    )

    result = await judge_pairwise(None, blocked, completed)

    assert result["winner"] is None
    assert "excluded" in result["comment"]
