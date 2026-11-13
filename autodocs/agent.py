"""The agent loop, written by hand: think, act, look at the result, repeat."""

from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from autodocs.llm import Message, ModelClient, Usage, cost_usd
from autodocs.tools import Tool, run_tool

SYSTEM_PROMPT = """You are AutoDocs. You document a finished branch of a Python repository.
Work in this order: read the diff; open any file you need to understand code the diff uses
but does not show; fix docstrings that are missing or wrong with write_docstring; then answer.
Rules:
- `functions` lists every application function the diff adds OR modifies (any changed line
  inside it), not only new ones. Skip tests and migrations.
- Describe only behaviour you read in code. Never guess what an unread helper does.
- could_not_determine lists, one item each: helpers the diff calls that you did not open,
  functions with no body (`...` or `pass`), and files that do not parse.
- Copy names, paths and URLs exactly as they appear in the code.
- Ask for several tools at once when they do not depend on each other.
You are done when every changed function is in `functions` and every field is filled."""


@dataclass
class RunResult:
    """How a run ended, what it produced and what it cost."""

    writeup: BaseModel | None
    stop_reason: str
    steps: int
    usage: Usage
    cost_usd: float
    tool_calls: int = 0
    trace: list[str] = field(default_factory=list)


def short(value, limit: int = 80) -> str:
    """Shorten a value for the trace."""
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def run_agent(client: ModelClient, goal: str, tools: list[Tool],
              output_schema: type[BaseModel], max_steps: int = 12,
              log: Callable[[str], None] = print) -> RunResult:
    """Run the loop until the model answers in the output schema or max_steps is reached."""
    # Stop condition, written before the code: the run ends when the model answers without
    # asking for a tool and the answer fits output_schema (done), or after max_steps (cap).
    history = [Message(role="user", text=goal)]
    tools_by_name = {tool.name: tool for tool in tools}
    usage, trace, tool_calls = Usage(), [], 0

    def note(line: str) -> None:
        """Record a trace line and show it."""
        trace.append(line)
        log(line)

    def result(writeup, reason: str, step: int) -> RunResult:
        """Package the run's outcome."""
        return RunResult(writeup, reason, step, usage, cost_usd(client.model, usage),
                         tool_calls, trace)

    for step in range(1, max_steps + 1):
        reply = client.reply(SYSTEM_PROMPT, history, tools, output_schema)
        usage.add(reply.usage)
        history.append(reply.message)
        tokens = f"{reply.usage.input_tokens:,} in / {reply.usage.output_tokens:,} out"
        if not reply.tool_calls:
            note(f"step {step} · final answer · {tokens}")
            try:
                return result(output_schema.model_validate_json(reply.text), "done", step)
            except ValidationError as exc:
                return result(None, f"answer did not match the schema: {short(exc, 200)}", step)
        results = []
        for call in reply.tool_calls:
            outcome = run_tool(tools_by_name, call.name, call.args)
            tool_calls += 1
            note(f"step {step} · {call.name}({short(call.args, 60)}) → {short(outcome, 70)}")
            results.append({"id": call.id, "name": call.name, "result": outcome})
        # All results for this turn go back in ONE message, each with its call's id.
        history.append(Message(role="tool", tool_results=results))
        note(f"step {step} · {len(results)} tool call(s) · {tokens}")
    return result(None, f"step cap of {max_steps} reached", max_steps)
