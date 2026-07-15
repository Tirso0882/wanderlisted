"""Regression tests for ``_extract_text_content``.

Guards the documented Responses-API content-shape bug: when
``use_responses_api=True`` (all gpt-5.4 tiers), ``message.content`` is a
``list[dict]`` of blocks, not a ``str``. Callers that read ``.content``
directly get a list and break; the helper must flatten those blocks to text.

Two copies of the helper exist — the canonical one in ``stage4_graph`` and a
duplicate in ``api/main`` — and they MUST behave identically.

See: .github/skills/responses-api-reasoning/SKILL.md
"""

import pytest

from src.agent.stage4_graph import _extract_text_content as extract_graph
from src.api.main import _extract_text_content as extract_api

# The two copies under test — parametrizing over both keeps them in sync.
_IMPLS = [
    pytest.param(extract_graph, id="stage4_graph"),
    pytest.param(extract_api, id="api_main"),
]

# (input, expected) — the contract both copies must satisfy.
_CASES = [
    # Chat Completions: a plain string passes through unchanged.
    ("hello world", "hello world"),
    ("", ""),
    # Responses API: a list of text blocks is flattened and space-joined.
    ([{"type": "text", "text": "Bonjour"}], "Bonjour"),
    (
        [{"type": "text", "text": "Bonjour"}, {"type": "text", "text": "Paris"}],
        "Bonjour Paris",
    ),
    # Non-text blocks (tool calls, images, reasoning) are skipped.
    (
        [
            {"type": "text", "text": "Weather"},
            {"type": "tool_use", "name": "get_weather"},
            {"type": "text", "text": "Paris"},
        ],
        "Weather Paris",
    ),
    ([{"type": "reasoning", "summary": "thinking"}], ""),
    # Empty text blocks contribute nothing (no stray separators).
    ([{"type": "text", "text": ""}, {"type": "text", "text": "hi"}], "hi"),
    # Empty list and None degrade to an empty string, never raise.
    ([], ""),
    (None, ""),
]


class TestExtractTextContent:
    @pytest.mark.parametrize("extract", _IMPLS)
    @pytest.mark.parametrize("content, expected", _CASES)
    def test_contract(self, extract, content, expected):
        assert extract(content) == expected

    @pytest.mark.parametrize(
        "content",
        [
            "plain string",
            [{"type": "text", "text": "a"}, {"type": "text", "text": ""}],
            [{"type": "image_url", "image_url": {"url": "x"}}],
            [{"type": "text", "text": "x"}, {"type": "other"}],
            [],
            None,
            123,  # unknown scalar -> str() fallback
        ],
    )
    def test_both_copies_stay_in_sync(self, content):
        # The duplicated implementations must never drift apart.
        assert extract_graph(content) == extract_api(content)
