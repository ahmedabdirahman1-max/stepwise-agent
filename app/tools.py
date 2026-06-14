"""The governed tool registry — the only capabilities the agent can use.

The planner may *only* select tools that appear here; the executor refuses
anything else. That allowlist is the safety boundary: the agent can't invent a
tool, shell out, or reach the network. Each tool validates its own input.

Two of the tools mirror the other demos in this portfolio — a structured-data
query (InsightSQL-style) and a grounded policy lookup (CiteRAG-style) — so the
agent's job is to *orchestrate* them, which is the point of an agent.
"""
from __future__ import annotations
import ast
import operator
import re
from typing import Any, Callable, Dict

# ---- tiny in-memory business dataset (the "data tool" operates on this) ----
_PRICES = {"Arabica Beans": 18.50, "Matcha Powder": 24.00, "Olive Oil": 12.75, "Oat Milk": 2.40}
# (customer, country, product, qty)
_ORDERS = [
    ("Acme Cafe", "USA", "Arabica Beans", 10),
    ("Acme Cafe", "USA", "Oat Milk", 40),
    ("Blue Harbor Hotel", "USA", "Olive Oil", 6),
    ("Sakura Foods", "Japan", "Matcha Powder", 15),
    ("Olive & Co", "Italy", "Olive Oil", 20),
    ("Blue Harbor Hotel", "USA", "Arabica Beans", 12),
    ("Sakura Foods", "Japan", "Matcha Powder", 9),
    ("Acme Cafe", "USA", "Olive Oil", 5),
]
_COUNTRY = {c: country for c, country, _p, _q in _ORDERS}


def _amount(product: str, qty: int) -> float:
    return round(_PRICES[product] * qty, 2)


def query_orders(metric: str) -> Dict[str, Any]:
    """Answer a question about the orders dataset. metric ∈
    {total_sales, order_count, top_customer, top_product}."""
    metric = (metric or "").strip().lower()
    if metric == "total_sales":
        total = round(sum(_amount(p, q) for _c, _co, p, q in _ORDERS), 2)
        return {"metric": metric, "value": total, "detail": f"${total:,.2f} across {len(_ORDERS)} orders"}
    if metric == "order_count":
        return {"metric": metric, "value": len(_ORDERS), "detail": f"{len(_ORDERS)} orders"}
    if metric == "top_customer":
        totals: Dict[str, float] = {}
        for c, _co, p, q in _ORDERS:
            totals[c] = totals.get(c, 0) + _amount(p, q)
        name = max(totals, key=totals.get)
        return {"metric": metric, "value": name,
                "detail": f"{name} ({_COUNTRY[name]}) — ${totals[name]:,.2f}"}
    if metric == "top_product":
        totals: Dict[str, float] = {}
        for _c, _co, p, q in _ORDERS:
            totals[p] = totals.get(p, 0) + _amount(p, q)
        name = max(totals, key=totals.get)
        return {"metric": metric, "value": name, "detail": f"{name} — ${totals[name]:,.2f}"}
    raise ValueError(f"unknown metric: {metric!r}")


# ---- grounded policy lookup (the "docs tool") ----
_POLICIES = {
    "returns": ("Returns", "Items may be returned within 30 days of delivery. Opened or "
                "non-defective returns carry a 15% restocking fee; clearance items are final."),
    "shipping": ("Shipping", "Free shipping on orders over $50; otherwise a flat $5.95. "
                 "Standard delivery is 3–5 business days."),
    "warranty": ("Warranty", "All products carry a 1-year limited warranty covering defects "
                 "in materials and workmanship under normal use."),
}
_POLICY_KEYWORDS = {
    "returns": ["return", "refund", "restock", "clearance"],
    "shipping": ["ship", "delivery", "deliver"],
    "warranty": ["warranty", "defect", "guarantee"],
}


def lookup_policy(topic: str) -> Dict[str, Any]:
    """Return the policy text for a topic ∈ {returns, shipping, warranty}."""
    topic = (topic or "").strip().lower()
    if topic not in _POLICIES:
        for key, words in _POLICY_KEYWORDS.items():       # be forgiving about phrasing
            if any(w in topic for w in words):
                topic = key
                break
    if topic not in _POLICIES:
        raise ValueError(f"no policy for topic: {topic!r}")
    title, text = _POLICIES[topic]
    return {"topic": topic, "title": title, "text": text, "source": f"Policy: {title}"}


# ---- safe calculator (no eval; ast whitelist only) ----
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> Dict[str, Any]:
    """Evaluate a pure-arithmetic expression safely (digits and + - * / % ** only)."""
    expr = (expression or "").strip()
    # Support "N% of M" phrasing.
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)\s*", expr, re.I)
    if m:
        expr = f"{m.group(2)} * {m.group(1)} / 100"
    if not re.fullmatch(r"[\d\s.+\-*/%()]+", expr):
        raise ValueError("expression contains disallowed characters")
    result = _eval(ast.parse(expr, mode="eval").body)
    return {"expression": expr, "value": round(result, 4)}


# ---- registry ----
TOOLS: Dict[str, Dict[str, Any]] = {
    "query_orders": {
        "fn": query_orders,
        "arg": "metric",
        "description": "Query the orders dataset. metric: total_sales | order_count | top_customer | top_product",
    },
    "lookup_policy": {
        "fn": lookup_policy,
        "arg": "topic",
        "description": "Look up a company policy. topic: returns | shipping | warranty",
    },
    "calculator": {
        "fn": calculator,
        "arg": "expression",
        "description": "Evaluate a pure arithmetic expression, e.g. '15% of 200' or '18.5 * 10'",
    },
}


def tool_catalog() -> str:
    return "\n".join(f"- {n}({m['arg']}): {m['description']}" for n, m in TOOLS.items())
