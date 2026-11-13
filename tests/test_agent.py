"""The hand-written loop, with a fake model client (no network)."""

from autodocs.agent import NO_MORE_INFO, honest_ticket_check, run_loop
from autodocs.llm import ModelReply, Usage


class FakeClient:
    """Replays scripted replies and records the messages it was sent."""

    model = "gemini-3.5-flash-lite"

    def __init__(self, replies: list[str]):
        """Script the replies, in order (the last one repeats)."""
        self.replies = replies
        self.seen = []

    def reply(self, system, messages):
        """Return the next scripted reply with a fixed token cost."""
        self.seen.append([dict(m) for m in messages])
        text = self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]
        return ModelReply(text, Usage(input_tokens=1000, output_tokens=10))

    def count_tokens(self, messages):
        """Pretend count."""
        return 42


def test_any_answer_is_done_by_default():
    """With the default check, the first ANSWER ends the run."""
    answer, reason, usage = run_loop(FakeClient(["ASK: which branch?", "ANSWER: done"]), "goal",
                                     log=lambda _: None)
    assert (answer, reason) == ("ANSWER: done", "done at step 2")
    assert usage.input_tokens == 2000


def test_cap_stops_a_model_that_never_answers():
    """A model that only asks is stopped at the cap, with no answer."""
    answer, reason, _ = run_loop(FakeClient(["ASK: more?"]), "goal", max_steps=3,
                                 log=lambda _: None)
    assert answer is None and reason == "step cap of 3 reached"


def test_asks_get_the_no_more_info_observation():
    """An ASK is answered with the fixed observation; the reply comes before it."""
    client = FakeClient(["ASK: more?", "ANSWER: ok"])
    run_loop(client, "goal", log=lambda _: None)
    assert [m["role"] for m in client.seen[1]] == ["user", "model", "user"]
    assert client.seen[1][-1]["text"] == NO_MORE_INFO


def test_honest_check_rejects_an_invented_ticket():
    """A ticket the source doesn't contain is not 'done'; the loop asks again."""
    source = "diff --git a/x.py ..."
    client = FakeClient(["ANSWER: Fixes JIRA-4821.", "ANSWER: No ticket is referenced."])
    answer, reason, _ = run_loop(client, "goal", honest_ticket_check(source), log=lambda _: None)
    assert reason == "done at step 2" and "No ticket is referenced" in answer
    assert client.seen[1][-1]["text"].startswith("Not done")


def test_honest_check_accepts_a_real_ticket():
    """A ticket that is in the source passes."""
    check = honest_ticket_check("Implements JIRA-12 in coupons.py")
    assert check("ANSWER: Implements JIRA-12.") and not check("ANSWER: Implements JIRA-13.")
