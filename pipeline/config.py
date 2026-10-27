import os

# Claude Sonnet 5.5 for every Claude call (extract, write, ClaudeBackend decisions).
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

# Effort per node. Sonnet 5.5 defaults to "high"; start at "medium" and tune with eval.
EFFORT = {
    "extract": os.environ.get("EFFORT_EXTRACT", "medium"),
    "decision": os.environ.get("EFFORT_DECISION", "medium"),
    "write": os.environ.get("EFFORT_WRITE", "medium"),
}

# "adaptive" (default) or "between_tools" (no up-front thinking; only at low/medium/high effort).
THINKING = os.environ.get("CLAUDE_THINKING", "adaptive")

# DecisionModel backend: "claude" or "jev" (needs TYPESAFE_API_KEY).
DECISION_BACKEND = os.environ.get("DECISION_BACKEND", "jev" if os.environ.get("TYPESAFE_API_KEY") else "claude")
JEV_MODEL = os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
JEV_TIMEOUT = float(os.environ.get("JEV_TIMEOUT", "60"))

LOW_CONFIDENCE = float(os.environ.get("LOW_CONFIDENCE", "0.6"))
MAX_TOKENS = 16000
