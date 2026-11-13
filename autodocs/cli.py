"""Command line: python -m autodocs <branch> --repo <path to a ShopLite clone>."""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from autodocs.agent import run_agent
from autodocs.llm import PRICES_USD_PER_MILLION, GeminiClient
from autodocs.repo_tools import Workspace, make_repo_tools
from autodocs.writeup import Writeup, correct_against_facts

# Cheapest per finished run in the 2026-11-13 comparison (reports/slot1-report.md).
DEFAULT_MODEL = "gemini-3.5-flash-lite"
GOAL = ("Document the branch '{branch}' (compared with '{base}'): write the pull request "
        "write-up and fix any missing or wrong docstrings of the functions it changes.")


class InputError(Exception):
    """The run would fail before it starts; caught before any money is spent."""


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command-line options."""
    parser = argparse.ArgumentParser(prog="autodocs", description=__doc__)
    parser.add_argument("branch", help="branch to document, e.g. feat/coupon-stacking")
    parser.add_argument("--repo", required=True, help="path to a local clone of the target repo")
    parser.add_argument("--base", default="main", help="branch to compare against")
    parser.add_argument("--max-steps", type=int, default=12, help="hard step cap")
    parser.add_argument("--out", default="runs", help="folder for run records")
    return parser.parse_args(argv)


def validate(args: argparse.Namespace, api_key: str | None, model: str) -> None:
    """Check everything that can be checked for free, before the first model call."""
    if not api_key:
        raise InputError("GEMINI_API_KEY is not set (copy .env.example to .env)")
    if model not in PRICES_USD_PER_MILLION:
        raise InputError(f"no price recorded for {model}; known: {sorted(PRICES_USD_PER_MILLION)}")
    if args.max_steps < 1:
        raise InputError("limits too small: need max-steps ≥ 1")
    repo = Path(args.repo)
    if not (repo / ".git").exists():
        raise InputError(f"{repo} is not a git repository")
    for ref in (args.branch, args.base):
        found = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo,
                               capture_output=True)
        if found.returncode != 0:
            raise InputError(f"branch '{ref}' does not exist in {repo}")
    diff = subprocess.run(["git", "diff", "--quiet", f"{args.base}...{args.branch}"], cwd=repo)
    if diff.returncode == 0:
        raise InputError(f"'{args.branch}' has no changes compared with '{args.base}'")


def to_markdown(branch: str, writeup: Writeup) -> str:
    """Render the write-up as a PR description plus release note."""
    lines = [f"# {writeup.title}", "", writeup.summary, "", "## Changes"]
    lines += [f"- {change}" for change in writeup.changes]
    lines += ["", "## Functions"]
    lines += [f"- `{f.path}::{f.function}` ({f.body}): {f.what_it_does}"
              for f in writeup.functions]
    lines += ["", "## Could not determine"]
    lines += [f"- {item}" for item in writeup.could_not_determine] or ["- Nothing."]
    lines += ["", "## Release note", writeup.release_note or "No user-visible change."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run AutoDocs on one branch and save the run record."""
    args = parse_args(argv)
    logging.getLogger("google_genai.types").setLevel(logging.ERROR)  # SDK chatter on tool turns
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("AUTODOCS_MODEL", DEFAULT_MODEL)
    try:
        validate(args, api_key, model)
    except InputError as exc:
        print(f"Not started: {exc}", file=sys.stderr)
        return 2

    safe_name = args.branch.replace("/", "_")
    workspace = Workspace(args.repo, args.branch, args.base, Path(".work") / safe_name)
    client = GeminiClient(api_key, model)
    goal = GOAL.format(branch=args.branch, base=args.base)
    print(f"AutoDocs · {args.branch} vs {args.base} · {model} · cap {args.max_steps} steps")
    run = run_agent(client, goal, make_repo_tools(workspace), Writeup, args.max_steps)

    changed = workspace.changed_functions()
    corrections = (correct_against_facts(run.writeup, changed["unparseable"])
                   if run.writeup else [])
    for line in corrections:
        print(f"corrected: {line}")
    record = {
        "branch": args.branch, "base": args.base, "model": model,
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "stop_reason": run.stop_reason, "steps": run.steps, "tool_calls": run.tool_calls,
        "tool_errors": run.tool_errors,
        "usage": vars(run.usage), "cost_usd": round(run.cost_usd, 6),
        "changed": changed, "corrections": corrections,
        "writeup": run.writeup.model_dump() if run.writeup else None,
        "docstring_patch": workspace.docstring_patch(), "trace": run.trace,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{safe_name}.json").write_text(json.dumps(record, indent=2) + "\n")
    if run.writeup:
        (out / f"{safe_name}.md").write_text(to_markdown(args.branch, run.writeup))
    print(f"Stop: {run.stop_reason} · {run.steps} steps · {run.tool_calls} tool calls "
          f"({run.tool_errors} errors) · {run.usage.input_tokens:,} in / "
          f"{run.usage.output_tokens:,} out tokens · ${run.cost_usd:.5f}")
    return 0 if run.writeup else 1
