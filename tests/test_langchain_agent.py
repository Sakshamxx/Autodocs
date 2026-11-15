"""The LangChain engine's adapters, without calling the network."""

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from autodocs.langchain_agent import is_tool_error, to_langchain_tool, usage_of
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


def test_langchain_argument_errors_are_counted():
    """Bad arguments are refused by LangChain itself; the run must still count them as errors."""
    tool = Tool.from_function(count_lines)
    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode([to_langchain_tool(tool, {tool.name: tool})]))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    bad_args = {"name": "count_lines", "args": {"path": 5}, "id": "1"}
    call = AIMessage(content="", tool_calls=[bad_args])
    reply = graph.compile().invoke({"messages": [call]})["messages"][-1]
    assert reply.status == "error" and is_tool_error(reply)


def test_tool_error_covers_both_shapes():
    """Our own error result counts too; a normal result doesn't."""
    assert is_tool_error(ToolMessage(content='{"error": "x is not a file"}', tool_call_id="1"))
    assert not is_tool_error(ToolMessage(content='{"result": 3}', tool_call_id="1"))
