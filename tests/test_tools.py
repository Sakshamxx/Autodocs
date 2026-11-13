"""Tools: typed functions with strict argument checking."""

import pytest

from autodocs.tools import Tool, run_tool


def read_lines(path: str, start: int = 1) -> str:
    """Read lines from a file."""
    return f"{path}:{start}"


def test_type_hints_become_the_schema():
    """Required and optional arguments come from the signature; the docstring is the description."""
    tool = Tool.from_function(read_lines)
    schema = tool.args_model.model_json_schema()
    assert schema["required"] == ["path"]
    assert schema["properties"]["start"]["type"] == "integer"
    assert tool.description == "Read lines from a file."


def test_functions_need_hints_and_docstrings():
    """A tool without a docstring or a type hint is refused at definition time."""
    def no_doc(path: str) -> str:
        """Removed below, to test a tool with no description."""
        return path
    no_doc.__doc__ = None

    def no_hint(path):
        """Has a docstring."""
        return path
    with pytest.raises(TypeError, match="docstring"):
        Tool.from_function(no_doc)
    with pytest.raises(TypeError, match="type hint"):
        Tool.from_function(no_hint)


@pytest.mark.parametrize("args", [{"path": 5}, {"path": "a", "start": "2"},
                                  {"path": "a", "extra": 1}, {}])
def test_bad_arguments_become_error_results(args):
    """Wrong types, extra fields and missing fields return an error instead of running."""
    tools = {"read_lines": Tool.from_function(read_lines)}
    assert "error" in run_tool(tools, "read_lines", args)


def test_valid_call_and_unknown_tool():
    """A valid call runs; an unknown tool name is an error result."""
    tools = {"read_lines": Tool.from_function(read_lines)}
    assert run_tool(tools, "read_lines", {"path": "a", "start": 3}) == {"result": "a:3"}
    assert "no tool called" in run_tool(tools, "delete_repo", {})["error"]
