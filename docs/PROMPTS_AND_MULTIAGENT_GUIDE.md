# Complete Guide to Prompts & MultiAgent Orchestration

**Last Updated:** March 11, 2026

---

## Table of Contents

1. [Part 1: Prompt Guide](#part-1-comprehensive-prompt-guide)
   - What Are Prompts?
   - Types of Prompts
   - Prompt Strategies
   - Categories
   - Implementation Approaches
   - Best Practices
   - Project Structure
   - Advanced Techniques

2. [Part 2: MultiAgent Orchestration](#part-2-multiagent-orchestration)
   - Architecture Patterns
   - Orchestration Strategies
   - Communication Patterns
   - Workflow Patterns
   - Error Handling & Reliability
   - State Management
   - Best Practices
   - Implementation Guide

---

# Part 1: Comprehensive Prompt Guide

## 1. What Are Prompts?

A **prompt** is an instruction or input that guides an AI model to perform a specific task. It's the bridge between human intent and model behavior. Prompts can be:

- **Direct instructions** ("Summarize this in 3 sentences")
- **Contextual guidance** (background + task definition)
- **Structured templates** (placeholders for dynamic data)
- **System-level constraints** (behavior modifiers, personality)
- **Compositional components** (combined to form complex instructions)

### Core Function
Prompts serve to:
1. Define **what** the model should do
2. Specify **how** it should behave
3. Establish **constraints** and guardrails
4. Provide **context** for decision-making
5. Control **output format** and structure

---

## 2. Types of Prompts

### By Structure

#### **Instruction-Based Prompts**
Direct, explicit commands with minimal context.
```
Summarize the following text in 3 bullet points:
[TEXT]
```
✅ **Best for:** Simple, well-defined tasks
❌ **Limitations:** Less effective for nuanced reasoning

#### **Few-Shot Prompts**
Provide 2-5 examples of desired behavior before the actual task.
```
Here are examples of sentiment classification:

Input: "This movie was amazing!"
Label: POSITIVE

Input: "I hated every minute."
Label: NEGATIVE

Now classify: "The service was adequate but slow."
```
✅ **Best for:** Complex tasks, domain-specific knowledge
✅ **Benefit:** Shows pattern through examples
❌ **Cost:** Longer tokens, slower inference

#### **Chain-of-Thought (CoT) Prompts**
Explicit step-by-step reasoning before reaching conclusion.
```
Let's think step by step:
1. Extract the key facts from the situation
2. Identify constraints and resources
3. Generate multiple solution approaches
4. Evaluate each approach
5. Choose the best one

Problem: [PROBLEM]
```
✅ **Best for:** Math, logic, complex reasoning
✅ **Benefit:** Transparently shows reasoning

#### **Role-Based Prompts**
Define a persona or expert perspective.
```
You are an experienced software architect with 20 years of 
enterprise system design. Analyze the following architecture proposal.

[PROPOSAL]
```
✅ **Best for:** Tasks requiring specific expertise/tone
✅ **Benefit:** Guides model toward domain expertise

#### **Template-Based Prompts**
Structured format with placeholders for dynamic content.
```
Customer Query: {QUERY}
Product Category: {CATEGORY}
Customer History: {HISTORY}

Provide a response addressing all concerns, 
maintaining brand voice: {BRAND_VOICE}
```
✅ **Best for:** Production systems with variable inputs
✅ **Benefit:** Consistency, easy to version control

#### **Dynamic/Contextual Prompts**
Adapt based on input, user context, or previous interactions.
```
Based on previous conversation context:
{CONVERSATION_HISTORY}

Current request: {CURRENT_REQUEST}

Note: User expertise level is {EXPERTISE_LEVEL}
Adjust explanations accordingly.
```
✅ **Best for:** Conversational agents, personalized systems

### By Function

| Type | Purpose | Characteristics |
|------|---------|-----------------|
| **System Prompt** | Define model behavior, personality, constraints | Foundational, applies to all subsequent interactions |
| **User Prompt** | Task-specific requests from end-users | Variable, single-turn or multi-turn |
| **Agent Prompt** | Autonomous agent behavior guidance | Includes tool selection, reasoning, decision-making |
| **Evaluation Prompt** | Assess output quality | Uses rubrics, scoring criteria |
| **Safety/Guardrail Prompt** | Prevent harmful outputs | Defines what NOT to do |
| **Refinement Prompt** | Iterative improvement | "Revise your answer to..." |

---

## 3. Prompt Strategies

### Strategy Comparison Table

| Strategy | Purpose | Complexity | Token Cost | When to Use |
|----------|---------|-----------|-----------|------------|
| **Zero-Shot** | Direct task with no examples | Low | Low | Simple, well-defined tasks |
| **Few-Shot** | 2-5 examples provided | Medium | Medium | Complex tasks, rare domains |
| **Chain-of-Thought** | Step-by-step reasoning | Medium-High | Medium | Math, logic, reasoning |
| **ReAct** | Reason + Act + Observe | High | High | Multi-step, tool-using agents |
| **Role-Playing** | Assume expertise/persona | Low | Low | Specific expertise, tone |
| **Retrieval-Augmented** | Inject contextual knowledge | High | High | Domain-specific accuracy |
| **Tree-of-Thought** | Multiple reasoning paths | Very High | Very High | Complex problem-solving |
| **Instruction Hierarchy** | Primary goal + sub-tasks | Medium | Medium | Multi-part complex tasks |
| **Negative Prompting** | Define what NOT to do | Low | Low | Behavioral constraints |
| **Constraint-Based** | Hard output constraints | Low | Low | Format/safety requirements |

### Detailed Strategy Explanations

#### **Zero-Shot**
Simplest approach: task description without examples.
```python
prompt = """
Translate the following text to French:
{text}
"""
```
✅ Fast, low tokens
❌ May work poorly for complex tasks

#### **Few-Shot**
Include representative examples.
```python
prompt = """
Classify emails as spam or not spam:

Example 1:
Email: "Limited time offer! Click now to win FREE MONEY!!!"
Classification: SPAM

Example 2:
Email: "Meeting rescheduled to 3pm tomorrow in Conference Room B"
Classification: NOT_SPAM

Email: {user_email}
Classification: """
```
✅ Dramatically improves accuracy for complex tasks
❌ Costs more tokens

#### **Chain-of-Thought (CoT)**
Forces step-by-step reasoning.
```python
prompt = """
Answer the following question. Think step by step before answering.

Question: If a train travels 120 miles in 2 hours, what's its speed?

Let's think:
1. Speed = Distance / Time
2. Distance = 120 miles
3. Time = 2 hours
4. Speed = 120 / 2 = 60 mph

Question: {user_question}

Let's think through this step by step:"""
```
✅ Improves reasoning quality
✅ Makes logic transparent
❌ Increases tokens and latency

#### **ReAct (Reasoning + Acting)**
For agents: reason about action, then execute, then observe.
```python
prompt = """
You are a helpful research assistant. Use available tools to answer questions.

Available tools:
- search(query): Search the internet
- calculate(expression): Perform calculations
- fetch_url(url): Get webpage content

When answering:
1. Reason about what information is needed
2. Use appropriate tools
3. Observe the results
4. Synthesize into your answer

User question: {question}

Thought: I need to... [REASON]
Action: {tool_name}({params})
Observation: [TOOL_RESULT]
Thought: ...
Final Answer: ...
"""
```
✅ Enables tool use and interactivity
✅ Self-correcting through observation

#### **Role-Playing**
Assume specific expertise.
```python
prompt = """
You are a senior data scientist with 15 years of experience in ML operations.
You are reviewing a new data pipeline design.

Perspective:
- Focus on scalability, monitoring, and failure modes
- Consider infrastructure costs
- Highlight potential data quality issues
- Suggest production-ready improvements

Pipeline Design:
{design_doc}

Please review and provide detailed feedback.
"""
```
✅ Guides model toward specific perspective
✅ Controls tone and depth

#### **Retrieval-Augmented Generation (RAG)**
Inject relevant context from knowledge base.
```python
prompt = """
You are answering questions based on company documentation.

Relevant documentation:
---
{context_docs}
---

User question: {question}

Answer based only on the provided documentation. 
If the answer is not in the documentation, say so explicitly.
"""
```
✅ Reduces hallucinations
✅ Ensures grounding in facts
❌ Requires good retrieval system

#### **Tree-of-Thought**
Explore multiple reasoning paths.
```python
prompt = """
For this problem, explore multiple solution approaches and evaluate each:

Problem: {problem}

Approach 1: {approach_1_description}
  - Pros: ...
  - Cons: ...
  - Outcome: ...

Approach 2: {approach_2_description}
  - Pros: ...
  - Cons: ...
  - Outcome: ...

Approach 3: {approach_3_description}
  - Pros: ...
  - Cons: ...
  - Outcome: ...

Best approach: {selected} because...
"""
```
✅ Comprehensive exploration
❌ Expensive (many tokens, slow)

#### **Instruction Hierarchy**
Combine primary objective with sub-objectives.
```python
prompt = """
PRIMARY OBJECTIVE: Help users resolve customer support tickets

SUB-OBJECTIVES:
1. Understand the customer's issue completely
2. Search knowledge base for solutions
3. If no solution found, escalate appropriately
4. Provide clear, empathetic communication
5. Document resolution for future reference

CONSTRAINTS:
- Response time < 5 minutes
- Only resolve within documented scope
- Always offer follow-up support

Customer Issue: {issue}
"""
```
✅ Organizes complex instructions
✅ Clear priority hierarchy

---

## 4. Categories of Prompts

### By Complexity Level

#### **Simple Prompts**
Single action, clear input/output.
```
Translate to Spanish: "Hello, world"
```
- Characteristics: One task, direct answer
- Model: Any model works
- Success rate: High (>95%)

#### **Moderate Complexity**
Multiple steps, conditional logic.
```
Analyze this customer feedback for:
1. Sentiment (positive/negative/neutral)
2. Product mentioned
3. Specific issues raised
4. Suggested improvements

Feedback: "{feedback}"

Format as JSON.
```
- Characteristics: 3-5 related subtasks
- Model: Medium+ capability needed
- Success rate: 80-90%

#### **High Complexity**
Multi-stage reasoning, tool integration, state management.
```
You are a project planning assistant.

Given a project description, you will:
1. Break down into milestones
2. Identify resource requirements for each
3. Calculate timeline and dependencies
4. Risk assessment
5. Create execution plan

Use these tools as needed:
- project_history_search()
- team_capability_lookup()
- risk_database_query()

Project: {description}
```
- Characteristics: Many interdependent tasks, requires judgment
- Model: Advanced model (GPT-4+) needed
- Success rate: 60-80%

### By Domain

#### **Conversational**
Chat, Q&A, dialogue systems.
```
You are a helpful customer service agent.
- Be friendly and professional
- Acknowledge customer emotions
- Provide solutions or escalate appropriately

Customer: {message}
```

#### **Creative**
Writing, ideation, content generation.
```
Write a creative product description for a new smartphone.
- Target audience: Tech-savvy millennials
- Tone: Exciting, innovative
- Length: 2-3 paragraphs
- Include 3 key features

Features: {features}
```

#### **Analytical**
Data analysis, summarization, insights.
```
Analyze the quarterly sales data provided.
Identify:
1. Top-performing products
2. Regional trends
3. Year-over-year growth rates
4. Anomalies or concerns
5. Recommendations for next quarter

Data: {csv_data}
Format: JSON summary
```

#### **Agent-Based**
Autonomous task execution, tool use.
```
You are an autonomous data processing agent.
Your task: Extract structured data from documents.

Available tools:
- read_document(path)
- extract_fields(document, schema)
- validate_data(data)
- save_results(filename)

Process: {documents}
"""
```

#### **Safety/Compliance**
Content filtering, policy enforcement.
```
Review the following content for policy violations.

Policy violations to check:
- Hate speech
- Violence or harm
- Personal information exposure
- Copyright infringement
- Company confidentiality breaches

Content: {content}
Action: {approve/flag/require_revision}
Reason: {explanation}
"""
```

### By Scope

#### **Local Prompts**
Inline in code, single use.
```python
response = model.complete("Write a haiku about Python")
```
✅ Simple for one-offs
❌ Clutters code, hard to maintain

#### **Global Prompts**
Reusable across project.
```python
SUMMARIZATION_PROMPT = "Summarize in 3 bullet points: {text}"
# Used in multiple places
result1 = model.complete(SUMMARIZATION_PROMPT.format(text=doc1))
result2 = model.complete(SUMMARIZATION_PROMPT.format(text=doc2))
```

#### **System Prompts**
Foundation, applies to all interactions.
```python
SYSTEM_PROMPT = """
You are a helpful AI assistant with expertise in:
- Software engineering
- Data analysis
- Project management

Always:
- Provide accurate information
- Admit uncertainty when applicable
- Ask clarifying questions
- Provide thorough explanations
"""
# Applied to all conversations
```

#### **User Override**
Allows customization per request.
```python
system_prompt = SYSTEM_PROMPT + custom_instructions
response = model.complete(
    system=system_prompt,
    user=user_message
)
```

---

## 5. Implementation Approaches

### A. Inline Prompts (Hardcoded)

**Use Case:** Quick prototyping, simple one-off tasks

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {
            "role": "system",
            "content": "You are a helpful Python expert."
        },
        {
            "role": "user",
            "content": "Explain async/await in Python"
        }
    ]
)
```

**Pros:**
- ✅ Simple, direct control
- ✅ Easy to debug

**Cons:**
- ❌ Not reusable
- ❌ Clutters code
- ❌ Hard to maintain
- ❌ Not version controllable

---

### B. File-Based Prompts (YAML/JSON)

**Use Case:** Reusable prompts, version control, multi-language projects

**Directory Structure:**
```
project/
├── prompts/
│   ├── system/
│   │   ├── base.yaml
│   │   ├── analyst.yaml
│   │   └── safety.yaml
│   ├── tasks/
│   │   ├── summarize.yaml
│   │   ├── extract.yaml
│   │   └── analyze.yaml
│   └── evaluation/
│       ├── correctness.yaml
│       └── quality.yaml
```

**Example: prompts/tasks/summarize.yaml**
```yaml
name: "Document Summarization"
version: "2.1"
category: "summarization"
author: "data-team"
created: "2024-01-15"
tested_models: ["gpt-4", "claude-3-5-sonnet"]
performance:
  accuracy: 0.92
  avg_latency_ms: 2500
  cost_per_call: 0.0042

system: |
  You are an expert document analyst.
  Your task is to create concise, accurate summaries.
  
  Guidelines:
  - Preserve key information
  - Eliminate redundancy
  - Use clear language
  - Maintain factual accuracy

user_template: |
  Document:
  {document}
  
  Required format:
  - 3-5 bullet points
  - Each point max 20 words
  - Focus on: {focus_areas}
  - Exclude: {exclude_topics}
  
  Summary:
```

**Implementation:**
```python
import yaml

class PromptManager:
    def __init__(self, prompts_dir="./prompts"):
        self.prompts_dir = prompts_dir
        self.prompts = self._load_all_prompts()
    
    def _load_all_prompts(self):
        """Recursively load all prompt YAML files"""
        prompts = {}
        for root, dirs, files in os.walk(self.prompts_dir):
            for file in files:
                if file.endswith('.yaml'):
                    path = os.path.join(root, file)
                    key = path.replace(self.prompts_dir, '').strip('/')
                    with open(path) as f:
                        prompts[key] = yaml.safe_load(f)
        return prompts
    
    def get_system_prompt(self, prompt_key):
        """Get system prompt by key"""
        return self.prompts[prompt_key]["system"]
    
    def format_user_prompt(self, prompt_key, **kwargs):
        """Format user prompt template with variables"""
        template = self.prompts[prompt_key]["user_template"]
        return template.format(**kwargs)
    
    def get_metadata(self, prompt_key):
        """Get prompt metadata (version, author, performance)"""
        prompt = self.prompts[prompt_key]
        return {
            "name": prompt.get("name"),
            "version": prompt.get("version"),
            "author": prompt.get("author"),
            "models": prompt.get("tested_models"),
            "performance": prompt.get("performance")
        }

# Usage
pm = PromptManager()
system = pm.get_system_prompt("tasks/summarize.yaml")
user = pm.format_user_prompt(
    "tasks/summarize.yaml",
    document=doc_text,
    focus_areas="key findings, methodology",
    exclude_topics="author, date"
)

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
)
```

**Pros:**
- ✅ Version controllable (git history)
- ✅ Reusable across projects
- ✅ Metadata tracked (performance, author)
- ✅ Easy to manage at scale
- ✅ Supports multiple languages

**Cons:**
- ❌ Requires file management
- ❌ Need loading logic

---

### C. Prompt Manager Classes (Recommended)

**Enhanced version with caching, versioning, A/B testing:**

```python
import json
from datetime import datetime
from typing import Dict, Optional

class PromptManager:
    def __init__(self, prompts_dir="./prompts", cache_dir="./cache"):
        self.prompts_dir = prompts_dir
        self.cache_dir = cache_dir
        self.prompts = self._load_all_prompts()
        self._execution_history = []
    
    def get_prompt(self, key: str, variant: str = "default") -> Dict:
        """Get prompt by key and optional variant (a, b, c for A/B testing)"""
        prompt = self.prompts[key]
        if variant != "default" and f"variant_{variant}" in prompt:
            return prompt[f"variant_{variant}"]
        return prompt
    
    def format_prompt(self, key: str, **kwargs) -> dict:
        """Return formatted system + user prompt"""
        prompt = self.get_prompt(key)
        return {
            "system": prompt.get("system", ""),
            "user": prompt.get("user_template", "").format(**kwargs),
            "metadata": prompt.get("metadata", {})
        }
    
    def execute(self, prompt_key: str, client, model: str, **prompt_vars):
        """Execute prompt and log execution"""
        formatted = self.format_prompt(prompt_key, **prompt_vars)
        
        response = client.messages.create(
            model=model,
            messages=[
                {"role": "system", "content": formatted["system"]},
                {"role": "user", "content": formatted["user"]}
            ]
        )
        
        # Log execution for analysis
        self._execution_history.append({
            "prompt_key": prompt_key,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "success": True
        })
        
        return response.content[0].text
    
    def analyze_performance(self, prompt_key: str):
        """Analyze execution performance for a prompt"""
        executions = [
            e for e in self._execution_history 
            if e["prompt_key"] == prompt_key
        ]
        
        if not executions:
            return None
        
        total_tokens = sum(
            e["input_tokens"] + e["output_tokens"] 
            for e in executions
        )
        avg_tokens = total_tokens / len(executions)
        
        return {
            "count": len(executions),
            "avg_tokens": avg_tokens,
            "total_tokens": total_tokens,
            "success_rate": sum(
                1 for e in executions if e["success"]
            ) / len(executions)
        }
```

**Pros:**
- ✅ Scalable and organized
- ✅ Built-in performance tracking
- ✅ A/B testing support
- ✅ Execution logging
- ✅ Easy versioning & testing

**Cons:**
- ❌ More complex initial setup

---

### D. Prompt Composition (Modular)

**Use Case:** Complex prompts built from reusable components

```python
class ComposablePrompt:
    """Build complex prompts from modular components"""
    
    def __init__(self):
        self.components = {}
    
    def add_role(self, role: str):
        """Add role definition"""
        self.components["role"] = f"You are a {role}."
        return self
    
    def add_task(self, task: str):
        """Add task description"""
        self.components["task"] = f"Your task is to {task}."
        return self
    
    def add_context(self, context: str):
        """Add background context"""
        self.components["context"] = f"Context: {context}"
        return self
    
    def add_instructions(self, instructions: List[str]):
        """Add numbered instructions"""
        inst_text = "\n".join(
            [f"{i+1}. {inst}" for i, inst in enumerate(instructions)]
        )
        self.components["instructions"] = f"Instructions:\n{inst_text}"
        return self
    
    def add_format(self, format_spec: str):
        """Add output format specification"""
        self.components["format"] = f"Output format: {format_spec}"
        return self
    
    def add_constraints(self, constraints: List[str]):
        """Add constraints"""
        const_text = "\n".join(
            [f"- {c}" for c in constraints]
        )
        self.components["constraints"] = f"Constraints:\n{const_text}"
        return self
    
    def add_examples(self, examples: List[Dict]):
        """Add examples"""
        ex_text = "\n".join([
            f"Example {i+1}:\nInput: {e['input']}\nOutput: {e['output']}"
            for i, e in enumerate(examples)
        ])
        self.components["examples"] = f"Examples:\n{ex_text}"
        return self
    
    def build(self) -> str:
        """Assemble all components into final prompt"""
        order = [
            "role", "task", "context", "instructions",
            "format", "constraints", "examples"
        ]
        
        parts = []
        for key in order:
            if key in self.components:
                parts.append(self.components[key])
        
        return "\n\n".join(parts)

# Usage
prompt = (ComposablePrompt()
    .add_role("expert data analyst")
    .add_task("analyze sales trends and provide insights")
    .add_context("quarterly sales data for Q1-Q3 2024")
    .add_instructions([
        "Extract top 3 performing products",
        "Calculate quarter-over-quarter growth",
        "Identify any concerning trends",
        "Provide 2-3 actionable recommendations"
    ])
    .add_format("JSON with structure: {products: [], growth: {}, trends: [], recommendations: []}")
    .add_constraints([
        "Only use data provided",
        "Be specific with numbers",
        "Cite which quarter for each insight"
    ])
    .build())
```

**Pros:**
- ✅ Modular and reusable
- ✅ Easy to build variations
- ✅ Readable and maintainable
- ✅ Test individual components

---

## 6. Best Practices for Creating & Defining Prompts

### Core Principles

#### **1. Be Explicit**
Clear instructions > implicit assumptions

❌ **Bad:**
```
Summarize this text
```

✅ **Good:**
```
Summarize the following text in 3 bullet points.
Focus on the main conclusions, not supporting details.
Use clear, simple language.
```

#### **2. Use Structure**
Organize with sections, numbered steps, clear delimiters.

❌ **Bad:**
```
Take this customer feedback and analyze it
```

✅ **Good:**
```
Analyze the following customer feedback for:

1. SENTIMENT: positive, negative, or neutral
2. TOPICS: What product/service is mentioned?
3. ISSUES: What specific problems are mentioned?
4. SENTIMENT DRIVERS: Why do they feel this way?

Feedback:
---
{feedback}
---

Analysis (JSON format):
```

#### **3. Provide Context**
Background information, constraints, examples.

✅ **Good:**
```
Company: TechCorp (SaaS, enterprise software)
Product: CloudSync (file collaboration tool)
Target User: Enterprise IT administrators
Tone: Professional, trustworthy, solution-focused

Customer Feedback: {feedback}

Analyze the feedback considering:
- Company positioning
- Product capabilities
- User role and needs
```

#### **4. Define Format**
Specify exact output format expected.

✅ **Examples:**
```
Format as JSON: {"sentiment": "...", "topics": [...], "action": "..."}
Format as structured text with clear sections
Format as CSV rows with headers: name,email,issue_type
Format as Markdown bullet list
```

#### **5. Include Guardrails**
Explicitly state what NOT to do, safety constraints.

✅ **Good:**
```
DO:
- Provide objective analysis
- Cite specific examples from the text
- Acknowledge limitations

DO NOT:
- Make assumptions about information not provided
- Include personal opinions
- Mention competitor products
- Generate harmful content
```

#### **6. Test Variations**
A/B test different framings.

```python
prompts_to_test = [
    {"version": "a", "framing": "analytical"},
    {"version": "b", "framing": "empathetic"},
    {"version": "c", "framing": "detailed"},
]

for variant in prompts_to_test:
    results = test_prompt("summarize.yaml", variant)
    print(f"Version {variant['version']}: {results.quality_score}")
```

#### **7. Iterate**
Start simple, add complexity as needed.

**Phase 1 (Simple):**
```
Summarize: {text}
```

**Phase 2 (With structure):**
```
Summarize in 3 parts:
- Main idea
- Key supporting points
- Conclusion

Text: {text}
```

**Phase 3 (With guardrails):**
```
Summarize professional meeting notes in 3 parts:
- Decisions made
- Action items (owner + deadline)
- Next steps

Notes: {text}

Only include items explicitly mentioned.
Do not infer decisions not stated.
```

#### **8. Document Reasoning**
Add comments explaining prompt design.

✅ **Good:**
```yaml
# We found that few-shot examples improved accuracy by 15%
# for classification of ambiguous product feedback.
# Each example is representative of a distinct category.
#
# The instruction "be concise" reduces token usage by 30%
# while maintaining 95%+ accuracy.

few_shot_examples:
  - example_1: {...}
  - example_2: {...}
```

### What NOT To Do

- ❌ **Open-ended vague instructions** - "Do something useful with this data"
- ❌ **Contradictory statements** - "Be detailed but concise"
- ❌ **Excessive complexity in single prompt** - Break into multiple prompts
- ❌ **Hardcoding sensitive information** - Use placeholders/templates
- ❌ **Ignoring output quality variations** - Test and iterate
- ❌ **Over-commenting** - Keep it readable
- ❌ **Assuming model knowledge** - Provide context explicitly

### Quick Template for Effective Prompts

```
[ROLE]: You are a {specific role/expertise}

[GOAL]: Your task is to {clear objective}

[CONTEXT]: 
{Background information}
{Relevant constraints}
{Related information}

[INSTRUCTIONS]:
1. {Step 1}
2. {Step 2}
3. {Step 3}

[FORMAT]: 
Output should be in {desired format}
{Specific structure requirements}

[CONSTRAINTS]:
- Do {positive constraint}
- Don't {negative constraint}
- Always {important requirement}

[EXAMPLES]:
Input: {example input}
Output: {example output}

Input: {example input}
Output: {example output}
```

---

## 7. Project Structure for Managing Prompts

### Recommended Directory Organization

```
project-root/
├── README.md
├── prompts/
│   ├── README.md                    # Registry of all prompts
│   ├── system/
│   │   ├── base.yaml               # Base system prompt
│   │   ├── analyst.yaml            # Analyst persona
│   │   ├── safety.yaml             # Safety constraints
│   │   └── agent.yaml              # Agent base behavior
│   ├── tasks/
│   │   ├── summarize.yaml
│   │   ├── classify.yaml
│   │   ├── extract.yaml
│   │   ├── analyze.yaml
│   │   ├── generate.yaml
│   │   └── validate.yaml
│   ├── evaluations/
│   │   ├── correctness.yaml        # Check if answer is correct
│   │   ├── relevance.yaml          # Check if answer is relevant
│   │   ├── quality.yaml            # General quality assessment
│   │   └── safety.yaml             # Check for safety violations
│   ├── agents/
│   │   ├── orchestrator.yaml       # Main agent orchestrator
│   │   ├── researcher.yaml         # Research agent
│   │   ├── analyst.yaml            # Analysis agent
│   │   └── planner.yaml            # Planning agent
│   └── variations/
│       ├── summarize_v1.yaml       # Older versions
│       ├── summarize_v2.yaml
│       └── ARCHIVE.md              # Deprecated prompts
├── src/
│   ├── prompt_manager.py           # Prompt loading/formatting
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── orchestrator.py
│   │   └── specialized_agents.py
│   └── evaluators/
│       └── prompt_evaluator.py
└── tests/
    ├── test_prompts.py
    ├── test_agents.py
    └── fixtures/
        └── test_data.json
```

### Prompt Metadata Template

Every prompt should include metadata:

```yaml
# prompts/tasks/summarize.yaml

metadata:
  name: "Document Summarization"
  version: "2.3.1"
  category: "summarization"
  author: "analytics-team"
  created: "2024-01-15"
  last_updated: "2024-03-10"
  status: "production"  # production, staging, experimental, deprecated
  
  # Track which models work best
  tested_models:
    - name: "gpt-4"
      accuracy: 0.94
      avg_latency_ms: 2100
      cost_per_call: 0.045
    - name: "claude-3-5-sonnet"
      accuracy: 0.92
      avg_latency_ms: 1800
      cost_per_call: 0.0042
  
  # Known issues and limitations
  known_issues:
    - "Struggles with very long documents (>10k tokens)"
    - "May miss nuanced technical details"
  
  # Links to related resources
  related:
    - "summarize_with_focus.yaml"
    - "extract_key_points.yaml"
  
  tags:
    - "summarization"
    - "nlp"
    - "content-processing"

# Prompt content follows...
```

### Prompt Registry (prompts/README.md)

Keep a central registry for discoverability:

```markdown
# Prompt Registry

## System Prompts
- [Base System Prompt](./system/base.yaml) - Default behavior and constraints
- [Analyst Persona](./system/analyst.yaml) - Expert analyst mode
- [Safety Constraints](./system/safety.yaml) - Safety guardrails

## Task Prompts

### Summarization
- [Document Summarization](./tasks/summarize.yaml) - General document summary
- [Summarize with Focus](./tasks/summarize_focused.yaml) - Focused summary on specific topics

### Classification
- [Text Classification](./tasks/classify.yaml) - Multi-class classification

### Extraction
- [Entity Extraction](./tasks/extract.yaml) - Extract structured data

### Analysis
- [Trend Analysis](./tasks/analyze_trends.yaml) - Identify trends in data
- [Sentiment Analysis](./tasks/analyze_sentiment.yaml) - Sentiment classification

### Generation
- [Content Generation](./tasks/generate.yaml) - Create content
- [Code Generation](./tasks/generate_code.yaml) - Generate code snippets

## Evaluation Prompts
- [Correctness Evaluator](./evaluations/correctness.yaml) - Check answer correctness
- [Quality Evaluator](./evaluations/quality.yaml) - General quality assessment

## Agent Prompts
- [Orchestrator Agent](./agents/orchestrator.yaml) - Main orchestration logic
- [Research Agent](./agents/researcher.yaml) - Information gathering
- [Analyst Agent](./agents/analyst.yaml) - Data analysis
```

---

## 8. Advanced: Prompt Engineering for Your Project

### For Agent-Based Systems

Given your project's focus on reliable agents, consider these agent-specific prompt patterns:

#### **Agent Role Definition**
```yaml
system: |
  You are a reliable, task-focused AI agent.
  
  CORE ATTRIBUTES:
  - Logical and methodical
  - Transparent about reasoning
  - Careful with accuracy
  - Proactive in error checking
  - Honest about limitations
  
  EXPERTISE AREAS:
  {expertise_areas}
  
  OPERATIONAL PRINCIPLES:
  1. Understand the full request before acting
  2. Break complex tasks into steps
  3. Verify assumptions with the user when unclear
  4. Document your reasoning
  5. Check results before returning
  6. Escalate when uncertain
```

#### **Action Space Definition**
```yaml
user_template: |
  AVAILABLE TOOLS:
  {tools_description}
  
  TASK: {task}
  CONSTRAINTS: {constraints}
  CONTEXT: {context}
  
  Please analyze the task and execute using available tools.
  Show your reasoning for each tool choice.
```

#### **Reasoning Process**
```yaml
system: |
  Your reasoning process:
  
  1. ANALYSIS: What is being asked?
     - Identify core objective
     - List constraints
     - Assess complexity
  
  2. PLANNING: How will you approach it?
     - Break into subtasks
     - Identify required tools
     - Plan error handling
  
  3. EXECUTION: Carry it out
     - Execute each step
     - Verify intermediate results
     - Adapt if needed
  
  4. VERIFICATION: Check the result
     - Does it meet requirements?
     - Are there any issues?
     - Is it safe to return?
```

#### **Safety & Constraints**
```yaml
system: |
  SAFETY CONSTRAINTS:
  
  MUST:
  - Verify all destructive operations with user first
  - Validate all inputs before processing
  - Log all decisions and actions
  - Report uncertainty explicitly
  
  MUST NOT:
  - Execute unverified operations
  - Access unauthorized resources
  - Modify data without confirmation
  - Provide information outside your scope
  
  ESCALATION TRIGGERS:
  {escalation_rules}
```

---

## 9. Testing & Iteration Strategies

### Minimal Testing Framework

```python
from dataclasses import dataclass
from typing import List, Callable

@dataclass
class TestCase:
    input_data: dict
    expected_patterns: List[str]  # Patterns that should appear in output
    should_contain: List[str]     # Exact phrases that should appear
    should_not_contain: List[str] # Phrases that should NOT appear

class PromptTester:
    def __init__(self, prompt_manager, model_client):
        self.pm = prompt_manager
        self.client = model_client
        self.results = []
    
    def test_prompt(self, prompt_key: str, test_cases: List[TestCase], model: str = "claude-3-5-sonnet-20241022"):
        """Test a prompt against multiple test cases"""
        passed = 0
        failed = 0
        
        for i, test_case in enumerate(test_cases):
            try:
                # Format and execute prompt
                formatted = self.pm.format_prompt(prompt_key, **test_case.input_data)
                response = self.client.messages.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": formatted["system"]},
                        {"role": "user", "content": formatted["user"]}
                    ]
                )
                output = response.content[0].text
                
                # Run assertions
                success = True
                failures = []
                
                for pattern in test_case.expected_patterns:
                    if pattern not in output:
                        success = False
                        failures.append(f"Missing pattern: {pattern}")
                
                for phrase in test_case.should_contain:
                    if phrase not in output:
                        success = False
                        failures.append(f"Missing phrase: {phrase}")
                
                for phrase in test_case.should_not_contain:
                    if phrase in output:
                        success = False
                        failures.append(f"Found forbidden phrase: {phrase}")
                
                if success:
                    passed += 1
                else:
                    failed += 1
                    print(f"❌ Test case {i+1} FAILED:")
                    for failure in failures:
                        print(f"   - {failure}")
                    print(f"Output:\n{output[:500]}...\n")
            
            except Exception as e:
                failed += 1
                print(f"❌ Test case {i+1} ERROR: {e}\n")
        
        # Print summary
        print(f"\n{'='*50}")
        print(f"Results for {prompt_key}:")
        print(f"Passed: {passed}/{len(test_cases)}")
        print(f"Failed: {failed}/{len(test_cases)}")
        print(f"Success rate: {passed/len(test_cases)*100:.1f}%")
        print(f"{'='*50}\n")
        
        return {"passed": passed, "failed": failed, "total": len(test_cases)}

# Usage
tester = PromptTester(pm, client)

test_cases = [
    TestCase(
        input_data={"document": "Lorem ipsum...", "focus_areas": "key findings"},
        expected_patterns=["bullet point", "finding"],
        should_contain=["finding"],
        should_not_contain=["author"]
    ),
    # ... more test cases
]

tester.test_prompt("tasks/summarize.yaml", test_cases)
```

### Evaluation Approaches

#### **Deterministic Evaluation**
Check for required phrases, format compliance.

```python
def evaluate_deterministic(output: str, criteria: dict) -> float:
    """Score output against deterministic criteria"""
    score = 0
    max_score = 0
    
    # Check required patterns
    if "required_patterns" in criteria:
        max_score += len(criteria["required_patterns"])
        for pattern in criteria["required_patterns"]:
            if pattern.lower() in output.lower():
                score += 1
    
    # Check format
    if "format" in criteria:
        max_score += 1
        try:
            json.loads(output)
            if criteria["format"] == "json":
                score += 1
        except:
            pass
    
    # Check length constraints
    if "min_words" in criteria:
        max_score += 1
        if len(output.split()) >= criteria["min_words"]:
            score += 1
    
    return score / max_score if max_score > 0 else 0
```

#### **Probabilistic Evaluation**
Use LLM to judge output quality.

```python
def evaluate_with_llm(output: str, criteria: str) -> dict:
    """Use an LLM evaluator to assess output"""
    evaluation_prompt = f"""
    Evaluate the following output against these criteria:
    
    CRITERIA:
    {criteria}
    
    OUTPUT:
    {output}
    
    Provide:
    1. Score (0-100)
    2. Strengths
    3. Weaknesses
    4. Improvements
    
    Response as JSON: {{"score": N, "strengths": [...], "weaknesses": [...], "improvements": [...]}}
    """
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": evaluation_prompt}]
    )
    
    return json.loads(response.content[0].text)
```

#### **User Review**
Manual spot checks by domain experts.

```python
# Save outputs for human review
samples_for_review = [
    {"prompt_key": "summarize", "output": output1, "reference": ref1},
    {"prompt_key": "summarize", "output": output2, "reference": ref2},
]

with open("review_samples.json", "w") as f:
    json.dump(samples_for_review, f, indent=2)

# Run in notebook for interactive review
for i, sample in enumerate(samples_for_review):
    print(f"\nSample {i+1}:")
    print(f"Output: {sample['output']}")
    print(f"Reference: {sample['reference']}")
    rating = input("Rate quality (1-5): ")
    sample["human_rating"] = int(rating)
```

---

## 10. Common Pitfalls & Solutions

| Problem | Symptoms | Solutions |
|---------|----------|-----------|
| **Inconsistent outputs** | Same input produces different quality outputs | Add examples, make constraints explicit, use system prompt for consistency |
| **Model ignores constraints** | Output violates stated requirements | Place constraints in system prompt, repeat important ones, use specific formatting instructions |
| **Too verbose** | Outputs longer than needed | Use "be concise", add word limits, specify "3 sentences max" |
| **Hallucinations** | Model invents facts | Add retrieval-augmented context, ask for citations, use "only mention facts from provided text" |
| **Wrong format** | Output doesn't match specified format | Explicitly state format in instructions, provide format example, validate output |
| **Poor reasoning** | Jumps to conclusions without explanation | Add chain-of-thought, use explicit reasoning steps |
| **Model doesn't understand task** | Fails on complex instructions | Break into simpler sub-tasks, add more examples, use role-playing |
| **Slow responses** | High latency | Simplify prompt, reduce examples, use streaming |
| **High costs** | Unexpected token usage | Reduce few-shot examples, compress context, use shorter instructions |

---

# Part 2: MultiAgent Orchestration

## 1. What is MultiAgent Orchestration?

**MultiAgent Orchestration** is the art and science of coordinating multiple AI agents to work together toward complex goals. Rather than one monolithic AI solving everything, orchestration breaks problems into specialized agent roles and coordinates their interactions.

### Key Concepts

- **Agents**: Specialized AI entities with specific roles/expertise
- **Orchestration**: Coordination logic deciding which agent acts when
- **Communication**: How agents share information and results
- **State**: Shared context and knowledge across agents
- **Workflows**: Sequences of agent interactions

### Why MultiAgent Systems?

✅ **Specialization** - Each agent focuses on what it's best at
✅ **Scalability** - Can handle more complex problems
✅ **Modularity** - Easy to add/remove agents without rebuilding
✅ **Debugging** - Easier to identify which agent caused an issue
✅ **Reasoning** - Can model expert interactions
✅ **Transparency** - Clear which agent made which decision
✅ **Cost** - Can use cheaper models for simple tasks, expensive ones for complex

### When to Use MultiAgent

**Use MultiAgent when:**
- Problem has distinct sub-tasks requiring different expertise
- You need specialist knowledge for different aspects
- Task requires research, analysis, and synthesis
- You want transparent reasoning (can see each agent's contribution)
- Complexity scales and single agent struggles
- Different models excel at different subtasks

**Use Single Agent when:**
- Problem is well-defined and focused
- Single prompt can cover all requirements
- Speed/cost are critical (fewer hops)
- No clear natural task decomposition

---

## 2. MultiAgent Architecture Patterns

### A. Sequential Pattern

Agents work in a strict sequence: Agent A → Agent B → Agent C

```
Input
  ↓
[Research Agent] - Gathers information
  ↓
[Analysis Agent] - Analyzes the information
  ↓
[Synthesis Agent] - Creates final output
  ↓
Output
```

**Use Case:** Data flows in one direction; later agents depend on earlier results

**Implementation:**
```python
class SequentialOrchestrator:
    def __init__(self, agents: List[Agent]):
        self.agents = agents
    
    def execute(self, input_data: dict) -> dict:
        result = input_data
        for agent in self.agents:
            print(f"🔄 Running {agent.name}...")
            result = agent.execute(result)
            print(f"✅ {agent.name} completed")
        return result

# Usage
orchestrator = SequentialOrchestrator([
    ResearchAgent(),
    AnalysisAgent(),
    SynthesisAgent()
])

result = orchestrator.execute({"query": "market trends in AI"})
```

**Pros:**
- ✅ Simple to understand and debug
- ✅ Clear execution flow
- ✅ Easy to add agents

**Cons:**
- ❌ Inefficient if agents could run in parallel
- ❌ Later agents depend on earlier agent quality
- ❌ No feedback loops

### B. Parallel Pattern

Multiple agents work independently, results merged.

```
Input
  ├→ [Agent A - Sentiment] ──┐
  ├→ [Agent B - Topics]      ├→ [Merger] → Output
  └→ [Agent C - Entities] ───┘
```

**Use Case:** Independent analyses that enrich overall output

**Implementation:**
```python
import asyncio

class ParallelOrchestrator:
    def __init__(self, agents: List[Agent]):
        self.agents = agents
    
    async def execute(self, input_data: dict) -> dict:
        print(f"🔄 Running {len(self.agents)} agents in parallel...")
        
        # Run all agents asynchronously
        results = await asyncio.gather(*[
            asyncio.to_thread(agent.execute, input_data)
            for agent in self.agents
        ])
        
        # Merge results
        merged = self._merge_results(
            [{"agent": a.name, "result": r} for a, r in zip(self.agents, results)]
        )
        
        print(f"✅ All agents completed")
        return merged
    
    def _merge_results(self, agent_results: List[dict]) -> dict:
        """Combine results from all agents"""
        return {
            "analyses": agent_results,
            "merged": {
                k: v for result in agent_results
                for k, v in result.get("result", {}).items()
            }
        }

# Usage
orchestrator = ParallelOrchestrator([
    SentimentAgent(),
    TopicAgent(),
    EntityAgent()
])

results = asyncio.run(orchestrator.execute({"text": feedback}))
```

**Pros:**
- ✅ Faster (parallel execution)
- ✅ Independent analyses enrich results
- ✅ Failure in one agent doesn't block others

**Cons:**
- ❌ More complex to implement
- ❌ Harder to pass results between agents

### C. Hierarchical Pattern

Master agent coordinates specialist agents.

```
                    [Master Orchestrator]
                    /        |        \
                   /         |         \
          [Specialist A]  [Specialist B]  [Specialist C]
               |               |                |
          [Sub-agents]    [Sub-agents]    [Sub-agents]
```

**Use Case:** Complex problems needing hierarchical decomposition

**Implementation:**
```python
class HierarchicalOrchestrator:
    def __init__(self, master_agent, specialist_agents: Dict[str, Agent]):
        self.master = master_agent
        self.specialists = specialist_agents
    
    def execute(self, input_data: dict) -> dict:
        # Step 1: Master analyzes and delegates
        print(f"🎯 Master orchestrator analyzing...")
        delegation_plan = self.master.analyze_and_plan(input_data)
        
        # Step 2: Execute delegated tasks
        specialist_results = {}
        for specialist_type, specialist in self.specialists.items():
            if specialist_type in delegation_plan["delegate_to"]:
                print(f"🔄 Delegating to {specialist_type}...")
                specialist_results[specialist_type] = specialist.execute(
                    input_data=input_data,
                    instructions=delegation_plan.get(f"{specialist_type}_instructions")
                )
        
        # Step 3: Master synthesizes results
        print(f"📋 Master synthesizing results...")
        final_result = self.master.synthesize(
            original_input=input_data,
            specialist_results=specialist_results
        )
        
        return final_result

# Usage
orchestrator = HierarchicalOrchestrator(
    master_agent=MasterOrchestrator(),
    specialist_agents={
        "researcher": ResearcherAgent(),
        "analyst": AnalystAgent(),
        "strategist": StrategistAgent()
    }
)

result = orchestrator.execute({"challenge": "improve market penetration"})
```

**Pros:**
- ✅ Handles complex hierarchical problems
- ✅ Master can adapt delegation
- ✅ Specialists don't need to know about each other

**Cons:**
- ❌ Most complex pattern
- ❌ Master agent needs strong planning ability

### D. State Machine Pattern

Agents represent states; transitions based on conditions.

```
START
  ↓
[Research State]
  ↓
Check: Have enough info?
  ├─ NO → Refine Research
  └─ YES → [Analysis State]
  ↓
Check: Analysis complete?
  ├─ NO → Expand Analysis
  └─ YES → [Output State]
  ↓
END
```

**Use Case:** Iterative processes where agents depend on conditions

**Implementation:**
```python
from enum import Enum

class State(Enum):
    RESEARCH = "research"
    ANALYZE = "analyze"
    REFINE = "refine"
    OUTPUT = "output"
    END = "end"

class StateBasedOrchestrator:
    def __init__(self, agents: Dict[State, Agent]):
        self.agents = agents
        self.current_state = State.RESEARCH
        self.context = {}
    
    def execute(self, input_data: dict) -> dict:
        self.context = input_data.copy()
        
        while self.current_state != State.END:
            print(f"📍 Current state: {self.current_state.value}")
            
            # Execute current state's agent
            agent = self.agents[self.current_state]
            result = agent.execute(self.context)
            self.context.update(result)
            
            # Determine next state
            self.current_state = self._determine_next_state()
        
        return self.context
    
    def _determine_next_state(self) -> State:
        """Logic for state transitions"""
        if self.current_state == State.RESEARCH:
            if self.context.get("research_complete"):
                return State.ANALYZE
            else:
                return State.RESEARCH
        
        elif self.current_state == State.ANALYZE:
            if self.context.get("needs_refinement"):
                return State.REFINE
            else:
                return State.OUTPUT
        
        elif self.current_state == State.REFINE:
            return State.ANALYZE
        
        else:
            return State.END

# Usage
orchestrator = StateBasedOrchestrator({
    State.RESEARCH: ResearchAgent(),
    State.ANALYZE: AnalysisAgent(),
    State.REFINE: RefinementAgent(),
    State.OUTPUT: OutputAgent()
})

result = orchestrator.execute({"topic": "AI trends"})
```

**Pros:**
- ✅ Natural for iterative problems
- ✅ Clear state transitions
- ✅ Easy to visualize flow

**Cons:**
- ❌ Can become complex with many states
- ❌ Requires careful state definition

### E. Publish-Subscribe (Event-Driven) Pattern

Agents communicate via events, not direct handoffs.

```
[Agent A] --emit event--> [Message Bus]
                            |
                            ├→ [Agent B] (listening)
                            ├→ [Agent C] (listening)
                            └→ [Agent D] (listening)
```

**Use Case:** Loosely coupled agents, dynamic interactions

**Implementation:**
```python
from typing import Callable, List

class EventBus:
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
        self.history = []
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(handler)
    
    def emit(self, event_type: str, data: dict):
        """Emit an event"""
        event = {"type": event_type, "data": data}
        self.history.append(event)
        print(f"📡 Event emitted: {event_type}")
        
        if event_type in self.listeners:
            for handler in self.listeners[event_type]:
                handler(data)

class EventDrivenAgent:
    def __init__(self, name: str, bus: EventBus):
        self.name = name
        self.bus = bus
        self.subscribed_to = []
    
    def subscribe_to(self, event_type: str):
        """Subscribe agent to event"""
        self.bus.subscribe(event_type, self.handle_event)
        self.subscribed_to.append(event_type)
    
    def emit(self, event_type: str, data: dict):
        """Emit event"""
        self.bus.emit(event_type, data)
    
    def handle_event(self, data: dict):
        """Override in subclass"""
        pass

class ResearchAgentEventDriven(EventDrivenAgent):
    def handle_event(self, data: dict):
        print(f"🔍 {self.name} received event: {data}")
        # Perform research
        results = {"research": "findings"}
        self.emit("research_complete", results)

class AnalysisAgentEventDriven(EventDrivenAgent):
    def handle_event(self, data: dict):
        print(f"📊 {self.name} analyzing: {data}")
        # Perform analysis
        results = {"analysis": "insights"}
        self.emit("analysis_complete", results)

# Usage
bus = EventBus()

research_agent = ResearchAgentEventDriven("Researcher", bus)
analysis_agent = AnalysisAgentEventDriven("Analyst", bus)

# Wire up event handlers
research_agent.subscribe_to("research_requested")
analysis_agent.subscribe_to("research_complete")

# Start the flow
bus.emit("research_requested", {"query": "AI trends"})
```

**Pros:**
- ✅ Very decoupled and flexible
- ✅ Easy to add new agents without modifying existing ones
- ✅ Natural for complex interaction patterns

**Cons:**
- ❌ Harder to debug (less visible flow)
- ❌ Can become chaotic with many events

---

## 3. Orchestration Strategies

### Strategy A: Pipeline Orchestration

Fixed sequence with progress tracking.

```python
class PipelineOrchestrator:
    def __init__(self, stages: List[dict]):
        """
        stages = [
            {"name": "stage1", "agent": agent1, "timeout": 30},
            {"name": "stage2", "agent": agent2, "timeout": 30},
        ]
        """
        self.stages = stages
        self.progress = {}
    
    def execute(self, input_data: dict) -> dict:
        data = input_data
        
        for stage in self.stages:
            stage_name = stage["name"]
            agent = stage["agent"]
            timeout = stage.get("timeout", 60)
            
            try:
                print(f"▶️  Starting {stage_name}...")
                
                # Execute with timeout
                result = self._execute_with_timeout(
                    agent.execute,
                    data,
                    timeout
                )
                
                data = result
                self.progress[stage_name] = "✅ completed"
                print(f"✅ {stage_name} completed")
            
            except Exception as e:
                self.progress[stage_name] = f"❌ failed: {e}"
                print(f"❌ {stage_name} failed: {e}")
                raise
        
        return data
    
    def _execute_with_timeout(self, func, data, timeout):
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Timeout after {timeout}s")
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        try:
            return func(data)
        finally:
            signal.alarm(0)
```

### Strategy B: Conditional Routing

Route to different agents based on input analysis.

```python
class ConditionalRouter:
    def __init__(self, router_agent, agents: Dict[str, Agent]):
        self.router = router_agent
        self.agents = agents
    
    def execute(self, input_data: dict) -> dict:
        # Router determines which agent(s) to use
        routing_decision = self.router.decide_route(input_data)
        
        results = {}
        for agent_key in routing_decision["selected_agents"]:
            if agent_key in self.agents:
                agent = self.agents[agent_key]
                print(f"🔀 Routing to {agent_key}...")
                results[agent_key] = agent.execute(input_data)
        
        return {
            "routing_decision": routing_decision,
            "results": results
        }
```

### Strategy C: Voting/Consensus

Multiple agents solve independently, results merged via voting.

```python
class VotingOrchestrator:
    def __init__(self, agents: List[Agent], merge_strategy="majority"):
        self.agents = agents
        self.merge_strategy = merge_strategy
    
    def execute(self, input_data: dict) -> dict:
        results = []
        
        for agent in self.agents:
            result = agent.execute(input_data)
            results.append(result)
        
        # Merge via voting
        if self.merge_strategy == "majority":
            final = self._majority_vote(results)
        elif self.merge_strategy == "weighted":
            final = self._weighted_vote(results)
        else:
            final = self._consensus(results)
        
        return final
    
    def _majority_vote(self, results):
        """Use most common answer"""
        from collections import Counter
        answers = [r.get("answer") for r in results]
        most_common = Counter(answers).most_common(1)[0][0]
        return {
            "answer": most_common,
            "confidence": answers.count(most_common) / len(answers),
            "all_results": results
        }
```

### Strategy D: Feedback Loop

Agents refine results iteratively.

```python
class FeedbackLoopOrchestrator:
    def __init__(self, worker_agent, evaluator_agent, max_iterations=3):
        self.worker = worker_agent
        self.evaluator = evaluator_agent
        self.max_iterations = max_iterations
    
    def execute(self, input_data: dict) -> dict:
        current_result = input_data
        
        for iteration in range(self.max_iterations):
            print(f"🔄 Iteration {iteration + 1}/{self.max_iterations}")
            
            # Worker produces result
            current_result = self.worker.execute(current_result)
            
            # Evaluator assesses
            evaluation = self.evaluator.evaluate(current_result)
            
            if evaluation.get("quality_score", 0) > 0.9:
                print(f"✅ Quality acceptable after iteration {iteration + 1}")
                break
            elif iteration < self.max_iterations - 1:
                # Provide feedback for next iteration
                current_result["feedback"] = evaluation.get("improvement_suggestions")
                print(f"📝 Feedback for next iteration: {evaluation.get('improvement_suggestions')}")
        
        return {
            "final_result": current_result,
            "iterations": iteration + 1,
            "final_evaluation": evaluation
        }
```

---

## 4. Communication Patterns

### Direct Communication
One agent explicitly calls another.

```python
class Agent:
    def __init__(self, name: str):
        self.name = name
    
    def execute(self, data):
        # Do work
        return result
    
    def ask(self, other_agent, question: str):
        """Ask another agent a question"""
        return other_agent.execute({"query": question})

# Usage
researcher = ResearcherAgent("Researcher")
analyst = AnalystAgent("Analyst")

research_result = researcher.execute({"topic": "AI"})
analysis = analyst.ask(researcher, "What are the key findings?")
```

**Pros:** Clear, direct, synchronous
**Cons:** Tight coupling, agent must know about others

### Indirect Communication (Message Queue)
Agents don't directly reference each other.

```python
class MessageQueue:
    def __init__(self):
        self.messages = []
    
    def send(self, from_agent: str, to_agent: str, message: dict):
        """Send message asynchronously"""
        self.messages.append({
            "from": from_agent,
            "to": to_agent,
            "content": message,
            "timestamp": datetime.now()
        })
    
    def receive(self, agent_name: str) -> List[dict]:
        """Receive all messages for this agent"""
        return [m for m in self.messages if m["to"] == agent_name]

class Agent:
    def __init__(self, name: str, queue: MessageQueue):
        self.name = name
        self.queue = queue
    
    def send_message(self, to_agent: str, message: dict):
        """Send to another agent via queue"""
        self.queue.send(self.name, to_agent, message)
    
    def check_messages(self):
        """Check for incoming messages"""
        return self.queue.receive(self.name)
```

**Pros:** Loose coupling, asynchronous, flexible
**Cons:** More complex, harder to debug

### Shared State Communication
Agents read/write shared context.

```python
class SharedContext:
    def __init__(self):
        self.data = {}
        self.history = []
    
    def set(self, key: str, value):
        """Set a value"""
        self.data[key] = value
        self.history.append({
            "action": "set",
            "key": key,
            "value": value,
            "timestamp": datetime.now()
        })
    
    def get(self, key: str):
        """Get a value"""
        return self.data.get(key)
    
    def update(self, updates: dict):
        """Update multiple values"""
        for k, v in updates.items():
            self.set(k, v)

class Agent:
    def __init__(self, name: str, context: SharedContext):
        self.name = name
        self.context = context
    
    def execute(self, task):
        # Read from shared context
        previous_findings = self.context.get("findings")
        
        # Do work
        results = self._do_work(task, previous_findings)
        
        # Write to shared context
        self.context.update({
            "findings": results,
            "last_agent": self.name
        })
        
        return results
```

**Pros:** Simple, all agents see all data
**Cons:** Can cause conflicts, race conditions in parallel execution

---

## 5. Error Handling & Reliability

### Strategy 1: Retry with Exponential Backoff

```python
import time
from typing import Callable

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """Retry function with exponential backoff"""
    retries = 0
    delay = base_delay
    
    while retries < max_retries:
        try:
            return func()
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                raise
            
            # Exponential backoff: delay * 2^retries
            delay = min(base_delay * (2 ** retries), max_delay)
            print(f"⏱️  Retry {retries}/{max_retries} after {delay}s: {e}")
            time.sleep(delay)

# Usage in agent
class RobustAgent:
    def execute(self, data):
        return retry_with_backoff(
            lambda: self._execute_internal(data),
            max_retries=3
        )
    
    def _execute_internal(self, data):
        # Actual execution logic
        pass
```

### Strategy 2: Fallback Agents

```python
class AgentWithFallback:
    def __init__(self, primary_agent: Agent, fallback_agents: List[Agent]):
        self.primary = primary_agent
        self.fallbacks = fallback_agents
    
    def execute(self, data):
        agents_to_try = [self.primary] + self.fallbacks
        
        for agent in agents_to_try:
            try:
                print(f"🔄 Trying {agent.name}...")
                return agent.execute(data)
            except Exception as e:
                print(f"❌ {agent.name} failed: {e}")
                if agent is agents_to_try[-1]:
                    raise
                continue
        
        raise RuntimeError("All agents failed")

# Usage
robust_agent = AgentWithFallback(
    primary_agent=GeminiAgent(),
    fallback_agents=[ClaudeAgent(), GPT4Agent()]
)
```

### Strategy 3: Timeout Handling

```python
import signal
import threading

class TimeoutError(Exception):
    pass

def execute_with_timeout(func, args=(), timeout=30):
    """Execute function with timeout"""
    result = [None]
    exception = [None]
    
    def target():
        try:
            result[0] = func(*args)
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        raise TimeoutError(f"Function timed out after {timeout}s")
    
    if exception[0]:
        raise exception[0]
    
    return result[0]

# Usage
class TimeoutAwareOrchestrator:
    def execute(self, agent, data, timeout=30):
        try:
            return execute_with_timeout(
                agent.execute,
                args=(data,),
                timeout=timeout
            )
        except TimeoutError:
            print(f"⏱️  {agent.name} timeout, using fallback...")
            # Handle timeout
```

### Strategy 4: Graceful Degradation

```python
class ResilientOrchestrator:
    def execute(self, input_data: dict) -> dict:
        results = {}
        warnings = []
        
        for agent in self.agents:
            try:
                results[agent.name] = agent.execute(input_data)
            except Exception as e:
                # Don't fail entire orchestration
                warnings.append({
                    "agent": agent.name,
                    "error": str(e)
                })
                # Provide partial result
                results[agent.name] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        return {
            "results": results,
            "warnings": warnings,
            "partial_success": len(warnings) > 0 and len(results) - len(warnings) > 0
        }
```

### Strategy 5: Circuit Breaker

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Stop sending requests
    HALF_OPEN = "half_open"  # Test if recovered

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
    
    def execute(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
            else:
                raise RuntimeError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def _should_attempt_recovery(self):
        return (
            datetime.now() - self.last_failure_time 
            >= timedelta(seconds=self.recovery_timeout)
        )

# Usage
class SafeAgent:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.circuit_breaker = CircuitBreaker()
    
    def execute(self, data):
        return self.circuit_breaker.execute(self.agent.execute, data)
```

---

## 6. State Management in MultiAgent Systems

### Centralized State

Single source of truth for all agents.

```python
class CentralizedState:
    def __init__(self):
        self.state = {}
        self.version = 0
    
    def get(self, path: str):
        """Get value at path (e.g., "research.findings")"""
        parts = path.split(".")
        value = self.state
        for part in parts:
            value = value.get(part, {})
        return value
    
    def set(self, path: str, value):
        """Set value at path, increment version"""
        parts = path.split(".")
        current = self.state
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
        self.version += 1
    
    def get_snapshot(self):
        """Get entire state snapshot"""
        return {
            "data": self.state.copy(),
            "version": self.version
        }

# Usage
state = CentralizedState()

# Agents read and write
state.set("research.findings", ["finding1", "finding2"])
findings = state.get("research.findings")
```

### Distributed State with Merging

Agents maintain local state, merge results.

```python
class DistributedState:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.local_state = {}
    
    def merge(self, other_state: dict):
        """Merge another agent's state"""
        # Merge strategy: deeper dicts, replace primitives
        for key, value in other_state.items():
            if key not in self.local_state:
                self.local_state[key] = value
            elif isinstance(value, dict) and isinstance(self.local_state[key], dict):
                self.local_state[key].update(value)
            else:
                # Conflict resolution: keep local if version newer
                pass

class Agent:
    def __init__(self, name: str):
        self.state = DistributedState(name)
    
    def step(self, global_state: dict):
        # Use global state
        self.state.merge(global_state)
        
        # Do work
        results = self._compute(self.state.local_state)
        
        # Return updated state
        return results
```

---

## 7. Best Practices for MultiAgent Orchestration

### 1. Clear Role Definition

Each agent should have a well-defined purpose.

```python
class Agent:
    """
    ROLE: Research Specialist
    
    RESPONSIBILITIES:
    - Search for relevant information
    - Validate source credibility
    - Extract key findings
    
    INPUTS: Query string, search parameters
    OUTPUTS: Structured findings with sources
    
    CONSTRAINTS:
    - Only return peer-reviewed sources
    - Max 10 minutes execution time
    - Limit to 5 sources per query
    """
    
    def __init__(self):
        self.role = "Research Specialist"
        self.max_sources = 5
        self.timeout_seconds = 600
```

### 2. Explicit Handoffs

Make it clear what data flows between agents.

```python
class HandoffContract:
    """Define what one agent passes to the next"""
    
    # From ResearchAgent to AnalysisAgent
    research_to_analysis = {
        "required": ["findings", "sources"],
        "optional": ["confidence_scores"],
        "schema": {
            "findings": List[str],
            "sources": List[Dict],
            "confidence_scores": Optional[List[float]]
        }
    }

# Validate handoff
def validate_handoff(data, contract):
    for required_key in contract["required"]:
        assert required_key in data, f"Missing required key: {required_key}"
```

### 3. Monitoring & Observability

Track what each agent does.

```python
import json
from datetime import datetime

class AgentMonitor:
    def __init__(self):
        self.logs = []
    
    def log_execution(
        self,
        agent_name: str,
        input_data: dict,
        output_data: dict,
        duration_seconds: float,
        status: str = "success",
        error: str = None
    ):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "status": status,
            "duration_seconds": duration_seconds,
            "input_size": len(json.dumps(input_data)),
            "output_size": len(json.dumps(output_data)),
            "error": error
        }
        self.logs.append(log_entry)
    
    def get_summary(self):
        """Get execution summary"""
        by_agent = {}
        for log in self.logs:
            agent = log["agent"]
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(log)
        
        summary = {}
        for agent, logs in by_agent.items():
            summary[agent] = {
                "total_executions": len(logs),
                "avg_duration": sum(l["duration_seconds"] for l in logs) / len(logs),
                "success_rate": sum(1 for l in logs if l["status"] == "success") / len(logs)
            }
        
        return summary

# Usage
monitor = AgentMonitor()

for agent in agents:
    start = time.time()
    try:
        result = agent.execute(data)
        monitor.log_execution(
            agent.name,
            data,
            result,
            time.time() - start
        )
    except Exception as e:
        monitor.log_execution(
            agent.name,
            data,
            {},
            time.time() - start,
            status="error",
            error=str(e)
        )
```

### 4. Context Threading

Pass context through the entire orchestration.

```python
import uuid

class ExecutionContext:
    def __init__(self, request_id: str = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.trace = []
        self.metadata = {}
    
    def add_step(self, agent_name: str, action: str, details: dict):
        """Log a step in execution"""
        self.trace.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "action": action,
            "details": details
        })
    
    def get_trace(self):
        """Get full execution trace"""
        return {
            "request_id": self.request_id,
            "trace": self.trace,
            "total_steps": len(self.trace)
        }

class ContextAwareAgent:
    def execute(self, data: dict, context: ExecutionContext):
        context.add_step(self.name, "started", {"input_keys": list(data.keys())})
        
        # Do work
        result = self._do_work(data)
        
        context.add_step(self.name, "completed", {"output_keys": list(result.keys())})
        
        return result

# Usage
context = ExecutionContext()

for agent in agents:
    result = agent.execute(data, context)
    data.update(result)

print(json.dumps(context.get_trace(), indent=2))
```

### 5. Version Control for Prompts

Track prompt versions used in agents.

```python
class VersionedAgent:
    def __init__(self, name: str, prompt_version: str, model_version: str):
        self.name = name
        self.prompt_version = prompt_version
        self.model_version = model_version
        self.executed_with = {
            "prompt_version": prompt_version,
            "model_version": model_version,
            "execution_timestamp": None
        }
    
    def execute(self, data):
        self.executed_with["execution_timestamp"] = datetime.now().isoformat()
        
        result = self._do_execute(data)
        result["_metadata"] = {
            "agent": self.name,
            "prompt_version": self.prompt_version,
            "model_version": self.model_version
        }
        
        return result
```

---

## 8. Implementation Guide for Your Project

### Recommended Architecture for `lca-reliable-agents`

Based on your project structure, here's a recommended implementation:

```
python/
├── prompts/
│   ├── system/
│   │   ├── agent_base.yaml
│   │   └── safety_constraints.yaml
│   ├── tasks/
│   │   ├── research.yaml
│   │   ├── analyze.yaml
│   │   └── synthesize.yaml
│   └── evaluations/
│       ├── quality.yaml
│       └── reliability.yaml
├── src/
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── research_agent.py
│   │   ├── analysis_agent.py
│   │   ├── orchestrator.py
│   │   └── monitoring.py
│   ├── orchestration/
│   │   ├── sequential.py
│   │   ├── parallel.py
│   │   ├── hierarchical.py
│   │   └── patterns.py
│   └── core/
│       ├── prompt_manager.py
│       ├── state_manager.py
│       └── execution_context.py
└── tests/
    ├── test_agents.py
    ├── test_orchestration.py
    └── fixtures/
```

### Complete Agent Implementation Example

```python
# src/agents/base_agent.py

import time
import json
from typing import Any, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ObjAssertion:
    prompt_key: str
    input_data: Dict[str, Any]
    expected_output_keys: list

class BaseAgent:
    """Base class for all agents"""
    
    def __init__(
        self,
        name: str,
        role: str,
        prompt_manager,
        llm_client,
        model: str = "claude-3-5-sonnet-20241022"
    ):
        self.name = name
        self.role = role
        self.prompt_manager = prompt_manager
        self.llm_client = llm_client
        self.model = model
        self.execution_history = []
    
    def execute(self, input_data: Dict, context=None) -> Dict:
        """Execute agent task"""
        start_time = time.time()
        
        try:
            # Log execution start
            if context:
                context.add_step(self.name, "started", {"input_keys": list(input_data.keys())})
            
            # Get prompts
            prompt = self._get_prompt(input_data)
            
            # Call LLM
            response = self.llm_client.messages.create(
                model=self.model,
                system=prompt["system"],
                user=prompt["user"],
                max_tokens=4096
            )
            
            # Parse response
            result = self._parse_response(response, input_data)
            
            # Log execution end
            execution_time = time.time() - start_time
            if context:
                context.add_step(
                    self.name,
                    "completed",
                    {
                        "output_keys": list(result.keys()),
                        "duration_seconds": execution_time
                    }
                )
            
            # Track execution
            self._log_execution(input_data, result, execution_time, "success")
            
            return result
        
        except Exception as e:
            execution_time = time.time() - start_time
            self._log_execution(input_data, {}, execution_time, "error", str(e))
            if context:
                context.add_step(self.name, "failed", {"error": str(e)})
            raise
    
    def _get_prompt(self, input_data: Dict) -> Dict:
        """Get formatted prompt for this agent"""
        prompt_key = f"agents/{self.role}.yaml"
        return self.prompt_manager.format_prompt(prompt_key, **input_data)
    
    def _parse_response(self, response, input_data) -> Dict:
        """Parse LLM response into structured output"""
        content = response.content[0].text
        
        try:
            # Try to parse as JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # Return as is if not JSON
            return {"result": content}
    
    def _log_execution(self, input_data, output_data, duration, status, error=None):
        """Log execution for monitoring"""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "input_size": len(json.dumps(input_data)),
            "output_size": len(json.dumps(output_data)),
            "duration_seconds": duration,
            "error": error
        })
    
    def get_stats(self):
        """Get agent performance statistics"""
        if not self.execution_history:
            return {}
        
        successes = [h for h in self.execution_history if h["status"] == "success"]
        
        return {
            "total_executions": len(self.execution_history),
            "successes": len(successes),
            "success_rate": len(successes) / len(self.execution_history) if self.execution_history else 0,
            "avg_duration": sum(h["duration_seconds"] for h in successes) / len(successes) if successes else 0,
            "avg_output_size": sum(h["output_size"] for h in successes) / len(successes) if successes else 0
        }
```

### Orchestrator Implementation

```python
# src/orchestration/orchestrator.py

import asyncio
from typing import List, Dict

class MultiAgentOrchestrator:
    """Orchestrate multiple agents in a workflow"""
    
    def __init__(self, agents: List[BaseAgent], name: str = "Orchestrator"):
        self.agents = {agent.name: agent for agent in agents}
        self.name = name
        self.execution_history = []
    
    def execute_sequential(self, input_data: Dict, context=None) -> Dict:
        """Execute agents in sequence"""
        data = input_data.copy()
        
        for agent in self.agents.values():
            data = agent.execute(data, context)
        
        return data
    
    async def execute_parallel(self, input_data: Dict, context=None) -> Dict:
        """Execute agents in parallel"""
        tasks = [
            asyncio.to_thread(agent.execute, input_data, context)
            for agent in self.agents.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge results
        merged = input_data.copy()
        for agent, result in zip(self.agents.values(), results):
            if isinstance(result, Exception):
                print(f"❌ {agent.name} failed: {result}")
            else:
                merged.update(result)
        
        return merged
    
    def execute_with_routing(self, input_data: Dict, router_agent, context=None) -> Dict:
        """Execute based on router agent's decision"""
        routing_decision = router_agent.execute(input_data, context)
        
        results = {}
        for agent_name in routing_decision.get("selected_agents", []):
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                results[agent_name] = agent.execute(input_data, context)
        
        return {
            "routing_decision": routing_decision,
            "results": results
        }
```

---

## Conclusion

MultiAgent Orchestration is a powerful pattern for building sophisticated AI systems that can tackle complex, multi-faceted problems. The key is:

1. **Clear Roles**: Each agent should have a well-defined purpose
2. **Explicit Handoffs**: Make data flow visible and validated
3. **Error Handling**: Build in resilience and fallbacks
4. **Monitoring**: Track what happens for debugging and optimization
5. **Flexibility**: Choose patterns that match your problem domain

Start simple with sequential orchestration, then evolve to more sophisticated patterns as your needs grow.

For your `lca-reliable-agents` project, I recommend:
- Start with **sequential pipeline pattern** for foundational lessons
- Use **hierarchical orchestration** for advanced modules
- Implement **feedback loops** for evaluation and refinement
- Track everything with comprehensive **logging and monitoring**

---

**This guide covers the complete landscape of prompts and multiagent orchestration. Save it, reference it, and extend it as you build your reliable agent systems.**
