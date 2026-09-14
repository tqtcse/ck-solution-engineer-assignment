# CK Agent

A customer-support agent for a US e-commerce company. It answers questions from an eighteen-page
extract of Amazon's FY2019 10-K, citing the page each claim came from, and reports order shipment
status only after verifying who is asking. The whole system runs on a container image on AWS
Lambda behind CloudFront, streams tokens to the browser as they are produced, and costs nothing
while idle.

Live: <https://d2ndqmawls4x5x.cloudfront.net/>

Built as a take-home assignment for a Solution Engineer Intern role at Cloud Kinetics.

## What it does

- Retrieval-augmented answers with a page citation on every factual claim, and an explicit
  refusal when the documents do not cover the question.
- Identity verification against three fields: a company email matching `@ck<number>`, the last
  four digits of a social security number, and a date of birth in any format, including natural
  language. An ambiguous date such as `05/01/1990` is queried back rather than guessed.
- Order lookup after verification. When a customer has several orders the agent lists the
  identifiers and asks which one, instead of choosing on their behalf.
- Streaming from Bedrock through Lambda to the browser, with no buffering hop in between.

## The decision worth knowing before reading the code

Access rules are enforced in the tool layer, never in the system prompt.
`_list_orders` checks the session flag before reading any record
([`app/tools/__init__.py:155`](app/tools/__init__.py#L155)), `_get_order_status` repeats that
check rather than trusting its caller ([`:166`](app/tools/__init__.py#L166)), and the record's
owner is compared against the verified customer before anything is returned
([`:174`](app/tools/__init__.py#L174)).

A prompt injection can change what the model says. It cannot change what the tool returns.

## Layout

```
app/
  api.py            FastAPI app, SSE endpoint, error boundary
  agent.py          ReAct loop over Bedrock Converse, streaming, step and search budgets
  router.py         Four-tier intent classification, three tiers cost nothing
  tools/            search_knowledge_base, submit_verification, list_orders, get_order_status
  verification.py   Email, SSN and date parsing, including ambiguous-date detection
  memory.py         DynamoDB conversation store, append-only writes
  session.py        Per-session verification state
  obs.py            Structured logs and EMF metrics, both written to stdout
  prompts/          System prompt
  static/           Chat UI, plain HTML with no build step
ingestion/          PDF to text to tables to chunks to embeddings to a compiled index
eval/               Golden set and agent-level scenarios, with their results
infra/
  bootstrap/        State bucket, OIDC provider, IAM roles. Applied by hand.
  *.tf              ECR, Lambda, CloudFront, DynamoDB, logs, alarms. Applied by CI.
tests/              pytest, 99 tests
data/               Committed index and chunks, plus fabricated customer and order records
scripts/            push.sh (build and push an image), observe.py (read metrics back)
```

## Prerequisites

- Python 3.12
- AWS credentials for an account with Amazon Bedrock available in `us-east-1`
- Model access granted in the Bedrock console for Claude Haiku 4.5, Nova Lite and
  Titan Text Embeddings V2

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.api:app --reload
```

Open <http://127.0.0.1:8000>. The compiled index and its chunks are committed, so there is no
build step before the first run.

Rebuild the index only after changing the source document. The 10-K PDF ships with the
assignment and is not committed here; place it under `data/raw/` first.

```bash
python -m ingestion.build --version v2
```

A terminal client is available if a browser is inconvenient:

```bash
python -m app.cli
```

## Configuration

Everything is read from the environment and every variable has a working default, so none are
required locally. Nothing loads a `.env` file; export the variables in the shell to override.

| Variable | Default | Purpose |
|---|---|---|
| `AWS_REGION` | `us-east-1` | Region for Bedrock and DynamoDB |
| `CHAT_MODEL` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Reasoning and generation |
| `ROUTER_MODEL` | `us.amazon.nova-lite-v1:0` | Intent classification, tier four only |
| `EMBED_MODEL` | `amazon.titan-embed-text-v2:0` | Query and chunk embeddings |
| `INDEX_VERSION` | `v1` | Which compiled index to load; deployment sets `v2` |
| `TOP_K` | `3` | Chunks returned per retrieval |
| `CONV_TABLE` | `ck-agent-dev-conversations` | DynamoDB table for conversation history |
| `HISTORY_TURNS` | `12` | Messages replayed into the model each turn |

## Tests

```bash
pytest -q                  # 99 tests
pytest -q -m "not aws"     # 95 tests, no AWS credentials needed
```

The second form is what continuous integration runs. Gating a merge therefore needs no cloud
access at all, which is also what makes it safe to run against a pull request from a fork.

## Evaluation

Two harnesses that measure different things.

```bash
python -m eval.run_eval --version v2                   # 38-question golden set
python -m eval.run_eval --version v2 --retrieval-only  # retrieval scores only, no model calls
python -m eval.run_agent_eval                          # 9 scenarios, 20 turns
python -m eval.run_agent_eval --repeat 3               # stability of each turn across runs
python -m eval.run_agent_eval --case a03               # one scenario
```

`run_eval` scores retrieval and answer generation against a fixed question set and writes
`eval/results_v2.json`. `run_agent_eval` drives `agent.run_turn` itself, so the router, the tool
loop, the real system prompt, conversation history and DynamoDB are all in the path; each
scenario is tied to a specific clause of the assignment brief. Written-up results are in
`eval/results.md` and `eval/results_agent.md`.

## Deployment

A push to `main` runs `.github/workflows/deploy.yml`: the test job first, then a container build
pushed to ECR tagged with the commit hash, then `terraform apply`, then a smoke test that sends a
signed request through CloudFront and fails the deploy if it does not return 200. The pipeline
authenticates through GitHub OIDC and holds no AWS access key.

Terraform is split into two roots with different owners. `infra/bootstrap/` creates the state
bucket, the OIDC provider and the IAM roles, and is applied by an administrator by hand. `infra/`
holds everything the pipeline is allowed to change, and its role has no permission to create or
modify IAM.

To deploy by hand:

```bash
TAG=$(scripts/push.sh)
cd infra && terraform apply -var="image_tag=$TAG"
```

## Operations

The application publishes no metrics through an API. It prints structured JSON to stdout, and
CloudWatch extracts the numbers from it using the embedded metric format, which is why the
function's execution role carries no `cloudwatch:PutMetricData` permission.

To read the metrics and reconstruct a conversation from the logs:

```bash
python scripts/observe.py --minutes 30
python scripts/observe.py --session <session-id>
```

Three alarms watch the results: Lambda errors, p95 duration, and a metric filter that counts
Bedrock throttling exceptions in the log text. The third exists because a throttled call that
the SDK retries successfully still returns 200, so the built-in error metric never sees it.

## Amazon Bedrock access notes

These cost time to discover, so they are recorded here.

- Claude 4.5 and newer require a cross-region inference profile. Use
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`, not the bare `anthropic.*` identifier.
- Anthropic models need the use case details form submitted once per account, in the Bedrock
  console under Model access, before any invocation succeeds.
- Legacy Claude 3.x models are unavailable to accounts that have not used them recently.
  `us.amazon.nova-lite-v1:0` has no such condition and is used for the routing tier.

## Data

The customer and order records under `data/` are fabricated. No real names, addresses, social
security numbers or dates of birth appear anywhere in this repository.
