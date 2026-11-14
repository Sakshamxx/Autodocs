"""The OpenAI-style adapter (used for Ollama), without a server."""

from types import SimpleNamespace

import openai
import pytest

from autodocs.llm import Message, ModelUnavailable, OpenAICompatibleClient
from autodocs.tools import Tool
from autodocs.writeup import Writeup


def read_diff() -> str:
    """Return the diff."""
    return "diff"


def completion(content="", calls=(), finish="stop", prompt=100, completion_tokens=10):
    """A fake Chat Completions response."""
    tool_calls = [SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=n, arguments=a))
                  for i, (n, a) in enumerate(calls)] or None
    message = SimpleNamespace(content=content, tool_calls=tool_calls,
                              model_dump=lambda **kw: {"role": "assistant", "content": content})
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion_tokens,
                            prompt_tokens_details=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish)],
                           usage=usage)


@pytest.fixture
def client():
    """An adapter pointed at a server that is never called."""
    return OpenAICompatibleClient("qwen3-4b-32k", base_url="http://localhost:1/v1")


def test_messages_include_system_and_one_tool_message_per_result(client):
    """Tool results become 'tool' messages carrying the call id."""
    history = [Message(role="user", text="hi"),
               Message(role="tool", tool_results=[{"id": "c0", "name": "read_diff",
                                                   "result": {"result": "x"}}])]
    messages = client.to_messages("system", history)
    assert messages[0] == {"role": "system", "content": "system"}
    assert messages[2] == {"role": "tool", "tool_call_id": "c0", "content": '{"result": "x"}'}


def test_tools_first_then_schema(client, monkeypatch):
    """With tools and a schema, the schema is asked for only after the tools stop."""
    sent = []
    replies = [completion("I am done"), completion('{"title": "x"}', prompt=50)]

    def create(**kwargs):
        """Record what was sent and reply in order."""
        sent.append(("tools" in kwargs, "response_format" in kwargs))
        return replies.pop(0)
    monkeypatch.setattr(client.client.chat.completions, "create", create)
    reply = client.reply("s", [Message(role="user", text="go")],
                         [Tool.from_function(read_diff)], Writeup)
    assert sent == [(True, False), (False, True)]
    assert reply.text == '{"title": "x"}' and reply.usage.input_tokens == 150


def test_bad_tool_json_and_cut_off(client):
    """Unparseable arguments become a validation problem; 'length' marks a cut-off."""
    reply = client.to_reply(completion(calls=[("read_diff", "{not json")], finish="length"))
    assert reply.tool_calls[0].args == {"invalid_json": "{not json"}
    assert reply.cut_off is True


def test_unreachable_server(client, monkeypatch):
    """A connection failure says where it tried to connect."""
    def refuse(**kwargs):
        """Pretend the server is down."""
        raise openai.APIConnectionError(request=None)
    monkeypatch.setattr(client.client.chat.completions, "create", refuse)
    with pytest.raises(ModelUnavailable, match="is it running"):
        client.reply("s", [Message(role="user", text="go")], [])
