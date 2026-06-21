import json

import anthropic

from . import config
from .agent import run_agent
from .prompts import REMEDIATION_PROMPT
from .tools import make_tool_registry

_ACTIONABLE_SEVERITIES = {"CRITICAL", "HIGH"}


class RemediationAgent:
    def apply_fixes(
        self,
        client: anthropic.Anthropic,
        repo_path: str,
        findings: list[dict],
        db_path: str = "security-review/db.sqlite",
    ) -> str:
        """Apply fixes for CRITICAL/HIGH findings that have a patch_hint.

        Returns the agent's summary of PRs opened and findings skipped.
        """
        actionable = [
            f for f in findings
            if f.get("severity") in _ACTIONABLE_SEVERITIES and f.get("patch_hint")
        ]

        if not actionable:
            return "No CRITICAL/HIGH findings with patch hints — nothing to remediate."

        task = (
            f"Repository path: {repo_path}\n\n"
            f"Findings to remediate:\n```json\n{json.dumps(actionable, indent=2)}\n```\n"
        )

        return run_agent(
            client=client,
            system_prompt=REMEDIATION_PROMPT,
            initial_message=task,
            tools=make_tool_registry("Read", "Write", "Bash", "Git"),
            model=config.SUBAGENT_MODEL,
            max_tokens=config.SUBAGENT_MAX_TOKENS,
            max_iterations=config.SUBAGENT_MAX_ITERATIONS,
        )
