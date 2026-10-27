# Fraud Investigation Agent

An agentic AI workflow that helps bank fraud analysts review suspicious accounts. Built with LangGraph, it gathers evidence through controlled tools, scores risk, retrieves the right internal policy with retrieval augmented generation (RAG), applies guardrails the model cannot override, and sends high risk cases to a human reviewer with a clear, traceable case summary.

This is a public, simplified version of the kind of system I work on in banking. All data is synthetic.

## Why this project

Fraud analysts spend a lot of time pulling the same evidence from different systems and checking it against policy. This agent does that groundwork in seconds and leaves the final call to a person for anything risky.

## How it works

```
START
  -> gather_evidence   (read only SQL tools: account profile, last 24 hours of activity)
  -> score             (explainable risk model: velocity, geo mismatch, account takeover, structuring)
  -> retrieve_policy   (RAG over policy documents)
  -> decide            (close, monitor, or escalate)
  -> guardrails        (hard business rules, e.g. structuring is always escalated)
  -> human_review      (only when needed)
  -> summarize         (LLM case summary grounded in the evidence, with policy citations)
END
```

Every run returns a structured `CaseReport` (validated with Pydantic) including the full execution trace, so an auditor can see exactly which steps ran.

## Key features

* Stateful agent workflow in LangGraph with conditional routing
* Controlled SQL tool: read only connection, single SELECT only, table allow list
* Retrieval over policy documents (TF IDF here, easy to swap for embeddings with FAISS or Pinecone)
* Guardrails and human in the loop escalation for high risk patterns
* Works fully offline; set `OPENAI_API_KEY` to use an LLM for the case summary
* FastAPI service, Docker image, pytest suite, and GitHub Actions CI

## Quick start

```bash
pip install -r requirements.txt
python data.py                      # builds the synthetic SQLite database
python graph.py                     # investigates all demo accounts
uvicorn api:app --reload
curl -X POST localhost:8000/investigate/A500
pytest -q
```

## Project files

| File | Purpose |
|---|---|
| graph.py | LangGraph workflow, state, guardrails, and routing |
| tools.py | Read only SQL tools, risk scoring, and policy retrieval |
| llm.py | Case summary writer (OpenAI or offline) |
| data.py | Builds the synthetic bank database |
| api.py | FastAPI service |
| *.md policies | high_velocity, geo_mismatch, large_transfer, structuring |
| test_agent.py | pytest suite |

## Demo accounts

| Account | Pattern | Expected outcome |
|---|---|---|
| A100 | Normal activity | close |
| A200 | High velocity card use | monitor or escalate |
| A300 | Transactions from two countries within an hour | escalate |
| A400 | Large wire to a new payee right after a profile change | escalate to human |
| A500 | Repeated cash deposits just under 10000 dollars | always escalate to human |

## Tech stack

Python, LangGraph, Pydantic, scikit learn, SQLite, FastAPI, OpenAI API (optional), Docker, pytest, GitHub Actions

## Next steps

* Replace TF IDF with sentence embeddings and a vector store
* Add an MCP server so the tools can be shared with other agents
* Add LangSmith tracing and an evaluation set of labeled cases
