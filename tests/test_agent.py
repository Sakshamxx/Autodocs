"""The hand-written loop with tools, using a fake model client (no network)."""

from autodocs.agent import honest_ticket_check, run_loop
from autodocs.llm import Message, ModelReply, ToolCall, Usage
from autodocs.practice_tools import count_lines, list_directory
from autodocs.tools import Tool

TOOLS = [Tool.from_function(count_lines), Tool.from_function(list_directory)]


def text_reply(text: str) -> ModelReply:
    """A scripted final answer."""
    return ModelReply(text, [], Usage(1000, 10), Message(role="model", text=text))


def calls_reply(*calls: ToolCall) -> ModelReply:
    """A scripted turn that asks for tools."""
    return ModelReply("", list(calls), Usage(1000, 10),
                      Message(role="model", tool_calls=list(calls)))


class FakeClient:
    """Replays scripted replies and records the conversation it was sent."""

    model = "gemini-3.5-flash-lite"

    def __init__(self, replies: list[ModelReply]):
        """Script the replies, in order (the last one repeats)."""
        self.replies = replies
        self.seen: list[list[Message]] = []

    def reply(self, system, history, tools):
        """Return the next scripted reply."""
        self.seen.append(list(history))
        return self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]

    def count_tokens(self, history):
        """Pretend count."""
        return 42


def quiet(_):
    """Swallow log lines."""


def test_any_answer_is_done_by_default():
    """With no tool calls, the first answer ends the run."""
    answer, reason, usage = run_loop(FakeClient([text_reply("3 files")]), "goal", TOOLS,
                                     log=quiet)
    assert (answer, reason, usage.input_tokens) == ("3 files", "done at step 1", 1000)


def test_cap_stops_a_model_that_never_answers():
    """A model that only calls tools is stopped at the cap, with no answer."""
    looping = calls_reply(ToolCall("1", "list_directory", {"path": "."}))
    answer, reason, _ = run_loop(FakeClient([looping]), "goal", TOOLS, max_steps=3, log=quiet)
    assert answer is None and reason == "step cap of 3 reached"


def test_two_calls_get_both_results_in_one_message():
    """Parallel calls: both results go back together, in ONE tool message."""
    both = calls_reply(ToolCall("1", "count_lines", {"path": "app/main.py"}),
                       ToolCall("2", "count_lines", {"path": "app/utils.py"}))
    client = FakeClient([both, text_reply("7 and 8")])
    run_loop(client, "goal", TOOLS, log=quiet)
    last = client.seen[1][-1]
    assert [m.role for m in client.seen[1]] == ["user", "model", "tool"]
    assert [r["result"] for r in last.tool_results] == [{"result": 7}, {"result": 8}]


def test_bad_arguments_come_back_as_an_error_result():
    """A wrong type is not run: the model gets the validation error to read instead."""
    bad = calls_reply(ToolCall("1", "count_lines", {"path": 5}))
    client = FakeClient([bad, text_reply("sorry")])
    run_loop(client, "goal", TOOLS, log=quiet)
    error = client.seen[1][-1].tool_results[0]["result"]["error"]
    assert "invalid arguments for count_lines" in error and "path" in error


def test_unknown_tool_comes_back_as_an_error_result():
    """A tool name that doesn't exist is reported, not crashed on."""
    client = FakeClient([calls_reply(ToolCall("1", "delete_file", {})), text_reply("ok")])
    run_loop(client, "goal", TOOLS, log=quiet)
    assert "no tool called delete_file" in client.seen[1][-1].tool_results[0]["result"]["error"]


def test_honest_check_rejects_an_invented_ticket():
    """A ticket the source doesn't contain is not 'done'; the loop asks again."""
    client = FakeClient([text_reply("Fixes JIRA-4821."), text_reply("No ticket is referenced.")])
    answer, reason, _ = run_loop(client, "goal", TOOLS, honest_ticket_check("diff ..."),
                                 log=quiet)
    assert reason == "done at step 2" and "No ticket is referenced" in answer
    assert client.seen[1][-1].text.startswith("Not done")


def test_honest_check_accepts_a_real_ticket():
    """A ticket that is in the source passes."""
    check = honest_ticket_check("Implements JIRA-12 in coupons.py")
    assert check("Implements JIRA-12.") and not check("Implements JIRA-13.")
