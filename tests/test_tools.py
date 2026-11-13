"""Tool.from_function and run_tool: what the model is shown, and what reaches the function."""

import pytest

from autodocs.practice_tools import count_lines, list_directory
from autodocs.tools import Tool, run_tool


def test_type_hints_become_the_schema_and_the_docstring_the_description():
    """The schema the model reads comes from the signature; nothing is typed twice."""
    tool = Tool.from_function(count_lines)
    schema = tool.args_model.model_json_schema()
    assert schema["properties"]["path"]["type"] == "string"
    assert schema["required"] == ["path"]
    assert tool.description.startswith("Return the number of lines")


def test_a_default_makes_an_argument_optional():
    """list_directory(path='.') is optional in the schema."""
    schema = Tool.from_function(list_directory).args_model.model_json_schema()
    assert "required" not in schema


def test_strict_mode_refuses_a_number_for_a_string():
    """Strict: 5 is not silently turned into '5'."""
    tools = {"count_lines": Tool.from_function(count_lines)}
    assert "error" in run_tool(tools, "count_lines", {"path": 5})


def test_extra_fields_are_refused():
    """An argument the function doesn't take is an error, not ignored."""
    tools = {"count_lines": Tool.from_function(count_lines)}
    assert "error" in run_tool(tools, "count_lines", {"path": "app/main.py", "lines": 3})


def test_a_missing_type_hint_is_caught_when_the_tool_is_built():
    """No type hint, no schema: refuse at build time, not at run time."""

    def broken(path):
        """Count lines."""
        return 0

    with pytest.raises(TypeError, match="needs a type hint"):
        Tool.from_function(broken)


def test_a_missing_docstring_is_caught_when_the_tool_is_built():
    """No docstring means the model has no description to read."""

    def silent(path: str) -> int:
        return 0

    with pytest.raises(TypeError, match="needs a docstring"):
        Tool.from_function(silent)


def test_the_practice_tools_stay_inside_practice():
    """A path that escapes practice/ gets nothing back."""
    assert count_lines("../pyproject.toml") == -1
    assert list_directory("..") == []
    assert count_lines("app/main.py") == 7


def test_show_line_counts_from_one():
    """The code matches the description: line 1 is the first line."""
    from autodocs.practice_tools import show_line

    assert show_line("app/utils.py", 1) == "def add(a, b):"
    assert show_line("app/utils.py", 0) == ""
