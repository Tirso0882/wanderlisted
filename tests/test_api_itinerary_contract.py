"""Public typed itinerary and handbook API contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, HumanMessage

from src.api.main import ResumeRequest, _public_components, resume_chat


def test_public_components_preserve_structured_itinerary_and_handbook():
    plan = {
        "schema_version": 1,
        "start_date": "2026-09-01",
        "end_date": "2026-09-01",
        "duration_days": 1,
        "days": [{"day_number": 1, "date": "2026-09-01", "city": "paris"}],
        "artifact_fingerprint": "fingerprint",
    }
    handbook = {"title": "Paris", "days": plan["days"]}
    components = {
        "routing": ["ItineraryAgent"],
        "itinerary": {"messages": [AIMessage(content="private transcript")]},
        "itinerary_structured": plan,
        "handbook_structured": handbook,
    }

    public = _public_components(
        components,
        {
            "itinerary": {
                "component": "itinerary",
                "status": "partial",
                "request_fingerprint": "fingerprint",
            }
        },
    )

    assert "routing" not in public
    assert public["itinerary"] == {}
    assert public["itinerary_structured"] == plan
    assert public["handbook_structured"] == handbook
    assert public["component_results"]["itinerary"]["status"] == "partial"


class _ResumeGraph:
    def __init__(self) -> None:
        self.ainvoke = AsyncMock(
            return_value={
                "messages": [AIMessage(content="Handbook compiled")],
                "itinerary_components": {
                    "budget_structured": {"total": 635, "currency": "USD"},
                    "itinerary_structured": {"artifact_fingerprint": "fp"},
                    "handbook_structured": {
                        "title": "Paris",
                        "days": [
                            {
                                "day_number": 1,
                                "date": "2026-09-01",
                                "city": "paris",
                            }
                        ],
                    },
                },
                "component_results": {
                    "handbook": {
                        "component": "handbook",
                        "status": "completed",
                    }
                },
            }
        )

    async def aget_state(self, _config):
        return SimpleNamespace(values={"messages": [HumanMessage(content="plan")]})


class _AllowLimiter:
    async def check(self, _principal_id: str) -> bool:
        return True


async def test_resume_response_returns_updated_structured_handbook():
    graph = _ResumeGraph()
    request = ResumeRequest(
        session_id="session",
        decision={"gate": "human_review", "action": "approved"},
    )

    response = await resume_chat(
        request,
        owner_id="02d1e9f54ec34110bb838d7765432705",
        rate_limiter=_AllowLimiter(),
        graph=graph,
    )

    assert response.status == "completed"
    assert response.components["itinerary_structured"]["artifact_fingerprint"] == "fp"
    assert response.components["handbook_structured"]["days"][0]["city"] == "paris"
    assert response.components["component_results"]["handbook"]["status"] == (
        "completed"
    )
    assert response.budget.total == 635
