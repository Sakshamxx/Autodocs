"""The same agent on LangChain's create_agent: the framework runs the loop agent.py writes."""

import time
from collections.abc import Callable

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from autodocs.agent import SYSTEM_PROMPT, Limits, RunResult, short
from autodocs.llm import MAX_OUTPUT_TOKENS, REQUEST_TIMEOUT_S, Usage, cost_usd
from autodocs.tools import Tool, run_tool


def to_langchain_tool(tool: Tool, tools_by_name: dict[str, Tool]) -> StructuredTool:
    """Wrap one of our tools; run_tool keeps the same validation and errors-as-data."""

    def call(**kwargs) -> dict:
        """Run the tool through our own dispatcher."""
        return run_tool(tools_by_name, tool.name, kwargs)

    return StructuredTool.from_function(func=call, name=tool.name, description=tool.description,
                                        args_schema=tool.args_model)


def usage_of(message: AIMessage) -> Usage:
    """Read token counts from LangChain's usage_metadata."""
    meta = message.usage_metadata or {}
    thinking = (meta.get("output_token_details") or {}).get("reasoning", 0)
    cached = (meta.get("input_token_details") or {}).get("cache_read", 0)
    return Usage(input_tokens=meta.get("input_tokens", 0),
                 output_tokens=meta.get("output_tokens", 0) - thinking,
                 thinking_tokens=thinking, cached_tokens=cached)


def run_langchain_agent(api_key: str, model: str, goal: str, tools: list[Tool],
                        output_schema: type[BaseModel], limits: Limits | None = None,
                        log: Callable[[str], None] = print) -> RunResult:
    """Run the agent on create_agent, streaming each step into the trace."""
    limits = limits or Limits()
    tools_by_name = {tool.name: tool for tool in tools}
    chat_model = init_chat_model(  # the provider string keeps this provider-agnostic
        f"google_genai:{model}", api_key=api_key, max_retries=2,
        timeout=REQUEST_TIMEOUT_S, max_output_tokens=MAX_OUTPUT_TOKENS)
    agent = create_agent(
        model=chat_model,
        tools=[to_langchain_tool(tool, tools_by_name) for tool in tools],
        system_prompt=SYSTEM_PROMPT,
        response_format=output_schema,
        middleware=[ModelCallLimitMiddleware(run_limit=limits.max_steps, exit_behavior="end")],
    )
    usage, trace, counts, step = Usage(), [], {"calls": 0, "errors": 0}, 0
    final_state: dict = {}
    started = time.monotonic()

    def note(line: str) -> None:
        """Record a trace line and show it."""
        trace.append(line)
        log(line)

    # stream_mode="updates" yields one dict per graph node as it finishes: {"model": ...} etc.
    for update in agent.stream({"messages": [{"role": "user", "content": goal}]},
                               stream_mode="updates"):
        for node, state in update.items():
            if not state:
                continue
            final_state.update(state)
            for message in state.get("messages", []):
                if isinstance(message, AIMessage):
                    step += 1
                    usage.add(usage_of(message))
                    called = ", ".join(c["name"] for c in message.tool_calls) or "answer"
                    note(f"step {step} · {node} · {called} · "
                         f"{usage_of(message).input_tokens:,} in")
                elif isinstance(message, ToolMessage):
                    counts["calls"] += 1
                    counts["errors"] += str(message.content).startswith('{"error"')
                    note(f"step {step} · {message.name} → {short(message.content, 70)}")
    writeup = final_state.get("structured_response")
    elapsed = time.monotonic() - started
    reason = "done" if writeup else f"no structured answer (model call limit {limits.max_steps})"
    note(f"finished in {elapsed:.1f} s · {reason}")
    return RunResult(writeup, reason, step, usage, cost_usd(model, usage), counts["calls"],
                     counts["errors"], trace, {model: usage})
