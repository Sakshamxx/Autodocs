"""The agent loop, written by hand: think, act, look at the result, repeat."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from autodocs.llm import Message, ModelClient, ModelError, Usage, cost_usd
from autodocs.tools import FailureInjector, Tool, run_tool

SYSTEM_PROMPT = """You are AutoDocs. You document a finished branch of a Python repository.
Work in this order: read the diff; open any file you need to understand code the diff uses
but does not show; fix docstrings that are missing or wrong with write_docstring; then answer.
Rules:
- `functions` lists every application function the diff adds OR modifies (any changed line
  inside it), not only new ones. Skip tests and migrations.
- Describe only behaviour you read in code. Never guess what an unread helper does.
- could_not_determine lists, one item each: helpers the diff calls that you did not open,
  functions with no body (`...` or `pass`), files that do not parse, and tools that failed.
- Copy names, paths and URLs exactly as they appear in the code.
- Ask for several tools at once when they do not depend on each other.
- A tool result marked "error" is information. Try another way once; if it fails again,
  record it in could_not_determine and carry on. Do not repeat a failing call.
- Watch the budget line below. When it is nearly spent, answer with what you have.
You are done when every changed function is in `functions` and every field is filled."""


FAILED_ROUNDS_BEFORE_NUDGE = 2  # then the engine tells the model to answer now
FAILED_ROUNDS_BEFORE_STOP = 4   # then the engine gives up for it


@dataclass
class Limits:
    """The run's ceilings."""

    max_steps: int = 12  # hard: the loop stops here
    budget_tokens: int = 60_000  # advisory each turn, and a hard stop once spent
    max_seconds: float = 300  # wall clock for the whole run


@dataclass
class RunResult:
    """How a run ended, what it produced and what it cost."""

    writeup: BaseModel | None
    stop_reason: str
    steps: int
    usage: Usage
    cost_usd: float
    tool_calls: int = 0
    tool_errors: int = 0
    trace: list[str] = field(default_factory=list)
    usage_by_model: dict[str, Usage] = field(default_factory=dict)


def short(value, limit: int = 80) -> str:
    """Shorten a value for the trace."""
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def budget_line(usage: Usage, limits: Limits, step: int, failed_rounds: int = 0) -> str:
    """The note the engine writes into every turn: budget, and a nudge if tools keep failing."""
    used = usage.input_tokens + usage.output_tokens + usage.thinking_tokens
    line = (f"\n\nBudget: {used:,} of {limits.budget_tokens:,} tokens used; "
            f"step {step} of {limits.max_steps}.")
    if failed_rounds >= FAILED_ROUNDS_BEFORE_NUDGE:
        line += (f" Every tool call in the last {failed_rounds} rounds failed: stop calling "
                 "tools and answer now, listing what you could not do in could_not_determine.")
    return line


def run_agent(client: ModelClient, goal: str, tools: list[Tool],
              output_schema: type[BaseModel], limits: Limits | None = None,
              failures: FailureInjector | None = None,
              log: Callable[[str], None] = print, clock: Callable[[], float] = time.monotonic,
              writer: ModelClient | None = None) -> RunResult:
    """Run the loop until it answers, or a step, token or time ceiling is reached.
    With a writer, the cheap client reads and calls tools; the writer writes the final answer."""
    # Stop conditions, written before the code: the run ends when the model answers without
    # asking for a tool and the answer fits output_schema (done); or when the step cap, the
    # token budget or the time limit is reached; or when the model call fails for good.
    limits = limits or Limits()
    failures = failures or FailureInjector()
    history = [Message(role="user", text=goal)]
    tools_by_name = {tool.name: tool for tool in tools}
    usage, trace, counts = Usage(), [], {"calls": 0, "errors": 0}
    by_model: dict[str, Usage] = {}

    def count_usage(model: str, used: Usage) -> None:
        """Add a call's tokens to the run total and to its model's total."""
        usage.add(used)
        by_model.setdefault(model, Usage()).add(used)
    failed_rounds = 0  # consecutive rounds in which every tool call failed
    started = clock()

    def note(line: str) -> None:
        """Record a trace line and show it."""
        trace.append(line)
        log(line)

    def result(writeup, reason: str, step: int) -> RunResult:
        """Package the run's outcome, keeping all the work done so far."""
        cost = sum(cost_usd(model, used) for model, used in by_model.items())
        return RunResult(writeup, reason, step, usage, cost, counts["calls"], counts["errors"],
                         trace, by_model)

    for step in range(1, limits.max_steps + 1):
        spent = usage.input_tokens + usage.output_tokens + usage.thinking_tokens
        if spent >= limits.budget_tokens:
            return result(None, f"token budget of {limits.budget_tokens:,} spent", step - 1)
        if clock() - started >= limits.max_seconds:
            return result(None, f"time limit of {limits.max_seconds:.0f} s reached", step - 1)
        if failed_rounds >= FAILED_ROUNDS_BEFORE_STOP:
            return result(None, f"gave up: every tool call failed {failed_rounds} rounds in a row",
                          step - 1)
        try:
            reply = client.reply(SYSTEM_PROMPT + budget_line(usage, limits, step, failed_rounds),
                                 history, tools, output_schema)
        except ModelError as exc:
            note(f"step {step} · model call failed: {exc}")
            return result(None, f"model error: {type(exc).__name__}", step)
        count_usage(client.model, reply.usage)
        tokens = f"{reply.usage.input_tokens:,} in / {reply.usage.output_tokens:,} out"
        if not reply.tool_calls and writer is not None:
            # The cheap model has finished reading; the better model writes from the same notes.
            note(f"step {step} · reading done ({client.model}) · {tokens}")
            try:
                reply = writer.reply(SYSTEM_PROMPT, history, [], output_schema)
            except ModelError as exc:
                note(f"step {step} · writer call failed: {exc}")
                return result(None, f"model error: {type(exc).__name__}", step)
            count_usage(writer.model, reply.usage)
            tokens = f"{reply.usage.input_tokens:,} in / {reply.usage.output_tokens:,} out"
        history.append(reply.message)
        if reply.cut_off:
            note(f"step {step} · answer cut off at the output cap · {tokens}")
            return result(None, "output cap reached (thinking counts toward it)", step)
        if not reply.tool_calls:
            note(f"step {step} · final answer ({(writer or client).model}) · {tokens}")
            try:
                return result(output_schema.model_validate_json(reply.text), "done", step)
            except ValidationError as exc:
                return result(None, f"answer did not match the schema: {short(exc, 200)}", step)
        results = []
        for call in reply.tool_calls:
            if failures.should_fail():
                outcome = {"error": f"{call.name} failed: injected failure (test switch)"}
            else:
                outcome = run_tool(tools_by_name, call.name, call.args)
            counts["calls"] += 1
            counts["errors"] += "error" in outcome
            note(f"step {step} · {call.name}({short(call.args, 60)}) → {short(outcome, 70)}")
            results.append({"id": call.id, "name": call.name, "result": outcome})
        failed_rounds = failed_rounds + 1 if all("error" in r["result"] for r in results) else 0
        # All results for this turn go back in ONE message, each with its call's id.
        history.append(Message(role="tool", tool_results=results))
        note(f"step {step} · {len(results)} tool call(s) · {tokens}")
    return result(None, f"step cap of {limits.max_steps} reached", limits.max_steps)
