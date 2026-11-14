"""The LangChain engine's adapters, without calling the network."""

from langchain_core.messages import AIMessage

from autodocs.langchain_agent import to_langchain_tool, usage_of
from autodocs.tools import Tool


def count_lines(path: str) -> int:
    """Count lines in a file."""
    return 3


def test_wrapped_tool_keeps_our_schema_and_errors_as_data():
    """The framework tool uses our args model, and bad arguments still come back as data."""
    tool = Tool.from_function(count_lines)
    wrapped = to_langchain_tool(tool, {tool.name: tool})
    assert wrapped.name == "count_lines" and wrapped.description == "Count lines in a file."
    assert wrapped.args_schema is tool.args_model
    assert wrapped.func(path="a.py") == {"result": 3}
    assert "error" in wrapped.func(path=5)


def test_usage_is_read_from_usage_metadata():
    """Tokens come from LangChain's usage_metadata; reasoning is split out as thinking."""
    message = AIMessage(content="", usage_metadata={
        "input_tokens": 1200, "output_tokens": 90, "total_tokens": 1290,
        "output_token_details": {"reasoning": 40}})
    usage = usage_of(message)
    assert (usage.input_tokens, usage.output_tokens, usage.thinking_tokens) == (1200, 50, 40)
