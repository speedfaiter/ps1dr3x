"""Claude-driven tool-use loop for building and rendering an edit."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import config, logging_utils
from .probe import probe
from .timeline import Timeline
from .tools import TOOL_SCHEMAS, ToolContext, ToolError, dispatch


class AgentError(RuntimeError):
    pass


class LLMClient(Protocol):
    """Minimal interface the agent needs. The real Anthropic SDK satisfies this,
    and the tests substitute a replay client.
    """

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: Any,
        tools: list[dict],
        messages: list[dict],
    ) -> Any: ...


@dataclass
class AgentResult:
    rendered: dict[str, Any]
    assistant_text: str
    iterations: int


SYSTEM_PROMPT_PATH = config.PROMPTS_DIR / "system.md"


def _load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _build_system(prompt: str) -> list[dict]:
    return [
        {
            "type": "text",
            "text": prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _build_tools() -> list[dict]:
    tools = [dict(t) for t in TOOL_SCHEMAS]
    # Cache the whole tool list (last tool carries the breakpoint).
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


def _format_user_turn(instruction: str, timeline: Timeline) -> str:
    c = timeline.clip
    return (
        f"Clip: {c.source.name}\n"
        f"Duration: {c.duration:.3f}s\n"
        f"Resolution: {c.width}x{c.height}\n"
        f"FPS: {c.fps:.3f}\n"
        f"Has audio: {c.has_audio}\n"
        f"\nInstruction: {instruction}"
    )


class AnthropicAdapter:
    """Wrap the real Anthropic client to the LLMClient Protocol."""

    def __init__(self, client):
        self._client = client

    def messages_create(self, **kwargs):
        return self._client.messages.create(**kwargs)


def build_default_client() -> AnthropicAdapter:
    try:
        import anthropic  # type: ignore
    except ImportError as e:
        raise AgentError(
            "The `anthropic` package is not installed. Run `pip install anthropic`."
        ) from e
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        raise AgentError(logging_utils.msg("need_api_key"))
    return AnthropicAdapter(anthropic.Anthropic())


def run(
    instruction: str,
    source: str | Path,
    output_path: str | Path,
    *,
    client: LLMClient | None = None,
    model: str = config.DEFAULT_MODEL,
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    dry_run: bool = False,
) -> AgentResult:
    """Drive the agent loop until it renders or hits the iteration cap."""
    if client is None:
        client = build_default_client()

    clip = probe(source)
    timeline = Timeline(clip=clip)
    ctx = ToolContext(timeline=timeline, output_default=Path(output_path))

    system = _build_system(_load_system_prompt())
    tools = _build_tools()
    messages: list[dict] = [{"role": "user", "content": _format_user_turn(instruction, timeline)}]

    final_text = ""
    for iteration in range(1, config.MAX_AGENT_ITERATIONS + 1):
        response = client.messages_create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        content = _normalize_content(response)
        messages.append({"role": "assistant", "content": content})

        stop_reason = getattr(response, "stop_reason", None) or (
            response.get("stop_reason") if isinstance(response, dict) else None
        )

        tool_uses = [b for b in content if _block_type(b) == "tool_use"]
        if not tool_uses:
            final_text = _extract_text(content)
            if ctx.rendered is None:
                raise AgentError(
                    "Agent stopped without calling `render`. Last message: "
                    + (final_text or "(empty)")
                )
            return AgentResult(rendered=ctx.rendered, assistant_text=final_text, iterations=iteration)

        tool_results = []
        for block in tool_uses:
            name = _block_attr(block, "name")
            tool_input = _block_attr(block, "input") or {}
            tool_use_id = _block_attr(block, "id")
            logging_utils.say("tool_called", name=name)
            try:
                output = dispatch(name, tool_input, ctx)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": output,
                    }
                )
            except ToolError as e:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"Tool error: {e}",
                        "is_error": True,
                    }
                )

        if ctx.rendered is not None:
            # The next assistant turn should be a short confirmation.
            messages.append({"role": "user", "content": tool_results})
            follow = client.messages_create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
            final_text = _extract_text(_normalize_content(follow))
            return AgentResult(rendered=ctx.rendered, assistant_text=final_text, iterations=iteration)

        messages.append({"role": "user", "content": tool_results})

        if stop_reason == "end_turn":
            # Model stopped without rendering and without further tool calls.
            raise AgentError("Agent ended its turn without rendering.")

    raise AgentError(logging_utils.msg("agent_max_iters", n=config.MAX_AGENT_ITERATIONS))


# ----- helpers that tolerate both the real SDK objects and dict replays -------


def _normalize_content(response: Any) -> list[Any]:
    if hasattr(response, "content"):
        return list(response.content)
    if isinstance(response, dict):
        return list(response.get("content", []))
    raise AgentError(f"Unexpected response type: {type(response)!r}")


def _block_type(block: Any) -> str:
    if hasattr(block, "type"):
        return block.type
    if isinstance(block, dict):
        return block.get("type", "")
    return ""


def _block_attr(block: Any, key: str) -> Any:
    if hasattr(block, key):
        return getattr(block, key)
    if isinstance(block, dict):
        return block.get(key)
    return None


def _extract_text(content: list[Any]) -> str:
    chunks = []
    for b in content:
        if _block_type(b) == "text":
            chunks.append(_block_attr(b, "text") or "")
    return "\n".join(chunks).strip()
