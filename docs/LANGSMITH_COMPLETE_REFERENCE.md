# LangSmith Fundamentals — Complete Reference Guide
### For Building Production-Ready Multi-Agent Systems with LangChain, LangGraph & LangSmith

> **Purpose**: This document is a complete, production-ready reference derived from every notebook, utility file, and application in the `intro-to-langsmith` course. It is structured to act as both a learning guide and a practical blueprint for building your first multi-agent system.

---

## Table of Contents

1. [Environment Setup & Project Scaffolding](#1-environment-setup--project-scaffolding)
2. [Module 0 — RAG Application Foundation](#2-module-0--rag-application-foundation)
3. [Module 1 — Tracing Fundamentals & Advanced Patterns](#3-module-1--tracing-fundamentals--advanced-patterns)
4. [Module 2 — Evaluation & Experimentation Framework](#4-module-2--evaluation--experimentation-framework)
5. [Module 3 — Prompt Engineering Lifecycle](#5-module-3--prompt-engineering-lifecycle)
6. [Module 4 — Feedback & Production Monitoring](#6-module-4--feedback--production-monitoring)
7. [Module 5 — Online Evaluation & Run Filtering](#7-module-5--online-evaluation--run-filtering)
8. [Multi-Agent System Architecture](#8-multi-agent-system-architecture)
9. [LangGraph Integration with LangSmith](#9-langgraph-integration-with-langsmith)
10. [Production Patterns & Best Practices](#10-production-patterns--best-practices)
11. [Complete End-to-End Code Reference](#11-complete-end-to-end-code-reference)

---

## 1. Environment Setup & Project Scaffolding

### 1.1 Required Dependencies

```text
# requirements.txt (from the course)
langchain
langgraph
langgraph-sdk
langgraph-checkpoint-sqlite
langsmith==0.7.7
langchain-community
langchain-core
langchain-openai
langchain-text-splitters
notebook
python-dotenv
lxml
scikit-learn
pandas
pyarrow
openai
pydantic
certifi
nest_asyncio
```

Install with:
```bash
pip install -r requirements.txt
```

### 1.2 Environment Variables

There are two approaches used throughout the course. Choose one per project.

**Approach A — Inline (quick dev/testing)**
```python
import os

os.environ["OPENAI_API_KEY"]      = "sk-..."
os.environ["LANGSMITH_API_KEY"]   = "ls__..."
os.environ["LANGSMITH_TRACING"]   = "true"          # Enable tracing
os.environ["LANGSMITH_PROJECT"]   = "langsmith-academy"  # Logical project bucket
```

**Approach B — `.env` file (recommended for all real work)**
```bash
# .env (never commit to git)
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=ls__...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=my-multi-agent-project
```

```python
from dotenv import load_dotenv
load_dotenv(dotenv_path="../../.env", override=True)
```

**Azure OpenAI variant** (used in modules 2, 3, 4, 5):
```bash
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME=text-embedding-ada-002
AZURE_OPENAI_EMBEDDINGS_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBEDDINGS_ENDPOINT=https://<your-resource>.openai.azure.com/
```

### 1.3 Checking Tracing Status

```python
from langsmith import utils

print(utils.tracing_is_enabled())  # True / False
```

### 1.4 Optional — EU Region

```bash
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

---

## 2. Module 0 — RAG Application Foundation

### 2.1 High-Level Architecture

```
User Question
     │
     ▼
┌────────────────────┐
│  retrieve_documents │  (run_type="chain") → invokes vectorstore retriever
└────────────────────┘
     │
     ▼
┌────────────────────┐
│  generate_response  │  (run_type="chain") → formats context + calls LLM
└────────────────────┘
     │
     ▼
┌────────────────────┐
│     call_openai     │  (run_type="llm")   → raw OpenAI call
└────────────────────┘
     │
     ▼
     Answer
```

### 2.2 Vector Database Setup (`utils.py`)

Used across **all modules** — the single source of truth for the course's SKLearn vector store.

```python
import os
import tempfile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.sitemap import SitemapLoader
from langchain_community.vectorstores import SKLearnVectorStore
from langchain_openai import OpenAIEmbeddings

def get_vector_db_retriever():
    persist_path = os.path.join(tempfile.gettempdir(), "union.parquet")
    embd = OpenAIEmbeddings()

    # Load existing vectorstore if it exists
    if os.path.exists(persist_path):
        vectorstore = SKLearnVectorStore(
            embedding=embd,
            persist_path=persist_path,
            serializer="parquet"
        )
        return vectorstore.as_retriever(lambda_mult=0)

    # Otherwise build from LangSmith docs
    loader = SitemapLoader(
        web_path="https://docs.langchain.com/sitemap.xml",
        filter_urls=["https://docs.langchain.com/langsmith/"],
        continue_on_failure=True
    )
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=500, chunk_overlap=0
    )
    splits = splitter.split_documents(docs)

    vectorstore = SKLearnVectorStore.from_documents(
        documents=splits,
        embedding=embd,
        persist_path=persist_path,
        serializer="parquet"
    )
    vectorstore.persist()
    return vectorstore.as_retriever(lambda_mult=0)
```

> **Key notes**:
> - `lambda_mult=0` disables diversity penalty (MMR) → pure similarity search.
> - `parquet` serializer allows persistence across process restarts.
> - Building the DB takes ~40–60 seconds on first run (hitting the sitemap).

### 2.3 Complete RAG Application (`app.py` — Module 2/3)

```python
import os
import tempfile
from typing import List
import nest_asyncio
from langsmith import traceable
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.sitemap import SitemapLoader
from langchain_community.vectorstores import SKLearnVectorStore
from langchain_openai import OpenAIEmbeddings

MODEL_NAME       = "gpt-4o-mini"
MODEL_PROVIDER   = "openai"
APP_VERSION      = 1.0
RAG_SYSTEM_PROMPT = """You are an assistant for question-answering tasks.
Use the following pieces of retrieved context to answer the latest question.
If you don't know the answer, say so. Use three sentences maximum.
"""

openai_client = OpenAI()
nest_asyncio.apply()

# ── Build retriever ──────────────────────────────────────────────────────────
def get_vector_db_retriever():
    persist_path = os.path.join(tempfile.gettempdir(), "union.parquet")
    embd = OpenAIEmbeddings()
    if os.path.exists(persist_path):
        return SKLearnVectorStore(
            embedding=embd, persist_path=persist_path, serializer="parquet"
        ).as_retriever(lambda_mult=0)
    loader = SitemapLoader(
        web_path="https://docs.langchain.com/sitemap.xml",
        filter_urls=["https://docs.langchain.com/langsmith/"],
        continue_on_failure=True,
    )
    splits = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=500, chunk_overlap=0
    ).split_documents(loader.load())
    vs = SKLearnVectorStore.from_documents(
        documents=splits, embedding=embd,
        persist_path=persist_path, serializer="parquet"
    )
    vs.persist()
    return vs.as_retriever(lambda_mult=0)

retriever = get_vector_db_retriever()

# ── RAG pipeline ─────────────────────────────────────────────────────────────

@traceable(run_type="chain")
def retrieve_documents(question: str):
    return retriever.invoke(question)

@traceable(run_type="chain")
def generate_response(question: str, documents):
    formatted_docs = "\n\n".join(doc.page_content for doc in documents)
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Context: {formatted_docs}\n\nQuestion: {question}"},
    ]
    return call_openai(messages)

@traceable(
    run_type="llm",
    metadata={"ls_provider": MODEL_PROVIDER, "ls_model_name": MODEL_NAME}
)
def call_openai(messages: List[dict]) -> str:
    return openai_client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
    )

@traceable(run_type="chain")
def langsmith_rag(question: str):
    documents = retrieve_documents(question)
    response  = generate_response(question, documents)
    return response.choices[0].message.content

# ── Usage ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    question = "What is LangSmith used for?"
    print(langsmith_rag(question))
```

### 2.4 LangSmith Extra — Runtime Metadata

You can inject **metadata, tags, run IDs, and parent context** at call time using `langsmith_extra`:

```python
# Attach metadata at runtime (not decorator time)
ai_answer = langsmith_rag(
    question,
    langsmith_extra={
        "metadata": {"website": "www.example.com", "user_id": "usr_123"}
    }
)
```

---

## 3. Module 1 — Tracing Fundamentals & Advanced Patterns

### 3.1 How `@traceable` Works

> The `@traceable` decorator:
> 1. Creates a `RunTree` for each invocation.
> 2. Inserts the run into the current trace hierarchy.
> 3. Streams inputs, name, metadata to LangSmith on a **background thread** (non-blocking).
> 4. Patches the run on error or successful completion.

**Minimum viable tracing:**
```python
from langsmith import traceable

@traceable
def my_function(input_text: str) -> str:
    return input_text.upper()
```

### 3.2 Run Types

| Type | Purpose | When to Use |
|------|---------|-------------|
| `"chain"` | Multi-step orchestration | Default; wrappers, pipelines, agents |
| `"llm"` | Language model calls | Raw OpenAI, Anthropic, etc. calls |
| `"retriever"` | Document retrieval | Vector DB queries, knowledge graph lookups |
| `"tool"` | Function/tool invocations | Tool calls from an agent |
| `"prompt"` | Prompt hydration | Formatting a template before sending to LLM |
| `"parser"` | Structured extraction | Output parsing, JSON extraction |

### 3.3 LLM Run Format Requirements

For **chat models** to render correctly in the LangSmith UI with cost tracking:

```python
@traceable(
    run_type="llm",
    metadata={
        "ls_provider": "openai",      # Required for cost calc
        "ls_model_name": "gpt-4o-mini" # Required for cost calc
    }
)
def call_openai(messages: list):
    # Input MUST be named "messages" and be a list of role/content dicts
    return openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
```

**Accepted output formats** (any of these works):
```python
# Format 1 — OpenAI choices style (canonical)
{"choices": [{"message": {"role": "assistant", "content": "..."}}]}

# Format 2 — Single message
{"message": {"role": "assistant", "content": "..."}}

# Format 3 — Role/content dict
{"role": "assistant", "content": "..."}

# Format 4 — Tuple
["assistant", "Hello!"]
```

### 3.4 Streaming LLM Runs

```python
def _reduce_chunks(chunks: list):
    """Combine streaming chunks into canonical output format."""
    all_text = "".join(
        [chunk["choices"][0]["message"]["content"] for chunk in chunks]
    )
    return {"choices": [{"message": {"content": all_text, "role": "assistant"}}]}

@traceable(
    run_type="llm",
    metadata={"ls_provider": "my_provider", "ls_model_name": "my_model"},
    reduce_fn=_reduce_chunks     # ← Aggregates streamed chunks into one run
)
def my_streaming_model(messages: list):
    for chunk in produce_chunks(messages):
        yield {"choices": [{"message": {"content": chunk, "role": "assistant"}}]}
```

### 3.5 Retriever Run Format

```python
@traceable(run_type="retriever")
def retrieve_docs(query: str):
    raw_results = my_db.search(query)
    # Must return this specific shape for LangSmith to render docs
    return [
        {
            "page_content": r["text"],
            "type": "Document",          # Literal "Document"
            "metadata": {"source": r["url"], "score": r["score"]}
        }
        for r in raw_results
    ]
```

### 3.6 Tool Run Format

```python
import json
from typing import Optional, List
from langsmith import traceable
from openai import OpenAI

openai_client = OpenAI()

@traceable(run_type="tool")
def get_current_temperature(location: str, unit: str) -> int:
    """Tool that gets temperature — annotated so LangSmith renders it as a tool call."""
    return 65 if unit == "Fahrenheit" else 17

@traceable(run_type="llm")
def call_openai(messages: List[dict], tools: Optional[List[dict]]):
    return openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0,
        tools=tools
    )

@traceable(run_type="chain")
def ask_about_weather(inputs, tools):
    response = call_openai(inputs, tools)
    tool_call_args = json.loads(
        response.choices[0].message.tool_calls[0].function.arguments
    )
    tool_response = {
        "role": "tool",
        "content": json.dumps({
            "temperature": get_current_temperature(
                tool_call_args["location"], tool_call_args["unit"]
            )
        }),
        "tool_call_id": response.choices[0].message.tool_calls[0].id
    }
    inputs.append(response.choices[0].message)
    inputs.append(tool_response)
    return call_openai(inputs, None)    # Second call with tool result
```

### 3.7 Metadata and Tags

```python
# === Static metadata (set at decoration time) ===
@traceable(
    run_type="llm",
    name="GPT-4o-Mini LLM Call",             # Custom display name
    metadata={
        "vectordb": "sklearn",
        "ls_provider": "openai",
        "ls_model_name": "gpt-4o-mini",
        "app_version": "2.1"
    },
    tags=["production", "rag", "v2"]
)
def call_openai(messages: list):
    ...

# === Dynamic metadata (set at call time) ===
result = call_openai(
    messages,
    langsmith_extra={
        "metadata": {"user_id": user_id, "session": session_id},
        "tags": ["experiment-42"]
    }
)
```

### 3.8 Conversational Threads (Multi-Turn)

Group multiple traces into a single conversation thread using one of these reserved metadata keys:

- `session_id`
- `thread_id`
- `conversation_id`

```python
import uuid
thread_id = str(uuid.uuid4())

# Turn 1
langsmith_rag(
    "How do I set up tracing?",
    langsmith_extra={"metadata": {"thread_id": thread_id}}
)

# Turn 2 — linked to the same conversation in LangSmith UI
langsmith_rag(
    "Can you give me a code example?",
    langsmith_extra={"metadata": {"thread_id": thread_id}}
)
```

### 3.9 Alternative Tracing Methods

#### Method A — LangChain / LangGraph (Auto-Tracing)

Only environment variables required — no decorator needed when using LangChain runnables:

```python
import os
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = "ls__..."

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

llm = ChatOpenAI(model="gpt-4o-mini")
# All .invoke() calls on LangChain/LangGraph objects are auto-traced
```

#### Method B — `trace` Context Manager

Use when you need precise control over what goes into a trace:

```python
from langsmith import trace

def generate_response(question: str, documents):
    formatted_docs = "\n\n".join(doc.page_content for doc in documents)

    with trace(
        name="Generate Response",
        run_type="chain",
        inputs={"question": question, "formatted_docs": formatted_docs},
        metadata={"foo": "bar"},
    ) as ls_trace:
        response = my_llm_call(formatted_docs, question)
        ls_trace.end(outputs={"output": response})   # Explicitly set output
    
    return response
```

#### Method C — `wrap_openai`

Wrap the OpenAI client once — all calls are auto-traced without `@traceable` on every function:

```python
from langsmith.wrappers import wrap_openai
import openai

# Wrap once at startup
openai_client = wrap_openai(openai.Client())

# Now every openai_client.chat.completions.create() is automatically traced
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
    langsmith_extra={"metadata": {"custom_key": "value"}}   # Still accepts extra params
)
```

> **When to use**: When you want light-touch tracing without modifying function signatures.

#### Method D — `RunTree` (Full Manual Control)

Use when you need maximum control over the trace hierarchy, e.g., across service boundaries:

```python
from langsmith import RunTree
from openai import OpenAI

openai_client = OpenAI()

def retrieve_documents(parent_run: RunTree, question: str):
    child = parent_run.create_child(
        name="Retrieve Documents",
        run_type="retriever",
        inputs={"question": question},
    )
    documents = my_retriever(question)
    child.end(outputs={"documents": documents})
    child.post()
    return documents

def call_openai(parent_run: RunTree, messages: list):
    child = parent_run.create_child(
        name="OpenAI Call",
        run_type="llm",
        inputs={"messages": messages},
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini", messages=messages
    )
    child.end(outputs=response)
    child.post()
    return response

def run_pipeline(question: str):
    # Create root run
    root = RunTree(
        name="RAG Pipeline",
        run_type="chain",
        inputs={"question": question},
    )
    root.post()

    docs     = retrieve_documents(root, question)
    response = call_openai(root, build_messages(docs, question))

    root.end(outputs={"answer": response.choices[0].message.content})
    root.post()
    return response.choices[0].message.content
```

> **Note**: When using `RunTree`, set `LANGSMITH_TRACING=false` — you're managing the lifecycle manually.

### 3.10 Distributed Tracing in Threads

```python
from langsmith.utils import ContextThreadPoolExecutor
from langsmith import traceable, get_current_run_tree
from concurrent.futures import ThreadPoolExecutor

# Option A — Use LangSmith's thread pool (recommended)
@traceable
def process_in_parallel(items: list):
    with ContextThreadPoolExecutor() as executor:
        results = list(executor.map(process_item, items))
    return results

@traceable
def process_item(item):
    return item * 2

# Option B — Pass parent run tree manually
@traceable
def process_in_parallel_manual(items: list):
    rt = get_current_run_tree()
    with ThreadPoolExecutor() as executor:
        results = list(
            executor.map(
                lambda x: process_item(x, langsmith_extra={"parent": rt}),
                items
            )
        )
    return results
```

---

## 4. Module 2 — Evaluation & Experimentation Framework

### 4.1 The Evaluator Contract

An evaluator is any Python callable that receives run context and returns a score:

```
evaluate(target_fn, data=dataset, evaluators=[my_evaluator])
           │
           ▼
For each example in dataset:
  Run target_fn(inputs) → outputs
  Call my_evaluator(inputs, reference_outputs, outputs) → {score, key}
  Write feedback to LangSmith
```

**Signature variants:**

```python
# Version 1 — Named dicts (most common, recommended)
def my_evaluator(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    score = compute(inputs, reference_outputs, outputs)
    return {"score": score, "key": "my_metric"}

# Version 2 — Run and Example objects (access full metadata)
from langsmith.schemas import Run, Example

def my_evaluator_v2(root_run: Run, example: Example) -> dict:
    run_output    = root_run["outputs"]["output"]
    expected      = example["outputs"]["output"]
    score         = compute(run_output, expected)
    return {"score": score, "key": "my_metric"}
```

### 4.2 Simple Heuristic Evaluator

```python
def correct_label(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    score = int(outputs.get("output") == reference_outputs.get("label"))
    return {"score": score, "key": "correct_label"}

def is_concise_enough(reference_outputs: dict, outputs: dict) -> dict:
    """Check that the output is at most 1.5× the length of the reference."""
    score = int(len(outputs["output"]) < 1.5 * len(reference_outputs["output"]))
    return {"key": "is_concise", "score": score}
```

### 4.3 LLM-as-Judge Evaluator (Pydantic Structured Output)

```python
from openai import OpenAI
from pydantic import BaseModel, Field

client = OpenAI()

class SimilarityScore(BaseModel):
    similarity_score: int = Field(
        description="Semantic similarity 1–10; 1 = unrelated, 10 = identical."
    )

def compare_semantic_similarity(
    inputs: dict, reference_outputs: dict, outputs: dict
) -> dict:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a semantic similarity evaluator. Compare the meanings of "
                    "two responses to a question. Score 1–10 where 1 = unrelated, "
                    "10 = identical in meaning."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {inputs['question']}\n"
                    f"Reference: {reference_outputs['output']}\n"
                    f"Candidate: {outputs['output']}"
                ),
            },
        ],
        response_format=SimilarityScore,
    )
    score = completion.choices[0].message.parsed.similarity_score
    return {"score": score, "key": "semantic_similarity"}
```

### 4.4 Summary Evaluator (Dataset-Level Metrics)

A **summary evaluator** gets the full list of inputs/outputs and computes aggregate metrics like F1, BLEU, ROUGE, etc.

```python
def f1_score_summary_evaluator(
    outputs: list[dict], reference_outputs: list[dict]
) -> dict:
    tp = fp = fn = 0
    for pred, ref in zip(outputs, reference_outputs):
        p_class = pred["class"]
        r_class = ref["class"]
        if p_class == "Toxic" and r_class == "Toxic":
            tp += 1
        elif p_class == "Toxic" and r_class == "Not toxic":
            fp += 1
        elif p_class == "Not toxic" and r_class == "Toxic":
            fn += 1

    if tp == 0:
        return {"key": "f1_score", "score": 0.0}

    precision = tp / (tp + fp)
    recall    = tp / (tp + fn)
    f1        = 2 * (precision * recall) / (precision + recall)
    return {"key": "f1_score", "score": f1}

# Usage — note: summary_evaluators parameter (not evaluators)
results = client.evaluate(
    my_classifier,
    data=dataset,
    summary_evaluators=[f1_score_summary_evaluator],
    experiment_prefix="classifier-v1"
)
```

### 4.5 Dataset Creation & Management

```python
from langsmith import Client

client = Client()

# ── Create dataset from scratch ──────────────────────────────────────────────
dataset = client.create_dataset(
    dataset_name="RAG Application Golden Dataset",
    description="Golden dataset for the LangSmith RAG app"
)

# Prepare data
example_pairs = [
    ("How do I set up tracing?",   "Use @traceable decorator..."),
    ("What is LangSmith for?",     "LangSmith is a platform for LLM observability..."),
]
inputs  = [{"question": q} for q, _ in example_pairs]
outputs = [{"output": a}   for _, a in example_pairs]

client.create_examples(
    inputs=inputs,
    outputs=outputs,
    dataset_id=dataset.id,
)

# ── Clone a public dataset ───────────────────────────────────────────────────
public_dataset = client.clone_public_dataset(
    "https://smith.langchain.com/public/9078d2f1-7bef-4ba7-b795-210a17682ef9/d"
)
```

### 4.6 Running Experiments with `evaluate()`

```python
from langsmith import evaluate, Client

client = Client()
dataset_name = "RAG Application Golden Dataset"

# Target function MUST accept a dict and return a dict
def target_function(inputs: dict) -> dict:
    answer = langsmith_rag(inputs["question"])
    return {"output": answer}

# ── Basic experiment ──────────────────────────────────────────────────────────
results = evaluate(
    target_function,
    data=dataset_name,
    evaluators=[is_concise_enough, compare_semantic_similarity],
    experiment_prefix="gpt-4o-mini-v1"
)

# ── With extra parameters ─────────────────────────────────────────────────────
results = evaluate(
    target_function,
    data=dataset_name,
    evaluators=[is_concise_enough],
    experiment_prefix="experiment-v2",
    num_repetitions=2,        # Run each example N times
    max_concurrency=4,        # Parallel threads (default None = sequential)
    metadata={"model": "gpt-4o-mini", "prompt_version": "v3"},
)
```

### 4.7 Targeting Specific Dataset Subsets

```python
# Run on a specific tagged version of the dataset
evaluate(
    target_function,
    data=client.list_examples(dataset_name=dataset_name, as_of="initial dataset"),
    evaluators=[is_concise_enough],
    experiment_prefix="initial-dataset-version"
)

# Run on a named split
evaluate(
    target_function,
    data=client.list_examples(dataset_name=dataset_name, splits=["Crucial Examples"]),
    evaluators=[is_concise_enough],
    experiment_prefix="crucial-examples-split"
)

# Run on specific example IDs
evaluate(
    target_function,
    data=client.list_examples(
        dataset_name=dataset_name,
        example_ids=["eb646d02-89ba-4517-94b4-6154c885e716"]
    ),
    evaluators=[is_concise_enough],
    experiment_prefix="single-example"
)
```

### 4.8 Pairwise Experiments (Head-to-Head Comparison)

Use `evaluate()` with a **tuple of experiment names** and a pairwise evaluator:

```python
from pydantic import BaseModel, Field
from langsmith import evaluate

class Preference(BaseModel):
    preference: int = Field(
        description="1 = Assistant A is better. 2 = Assistant B is better. 0 = Tie."
    )

JUDGE_SYSTEM = """As an impartial judge, evaluate which summarization better captures
the key points of the meeting transcript. Consider helpfulness, accuracy, and depth."""

JUDGE_HUMAN = """
[Transcript] {transcript}
[Assistant A] {answer_a}
[Assistant B] {answer_b}
"""

def ranked_preference(inputs: dict, outputs: list[dict]) -> list:
    """
    inputs: single example inputs
    outputs: list of 2 dicts — one per experiment being compared
    Returns: list of 2 scores (one per experiment)
    """
    structured_llm = openai_client.with_structured_output(Preference)
    response = structured_llm.invoke([
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": JUDGE_HUMAN.format(
            transcript=inputs["transcript"],
            answer_a=outputs[0].get("output", "N/A"),
            answer_b=outputs[1].get("output", "N/A"),
        )}
    ])
    preference = response.preference
    if preference == 1:   return [1, 0]
    elif preference == 2: return [0, 1]
    else:                 return [0, 0]

# Pass a TUPLE of experiment IDs/names — NOT a list
evaluate(
    ("Good-Summarizer-abc123", "Bad-Summarizer-def456"),
    evaluators=[ranked_preference]
)
```

> **When to use pairwise**: When you have no ground truth reference but want to compare two system versions head-to-head.

---

## 5. Module 3 — Prompt Engineering Lifecycle

### 5.1 Prompt Hub Concepts

| Concept | Description |
|---------|-------------|
| **Prompt Hub** | Centralized repository for named, versioned prompts |
| **Commit** | An immutable snapshot of a prompt (hash-based) |
| **Pull** | Download the latest (or specific) commit |
| **Push** | Upload/update a prompt in the hub |
| **Playground** | Interactive UI for testing prompts against datasets |

### 5.2 Pulling Prompts

```python
from langsmith import Client
from langsmith.client import convert_prompt_to_openai_format

client = Client()

# Pull latest version
prompt = client.pull_prompt("username/my-rag-prompt")

# Pull specific commit
prompt_pinned = client.pull_prompt("username/my-rag-prompt:abc1234def5678")

# Pull with model config (LangChain only — returns RunnableBinding)
prompt_with_model = client.pull_prompt(
    "username/my-rag-prompt",
    include_model=True,
    secrets={"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")}
)
```

### 5.3 Hydrating and Using Prompts

```python
# Hydrate with variables
hydrated = prompt.invoke({"question": "What is LangGraph?", "context": "..."})

# Convert to OpenAI messages format
messages = convert_prompt_to_openai_format(hydrated)["messages"]

# Call OpenAI with the converted messages
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
)
```

### 5.4 Using Prompt Hub in Your Application

```python
from langsmith import Client, traceable
from langsmith.client import convert_prompt_to_openai_format
from openai import OpenAI

client       = Client()
openai_client = OpenAI()

# Pull once at startup (or refresh periodically)
prompt = client.pull_prompt("username/my-rag-prompt")

@traceable(run_type="chain")
def generate_response(question: str, documents):
    formatted_docs = "\n\n".join(doc.page_content for doc in documents)

    # Hydrate the hub prompt — replaces hard-coded RAG_SYSTEM_PROMPT
    formatted_prompt = prompt.invoke({"context": formatted_docs, "question": question})
    messages = convert_prompt_to_openai_format(formatted_prompt)["messages"]

    return call_openai(messages)
```

### 5.5 Pushing Prompts to Hub

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import Client

client = Client()

# Push as prompt template only
template = ChatPromptTemplate.from_template(
    """You are a RAG assistant. Answer in French.

    Context: {context}
    Conversation: {conversation}
    Question: {question}
    Answer:"""
)
client.push_prompt("french-rag-prompt", object=template)

# Push as prompt + model (stores model config alongside prompt)
model = ChatOpenAI(model="gpt-4o-mini")
chain = template | model
client.push_prompt("french-rag-with-model", object=chain)
```

### 5.6 Playground Experiments Dataset

```python
from langsmith import Client

# Create a dataset to test in the Playground UI
client = Client()
dataset = client.create_dataset(
    dataset_name="Sample Questions",
    description="Sample questions for playground testing"
)

examples = [
    ("What color is the sky?",  "The sky is blue"),
    ("What color is grass?",    "Grass is green"),
    ("What color is dirt?",     "Dirt is brown"),
]
client.create_examples(
    inputs=[{"question": q} for q, _ in examples],
    outputs=[{"output": a} for _, a in examples],
    dataset_id=dataset.id,
)
# Then open the dataset in LangSmith UI → Open in Playground
```

---

## 6. Module 4 — Feedback & Production Monitoring

### 6.1 Feedback Types

| Type | Parameter | Value Example | Use Case |
|------|-----------|---------------|----------|
| Continuous | `score` | `7.5`, `0.92` | Quality ratings, confidence scores |
| Categorical | `value` | `"yes"`, `"no"`, `"toxic"` | Thumbs up/down, pass/fail |
| With comment | `comment` | `"Response was too vague"` | Human annotations |

### 6.2 Adding Feedback to an Existing Run

```python
from langsmith import Client

client = Client()

# From run_id copied from LangSmith UI
run_id = "019c8be2-6180-7522-9f75-d90b9bff3ff4"

# Continuous feedback
client.create_feedback(
    run_id,
    key="helpfulness",
    score=7.0,
    comment="Response was helpful but missing code examples"
)

# Categorical feedback
client.create_feedback(
    run_id,
    key="thumbs",
    value="yes",
    comment="Correct and concise"
)
```

### 6.3 Pre-Generated Run IDs (Best for Production)

Pre-generate the run ID before calling your application so you can attach feedback immediately after:

```python
import uuid
from langsmith import traceable, Client

client = Client()

# 1. Generate ID before execution
pre_defined_run_id = uuid.uuid4()

@traceable
def my_application(input_data: str) -> str:
    return process(input_data)

# 2. Execute with the pre-defined ID
result = my_application(
    "What is LangSmith?",
    langsmith_extra={"run_id": pre_defined_run_id}
)

# 3. Create feedback immediately (or later in the same request lifecycle)
client.create_feedback(
    run_id=pre_defined_run_id,
    key="user_rating",
    score=9.0,
    comment="User clicked thumbs up"
)
```

### 6.4 Pre-Signed Feedback URLs (Frontend Use)

Use when you **cannot expose API keys** to the browser/client:

```python
import uuid, requests
from langsmith import Client

client = Client()

# 1. Generate run ID and pre-sign feedback URL (server-side)
run_id = uuid.uuid4()
presigned = client.create_presigned_feedback_token(
    run_id, "user_presigned_feedback"
)
print(presigned.url)  # URL to send to the browser (expires after some time)

# 2. Execute run with pre-defined ID (server-side)
my_application("User question", langsmith_extra={"run_id": run_id})

# 3. Client-side: POST to the pre-signed URL with score
# No API key required
url_with_score = f"{presigned.url}?score=1"
response = requests.get(url_with_score)
print("Feedback submitted!" if response.ok else "Failed")
```

### 6.5 Full Feedback Lifecycle in a Web App

```python
import uuid
from fastapi import FastAPI
from langsmith import traceable, Client
from pydantic import BaseModel

app    = FastAPI()
client = Client()

class QueryRequest(BaseModel):
    question: str

class FeedbackRequest(BaseModel):
    run_id: str
    score: float
    comment: str = ""

@traceable(run_type="chain")
def _run_rag(question: str) -> str:
    return langsmith_rag(question)

@app.post("/query")
async def query(req: QueryRequest):
    run_id   = uuid.uuid4()
    response = _run_rag(req.question, langsmith_extra={"run_id": run_id})
    return {"answer": response, "run_id": str(run_id)}  # send run_id to UI

@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    client.create_feedback(
        run_id=req.run_id,
        key="user_rating",
        score=req.score,
        comment=req.comment
    )
    return {"status": "ok"}
```

---

## 7. Module 5 — Online Evaluation & Run Filtering

### 7.1 Online Evaluation Overview

Online evaluators run **automatically** on a sampled subset of production traffic, without requiring a separate dataset or manual triggering.

Configuration (done in LangSmith UI or via automation rules):
1. Select a project.
2. Define filter rules for which runs to evaluate.
3. Choose a sampling rate (e.g., 10% of runs).
4. Attach evaluator code (LLM-as-Judge or custom).

### 7.2 Triggering Online Evaluation via Code

```python
from app import langsmith_rag

# Simply run the application — if online evaluators are configured, they fire
# automatically on the resulting run
question = "What are the existing MultiAgent architectures for a Travel Agent?"
langsmith_rag(question)
```

### 7.3 Querying and Filtering Runs with the SDK

```python
from langsmith import Client
from datetime import datetime, timedelta

client = Client()

# ── Basic filter ──────────────────────────────────────────────────────────────
runs = client.list_runs(
    project_name="langsmith-academy",
    filter='and(eq(status, "success"), gt(latency, 2))',  # filter DSL
    start_time=datetime.now() - timedelta(days=7),
)

# ── Only root runs (top-level traces) ────────────────────────────────────────
root_runs = client.list_runs(
    project_name="langsmith-academy",
    filter="eq(is_root, true)",
)

# ── Trace-level filter (runs where ANY run in the trace matches) ──────────────
runs_with_trace_filter = client.list_runs(
    project_name="langsmith-academy",
    trace_filter='has(metadata, "user_id", "usr_123")',
)

# ── Tree filter (filter to sub-trees matching condition) ─────────────────────
runs_with_tree_filter = client.list_runs(
    project_name="langsmith-academy",
    tree_filter='eq(name, "Retrieve Documents")',
)

for run in root_runs:
    print(run.id, run.name, run.status, run.total_tokens)
```

### 7.4 Filter DSL Reference

| Operator | Example | Meaning |
|----------|---------|---------|
| `eq`      | `eq(status, "success")` | Equals |
| `neq`     | `neq(status, "error")` | Not equals |
| `gt`      | `gt(latency, 2)` | Greater than |
| `gte`     | `gte(total_cost, 0.01)` | Greater than or equal |
| `lt`      | `lt(total_tokens, 500)` | Less than |
| `and`     | `and(eq(is_root, true), gt(latency, 1))` | Logical AND |
| `or`      | `or(eq(status, "error"), eq(status, "timeout"))` | Logical OR |
| `has`     | `has(metadata, "user_id", "abc")` | Metadata key/value |

Filters can be copied directly from the LangSmith UI's filter panel.

---

## 8. Multi-Agent System Architecture

This section goes beyond the course content to show you how to apply every LangSmith concept to a real multi-agent system.

### 8.1 Multi-Agent Topology Patterns

**Pattern A — Supervisor Agent**
```
User Input → Supervisor Agent
                ├── Research Agent (RAG + tools)
                ├── Code Agent    (code generation + execution)
                └── QA Agent      (fact-checking)
             Supervisor aggregates → Final Response
```

**Pattern B — Sequential Specialist Chain**
```
User Input → Planner Agent → Research Agent → Writer Agent → Reviewer Agent → Output
```

**Pattern C — Hierarchical (used in complex workflows)**
```
Orchestrator
  ├── Sub-Orchestrator A
  │     ├── Worker 1
  │     └── Worker 2
  └── Sub-Orchestrator B
        ├── Worker 3
        └── Worker 4
```

### 8.2 Shared State Design with TypedDict

```python
import operator
from typing import List, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, AnyMessage

class MultiAgentState(TypedDict):
    # User question
    question: str

    # Conversation history — Annotated with operator.add for automatic appending
    messages: Annotated[List[AnyMessage], operator.add]

    # Retrieved documents
    documents: List[dict]

    # Agent reasoning steps / scratchpad
    agent_scratchpad: str

    # Which agent should act next
    next_agent: str

    # Final aggregated answer
    final_answer: str

    # Metadata for tracing
    session_id: str
    user_id: str
```

### 8.3 LangGraph State Graph for Multi-Agents

```python
import operator
from typing import List, Annotated, Literal
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

llm = ChatOpenAI(model="gpt-4o-mini")

class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    next: str

# ── Agent nodes ───────────────────────────────────────────────────────────────

def research_agent(state: AgentState) -> AgentState:
    """Retrieves relevant documents."""
    last_message = state["messages"][-1].content
    docs = retriever.invoke(last_message)
    doc_text = "\n\n".join(d.page_content for d in docs)
    return {"messages": [HumanMessage(content=f"Research: {doc_text}")]}

def writer_agent(state: AgentState) -> AgentState:
    """Generates a well-structured answer."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def reviewer_agent(state: AgentState) -> AgentState:
    """Reviews and refines the answer for quality."""
    review_prompt = f"Review this answer for accuracy and completeness: {state['messages'][-1].content}"
    response = llm.invoke([HumanMessage(content=review_prompt)])
    return {"messages": [response]}

def router(state: AgentState) -> Literal["writer", "end"]:
    """Decide whether to continue or stop."""
    last = state["messages"][-1].content.lower()
    if "insufficient" in last or "needs more" in last:
        return "writer"    # Loop back
    return "end"

# ── Build graph ───────────────────────────────────────────────────────────────

graph = StateGraph(AgentState)
graph.add_node("research",  research_agent)
graph.add_node("writer",    writer_agent)
graph.add_node("reviewer",  reviewer_agent)

graph.add_edge(START,       "research")
graph.add_edge("research",  "writer")
graph.add_edge("writer",    "reviewer")
graph.add_conditional_edges("reviewer", router, {"writer": "writer", "end": END})

agent_graph = graph.compile()
```

### 8.4 Supervisor Pattern with LangGraph

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from typing import Literal

AGENTS = ["researcher", "coder", "reviewer"]

class RouteDecision(BaseModel):
    next: Literal["researcher", "coder", "reviewer", "FINISH"]

supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a supervisor managing a team of agents: {agents}.
     Given the conversation, decide which agent should act next.
     Reply FINISH when the task is complete."""),
    ("human", "{messages}"),
])

def make_supervisor(llm):
    chain = supervisor_prompt | llm.with_structured_output(RouteDecision)
    def supervisor_node(state):
        result = chain.invoke({"agents": AGENTS, "messages": state["messages"]})
        return {"next": result.next}
    return supervisor_node
```

---

## 9. LangGraph Integration with LangSmith

### 9.1 Automatic Tracing — Zero Config

LangGraph traces everything automatically when `LANGSMITH_TRACING=true` is set:

```python
import os
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = "ls__..."
os.environ["LANGSMITH_PROJECT"] = "my-multi-agent-project"

# All graph.invoke() / graph.stream() calls are auto-traced
result = agent_graph.invoke(
    {"messages": [HumanMessage(content="What is LangSmith?")]}
)
```

### 9.2 Passing Config / Metadata into a Graph

```python
from langchain_core.runnables import RunnableConfig

config: RunnableConfig = {
    "tags":     ["production", "v2"],
    "metadata": {
        "user_id":    "usr_123",
        "session_id": str(uuid.uuid4()),
        "app_version": "2.0"
    },
    "run_name": "Multi-Agent Question Answering"
}

result = agent_graph.invoke(
    {"question": "Explain retrieval-augmented generation"},
    config=config
)
```

### 9.3 Complete LangGraph RAG Multi-Agent (Auto-Traced)

```python
import operator
import nest_asyncio
from typing import List
from typing_extensions import TypedDict, Annotated
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AnyMessage, get_buffer_string
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate

nest_asyncio.apply()

RAG_PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
    """You are a helpful assistant.
    Prior conversation: {conversation}
    Context: {context}
    Question: {question}
    Answer:"""
)

llm       = ChatOpenAI(model="gpt-4o-mini", temperature=0)
retriever = get_vector_db_retriever()

class GraphState(TypedDict):
    question:  str
    messages:  Annotated[List[AnyMessage], operator.add]
    documents: List[Document]

# ── Node: retrieve ────────────────────────────────────────────────────────────
def retrieve_documents(state: GraphState) -> dict:
    messages = state.get("messages", [])
    question = state["question"]
    # Include conversation history for contextual retrieval
    docs = retriever.invoke(f"{get_buffer_string(messages)} {question}")
    return {"documents": docs}

# ── Node: generate ────────────────────────────────────────────────────────────
def generate_response(state: GraphState) -> dict:
    question  = state["question"]
    messages  = state["messages"]
    documents = state["documents"]
    context   = "\n\n".join(doc.page_content for doc in documents)

    rag_prompt = RAG_PROMPT_TEMPLATE.format(
        context=context,
        conversation=messages,
        question=question
    )
    generation = llm.invoke([HumanMessage(content=rag_prompt)])
    return {
        "documents": documents,
        "messages":  [HumanMessage(question), generation]
    }

# ── Build & compile ───────────────────────────────────────────────────────────
builder = StateGraph(GraphState)
builder.add_node("retrieve_documents", retrieve_documents)
builder.add_node("generate_response",  generate_response)
builder.add_edge(START,                "retrieve_documents")
builder.add_edge("retrieve_documents", "generate_response")
builder.add_edge("generate_response",  END)

rag_graph = builder.compile()

# ── Invocation ────────────────────────────────────────────────────────────────
result = rag_graph.invoke(
    {"question": "How do I set up tracing?"},
    config={"metadata": {"user_id": "test_user"}}
)
print(result["messages"][-1].content)
```

### 9.4 Mixing `@traceable` with LangGraph

Custom Python functions inside graph nodes are NOT automatically traced — you must annotate them:

```python
from langsmith import traceable

# This custom function inside a node will be traced
@traceable(run_type="tool")
def search_web(query: str) -> str:
    # Custom tool — not a LangChain runnable
    return web_search_api(query)

# The node itself is traced by LangGraph
def tool_node(state: AgentState) -> dict:
    result = search_web(state["messages"][-1].content)    # @traceable kicks in here
    return {"messages": [HumanMessage(content=result)]}
```

### 9.5 Thread Management in Multi-Turn Agents

```python
import uuid

def create_session() -> str:
    return str(uuid.uuid4())

session_id = create_session()

# Turn 1
rag_graph.invoke(
    {"question": "What is RAG?"},
    config={"metadata": {"thread_id": session_id}}
)

# Turn 2 — linked to the same thread in LangSmith
rag_graph.invoke(
    {"question": "Can you give a code example?"},
    config={"metadata": {"thread_id": session_id}}
)
```

---

## 10. Production Patterns & Best Practices

### 10.1 The LangSmith Development Lifecycle

```
┌────────────────────────────────────────────────────────────────────────┐
│  DEVELOP                                                               │
│  • Module 0: Build RAG/agent application                               │
│  • Module 1: Add @traceable to all functions                           │
│  • Module 3: Store prompts in Prompt Hub                               │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────┐
│  EVALUATE                                                              │
│  • Module 2: Create golden datasets                                    │
│  • Module 2: Run experiments with evaluators                           │
│  • Module 2: Pairwise comparison before promoting                      │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────┐
│  DEPLOY                                                                │
│  • Module 5: Configure online evaluators                               │
│  • Module 4: Collect user feedback (run IDs + pre-signed URLs)         │
│  • Module 5: Filter & analyze production runs                          │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────┐
│  IMPROVE                                                               │
│  • Module 3: Iterate on prompts in Prompt Hub Playground               │
│  • Module 2: Re-run experiments on updated prompts                     │
│  • Module 4: Add poor-performing runs to evaluation dataset            │
└────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Trace Annotation Checklist

| Element | Required | Code Pattern |
|---------|----------|--------------|
| `run_type` on every `@traceable` | Yes | `@traceable(run_type="chain")` |
| LLM cost metadata | Recommended | `metadata={"ls_provider": "openai", "ls_model_name": "gpt-4o-mini"}` |
| App version metadata | Recommended | `metadata={"app_version": "1.2"}` |
| Session/thread IDs | For chatbots | `langsmith_extra={"metadata": {"thread_id": tid}}` |
| Run IDs for feedback | For production | `langsmith_extra={"run_id": uuid4()}` |
| Project name | Yes | `LANGSMITH_PROJECT=my-project` |

### 10.3 Context Propagation Gotchas

```python
# ❌ WRONG — spawning vanilla threads breaks trace hierarchy in Python < 3.11
import threading
@traceable
def outer():
    t = threading.Thread(target=inner)  # inner() trace will NOT nest under outer
    t.start()

# ✅ CORRECT — use ContextThreadPoolExecutor
from langsmith.utils import ContextThreadPoolExecutor
@traceable
def outer():
    with ContextThreadPoolExecutor() as executor:
        executor.map(inner, items)  # inner() traces nest correctly

# ✅ CORRECT — pass parent run tree manually
from langsmith import get_current_run_tree
@traceable
def outer():
    rt = get_current_run_tree()
    with ThreadPoolExecutor() as executor:
        executor.map(
            lambda x: inner(x, langsmith_extra={"parent": rt}),
            items
        )
```

### 10.4 Cost Optimization Strategies

```python
# 1. Sampling — only evaluate some production runs
import random

def sampled_online_evaluator(root_run, example=None, sample_rate=0.1):
    if random.random() > sample_rate:
        return None    # Skip this run
    score = expensive_llm_judge(root_run)
    return {"key": "sampled_quality", "score": score}

# 2. Cheap heuristics first, expensive LLM judge only on failures
def tiered_evaluator(root_run, example=None):
    output = root_run.outputs.get("output", "")

    # Tier 1: Fast heuristic check (free)
    if len(output) < 10 or output.strip() == "":
        return {"key": "quality", "score": 0, "comment": "Empty/very short"}

    # Tier 2: Pattern check (free)
    if "i don't know" in output.lower() and len(output) < 50:
        return {"key": "quality", "score": 0.3, "comment": "Low confidence answer"}

    # Tier 3: LLM judge (costs money) — only if heuristics pass
    return llm_quality_judge(root_run)

# 3. Run experiments with max_concurrency to save wall-clock time
evaluate(
    target_function,
    data=dataset_name,
    evaluators=[my_evaluator],
    max_concurrency=5     # Parallelize across examples
)
```

### 10.5 Dataset Versioning Strategy

```python
# Tag dataset snapshots at key milestones
from langsmith import Client

client = Client()

# List examples at a specific tag
examples = client.list_examples(
    dataset_name="RAG Golden Dataset",
    as_of="pre-gpt-4o-upgrade"    # Your tag string
)

# You tag dataset versions from the LangSmith UI (Dataset → Settings → Create Version)
# Then reference via as_of= in evaluate() calls for reproducible benchmarks
```

### 10.6 Error Handling and Resilience

```python
from langsmith import traceable

@traceable(run_type="chain")
def resilient_rag(question: str) -> dict:
    try:
        documents = retrieve_documents(question)
        response  = generate_response(question, documents)
        return {"output": response, "status": "success"}
    except Exception as e:
        # LangSmith captures the error automatically in the trace
        # but you can also add metadata
        return {
            "output": "I encountered an error. Please try again.",
            "status": "error",
            "error_type": type(e).__name__
        }
```

---

## 11. Complete End-to-End Code Reference

This section provides a consolidated, production-ready implementation that stitches together **all modules** into a single project.

### 11.1 Project Structure

```
my_multi_agent_project/
├── .env
├── requirements.txt
├── config.py               # Environment config
├── vectorstore.py          # Vector DB (Module 0)
├── rag_chain.py            # Core RAG chain with tracing (Module 0 + 1)
├── agents/
│   ├── __init__.py
│   ├── researcher.py       # Research agent node
│   ├── writer.py           # Writer agent node
│   └── supervisor.py       # Routing supervisor
├── graph.py                # LangGraph multi-agent graph (Module 9)
├── evaluators.py           # All evaluators (Module 2)
├── experiments.py          # Experiment runner (Module 2)
├── feedback.py             # Feedback utilities (Module 4)
└── main.py                 # Entry point
```

### 11.2 `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv(override=True)

OPENAI_API_KEY    = os.environ["OPENAI_API_KEY"]
LANGSMITH_API_KEY = os.environ["LANGSMITH_API_KEY"]
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "my-multi-agent-project")
MODEL_NAME        = os.getenv("MODEL_NAME", "gpt-4o-mini")
MODEL_PROVIDER    = "openai"

# Ensure tracing is enabled
os.environ.setdefault("LANGSMITH_TRACING", "true")
```

### 11.3 `rag_chain.py`

```python
from typing import List
from langsmith import traceable
from openai import OpenAI
from config import MODEL_NAME, MODEL_PROVIDER
from vectorstore import get_vector_db_retriever

RAG_SYSTEM_PROMPT = """You are an assistant for question-answering tasks.
Use the retrieved context to answer the question concisely (max 3 sentences).
If you don't know, say so.
"""

openai_client = OpenAI()
retriever     = get_vector_db_retriever()

@traceable(run_type="retriever")
def retrieve_documents(question: str) -> list:
    raw = retriever.invoke(question)
    return [
        {"page_content": d.page_content, "type": "Document", "metadata": d.metadata}
        for d in raw
    ]

@traceable(run_type="chain")
def generate_response(question: str, documents: list) -> str:
    context  = "\n\n".join(d["page_content"] for d in documents)
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Context: {context}\n\nQuestion: {question}"},
    ]
    return _call_llm(messages)

@traceable(
    run_type="llm",
    metadata={"ls_provider": MODEL_PROVIDER, "ls_model_name": MODEL_NAME}
)
def _call_llm(messages: List[dict]) -> str:
    response = openai_client.chat.completions.create(
        model=MODEL_NAME, messages=messages
    )
    return response.choices[0].message.content

@traceable(run_type="chain", metadata={"app_version": "1.0"})
def langsmith_rag(question: str) -> str:
    docs     = retrieve_documents(question)
    response = generate_response(question, docs)
    return response
```

### 11.4 `evaluators.py`

```python
from openai import OpenAI
from pydantic import BaseModel, Field
from langsmith.schemas import Run, Example

client = OpenAI()

# ── Heuristic evaluators ──────────────────────────────────────────────────────

def is_concise(reference_outputs: dict, outputs: dict) -> dict:
    score = int(len(outputs["output"]) < 1.5 * len(reference_outputs["output"]))
    return {"key": "is_concise", "score": score}

def not_empty(outputs: dict) -> dict:
    score = int(bool(outputs.get("output", "").strip()))
    return {"key": "not_empty", "score": score}

# ── LLM-as-Judge evaluators ───────────────────────────────────────────────────

class SemanticScore(BaseModel):
    score: int = Field(description="Semantic similarity 1–10")

def semantic_similarity(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Score semantic similarity 1–10."},
            {"role": "user", "content": (
                f"Question: {inputs['question']}\n"
                f"Reference: {reference_outputs['output']}\n"
                f"Candidate: {outputs['output']}"
            )},
        ],
        response_format=SemanticScore,
    )
    return {
        "score": completion.choices[0].message.parsed.score,
        "key": "semantic_similarity"
    }

# ── Summary evaluators ────────────────────────────────────────────────────────

def f1_score(outputs: list[dict], reference_outputs: list[dict]) -> dict:
    tp = fp = fn = 0
    for pred, ref in zip(outputs, reference_outputs):
        p, r = pred.get("class"), ref.get("class")
        if p == "Toxic" and r == "Toxic":        tp += 1
        elif p == "Toxic" and r == "Not toxic":  fp += 1
        elif p == "Not toxic" and r == "Toxic":  fn += 1
    if tp == 0:
        return {"key": "f1", "score": 0.0}
    prec   = tp / (tp + fp)
    recall = tp / (tp + fn)
    return {"key": "f1", "score": 2 * prec * recall / (prec + recall)}
```

### 11.5 `experiments.py`

```python
from langsmith import evaluate, Client
from rag_chain import langsmith_rag
from evaluators import is_concise, semantic_similarity

client      = Client()
DATASET_NAME = "RAG Application Golden Dataset"

def run_experiment(experiment_prefix: str, model_override: str = None):
    """Run a full evaluation experiment and return results."""

    def target(inputs: dict) -> dict:
        # Optionally override the model for this experiment
        return {"output": langsmith_rag(inputs["question"])}

    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[is_concise, semantic_similarity],
        experiment_prefix=experiment_prefix,
        max_concurrency=3,
        metadata={"model": model_override or "gpt-4o-mini"}
    )
    return results

if __name__ == "__main__":
    run_experiment("baseline-gpt-4o-mini")
```

### 11.6 `feedback.py`

```python
import uuid
from typing import Optional
from langsmith import Client

client = Client()

def generate_run_context() -> dict:
    """Generate a run ID and optional pre-signed URL for feedback."""
    run_id = uuid.uuid4()
    presigned = client.create_presigned_feedback_token(run_id, "user_feedback")
    return {
        "run_id": run_id,
        "feedback_url": presigned.url,
    }

def add_feedback(
    run_id: str,
    score: float,
    key: str = "user_rating",
    comment: str = ""
) -> None:
    client.create_feedback(
        run_id=run_id,
        key=key,
        score=score,
        comment=comment
    )

def add_categorical_feedback(
    run_id: str,
    value: str,
    key: str = "thumbs",
    comment: str = ""
) -> None:
    client.create_feedback(
        run_id=run_id,
        key=key,
        value=value,
        comment=comment
    )
```

### 11.7 `graph.py` — Multi-Agent Graph

```python
import operator
import uuid
import nest_asyncio
from typing import List, Annotated, Literal
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, AnyMessage, get_buffer_string
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from vectorstore import get_vector_db_retriever
from langsmith import traceable

nest_asyncio.apply()

llm       = ChatOpenAI(model="gpt-4o-mini", temperature=0)
retriever = get_vector_db_retriever()

class MultiAgentState(TypedDict):
    question:     str
    messages:     Annotated[List[AnyMessage], operator.add]
    documents:    List[Document]
    session_id:   str
    final_answer: str

# ── Agent nodes ───────────────────────────────────────────────────────────────

def research_node(state: MultiAgentState) -> dict:
    """Retrieve relevant documents for the question."""
    question = state["question"]
    history  = get_buffer_string(state.get("messages", []))
    docs     = retriever.invoke(f"{history} {question}")
    return {"documents": docs}

def generate_node(state: MultiAgentState) -> dict:
    """Generate an answer using retrieved docs."""
    question = state["question"]
    messages = state.get("messages", [])
    context  = "\n\n".join(d.page_content for d in state["documents"])
    prompt   = (
        f"Conversation history:\n{get_buffer_string(messages)}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {
        "messages":     [HumanMessage(content=question), response],
        "final_answer": response.content,
    }

def review_node(state: MultiAgentState) -> dict:
    """Optional quality review pass."""
    last_answer = state["final_answer"]
    review_prompt = (
        f"Review this answer for accuracy and helpfulness. "
        f"If it's already good, just return it. If it needs improvement, fix it.\n\n"
        f"Answer: {last_answer}"
    )
    improved = llm.invoke([HumanMessage(content=review_prompt)])
    return {
        "messages":     [improved],
        "final_answer": improved.content,
    }

# ── Graph assembly ────────────────────────────────────────────────────────────

builder = StateGraph(MultiAgentState)
builder.add_node("research",  research_node)
builder.add_node("generate",  generate_node)
builder.add_node("review",    review_node)

builder.add_edge(START,      "research")
builder.add_edge("research", "generate")
builder.add_edge("generate", "review")
builder.add_edge("review",   END)

multi_agent_graph = builder.compile()

# ── Invocation helper ─────────────────────────────────────────────────────────

def ask(question: str, user_id: str = "anon", session_id: str = None) -> str:
    """Invoke the multi-agent graph with full tracing metadata."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    result = multi_agent_graph.invoke(
        {"question": question, "session_id": session_id, "messages": []},
        config={
            "metadata": {
                "user_id":    user_id,
                "thread_id":  session_id,   # Links turns into a conversation thread
                "app_version": "1.0"
            }
        }
    )
    return result["final_answer"]
```

### 11.8 `main.py`

```python
import uuid
from graph import ask
from feedback import generate_run_context, add_feedback
from langsmith import traceable, Client
from rag_chain import langsmith_rag

@traceable(run_type="chain", metadata={"entry_point": "main"})
def run_with_feedback(question: str, user_id: str = "anon") -> dict:
    """Run the multi-agent graph and wire up feedback collection."""
    ctx    = generate_run_context()        # Pre-generate run ID
    answer = ask(
        question,
        user_id    = user_id,
        session_id = str(ctx["run_id"]),
    )
    return {
        "answer":       answer,
        "run_id":       str(ctx["run_id"]),
        "feedback_url": ctx["feedback_url"],   # Send this to the UI
    }

if __name__ == "__main__":
    # Simple test
    result = run_with_feedback(
        "What multi-agent architectures should I consider for a travel agent system?",
        user_id="test_user"
    )
    print(f"Answer:       {result['answer']}")
    print(f"Run ID:       {result['run_id']}")
    print(f"Feedback URL: {result['feedback_url']}")

    # Simulate user feedback
    add_feedback(result["run_id"], score=8.5, comment="Very helpful overview!")
```

---

## Quick Reference Card

### Environment Variables

```bash
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=ls__...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=my-project
# Optional
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

### Tracing Decorators

```python
@traceable                                           # Default chain
@traceable(run_type="llm")                           # LLM call
@traceable(run_type="retriever")                     # Document retrieval
@traceable(run_type="tool")                          # Tool/function call
@traceable(run_type="llm", metadata={               # With cost tracking
    "ls_provider": "openai", "ls_model_name": "gpt-4o-mini"})
```

### Runtime Extras

```python
my_fn(input, langsmith_extra={
    "metadata":  {"user_id": "...", "version": "1.0"},
    "tags":      ["production"],
    "run_id":    uuid.uuid4(),
    "thread_id": session_uuid,
})
```

### Evaluator Return Format

```python
{"score": 0.85, "key": "my_metric"}             # Numeric
{"value": "pass", "key": "my_check"}             # Categorical
{"score": 1, "key": "ok", "comment": "Correct"} # With comment
```

### `evaluate()` Signature

```python
evaluate(
    target_fn,              # (inputs: dict) -> dict
    data=dataset_name,      # str | list[Example] | iterator
    evaluators=[...],       # Per-example evaluators
    summary_evaluators=[...],  # Dataset-level evaluators
    experiment_prefix="v1",
    max_concurrency=4,
    num_repetitions=1,
    metadata={"model": "gpt-4o-mini"}
)
```

### Feedback

```python
client.create_feedback(run_id, key="rating",   score=8.5)
client.create_feedback(run_id, key="thumbs",   value="yes")
client.create_presigned_feedback_token(run_id, key="user_fb")
```

### Run Filtering

```python
client.list_runs(
    project_name="...",
    filter='and(eq(is_root, true), gt(latency, 2))',
    start_time=datetime.now() - timedelta(days=7)
)
```

---

*Generated from the complete `intro-to-langsmith` course: Modules 0–5, all notebooks, utility files, and app.py implementations. Designed as a reference guide for building multi-agent systems with LangChain, LangGraph, and LangSmith.*
