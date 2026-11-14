"""Command line: python -m autodocs <branch> --repo <path to a ShopLite clone>."""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from autodocs.agent import Limits, run_agent
from autodocs.llm import (
    OLLAMA_BASE_URL,
    PRICES_USD_PER_MILLION,
    GeminiClient,
    OpenAICompatibleClient,
)
from autodocs.repo_tools import Workspace, make_repo_tools
from autodocs.tools import FailureInjector
from autodocs.tracing import Tracer
from autodocs.writeup import Writeup, correct_against_facts

# Cheapest per finished run in the 2026-11-13 comparison (reports/slot1-report.md).
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_OLLAMA_MODEL = "qwen3-4b-32k"  # Qwen3 4B with a 32K context (see README)
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
    parser.add_argument("--budget-tokens", type=int, default=60_000, help="run token budget")
    parser.add_argument("--max-seconds", type=float, default=300, help="wall-clock limit")
    parser.add_argument("--writer-model", default=os.environ.get("AUTODOCS_WRITER_MODEL"),
                        help="better model for the final write-up (default: same model)")
    parser.add_argument("--provider", choices=["gemini", "ollama"],
                        default=os.environ.get("AUTODOCS_PROVIDER", "gemini"),
                        help="gemini (needs GEMINI_API_KEY) or a local model through ollama")
    parser.add_argument("--engine", choices=["hand", "langchain"], default="hand",
                        help="the hand-written loop, or the same agent on LangChain")
    parser.add_argument("--out", default="runs", help="folder for run records")
    return parser.parse_args(argv)


def make_client(provider: str, model: str, api_key: str | None):
    """The model client for a provider; the agent never needs to know which."""
    if provider == "ollama":
        return OpenAICompatibleClient(model, base_url=OLLAMA_BASE_URL)
    return GeminiClient(api_key, model)


def validate(args: argparse.Namespace, api_key: str | None, model: str) -> None:
    """Check everything that can be checked for free, before the first model call."""
    provider = getattr(args, "provider", "gemini")
    if provider == "gemini" and not api_key:
        raise InputError("GEMINI_API_KEY is not set (copy .env.example to .env)")
    if provider == "ollama":
        try:
            urllib.request.urlopen(OLLAMA_BASE_URL.removesuffix("/v1") + "/api/version", timeout=3)
        except OSError:
            raise InputError(f"Ollama is not answering at {OLLAMA_BASE_URL}") from None
    for name in filter(None, [model, getattr(args, "writer_model", None)]):
        if name not in PRICES_USD_PER_MILLION:
            raise InputError(f"no price recorded for {name}; "
                             f"known: {sorted(PRICES_USD_PER_MILLION)}")
    if args.max_steps < 1 or args.budget_tokens < 1_000 or args.max_seconds < 10:
        raise InputError("limits too small: need max-steps ≥ 1, budget ≥ 1,000, seconds ≥ 10")
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


LANGCHAIN_GAPS = ("the token budget, the time limit, the give-up guard, failure injection "
                  "and per-call tracing")


def run_engine(args: argparse.Namespace, api_key: str, model: str, goal: str,
               workspace: Workspace, limits: Limits, failures: FailureInjector, log,
               tracer: Tracer):
    """Run the chosen engine (hand loop or LangChain) on the chosen provider."""
    if args.engine == "langchain":
        # S5 found this: the framework port enforces only the step cap. Say so, every time.
        print(f"Warning: the LangChain engine enforces only the step cap. Not enforced: "
              f"{LANGCHAIN_GAPS}. Use --engine hand (the default) for those.", file=sys.stderr)
        from autodocs.langchain_agent import run_langchain_agent  # heavy import, only if used
        return run_langchain_agent(api_key, model, goal, make_repo_tools(workspace), Writeup,
                                   limits, log=log)
    provider = getattr(args, "provider", "gemini")
    writer = make_client(provider, args.writer_model, api_key) if args.writer_model else None
    return run_agent(make_client(provider, model, api_key), goal, make_repo_tools(workspace),
                     Writeup, limits, failures, log=log, writer=writer, tracer=tracer)


def run_and_record(args: argparse.Namespace, api_key: str, model: str,
                   log=print, work_dir: str = ".work") -> dict:
    """Run AutoDocs on one branch, save the run record, and return it (CLI and web share this)."""
    safe_name = args.branch.replace("/", "_")
    workspace = Workspace(args.repo, args.branch, args.base, Path(work_dir) / safe_name)
    limits = Limits(args.max_steps, args.budget_tokens, args.max_seconds)
    failures = FailureInjector(os.environ.get("AUTODOCS_FAIL_TOOL_CALLS", ""))
    log(f"AutoDocs ({args.engine}) · {args.branch} vs {args.base} · {model} · "
        f"cap {limits.max_steps} steps, {limits.budget_tokens:,} tokens, "
        f"{limits.max_seconds:.0f} s")
    goal = GOAL.format(branch=args.branch, base=args.base)
    started = time.monotonic()
    tracer = Tracer()
    with tracer.run(f"autodocs {args.branch}", goal) as finish_trace:
        run = run_engine(args, api_key, model, goal, workspace, limits, failures, log, tracer)
        finish_trace(output=run.writeup.model_dump() if run.writeup else run.stop_reason,
                     metadata={"stop_reason": run.stop_reason, "steps": run.steps,
                               "cost_usd": round(run.cost_usd, 6), "model": model})
    tracer.flush()  # a short command would otherwise exit before the trace is sent

    changed = workspace.changed_functions()
    corrections = (correct_against_facts(run.writeup, changed["unparseable"])
                   if run.writeup else [])
    for line in corrections:
        log(f"corrected: {line}")
    record = {
        "branch": args.branch, "base": args.base, "model": model, "engine": args.engine,
        "provider": getattr(args, "provider", "gemini"),
        "writer_model": args.writer_model,
        "duration_s": round(time.monotonic() - started, 1),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "stop_reason": run.stop_reason, "steps": run.steps, "tool_calls": run.tool_calls,
        "tool_errors": run.tool_errors, "limits": vars(limits),
        "usage": vars(run.usage), "cost_usd": round(run.cost_usd, 6),
        "usage_by_model": {name: vars(used) for name, used in run.usage_by_model.items()},
        "changed": changed, "corrections": corrections,
        "writeup": run.writeup.model_dump() if run.writeup else None,
        "markdown": to_markdown(args.branch, run.writeup) if run.writeup else None,
        "docstring_patch": workspace.docstring_patch(), "trace": run.trace,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # A run without a write-up keeps its own file, so a later success never hides it.
    name = safe_name if run.writeup else f"{safe_name}.failed-{record['finished_at'][11:19]}"
    (out / f"{name.replace(':', '')}.json").write_text(json.dumps(record, indent=2) + "\n")
    if run.writeup:
        (out / f"{safe_name}.md").write_text(record["markdown"])
    log(f"Stop: {run.stop_reason} · {run.steps} steps · {run.tool_calls} tool calls "
        f"({run.tool_errors} errors) · {run.usage.input_tokens:,} in / "
        f"{run.usage.output_tokens:,} out tokens · ${run.cost_usd:.5f}")
    return record


def main(argv: list[str] | None = None) -> int:
    """Run AutoDocs on one branch from the command line."""
    args = parse_args(argv)
    logging.getLogger("google_genai.types").setLevel(logging.ERROR)  # SDK chatter on tool turns
    api_key = os.environ.get("GEMINI_API_KEY")
    default = DEFAULT_OLLAMA_MODEL if args.provider == "ollama" else DEFAULT_MODEL
    model = os.environ.get("AUTODOCS_MODEL", default)
    try:
        validate(args, api_key, model)
    except InputError as exc:
        print(f"Not started: {exc}", file=sys.stderr)
        return 2
    record = run_and_record(args, api_key, model)
    return 0 if record["writeup"] else 1
