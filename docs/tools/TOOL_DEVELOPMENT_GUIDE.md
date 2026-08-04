# Tool Development Guide

> How to add a new LangChain tool to Wanderlisted — from code to agent wiring to tests.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step-by-Step Guide](#step-by-step-guide)
  - [1. Create the tool module](#1-create-the-tool-module)
  - [2. Wire it into an agent](#2-wire-it-into-an-agent)
  - [3. Update the agent prompt](#3-update-the-agent-prompt)
  - [4. Write tests](#4-write-tests)
  - [5. Add configuration](#5-add-configuration)
  - [6. Update documentation](#6-update-documentation)
- [Tool Template](#tool-template)
- [Conventions & Patterns](#conventions--patterns)
- [Checklist](#checklist)

---

## Overview

Every tool in Wanderlisted is a standalone async Python function decorated with `@tool` from `langchain_core.tools`. Tools are the **bridge between the LLM and the outside world** — they let agents call APIs, compute results, and retrieve data.

```
Agent (LLM) ──calls──→ @tool function ──calls──→ External API / database / computation
                            │
                     returns string result
                            │
Agent (LLM) ←──observes────┘
```

Tools live in `src/tools/`, one file per external API or capability group.

---

## Prerequisites

Before creating a tool, understand:

- **Python 3.12+** — use modern type hints (`list[str]`, `dict[str, Any]`, `X | None`)
- **`@tool` decorator** — from `langchain_core.tools`, converts a function into a LangChain tool
- **Async by default** — all HTTP-calling tools must be `async def`
- **`httpx.AsyncClient`** — our HTTP client (not `requests`)
- **`tenacity`** — retry decorator for transient failures
- **`AppLogger`** — our logging system (not `print()` or bare `logging`)

---

## Step-by-Step Guide

### 1. Create the tool module

Create `src/tools/<your_tool>.py`:

```python
"""Short description of what this tool does."""

import os
import httpx
from langchain_core.tools import tool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from custom_logging import AppLogger

logger = AppLogger(logger_name="tools.<your_tool>", level="DEBUG")


def _build_headers() -> dict[str, str]:
    """Build authentication headers."""
    api_key = os.environ.get("YOUR_API_KEY", "")
    if not api_key:
        raise RuntimeError("YOUR_API_KEY environment variable must be set")
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
)
async def _call_api(param1: str, param2: str) -> dict:
    """Internal API call with retry logic."""
    url = "https://api.example.com/v1/endpoint"
    headers = _build_headers()

    logger.debug("Calling API: %s %s", param1, param2)

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params={"q": param1}, timeout=15.0)
        resp.raise_for_status()

    return resp.json()


@tool
async def your_tool_name(
    param1: str,
    param2: str = "default",
) -> str:
    """One-line description shown to the LLM when it decides which tool to call.

    More detailed description of what this tool does, when to use it,
    and what it returns.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: "default")
    """
    try:
        data = await _call_api(param1, param2)
    except httpx.HTTPStatusError as e:
        logger.error("API HTTP error %s: %s", e.response.status_code, e.response.text[:300])
        return f"API error (HTTP {e.response.status_code})."
    except httpx.RequestError as e:
        logger.error("API request error: %s", e)
        return f"Could not reach API: {e}"
    except RuntimeError as e:
        return str(e)

    if not data:
        return "No results found."

    # Format results as readable text for the LLM
    lines = ["Results:\n"]
    for item in data.get("results", [])[:5]:
        lines.append(f"  - {item.get('name', 'Unknown')}: {item.get('value', 'N/A')}")

    return "\n".join(lines)
```

**Key design decisions:**
- The `@tool` function returns a **string** — the LLM reads text, not structured data
- Internal API calls are **separate functions** with retry decorators
- Authentication is in a **helper function**, credentials from environment variables
- Error handling returns **user-friendly messages**, not stack traces
- Results are **formatted for readability**, not raw JSON

### 2. Wire it into an agent

Edit the appropriate agent class in `src/agent/agents/`:

```python
# src/agent/agents/<relevant>_agent.py

from src.tools.your_tool import your_tool_name

class RelevantAgent(SpecializedAgent):
    @property
    def tools(self):
        return [
            existing_tool,
            your_tool_name,  # ← Add here
        ]
```

If your tool doesn't fit an existing agent, create a new one:

```python
# src/agent/agents/new_agent.py

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import NEW_AGENT_SYSTEM_PROMPT
from src.tools.your_tool import your_tool_name


class NewAgent(SpecializedAgent):
    name = "NewAgent"
    description = "Expert in <domain>"

    @property
    def tools(self):
        return [your_tool_name]

    @property
    def system_prompt(self) -> str:
        return NEW_AGENT_SYSTEM_PROMPT
```

Then register it in `src/agent/agents/__init__.py` and update `config/config.yaml` routing.

### 3. Update the agent prompt

Edit `src/agent/prompts/agent_prompt.py` to tell the agent **when and how** to use the new tool:

```python
RELEVANT_SYSTEM_PROMPT = """...

Your tools:
...
N. your_tool_name — What it does, when to use it, what it returns.
   Accepts: param1 (required), param2 (optional, default "default").
   Example usage scenario: "When the user asks about X, call this tool with Y."

...
"""
```

**Prompt tips:**
- Be explicit about **when** to call the tool vs. other tools
- Include the parameter names and types the LLM should pass
- Mention any **dependencies** (e.g., "Call lookup_iata_code first if you have a city name")
- Note what the output looks like so the LLM knows how to interpret it

### 4. Write tests

Create `tests/test_<your_tool>.py`:

```python
"""Unit tests for <your_tool> — mocked HTTP responses."""

import json
import respx
from httpx import Response
from src.tools.your_tool import your_tool_name


_MOCK_SUCCESS_RESPONSE = {
    "results": [{"name": "Test Item", "value": "42"}]
}

_MOCK_EMPTY_RESPONSE = {"results": []}


class TestYourTool:
    @respx.mock
    async def test_returns_results(self, monkeypatch):
        monkeypatch.setenv("YOUR_API_KEY", "test-key")

        respx.get("https://api.example.com/v1/endpoint").mock(
            return_value=Response(200, json=_MOCK_SUCCESS_RESPONSE)
        )

        result = await your_tool_name.ainvoke({"param1": "test"})

        assert "Test Item" in result
        assert "42" in result

    @respx.mock
    async def test_empty_results(self, monkeypatch):
        monkeypatch.setenv("YOUR_API_KEY", "test-key")

        respx.get("https://api.example.com/v1/endpoint").mock(
            return_value=Response(200, json=_MOCK_EMPTY_RESPONSE)
        )

        result = await your_tool_name.ainvoke({"param1": "test"})

        assert "No results" in result

    @respx.mock
    async def test_http_error(self, monkeypatch):
        monkeypatch.setenv("YOUR_API_KEY", "test-key")

        respx.get("https://api.example.com/v1/endpoint").mock(
            return_value=Response(500, text="Server error")
        )

        result = await your_tool_name.ainvoke({"param1": "test"})

        assert "error" in result.lower()

    async def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("YOUR_API_KEY", raising=False)

        result = await your_tool_name.ainvoke({"param1": "test"})

        assert "YOUR_API_KEY" in result

    @respx.mock
    async def test_sends_correct_request(self, monkeypatch):
        monkeypatch.setenv("YOUR_API_KEY", "test-key")

        route = respx.get("https://api.example.com/v1/endpoint").mock(
            return_value=Response(200, json=_MOCK_SUCCESS_RESPONSE)
        )

        await your_tool_name.ainvoke({"param1": "test_value"})

        assert route.calls[0].request.url.params["q"] == "test_value"
```

**Test patterns:**
- Use **`respx`** for HTTP mocking (not `unittest.mock`)
- Mock payloads as module-level `_MOCK_*` constants
- Use `monkeypatch.setenv()` for API keys
- All test functions are `async def`
- Test: success, empty, HTTP errors, missing credentials, correct request body

### 5. Add configuration

If the tool has a timeout, add it to `config/config.yaml`:

```yaml
timeouts:
  your_tool: 15  # seconds
```

Add the environment variable to `.env.example`:

```bash
YOUR_API_KEY=           # Get from https://example.com/developers
```

### 6. Update documentation

1. Add a row to `docs/tools/TOOLS_REFERENCE.md`
2. For non-trivial APIs, create `docs/tools/<API_NAME>_INTEGRATION.md`
3. Update `README.md` tools table
4. If adding a new agent, update the architecture diagram in `README.md`

---

## Conventions & Patterns

| Convention | Example |
| ---------- | ------- |
| File naming | `src/tools/hotels_hotelbeds.py` (snake_case, descriptive) |
| Tool function naming | `search_hotels_hotelbeds` (verb_noun pattern) |
| Logger name | `"tools.hotels_hotelbeds"` (dot-separated module path) |
| Internal API calls | Separate `_function()` with `@retry` decorator |
| Auth headers | Helper `_build_headers()` reading from `os.environ` |
| HTTP client | `httpx.AsyncClient` in async context manager |
| Error returns | Human-readable string, not raw exception |
| Test file | `tests/test_hotels_hotelbeds.py` (mirrors source) |
| Mock data | `_MOCK_AVAILABILITY_RESPONSE` (module-level constant) |
| Imports | stdlib → third-party → local, separated by blank lines |

**What NOT to do:**
- Don't use `print()` — use `AppLogger`
- Don't use `requests` — use `httpx`
- Don't use `unittest.mock` — use `respx` for HTTP mocking
- Don't make unscoped network calls without timeout and error handling
- Don't return raw JSON to the LLM — format as readable text

---

## Checklist

Use this checklist when adding a new tool:

- [ ] Created `src/tools/<tool>.py` with `@tool` decorator
- [ ] Used `async def` for HTTP-calling tools
- [ ] Added retry logic with `tenacity`
- [ ] Used `AppLogger` for logging
- [ ] Credentials read from environment variables
- [ ] Added timeout to HTTP calls
- [ ] Error handling returns user-friendly strings
- [ ] Tool returns formatted text (not raw JSON)
- [ ] Wired tool into appropriate agent in `src/agent/agents/`
- [ ] Updated agent prompt in `src/agent/prompts/agent_prompt.py`
- [ ] Created `tests/test_<tool>.py` with mocked HTTP
- [ ] Tests cover: success, empty, HTTP error, missing credentials, request validation
- [ ] Added env var to `.env.example`
- [ ] Updated `docs/tools/TOOLS_REFERENCE.md`
- [ ] Updated `README.md` tools table
- [ ] Created integration doc if API is non-trivial
