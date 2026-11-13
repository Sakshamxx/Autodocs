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
