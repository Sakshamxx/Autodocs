"""Turn saved runs into the slot report table: python -m autodocs.report [runs folder]."""

import json
import sys
from pathlib import Path


def load_runs(folder: Path) -> list[dict]:
    """Read every run record in the folder, sorted by branch."""
    return sorted((json.loads(p.read_text()) for p in folder.glob("*.json")),
                  key=lambda record: (record["branch"], record["finished_at"]))


def coverage(record: dict) -> tuple[int, int, list[str]]:
    """How many changed functions the write-up covers, out of how many, and which it missed."""
    changed = record["changed"]["functions"]
    written = record["writeup"]["functions"] if record["writeup"] else []
    named = {f"{f['path']}::{f['function']}" for f in written}
    missed = [name for name in changed if name not in named]
    return len(changed) - len(missed), len(changed), missed


def docstrings_edited(record: dict) -> int:
    """Count docstring lines the agent added or replaced."""
    return sum(1 for line in record["docstring_patch"].splitlines()
               if line.startswith("+") and not line.startswith("+++") and '"""' in line)


def table(records: list[dict]) -> str:
    """Render the runs as a Markdown table."""
    rows = ["| Branch | Model | Stop | Steps | Tool calls | Input tokens | Output tokens | "
            "Cost (USD) | Changed functions covered | Docstrings edited | Could not determine | "
            "Corrected by code |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        covered, total, _ = coverage(r)
        unknowns = len(r["writeup"]["could_not_determine"]) if r["writeup"] else "-"
        model = r["model"] + (f" → {r['writer_model']}" if r.get("writer_model") else "")
        rows.append(f"| `{r['branch']}` | {model} | {r['stop_reason'][:60]} | {r['steps']} | "
                    f"{r['tool_calls']} | {r['usage']['input_tokens']:,} | "
                    f"{r['usage']['output_tokens'] + r['usage'].get('thinking_tokens', 0):,} | "
                    f"{r['cost_usd']:.5f} | {covered}/{total} | {docstrings_edited(r)} | "
                    f"{unknowns} | {len(r.get('corrections', []))} |")
    return "\n".join(rows)


def main() -> int:
    """Print the table for runs/ (or the folder given)."""
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "runs")
    records = load_runs(folder)
    if not records:
        print(f"no runs in {folder}/")
        return 1
    print(table(records))
    for r in records:
        _, _, missed = coverage(r)
        if missed:
            print(f"\n{r['branch']} missed: {', '.join(missed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
