"""The command line."""

import argparse

import pytest

from autodocs.cli import InputError, main, to_markdown, validate
from autodocs.writeup import FunctionNote, Writeup


def test_missing_key_exits_2(monkeypatch, capsys):
    """Without GEMINI_API_KEY the run doesn't start."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert main(["feat/x", "--repo", "."]) == 2
    assert "Not started: GEMINI_API_KEY" in capsys.readouterr().err


def test_markdown_lists_unknowns_or_says_nothing():
    """The write-up renders every section, including an empty 'could not determine'."""
    writeup = Writeup(title="feat: x", summary="s", changes=["c"], release_note="",
                      functions=[FunctionNote(path="a.py", function="f", body="empty",
                                              what_it_does="does f",
                                              docstring_updated=False)],
                      could_not_determine=[])
    text = to_markdown("feat/x", writeup)
    assert "- `a.py::f` (empty): does f" in text
    assert "## Could not determine\n- Nothing." in text
    assert "No user-visible change." in text


def args_for(repo, branch="feat/x", base="main", **extra) -> argparse.Namespace:
    """Arguments as parse_args would build them."""
    return argparse.Namespace(repo=str(repo), branch=branch, base=base, max_steps=12,
                              budget_tokens=60_000, max_seconds=300, **extra)


def test_validation_passes_for_a_real_branch(sample_repo):
    """A repo with a changed branch is accepted."""
    validate(args_for(sample_repo), "key", "gemini-3.5-flash-lite")


@pytest.mark.parametrize("change, message", [
    ({"branch": "feat/nope"}, "does not exist"),
    ({"branch": "main"}, "no changes"),
    ({"repo": "/"}, "not a git repository"),
])
def test_validation_rejects_before_spending(sample_repo, change, message):
    """Unknown branch, empty diff and a non-repo are caught without a model call."""
    values = {"repo": sample_repo, **change}
    with pytest.raises(InputError, match=message):
        validate(args_for(**values), "key", "gemini-3.5-flash-lite")


def test_validation_rejects_unknown_model_and_tiny_limits(sample_repo):
    """An unpriced model or silly limits are refused."""
    with pytest.raises(InputError, match="no price"):
        validate(args_for(sample_repo), "key", "gemini-9")
    small = args_for(sample_repo)
    small.max_steps = 0
    with pytest.raises(InputError, match="limits too small"):
        validate(small, "key", "gemini-3.5-flash-lite")


def test_facts_override_the_model_for_unparseable_files():
    """A function in a broken file is forced to 'file does not parse', and the reason added."""
    from autodocs.writeup import correct_against_facts
    writeup = Writeup(title="t", summary="s", changes=[], release_note="",
                      functions=[FunctionNote(path="r/stock.py", function="low_stock",
                                              body="implemented", what_it_does="guess",
                                              docstring_updated=False)],
                      could_not_determine=["r/stock.py"])
    corrections = correct_against_facts(writeup, ["r/stock.py"])
    assert writeup.functions[0].body == "file does not parse"
    assert "r/stock.py does not parse, so its functions could not be read" in \
        writeup.could_not_determine
    assert len(corrections) == 2
    assert correct_against_facts(writeup, ["r/stock.py"]) == []  # already correct
