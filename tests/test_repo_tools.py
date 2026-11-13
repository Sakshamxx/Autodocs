"""The three repository tools and the workspace."""

from pathlib import Path

import pytest

from autodocs.repo_tools import Workspace, make_repo_tools


@pytest.fixture
def tools(sample_repo, tmp_path):
    """Workspace on feat/x and its tools by name."""
    workspace = Workspace(str(sample_repo), "feat/x", "main", tmp_path / "work")
    return workspace, {tool.name: tool.function for tool in make_repo_tools(workspace)}


def test_read_diff_shows_the_branch_change(tools):
    """The diff contains the changed line and the new file."""
    _, t = tools
    diff = t["read_diff"]()
    assert "- discount" in diff and "app/broken.py" in diff


def test_open_file_numbers_lines_and_refuses_escapes(tools):
    """Lines are numbered; paths outside the repo are refused."""
    _, t = tools
    assert "    1  def total(prices, discount=0):" in t["open_file"]("app/shop.py", 1, 1)
    assert t["open_file"]("../../etc/passwd").startswith("error")
    assert t["open_file"]("app/nope.py").startswith("error")


def test_write_docstring_replaces_and_inserts(tools):
    """An existing docstring is replaced; a method without one gets one; the file still parses."""
    workspace, t = tools
    t["write_docstring"]("app/shop.py", "total", "Sum the prices, minus a discount.")
    t["write_docstring"]("app/shop.py", "Cart.size", "Number of items in the cart.")
    source = (workspace.root / "app" / "shop.py").read_text()
    assert '    """Sum the prices, minus a discount."""\n' in source
    assert '        """Number of items in the cart."""\n        return 0' in source
    assert "+" in workspace.docstring_patch()


def test_same_docstring_is_a_no_op(tools):
    """Writing the docstring a function already has changes nothing and says so."""
    workspace, t = tools
    assert "nothing changed" in t["write_docstring"]("app/shop.py", "total", "Sum the prices.")
    assert workspace.docstring_patch() == ""


def test_write_docstring_refusals(tools):
    """Unknown functions, unchanged files and unparseable files are not edited."""
    workspace, t = tools
    assert t["write_docstring"]("app/shop.py", "missing", "x").startswith("error")
    assert t["write_docstring"]("app/broken.py", "oops", "x").startswith("error: app/broken.py "
                                                                       "does not parse")
    (workspace.root / "README.md").write_text("x")
    assert "not changed" in t["write_docstring"]("README.md", "x", "x")


def test_changed_functions_ignore_docstring_only_edits(tools):
    """Body changes and new functions count; untouched ones don't; broken files are listed."""
    workspace, _ = tools
    changed = workspace.changed_functions()
    assert changed == {"functions": ["app/shop.py::total", "app/shop.py::Cart.size"],
                       "unparseable": ["app/broken.py"]}


def test_relative_workspace_path(sample_repo, tmp_path, monkeypatch):
    """A relative workspace path (as the CLI passes) clones to the right place."""
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(str(sample_repo), "feat/x", "main", Path(".work") / "feat_x")
    assert workspace.root == (tmp_path / ".work" / "feat_x").resolve()
    assert (workspace.root / "app" / "shop.py").is_file()
