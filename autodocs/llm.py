"""The model interface: every model call goes through ModelClient, so providers can be swapped."""

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx2
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

# Dollars per 1M tokens, from https://aistudio.google.com/docs/pricing (checked 2026-11-13).
# Output prices include thinking tokens. Re-check before every batch: prices change.
PRICES_USD_PER_MILLION = {
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.6-flash": {"input": 0.75, "output": 3.75},  # until 2026-12-31
}

# The adapter's own retry policy. The SDK retries these status codes with exponential
# back-off; 400 (bad request) and 429 (quota) are deliberately NOT on the list.
RETRY_STATUS_CODES = [408, 500, 502, 503, 504]
RETRY_ATTEMPTS = 3          # including the first call
REQUEST_TIMEOUT_S = 60      # per attempt: the worst case is about 3 x 60 s plus back-off
MAX_RATE_LIMIT_WAIT_S = 60  # wait out a per-minute 429 only if Google asks for less than this
MAX_OUTPUT_TOKENS = 4096    # hard cap per call; the model never sees it


class ModelError(Exception):
    """The model call failed in a way the agent cannot fix."""


class BadRequest(ModelError):
    """400: our request is wrong. Never retried: it would fail the same way every time."""


class AuthError(ModelError):
    """401/403: the key is missing, wrong or not allowed to use this model."""


class RateLimited(ModelError):
    """429 that resets within a minute (requests per minute)."""


class QuotaExceeded(ModelError):
    """429 that will not reset soon: e.g. the free tier's requests-per-day limit."""


class ModelUnavailable(ModelError):
    """5xx still failing after the SDK's retries (e.g. 503 high demand)."""


class ModelTimeout(ModelError):
    """No answer within the request timeout, after retries."""


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

    def reply(self, system: str, history: list[Message], tools: list,
              output_schema: type[BaseModel] | None = None) -> ModelReply:
        """Send the conversation and the tools; with output_schema, the answer must fit it."""
        ...

    def count_tokens(self, history: list[Message]) -> int:
        """Ask the provider how many input tokens the conversation is."""
        ...


def cost_usd(model: str, usage: Usage) -> float:
    """Cost of the usage at the published rates."""
    price = PRICES_USD_PER_MILLION[model]
    return (usage.input_tokens * price["input"] + usage.output_tokens * price["output"]) / 1e6


def classify_429(exc: errors.ClientError) -> ModelError:
    """Tell a short per-minute limit (worth waiting for) from a daily quota (stop)."""
    details = (exc.details or {}).get("error", {}).get("details", [])
    delay_s, per_day = None, False
    for item in details:
        if item.get("@type", "").endswith("RetryInfo"):
            delay_s = float(item.get("retryDelay", "0s").rstrip("s") or 0)
        for violation in item.get("violations", []):
            per_day = per_day or "PerDay" in violation.get("quotaId", "")
    if per_day or delay_s is None or delay_s > MAX_RATE_LIMIT_WAIT_S:
        wait = f"; resets in {delay_s / 3600:.1f} h" if delay_s else ""
        return QuotaExceeded(f"Gemini returned 429 (quota used up{wait}): {exc.message}")
    error = RateLimited(f"Gemini returned 429 (rate limit, retry in {delay_s:.0f} s)")
    error.retry_after = delay_s
    return error


class GeminiClient:
    """ModelClient for Google's Gemini API (google-genai, generate_content)."""

    def __init__(self, api_key: str, model: str, sleep=time.sleep):
        """Create the SDK client for one model, with our timeout and retry policy."""
        if model not in PRICES_USD_PER_MILLION:
            raise ValueError(f"no price recorded for {model}; add it to PRICES_USD_PER_MILLION")
        self.model = model
        self.sleep = sleep
        retry = types.HttpRetryOptions(attempts=RETRY_ATTEMPTS, initial_delay=2.0, max_delay=20.0,
                                       http_status_codes=RETRY_STATUS_CODES)
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_S * 1000, retry_options=retry))

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

    def reply(self, system: str, history: list[Message], tools: list,
              output_schema: type[BaseModel] | None = None) -> ModelReply:
        """Send the conversation and tools to Gemini and return its next turn."""
        config = types.GenerateContentConfig(
            system_instruction=system, tools=self.to_tools(tools),
            # We run tools ourselves: that is the agent loop we are writing.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        config.max_output_tokens = MAX_OUTPUT_TOKENS
        if output_schema is not None:
            # The final answer must be JSON that fits the pydantic model.
            config.response_mime_type = "application/json"
            config.response_schema = output_schema
        contents = self.to_contents(history)
        for _ in range(2):  # at most two waits for a per-minute rate limit
            try:
                return self.call(contents, config)
            except RateLimited as exc:
                self.sleep(exc.retry_after)
        return self.call(contents, config)

    def call(self, contents: list, config: types.GenerateContentConfig) -> ModelReply:
        """One SDK call, with its errors mapped to ours (most specific first)."""
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=contents, config=config)
        except errors.ClientError as exc:  # 4xx
            if exc.code == 429:
                raise classify_429(exc) from exc
            if exc.code in (401, 403):
                raise AuthError(f"Gemini refused the key ({exc.code}): {exc.message}") from exc
            raise BadRequest(f"Gemini rejected the request ({exc.code}): {exc.message}") from exc
        except errors.ServerError as exc:  # 5xx, already retried by the SDK
            raise ModelUnavailable(f"Gemini server error ({exc.code}) after "
                                   f"{RETRY_ATTEMPTS} attempts: {exc.message}") from exc
        except httpx2.TimeoutException as exc:
            raise ModelTimeout(f"no answer within {REQUEST_TIMEOUT_S} s, "
                               f"{RETRY_ATTEMPTS} attempts") from exc
        return self.to_reply(response)

    def to_reply(self, response: types.GenerateContentResponse) -> ModelReply:
        """Turn a Gemini response into a ModelReply."""
        if not response.candidates or response.candidates[0].content is None:
            raise ModelError(f"Gemini returned no answer (prompt feedback: "
                             f"{response.prompt_feedback})")
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
