"""Tools: an ordinary typed function plus a description the model reads."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError, create_model


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
    return {"result": tool.function(**valid.model_dump())}
