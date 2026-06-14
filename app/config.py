"""Runtime configuration, read from environment with safe defaults."""
from __future__ import annotations
import os

# If set, Claude plans the steps and phrases the answer. If empty, a deterministic
# rule-based planner is used, so the agent runs with no API key and no network.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-4-5-20251001").strip()

# The executor will never run more than this many steps — a hard stop against
# runaway plans / loops.
MAX_STEPS = int(os.environ.get("MAX_STEPS", "6"))
