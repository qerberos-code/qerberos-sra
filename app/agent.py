import json
import sys
import time

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
        # Retry on rate limit with exponential backoff
        for attempt in range(6):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    tools=tool_specs,
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                wait = 10 * (2 ** attempt)
                print(f"  Rate limit hit — retrying in {wait}s…", file=sys.stderr)
                time.sleep(wait)
        else:
            raise RuntimeError("Rate limit: exhausted retries. Add API credits at console.anthropic.com")

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

    Searches for a ```json ... ``` block anywhere in the text, then falls
    back to finding the first { ... } span. Returns a stub on failure.
    """
    import re

    # Try fenced block first (```json ... ``` or ``` ... ```)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        # Find the first { and last } in the whole response
        start = text.find("{")
        end = text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end != -1 else text

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"  [parse] failed: {exc} — raw[:200]: {text[:200]}", file=sys.stderr)
        return {"findings": [], "error": str(exc), "raw": text[:500]}
