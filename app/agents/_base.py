import anthropic

from .. import config
from ..agent import run_agent, _parse_json_response
from ..tools import make_tool_registry


class BaseAgent:
    SYSTEM_PROMPT: str = ""
    TOOLS: tuple = ("Read", "Bash")

    def run(self, client: anthropic.Anthropic, repo_path: str) -> dict:
        tools = make_tool_registry(*self.TOOLS)
        task = f"Scan the repository at: {repo_path}"
        raw = run_agent(
            client=client,
            system_prompt=self.SYSTEM_PROMPT,
            initial_message=task,
            tools=tools,
            model=config.SUBAGENT_MODEL,
            max_tokens=config.SUBAGENT_MAX_TOKENS,
            max_iterations=config.SUBAGENT_MAX_ITERATIONS,
        )
        return _parse_json_response(raw)
