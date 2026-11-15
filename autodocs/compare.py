"""Compare two run records side by side: python -m autodocs.compare a.json b.json."""

import json
import sys
from pathlib import Path

from autodocs.report import coverage

ROWS = [
    ("engine", lambda r: r.get("engine", "hand")),
    ("model", lambda r: r["model"]),
    ("stop", lambda r: r["stop_reason"]),
    ("steps", lambda r: r["steps"]),
    ("tool calls (errors)", lambda r: f"{r['tool_calls']} ({r.get('tool_errors', 0)})"),
    ("input tokens", lambda r: f"{r['usage']['input_tokens']:,}"),
    # Output includes thinking; since S6 the record keeps thinking_tokens apart, so add it back.
    ("output tokens",
     lambda r: f"{r['usage']['output_tokens'] + r['usage'].get('thinking_tokens', 0):,}"),
    ("cost (USD)", lambda r: f"{r['cost_usd']:.5f}"),
    ("duration (s)", lambda r: r.get("duration_s", "-")),
    ("functions covered", lambda r: "{}/{}".format(*coverage(r)[:2])),
    ("could not determine", lambda r: len(r["writeup"]["could_not_determine"])
     if r["writeup"] else "-"),
]


def tool_sequence(record: dict) -> list[str]:
    """The tools called, in order, read from the trace."""
    calls = []
    for line in record["trace"]:
        if "→" in line:
            name = line.split(" · ", 1)[1].split("(")[0].split(" →")[0]
            calls.append(name)
    return calls


def compare(a: dict, b: dict) -> str:
    """Render the two runs as a Markdown table plus their tool sequences."""
    lines = ["| | A | B |", "|---|---|---|"]
    lines += [f"| {label} | {get(a)} | {get(b)} |" for label, get in ROWS]
    lines += ["", f"A tools: {' → '.join(tool_sequence(a))}",
              f"B tools: {' → '.join(tool_sequence(b))}"]
    return "\n".join(lines)


def main() -> int:
    """Print the comparison of the two files given."""
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a, b = (json.loads(Path(p).read_text()) for p in sys.argv[1:3])
    print(compare(a, b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
