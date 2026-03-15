# Building Reliable Agents — Key Concepts

## Overview

This project (LangChain Academy's **Building Reliable Agents** course) demonstrates how to build, observe, evaluate, and iteratively improve an AI agent — a customer support assistant named **Emma** for OfficeFlow Supply Co. It covers the full lifecycle: from a basic prototype to a production-grade agent with comprehensive evaluation guardrails.

---

## 1. Iterative Agent Development (v0 → v5)

The core of the project is an **incremental improvement loop** where each agent version adds a single capability, validated by evaluation before moving on.

| Version | What Changed | Why |
|---------|-------------|-----|
| **v0** | Baseline agent with tools (DB query + KB search) | Starting point — no tracing, no guardrails |
| **v1** | Added LangSmith tracing (`@traceable`) | Observability — every LLM call and tool invocation is captured |
| **v2** | Enhanced tool instructions (schema discovery via `PRAGMA table_info` before SQL queries) | Prevents blind column guessing; agent inspects DB schema first |
| **v3** | Added stock quantity confidentiality policy | Agent must never reveal exact stock numbers — only qualitative levels ("in stock", "low stock", "out of stock") |
| **v4** | Added RAG with no-chunking strategy + knowledge base search | Accurate retrieval of company policies via semantic search on pre-embedded documents |
| **v5** | Conciseness improvements + embedding cache staleness detection | Shorter responses; regenerates embeddings only when source docs change |

**Key principle:** Never change multiple things at once. Each version isolates one improvement, making it possible to attribute evaluation results to specific changes.

---

## 2. Observability — Tracing with LangSmith

Traditional debugging (print statements, breakpoints) fails for AI agents because:

- LLM calls are non-deterministic
- Tool invocations and multi-step reasoning create complex execution paths
- Failures may be subtle (wrong tone, policy violations) rather than crashes

**LangSmith tracing** captures the full execution tree — every LLM call, tool invocation, and intermediate decision — enabling developers to:

- Replay and inspect agent behavior step by step
- Spot failure patterns across many interactions
- Compare behavior across agent versions

---

## 3. Evaluation Framework (Progressive Rigor)

Evaluation is layered, progressing from fast deterministic checks to expensive LLM-based judgment:

### Layer 1: Code-Based Evaluators (Deterministic)

These work like unit tests — fast, cheap, binary pass/fail:

| Evaluator | What It Checks |
|-----------|---------------|
| **schema_before_query** | Agent runs `PRAGMA table_info` before any data query |
| **no_quantity_leak** | Output doesn't contain exact stock numbers (policy compliance) |
| **correct_tool_routing** | Product questions → `query_database`; Policy questions → `search_knowledge_base` |
| **valid_email_references** | Agent doesn't hallucinate email addresses |

### Layer 2: LLM-as-Judge

An LLM evaluates subjective quality on a 0–3 scale:

| Score | Meaning |
|-------|---------|
| 0 | Fail — factually wrong or policy violation |
| 1 | Poor — partially correct but missing key information |
| 2 | Good — correct and helpful |
| 3 | Excellent — correct, helpful, and concise |

Judges correctness, policy compliance, and helpfulness simultaneously.

### Layer 3: Pairwise Evaluation

Compares two agent versions (e.g., v4 vs. v5) side by side. An LLM decides which response is better along a specific dimension (e.g., conciseness) while retaining essential information.

### Layer 4: Human Alignment (Calibration)

Compares LLM judge scores against human reviews to validate the evaluator itself:

- **Exact match %** — how often judge and human agree perfectly
- **Within-1 %** — how often they're within 1 point
- **Mean Absolute Error (MAE)** — average score difference
- **Cohen's κ** — agreement beyond chance
- **Disagreement report** — identifies where the judge over/under-scores

---

## 4. Core Architecture

### Tools

The agent has two primary tools:

1. **`query_database()`** — Executes SQL against an inventory SQLite database (products, stock, pricing)
2. **`search_knowledge_base()`** — Semantic search over company policy documents using cosine similarity on pre-computed embeddings

### RAG System

Documents → Embed → Cache → Semantic Search:

- **5 knowledge base documents**: company info, ordering policy, shipping policy, returns policy, locations & contact
- Embeddings are pre-computed and cached in `embeddings.json`
- v5 adds **staleness detection**: compares file hashes to detect when source documents change and only regenerates embeddings when needed

### System Prompt Design

The system prompt evolves with each version, accumulating:

- Role definition (Emma, OfficeFlow customer support)
- Tool usage instructions
- Schema discovery requirement
- Stock confidentiality policy (qualitative-only disclosure)
- Conciseness directive

---

## 5. Key Reliability Patterns

### Schema Safety

The agent must always run `PRAGMA table_info(table_name)` before writing SQL queries. This prevents hallucinating column names and ensures queries are grounded in the actual database structure.

### Stock Confidentiality as Code

The stock policy is enforced at two levels:

1. **System prompt** — instructs the agent to disclose stock qualitatively only
2. **Code-based evaluator** — automatically catches any response containing exact numbers

### Tool Routing

Explicit separation: product/inventory questions go to the database tool, policy questions go to the knowledge base. The routing evaluator verifies this automatically.

### Embedding Cache Staleness Detection

v5 hashes source documents and compares against the cached hash. If documents have been updated, embeddings are regenerated transparently — no manual intervention needed.

---

## 6. Prompt Engineering Strategies

The project demonstrates several prompt strategies in practice:

| Strategy | Application in This Project |
|----------|---------------------------|
| **Role-Based** | Emma is defined as a customer support specialist with specific personality and constraints |
| **Instruction Hierarchy** | System prompt layers: role → tools → policies → behavior modifiers |
| **Negative Prompting** | "Never reveal exact stock quantities" — defining what NOT to do |
| **Chain-of-Thought** | Schema discovery before SQL queries is a forced reasoning step |
| **Template-Based** | Evaluation prompts use structured templates with placeholders for dynamic data |

---

## 7. Moving to Production (Module 3)

### Synthetic Trace Generation

Generates 1,000 synthetic interactions across 5 categories (inventory, policy, out-of-scope, mixed, website troubleshooting) for stress-testing at scale.

### Trace Upload

Loads synthetic traces, shifts timestamps to the current time, regenerates unique IDs, and uploads to LangSmith for large-scale analysis.

### Online Evaluation

Automatically scores every production trace as it arrives, providing continuous signal on agent quality without manual review.

---

## 8. MultiAgent Orchestration Patterns

The project also covers orchestration architectures for more complex systems:

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Sequential** | A → B → C pipeline | Simple workflows with strict ordering |
| **Parallel** | A ‖ B ‖ C, then merge | Independent analyses that need aggregation |
| **Hierarchical** | Master coordinates specialists | Complex tasks requiring different expertise |
| **State Machine** | Conditional transitions with loops | Iterative refinement (research ⇄ refine → analyze) |
| **Pub-Sub** | Event-driven, loosely coupled | Scalable, decoupled architectures |

### Reliability in Orchestration

- **Retry with exponential backoff** — transient failure recovery
- **Fallback agents** — primary → fallback1 → fallback2
- **Circuit breaker** — CLOSED → OPEN → HALF_OPEN recovery states
- **Graceful degradation** — one agent failure ≠ entire system failure
- **Timeout handling** — prevent indefinite waits

---

## Summary

Building reliable agents is not about writing a perfect prompt on the first try. It's a **disciplined loop**:

1. **Build** a minimal version
2. **Observe** behavior through tracing
3. **Evaluate** with layered, automated checks
4. **Improve** one thing at a time
5. **Validate** the improvement didn't break anything else
6. **Repeat**

The tools — LangSmith for observability, code-based and LLM-based evaluators for quality, pairwise comparison for A/B testing, and human alignment for calibration — form an evaluation infrastructure that makes agent development as rigorous as traditional software engineering.
