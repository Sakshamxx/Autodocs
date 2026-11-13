"""The command line."""

from autodocs.cli import main, to_markdown
from autodocs.writeup import FunctionNote, Writeup


def test_missing_key_exits_2(monkeypatch, capsys):
    """Without GEMINI_API_KEY the run doesn't start."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert main(["feat/x", "--repo", "."]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


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
