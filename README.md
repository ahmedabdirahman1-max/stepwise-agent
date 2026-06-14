# StepWise — a governed planner/executor agent

An AI agent that answers multi-step requests by **planning** a sequence of tool
calls, **executing** them through a bounded, allow-listed tool set, and returning
a **fully auditable trace** — the plan, every step, and whether the result is
trustworthy. It's an agent you can actually reason about, not a black box.

> Python · FastAPI · framework-free agent loop · Claude-optional planning ·
> tool allowlist + step cap + safe calculator · eval tests.

---

## Why "governed"

Most agent demos hand the model a pile of tools and hope. The failure modes are
predictable: it invents a tool that doesn't exist, loops forever, or asserts an
answer no tool actually produced. StepWise closes each of those off:

- **Allowlisted tools.** The planner may only choose from the registry; the
  executor *blocks* anything else ([`app/executor.py`](app/executor.py)). The
  agent can't shell out, hit the network, or call a made-up tool.
- **Hard step cap.** Execution stops after `MAX_STEPS` — no runaway loops.
- **Grounded answers.** The final answer is assembled only from the step
  results ([`app/agent.py`](app/agent.py)); it can't claim something a tool
  didn't return, and it reports failed steps honestly.
- **A safe calculator.** Arithmetic is evaluated with an AST whitelist, never
  `eval` ([`app/tools.py`](app/tools.py)).
- **Full trace.** Every run returns its plan and per-step results, so you can
  audit exactly what happened.

The loop is **framework-free on purpose** — so the orchestration is explicit and
reviewable. It maps directly onto LangGraph (each stage = a node) if you want the
framework; the guardrails are the part that matters.

## What it orchestrates

The tools deliberately mirror the rest of this portfolio, so the agent's job is
*composition*:

| Tool | Does |
|------|------|
| `query_orders(metric)` | structured-data query (top customer, total sales, best product…) |
| `lookup_policy(topic)` | grounded policy lookup (returns / shipping / warranty) |
| `calculator(expression)` | safe arithmetic, e.g. `15% of 200` |

So *"What were total sales, and what's our return policy?"* becomes a two-step
plan — one data call, one policy lookup — and the answer cites both.

## Run it

Requires Python 3.10+.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

Ask a question or click a sample. Set `ANTHROPIC_API_KEY` in `.env` to let Claude
do the planning; without it, a deterministic rule-based planner runs (no key, no
network).

## Tests

```bash
python -m unittest discover -s tests -v
```

The guardrail tests prove the boundaries hold: a step naming a tool outside the
allowlist is **blocked**, the step cap is **enforced**, the calculator **refuses
code**, and an unmappable request is **declined** rather than answered with a
guess.

## Project layout

```
app/
  tools.py     governed tool registry (data, policy, safe calculator)
  planner.py   request -> ordered plan of tool calls (rules or Claude)
  executor.py  runs the plan: allowlist + step cap + per-step trace
  agent.py     orchestration + grounded synthesis + verification
  main.py      FastAPI app
static/        single-page UI (answer + full step trace)
tests/         tool, planner, guardrail, and end-to-end eval
```

---

*Demo project. The pattern — plan explicitly, execute through a narrow allow-listed
interface, cap the work, and keep the whole run auditable — is how I'd build an
agent that's safe to put in front of real systems.*
