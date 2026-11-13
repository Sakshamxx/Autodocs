"""The model interface: every model call goes through ModelClient, so providers can be swapped."""

from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types

# Dollars per 1M tokens, from https://ai.google.dev/gemini-api/docs/pricing (checked 2026-11-13).
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
class ModelReply:
    """The model's text and what the call cost in tokens."""

    text: str
    usage: Usage


class ModelClient(Protocol):
    """Anything that can answer a conversation. The agent loop only talks to this."""

    model: str

    def reply(self, system: str, messages: list[dict]) -> ModelReply:
        """Send the conversation and return the model's next turn."""
        ...

    def count_tokens(self, messages: list[dict]) -> int:
        """Ask the provider how many input tokens the messages are."""
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

    def to_contents(self, messages: list[dict]) -> list[types.Content]:
        """Turn {'role': 'user'|'model', 'text': ...} messages into Gemini Content objects."""
        return [types.Content(role=m["role"], parts=[types.Part(text=m["text"])])
                for m in messages]

    def reply(self, system: str, messages: list[dict]) -> ModelReply:
        """Send the conversation to Gemini and return its next turn."""
        response = self.client.models.generate_content(
            model=self.model, contents=self.to_contents(messages),
            config=types.GenerateContentConfig(system_instruction=system))
        meta = response.usage_metadata
        output = (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
        return ModelReply(response.text or "", Usage(meta.prompt_token_count or 0, output))

    def count_tokens(self, messages: list[dict]) -> int:
        """Ask Gemini how many input tokens the messages are (the system prompt isn't counted)."""
        return self.client.models.count_tokens(model=self.model,
                                               contents=self.to_contents(messages)).total_tokens
