# LangChain Fundamentals — Complete Reference Guide
> **Purpose:** Production-ready reference for building multi-agent systems with LangChain, LangGraph, and LangSmith.  
> **Source:** LangChain Academy — *Introduction to LangChain* (`lca-lc-foundations`)  
> **Date:** March 2026

---

## Table of Contents

1. [Environment & Setup](#1-environment--setup)
2. [Module 1 — Core Primitives](#2-module-1--core-primitives)
   - [1.1 Foundational Models](#11-foundational-models)
   - [1.1 Prompting Techniques](#12-prompting-techniques)
   - [1.2 Tools](#13-tools)
   - [1.2 Web Search](#14-web-search)
   - [1.3 Memory & Persistence](#15-memory--persistence)
   - [1.4 Multimodal Messages](#16-multimodal-messages)
   - [1.5 Personal Chef — Module 1 Capstone](#17-personal-chef--module-1-capstone)
3. [Module 2 — Agentic Architecture](#3-module-2--agentic-architecture)
   - [2.1 Model Context Protocol (MCP)](#21-model-context-protocol-mcp)
   - [2.1 Travel Agent](#22-travel-agent)
   - [2.2 State Management](#23-state-management)
   - [2.2 Runtime Context](#24-runtime-context)
   - [2.3 Multi-Agent Systems](#25-multi-agent-systems)
   - [2.4 Wedding Planners — Module 2 Capstone](#26-wedding-planners--module-2-capstone)
   - [Bonus: RAG (Retrieval-Augmented Generation)](#bonus-rag-retrieval-augmented-generation)
   - [Bonus: SQL Agent](#bonus-sql-agent)
4. [Module 3 — Advanced Agent Patterns](#4-module-3--advanced-agent-patterns)
   - [3.2 Managing Messages](#32-managing-messages)
   - [3.3 Human-in-the-Loop (HITL)](#33-human-in-the-loop-hitl)
   - [3.4 Dynamic Models](#34-dynamic-models)
   - [3.4 Dynamic Prompts](#35-dynamic-prompts)
   - [3.4 Dynamic Tools](#36-dynamic-tools)
   - [3.5 Email Agent — Module 3 Capstone](#37-email-agent--module-3-capstone)
5. [LangSmith — Observability & Tracing](#5-langsmith--observability--tracing)
6. [Multi-Agent Architecture Blueprints](#6-multi-agent-architecture-blueprints)
7. [Complete API Quick Reference](#7-complete-api-quick-reference)
8. [Production Patterns & Best Practices](#8-production-patterns--best-practices)

---

## 1. Environment & Setup

### 1.1 Prerequisites

| Requirement       | Version          | Notes                              |
|-------------------|------------------|------------------------------------|
| Python            | >=3.12, <3.14    | Managed by `uv` automatically      |
| uv (recommended)  | latest           | Also needed for MCP `uvx` commands |
| Node.js           | latest LTS       | Required for `agent-chat-ui`       |

### 1.2 Installation

```bash
# Clone the repo
git clone https://github.com/langchain-ai/lca-lc-foundations.git
cd lca-lc-foundations

# Create environment file
cp example.env .env

# Install all dependencies
uv sync
```

Alternative with pip:
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1.3 Environment Variables (`.env`)

```dotenv
# ── Required ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY='sk-...'            # OpenAI or Azure-compatible key
TAVILY_API_KEY='tvly-...'          # Web search via Tavily

# ── Azure OpenAI (if using Azure instead of OpenAI) ───────────────────────────
AZURE_OPENAI_API_KEY='...'
AZURE_OPENAI_ENDPOINT='https://<resource>.openai.azure.com/'
AZURE_OPENAI_DEPLOYMENT_NAME='gpt-4o'
AZURE_OPENAI_API_VERSION='2024-02-01'

# ── Optional: alternate model providers ──────────────────────────────────────
ANTHROPIC_API_KEY='sk-ant-...'
GOOGLE_API_KEY='AIza...'

# ── LangSmith (observability & tracing) ──────────────────────────────────────
LANGSMITH_API_KEY='lsv2_...'
LANGSMITH_TRACING=true             # Uncomment to enable tracing
LANGSMITH_PROJECT=lca-lc-foundation
# LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com  # EU instance
```

### 1.4 Core Dependencies

```
langchain>=1.1.3
langchain-openai>=1.1.1
langgraph>=1.0.3
langgraph-cli>=0.4.9
langgraph-api>=0.5.37
langsmith>=0.4.43
langchain-core>=1.1.3
langchain-community>=0.4.1
langchain-mcp-adapters>=0.1.13
mcp>=1.21.1
tavily-python>=0.7.13
langchain-tavily>=0.2.13
langchain-text-splitters>=1.0.0
langchain-google-genai>=3.1.0
langchain-anthropic>=1.0.3
pypdf>=6.2.0
ipywidgets>=8.1.8
sounddevice>=0.5.3
scipy>=1.16.3
```

### 1.5 Loading Environment Variables

```python
from dotenv import load_dotenv

load_dotenv()   # Reads .env from the current working directory
```

---

## 2. Module 1 — Core Primitives

### 1.1 Foundational Models

#### Initializing a Model (Azure OpenAI)

```python
import os
from langchain_openai import AzureChatOpenAI

model = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)
```

#### Customising Model Parameters

```python
model = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=1.0,    # 0.0 = deterministic, 2.0 = very random
)
```

#### Direct Model Invocation (without an agent)

```python
response = model.invoke("What's the capital of the Moon?")
print(response.content)             # The text answer
print(response.response_metadata)   # Token usage, model name, etc.
```

#### Alternative Model Providers

```python
# OpenAI via init_chat_model (provider-agnostic helper)
from langchain.chat_models import init_chat_model
model = init_chat_model(model="claude-sonnet-4-5")

# Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")
```

> See all supported integrations: https://docs.langchain.com/oss/python/integrations/chat

#### Creating an Agent

```python
from langchain.agents import create_agent

# From a model object
agent = create_agent(model=model)

# From a model string identifier
agent = create_agent(model="gpt-5-nano")
agent = create_agent(model="claude-sonnet-4-5")
```

#### Invoking an Agent

```python
from langchain.messages import HumanMessage

response = agent.invoke(
    {"messages": [HumanMessage(content="What's the capital of the Moon?")]}
)

print(response['messages'][-1].content)   # Final answer
```

#### Multi-Turn Invocation (manual history)

```python
from langchain.messages import HumanMessage, AIMessage

response = agent.invoke(
    {"messages": [
        HumanMessage(content="What's the capital of the Moon?"),
        AIMessage(content="The capital of the Moon is Luna City."),
        HumanMessage(content="Interesting, tell me more about Luna City")
    ]}
)
```

#### Streaming Output

```python
for token, metadata in agent.stream(
    {"messages": [HumanMessage(content="Tell me all about Luna City")]},
    stream_mode="messages"
):
    # token = message chunk with partial content
    # metadata = which node produced the token
    if token.content:
        print(token.content, end="", flush=True)
```

#### Response Object Structure

```python
response = agent.invoke({"messages": [question]})

# Key fields:
response['messages']           # Full message history list
response['messages'][-1]       # Last message (the AI's final answer)
response['messages'][-1].content          # Text content
response['messages'][-1].response_metadata  # Model metadata
response['messages'][1].tool_calls         # Tool calls made by the AI
```

---

### 1.2 Prompting Techniques

#### Basic System Prompt

```python
agent = create_agent(
    model="gpt-5-nano",
    system_prompt="You are a science fiction writer, create a capital city at the users request."
)
```

#### Few-Shot Examples in System Prompt

Embed input–output examples directly in the system prompt to guide model behavior:

```python
system_prompt = """
You are a science fiction writer, create a space capital city at the users request.

User: What is the capital of mars?
Scifi Writer: Marsialis

User: What is the capital of Venus?
Scifi Writer: Venusovia
"""

agent = create_agent(
    model="gpt-5-nano",
    system_prompt=system_prompt
)
```

#### Structured Prompt (Output Schema in Prompt)

Define the expected output format in natural language within the system prompt:

```python
system_prompt = """
You are a science fiction writer, create a space capital city at the users request.

Please keep to the below structure.

Name: The name of the capital city
Location: Where it is based
Vibe: 2-3 words to describe its vibe
Economy: Main industries
"""
```

#### Structured Output (Pydantic Schema)

Use Pydantic models to enforce machine-parseable output:

```python
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.messages import HumanMessage

class CapitalInfo(BaseModel):
    name: str
    location: str
    vibe: str
    economy: str

agent = create_agent(
    model='gpt-5-nano',
    system_prompt="You are a science fiction writer, create a capital city at the users request.",
    response_format=CapitalInfo    # enforces Pydantic output
)

response = agent.invoke({"messages": [HumanMessage(content="What is the capital of The Moon?")]})

# Access structured output
capital = response["structured_response"]     # CapitalInfo instance
print(capital.name)
print(capital.location)
print(f"{capital.name} is a city located at {capital.location}")
```

> **Key concept:** `response_format` enforces Pydantic schema. The parsed object is at `response["structured_response"]`.

---

### 1.3 Tools

**Tools** give agents the ability to call external functions (APIs, databases, calculations, etc.).

#### Defining a Tool

```python
from langchain.tools import tool

# Method 1: basic decorator (uses function name and docstring)
@tool
def square_root(x: float) -> float:
    """Calculate the square root of a number"""
    return x ** 0.5

# Method 2: explicit name override
@tool("square_root")
def tool1(x: float) -> float:
    """Calculate the square root of a number"""
    return x ** 0.5

# Method 3: name + description override
@tool("square_root", description="Calculate the square root of a number")
def tool1(x: float) -> float:
    return x ** 0.5
```

> **Important:** The docstring is what the LLM reads to decide when to call the tool. Make it clear and accurate.

#### Directly Invoking a Tool (for testing)

```python
result = square_root.invoke({"x": 467})    # Returns: 21.610...
```

#### Attaching Tools to an Agent

```python
from langchain.agents import create_agent

agent = create_agent(
    model="gpt-5-nano",
    tools=[square_root],
    system_prompt="You are an arithmetic wizard. Use your tools to calculate the square root of any number."
)

from langchain.messages import HumanMessage
response = agent.invoke({"messages": [HumanMessage(content="What is the square root of 467?")]})
print(response['messages'][-1].content)
```

#### Inspecting Tool Calls in the Response

```python
from pprint import pprint

pprint(response['messages'])               # Full message list (Human → AI w/ tool call → Tool → AI)
print(response["messages"][1].tool_calls)  # Tool call metadata: name + args
```

---

### 1.4 Web Search

**Pattern:** Define a Tavily-backed tool and give it to an agent.

```python
from langchain.tools import tool
from typing import Dict, Any
from tavily import TavilyClient

tavily_client = TavilyClient()   # Uses TAVILY_API_KEY from environment

@tool
def web_search(query: str) -> Dict[str, Any]:
    """Search the web for information"""
    return tavily_client.search(query)

# Test directly
web_search.invoke("Who is the current mayor of San Francisco?")
```

#### Web-Enabled Agent

```python
from langchain.agents import create_agent
from langchain.messages import HumanMessage

agent = create_agent(
    model="gpt-5-nano",
    tools=[web_search]
)

response = agent.invoke(
    {"messages": [HumanMessage(content="Who is the current mayor of San Francisco?")]}
)
print(response['messages'][-1].content)
```

> **Without web search:** The model uses its training cutoff.  
> **With web search:** The model fetches live data, then synthesizes a response.

---

### 1.5 Memory & Persistence

By default, each `agent.invoke()` call is **stateless** — the agent has no memory of previous turns.

#### Without Memory (stateless, default)

```python
agent = create_agent("gpt-5-nano")

# Turn 1
agent.invoke({"messages": [HumanMessage(content="My name is Seán and my favourite colour is green")]})

# Turn 2 — agent does NOT remember Turn 1
agent.invoke({"messages": [HumanMessage(content="What's my favourite colour?")]})
# → "I don't know your favourite colour."
```

#### With Memory (InMemorySaver + thread_id)

```python
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    "gpt-5-nano",
    checkpointer=InMemorySaver(),   # persists state between calls
)

config = {"configurable": {"thread_id": "1"}}  # unique session identifier

# Turn 1
agent.invoke(
    {"messages": [HumanMessage(content="My name is Seán and my favourite colour is green")]},
    config
)

# Turn 2 — agent REMEMBERS Turn 1 because same thread_id
agent.invoke(
    {"messages": [HumanMessage(content="What's my favourite colour?")]},
    config
)
# → "Your favourite colour is green."
```

> **`thread_id`:** Identifies the conversation session. Different `thread_id` values = different isolated conversations.

#### Key Concepts

| Concept | Description |
|---------|-------------|
| `InMemorySaver` | In-process memory — lost on process restart |
| `thread_id` | Unique key that scopes a conversation's memory |
| `config` | Dict passed as second arg to `agent.invoke()` |
| Production checkpointers | `SqliteSaver`, `PostgresSaver`, Redis-backed, etc. |

---

### 1.6 Multimodal Messages

Agents can process **text**, **images**, and **audio** by passing structured content blocks in `HumanMessage`.

#### Text Input (explicit content block)

```python
from langchain.messages import HumanMessage

question = HumanMessage(content=[
    {"type": "text", "text": "What is the capital of The Moon?"}
])
```

#### Image Input (base64-encoded)

```python
import base64
from langchain.messages import HumanMessage

# Read and encode the image
with open("image.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

# Widget-based upload approach (in Jupyter)
from ipywidgets import FileUpload
uploader = FileUpload(accept='.png', multiple=False)
# After upload:
img_bytes = bytes(uploader.value[0]["content"])
img_b64 = base64.b64encode(img_bytes).decode("utf-8")

# Multimodal message
multimodal_question = HumanMessage(content=[
    {"type": "text",  "text": "Tell me about this capital"},
    {"type": "image", "base64": img_b64, "mime_type": "image/png"}
])

response = agent.invoke({"messages": [multimodal_question]})
```

#### Audio Input (WAV, base64-encoded)

```python
import sounddevice as sd
from scipy.io.wavfile import write
import base64, io, time
from tqdm import tqdm

# Record 5 seconds of audio
duration, sample_rate = 5, 44100
audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
for _ in tqdm(range(duration * 10)):
    time.sleep(0.1)
sd.wait()

# Encode to base64
buf = io.BytesIO()
write(buf, sample_rate, audio)
aud_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

# Use an audio-capable model
agent = create_agent(model='gpt-4o-audio-preview')

multimodal_question = HumanMessage(content=[
    {"type": "text",  "text": "Tell me about this audio file"},
    {"type": "audio", "base64": aud_b64, "mime_type": "audio/wav"}
])
```

#### Content Block Types

| Type | Key Fields |
|------|------------|
| `"text"` | `"text": "..."` |
| `"image"` | `"base64": "<b64>", "mime_type": "image/png"` |
| `"audio"` | `"base64": "<b64>", "mime_type": "audio/wav"` |

---

### 1.7 Personal Chef — Module 1 Capstone

This project integrates: **tools + web search + memory + system prompt**.

```python
from dotenv import load_dotenv
from langchain.tools import tool
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.messages import HumanMessage
from typing import Dict, Any
from tavily import TavilyClient

load_dotenv()

# ── Tool ──────────────────────────────────────────────────────────────────────
tavily_client = TavilyClient()

@tool
def web_search(query: str) -> Dict[str, Any]:
    """Search the web for information"""
    return tavily_client.search(query)

# ── System Prompt ─────────────────────────────────────────────────────────────
system_prompt = """
You are a personal chef. The user will give you a list of ingredients they have left over in their house.
Using the web search tool, search the web for recipes that can be made with the ingredients they have.
Return recipe suggestions and eventually the recipe instructions to the user, if requested.
"""

# ── Agent ─────────────────────────────────────────────────────────────────────
agent = create_agent(
    model="gpt-5-nano",
    tools=[web_search],
    system_prompt=system_prompt,
    checkpointer=InMemorySaver()
)

# ── Invocation ────────────────────────────────────────────────────────────────
config = {"configurable": {"thread_id": "1"}}

response = agent.invoke(
    {"messages": [HumanMessage(content="I have some leftover chicken and rice. What can I make?")]},
    config
)
print(response['messages'][-1].content)
```

---

## 3. Module 2 — Agentic Architecture

### 2.1 Model Context Protocol (MCP)

**MCP** is a protocol for exposing tools, resources, and prompts to LLM agents via a standardized server interface. `langchain-mcp-adapters` bridges MCP servers and LangChain agents.

#### MCP Server Components

| Component | Description | Decorator |
|-----------|-------------|-----------|
| **Tools** | Callable functions (actions) | `@mcp.tool()` |
| **Resources** | Static/dynamic data sources (knowledge) | `@mcp.resource("uri://...")` |
| **Prompts** | Reusable prompt templates | `@mcp.prompt()` |

#### Building a Local MCP Server

```python
# resources/2.1_mcp_server.py
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient
from typing import Dict, Any
from requests import get

load_dotenv()

mcp = FastMCP("mcp_server")
tavily_client = TavilyClient()

# ── Tool ──────────────────────────────────────────────────────────────────────
@mcp.tool()
def search_web(query: str) -> Dict[str, Any]:
    """Search the web for information"""
    return tavily_client.search(query)

# ── Resource ──────────────────────────────────────────────────────────────────
@mcp.resource("github://langchain-ai/langchain-mcp-adapters/blob/main/README.md")
def github_file():
    """Resource for accessing langchain-ai/langchain-mcp-adapters/README.md file"""
    url = "https://raw.githubusercontent.com/langchain-ai/langchain-mcp-adapters/blob/main/README.md"
    try:
        return get(url).text
    except Exception as e:
        return f"Error: {str(e)}"

# ── Prompt ────────────────────────────────────────────────────────────────────
@mcp.prompt()
def prompt():
    """Analyze data from a langchain-ai repo file with comprehensive insights"""
    return """
    You are a helpful assistant that answers user questions about LangChain, LangGraph and LangSmith.
    ...
    """

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

#### Connecting to a Local MCP Server

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "local_server": {
            "transport": "stdio",
            "command": "python",
            "args": ["resources/2.1_mcp_server.py"],
        }
    }
)

# Async — must be called in an async context (await in Jupyter)
tools = await client.get_tools()
resources = await client.get_resources("local_server")
prompt = await client.get_prompt("local_server", "prompt")
prompt_text = prompt[0].content
```

#### Connecting to a Remote/Online MCP Server

```python
client = MultiServerMCPClient(
    {
        "travel_server": {
            "transport": "streamable_http",
            "url": "https://mcp.kiwi.com"   # Remote MCP endpoint
        }
    }
)
tools = await client.get_tools()
```

#### Using MCP Tools in an Agent

```python
from langchain.agents import create_agent

agent = create_agent(
    model=model,
    tools=tools,            # tools from MCP client — same interface as @tool
    system_prompt=prompt_text
)

response = await agent.ainvoke(
    {"messages": [HumanMessage(content="Tell me about the langchain-mcp-adapters library")]},
    config={"configurable": {"thread_id": "1"}}
)
```

> **Note:** When using `async` tools (from MCP), use `await agent.ainvoke()` instead of `agent.invoke()`.

#### Transport Types

| Transport | Use Case | Config Key |
|-----------|----------|------------|
| `stdio` | Local server (subprocess) | `command`, `args` |
| `streamable_http` | Remote/cloud server | `url` |
| `sse` | Server-Sent Events | `url` |

---

### 2.2 Travel Agent

Demonstrates: **remote MCP server + async agent + memory**.

```python
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.messages import HumanMessage
import os
from langchain_openai import AzureChatOpenAI

load_dotenv()

# ── MCP client ────────────────────────────────────────────────────────────────
client = MultiServerMCPClient(
    {
        "travel_server": {
            "transport": "streamable_http",
            "url": "https://mcp.kiwi.com"
        }
    }
)
tools = await client.get_tools()

# ── Model ─────────────────────────────────────────────────────────────────────
model = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

# ── Agent ─────────────────────────────────────────────────────────────────────
agent = create_agent(
    model=model,
    tools=tools,
    checkpointer=InMemorySaver(),
    system_prompt="You are a travel agent. No follow up questions."
)

config = {"configurable": {"thread_id": "1"}}

response = await agent.ainvoke(
    {"messages": [HumanMessage(content="Get me a direct flight from San Francisco to Tokyo on March 31st")]},
    config
)
print(response["messages"][-1].content)
```

---

### 2.3 State Management

**State** is the data structure shared across an agent's execution. Extending `AgentState` allows you to add custom fields that tools and middleware can read and write.

#### Defining Custom State

```python
from langchain.agents import AgentState

class CustomState(AgentState):
    favourite_colour: str    # Additional field beyond messages
```

#### Writing to State from a Tool

Use `Command` to return both a tool message and a state update:

```python
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from langchain.messages import ToolMessage

@tool
def update_favourite_colour(favourite_colour: str, runtime: ToolRuntime) -> Command:
    """Update the favourite colour of the user in the state once they've revealed it."""
    return Command(update={
        "favourite_colour": favourite_colour,
        "messages": [ToolMessage("Successfully updated favourite colour",
                                  tool_call_id=runtime.tool_call_id)]
    })
```

#### Reading from State in a Tool

```python
@tool
def read_favourite_colour(runtime: ToolRuntime) -> str:
    """Read the favourite colour of the user from the state."""
    try:
        return runtime.state["favourite_colour"]
    except KeyError:
        return "No favourite colour found in state"
```

#### Using Custom State in an Agent

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    "gpt-5-nano",
    tools=[update_favourite_colour, read_favourite_colour],
    checkpointer=InMemorySaver(),
    state_schema=CustomState   # Register the custom state class
)
```

#### Pre-Populating State on Invocation

```python
response = agent.invoke(
    {
        "messages": [HumanMessage(content="Hello, how are you?")],
        "favourite_colour": "green"    # Pre-loaded state value
    },
    {"configurable": {"thread_id": "10"}}
)
```

#### `AgentState` Base Fields

| Field | Type | Description |
|-------|------|-------------|
| `messages` | `list[BaseMessage]` | The conversation history |

All custom fields are added via class inheritance.

#### `ToolRuntime` Fields

| Field | Access | Description |
|-------|--------|-------------|
| `tool_call_id` | `runtime.tool_call_id` | ID of the current tool call |
| `state` | `runtime.state["field"]` | Current agent state |
| `context` | `runtime.context.field` | Runtime context (see §2.4) |

---

### 2.4 Runtime Context

**Runtime context** is read-only data injected at invocation time — user preferences, auth info, feature flags — without polluting the state.

#### Defining a Context Schema

```python
from dataclasses import dataclass

@dataclass
class ColourContext:
    favourite_colour: str = "blue"
    least_favourite_colour: str = "yellow"
```

#### Creating an Agent with Context

```python
from langchain.agents import create_agent

agent = create_agent(
    model="gpt-5-nano",
    context_schema=ColourContext
)
```

#### Passing Context on Invocation

```python
from langchain.messages import HumanMessage

response = agent.invoke(
    {"messages": [HumanMessage(content="What is my favourite colour?")]},
    context=ColourContext(favourite_colour="green")   # Override defaults
)
```

#### Accessing Context in a Tool

```python
from langchain.tools import tool, ToolRuntime

@tool
def get_favourite_colour(runtime: ToolRuntime) -> str:
    """Get the favourite colour of the user"""
    return runtime.context.favourite_colour

@tool
def get_least_favourite_colour(runtime: ToolRuntime) -> str:
    """Get the least favourite colour of the user"""
    return runtime.context.least_favourite_colour
```

#### State vs. Context Comparison

| | State (`AgentState`) | Context (`@dataclass`) |
|--|---------------------|----------------------|
| **Mutability** | Mutable (tools can write to it) | Read-only at runtime |
| **Persistence** | Persisted by checkpointer | Not persisted |
| **Access** | `runtime.state["field"]` | `runtime.context.field` |
| **Use for** | Evolving conversation data | User config, auth, feature flags |

---

### 2.5 Multi-Agent Systems

A **multi-agent system** breaks complex tasks across specialised agents. The key pattern: **wrap subagents as tools** so a **supervisor agent** can delegate.

#### Creating Subagents

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def square_root(x: float) -> float:
    """Calculate the square root of a number"""
    return x ** 0.5

@tool
def square(x: float) -> float:
    """Calculate the square of a number"""
    return x ** 2

subagent_1 = create_agent(model=model, tools=[square_root])
subagent_2 = create_agent(model=model, tools=[square])
```

#### Wrapping Subagents as Tools

```python
from langchain.tools import tool
from langchain.messages import HumanMessage

@tool
def call_subagent_1(x: float) -> float:
    """Call subagent 1 in order to calculate the square root of a number"""
    response = subagent_1.invoke({"messages": [HumanMessage(content=f"Calculate the square root of {x}")]})
    return response["messages"][-1].content

@tool
def call_subagent_2(x: float) -> float:
    """Call subagent 2 in order to calculate the square of a number"""
    response = subagent_2.invoke({"messages": [HumanMessage(content=f"Calculate the square of {x}")]})
    return response["messages"][-1].content
```

#### Supervisor (Main) Agent

```python
main_agent = create_agent(
    model=model,
    tools=[call_subagent_1, call_subagent_2],
    system_prompt="You are a helpful assistant who can call subagents to calculate the square root or square of a number."
)

response = main_agent.invoke({"messages": [HumanMessage(content="What is the square root of 456?")]})
```

#### Multi-Agent Architecture Pattern

```
User
 │
 ▼
Supervisor Agent
 ├──► Tool: call_subagent_1  ──► Subagent 1 (specialized tools A)
 └──► Tool: call_subagent_2  ──► Subagent 2 (specialized tools B)
```

---

### 2.6 Wedding Planners — Module 2 Capstone

This is a full multi-agent system combining: **custom state + MCP tools + web search + SQL + subagents + coordinator**.

#### State

```python
from langchain.agents import AgentState

class WeddingState(AgentState):
    origin: str
    destination: str
    guest_count: str
    genre: str
```

#### Subagents

```python
# Travel agent — uses MCP tools for real flight search
travel_agent = create_agent(
    model=model,
    tools=tools,       # from MultiServerMCPClient
    system_prompt="""
    You are a travel agent. Search for flights to the desired destination wedding location.
    Only look for one ticket, one way.
    Once you have found the best options, let the user know your shortlist of options.
    """
)

# Venue agent — uses web search
venue_agent = create_agent(
    model=model,
    tools=[web_search],
    system_prompt="""
    You are a venue specialist. Search for venues in the desired location with the desired capacity.
    """
)

# Playlist agent — queries SQL database
playlist_agent = create_agent(
    model=model,
    tools=[query_playlist_db],
    system_prompt="""
    You are a playlist specialist. Query the SQL database and curate the perfect playlist for a wedding.
    """
)
```

#### State-Reading Coordinator Tools

```python
from langchain.tools import ToolRuntime
from langchain.messages import HumanMessage, ToolMessage
from langgraph.types import Command

@tool
async def search_flights(runtime: ToolRuntime) -> str:
    """Travel agent searches for flights to the desired destination wedding location."""
    origin = runtime.state["origin"]
    destination = runtime.state["destination"]
    response = await travel_agent.ainvoke(
        {"messages": [HumanMessage(content=f"Find flights from {origin} to {destination}")]}
    )
    return response['messages'][-1].content

@tool
def search_venues(runtime: ToolRuntime) -> str:
    """Venue agent chooses the best venue for the given location and capacity."""
    destination = runtime.state["destination"]
    capacity = runtime.state["guest_count"]
    response = venue_agent.invoke(
        {"messages": [HumanMessage(content=f"Find wedding venues in {destination} for {capacity} guests")]}
    )
    return response['messages'][-1].content

@tool
def suggest_playlist(runtime: ToolRuntime) -> str:
    """Playlist agent curates the perfect playlist for the given genre."""
    genre = runtime.state["genre"]
    response = playlist_agent.invoke(
        {"messages": [HumanMessage(content=f"Find {genre} tracks for wedding playlist")]}
    )
    return response['messages'][-1].content

@tool
def update_state(origin: str, destination: str, guest_count: str, genre: str, runtime: ToolRuntime) -> Command:
    """Update the state when you know all of the values: origin, destination, guest_count, genre"""
    return Command(update={
        "origin": origin,
        "destination": destination,
        "guest_count": guest_count,
        "genre": genre,
        "messages": [ToolMessage("Successfully updated state", tool_call_id=runtime.tool_call_id)]
    })
```

#### Coordinator Agent

```python
coordinator = create_agent(
    model=model,
    tools=[search_flights, search_venues, suggest_playlist, update_state],
    state_schema=WeddingState,
    system_prompt="""
    You are a wedding coordinator. Delegate tasks to your specialists for flights, venues and playlists.
    First find all the information you need to update the state. Once that is done you can delegate the tasks.
    """
)

response = await coordinator.ainvoke(
    {"messages": [HumanMessage(content="I'm from London and I'd like a wedding in Paris for 100 guests, jazz-genre")]}
)
print(response["messages"][-1].content)
```

#### SQL Tool Pattern (used in playlist agent)

```python
from langchain_community.utilities import SQLDatabase
from langchain.tools import tool

db = SQLDatabase.from_uri("sqlite:///resources/Chinook.db")

@tool
def query_playlist_db(query: str) -> str:
    """Query the database for playlist information"""
    try:
        return db.run(query)
    except Exception as e:
        return f"Error querying database: {e}"
```

---

### Bonus: RAG (Retrieval-Augmented Generation)

**RAG** allows agents to answer questions using documents not in the model's training data.

#### Pipeline: Load → Split → Embed → Store → Retrieve → Answer

```python
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.messages import HumanMessage

load_dotenv()

# 1. Load document
loader = PyPDFLoader("resources/acmecorp-employee-handbook.pdf")
data = loader.load()

# 2. Split into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    add_start_index=True
)
all_splits = text_splitter.split_documents(data)

# 3. Embed chunks
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

# 4. Store in vector store
vector_store = InMemoryVectorStore(embeddings)
ids = vector_store.add_documents(documents=all_splits)

# 5. Similarity search (standalone test)
results = vector_store.similarity_search(
    "How many days of vacation does an employee get in their first year?"
)
print(results[0].page_content)

# 6. Wrap as a tool
@tool
def search_handbook(query: str) -> str:
    """Search the employee handbook for information"""
    results = vector_store.similarity_search(query)
    return results[0].page_content

# 7. RAG Agent
agent = create_agent(
    model="gpt-5-nano",
    tools=[search_handbook],
    system_prompt="You are a helpful agent that can search the employee handbook for information."
)

response = agent.invoke(
    {"messages": [HumanMessage(content="How many days of vacation does an employee get in their first year?")]}
)
print(response['messages'][-1].content)
```

> See all embedding model integrations: https://docs.langchain.com/oss/python/integrations/text_embedding

---

### Bonus: SQL Agent

**Pattern:** Wrap `SQLDatabase.run()` as a LangChain tool and give it to an agent.

```python
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from pprint import pprint

load_dotenv()

# Connect to database
db = SQLDatabase.from_uri("sqlite:///resources/Chinook.db")

# Define tool
@tool
def sql_query(query: str) -> str:
    """Obtain information from the database using SQL queries"""
    try:
        return db.run(query)
    except Exception as e:
        return f"Error: {e}"

# Test directly
sql_query.invoke("SELECT * FROM Artist LIMIT 10")

# SQL-powered agent
agent = create_agent(
    model="gpt-5-nano",
    tools=[sql_query]
)

question = HumanMessage(content="Who is the most popular artist beginning with 'S' in this database?")
response = agent.invoke({"messages": [question]})

pprint(response['messages'])
print(response["messages"][-3].tool_calls[0]['args']['query'])  # Inspect the SQL query used
```

---

## 4. Module 3 — Advanced Agent Patterns

### 3.2 Managing Messages

Long conversations accumulate thousands of tokens. These techniques manage context window usage.

#### Summarization Middleware

Automatically summarises conversation history when token count exceeds a threshold:

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model="gpt-5-nano",
    checkpointer=InMemorySaver(),
    middleware=[
        SummarizationMiddleware(
            model="gpt-4o-mini",         # cheaper model for summarisation
            trigger=("tokens", 100),     # trigger when > 100 tokens
            keep=("messages", 1)         # keep the last 1 message after summarising
        )
    ]
)
```

The oldest messages are summarised into a single `AIMessage` stored at position `[0]`:
```python
print(response["messages"][0].content)   # → the summary
```

#### Trim/Delete Messages with Middleware

Use `@before_agent` to pre-process state before each LLM call:

```python
from typing import Any
from langchain.agents import AgentState
from langchain.messages import RemoveMessage, ToolMessage
from langgraph.runtime import Runtime
from langchain.agents.middleware import before_agent

@before_agent
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Remove all the tool messages from the state before each model call."""
    messages = state["messages"]
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    return {"messages": [RemoveMessage(id=m.id) for m in tool_messages]}

agent = create_agent(
    model="gpt-5-nano",
    checkpointer=InMemorySaver(),
    middleware=[trim_messages],
)
```

#### `@before_agent` as a Pattern

`@before_agent` runs BEFORE the agent's LLM call. Use it for:
- Removing or replacing messages
- Pre-processing state
- Injecting context into messages

Return `None` to make no changes. Return a dict to update state.

#### `RemoveMessage`

```python
from langchain.messages import RemoveMessage

# Remove a specific message by ID
RemoveMessage(id=message.id)
```

---

### 3.3 Human-in-the-Loop (HITL)

**HITL** pauses agent execution before sensitive tool calls, allowing a human to **approve**, **reject**, or **edit** the action.

#### Setup

```python
from langchain.agents import create_agent, AgentState
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import HumanInTheLoopMiddleware

class EmailState(AgentState):
    email: str

agent = create_agent(
    model="gpt-5-nano",
    tools=[read_email, send_email],
    state_schema=EmailState,
    checkpointer=InMemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "read_email": False,     # Never interrupt for this tool
                "send_email": True,      # Always interrupt for this tool
            },
            description_prefix="Tool execution requires approval",
        ),
    ],
)
```

#### Initial Invocation (triggers interrupt)

```python
config = {"configurable": {"thread_id": "1"}}

response = agent.invoke(
    {
        "messages": [HumanMessage(content="Read my email and send a response.")],
        "email": "Hi, can we reschedule tomorrow's meeting? - John"
    },
    config=config
)

# Inspect the interrupt
print(response['__interrupt__'])
# Access the proposed tool arguments
print(response['__interrupt__'][0].value['action_requests'][0]['args']['body'])
```

#### Approve

```python
from langgraph.types import Command

response = agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=config   # SAME thread_id — resumes paused conversation
)
```

#### Reject (with explanation)

```python
response = agent.invoke(
    Command(
        resume={
            "decisions": [{
                "type": "reject",
                "message": "Please sign off properly — Your leader, Seán."
            }]
        }
    ),
    config=config
)
```

#### Edit (modify tool arguments before executing)

```python
response = agent.invoke(
    Command(
        resume={
            "decisions": [{
                "type": "edit",
                "edited_action": {
                    "name": "send_email",            # Same tool
                    "args": {"body": "This is the last straw, you're fired!"}   # New args
                }
            }]
        }
    ),
    config=config
)
```

#### HITL Flow

```
agent.invoke() → interrupt → response['__interrupt__']
                                │
                    ┌───────────┴────────────┐
                    │                        │
               approve                  reject / edit
                    │                        │
              agent.invoke(              agent.invoke(
               Command(resume=           Command(resume=
                {"decisions":            {"decisions":
                 "approve"}))             "reject"/"edit"}))
                    │                        │
              tool executes            agent re-plans
```

---

### 3.4 Dynamic Models

Dynamically select a different LLM model based on runtime conditions (e.g., conversation length, cost, complexity).

```python
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from langchain.chat_models import init_chat_model
from typing import Callable

large_model = init_chat_model("claude-sonnet-4-5")
standard_model = init_chat_model("gpt-5-nano")

@wrap_model_call
def state_based_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Select model based on conversation length."""
    message_count = len(request.messages)  # shortcut for request.state["messages"]

    if message_count > 10:
        model = large_model    # Long conversation → powerful model
    else:
        model = standard_model  # Short conversation → efficient model

    request = request.override(model=model)
    return handler(request)

agent = create_agent(
    model="gpt-5-nano",
    middleware=[state_based_model],
    system_prompt="You are roleplaying a real life helpful office intern."
)

# The model used is visible in response metadata
print(response["messages"][-1].response_metadata["model_name"])
```

#### `@wrap_model_call` Pattern

```python
@wrap_model_call
def my_middleware(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    # Inspect/modify the request
    request = request.override(model=..., tools=..., system_prompt=...)
    # Call the next handler (continue the chain)
    return handler(request)
```

| `ModelRequest` field | Description |
|---------------------|-------------|
| `request.messages` | Current message list (shortcut for `request.state["messages"]`) |
| `request.state` | Full agent state dict |
| `request.runtime.context` | Runtime context object |
| `request.override(...)` | Create a new request with field overrides |

---

### 3.5 Dynamic Prompts

Change the system prompt at runtime based on user context, state, or role.

```python
from dataclasses import dataclass
from langchain.agents.middleware import dynamic_prompt, ModelRequest

@dataclass
class LanguageContext:
    user_language: str = "English"

@dynamic_prompt
def user_language_prompt(request: ModelRequest) -> str:
    """Generate system prompt based on user language context."""
    user_language = request.runtime.context.user_language
    base_prompt = "You are a helpful assistant."

    if user_language != "English":
        return f"{base_prompt} Only respond in {user_language}."
    return base_prompt

agent = create_agent(
    model=model,
    context_schema=LanguageContext,
    middleware=[user_language_prompt]
)

# Irish
response = agent.invoke(
    {"messages": [HumanMessage(content="Hello, how are you?")]},
    context=LanguageContext(user_language="Irish")
)

# Spanish
response = agent.invoke(
    {"messages": [HumanMessage(content="Hello, how are you?")]},
    context=LanguageContext(user_language="Spanish")
)
```

#### `@dynamic_prompt` Pattern

```python
@dynamic_prompt
def my_prompt(request: ModelRequest) -> str:
    # Access context, state, or any condition
    role = request.runtime.context.user_role
    if role == "admin":
        return "You are an admin assistant with full access."
    return "You are a restricted assistant."
```

---

### 3.6 Dynamic Tools

Control which tools are available to the agent at runtime based on user role, auth status, or any condition.

```python
from dataclasses import dataclass
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from typing import Callable

@dataclass
class UserRole:
    user_role: str = "external"

@wrap_model_call
def dynamic_tool_call(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Dynamically assign tools based on user role."""
    user_role = request.runtime.context.user_role

    if user_role == "internal":
        pass  # Internal users keep all tools (no override)
    else:
        # External users only get web search
        request = request.override(tools=[web_search])

    return handler(request)

agent = create_agent(
    model="gpt-5-nano",
    tools=[web_search, sql_query],     # Registered tools (all)
    middleware=[dynamic_tool_call],
    context_schema=UserRole
)

# External user — can only use web_search
response = agent.invoke(
    {"messages": [HumanMessage(content="How many artists are in the database?")]},
    context={"user_role": "external"}
)

# Internal user — can use web_search and sql_query
response = agent.invoke(
    {"messages": [HumanMessage(content="How many artists are in the database?")]},
    context={"user_role": "internal"}
)
```

---

### 3.7 Email Agent — Module 3 Capstone

The Email Agent integrates all Module 3 techniques:
- **Custom state** (`AuthenticatedState`)
- **Runtime context** (`EmailContext`)
- **Dynamic tools** (auth gate)
- **Dynamic prompt** (auth-based persona)
- **Human-in-the-loop** (approve before sending email)

```python
from dotenv import load_dotenv
from dataclasses import dataclass
from langchain.agents import AgentState, create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from langchain.messages import ToolMessage
from langchain.agents.middleware import (
    wrap_model_call, dynamic_prompt, HumanInTheLoopMiddleware,
    ModelRequest, ModelResponse
)
from langgraph.checkpoint.memory import InMemorySaver
from typing import Callable

load_dotenv()

# ── Context ───────────────────────────────────────────────────────────────────
@dataclass
class EmailContext:
    email_address: str = "julie@example.com"
    password: str = "password123"

# ── State ─────────────────────────────────────────────────────────────────────
class AuthenticatedState(AgentState):
    authenticated: bool

# ── Tools ─────────────────────────────────────────────────────────────────────
@tool
def check_inbox() -> str:
    """Check the inbox for recent emails"""
    return """
    Hi Julie,
    I'm going to be in town next week and was wondering if we could grab a coffee?
    - best, Jane (jane@example.com)
    """

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an response email"""
    return f"Email sent to {to} with subject {subject} and body {body}"

@tool
def authenticate(email: str, password: str, runtime: ToolRuntime) -> Command:
    """Authenticate the user with the given email and password"""
    if email == runtime.context.email_address and password == runtime.context.password:
        return Command(update={
            "authenticated": True,
            "messages": [ToolMessage("Successfully authenticated", tool_call_id=runtime.tool_call_id)]
        })
    else:
        return Command(update={
            "authenticated": False,
            "messages": [ToolMessage("Authentication failed", tool_call_id=runtime.tool_call_id)]
        })

# ── Dynamic Tools Middleware ───────────────────────────────────────────────────
@wrap_model_call
async def dynamic_tool_call(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Allow inbox/email tools only if authenticated."""
    if request.state.get("authenticated"):
        tools = [check_inbox, send_email]
    else:
        tools = [authenticate]
    request = request.override(tools=tools)
    return await handler(request)

# ── Dynamic Prompt Middleware ─────────────────────────────────────────────────
authenticated_prompt = "You are a helpful assistant that can check the inbox and send emails."
unauthenticated_prompt = "You are a helpful assistant that can authenticate users."

@dynamic_prompt
def dynamic_prompt_func(request: ModelRequest) -> str:
    """Generate system prompt based on authentication status."""
    if request.state.get("authenticated"):
        return authenticated_prompt
    return unauthenticated_prompt

# ── Agent ─────────────────────────────────────────────────────────────────────
agent = create_agent(
    "gpt-5-nano",
    tools=[authenticate, check_inbox, send_email],
    checkpointer=InMemorySaver(),
    state_schema=AuthenticatedState,
    context_schema=EmailContext,
    middleware=[
        dynamic_tool_call,
        dynamic_prompt_func,
        HumanInTheLoopMiddleware(
            interrupt_on={
                "authenticate": False,
                "check_inbox": False,
                "send_email": True,      # Pause before sending
            }
        )
    ]
)

# ── Usage ─────────────────────────────────────────────────────────────────────
config = {"configurable": {"thread_id": "1"}}

# Step 1: Trigger flow — agent will authenticate and check inbox, then draft email
response = agent.invoke(
    {"messages": [HumanMessage(content="Check my inbox and draft a reply")]},
    context=EmailContext(),
    config=config
)

# Step 2: Inspect proposed email body
print(response['__interrupt__'][0].value['action_requests'][0]['args']['body'])

# Step 3: Approve the send
from langgraph.types import Command
response = agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=config
)
print(response["messages"][-1].content)
```

---

## 5. LangSmith — Observability & Tracing

LangSmith provides end-to-end **tracing**, **evaluation**, and **debugging** for LangChain/LangGraph applications.

### 5.1 Setup

```dotenv
# .env
LANGSMITH_API_KEY='lsv2_...'
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=lca-lc-foundation
# EU instance:
# LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

When `LANGSMITH_TRACING=true` is set and you have a valid `LANGSMITH_API_KEY`, **every** `agent.invoke()` call is automatically traced — no code changes required.

### 5.2 What LangSmith Captures

| Captured Data | Description |
|---------------|-------------|
| **Inputs** | Complete input messages |
| **Outputs** | All responses and tool results |
| **LLM calls** | Model name, prompt, completion, token counts |
| **Tool calls** | Tool name, input args, output |
| **Latency** | Time for each step |
| **Errors** | Exceptions with full stack traces |
| **Agent trajectory** | Sequence of nodes/steps in LangGraph |

### 5.3 Viewing Traces

- Navigate to [smith.langchain.com](https://smith.langchain.com)
- Go to your project (default: `lca-lc-foundation`)
- Click any trace to see the full execution tree

#### Example Public Trace URLs (from the course)

```
# Web search example
https://smith.langchain.com/public/59432173-0dd6-49e8-9964-b16be6048426/r

# Wedding planners multi-agent
https://smith.langchain.com/public/7b5fe668-d3e3-4af4-b513-a8cacc0c9e84/r
```

### 5.4 Using LangSmith for Multi-Agent Debugging

In a multi-agent system, LangSmith is invaluable for:
- Seeing which subagent handled a request
- Inspecting the exact prompts sent to each model
- Finding where a tool call failed
- Measuring latency per agent/step
- Comparing runs to identify regressions

---

## 6. Multi-Agent Architecture Blueprints

### 6.1 Pattern 1: Supervisor + Subagents

The most common pattern. A supervisor orchestrates specialised subagents via tool calls.

```
User
 │
 ▼
[Supervisor Agent]
 ├──tools──► call_research_agent()  ──► [Research Agent] (web_search tool)
 ├──tools──► call_writer_agent()    ──► [Writer Agent] (structured output)
 └──tools──► call_reviewer_agent()  ──► [Reviewer Agent] (evaluation tool)
```

```python
# Template

@tool
def call_subagent(query: str) -> str:
    """Description the supervisor uses to decide when to call this."""
    response = subagent.invoke({"messages": [HumanMessage(content=query)]})
    return response["messages"][-1].content

supervisor = create_agent(
    model=model,
    tools=[call_subagent_A, call_subagent_B, call_subagent_C],
    state_schema=MyState,
    system_prompt="You are a coordinator. Delegate tasks appropriately."
)
```

### 6.2 Pattern 2: State-Sharing Subagents

Subagents read from shared state using `ToolRuntime`. Eliminates passing parameters via message content.

```python
@tool
async def research_task(runtime: ToolRuntime) -> str:
    """Research agent reads topic from shared state."""
    topic = runtime.state["research_topic"]
    response = await research_agent.ainvoke(
        {"messages": [HumanMessage(content=f"Research: {topic}")]}
    )
    return response["messages"][-1].content
```

### 6.3 Pattern 3: MCP-Powered Agent Network

Use MCP servers to give agents access to external APIs, databases, and services:

```python
client = MultiServerMCPClient({
    "flights": {"transport": "streamable_http", "url": "https://mcp.kiwi.com"},
    "hotels": {"transport": "streamable_http", "url": "https://mcp.hotels.com"},
    "local_db": {"transport": "stdio", "command": "python", "args": ["db_server.py"]}
})
tools = await client.get_tools()
```

### 6.4 Pattern 4: Role-Based Access Control (RBAC)

Control which tools each agent or user role can access via dynamic tools:

```python
@wrap_model_call
def role_based_tools(request, handler):
    role = request.runtime.context.user_role
    tools = ALL_TOOLS if role == "admin" else RESTRICTED_TOOLS
    request = request.override(tools=tools)
    return handler(request)
```

### 6.5 Pattern 5: HITL in Multi-Agent Pipelines

Add human approval gates to high-stakes subagent actions:

```python
sensitive_agent = create_agent(
    model=model,
    tools=[write_to_database, send_external_api_call],
    checkpointer=InMemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "write_to_database": True,
                "send_external_api_call": True,
            }
        )
    ]
)
```

### 6.6 Complete Multi-Agent System Template

```python
from dotenv import load_dotenv
from dataclasses import dataclass
from langchain.agents import AgentState, create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from langchain.messages import HumanMessage, ToolMessage
from langchain.agents.middleware import (
    wrap_model_call, dynamic_prompt, HumanInTheLoopMiddleware,
    ModelRequest, ModelResponse, SummarizationMiddleware
)
from langgraph.checkpoint.memory import InMemorySaver
from langchain.chat_models import init_chat_model
from typing import Callable

load_dotenv()

# ── Shared State ──────────────────────────────────────────────────────────────
class SystemState(AgentState):
    task_context: str
    result_summary: str
    user_role: str

# ── Context ───────────────────────────────────────────────────────────────────
@dataclass
class UserContext:
    user_id: str = "anonymous"
    role: str = "viewer"
    language: str = "English"

# ── Subagent A ────────────────────────────────────────────────────────────────
@tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base"""
    # ... implementation ...
    return "knowledge base results"

subagent_research = create_agent(
    model="gpt-5-nano",
    tools=[search_knowledge_base],
    system_prompt="You are a research specialist. Find accurate information."
)

# ── Subagent B ────────────────────────────────────────────────────────────────
@tool
def generate_report(data: str) -> str:
    """Generate a formatted report from data"""
    # ... implementation ...
    return "formatted report"

subagent_writer = create_agent(
    model="gpt-5-nano",
    tools=[generate_report],
    system_prompt="You are a technical writer. Produce clear, concise reports."
)

# ── Coordinator Tools ─────────────────────────────────────────────────────────
@tool
def delegate_research(runtime: ToolRuntime) -> str:
    """Delegate research task to research subagent using shared state."""
    context = runtime.state.get("task_context", "")
    response = subagent_research.invoke(
        {"messages": [HumanMessage(content=f"Research: {context}")]}
    )
    return response["messages"][-1].content

@tool
def delegate_writing(data: str, runtime: ToolRuntime) -> str:
    """Delegate writing task to writer subagent."""
    response = subagent_writer.invoke(
        {"messages": [HumanMessage(content=f"Write report from: {data}")]}
    )
    return response["messages"][-1].content

@tool
def update_task_context(context: str, runtime: ToolRuntime) -> Command:
    """Update the shared task context in state."""
    return Command(update={
        "task_context": context,
        "messages": [ToolMessage("Context updated", tool_call_id=runtime.tool_call_id)]
    })

# ── Dynamic Tools ─────────────────────────────────────────────────────────────
@wrap_model_call
def rbac_tools(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    role = request.runtime.context.role
    if role in ["admin", "editor"]:
        pass  # full access
    else:
        request = request.override(tools=[delegate_research])  # read-only
    return handler(request)

# ── Dynamic Prompt ────────────────────────────────────────────────────────────
@dynamic_prompt
def role_prompt(request: ModelRequest) -> str:
    role = request.runtime.context.role
    if role == "admin":
        return "You are a supervisor with full access to all capabilities."
    return "You are a read-only assistant."

# ── Supervisor Agent ──────────────────────────────────────────────────────────
supervisor = create_agent(
    model="gpt-5-nano",
    tools=[update_task_context, delegate_research, delegate_writing],
    state_schema=SystemState,
    context_schema=UserContext,
    checkpointer=InMemorySaver(),
    middleware=[
        rbac_tools,
        role_prompt,
        SummarizationMiddleware(model="gpt-4o-mini", trigger=("tokens", 500), keep=("messages", 2)),
        HumanInTheLoopMiddleware(interrupt_on={"delegate_writing": True})
    ]
)

# ── Run ───────────────────────────────────────────────────────────────────────
config = {"configurable": {"thread_id": "session-001"}}

response = supervisor.invoke(
    {"messages": [HumanMessage(content="Research the latest trends in renewable energy and write a report.")]},
    context=UserContext(user_id="user-123", role="admin", language="English"),
    config=config
)
```

---

## 7. Complete API Quick Reference

### 7.1 `create_agent()` — All Parameters

```python
agent = create_agent(
    model,                    # str (model ID) or model object
    tools=[],                 # list of @tool functions or MCP tools
    system_prompt="...",      # str — base system prompt
    response_format=None,     # Pydantic BaseModel — for structured output
    checkpointer=None,        # e.g. InMemorySaver() — enables memory
    state_schema=None,        # class inheriting AgentState — custom state
    context_schema=None,      # @dataclass — read-only runtime context
    middleware=[],            # list of middleware functions
)
```

### 7.2 `agent.invoke()` — All Parameters

```python
response = agent.invoke(
    {"messages": [HumanMessage(content="...")]},    # Input state
    config={"configurable": {"thread_id": "1"}},    # Config (for memory)
    context=MyContext(),                             # Runtime context
)
```

### 7.3 `agent.ainvoke()` — Async Version

```python
response = await agent.ainvoke(
    {"messages": [HumanMessage(content="...")]},
    config={"configurable": {"thread_id": "1"}},
    context=MyContext(),
)
```

### 7.4 `agent.stream()` — Streaming

```python
for token, metadata in agent.stream(
    {"messages": [HumanMessage(content="...")]},
    stream_mode="messages"
):
    if token.content:
        print(token.content, end="", flush=True)
```

### 7.5 `@tool` Decorator

```python
from langchain.tools import tool, ToolRuntime

@tool
def my_tool(param: str, runtime: ToolRuntime) -> str:
    """Clear description for the LLM"""
    
    # Access state
    state_value = runtime.state["my_field"]
    
    # Access context
    ctx_value = runtime.context.my_field
    
    # Get tool call ID (for ToolMessage)
    call_id = runtime.tool_call_id
    
    return "result"

# Test directly
my_tool.invoke({"param": "value"})
```

### 7.6 `Command` — Write to State from Tool

```python
from langgraph.types import Command
from langchain.messages import ToolMessage

return Command(update={
    "my_field": new_value,
    "messages": [ToolMessage("Done", tool_call_id=runtime.tool_call_id)]
})
```

### 7.7 Message Types

```python
from langchain.messages import (
    HumanMessage,      # User input
    AIMessage,         # Model response
    ToolMessage,       # Tool execution result
    RemoveMessage,     # Signal to delete a message from state
    SystemMessage,     # System prompt (used internally)
)

# Construction
HumanMessage(content="text")
HumanMessage(content=[{"type": "text", "text": "..."}, {"type": "image", ...}])
AIMessage(content="text")
ToolMessage(content="result", tool_call_id="call_id")
RemoveMessage(id=message.id)
```

### 7.8 Middleware Decorators

| Decorator | When it runs | Returns |
|-----------|-------------|---------|
| `@wrap_model_call` | Wraps every LLM call | `ModelResponse` |
| `@dynamic_prompt` | Generates system prompt before each call | `str` |
| `@before_agent` | Runs before agent's LLM call | `dict` (state update) or `None` |

### 7.9 `HumanInTheLoopMiddleware` — Resume Patterns

```python
# Approve
Command(resume={"decisions": [{"type": "approve"}]})

# Reject
Command(resume={"decisions": [{"type": "reject", "message": "reason"}]})

# Edit
Command(resume={"decisions": [{"type": "edit", "edited_action": {"name": "tool_name", "args": {...}}}]})
```

### 7.10 `MultiServerMCPClient` — Transport Config

```python
# stdio (local subprocess)
{"transport": "stdio", "command": "python", "args": ["server.py"]}

# streamable_http (remote)  
{"transport": "streamable_http", "url": "https://..."}

# uvx (npm package)
{"transport": "stdio", "command": "uvx", "args": ["mcp-server-time"]}
```

---

## 8. Production Patterns & Best Practices

### 8.1 State Design

```python
# Good: Flat, typed fields
class MyState(AgentState):
    user_id: str
    authenticated: bool
    task_status: str

# Avoid: Deeply nested or untyped fields
class BadState(AgentState):
    data: dict   # untyped — hard to work with
```

### 8.2 Tool Design

```python
# ✅ Specific, unambiguous docstring
@tool
def get_employee_vacation_days(employee_id: str) -> int:
    """Get the total remaining vacation days for a specific employee by their ID."""
    ...

# ❌ Vague docstring — LLM won't know when/how to use it
@tool
def get_data(id: str) -> dict:
    """Get some data"""
    ...
```

### 8.3 Error Handling in Tools

```python
@tool
def safe_sql_query(query: str) -> str:
    """Execute a SQL query safely"""
    try:
        return db.run(query)
    except Exception as e:
        return f"Error: {e}"   # Return error as string — agent can retry/adapt
```

### 8.4 Async Tools in Multi-Agent Systems

When subagents call remote MCP tools, use `async`:

```python
@tool
async def call_remote_agent(query: str) -> str:
    """Call the remote agent."""
    response = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
    return response["messages"][-1].content
```

Use `await coordinator.ainvoke()` when any tool in the chain is async.

### 8.5 Memory Architecture

| Use Case | Checkpointer |
|----------|-------------|
| Development/testing | `InMemorySaver()` |
| Single-server production | `SqliteSaver` |
| Distributed production | `PostgresSaver` / Redis-backed |
| LangGraph Cloud | Managed by platform |

### 8.6 Context vs. State Decision Guide

Ask yourself: "Does this data change during the conversation?"
- **YES** → Use `AgentState` (mutable, persisted)
- **NO** → Use context `@dataclass` (read-only, injected per call)

Examples:
| Data | Use |
|------|-----|
| User authentication status | `AgentState` — changes during session |
| User's role (admin/viewer) | Context — fixed per invocation |
| Conversation topic | `AgentState` — evolves |
| User language preference | Context — set externally |
| Collected form fields | `AgentState` — filled progressively |

### 8.7 Middleware Ordering

Middleware executes in the order listed. Order matters:

```python
middleware=[
    dynamic_tool_call,       # 1st: restrict tools based on auth
    dynamic_prompt_func,     # 2nd: set prompt based on auth state
    SummarizationMiddleware, # 3rd: manage context window
    HumanInTheLoopMiddleware # 4th: pause for human approval
]
```

### 8.8 Thread ID Strategy

| Strategy | Thread ID | Use For |
|----------|-----------|---------|
| Single session | `"1"` | Testing |
| Per user | `f"user-{user_id}"` | Production web app |
| Per task | `f"task-{task_id}"` | Background processing |
| Per user + session | `f"{user_id}-{session_id}"` | Multi-session users |

### 8.9 LangSmith Tracing in Production

```python
# Automatic: set env vars and all runs are traced
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=my-production-project

# Add custom metadata to traces via config
config = {
    "configurable": {"thread_id": "123"},
    "metadata": {"user_id": "u-456", "environment": "prod"}
}
```

### 8.10 Windows Async Compatibility

```python
import sys
import asyncio

# Required for MCP servers on Windows in Jupyter
if sys.platform == "win32":
    if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    if "ipykernel" in sys.modules:
        sys.stderr = sys.__stderr__
```

### 8.11 Deploying Agents with LangGraph CLI

`langgraph.json` configures the agent for deployment:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./my_agent.py:agent"
  }
}
```

```bash
# Start local server
langgraph dev

# Deploy to LangGraph Cloud
langgraph deploy
```

---

## Appendix: Key Imports Cheatsheet

```python
# ── Model Setup ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv
import os
from langchain_openai import AzureChatOpenAI
from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI

# ── Core Agent ────────────────────────────────────────────────────────────────
from langchain.agents import create_agent, AgentState
from langchain.tools import tool, ToolRuntime
from langchain.messages import HumanMessage, AIMessage, ToolMessage, RemoveMessage

# ── Memory ────────────────────────────────────────────────────────────────────
from langgraph.checkpoint.memory import InMemorySaver

# ── State & Commands ──────────────────────────────────────────────────────────
from langgraph.types import Command
from langgraph.runtime import Runtime

# ── MCP ───────────────────────────────────────────────────────────────────────
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.server.fastmcp import FastMCP

# ── Middleware ────────────────────────────────────────────────────────────────
from langchain.agents.middleware import (
    wrap_model_call,
    dynamic_prompt,
    before_agent,
    HumanInTheLoopMiddleware,
    SummarizationMiddleware,
    ModelRequest,
    ModelResponse,
)

# ── RAG ───────────────────────────────────────────────────────────────────────
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

# ── SQL ───────────────────────────────────────────────────────────────────────
from langchain_community.utilities import SQLDatabase

# ── Web Search ────────────────────────────────────────────────────────────────
from tavily import TavilyClient

# ── Structured Output ─────────────────────────────────────────────────────────
from pydantic import BaseModel

# ── Utilities ─────────────────────────────────────────────────────────────────
from pprint import pprint
from dataclasses import dataclass
from typing import Dict, Any, Callable
```

---

*End of LangChain Fundamentals Reference Guide*
