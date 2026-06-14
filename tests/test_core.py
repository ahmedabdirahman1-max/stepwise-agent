"""Tests for the agent: tools, planning, the executor guardrails, and end-to-end.

The guardrail tests matter most — they prove the agent can't run a tool outside
its allowlist and can't exceed the step cap.

Run from the project root:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tools, planner, executor          # noqa: E402
from app.agent import run_agent                    # noqa: E402
from app.config import MAX_STEPS                    # noqa: E402


class ToolTests(unittest.TestCase):
    def test_total_sales(self):
        self.assertEqual(tools.query_orders("total_sales")["value"], 1474.25)

    def test_top_customer_and_product(self):
        self.assertEqual(tools.query_orders("top_customer")["value"], "Sakura Foods")
        self.assertEqual(tools.query_orders("top_product")["value"], "Matcha Powder")

    def test_order_count(self):
        self.assertEqual(tools.query_orders("order_count")["value"], 8)

    def test_policy_lookup_forgiving(self):
        self.assertEqual(tools.lookup_policy("refunds please")["topic"], "returns")

    def test_calculator_percent(self):
        self.assertEqual(tools.calculator("15% of 200")["value"], 30)

    def test_calculator_rejects_code(self):
        with self.assertRaises(ValueError):
            tools.calculator("__import__('os').system('ls')")


class PlannerTests(unittest.TestCase):
    def test_single_step(self):
        steps = planner.plan_rules("Who is our top customer?")
        self.assertEqual(steps, [{"tool": "query_orders", "args": {"metric": "top_customer"}}])

    def test_multi_step(self):
        steps = planner.plan_rules("What were total sales, and what's our return policy?")
        names = [(s["tool"], s["args"]) for s in steps]
        self.assertIn(("query_orders", {"metric": "total_sales"}), names)
        self.assertIn(("lookup_policy", {"topic": "returns"}), names)

    def test_unmappable(self):
        self.assertEqual(planner.plan_rules("tell me a joke about pirates"), [])


class GuardrailTests(unittest.TestCase):
    def test_unknown_tool_is_blocked(self):
        trace = executor.run([{"tool": "shell", "args": {"cmd": "rm -rf /"}}])
        self.assertFalse(trace[0]["ok"])
        self.assertIn("allowlist", trace[0]["error"])

    def test_step_cap_enforced(self):
        plan = [{"tool": "calculator", "args": {"expression": "1+1"}} for _ in range(MAX_STEPS + 2)]
        trace = executor.run(plan)
        self.assertLessEqual(len(trace), MAX_STEPS + 1)
        self.assertTrue(any("step limit" in (t.get("error") or "") for t in trace))


class AgentTests(unittest.TestCase):
    def test_single_step_answer(self):
        res = run_agent("Who is our top customer?")
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["plan"]), 1)
        self.assertIn("Sakura", res["answer"])

    def test_multi_step_answer_is_grounded(self):
        res = run_agent("What were total sales, and what's our return policy?")
        self.assertTrue(res["ok"])
        self.assertEqual(len([t for t in res["trace"] if t["ok"]]), 2)
        self.assertIn("1,474", res["answer"])
        self.assertIn("30 days", res["answer"])

    def test_unmappable_request_refuses(self):
        res = run_agent("write me a poem")
        self.assertFalse(res["ok"])
        self.assertEqual(res["plan"], [])
        self.assertIn("couldn't map", res["answer"].lower())


if __name__ == "__main__":
    unittest.main()
