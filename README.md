# CK Agent — Agentic Conversational System

A customer-support agent for a US e-commerce company. It does two things:

1. **Answers questions from internal documents** (RAG, with page citations, and it
   refuses when the document does not cover the question).
2. **Checks order shipment status** — but only after verifying the customer, and it
   discloses nothing before verification completes.

> Built as a take-home assignment for a Solution Engineer Intern role.

---

## Design principle

> **Every security decision is deterministic code; the model only phrases things.**
> The "no order data before verification" rule lives in the **tool layer**, not in the
> system prompt — a prompt is text, and text is something the user can influence.

A prompt-injected model can be talked into saying the wrong thing. It cannot be
talked into *retrieving* data it was never allowed to reach.

---

## Layout

```
app/          Runtime: FastAPI + SSE, agent loop, router, verification, tools
  tools/      search_knowledge_base · submit_verification · list_orders · get_order_status
  prompts/    system prompt
  static/     chat UI (plain HTML, no build step)
ingestion/    PDF -> clean -> extract tables -> chunk -> embed -> index
eval/         Golden set and runner: hit@3, groundedness, refusal accuracy
infra/
  bootstrap/  S3 backend for Terraform state (applied once)
  terraform/  ECR, Lambda + Function URL, DynamoDB, IAM, CloudWatch
tests/        pytest — focused on the verification parsers
data/         Mock customer and order data (fabricated, not real people)
docs/         Solution write-up, ADRs, data model, observability notes
scripts/      Utilities (Bedrock smoke test, ...)
```

## Status

| Level | Scope | Status |
|---|---|---|
| 100 | RAG + tool workflow + multi-turn conversation | 🟡 in progress |
| 200 | AWS deployment via Terraform, streaming, CI/CD | ⬜ not started |
| 300 | Conversation data model, observability, evaluation, preprocessing | ⬜ not started |

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # set AWS_REGION, model ids, table names
python -m ingestion.build --version v1
uvicorn app.api:app --reload    # http://127.0.0.1:8000
```

**Dataset:** the source PDF ships with the assignment and is not committed to this
repository. Place it at `data/raw/` before running `ingestion.build`.

## Model access notes (Amazon Bedrock)

- Claude 4.5 and newer require a **cross-region inference profile**: use
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`, not the bare `anthropic.*` id.
- Anthropic models need the **use case details form** submitted once per account
  (Bedrock console → Model access) before any invocation succeeds.
- Legacy Claude 3.x models are unavailable to accounts that have not used them
  recently — `us.amazon.nova-lite-v1:0` is the fallback that has no such condition.
