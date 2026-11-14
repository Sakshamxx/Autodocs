"""A small web page over AutoDocs: saved runs for everyone, live runs on the visitor's own key."""

import argparse
import json
import os
import re
import uuid
from pathlib import Path

from flask import Flask, abort, render_template_string, request

from autodocs.cli import DEFAULT_MODEL, InputError, run_and_record, validate

# Live runs use small limits: the visitor pays with their own key.
LIVE_LIMITS = {"max_steps": 8, "budget_tokens": 40_000, "max_seconds": 120}
KEY_PATTERN = re.compile(r"[A-Za-z0-9._-]{20,200}")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>AutoDocs</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;
      line-height:1.5}
 table{border-collapse:collapse;width:100%}
 td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left}
 pre{background:#f5f5f5;padding:1rem;overflow-x:auto;white-space:pre-wrap}
 .note{color:#555;font-size:.9rem} .error{color:#a00}
</style></head><body>
<h1>AutoDocs</h1>
<p class="note">An agent that reads a finished branch and writes its pull request description,
release note and docstrings. Course reference build; all data is synthetic.</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if run %}
 <h2>{{ run.branch }} · {{ run.stop_reason }}</h2>
 <p>{{ run.steps }} steps · {{ run.tool_calls }} tool calls · ${{ "%.5f"|format(run.cost_usd) }}
  · {{ run.model }}{% if run.writer_model %} → {{ run.writer_model }}{% endif %}</p>
 {% if run.markdown %}<pre>{{ run.markdown }}</pre>{% endif %}
 <h3>Trace</h3><pre>{{ run.trace|join("\n") }}</pre>
 <p><a href="/">Back</a></p>
{% else %}
 <h2>Saved runs</h2>
 <table><tr><th>Branch</th><th>Model</th><th>Stop</th><th>Cost (USD)</th></tr>
 {% for name, r in runs %}<tr><td><a href="/runs/{{ name }}">{{ r.branch }}</a></td>
  <td>{{ r.model }}{% if r.writer_model %} → {{ r.writer_model }}{% endif %}</td>
  <td>{{ r.stop_reason }}</td><td>{{ "%.5f"|format(r.cost_usd) }}</td></tr>
 {% else %}<tr><td colspan="4">No saved runs yet.</td></tr>{% endfor %}</table>
 <h2>Run it live, on your own key</h2>
 <form method="post" action="/run">
  <p><label>Branch <select name="branch">{% for b in branches %}<option>{{ b }}</option>
  {% endfor %}</select></label></p>
  <p><label>Your Gemini API key <input name="api_key" type="password" size="50" required
   autocomplete="off"></label></p>
  <p class="note">Your key is used for this one run and is never stored or logged.
  Limits: {{ limits.max_steps }} steps, {{ "{:,}".format(limits.budget_tokens) }} tokens.</p>
  <button>Run AutoDocs</button>
 </form>
{% endif %}
</body></html>"""


def create_app(runs_dir: str | None = None, demo_repo: str | None = None) -> Flask:
    """Build the web app (saved runs from runs_dir, live runs against demo_repo)."""
    app = Flask(__name__)
    runs_path = Path(runs_dir or os.environ.get("AUTODOCS_RUNS_DIR", "runs"))
    repo = demo_repo or os.environ.get("AUTODOCS_DEMO_REPO", "")
    branches = [b for b in os.environ.get(
        "AUTODOCS_DEMO_BRANCHES",
        "feat/coupon-stacking,fix/stock-race,feat/review-moderation").split(",") if b]

    def saved_runs() -> list[tuple[str, dict]]:
        """Every saved run record, newest first."""
        records = [(p.stem, json.loads(p.read_text())) for p in runs_path.glob("*.json")]
        return sorted(records, key=lambda item: item[1]["finished_at"], reverse=True)

    def page(**context) -> str:
        """Render the page with the defaults every view needs."""
        values = {"runs": [], "run": None, "error": None, **context}
        return render_template_string(PAGE, branches=branches, limits=LIVE_LIMITS, **values)

    @app.get("/")
    def index():
        """List saved runs and show the live-run form."""
        return page(runs=saved_runs())

    @app.get("/runs/<name>")
    def show_run(name: str):
        """Show one saved run."""
        path = runs_path / f"{name}.json"
        if not re.fullmatch(r"[\w.-]+", name) or not path.is_file():
            abort(404)
        return page(run=json.loads(path.read_text()))

    @app.post("/run")
    def live_run():
        """Run AutoDocs on the visitor's key; the key lives only in this request."""
        api_key = request.form.get("api_key", "").strip()
        branch = request.form.get("branch", "")
        if branch not in branches:
            return page(runs=saved_runs(), error="Unknown branch."), 400
        if not KEY_PATTERN.fullmatch(api_key):
            return page(runs=saved_runs(), error="That does not look like an API key."), 400
        args = argparse.Namespace(repo=repo, branch=branch, base="main", engine="hand",
                                  writer_model=None, out=str(runs_path), **LIVE_LIMITS)
        try:
            validate(args, api_key, DEFAULT_MODEL)
        except InputError as exc:
            return page(runs=saved_runs(), error=f"Not started: {exc}"), 400
        work_dir = Path(os.environ.get("AUTODOCS_WORK_DIR", "/tmp/autodocs")) / uuid.uuid4().hex
        record = run_and_record(args, api_key, DEFAULT_MODEL, log=lambda _: None,
                                work_dir=str(work_dir))  # own folder: visitors never collide
        return page(run=record)

    @app.get("/healthz")
    def healthz():
        """Liveness check for Cloud Run."""
        return {"status": "ok"}

    return app
