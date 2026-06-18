# Agent Flight Recorder

> A black-box recorder for AI agents: trace what happened, evaluate what broke, and make agent behavior easier to debug, audit, and improve.

**Agent Flight Recorder** is an in-progress AI agent observability project. It captures structured execution traces from agent runs, including LLM calls, tool calls, tool results, failures, costs, and run metadata. The goal is to make autonomous agent behavior inspectable instead of treating it like an opaque chat transcript.

This is not another chatbot. It is infrastructure for understanding, debugging, and eventually evaluating AI agents.

---

## Current status

**Project phase:** Milestone 1 — real agent instrumentation  
**Completed:** M1.2 — tracer maps a real Claude Agent SDK message stream into structured run/span JSON  
**Next:** M1.3 — POST assembled runs to the AFR `/runs` API so real traces land in storage

### What works right now

- FastAPI ingestion API foundation
- Pydantic schemas for runs and spans
- SQLAlchemy storage layer
- SQLite development database
- Run/span data model
- Real Claude Agent SDK subject agent
- Stream-to-trace conversion in `afr/tracer.py`
- Tool-call/tool-result correlation using `tool_use_id`
- Run finalization from SDK `ResultMessage`

### What is still in progress

- Posting traced runs into the `/runs` API automatically
- CI with GitHub Actions
- MCP tracing and MCP server exposure
- RAG evaluation
- Trace embeddings and semantic failure search
- LLM-as-judge evaluation
- Dashboard
- Docker, Kubernetes, and AWS deployment

---

## Why this exists

AI agents are becoming more powerful, but their behavior is still hard to inspect.

When an agent fails, the important questions are usually buried inside a messy sequence of model outputs, tool calls, retries, retrieved documents, and hidden intermediate decisions:

- What did the agent try to do?
- Which tool did it call?
- What did the tool return?
- Where did the failure happen?
- Was the answer grounded in retrieved context?
- How much did the run cost?
- Can this failure be searched, reproduced, or audited later?

Agent Flight Recorder is designed to answer those questions by turning agent execution into structured traces.

---

## Core idea

A run is modeled as a tree of spans.

```text
Run
├── LLM call span
│   ├── Tool call span
│   └── Tool call span
├── LLM call span
│   └── Tool call span
└── Final result
```

### Run

A **run** represents one end-to-end agent execution.

Example fields:

- `id`
- `agent_name`
- `status`
- `started_at`
- `ended_at`
- `input`
- `output`
- `metadata`
- `spans[]`

Runs begin as `running` and are finalized as `success` or `error` when the agent completes.

### Span

A **span** represents one step inside a run.

Supported span types include:

- `llm_call`
- `tool_call`
- `retrieval`
- `guardrail`
- `other`

Spans support parent-child relationships through `parent_span_id`, allowing AFR to represent an agent run as a trace tree instead of a flat log.

---

## How tracing works

The current tracer is built around the Claude Agent SDK message stream.

During M1.1 and M1.2, the project verified that SDK messages map naturally into AFR traces:

| SDK message/block | AFR behavior |
|---|---|
| `SystemMessage(init)` | Captures run metadata such as model and session ID |
| `AssistantMessage` | Creates an `llm_call` span |
| `ToolUseBlock` | Creates a child `tool_call` span |
| `UserMessage` with `ToolResultBlock` | Closes the matching tool span using `tool_use_id` |
| `ResultMessage` | Finalizes the run with status, cost, duration, and turn count |

One important issue discovered during instrumentation: tool calls and tool results arrive in separate messages. AFR handles this by keeping pending tool spans in memory until the matching result arrives.

---

## Tech stack

| Layer | Tool |
|---|---|
| API | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite for development, PostgreSQL planned at M3 |
| Agent framework | Claude Agent SDK |
| Environment | python-dotenv |
| Future vector search | pgvector |
| Future cache/queue | Redis |
| Future deployment | Docker, Kubernetes, AWS |
| Future CI/CD | GitHub Actions |

---

## Repository structure

```text
afr/
├── __init__.py
├── api.py          # FastAPI routes and API/storage translation
├── db.py           # SQLAlchemy models and database setup
├── schemas.py      # Pydantic API schemas
└── tracer.py       # Agent SDK stream-to-run tracing logic

examples/
└── subject_agent.py # Real instrumented subject agent

README.md
requirements.txt
.gitignore
.env               # Local only, not committed
```

---

## Local setup

Clone the repo:

```bash
git clone https://github.com/joshuamendozaa/agent-flight-recorder.git
cd agent-flight-recorder
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file:

```bash
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///./afr.db
```

Run the API:

```bash
uvicorn afr.api:app --reload
```

Once M1.3 is complete, the traced subject agent will POST real runs into the API.

---

## Example trace shape

```json
{
  "agent_name": "subject_agent",
  "status": "success",
  "input": "Investigate the repo and summarize what changed.",
  "output": "Summary of agent result...",
  "run_metadata": {
    "model": "claude-sonnet",
    "session_id": "example-session"
  },
  "spans": [
    {
      "type": "llm_call",
      "name": "assistant_turn",
      "attributes": {
        "model": "claude-sonnet"
      },
      "children": [
        {
          "type": "tool_call",
          "name": "Bash",
          "attributes": {
            "tool_name": "Bash",
            "input": "ls -la",
            "output": "..."
          }
        }
      ]
    }
  ]
}
```

---

## Roadmap

### M0 — Trace model, ingestion API, and storage

Status: complete

- Run and span schemas
- FastAPI ingestion route
- SQLAlchemy persistence
- SQLite development storage

### M1 — Real agent instrumentation

Status: in progress

- M1.1: Build and observe a real subject agent
- M1.2: Convert SDK message stream into structured run/span JSON
- M1.3: POST completed traces to `/runs`
- Next: Add basic GitHub Actions workflow for linting and tests

### M2 — MCP support

Planned:

- Trace agents that use MCP tools
- Expose AFR traces through an MCP server

### M3 — RAG and vector search

Planned:

- Add a RAG subject agent
- Switch development database path toward PostgreSQL
- Add pgvector
- Embed traces for semantic failure search

### M4 — Evaluation layer

Planned:

- Faithfulness scoring
- Retrieval quality checks
- Guardrail detection
- LLM-as-judge evaluation

### M5 — Analyst agent

Planned:

- Build an agent that investigates failing traces
- Search prior failures
- Suggest likely root causes

### M6 — Deployment

Planned:

- Dashboard
- Docker Compose
- Kubernetes deployment target
- AWS deployment
- Cloud secret management
- CI/CD expansion

---

## Design decisions

- Runs and spans are represented separately.
- Spans form a tree through `parent_span_id`.
- Span types use lowercase snake_case values as the wire/API contract.
- Flexible span-specific data lives in an `attributes` object.
- Pydantic models define the API contract.
- SQLAlchemy models define the storage layer.
- SQLAlchemy reserved names are avoided, so API `metadata` maps to storage `run_metadata`.
- Database portability is handled through `DATABASE_URL`.
- SQLite is used for development, with PostgreSQL planned before vector search.

---

## Long-term vision

The long-term goal is to make AFR useful for more than debugging.

Future versions should support:

- Agent reliability analysis
- Failure clustering
- RAG faithfulness evaluation
- Compliance and audit evidence
- Human oversight records
- Searchable trace history
- Framework-agnostic agent instrumentation

The bigger idea: teams should not just ship agents. They should be able to prove what their agents did, why they did it, and where they failed.

---

## Author

Built by [Joshua Mendoza](https://github.com/joshuamendozaa) as a production-style AI engineering project focused on agent observability, evaluation, and deployment.
