# LangChain / LangGraph / LangSmith — Complete Production Reference

> **Owner:** Tirso Gomez  
> **Purpose:** Comprehensive reference guide for building multi-agent systems with LangGraph  
> **Source:** LangChain Academy — Introduction to LangGraph (all modules, notebooks, transcripts, and deployment code)  
> **Last Updated:** 2025  

---

## Table of Contents

- [Module 0 — LangChain Foundations](#module-0--langchain-foundations)
- [Module 1 — LangGraph Fundamentals](#module-1--langgraph-fundamentals)
- [Module 2 — State & Memory Management](#module-2--state--memory-management)
- [Module 3 — Human-in-the-Loop](#module-3--human-in-the-loop)
- [Module 4 — Multi-Agent Architectures](#module-4--multi-agent-architectures)
- [Module 5 — Long-Term Memory & Memory Agents](#module-5--long-term-memory--memory-agents)
- [Module 6 — Deployment & Production](#module-6--deployment--production)
- [Architecture Patterns Catalog](#architecture-patterns-catalog)
- [Production Checklist](#production-checklist)
- [Quick Reference Index](#quick-reference-index)
- [Key Links & Resources](#key-links--resources)

---

## Module 0 — LangChain Foundations

### Environment Setup

```bash
# Core dependencies
pip install langchain_openai langchain_core langgraph langchain_tavily

# Environment variables
export OPENAI_API_KEY="..."
export LANGSMITH_API_KEY="..."
export LANGSMITH_TRACING="true"
export LANGSMITH_PROJECT="langchain-academy"
export TAVILY_API_KEY="..."
```

### Chat Models

Chat models are **stateless** LLM wrappers — they take messages in, return messages out. Every invocation is independent.

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o", temperature=0)
response = model.invoke("Hello world")
print(response.content)
```

**Azure OpenAI variant:**
```python
from langchain_openai import AzureChatOpenAI

model = AzureChatOpenAI(
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)
```

- `temperature=0` → deterministic; `temperature=1` → creative
- All chat models share the same interface → swap providers without changing downstream code
- Models are **stateless** — they don't remember previous calls. Memory requires a checkpointer (Module 2)

### Message Types

Messages have a **role** (who is speaking) and **content** (what they say):

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

messages = [
    SystemMessage(content="You are a pirate."),        # Instructions/persona
    HumanMessage(content="Hello!"),                     # User input
    AIMessage(content="Ahoy!"),                         # Model response
    # ToolMessage(content="result", tool_call_id="1")  # Tool execution result
]
response = model.invoke(messages)
```

| Type | Role | Purpose |
|------|------|---------|
| `SystemMessage` | System | Set persona, instructions, constraints |
| `HumanMessage` | User | User input |
| `AIMessage` | Assistant | Model response (may contain `tool_calls`) |
| `ToolMessage` | Tool | Result of tool execution (must have `tool_call_id`) |
| `RemoveMessage` | — | Special: removes messages by ID from state |

### Tool Calling

Tools are Python functions that LLMs can decide to invoke. The model doesn't execute the tool — it generates **structured arguments** that match the tool's schema.

```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply a and b.

    Args:
        a: first int
        b: second int
    """
    return a * b

# Bind tools to the model
llm_with_tools = model.bind_tools([multiply])

# The model generates a tool call (not the result!)
result = llm_with_tools.invoke([HumanMessage(content="What is 2 * 3?")])
print(result.tool_calls)
# [{'name': 'multiply', 'args': {'a': 2, 'b': 3}, 'id': 'call_xxx'}]
```

**Key insight from the course:** *"The model decides to call the tool and extracts the arguments, but the model does NOT execute the tool itself."* — The graph/application is responsible for executing the tool and passing the `ToolMessage` result back.

### Structured Output with `with_structured_output`

Force an LLM to produce output conforming to a specific schema:

```python
from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    search_query: str = Field(description="A focused search query")

structured_llm = model.with_structured_output(SearchQuery)
result = structured_llm.invoke("Find info about LangGraph development")
print(result.search_query)  # "LangGraph agent framework development guide"
```

This uses tool calling under the hood in most providers. Extremely useful for:
- Memory schema extraction (Module 5)
- Analyst persona generation (Module 4 Research Assistant)
- Query refinement for search tools
- Enforcing data formats in map-reduce pipelines

### Chains (LCEL)

LangChain Expression Language (LCEL) composes components with the `|` pipe operator:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_template("Tell me about {topic}")
chain = prompt | model | StrOutputParser()
result = chain.invoke({"topic": "bears"})
```

The chain automatically:
1. Formats the prompt with `{topic}`
2. Passes it to the model
3. Parses the output to a string

### Search Tools

**Tavily** — search engine optimized for LLMs and RAG:
```python
from langchain_tavily import TavilySearch

tavily_search = TavilySearch(max_results=3)
data = tavily_search.invoke({"query": "What is LangGraph?"})
```

**Wikipedia:**
```python
from langchain_community.document_loaders import WikipediaLoader

docs = WikipediaLoader(query="LangGraph", load_max_docs=2).load()
formatted = "\n\n---\n\n".join([
    f'<Document source="{d.metadata["source"]}">\n{d.page_content}\n</Document>'
    for d in docs
])
```

---

## Module 1 — LangGraph Fundamentals

### Why LangGraph?

LLMs are fundamentally **unreliable** — they hallucinate, make wrong decisions, and need guardrails. LangGraph gives developers **control** over the execution flow while still leveraging the LLM's intelligence for decisions.

> *"LangGraph is a way to build controllable agents. The key idea is that instead of the LLM dictating all control flow, you define the graph structure, and the LLM operates within it."* — Lance Martin

### Core Concepts

LangGraph models AI workflows as **directed graphs**:

| Concept | Definition | Analogy |
|---------|-----------|---------|
| **Node** | A Python function (unit of work) | A station on an assembly line |
| **Edge** | Connection between nodes (control flow) | A conveyor belt |
| **State** | Shared data object passed through the graph | The product being assembled |
| **Conditional Edge** | A function that chooses the next node dynamically | A switch on the conveyor |

### Building a Simple Graph

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# 1. Define State
class State(TypedDict):
    graph_state: str

# 2. Define Nodes (regular Python functions)
def node_1(state: State) -> dict:
    print("---Node 1---")
    return {"graph_state": state['graph_state'] + " I am"}

def node_2(state: State) -> dict:
    print("---Node 2---")
    return {"graph_state": state['graph_state'] + " happy!"}

def node_3(state: State) -> dict:
    print("---Node 3---")
    return {"graph_state": state['graph_state'] + " sad!"}

# 3. Define Conditional Edge logic
import random
def decide_mood(state: State) -> str:
    if random.random() < 0.5:
        return "node_2"
    return "node_3"

# 4. Build the Graph
builder = StateGraph(State)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_node("node_3", node_3)

builder.add_edge(START, "node_1")
builder.add_conditional_edges("node_1", decide_mood)
builder.add_edge("node_2", END)
builder.add_edge("node_3", END)

# 5. Compile
graph = builder.compile()

# 6. Run
result = graph.invoke({"graph_state": "Hi, this is Lance."})
# Output: "Hi, this is Lance. I am happy!" (50%) or "Hi, this is Lance. I am sad!" (50%)
```

### Using LangGraph Studio

LangGraph Studio is an IDE for visualizing, debugging, and interacting with graphs. Access it via:
- **Desktop app** (macOS) — uses Docker under the hood
- **Cloud** — via LangSmith (`https://smith.langchain.com/studio`)

To use Studio, you need:
1. A Python file with a compiled graph (e.g., `simple.py`)
2. A `langgraph.json` configuration file
3. A `requirements.txt`

**Example `langgraph.json`:**
```json
{
    "graphs": {
        "simple_graph": "./simple.py:graph"
    },
    "env": ".env"
}
```

Studio can visualize:
- Graph topology
- State at each node
- Memory store contents
- Thread history
- Real-time streaming

### Chain Pattern — LLM with Messages

Wrap an LLM call in a graph node with `MessagesState`:

```python
from langgraph.graph import MessagesState

class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]
```

`MessagesState` is a pre-built state with a `messages` key that uses the `add_messages` reducer. The `add_messages` reducer:
- **Appends** new messages to the list
- **Overwrites** existing messages if the new message has the same ID

```python
from langgraph.graph import MessagesState, StateGraph, START, END

def tool_calling_llm(state: MessagesState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("tool_calling_llm", tool_calling_llm)
builder.add_edge(START, "tool_calling_llm")
builder.add_edge("tool_calling_llm", END)

graph = builder.compile()
```

### Router Pattern

The LLM decides: either respond directly or call a tool.

```python
from langgraph.prebuilt import ToolNode, tools_condition

builder = StateGraph(MessagesState)
builder.add_node("tool_calling_llm", tool_calling_llm)
builder.add_node("tools", ToolNode([multiply, tavily_search]))

builder.add_edge(START, "tool_calling_llm")
builder.add_conditional_edges("tool_calling_llm", tools_condition)
builder.add_edge("tools", END)

graph = builder.compile()
```

- **`tools_condition`** — built-in function that examines the last `AIMessage`:
  - If it has `tool_calls` → route to `"tools"` node
  - Otherwise → route to `END`
- **`ToolNode`** — built-in node that executes all tool calls in the `AIMessage` and returns `ToolMessage` results

### ReAct Agent Pattern (Reason + Act)

The key difference from the router: tool results loop **back** to the LLM, creating a reasoning cycle.

```python
def assistant(state: MessagesState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)
builder.add_edge("tools", "assistant")  # ← THE LOOP — tool results go back to LLM

graph = builder.compile()
```

**The ReAct loop:**
1. **Act** — LLM calls a tool
2. **Observe** — Tool executes, result passed back to LLM as `ToolMessage`
3. **Reason** — LLM reviews the result. Decides: call another tool, or respond directly
4. Repeat until LLM responds without tool calls

> *"The agent will keep reasoning and acting until it's satisfied it has the information it needs to respond."*

**Visualize in LangSmith:** Every iteration of the loop is visible as a separate step in the trace, showing the tool calls, arguments, and results.

### Agent Memory with Checkpointer

By default, graph state is **transient** — lost after each `invoke()`. Add a checkpointer to persist conversation history:

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# Conversations are scoped by thread_id
config = {"configurable": {"thread_id": "1"}}

# First turn
graph.invoke({"messages": [HumanMessage("Add 3 and 4")]}, config)

# Second turn — the model remembers the conversation!
graph.invoke({"messages": [HumanMessage("Multiply that by 2")]}, config)
```

- Each **super-step** (node execution) saves a **checkpoint** to the checkpointer
- Checkpoints are scoped by `thread_id` — different threads = different conversations
- `MemorySaver` is in-memory (development only). Use `PostgresSaver` or `SqliteSaver` for production
- The checkpointer enables: conversation memory, time travel, human-in-the-loop, replay

### Deployment Preview (LangGraph API)

LangGraph graphs can be deployed as a server with three options:
1. **LangGraph Cloud** — managed hosting on LangChain's infrastructure
2. **Self-Hosted** — Docker on your infrastructure
3. **Self-Hosted Lite** — free tier, up to 1M nodes/year

Once deployed, interact via the **LangGraph SDK**:
```python
from langgraph_sdk import get_client
client = get_client(url="http://localhost:8123")

thread = await client.threads.create()
async for chunk in client.runs.stream(
    thread["thread_id"], "agent",
    input={"messages": [{"role": "user", "content": "Hello"}]},
    stream_mode="messages-tuple"):
    # Process streaming tokens
    pass
```

---

## Module 2 — State & Memory Management

### State Schema Options

The state schema is the **#1 architectural decision** in a LangGraph application. It defines what data flows through the graph.

| Approach | Import | Access | Runtime Validation |
|----------|--------|--------|-------------------|
| `TypedDict` | `from typing import TypedDict` | `state["key"]` | No (hints only) |
| `dataclass` | `from dataclasses import dataclass` | `state.key` | No (hints only) |
| `Pydantic BaseModel` | `from pydantic import BaseModel` | `state.key` | **Yes** |

```python
# TypedDict — lightweight, most common
from typing import TypedDict
class State(TypedDict):
    name: str
    mood: str

# dataclass — attribute access
from dataclasses import dataclass
@dataclass
class State:
    name: str
    mood: str

# Pydantic — runtime validation
from pydantic import BaseModel, field_validator
class State(BaseModel):
    name: str
    mood: str

    @field_validator('mood')
    @classmethod
    def validate_mood(cls, value):
        if value not in ["happy", "sad"]:
            raise ValueError("mood must be 'happy' or 'sad'")
        return value
```

> *"Pydantic models are particularly useful when you want to enforce specific value constraints at runtime — for example, ensuring mood is always 'happy' or 'sad'."*

### Reducers — How State Updates Merge

**Without a reducer**, a state key uses **overwrite** semantics — the last write wins. This causes `InvalidUpdateError` when parallel nodes write to the same key.

**With a reducer**, you define how updates combine:

```python
from typing import Annotated
from operator import add
from langgraph.graph import add_messages

class State(TypedDict):
    # Default: overwrite (no annotation)
    summary: str
    
    # Append/concatenate
    context: Annotated[list, add]
    
    # Smart message handling (append + dedup by ID)
    messages: Annotated[list, add_messages]
    
    # Custom: sort after each update
    ranked_items: Annotated[list, sorted_add]
```

**Reducer behaviors:**

| Reducer | Behavior | Use Case |
|---------|----------|----------|
| Default (none) | Last write wins | Summary, final answer |
| `operator.add` | Append lists/concatenate | Context accumulation |
| `add_messages` | Append + overwrite by message ID | Conversation messages |
| Custom function | Any logic | Sorting, counters, null-safety |

**Custom null-safe reducer:**
```python
def reduce_list(left: list | None, right: list | None) -> list:
    """Safely concatenate lists, handling None values."""
    if not left:
        left = []
    if not right:
        right = []
    return left + right

class State(TypedDict):
    context: Annotated[list, reduce_list]
```

**Custom sorting reducer:**
```python
def sorted_add(left, right):
    """Append then sort — controls order of parallel updates."""
    if not isinstance(left, list):
        left = [left]
    if not isinstance(right, list):
        right = [right]
    return sorted(left + right)
```

> *"Within the same step, LangGraph decides how to order parallel updates. You don't have control over that ordering unless you supply a reducer that manages ordering."*

### `add_messages` Reducer

The built-in `add_messages` reducer is the most commonly used:

```python
from langgraph.graph import add_messages

# Behavior 1: Append new messages
add_messages([msg1], [msg2])  # → [msg1, msg2]

# Behavior 2: Overwrite by ID
add_messages([msg_with_id_1], [new_msg_with_id_1])  # → [new_msg_with_id_1]

# Behavior 3: Remove by ID
from langchain_core.messages import RemoveMessage
add_messages([msg1, msg2], [RemoveMessage(id=msg1.id)])  # → [msg2]
```

### Multiple Schemas — Private State & I/O Filtering

Nodes often need internal data that shouldn't be exposed to the user. Use separate schemas:

```python
# Internal state — everything the graph needs
class OverallState(TypedDict):
    messages: list
    internal_reasoning: str    # private
    retrieval_scores: list     # private

# Input schema — what the user provides
class InputState(TypedDict):
    messages: list

# Output schema — what the user sees
class OutputState(TypedDict):
    messages: list

builder = StateGraph(
    state_schema=OverallState,
    input=InputState,
    output=OutputState,
)
```

**Private state for edges only:**
Nodes can pass data to the NEXT node without writing it to the overall state:

```python
class PrivateState(TypedDict):
    baz: int  # only visible between two specific nodes

def node_2(state: PrivateState):
    return {"bar": state["baz"] + 1}  # reads private, writes to overall

# Wire it up
builder.add_edge("node_1", "node_2")  # node_1 returns {"baz": 1}
```

### Message Management Techniques

As conversations grow, they consume more tokens. Three strategies to manage this:

**1. Trim Messages — Keep only recent messages:**
```python
from langchain_core.messages import trim_messages

trimmed = trim_messages(
    messages,
    max_tokens=100,
    strategy="last",           # Keep last N tokens
    token_counter=ChatOpenAI(model="gpt-4o"),
    allow_partial=False,       # Don't split messages
    include_system=True,       # Always keep system message
)
```

**2. Filter Messages — Remove specific message types:**
```python
# Remove tool messages
filtered = [m for m in messages if not isinstance(m, ToolMessage)]

# Or use RemoveMessage to remove by ID
from langchain_core.messages import RemoveMessage
messages_to_remove = [RemoveMessage(id=m.id) for m in messages[:-2]]
```

**3. Summarize — Compress history into a running summary:**
```python
def summarize_conversation(state: State):
    """Create a running summary, keeping only recent messages."""
    summary = state.get("summary", "")
    
    if summary:
        summary_message = f"Summary of earlier conversation: {summary}\n\n"
    else:
        summary_message = ""
    
    messages = state["messages"]
    # Summarize all but the last 2 messages
    messages_to_summarize = messages[:-2]
    
    summary_prompt = f"{summary_message}Extend the summary with new messages:\n{messages_to_summarize}"
    new_summary = model.invoke([HumanMessage(content=summary_prompt)])
    
    # Delete summarized messages, keep last 2
    delete_messages = [RemoveMessage(id=m.id) for m in messages[:-2]]
    
    return {
        "summary": new_summary.content,
        "messages": delete_messages,
    }
```

### External Memory with SQLite Checkpointer

For persistence across app restarts:

```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

# File-based persistence
db = sqlite3.connect("checkpoints.db", check_same_thread=False)
memory = SqliteSaver(db)

graph = builder.compile(checkpointer=memory)
```

With a checkpointer, switching threads builds on existing history:
```python
# Thread 1 — first conversation
config_1 = {"configurable": {"thread_id": "1"}}
graph.invoke({"messages": [HumanMessage("I'm Lance")]}, config_1)

# Thread 2 — completely separate conversation
config_2 = {"configurable": {"thread_id": "2"}}
graph.invoke({"messages": [HumanMessage("What's my name?")]}, config_2)
# → "I don't know your name"

# Thread 1 — remembers!
graph.invoke({"messages": [HumanMessage("What's my name?")]}, config_1)
# → "Your name is Lance"
```

---

## Module 3 — Human-in-the-Loop

### Three Motivations for HIL

1. **Approval** — require human sign-off before risky operations (tool calls, external writes)
2. **Debugging** — rewind to reproduce issues, inspect intermediate states
3. **Editing** — modify the agent's plan, inject new information, redirect behavior

> *"Never let agents run unsupervised on high-stakes actions."*

### Streaming

Stream graph execution to see results in real-time:

```python
# Stream mode: "values" — full state at each step
for event in graph.stream(input, config, stream_mode="values"):
    event['messages'][-1].pretty_print()

# Stream mode: "updates" — only changes at each step
for event in graph.stream(input, config, stream_mode="updates"):
    for node, updates in event.items():
        print(f"Node '{node}': {updates}")

# Stream individual tokens from LLM calls
async for event in graph.astream_events(input, config, version="v2"):
    if event["event"] == "on_chat_model_stream":
        token = event["data"]["chunk"].content
        if token:
            print(token, end="", flush=True)

# messages-tuple mode (LangGraph API / SDK)
# Returns (message_chunk, metadata) tuples for real-time token streaming
```

### Breakpoints (Static Interrupts)

Pause the graph **before** or **after** a specific node:

```python
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"],   # pause BEFORE tools node
)
```

**Full approval workflow:**
```python
# 1. Run until breakpoint
initial_input = {"messages": [HumanMessage("Search for LangGraph")]}
for event in graph.stream(initial_input, config, stream_mode="values"):
    event['messages'][-1].pretty_print()

# 2. Inspect state — what tool call is pending?
state = graph.get_state(config)
print(f"Next node: {state.next}")          # ('tools',)
print(f"Pending tool call: {state.values['messages'][-1].tool_calls}")

# 3. Human approves → resume from checkpoint
for event in graph.stream(None, config, stream_mode="values"):
    event['messages'][-1].pretty_print()
```

### Editing State (Update State)

Modify state before resuming:

```python
# Get current state
state = graph.get_state(config)
last_message = state.values['messages'][-1]

# Modify the LLM's tool call
modified_tool_call = last_message.tool_calls[0].copy()
modified_tool_call['args'] = {'query': 'better query'}

# Create modified message with same ID (triggers overwrite via add_messages)
new_message = AIMessage(
    content=last_message.content,
    tool_calls=[modified_tool_call],
    id=last_message.id,  # ← same ID = overwrite
)

# Apply state update
graph.update_state(config, {"messages": [new_message]})

# Resume
for event in graph.stream(None, config, stream_mode="values"):
    event['messages'][-1].pretty_print()
```

**`as_node` parameter** — pretend the update came from a specific node:
```python
# Update state as if the "human_feedback" node produced it
graph.update_state(config, {"messages": [HumanMessage("Actually, search for X")]}, as_node="human_feedback")
```

This controls which node the graph transitions to next (based on the graph's edges from that node).

### Dynamic Breakpoints

Conditionally interrupt inside a node using `interrupt()`:

```python
from langgraph.types import interrupt

def human_feedback(state: State):
    """Interrupt and wait for human input."""
    feedback = interrupt("Please provide feedback:")
    # Execution resumes here when human responds
    return {"messages": [HumanMessage(content=feedback)]}
```

Or raise `NodeInterrupt` for diagnostic-style interrupts:

```python
from langgraph.types import NodeInterrupt

def my_tool(state: State):
    if len(state['input']) > 5:
        raise NodeInterrupt(f"Input too long: {len(state['input'])} chars")
    return {"output": "processed"}
```

### Time Travel

Every checkpoint is replayable. You can fork execution from any point in history.

```python
# Get all checkpoints (newest first)
all_states = list(graph.get_state_history(config))

# Find the state you want to replay from (e.g., 3rd state)
target_state = all_states[2]

# Fork from that checkpoint
fork_config = target_state.config  # contains checkpoint_id

# Option 1: Replay — re-execute from that point with same input
for event in graph.stream(None, fork_config, stream_mode="values"):
    event['messages'][-1].pretty_print()

# Option 2: Re-execute with modified input
graph.update_state(fork_config, {"messages": [HumanMessage("Different question")]})
for event in graph.stream(None, fork_config, stream_mode="values"):
    event['messages'][-1].pretty_print()
```

**Replay vs Fork:**
- **Replay**: Re-run from a checkpoint with the same inputs. Useful for reproducing behavior.
- **Fork**: Modify state at a checkpoint and run from there. Creates a new branch of execution.

### HIL Patterns Summary

| Pattern | Mechanism | Use Case |
|---------|-----------|----------|
| **Approval Gate** | `interrupt_before=["risky_node"]` | Tool calls that modify external systems |
| **Edit & Continue** | `update_state()` + resume | Tweak the LLM's plan |
| **Reject & Redirect** | `update_state(as_node=...)` | Wrong tool, redirect to different node |
| **Review Output** | `interrupt_after=["node"]` | Verify before delivering to user |
| **Dynamic Approval** | `interrupt()` inside node | Conditional human review |
| **Multi-Turn Dialog** | `interrupt()` + human message | Agent needs clarification |
| **Time Travel / Fork** | `get_state_history()` + `update_state()` | Explore alternatives, debug |

---

## Module 4 — Multi-Agent Architectures

### Parallelization (Fan-Out / Fan-In)

Run multiple nodes simultaneously by adding multiple edges from the same source:

```python
builder.add_edge(START, "search_web")        # fan out
builder.add_edge(START, "search_wikipedia")  # fan out
builder.add_edge("search_web", "generate_answer")        # fan in
builder.add_edge("search_wikipedia", "generate_answer")  # fan in
```

**Critical rules:**
1. Parallel nodes writing to the **same key** MUST have a **reducer** — otherwise `InvalidUpdateError`
2. The graph **waits** for all parallel branches to complete before the fan-in node runs
3. Within the same step, you **cannot control** the order of parallel updates (use a custom sorting reducer if needed)

**Practical example — parallel search aggregation:**
```python
from typing import Annotated
from operator import add

class State(TypedDict):
    question: str
    answer: str
    context: Annotated[list, add]  # ← accumulate from parallel sources

def search_web(state: State):
    """Search the web and write results to context."""
    results = tavily_search.invoke({"query": state["question"]})
    formatted = "\n\n".join([
        f"<Document source='{r['url']}'>\n{r['content']}\n</Document>"
        for r in results
    ])
    return {"context": [formatted]}  # ← list because of add reducer

def search_wikipedia(state: State):
    """Search Wikipedia and write results to context."""
    docs = WikipediaLoader(query=state["question"], load_max_docs=2).load()
    formatted = "\n\n".join([
        f"<Document source='{d.metadata['source']}'>\n{d.page_content}\n</Document>"
        for d in docs
    ])
    return {"context": [formatted]}

def generate_answer(state: State):
    """Generate answer using all accumulated context."""
    context = "\n\n".join(state["context"])
    prompt = f"Answer based on:\n{context}\n\nQuestion: {state['question']}"
    answer = model.invoke([HumanMessage(content=prompt)])
    return {"answer": answer.content}

# Build graph
builder = StateGraph(State)
builder.add_node("search_web", search_web)
builder.add_node("search_wikipedia", search_wikipedia)
builder.add_node("generate_answer", generate_answer)

builder.add_edge(START, "search_web")
builder.add_edge(START, "search_wikipedia")
builder.add_edge("search_web", "generate_answer")
builder.add_edge("search_wikipedia", "generate_answer")
builder.add_edge("generate_answer", END)

graph = builder.compile()
```

### Sub-Graphs

Encapsulate complex logic within nested graphs. Each sub-graph has its **own state** — parent and sub-graph communicate via **overlapping keys**.

```python
# === Sub-Graph: Failure Analysis ===
class FailureAnalysisState(TypedDict):
    cleaned_logs: list    # ← shared with parent (input)
    failures: list        # internal only
    fa_summary: str       # ← shared with parent (output)

class FailureAnalysisOutputState(TypedDict):
    fa_summary: str  # ← only this key bubbles up to parent

fa_builder = StateGraph(
    FailureAnalysisState,
    output=FailureAnalysisOutputState  # ← KEY: controls what parent sees
)
fa_builder.add_node("get_failures", get_failures)
fa_builder.add_node("generate_summary", generate_summary)
fa_builder.add_edge(START, "get_failures")
fa_builder.add_edge("get_failures", "generate_summary")
fa_builder.add_edge("generate_summary", END)

fa_graph = fa_builder.compile()

# === Parent Graph ===
class EntryGraphState(TypedDict):
    raw_logs: list
    cleaned_logs: list            # ← shared: input to sub-graphs
    fa_summary: str               # ← from failure analysis sub-graph
    report: str                   # ← from summarization sub-graph
    processed_logs: Annotated[list, add]  # ← both sub-graphs write here

entry_builder = StateGraph(EntryGraphState)
entry_builder.add_node("clean_logs", clean_logs)
entry_builder.add_node("failure_analysis", fa_graph)         # ← add compiled sub-graph as node
entry_builder.add_node("summarization", summarization_graph) # ← another sub-graph

entry_builder.add_edge(START, "clean_logs")
entry_builder.add_edge("clean_logs", "failure_analysis")     # fan out
entry_builder.add_edge("clean_logs", "summarization")        # fan out
entry_builder.add_edge("failure_analysis", END)
entry_builder.add_edge("summarization", END)

entry_graph = entry_builder.compile()
```

**Why `output_schema` matters:**
> *"Both sub-graphs' output state will contain all their keys, even if unmodified. Without output_schema, keys like `cleaned_logs` would appear in both outputs, causing a collision. The output_schema filters what gets returned to the parent."*

**Sub-graph benefits:**
- Encapsulate complex agent logic (own state, own message history)
- Make LangSmith traces **much more readable** — sub-graphs are collapsible
- Enable team-of-agents architectures

### Map-Reduce with the `Send` API

`Send` enables **dynamic parallelism** — spawn N parallel nodes at runtime based on data:

```python
from langgraph.types import Send

# === State ===
class OverallState(TypedDict):
    topic: str
    subjects: list
    jokes: Annotated[list, add]  # ← accumulate from mapped nodes
    best_joke: str

class JokeState(TypedDict):
    subject: str  # ← each mapped node gets its own state

# === Map function (conditional edge that uses Send) ===
def continue_to_jokes(state: OverallState):
    """Dynamically spawn a generate_joke node for each subject."""
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

# === Nodes ===
def generate_topics(state: OverallState):
    """Generate a list of subjects related to the topic."""
    response = model.with_structured_output(Subjects).invoke(
        [HumanMessage(f"Generate {len(state['subjects'])} subjects about {state['topic']}")]
    )
    return {"subjects": response.subjects}

def generate_joke(state: JokeState):
    """Generate a joke about a single subject (runs in parallel)."""
    joke = model.invoke([HumanMessage(f"Write a joke about {state['subject']}")])
    return {"jokes": [joke.content]}  # ← list, appended via reducer

def best_joke(state: OverallState):
    """Select the best joke from all generated jokes (reduce step)."""
    jokes_str = "\n\n".join(state["jokes"])
    response = model.with_structured_output(BestJoke).invoke(
        [HumanMessage(f"Pick the best joke:\n{jokes_str}")]
    )
    return {"best_joke": state["jokes"][response.id]}

# === Build Graph ===
builder = StateGraph(OverallState)
builder.add_node("generate_topics", generate_topics)
builder.add_node("generate_joke", generate_joke)
builder.add_node("best_joke", best_joke)

builder.add_edge(START, "generate_topics")
builder.add_conditional_edges("generate_topics", continue_to_jokes, ["generate_joke"])
builder.add_edge("generate_joke", "best_joke")
builder.add_edge("best_joke", END)

graph = builder.compile()
```

**Key properties of `Send`:**
1. The list can be **arbitrarily long** — 3 subjects, 100 subjects, doesn't matter
2. Each spawned node can have its **own state** (decoupled from `OverallState`)
3. Results are collected via the **reducer** on the accumulation key
4. No need to manually define edges — `Send` handles the wiring
5. Shown as a **dotted line** (conditional edge) in graph visualizations

### Research Assistant — Complete Multi-Agent System

The capstone project combines every concept from the course into a real-world research automation system.

**Architecture:**
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        Research Assistant Graph                                   │
│                                                                                   │
│  Topic → create_analysts (HIL) → human_feedback → [approve?]                     │
│                                       ↓                                           │
│                              initiate_all_interviews                              │
│                        ┌──────────┼──────────┐                                    │
│                   [Send]     [Send]      [Send]                                   │
│                     ↓          ↓           ↓                                      │
│               ┌─────────┐ ┌─────────┐ ┌─────────┐                                │
│               │Interview│ │Interview│ │Interview│  ← Sub-graphs (each with       │
│               │  Sub-   │ │  Sub-   │ │  Sub-   │     own InterviewState)         │
│               │  Graph  │ │  Graph  │ │  Graph  │                                 │
│               └────┬────┘ └────┬────┘ └────┬────┘                                │
│                    ↓           ↓           ↓                                      │
│              write_section  write_section  write_section                           │
│                    ↓           ↓           ↓                                      │
│                    └──────────┼───────────┘                                        │
│                          write_report                                              │
│                               ↓                                                   │
│                        write_introduction                                          │
│                               ↓                                                   │
│                        write_conclusion                                            │
│                               ↓                                                   │
│                         finalize_report                                            │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Phase 1: Analyst Generation with HIL**

```python
from pydantic import BaseModel, Field

class Analyst(BaseModel):
    affiliation: str = Field(description="Primary affiliation of the analyst.")
    name: str = Field(description="Name of the analyst.")
    role: str = Field(description="Role of the analyst in the context of the topic.")
    description: str = Field(description="Description of the analyst focus, concerns, and motives.")

    @property
    def persona(self) -> str:
        return f"Name: {self.name}\nRole: {self.role}\nAffiliation: {self.affiliation}\nDescription: {self.description}\n"

class Perspectives(BaseModel):
    analysts: list[Analyst] = Field(description="Comprehensive list of analysts with their roles and affiliations.")

class GenerateAnalystsState(TypedDict):
    topic: str
    max_analysts: int
    human_analyst_feedback: str
    analysts: list[Analyst]
```

The graph creates analysts using `model.with_structured_output(Perspectives)`, then pauses at a `human_feedback` node with `interrupt_before`. The user can refine analysts (e.g., "Add a startup CEO perspective") until they approve.

**Phase 2: Interview Sub-Graph**

Each analyst conducts a multi-turn interview with an AI expert that has access to search tools:

```python
class InterviewState(MessagesState):
    max_num_turns: int
    context: Annotated[list, add]  # ← accumulate search results
    analyst: Analyst
    interview: str
    sections: list

def generate_question(state: InterviewState):
    """Analyst asks a question based on their persona."""
    analyst = state["analyst"]
    system_message = analyst_instructions.format(
        goals=analyst.persona,
        # instruct to say "Thank you" when done
    )
    question = model.invoke([SystemMessage(content=system_message)] + state["messages"])
    return {"messages": [question]}

def search_web(state: InterviewState):
    """Distill conversation into focused query, then search."""
    structured_llm = model.with_structured_output(SearchQuery)
    query = structured_llm.invoke([search_instructions] + state["messages"])
    results = tavily_search.invoke({"query": query.search_query})
    return {"context": [format_results(results)]}

def search_wikipedia(state: InterviewState):
    """Same pattern, different source."""
    # ... similar to search_web

def generate_answer(state: InterviewState):
    """Expert answers using accumulated context."""
    context = "\n\n".join(state["context"])
    system_message = answer_instructions.format(persona=state["analyst"].persona, context=context)
    answer = model.invoke([SystemMessage(content=system_message)] + state["messages"])
    answer.name = "expert"
    return {"messages": [answer]}

def should_continue(state: InterviewState):
    """End interview when max turns reached or analyst says 'thank you'."""
    messages = state["messages"]
    num_expert_answers = sum(1 for m in messages if isinstance(m, AIMessage) and m.name == "expert")
    if num_expert_answers >= state.get("max_num_turns", 2):
        return "save_interview"
    if "thank you" in messages[-1].content.lower():
        return "save_interview"
    return "ask_question"
```

**Phase 3: Parallel Interviews via Send API**

```python
def initiate_all_interviews(state: ResearchGraphState):
    """Spawn parallel interview sub-graphs for each analyst."""
    topic = state["topic"]
    return [
        Send("conduct_interview", {
            "analyst": analyst,
            "messages": [HumanMessage(content=f"You are writing an article about {topic}...")],
            "max_num_turns": 2,
        })
        for analyst in state["analysts"]
    ]
```

**Phase 4: Report Generation (Reduce)**

```python
def write_report(state: ResearchGraphState):
    """Combine all interview sections into a final report."""
    sections = state["sections"]
    formatted_sections = "\n\n".join([f"## {s}" for s in sections])
    report = model.invoke([
        SystemMessage(content=report_writer_instructions.format(
            topic=state["topic"],
            context=formatted_sections,
        ))
    ])
    return {"content": report.content}
```

**Concepts used:**

| Concept | How It's Used |
|---------|---------------|
| Human-in-the-loop | Review analysts before heavy research |
| Structured output | Generate analyst personas, search queries |
| Sub-graphs | Each interview encapsulated with own state |
| Parallelization | Expert searches web + Wikipedia simultaneously |
| Map-reduce (Send) | Spawn interviews for each analyst in parallel |
| Multi-turn conversation | Analyst ↔ Expert interview loop |
| Custom state | Interview has InterviewState, parent has ResearchGraphState |
| Output schema | Control what flows from interview sub-graph to parent |

**Performance (from transcript):** *"Each interview took 23-24 seconds. Overall latency is only 35 seconds. These clearly ran in parallel — sequentially would be 3x higher."*

---

## Module 5 — Long-Term Memory & Memory Agents

### Memory Concepts

> *"Memory is a cognitive function that allows people to store, retrieve, and use information to understand their present and future."* — from the course

**Two types of memory in LangGraph:**

| Dimension | Short-Term | Long-Term |
|-----------|-----------|-----------|
| **Scope** | Within a single thread | Across all threads |
| **Mechanism** | Checkpointer (`MemorySaver`) | Store (`InMemoryStore`) |
| **Scoped by** | `thread_id` | `user_id` / namespace |
| **Use case** | Conversation history | User profile, ToDos, preferences |
| **Persistence** | Per conversation | Permanent |

### Memory Type Taxonomy (from CoALA paper)

| Type | Human Analogy | Agent Example | Structure |
|------|---------------|---------------|-----------|
| **Semantic** | Facts learned in school | User profile, ToDo items | Profile (single doc) or Collection (list) |
| **Episodic** | Past experiences | Prior agent actions, few-shot examples | Collections of past trajectories |
| **Procedural** | Motor skills, how-to | Agent instructions, prompts | Instructions text |

**Profile vs Collection for semantic memory:**

| Approach | Pros | Cons | Example |
|----------|------|------|---------|
| **Profile** (single doc) | Easy to retrieve, single representation | Harder to maintain as it grows | User profile: name, location, interests |
| **Collection** (list of docs) | Small, scoped items; easy to add | Retrieval challenge at scale | ToDo list: each item is a separate memory |

### Memory Update Timing

| Approach | Description | Pros | Cons |
|----------|-------------|------|------|
| **Hot path** | Update during conversation (like ChatGPT) | Real-time, transparent to user | May increase latency |
| **Background** | Separate process runs periodically | No impact on UX | Memories may not be immediately available |

### LangGraph Store API

```python
from langgraph.store.memory import InMemoryStore
import uuid

store = InMemoryStore()

# === PUT: Store a memory ===
namespace = ("memory", "user_123")  # tuple acts like directory path
key = str(uuid.uuid4())             # unique key (like filename)
value = {"content": "User likes biking in SF"}  # must be a dict

store.put(namespace, key, value)

# === SEARCH: Get all memories in a namespace ===
memories = store.search(namespace)
for m in memories:
    print(f"Key: {m.key}, Value: {m.value}")

# === GET: Retrieve a specific memory ===
memory = store.get(namespace, key)
print(memory.value)  # {"content": "User likes biking in SF"}
```

**Namespace pattern:** Tuples work like directory paths:
- `("memory", "user_123")` — user's general memories
- `("todo", "personal", "user_123")` — user's personal ToDos
- `("instructions", "user_123")` — user's custom instructions

### Chatbot with Both Memory Types

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

# --- Nodes ---
def call_model(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    """Call LLM with personalized system message from long-term memory."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    
    # Get existing memory
    existing = store.get(namespace, "user_memory")
    memory_content = existing.value["memory"] if existing else "No memory found."
    
    system_msg = f"You are a helpful assistant. Here's what you know about the user:\n{memory_content}"
    response = model.invoke([SystemMessage(content=system_msg)] + state["messages"])
    return {"messages": [response]}

def write_memory(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    """Extract user information from conversation and save to store."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    
    existing = store.get(namespace, "user_memory")
    existing_content = existing.value.get("memory", "") if existing else ""
    
    # Ask LLM to update memory based on conversation
    prompt = f"""Review the conversation. Extract user-specific details (name, preferences, etc.).
    Existing memory: {existing_content}
    Merge new info with existing memory."""
    
    new_memory = model.invoke(state["messages"] + [SystemMessage(content=prompt)])
    store.put(namespace, "user_memory", {"memory": new_memory.content})

# --- Build Graph ---
builder = StateGraph(MessagesState)
builder.add_node("call_model", call_model)
builder.add_node("write_memory", write_memory)
builder.add_edge(START, "call_model")
builder.add_edge("call_model", "write_memory")
builder.add_edge("write_memory", END)

# Compile with BOTH memory types
checkpointer = MemorySaver()      # short-term (within thread)
memory_store = InMemoryStore()     # long-term (across threads)

graph = builder.compile(checkpointer=checkpointer, store=memory_store)

# --- Usage ---
config = {"configurable": {"thread_id": "1", "user_id": "lance"}}
graph.invoke({"messages": [HumanMessage("I'm Lance. I like biking in SF.")]}, config)

# New thread, same user — memory persists!
config2 = {"configurable": {"thread_id": "2", "user_id": "lance"}}
graph.invoke({"messages": [HumanMessage("Where should I go biking?")]}, config2)
# → Recommends SF biking spots because it remembers from long-term memory
```

### Trustcall — Reliable Schema Extraction & Updates

[Trustcall](https://github.com/hinthornw/trustcall) solves two problems:
1. **Complex schemas** are hard to extract reliably with `with_structured_output` (validation errors)
2. **Full regeneration** of schemas is wasteful and can **lose information**

Trustcall uses **JSON patches** under the hood: it prompts the model to produce only the changes, then validates and retries if needed.

**Basic extraction:**
```python
from trustcall import create_extractor
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    user_name: str = Field(description="The user's preferred name")
    interests: list[str] = Field(description="A list of the user's interests")

extractor = create_extractor(
    model,
    tools=[UserProfile],
    tool_choice="UserProfile",  # force extraction into this schema
)

result = extractor.invoke({
    "messages": [
        SystemMessage(content="Extract user profile from conversation"),
        HumanMessage(content="I'm Lance. I like biking."),
    ]
})

# result has: .messages (raw tool calls), .responses (parsed Pydantic objects), .response_metadata
profile = result["responses"][0]  # UserProfile(user_name="Lance", interests=["biking"])
```

**Updating existing schemas (the magic):**
```python
# First extraction
existing_profile = profile.model_dump()
# {"user_name": "Lance", "interests": ["biking"]}

# Updated conversation
new_messages = [HumanMessage(content="I also enjoy eating at bakeries")]

# Update — Trustcall produces a JSON PATCH, not a full regeneration
result = extractor.invoke({
    "messages": [SystemMessage(content="Update the profile")] + new_messages,
    "existing": [("UserProfile", existing_profile)],  # ← provide existing data
})

updated = result["responses"][0]
# UserProfile(user_name="Lance", interests=["biking", "bakeries"])
```

**Collection management (insert + update):**
```python
class Memory(BaseModel):
    content: str = Field(description="The main content of the memory")

collection_extractor = create_extractor(
    model,
    tools=[Memory],
    tool_choice="Memory",
    enable_inserts=True,  # ← allow creating NEW items in the collection
)

# Provide existing memories as tuples: (id, tool_name, dict)
existing = [
    ("mem_001", "Memory", {"content": "Lance went biking in GGP"}),
]

result = collection_extractor.invoke({
    "messages": messages,
    "existing": existing,
})

# Check metadata to see what Trustcall did:
for r in result["response_metadata"]:
    if r.get("json_doc_id"):
        print(f"Updated existing memory: {r['json_doc_id']}")
    else:
        print("Created new memory")
```

**Spy listener for visibility:**
```python
# See exactly what Trustcall did under the hood
class Spy:
    def __init__(self):
        self.called_tools = []
    def __call__(self, run):
        # Extract all tool calls from the run
        q = [run]
        while q:
            r = q.pop()
            if r.child_runs:
                q.extend(r.child_runs)
            if r.run_type == "chat_model":
                for generation in r.outputs.get("generations", []):
                    for gen in generation:
                        if gen.get("message", {}).get("tool_calls"):
                            self.called_tools.extend(gen["message"]["tool_calls"])

spy = Spy()
extractor_with_spy = extractor.with_listeners(on_end=spy)

result = extractor_with_spy.invoke(...)

# Now spy.called_tools contains ALL tool calls including PatchDoc
for tc in spy.called_tools:
    if tc["name"] == "PatchDoc":
        print(f"Planned edits: {tc['args']['planned_edits']}")
```

### Memory Agent — `task_mAIstro`

An agent that **decides** when and what to memorize, managing three memory types:

**Memory schemas:**
```python
from pydantic import BaseModel, Field

class Profile(BaseModel):
    """User profile information."""
    name: str = Field(description="The user's name", default=None)
    location: str = Field(description="Where the user lives", default=None)
    job: str = Field(description="The user's job title", default=None)
    connections: list[str] = Field(description="Important people", default_factory=list)
    interests: list[str] = Field(description="User's interests", default_factory=list)

class ToDo(BaseModel):
    """A ToDo item."""
    task: str = Field(description="The task to be done")
    time_to_complete: int = Field(description="Estimated minutes", default=None)
    deadline: str = Field(description="When it needs to be done", default=None)
    solutions: list[str] = Field(description="Suggested approaches", default_factory=list)
    status: str = Field(description="Current status", default="not started")
```

**Decision tool:**
```python
class UpdateMemory(TypedDict):
    """Decides which memory type to update."""
    update_type: Literal['user', 'todo', 'instructions']
```

**Agent flow:**
```python
def task_maistro(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    """Core agent node — loads memories and decides what to do."""
    user_id = config["configurable"]["user_id"]
    
    # Load all three memory types from store
    profile = store.search(("profile", user_id))
    todos = store.search(("todo", todo_category, user_id))
    instructions = store.get(("instructions", user_id), "user_instructions")
    
    # Format memories into system prompt
    system_msg = MODEL_SYSTEM_MESSAGE.format(
        user_profile=format_profile(profile),
        todos=format_todos(todos),
        instructions=format_instructions(instructions),
    )
    
    # Model decides: respond directly OR call UpdateMemory tool
    response = model.bind_tools([UpdateMemory]).invoke(
        [SystemMessage(content=system_msg)] + state["messages"]
    )
    return {"messages": [response]}

def route_message(state: MessagesState):
    """Route based on the model's decision."""
    last_msg = state["messages"][-1]
    if not last_msg.tool_calls:
        return END
    
    update_type = last_msg.tool_calls[0]["args"]["update_type"]
    return {
        "user": "update_profile",
        "todo": "update_todos",
        "instructions": "update_instructions",
    }[update_type]
```

**Update nodes:**
```python
def update_todos(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    """Update ToDo collection using Trustcall."""
    user_id = config["configurable"]["user_id"]
    namespace = ("todo", todo_category, user_id)
    
    # Get existing ToDos
    existing = store.search(namespace)
    existing_memories = [(m.key, "ToDo", m.value) for m in existing]
    
    # Run Trustcall with spy for visibility
    spy = Spy()
    extractor = todo_extractor.with_listeners(on_end=spy)
    result = extractor.invoke({
        "messages": state["messages"],
        "existing": existing_memories,
    })
    
    # Save updated/new ToDos to store
    for r, meta in zip(result["responses"], result["response_metadata"]):
        key = meta.get("json_doc_id", str(uuid.uuid4()))
        store.put(namespace, key, r.model_dump())
    
    # Report what Trustcall did back to the agent
    tool_call_id = state["messages"][-1].tool_calls[0]["id"]
    update_info = extract_tool_info(spy.called_tools, "ToDo")
    return {"messages": [ToolMessage(content=update_info, tool_call_id=tool_call_id)]}

def update_instructions(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    """Update procedural memory (instructions)."""
    user_id = config["configurable"]["user_id"]
    namespace = ("instructions", user_id)
    
    existing = store.get(namespace, "user_instructions")
    existing_text = existing.value.get("instructions", "") if existing else ""
    
    # LLM rewrites instructions based on conversation
    new_instructions = model.invoke([
        SystemMessage(content=f"Current instructions: {existing_text}\nUpdate based on conversation."),
        *state["messages"],
    ])
    
    store.put(namespace, "user_instructions", {"instructions": new_instructions.content})
    
    tool_call_id = state["messages"][-1].tool_calls[0]["id"]
    return {"messages": [ToolMessage(content="Instructions updated", tool_call_id=tool_call_id)]}
```

**Important implementation detail — ToolMessage response:**
> *"When a chat model makes a tool call, it expects a ToolMessage back verifying the tool call was actually performed. This is a very important point in tool calling workflow communication."*

### Configurable Memory Agent

```python
from langchain_core.runnables import RunnableConfig

class Configuration:
    """Configurable parameters for the memory agent."""
    user_id: str = "default-user"
    todo_category: str = "general"      # namespace ToDos separately
    task_maistro_role: str = ""          # custom system prompt addition
```

This enables **Assistants** (Module 6) — same graph, different configurations.

---

## Module 6 — Deployment & Production

### LangGraph Platform Architecture

```
┌──────────────────────────────────────────────────┐
│              LangGraph Platform                    │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Redis    │  │ Postgres │  │ LangGraph API  │  │
│  │          │  │          │  │ Server         │  │
│  │ • Pub/Sub │  │ • Check- │  │ • HTTP Worker  │  │
│  │ • Stream  │  │   points │  │ • Queue Worker │  │
│  │ • Cancel  │  │ • Store  │  │ • Your Graph   │  │
│  │          │  │ • Tasks  │  │                │  │
│  └──────────┘  └──────────┘  └────────────────┘  │
└──────────────────────────────────────────────────┘
```

**How it works under the hood:**
1. Client sends request → **HTTP Worker** receives it, creates a `run_id` in Postgres
2. **Queue Worker** polls Postgres for new runs, picks up the run, executes the graph
3. During execution, Queue Worker publishes state updates to **Redis**
4. HTTP Worker subscribes to Redis updates, streams them back to the client
5. Checkpoints and Store data persist in **Postgres**

### Creating a Deployment

**Required files:**
```
deployment/
├── task_maistro.py      # Your graph code
├── configuration.py     # Configurable parameters
├── langgraph.json       # API configuration
├── requirements.txt     # Dependencies
├── docker-compose.yml   # Container orchestration
└── .env                 # Environment variables (optional)
```

**`langgraph.json`:**
```json
{
    "dependencies": ["."],
    "graphs": {
        "task_maistro": "./task_maistro.py:graph"
    },
    "env": ".env"
}
```

**`requirements.txt`:**
```
langgraph
langchain_openai
langchain_community
langchain_tavily
trustcall
```

**`docker-compose.yml`:**
```yaml
volumes:
  langgraph-data:
    driver: local

services:
  langgraph-redis:
    image: redis:6
    healthcheck:
      test: redis-cli ping
      interval: 5s
      timeout: 1s
      retries: 5

  langgraph-postgres:
    image: postgres:16
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - langgraph-data:/var/lib/postgresql/data
    healthcheck:
      test: pg_isready -U postgres
      start_period: 10s
      timeout: 1s
      retries: 5
      interval: 5s

  langgraph-api:
    image: ${IMAGE_NAME}
    ports:
      - "8123:8000"
    depends_on:
      langgraph-redis:
        condition: service_healthy
      langgraph-postgres:
        condition: service_healthy
    environment:
      REDIS_URI: redis://langgraph-redis:6379
      LANGSMITH_API_KEY: ${LANGSMITH_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      POSTGRES_URI: postgres://postgres:postgres@langgraph-postgres:5432/postgres?sslmode=disable
```

**Deploy in 2 commands:**
```bash
cd module-6/deployment

# 1. Build Docker image
langgraph build -t my-image

# 2. Launch all services
IMAGE_NAME=my-image docker compose up
```

**Access points after deployment:**
- API: `http://localhost:8123`
- API Docs: `http://localhost:8123/docs`
- Studio: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123`

### Deployment Options

| Option | Managed By | Infrastructure | Cost | Best For |
|--------|-----------|---------------|------|----------|
| **Self-Hosted Lite** | You | Yours | Free (≤1M nodes/yr) | Development, prototyping |
| **LangGraph Cloud** | LangChain | LangChain's | Pay-per-use | Fastest onboarding |
| **BYOC** | LangChain | Yours | Enterprise | Data privacy + managed service |
| **Self-Hosted** | You | Yours | Enterprise | Full control |

### LangGraph SDK

The SDK provides Python (and JS) clients for interacting with deployed graphs.

```python
from langgraph_sdk import get_client

client = get_client(url="http://localhost:8123")
```

**Threads — Multi-turn conversations:**
```python
# Create a thread
thread = await client.threads.create()

# Get thread state (all message history)
state = await client.threads.get_state(thread["thread_id"])

# Copy/fork a thread
forked = await client.threads.copy(thread["thread_id"])

# Get full history
history = await client.threads.get_history(thread["thread_id"])
```

**Runs — Execute the graph:**
```python
# Background run (fire & forget)
run = await client.runs.create(
    thread["thread_id"],
    "task_maistro",
    input={"messages": [{"role": "user", "content": "Add a ToDo: buy groceries"}]},
    config={"configurable": {"user_id": "tirso"}},
)

# Wait for completion
await client.runs.join(thread["thread_id"], run["run_id"])

# Check status
status = await client.runs.get(thread["thread_id"], run["run_id"])
print(status["status"])  # "success"

# Streaming run
async for chunk in client.runs.stream(
    thread["thread_id"],
    "task_maistro",
    input={"messages": [{"role": "user", "content": "Summary of my ToDos"}]},
    config={"configurable": {"user_id": "tirso"}},
    stream_mode="messages-tuple",
):
    if chunk.event == "messages":
        # chunk.data contains (message_chunk, metadata)
        msg = chunk.data[0]
        if hasattr(msg, 'content') and msg['content']:
            print(msg['content'], end="", flush=True)
```

**Store — Long-term memory via SDK:**
```python
# Search store
items = await client.store.search(("todo", "general", "tirso"))
for item in items:
    print(f"Key: {item['key']}, Value: {item['value']}")

# Add to store
await client.store.put_item(("todo", "general", "tirso"), "new_key", {"task": "Test"})

# Delete from store
await client.store.delete_item(("todo", "general", "tirso"), "new_key")
```

**Human-in-the-Loop via SDK:**
```python
# Get state history
history = await client.threads.get_history(thread["thread_id"])

# Find a checkpoint to fork from
target = history[2]  # e.g., third state

# Update state at that checkpoint (overwrite message by ID)
await client.threads.update_state(
    thread["thread_id"],
    values={"messages": [{"role": "user", "content": "Modified question", "id": target_msg_id}]},
    checkpoint_id=target["checkpoint_id"],
)

# Resume from modified checkpoint
async for chunk in client.runs.stream(
    thread["thread_id"],
    "task_maistro",
    input=None,
    config={"configurable": {"user_id": "tirso"}},
    checkpoint_id=target["checkpoint_id"],
):
    pass
```

### RemoteGraph

Use a deployed graph directly within the LangGraph library (e.g., as a sub-graph):

```python
from langgraph.pregel.remote import RemoteGraph

remote_graph = RemoteGraph("task_maistro", url="http://localhost:8123")

# Use like any local graph
result = remote_graph.invoke(
    {"messages": [HumanMessage("Hello")]},
    config={"configurable": {"user_id": "tirso"}},
)

# Can also be added as a sub-graph in another graph:
parent_builder.add_node("remote_agent", remote_graph)
```

### Assistants — Versioned Agent Configurations

Create multiple personas from the same deployed graph:

```python
# Create a personal assistant
personal = await client.assistants.create(
    "task_maistro",
    config={"configurable": {
        "user_id": "tirso",
        "todo_category": "personal",
        "task_maistro_role": """For personal tasks:
        - List tasks by deadline when asked for summary
        - Highlight tasks missing deadlines
        - Gently encourage adding time estimates"""
    }},
)

# Create a work assistant (same graph, different behavior)
work = await client.assistants.create(
    "task_maistro",
    config={"configurable": {
        "user_id": "tirso",
        "todo_category": "work",
        "task_maistro_role": """For work tasks:
        - REQUIRE realistic timeframes for EVERY task
        - ENFORCE deadlines — reject tasks without them
        - Flag unrealistic time estimates"""
    }},
)

# Use an assistant
async for chunk in client.runs.stream(
    thread["thread_id"],
    work["assistant_id"],  # ← use assistant ID instead of graph name
    input={"messages": [{"role": "user", "content": "Add task: review PR"}]},
):
    pass

# List, search, update, delete assistants
all_assistants = await client.assistants.search()
await client.assistants.update(work["assistant_id"], config={...})
await client.assistants.delete(old_assistant["assistant_id"])
```

**Key insight:** Assistants namespace both **behavior** (via `task_maistro_role` prompt) and **data** (via `todo_category` namespace in the store). A personal assistant and work assistant maintain completely separate ToDo lists.

### Double Texting — Concurrent Run Handling

When a user sends a second request before the first completes:

```python
# === REJECT — Block new runs until current completes ===
run2 = await client.runs.create(
    thread_id, graph_name, input=input2,
    multitask_strategy="reject",
)
# → Raises error: "Cannot create new run while existing run is in progress"

# === ENQUEUE — Queue the new run, execute after current finishes ===
run2 = await client.runs.create(
    thread_id, graph_name, input=input2,
    multitask_strategy="enqueue",
)
# → run2 waits for run1 to complete, then executes

# === INTERRUPT — Stop current run, save progress, start new ===
run2 = await client.runs.create(
    thread_id, graph_name, input=input2,
    multitask_strategy="interrupt",
)
# → run1 stops but its progress IS saved to thread
# → run2 starts immediately

# === ROLLBACK — Stop current run, DELETE it, start new ===
run2 = await client.runs.create(
    thread_id, graph_name, input=input2,
    multitask_strategy="rollback",
)
# → run1 stops and its progress is DELETED from thread
# → run2 starts from clean state
```

| Strategy | Run1 Progress | Run2 Timing | Use Case |
|----------|--------------|-------------|----------|
| **Reject** | Completes | Rejected | Prevent accidental duplicates |
| **Enqueue** | Completes | After run1 | Ordered processing |
| **Interrupt** | Saved to thread | Immediate | User changed their mind |
| **Rollback** | Deleted | Immediate | User corrected their input |

---

## Architecture Patterns Catalog

### Pattern 1: Simple Chain
```
START → LLM → END
```
Best for: Single-turn Q&A, text generation, simple transformations.

### Pattern 2: Router
```
START → LLM → [tool_calls?] → Tools → END
                    ↓ (no)
                   END
```
Best for: Conditional tool use without multi-step reasoning.

### Pattern 3: ReAct Agent
```
START → LLM ←→ Tools (loop until done)
         ↓ (no tool calls)
        END
```
Best for: Multi-step reasoning, research, complex tasks requiring multiple tool calls.

### Pattern 4: Agent with Memory
```
Same as ReAct + Checkpointer for thread persistence
Config: {thread_id, user_id}
```
Best for: Conversational agents, assistants that remember context.

### Pattern 5: Parallel Search Aggregation
```
START → [search_web, search_wiki] → generate_answer → END
```
Best for: RAG with multiple sources, context enrichment.

### Pattern 6: Human-in-the-Loop Approval
```
START → LLM → [interrupt_before] → Tools → LLM → END
```
Best for: Tool calls that modify external systems, financial transactions.

### Pattern 7: Sub-Graph Architecture
```
Parent: START → clean → [sub_graph_a, sub_graph_b] → END
Sub-graph A: START → process → summarize → END
```
Best for: Team-of-agents, encapsulated workflows with own state.

### Pattern 8: Map-Reduce (Dynamic Parallelism)
```
START → generate_tasks → [Send] → task₁, task₂, ..., taskₙ → aggregate → END
```
Best for: Variable-length workloads, batch processing, research across topics.

### Pattern 9: Research Assistant (Full Multi-Agent)
```
START → create_analysts (HIL) → [Send] → interview₁..ₙ (sub-graphs) → write_report → END
```
Best for: Open-ended research, report generation, complex analysis.

### Pattern 10: Memory Agent
```
START → agent → [route] → update_profile / update_todos / update_instructions → agent → END
```
Best for: Personalized assistants, task management, user-adaptive applications.

---

## Production Checklist

### Before Deployment
- [ ] Replace `MemorySaver` with `PostgresSaver` or `SqliteSaver`
- [ ] Use `InMemoryStore` only for development; Postgres handles Store in production deployments
- [ ] Set `LANGSMITH_TRACING=true` for observability
- [ ] Define `input` and `output` schemas to hide internal state
- [ ] Add reducers to ALL state keys that could receive parallel writes
- [ ] Test with LangGraph Studio before deploying
- [ ] Configure double texting strategy for your use case
- [ ] Set appropriate `max_num_turns` for interview/loop patterns

### Error Handling
- [ ] Always return `ToolMessage` after a tool call (models expect it)
- [ ] Use `try/except` around external API calls in nodes
- [ ] Use `field_validator` (Pydantic) for critical state integrity
- [ ] Trustcall handles extraction validation/retries automatically
- [ ] Handle `NodeInterrupt` for graceful human-in-the-loop

### Deployment
- [ ] Create `langgraph.json` with correct graph paths
- [ ] Build Docker image with `langgraph build -t image-name`
- [ ] Configure `docker-compose.yml` with API keys
- [ ] `docker compose up` to start Redis + Postgres + API server
- [ ] Test via SDK before connecting frontend
- [ ] Create Assistants for different use cases/personas

### Observability (LangSmith)
- [ ] All runs are automatically traced when `LANGSMITH_TRACING=true`
- [ ] Sub-graphs appear as collapsible sections in traces
- [ ] Monitor token usage, latency, and cost per run
- [ ] Parallel runs show actual parallelism (e.g., 3 interviews in ~25s not 75s)

---

## Quick Reference Index

| Concept | Module | Import / Usage |
|---------|--------|----------------|
| `StateGraph` | 1 | `from langgraph.graph import StateGraph` |
| `MessagesState` | 1 | `from langgraph.graph import MessagesState` |
| `START`, `END` | 1 | `from langgraph.graph import START, END` |
| `ToolNode` | 1 | `from langgraph.prebuilt import ToolNode` |
| `tools_condition` | 1 | `from langgraph.prebuilt import tools_condition` |
| `add_messages` | 2 | `from langgraph.graph import add_messages` |
| `RemoveMessage` | 2 | `from langchain_core.messages import RemoveMessage` |
| `trim_messages` | 2 | `from langchain_core.messages import trim_messages` |
| `MemorySaver` | 2 | `from langgraph.checkpoint.memory import MemorySaver` |
| `SqliteSaver` | 2 | `from langgraph.checkpoint.sqlite import SqliteSaver` |
| `interrupt_before/after` | 3 | `graph.compile(interrupt_before=["node"])` |
| `interrupt()` | 3 | `from langgraph.types import interrupt` |
| `NodeInterrupt` | 3 | `from langgraph.types import NodeInterrupt` |
| `update_state()` | 3 | `graph.update_state(config, values, as_node=...)` |
| `get_state()` | 3 | `graph.get_state(config)` |
| `get_state_history()` | 3 | `graph.get_state_history(config)` |
| `Send` | 4 | `from langgraph.types import Send` |
| `add_conditional_edges` | 4 | `builder.add_conditional_edges(src, fn, targets)` |
| `output_schema` | 4 | `StateGraph(State, output=OutputState)` |
| `InMemoryStore` | 5 | `from langgraph.store.memory import InMemoryStore` |
| `create_extractor` | 5 | `from trustcall import create_extractor` |
| `with_structured_output` | 5 | `model.with_structured_output(Schema)` |
| `@tool` | 0 | `from langchain_core.tools import tool` |
| `get_client` | 6 | `from langgraph_sdk import get_client` |
| `RemoteGraph` | 6 | `from langgraph.pregel.remote import RemoteGraph` |
| `RunnableConfig` | 5 | `from langchain_core.runnables import RunnableConfig` |

---

## Key Links & Resources

| Resource | URL |
|----------|-----|
| LangGraph Docs | https://langchain-ai.github.io/langgraph/ |
| LangSmith Docs | https://docs.smith.langchain.com/ |
| LangGraph API Reference | https://langchain-ai.github.io/langgraph/reference/ |
| Trustcall | https://github.com/hinthornw/trustcall |
| LangChain Academy | https://academy.langchain.com |
| STORM Paper (multi-turn interviews) | https://arxiv.org/abs/2402.14207 |
| CoALA Paper (agent memory taxonomy) | Referenced in Module 5 |
| LangGraph Platform Docs | https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/ |
| LangGraph Studio | https://smith.langchain.com/studio |

---

*This document was generated from the complete LangChain Academy course materials: 7 modules, 31 notebooks, 12 studio Python files, deployment configurations, and full course transcriptions.*
