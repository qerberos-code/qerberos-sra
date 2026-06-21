import os

MODEL = os.getenv("MODEL", "claude-opus-4-8")
MANAGER_MODEL = os.getenv("MANAGER_MODEL", MODEL)
SUBAGENT_MODEL = os.getenv("SUBAGENT_MODEL", MODEL)

MAX_TOKENS = 8192
MANAGER_MAX_TOKENS = 16384
SUBAGENT_MAX_TOKENS = 8192

MAX_ITERATIONS = 60
SUBAGENT_MAX_ITERATIONS = 30

EXCLUDED_DIRS = [
    ".venv", "venv", "node_modules", "dist", "build",
    ".git", "vendor", "site-packages",
]
