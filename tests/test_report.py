"""The report table."""

from autodocs.report import coverage, docstrings_edited, table

RECORD = {
    "branch": "feat/x", "model": "gemini-3.5-flash-lite", "stop_reason": "done", "steps": 3,
    "tool_calls": 2, "usage": {"input_tokens": 5000, "output_tokens": 300},
    "cost_usd": 0.0017, "changed": {"functions": ["a.py::f", "a.py::g"], "unparseable": []},
    "writeup": {"functions": [{"path": "a.py", "function": "f"}], "could_not_determine": ["x"]},
    "docstring_patch": '+++ b/a.py\n+    """New."""\n-    """Old."""\n',
}


def test_coverage_counts_missed_functions():
    """Functions the write-up leaves out are reported."""
    assert coverage(RECORD) == (1, 2, ["a.py::g"])


def test_table_row():
    """One row per run with the key numbers."""
    row = table([RECORD]).splitlines()[2]
    assert "`feat/x`" in row and "1/2" in row and "0.00170" in row
    assert docstrings_edited(RECORD) == 1
