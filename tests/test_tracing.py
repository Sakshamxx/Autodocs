"""Tracing: off without keys; with a client, one observation per model call and tool call."""

from contextlib import contextmanager

from autodocs.agent import run_agent
from autodocs.tools import Tool
from autodocs.tracing import Tracer
from autodocs.writeup import Writeup
from tests.test_agent import ANSWER, count_lines


class FakeLangfuse:
    """Records observations instead of sending them."""

    def __init__(self):
        """Start empty."""
        self.observations, self.flushed = [], False

    @contextmanager
    def start_as_current_observation(self, name, as_type, **fields):
        """Record one observation and let the caller update it."""
        record = {"name": name, "type": as_type, **fields}
        self.observations.append(record)

        class Observation:
            """Stands in for a Langfuse observation."""

            def update(self, **more):
                """Merge the update into the record."""
                record.update(more)
        yield Observation()

    def flush(self):
        """Note that a flush happened."""
        self.flushed = True


def test_tracing_is_off_without_keys(monkeypatch):
    """No keys, no client: the run works and nothing is sent."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    assert Tracer().client is None


def test_each_model_call_and_tool_call_is_recorded(fake_client):
    """Two model calls become generations with usage and cost; the tool call is recorded."""
    tracer = Tracer(enabled=False)
    tracer.client = FakeLangfuse()
    client = fake_client([[("count_lines", {"path": "a"})], ANSWER])
    with tracer.run("autodocs test", "goal") as finish:
        run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                  log=lambda _: None, tracer=tracer)
        finish(output="done")
    tracer.flush()
    kinds = [(o["type"], o["name"]) for o in tracer.client.observations]
    assert kinds == [("span", "autodocs test"), ("generation", "step 1"),
                     ("tool", "count_lines"), ("generation", "step 2")]
    generation = tracer.client.observations[1]
    assert generation["usage_details"] == {"input": 1000, "output": 100}
    assert generation["cost_details"]["total"] > 0
    assert tracer.client.observations[0]["output"] == "done" and tracer.client.flushed


def test_the_writer_call_is_traced_too(fake_client):
    """With a writer, its call is a generation of its own, so the trace adds up to the bill."""

    class Writer(fake_client):
        """A pricier model that only writes."""

        model = "gemini-3.6-flash"
    tracer = Tracer(enabled=False)
    tracer.client = FakeLangfuse()
    reader = fake_client([[("count_lines", {"path": "a"})], "reader would answer here"])
    run = run_agent(reader, "goal", [Tool.from_function(count_lines)], Writeup,
                    log=lambda _: None, writer=Writer([ANSWER]), tracer=tracer)
    models = [o.get("model") for o in tracer.client.observations if o["type"] == "generation"]
    assert models == ["gemini-3.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
    traced = sum(o["cost_details"]["total"] for o in tracer.client.observations
                 if o["type"] == "generation")
    assert abs(traced - run.cost_usd) < 1e-12

