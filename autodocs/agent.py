"""The agent loop, written by hand: think, act, look at the result, repeat. Now with tools."""

import argparse
import os
import re
import sys
from collections.abc import Callable

from autodocs.llm import GeminiClient, Message, ModelClient, Usage, cost_usd
from autodocs.tools import Tool, run_tool

SYSTEM_PROMPT = """You answer questions about files by calling the tools you are given.
Never guess what a tool could tell you. Ask for several tools at once when they do not
depend on each other. When you have everything you need, reply with your answer and no
tool call."""
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def answer_given(text: str) -> bool:
    """Default done check: any non-empty answer counts."""
    return bool(text.strip())


def honest_ticket_check(source: str) -> Callable[[str], bool]:
    """Done check with an honest exit: cited tickets must be in the source, or none claimed."""

    def is_done(text: str) -> bool:
        """True if every cited ticket is in the source, or the answer says there is none."""
        cited = re.findall(r"\bJIRA-\d+\b", text)
        if cited:
            return all(ticket in source for ticket in cited)
        return "No ticket is referenced" in text

    return is_done


def run_loop(client: ModelClient, goal: str, tools: list[Tool],
             is_done: Callable[[str], bool] = answer_given, max_steps: int = 8,
             log: Callable[[str], None] = print):
    """Loop until an answer passes is_done or the step cap; return (answer, reason, usage)."""
    # Stop condition, written before the code: stop when the model replies with no tool
    # call and the text passes is_done (done), or after max_steps (cap).
    history = [Message(role="user", text=goal)]
    tools_by_name = {tool.name: tool for tool in tools}
    total = Usage()
    for step in range(1, max_steps + 1):
        reply = client.reply(SYSTEM_PROMPT, history, tools)
        total.add(reply.usage)
        history.append(reply.message)
        asked = ", ".join(f"{c.name}({c.args})" for c in reply.tool_calls)
        log(f"step {step:2d} · {reply.usage.input_tokens:>6,} in · "
            f"${cost_usd(client.model, total):.5f} so far · "
            f"{asked or reply.text.strip()[:70]}")
        if reply.tool_calls:
            # Run every call, then send ALL the results back together, in one message.
            results = [{"id": c.id, "name": c.name,
                        "result": run_tool(tools_by_name, c.name, c.args)}
                       for c in reply.tool_calls]
            history.append(Message(role="tool", tool_results=results))
            continue
        if is_done(reply.text):
            return reply.text, f"done at step {step}", total
        history.append(Message(role="user", text="Not done: the answer does not meet the "
                                                 "goal. Try again."))
    return None, f"step cap of {max_steps} reached", total


def main(argv: list[str] | None = None) -> int:
    """Ask a question about the practice/ folder: python -m autodocs.agent "question"."""
    from autodocs.practice_tools import count_lines, list_directory

    parser = argparse.ArgumentParser(prog="autodocs.agent")
    parser.add_argument("goal")
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args(argv)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set (copy .env.example to .env)", file=sys.stderr)
        return 2
    client = GeminiClient(api_key, os.environ.get("AUTODOCS_MODEL", DEFAULT_MODEL))
    tools = [Tool.from_function(count_lines), Tool.from_function(list_directory)]
    answer, reason, total = run_loop(client, args.goal, tools, max_steps=args.max_steps)
    print(f"\n{reason} · {total.input_tokens:,} in / {total.output_tokens:,} out · "
          f"${cost_usd(client.model, total):.5f}")
    if answer:
        print(answer)
    return 0 if answer else 1


if __name__ == "__main__":
    sys.exit(main())
