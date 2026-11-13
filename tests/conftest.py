"""Shared fixtures: a fake model client and a small git repo with a branch."""

import subprocess
from pathlib import Path

import pytest

from autodocs.llm import Message, ModelReply, ToolCall, Usage


class FakeClient:
    """A ModelClient that replays scripted turns and records what it was sent."""

    model = "gemini-3.5-flash-lite"

    def __init__(self, turns: list):
        """turns: each is a list of (tool_name, args) calls, or a final answer string."""
        self.turns = list(turns)
        self.histories = []

    def reply(self, system, history, tools, output_schema=None) -> ModelReply:
        """Return the next scripted turn."""
        self.histories.append(list(history))
        turn = self.turns.pop(0) if self.turns else []  # nothing left: keep asking for nothing
        usage = Usage(input_tokens=1000, output_tokens=100)
        if isinstance(turn, str):
            return ModelReply(turn, [], usage, Message(role="model", text=turn))
        calls = [ToolCall(id=f"c{i}", name=name, args=args) for i, (name, args) in enumerate(turn)]
        return ModelReply("", calls, usage, Message(role="model", tool_calls=calls))

    def count_tokens(self, history) -> int:
        """Pretend count."""
        return 42


@pytest.fixture
def fake_client():
    """Return the FakeClient class so tests can script turns."""
    return FakeClient


def git(cwd: Path, *args: str) -> str:
    """Run git in a folder."""
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture
def sample_repo(tmp_path) -> Path:
    """A repo whose branch 'feat/x' changes one function and adds a broken file."""
    repo = tmp_path / "sample"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "app").mkdir()
    (repo / "app" / "shop.py").write_text(
        'def total(prices):\n    """Sum the prices."""\n    return sum(prices)\n\n\n'
        'def untouched():\n    return 1\n')
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "switch", "-q", "-c", "feat/x")
    (repo / "app" / "shop.py").write_text(
        'def total(prices, discount=0):\n    """Sum the prices."""\n'
        '    return sum(prices) - discount\n\n\ndef untouched():\n    return 1\n\n\n'
        'class Cart:\n    def size(self):\n        return 0\n')
    (repo / "app" / "broken.py").write_text("def oops(:\n    pass\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "feat")
    git(repo, "switch", "-q", "main")
    return repo
