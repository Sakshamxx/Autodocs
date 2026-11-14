"""Tracing to Langfuse: one span per run, a generation per model call, an entry per tool call.

Off unless LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, so runs work without an account.
"""

import os
from contextlib import contextmanager, nullcontext


class Tracer:
    """Sends observations to Langfuse, or does nothing when no keys are set."""

    def __init__(self, enabled: bool | None = None):
        """Connect to Langfuse if keys are present (LANGFUSE_BASE_URL picks the region)."""
        if enabled is None:
            enabled = bool(os.environ.get("LANGFUSE_PUBLIC_KEY")
                           and os.environ.get("LANGFUSE_SECRET_KEY"))
        self.client = None
        if enabled:
            from langfuse import Langfuse  # imported only when tracing is on
            self.client = Langfuse()

    @contextmanager
    def run(self, name: str, goal: str):
        """Wrap a whole agent run; yields a function that records its outcome."""
        if self.client is None:
            yield lambda **_: None
            return
        with self.client.start_as_current_observation(name=name, as_type="span",
                                                      input=goal) as span:
            yield lambda **fields: span.update(**fields)

    def model_call(self, model: str, step: int):
        """Context for one model call; call .update(...) on what it yields."""
        if self.client is None:
            return nullcontext(_NoOp())
        return self.client.start_as_current_observation(name=f"step {step}", as_type="generation",
                                                        model=model)

    def tool_call(self, name: str, args: dict, result: dict) -> None:
        """Record one finished tool call."""
        if self.client is None:
            return
        level = "ERROR" if "error" in result else "DEFAULT"
        with self.client.start_as_current_observation(name=name, as_type="tool", input=args,
                                                      output=result, level=level):
            pass

    def flush(self) -> None:
        """Send everything now: short scripts otherwise exit before traces are delivered."""
        if self.client is not None:
            self.client.flush()


class _NoOp:
    """Stands in for an observation when tracing is off."""

    def update(self, **_) -> None:
        """Ignore the update."""
