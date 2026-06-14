"""Turn a request into an ordered plan of tool calls.

A plan is a list of steps: {"tool": <name>, "args": {<arg>: <value>}}. The
planner may only reference tools in the registry; anything else is dropped here
and would be blocked by the executor anyway.

Two modes, same output contract:
  * rule-based (default): deterministic keyword matching, no API key.
  * LLM (optional): Claude proposes the plan from the tool catalog.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List

from .config import ANTHROPIC_API_KEY, AGENT_MODEL
from .tools import TOOLS, tool_catalog

Step = Dict[str, Any]


def _calc_expr(request: str) -> str | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", request, re.I)
    if m:
        return m.group(0)
    m = re.search(r"\d+(?:\.\d+)?\s*[-+*/%]\s*\d+(?:\.\d+)?(?:\s*[-+*/%]\s*\d+(?:\.\d+)?)*", request)
    return m.group(0) if m else None


def plan_rules(request: str) -> List[Step]:
    q = request.lower()
    steps: List[Step] = []

    if any(k in q for k in ["top customer", "best customer", "biggest customer", "largest customer"]):
        steps.append({"tool": "query_orders", "args": {"metric": "top_customer"}})
    if any(k in q for k in ["top product", "best selling", "best-selling", "most sold", "bestseller"]):
        steps.append({"tool": "query_orders", "args": {"metric": "top_product"}})
    if any(k in q for k in ["total sales", "total revenue", "revenue", "sales total", "how much did we sell"]):
        steps.append({"tool": "query_orders", "args": {"metric": "total_sales"}})
    if any(k in q for k in ["how many orders", "order count", "number of orders"]):
        steps.append({"tool": "query_orders", "args": {"metric": "order_count"}})

    if any(k in q for k in ["return", "refund", "restock", "clearance"]):
        steps.append({"tool": "lookup_policy", "args": {"topic": "returns"}})
    if any(k in q for k in ["ship", "delivery", "deliver"]):
        steps.append({"tool": "lookup_policy", "args": {"topic": "shipping"}})
    if "warranty" in q or "defect" in q:
        steps.append({"tool": "lookup_policy", "args": {"topic": "warranty"}})

    expr = _calc_expr(request)
    if expr:
        steps.append({"tool": "calculator", "args": {"expression": expr}})

    return steps


_SYSTEM = (
    "You are a planner. Break the user's request into an ordered list of tool calls, "
    "using ONLY these tools:\n{catalog}\n\n"
    "Respond with ONLY a JSON array of steps, each {{\"tool\": <name>, \"args\": {{<arg>: <value>}}}}. "
    "Use no tool not listed. If nothing fits, return []."
)


def plan_llm(request: str) -> List[Step]:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=400,
            system=_SYSTEM.format(catalog=tool_catalog()),
            messages=[{"role": "user", "content": request}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        data = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
        steps = [s for s in data if isinstance(s, dict) and s.get("tool") in TOOLS]
        return steps
    except Exception:
        return plan_rules(request)


def plan(request: str) -> List[Step]:
    if ANTHROPIC_API_KEY:
        return plan_llm(request)
    return plan_rules(request)
