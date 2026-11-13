"""The Gemini adapter's conversion of our messages (no network)."""

from autodocs.llm import GeminiClient, Message


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
