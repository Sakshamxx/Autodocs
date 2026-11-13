"""The agent loop, written by hand: think, act, look at the result, repeat. No tools yet."""

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from autodocs.llm import GeminiClient, ModelClient, Usage, cost_usd

SYSTEM_PROMPT = """You help document a code branch. Each turn, reply with exactly one line
starting with ASK: (a question you need answered) or ANSWER: (your final answer)."""
NO_MORE_INFO = "No more information is available. Answer with what you have."
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def answer_given(text: str) -> bool:
    """Default done check: any ANSWER counts."""
    return True


def run_loop(client: ModelClient, goal: str, is_done: Callable[[str], bool] = answer_given,
             max_steps: int = 8, log: Callable[[str], None] = print):
    """Loop until an ANSWER passes is_done or the step cap; return (answer, reason, usage)."""
    # Stop condition, written before the code: stop when an ANSWER passes is_done (done),
    # or after max_steps (cap). Nothing else ends the run.
    messages = [{"role": "user", "text": goal}]
    total = Usage()
    for step in range(1, max_steps + 1):
        reply = client.reply(SYSTEM_PROMPT, messages)
        total.add(reply.usage)
        messages.append({"role": "model", "text": reply.text})
        first_line = reply.text.strip().splitlines()[0] if reply.text.strip() else ""
        log(f"step {step:2d} · {reply.usage.input_tokens:>6,} in · "
            f"${cost_usd(client.model, total):.5f} so far · {first_line[:70]}")
        if first_line.startswith("ANSWER:") and is_done(reply.text):
            return reply.text, f"done at step {step}", total
        if first_line.startswith("ANSWER:"):
            observation = "Not done: the answer does not meet the goal. Try again."
        else:
            observation = NO_MORE_INFO
        messages.append({"role": "user", "text": observation})
    return None, f"step cap of {max_steps} reached", total


def main(argv: list[str] | None = None) -> int:
    """Run one goal from the command line: python -m autodocs.agent "goal" [--attach file]."""
    parser = argparse.ArgumentParser(prog="autodocs.agent")
    parser.add_argument("goal")
    parser.add_argument("--attach", help="a file to append to the goal, e.g. a diff")
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args(argv)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set (copy .env.example to .env)", file=sys.stderr)
        return 2
    goal = args.goal + (f"\n\n{Path(args.attach).read_text()}" if args.attach else "")
    client = GeminiClient(api_key, os.environ.get("AUTODOCS_MODEL", DEFAULT_MODEL))
    print(f"counting call: {client.count_tokens([{'role': 'user', 'text': goal}]):,} tokens "
          "(messages only; the system prompt is not counted)")
    answer, reason, total = run_loop(client, goal, max_steps=args.max_steps)
    print(f"\n{reason} · {total.input_tokens:,} in / {total.output_tokens:,} out · "
          f"${cost_usd(client.model, total):.5f}")
    if answer:
        print(answer)
    return 0 if answer else 1


if __name__ == "__main__":
    sys.exit(main())
