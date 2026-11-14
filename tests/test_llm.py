"""The Gemini adapter's conversion of our messages (no network)."""

import httpx2
import pytest
from google.genai import errors, types

from autodocs.llm import (
    RETRY_STATUS_CODES,
    BadRequest,
    GeminiClient,
    Message,
    ModelTimeout,
    ModelUnavailable,
    QuotaExceeded,
    RateLimited,
    Usage,
    classify_429,
    cost_usd,
)


def test_all_results_go_back_in_one_message_with_their_ids():
    """Two results for one turn become ONE user Content, each part carrying its call's id."""
    client = GeminiClient("not-a-real-key", "gemini-3.5-flash-lite")
    results = [{"id": "a1", "name": "count_lines", "result": {"result": 7}},
               {"id": "b2", "name": "count_lines", "result": {"result": 8}}]
    contents = client.to_contents([Message(role="user", text="goal"),
                                   Message(role="tool", tool_results=results)])
    assert len(contents) == 2 and contents[1].role == "user"
    responses = [part.function_response for part in contents[1].parts]
    assert [(r.id, r.response) for r in responses] == [("a1", {"result": 7}), ("b2", {"result": 8})]


def test_an_output_schema_asks_gemini_for_json_in_that_shape(monkeypatch):
    """With output_schema, the request carries a JSON MIME type and the pydantic model."""
    from google.genai import types

    from autodocs.writeup import Writeup

    client = GeminiClient("not-a-real-key", "gemini-3.5-flash-lite")
    sent = {}

    def fake_generate(model, contents, config):
        """Record the config and return a one-part text answer."""
        sent["config"] = config
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(
                role="model", parts=[types.Part(text="{}")]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=10, candidates_token_count=2))

    monkeypatch.setattr(client.client.models, "generate_content", fake_generate)
    reply = client.reply("system", [Message(role="user", text="goal")], [], Writeup)
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].response_schema is Writeup
    assert reply.text == "{}" and reply.usage.input_tokens == 10


def lite(**kwargs) -> GeminiClient:
    """A client that never touches the network unless a test patches it."""
    return GeminiClient("not-a-real-key", "gemini-3.5-flash-lite", **kwargs)


def error_429(quota_id: str, delay: str) -> errors.ClientError:
    """A 429 shaped like Gemini's real one."""
    return errors.ClientError(429, {"error": {"code": 429, "message": "quota", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": quota_id}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]}})


def text_response(text: str) -> types.GenerateContentResponse:
    """A one-part answer."""
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model",
                                                          parts=[types.Part(text=text)]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=1))


def test_classify_429():
    """A daily quota stops; a per-minute limit is worth a short wait."""
    daily = classify_429(error_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "55725s"))
    assert isinstance(daily, QuotaExceeded) and "15.5 h" in str(daily)
    minute = classify_429(error_429("GenerateRequestsPerMinutePerProjectPerModel", "12s"))
    assert isinstance(minute, RateLimited) and minute.retry_after == 12


def test_retry_policy_never_includes_400_or_429():
    """The SDK only retries transient server errors and timeouts."""
    assert 400 not in RETRY_STATUS_CODES and 429 not in RETRY_STATUS_CODES
    assert 503 in RETRY_STATUS_CODES


def test_rate_limit_waits_then_succeeds(monkeypatch):
    """A per-minute 429 is waited out once, then the call succeeds."""
    waits = []
    client = lite(sleep=waits.append)
    responses = [error_429("PerMinute", "7s"), text_response("{}")]

    def fake_generate(**kwargs):
        """Raise the 429 first, then answer."""
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(client.client.models, "generate_content", fake_generate)
    assert client.reply("s", [Message(role="user", text="hi")], []).text == "{}"
    assert waits == [7.0]


def test_bad_request_is_not_retried(monkeypatch):
    """A 400 is raised at once, after exactly one call."""
    client, calls = lite(), []

    def bad(**kwargs):
        """Always 400."""
        calls.append(1)
        raise errors.ClientError(400, {"error": {"code": 400, "message": "bad",
                                                 "status": "INVALID_ARGUMENT"}})

    monkeypatch.setattr(client.client.models, "generate_content", bad)
    with pytest.raises(BadRequest):
        client.reply("s", [Message(role="user", text="hi")], [])
    assert calls == [1]


def test_server_error_becomes_model_unavailable(monkeypatch):
    """A 503 that outlasts the SDK's retries is reported as ModelUnavailable."""
    client = lite()

    def busy(**kwargs):
        """Always 503."""
        raise errors.ServerError(503, {"error": {"code": 503, "message": "high demand",
                                                 "status": "UNAVAILABLE"}})

    monkeypatch.setattr(client.client.models, "generate_content", busy)
    with pytest.raises(ModelUnavailable, match="503"):
        client.reply("s", [Message(role="user", text="hi")], [])


def test_timeout_becomes_model_timeout(monkeypatch):
    """An HTTP timeout is reported as ModelTimeout."""
    client = lite()

    def slow(**kwargs):
        """Time out."""
        raise httpx2.ReadTimeout("The read operation timed out")

    monkeypatch.setattr(client.client.models, "generate_content", slow)
    with pytest.raises(ModelTimeout):
        client.reply("s", [Message(role="user", text="hi")], [])


def test_every_call_carries_the_output_cap(monkeypatch):
    """max_output_tokens is set on every request: a single call can't run away."""
    client, seen = lite(), []

    def capture(model, contents, config):
        """Record the config."""
        seen.append(config.max_output_tokens)
        return text_response("{}")

    monkeypatch.setattr(client.client.models, "generate_content", capture)
    client.reply("s", [Message(role="user", text="hi")], [])
    assert seen == [4096]



def test_cached_tokens_are_billed_at_the_cache_price():
    """Cached input costs a tenth here; the rest is billed as normal input."""
    usage = Usage(input_tokens=1_000_000, output_tokens=0, thinking_tokens=0,
                  cached_tokens=400_000)
    assert cost_usd("gemini-3.5-flash-lite", usage) == (600_000 * 0.30 + 400_000 * 0.03) / 1e6


def test_cut_off_answer_is_flagged():
    """finish_reason MAX_TOKENS marks the reply as cut off."""
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(finish_reason=types.FinishReason.MAX_TOKENS,
                                    content=types.Content(role="model",
                                                          parts=[types.Part(text='{"ti')]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=1))
    assert lite().to_reply(response).cut_off is True
