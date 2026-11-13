"""The hand-written agent loop."""

import json

from autodocs.agent import run_agent
from autodocs.tools import Tool
from autodocs.writeup import Writeup

ANSWER = json.dumps({
    "title": "feat: x", "summary": "s", "changes": ["c"], "functions": [],
    "release_note": "", "could_not_determine": []})


def count_lines(path: str) -> int:
    """Count lines in a file."""
    return 3


def test_stops_on_final_answer(fake_client):
    """A reply with no tool calls that fits the schema ends the run as done."""
    client = fake_client([[("count_lines", {"path": "a"})], ANSWER])
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup, log=lambda _: None)
    assert run.stop_reason == "done"
    assert run.steps == 2
    assert isinstance(run.writeup, Writeup)
    assert run.usage.input_tokens == 2000
    assert run.cost_usd == (2000 * 0.30 + 200 * 2.50) / 1_000_000


def test_step_cap_stops_a_runaway_loop(fake_client):
    """A model that never stops asking is cut off at max_steps."""
    client = fake_client([[("count_lines", {"path": "a"})]] * 50)
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup, max_steps=4,
                    log=lambda _: None)
    assert run.stop_reason == "step cap of 4 reached"
    assert run.writeup is None
    assert run.tool_calls == 4


def test_parallel_results_go_back_in_one_message(fake_client):
    """Two tool calls in one turn produce one tool message with two results."""
    client = fake_client([[("count_lines", {"path": "a"}), ("count_lines", {"path": "b"})],
                          ANSWER])
    run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup, log=lambda _: None)
    tool_messages = [m for m in client.histories[1] if m.role == "tool"]
    assert len(tool_messages) == 1
    assert [r["id"] for r in tool_messages[0].tool_results] == ["c0", "c1"]


def test_answer_that_breaks_the_contract_is_not_accepted(fake_client):
    """A final answer missing a required field stops the run without a write-up."""
    client = fake_client(['{"title": "only a title"}'])
    run = run_agent(client, "goal", [], Writeup, log=lambda _: None)
    assert run.writeup is None
    assert run.stop_reason.startswith("answer did not match the schema")


def test_trace_records_each_step(fake_client):
    """Every tool call and the final answer appear in the trace."""
    client = fake_client([[("count_lines", {"path": "a"})], ANSWER])
    lines = []
    run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup, log=lines.append)
    assert any("count_lines" in line for line in lines)
    assert lines[-1].startswith("step 2 · final answer")
