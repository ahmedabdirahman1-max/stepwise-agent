"""The agent loop: plan -> execute -> synthesize -> verify.

Returns a fully transparent envelope: the plan, the per-step trace, the final
answer, and whether it's trustworthy (`ok`). The answer is built only from the
step results, so it can't claim something a tool didn't actually return.
"""
from __future__ import annotations
from typing import Any, Dict, List

from . import planner, executor
from .config import ANTHROPIC_API_KEY, MAX_STEPS

SAMPLE_REQUESTS = [
    "Who is our top customer?",
    "What were total sales, and what's our return policy?",
    "What's our best-selling product and how many orders do we have?",
    "If a customer returns a $200 order, what's the 15% restocking fee? (15% of 200)",
    "What's the warranty, and is shipping free?",
]


def _clause(entry: Dict[str, Any]) -> str:
    r = entry["result"]
    if entry["tool"] == "query_orders":
        return r["detail"]
    if entry["tool"] == "lookup_policy":
        return f"{r['text']} ({r['source']})"
    if entry["tool"] == "calculator":
        return f"{r['expression']} = {r['value']}"
    return str(r)


def synthesize(trace: List[Dict[str, Any]]) -> str:
    parts = [_clause(t) for t in trace if t.get("ok")]
    answer = " ".join(parts) if parts else "I couldn't complete that with my tools."
    failures = [t for t in trace if not t.get("ok")]
    if failures and parts:
        answer += f"  (Note: {len(failures)} step(s) could not complete.)"
    return answer


def verify(trace: List[Dict[str, Any]]) -> bool:
    return any(t.get("ok") for t in trace)


def run_agent(request: str) -> Dict[str, Any]:
    mode = "llm" if ANTHROPIC_API_KEY else "rules"
    plan = planner.plan(request)

    if not plan:
        return {
            "request": request,
            "mode": mode,
            "plan": [],
            "trace": [],
            "answer": ("I couldn't map that to my tools. Try asking about the orders data "
                       "(top customer, total sales, best product), a policy (returns, shipping, "
                       "warranty), or a calculation."),
            "ok": False,
            "max_steps": MAX_STEPS,
        }

    trace = executor.run(plan)
    return {
        "request": request,
        "mode": mode,
        "plan": plan,
        "trace": trace,
        "answer": synthesize(trace),
        "ok": verify(trace),
        "max_steps": MAX_STEPS,
    }
