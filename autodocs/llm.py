"""The model interface: every model call goes through ModelClient, so providers can be swapped."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from google import genai
from google.genai import types

# Dollars per 1M tokens, from https://aistudio.google.com/docs/pricing (checked 2026-11-13).
# Output prices include thinking tokens. Re-check before every batch: prices change.
PRICES_USD_PER_MILLION = {
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.6-flash": {"input": 0.75, "output": 3.75},  # until 2026-12-31
}


@dataclass
class Usage:
    """Tokens used by one or more model calls."""

    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: "Usage") -> None:
        """Add another call's tokens to this total."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


@dataclass
class ToolCall:
    """One tool the model asked us to run."""

    id: str | None
    name: str
    args: dict[str, Any]


@dataclass
class Message:
    """One entry in the conversation: the agent's whole memory is a list of these."""

    role: str  # "user", "model" or "tool"
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)  # [{"id", "name", "result"}]
    raw: Any = None  # the provider's own copy of a model turn, sent back unchanged


@dataclass
class ModelReply:
    """What came back from one model call."""

    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    message: Message


class ModelClient(Protocol):
    """Anything that can answer a conversation. The agent loop only talks to this."""

    model: str

    def reply(self, system: str, history: list[Message], tools: list) -> ModelReply:
        """Send the conversation (and the tools on offer) and return the model's next turn."""
        ...

    def count_tokens(self, history: list[Message]) -> int:
        """Ask the provider how many input tokens the conversation is."""
        ...


def cost_usd(model: str, usage: Usage) -> float:
    """Cost of the usage at the published rates."""
    price = PRICES_USD_PER_MILLION[model]
    return (usage.input_tokens * price["input"] + usage.output_tokens * price["output"]) / 1e6


class GeminiClient:
    """ModelClient for Google's Gemini API (google-genai, generate_content)."""

    def __init__(self, api_key: str, model: str):
        """Create the SDK client for one model."""
        if model not in PRICES_USD_PER_MILLION:
            raise ValueError(f"no price recorded for {model}; add it to PRICES_USD_PER_MILLION")
        self.model = model
        self.client = genai.Client(api_key=api_key)

    def to_contents(self, history: list[Message]) -> list[types.Content]:
        """Convert our messages into Gemini Content objects."""
        contents = []
        for message in history:
            if message.role == "model":
                # The raw turn keeps Gemini's thought signatures, which it requires back.
                contents.append(message.raw)
            elif message.role == "tool":
                # Every result for one model turn goes back together, in one message.
                # The id ties each result to the call that asked for it.
                parts = [types.Part(function_response=types.FunctionResponse(
                    id=r["id"], name=r["name"], response=r["result"]))
                    for r in message.tool_results]
                contents.append(types.Content(role="user", parts=parts))
            else:
                contents.append(types.Content(role="user", parts=[types.Part(text=message.text)]))
        return contents

    def to_tools(self, tools: list) -> list[types.Tool]:
        """Describe our tools to Gemini: name, description and JSON schema."""
        if not tools:
            return []
        declarations = [types.FunctionDeclaration(
            name=tool.name, description=tool.description,
            parameters_json_schema=tool.args_model.model_json_schema()) for tool in tools]
        return [types.Tool(function_declarations=declarations)]

    def reply(self, system: str, history: list[Message], tools: list) -> ModelReply:
        """Send the conversation and tools to Gemini and return its next turn."""
        config = types.GenerateContentConfig(
            system_instruction=system, tools=self.to_tools(tools),
            # We run tools ourselves: that is the agent loop we are writing.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        response = self.client.models.generate_content(
            model=self.model, contents=self.to_contents(history), config=config)
        content = response.candidates[0].content
        calls = [ToolCall(id=part.function_call.id, name=part.function_call.name,
                          args=dict(part.function_call.args or {}))
                 for part in content.parts or [] if part.function_call]
        text = "".join(part.text for part in content.parts or []
                       if part.text and not part.thought)
        meta = response.usage_metadata
        usage = Usage(meta.prompt_token_count or 0,
                      (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0))
        message = Message(role="model", text=text, tool_calls=calls, raw=content)
        return ModelReply(text, calls, usage, message)

    def count_tokens(self, history: list[Message]) -> int:
        """Ask Gemini how many input tokens the messages are (the system prompt isn't counted)."""
        return self.client.models.count_tokens(model=self.model,
                                               contents=self.to_contents(history)).total_tokens
