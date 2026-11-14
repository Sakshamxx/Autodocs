"""The hand-written agent loop."""

import json

from autodocs.agent import Limits, run_agent
from autodocs.llm import ModelUnavailable
from autodocs.tools import FailureInjector, Tool
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
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                    Limits(max_steps=4), log=lambda _: None)
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


def test_a_function_without_a_body_status_breaks_the_contract(fake_client):
    """The body field is required: an answer that leaves it out is not a write-up."""
    note = {"path": "a.py", "function": "f", "what_it_does": "x", "docstring_updated": False}
    answer = json.dumps({**json.loads(ANSWER), "functions": [note]})
    run = run_agent(fake_client([answer]), "goal", [], Writeup, log=lambda _: None)
    assert run.writeup is None and run.stop_reason.startswith("answer did not match")


def broken_tool(path: str) -> str:
    """Always raises."""
    raise OSError("disk on fire")


def test_tool_exception_becomes_error_result(fake_client):
    """A tool that raises returns an error the model sees; the run carries on."""
    client = fake_client([[("broken_tool", {"path": "a"})], ANSWER])
    run = run_agent(client, "goal", [Tool.from_function(broken_tool)], Writeup,
                    log=lambda _: None)
    sent = client.histories[1][-1].tool_results[0]["result"]
    assert sent == {"error": "broken_tool failed: OSError: disk on fire"}
    assert run.stop_reason == "done" and run.tool_errors == 1


def test_failure_injection_every_call(fake_client):
    """AUTODOCS_FAIL_TOOL_CALLS=every fails each call without running the tool."""
    client = fake_client([[("count_lines", {"path": "a"})], [("count_lines", {"path": "b"})],
                          ANSWER])
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                    failures=FailureInjector("every"), log=lambda _: None)
    assert run.tool_errors == 2 and run.stop_reason == "done"  # the model chose to answer


def test_failure_injection_numbers():
    """'2,3' fails only the second and third calls."""
    injector = FailureInjector("2,3")
    assert [injector.should_fail() for _ in range(4)] == [False, True, True, False]


def test_budget_is_written_into_every_turn_and_stops_the_run(fake_client):
    """Each call carries the budget line; once spent, the run stops."""
    seen = []

    class Recording(fake_client):
        """Remember the system prompt of each call."""

        def reply(self, system, history, tools, output_schema=None):
            """Record, then answer as scripted."""
            seen.append(system.splitlines()[-1])
            return super().reply(system, history, tools, output_schema)
    client = Recording([[("count_lines", {"path": "a"})]] * 10)
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                    Limits(budget_tokens=2_500), log=lambda _: None)
    assert seen[0] == "Budget: 0 of 2,500 tokens used; step 1 of 12."
    assert seen[1].startswith("Budget: 1,100 of 2,500")
    assert run.stop_reason == "token budget of 2,500 spent" and run.steps == 3


def test_time_limit(fake_client):
    """The wall clock is checked before each step."""
    ticks = iter([0, 0, 400])
    client = fake_client([[("count_lines", {"path": "a"})]] * 5)
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                    Limits(max_seconds=300), log=lambda _: None, clock=lambda: next(ticks))
    assert run.stop_reason == "time limit of 300 s reached" and run.steps == 1


def test_model_error_keeps_the_work_done(fake_client):
    """A failing model call ends the run but keeps the trace and the tokens spent."""

    class FailsSecond(fake_client):
        """Fail on the second call."""

        def reply(self, system, history, tools, output_schema=None):
            """Raise once a first turn has happened."""
            if self.histories:
                raise ModelUnavailable("503 high demand")
            return super().reply(system, history, tools, output_schema)
    client = FailsSecond([[("count_lines", {"path": "a"})]])
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                    log=lambda _: None)
    assert run.stop_reason == "model error: ModelUnavailable"
    assert run.usage.input_tokens == 1000 and len(run.trace) == 3


def test_engine_nudges_then_gives_up_when_every_tool_fails(fake_client):
    """After 2 all-failed rounds the turn says 'answer now'; after 4 the engine stops."""
    seen = []

    class Recording(fake_client):
        """Remember the last system-prompt line."""

        def reply(self, system, history, tools, output_schema=None):
            """Record, then answer as scripted."""
            seen.append(system.splitlines()[-1])
            return super().reply(system, history, tools, output_schema)
    client = Recording([[("count_lines", {"path": "a"})]] * 10)
    run = run_agent(client, "goal", [Tool.from_function(count_lines)], Writeup,
                    failures=FailureInjector("every"), log=lambda _: None)
    assert "stop calling tools" not in seen[1]
    assert "last 2 rounds failed" in seen[2]
    assert run.stop_reason == "gave up: every tool call failed 4 rounds in a row"
    assert run.steps == 4


def test_tool_error_is_sent_without_a_traceback(fake_client):
    """An expected ToolError reaches the model as its plain message."""
    from autodocs.tools import ToolError

    def missing(path: str) -> str:
        """Pretend the file is missing."""
        raise ToolError(f"{path} is not a file in this repository")
    client = fake_client([[("missing", {"path": "x.py"})], ANSWER])
    run_agent(client, "goal", [Tool.from_function(missing)], Writeup, log=lambda _: None)
    sent = client.histories[1][-1].tool_results[0]["result"]
    assert sent == {"error": "x.py is not a file in this repository"}


def test_writer_model_writes_the_final_answer(fake_client):
    """The reader calls tools; the writer gets the history with no tools and answers."""

    class Writer(fake_client):
        """A pricier model that only writes."""

        model = "gemini-3.6-flash"
    reader = fake_client([[("count_lines", {"path": "a"})], "reader would answer here"])
    writer = Writer([ANSWER])
    tool_lists = []
    original = writer.reply

    def spy(system, history, tools, output_schema=None):
        """Remember which tools the writer was offered."""
        tool_lists.append(tools)
        return original(system, history, tools, output_schema)
    writer.reply = spy
    run = run_agent(reader, "goal", [Tool.from_function(count_lines)], Writeup,
                    writer=writer, log=lambda _: None)
    assert run.stop_reason == "done" and tool_lists == [[]]
    assert set(run.usage_by_model) == {"gemini-3.5-flash-lite", "gemini-3.6-flash"}
    assert run.usage_by_model["gemini-3.5-flash-lite"].input_tokens == 2000
    expected = (2000 * 0.30 + 200 * 2.50 + 1000 * 0.75 + 100 * 3.75) / 1_000_000
    assert abs(run.cost_usd - expected) < 1e-12


def test_cut_off_answer_stops_with_a_clear_reason(fake_client):
    """A truncated answer is reported as the output cap, not as a schema error."""

    class CutOff(fake_client):
        """Return a reply marked as cut off."""

        def reply(self, system, history, tools, output_schema=None):
            """Pretend the answer hit max_output_tokens."""
            answer = super().reply(system, history, tools, output_schema)
            answer.cut_off = True
            return answer
    run = run_agent(CutOff(['{"title": "fe']), "goal", [], Writeup, log=lambda _: None)
    assert run.stop_reason == "output cap reached (thinking counts toward it)"
