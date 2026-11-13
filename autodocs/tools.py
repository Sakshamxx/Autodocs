"""Tools: an ordinary typed function plus a description the model reads."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError, create_model


class ToolError(Exception):
    """An expected tool failure (missing file, unparseable code); sent to the model as an error."""


class StrictArgs(BaseModel):
    """Base for tool arguments: no extra fields, no silent type coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass
class Tool:
    """A function the agent may call."""

    name: str
    description: str
    args_model: type[BaseModel]
    function: Callable

    @classmethod
    def from_function(cls, function: Callable) -> "Tool":
        """Build a Tool: type hints become the schema, the docstring the description."""
        fields = {}
        for name, param in inspect.signature(function).parameters.items():
            if param.annotation is inspect.Parameter.empty:
                raise TypeError(f"{function.__name__}: argument '{name}' needs a type hint")
            default = ... if param.default is inspect.Parameter.empty else param.default
            fields[name] = (param.annotation, default)
        args_model = create_model(f"{function.__name__}_args", __base__=StrictArgs, **fields)
        description = inspect.getdoc(function)
        if not description:
            raise TypeError(f"{function.__name__} needs a docstring: it is what the model reads")
        return cls(function.__name__, description, args_model, function)


def run_tool(tools: dict[str, Tool], name: str, args: dict) -> dict:
    """Validate the arguments, run the tool, and return a result for the model."""
    tool = tools.get(name)
    if tool is None:
        return {"error": f"there is no tool called {name}; available: {sorted(tools)}"}
    try:
        valid = tool.args_model.model_validate(args)
    except ValidationError as exc:
        problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        return {"error": f"invalid arguments for {name}: {'; '.join(problems)}"}
    try:
        return {"result": tool.function(**valid.model_dump())}
    except ToolError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # errors are data: the model reads this and decides what to do
        return {"error": f"{name} failed: {type(exc).__name__}: {exc}"}


class FailureInjector:
    """Fail chosen tool calls on purpose, to see how the agent copes (AUTODOCS_FAIL_TOOL_CALLS)."""

    def __init__(self, setting: str = ""):
        """setting: '' (off), 'every', or comma-separated call numbers such as '2,3'."""
        self.every = setting.strip().lower() == "every"
        self.numbers = {int(n) for n in setting.split(",") if n.strip().isdigit()}
        self.count = 0

    def should_fail(self) -> bool:
        """Count this call and say whether to fail it."""
        self.count += 1
        return self.every or self.count in self.numbers
