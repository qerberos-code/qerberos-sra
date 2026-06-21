import json
import sys

import anthropic

from . import config
from .tools import execute_tool


def run_agent(
    client: anthropic.Anthropic,
    system_prompt: str,
    initial_message: str,
    tools: dict,
    model: str = config.SUBAGENT_MODEL,
    max_tokens: int = config.SUBAGENT_MAX_TOKENS,
    max_iterations: int = config.SUBAGENT_MAX_ITERATIONS,
) -> str:
    """Run a single agentic loop and return the agent's final text response."""
    tool_specs = [tool["spec"] for tool in tools.values()]
    messages = [{"role": "user", "content": initial_message}]

    for _ in range(max_iterations):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tool_specs,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [{block.name}] {str(block.input)[:120]}", file=sys.stderr)
                result = execute_tool(block.name, block.input, tools)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    print(
        f"Reached {max_iterations}-iteration safety cap before finishing.",
        file=sys.stderr,
    )
    return ""


def _parse_json_response(text: str) -> dict:
    """Extract JSON from an agent's final text response.

    Agents may wrap JSON in markdown fences; this strips them before parsing.
    Returns a stub dict with an error field if parsing fails.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # drop opening fence (```json or ```) and closing fence
        inner = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
        stripped = inner.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        return {"findings": [], "error": str(exc), "raw": text[:500]}
