import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from . import config
from .agent import run_agent
from .agents import (
    AICodeAgent, AIVBMAgent, ComplianceAgent,
    DependencyAgent, IaCAgent, SASTAgent, SecretsAgent,
)
from .prompts import MANAGER_PROMPT
from .tools import make_tool_registry

_ALL_AGENTS = [
    SecretsAgent,
    DependencyAgent,
    SASTAgent,
    IaCAgent,
    AICodeAgent,
    ComplianceAgent,
    AIVBMAgent,
]


def _run_subagents_parallel(
    client: anthropic.Anthropic,
    repo_path: str,
    max_workers: int = 4,
) -> dict[str, dict]:
    """Fire all sub-agents in parallel threads. Returns {AgentName: findings_dict}."""
    instances = [cls() for cls in _ALL_AGENTS]
    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(agent.run, client, repo_path): type(agent).__name__
            for agent in instances
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
                count = len(results[name].get("findings", []))
                print(f"  [{name}] done — {count} finding(s)", file=sys.stderr)
            except Exception as exc:
                results[name] = {"findings": [], "error": str(exc)}
                print(f"  [{name}] error: {exc}", file=sys.stderr)

    return results


class ReviewManager:
    def orchestrate(
        self,
        client: anthropic.Anthropic,
        repo_path: str,
        output_dir: str,
        subagent_results: dict[str, dict],
        extra_prompt: str | None = None,
    ) -> str:
        """Deduplicate, prioritize, and write the three Markdown reports."""
        combined = json.dumps(subagent_results, indent=2)
        task = (
            f"Sub-agent findings for repository at: {repo_path}\n\n"
            f"```json\n{combined}\n```\n\n"
            f"Write all reports to: {output_dir}\n"
        )
        if extra_prompt:
            task += f"\nAdditional instructions: {extra_prompt}\n"

        return run_agent(
            client=client,
            system_prompt=MANAGER_PROMPT,
            initial_message=task,
            tools=make_tool_registry("Read", "Write", "Bash"),
            model=config.MANAGER_MODEL,
            max_tokens=config.MANAGER_MAX_TOKENS,
            max_iterations=config.MAX_ITERATIONS,
        )
