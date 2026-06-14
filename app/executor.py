"""Execute a plan against the governed tool registry.

This is where the guardrails bite:
  * a step naming a tool outside the registry is BLOCKED, not run
  * no more than MAX_STEPS steps execute, ever (runaway protection)
  * each tool call is wrapped, so one failing step doesn't crash the run
Every step produces a trace entry, so the whole run is auditable.
"""
from __future__ import annotations
from typing import Any, Dict, List

from .config import MAX_STEPS
from .tools import TOOLS

Step = Dict[str, Any]
TraceEntry = Dict[str, Any]


def run(plan: List[Step]) -> List[TraceEntry]:
    trace: List[TraceEntry] = []
    for i, step in enumerate(plan):
        if i >= MAX_STEPS:
            trace.append({"tool": step.get("tool"), "args": step.get("args", {}),
                          "ok": False, "error": f"step limit reached (MAX_STEPS={MAX_STEPS})"})
            break

        tool = step.get("tool")
        args = step.get("args", {}) or {}

        if tool not in TOOLS:
            trace.append({"tool": tool, "args": args, "ok": False,
                          "error": "blocked: tool not in allowlist"})
            continue

        spec = TOOLS[tool]
        value = args.get(spec["arg"])
        if value is None and len(args) == 1:
            value = next(iter(args.values()))

        try:
            result = spec["fn"](value)
            trace.append({"tool": tool, "args": args, "ok": True, "result": result})
        except Exception as e:
            trace.append({"tool": tool, "args": args, "ok": False, "error": str(e)})

    return trace
