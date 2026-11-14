"""The web page: saved runs for all, live runs on the visitor's own key."""

import json

import pytest

from autodocs import web

RECORD = {"branch": "feat/x", "model": "gemini-3.5-flash-lite", "writer_model": None,
          "stop_reason": "done", "steps": 2, "tool_calls": 1, "cost_usd": 0.0024,
          "finished_at": "2026-11-13T10:00:00+00:00", "markdown": "# feat: x\n<b>bold</b>",
          "trace": ["step 1 · read_diff({}) → ok"]}


@pytest.fixture
def client(tmp_path, sample_repo, monkeypatch):
    """A test client with one saved run and the sample repo as the demo repo."""
    (tmp_path / "feat_x.json").write_text(json.dumps(RECORD))
    monkeypatch.setenv("AUTODOCS_DEMO_BRANCHES", "feat/x")
    return web.create_app(str(tmp_path), str(sample_repo)).test_client()


def test_index_lists_saved_runs_and_the_form(client):
    """Saved runs show; the form asks for the visitor's own key."""
    page = client.get("/").get_data(as_text=True)
    assert "/runs/feat_x" in page and 'type="password"' in page


def test_saved_run_is_escaped(client):
    """Model output is shown as text, never as HTML."""
    page = client.get("/runs/feat_x").get_data(as_text=True)
    assert "&lt;b&gt;bold&lt;/b&gt;" in page and "<b>bold</b>" not in page


def test_unknown_or_unsafe_run_name_is_404(client):
    """Only saved run names are served."""
    assert client.get("/runs/nope").status_code == 404
    assert client.get("/runs/..%2Fsecret").status_code == 404


@pytest.mark.parametrize("form, message", [
    ({"branch": "feat/other", "api_key": "k" * 30}, "Unknown branch"),
    ({"branch": "feat/x", "api_key": "short"}, "does not look like an API key"),
])
def test_live_run_rejects_bad_input(client, form, message):
    """Unknown branches and junk keys are refused before anything runs."""
    response = client.post("/run", data=form)
    assert response.status_code == 400 and message in response.get_data(as_text=True)


def test_live_run_uses_the_visitor_key_once(client, monkeypatch):
    """The key goes to the run and nowhere else; the result is shown."""
    seen = {}

    def fake_run(args, api_key, model, log, work_dir):
        """Record the call instead of calling Gemini."""
        seen.update(key=api_key, steps=args.max_steps, work_dir=work_dir)
        return {**RECORD, "markdown": "# done"}
    monkeypatch.setattr(web, "run_and_record", fake_run)
    page = client.post("/run", data={"branch": "feat/x", "api_key": "AQ." + "k" * 40})
    assert "# done" in page.get_data(as_text=True)
    assert seen["key"] == "AQ." + "k" * 40 and seen["steps"] == 8
    assert "AQ." + "k" * 40 not in page.get_data(as_text=True)


def test_healthz(client):
    """Cloud Run's health check answers."""
    assert client.get("/healthz").get_json() == {"status": "ok"}
