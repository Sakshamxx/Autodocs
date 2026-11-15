"""The run comparison."""

from autodocs.compare import compare, tool_sequence
from tests.test_report import RECORD


def test_tool_sequence_reads_both_trace_styles():
    """Hand-loop and LangChain trace lines both yield tool names."""
    record = {"trace": ["step 1 · read_diff({}) → {'result': 'x'}", "step 1 · 1 tool call(s)",
                        "step 2 · open_file → {\"result\": \"y\"}"]}
    assert tool_sequence(record) == ["read_diff", "open_file"]


def test_compare_table():
    """Both runs appear in one table."""
    b = {**RECORD, "engine": "langchain", "cost_usd": 0.004, "trace": []}
    table = compare({**RECORD, "trace": []}, b)
    assert "| engine | hand | langchain |" in table
    assert "| cost (USD) | 0.00170 | 0.00400 |" in table


def test_output_tokens_include_thinking():
    """Records since S6 keep thinking apart; the comparison adds it back into output."""
    usage = {**RECORD["usage"], "output_tokens": 934, "thinking_tokens": 284}
    table = compare({**RECORD, "usage": usage, "trace": []}, {**RECORD, "trace": []})
    assert "| output tokens | 1,218 |" in table
