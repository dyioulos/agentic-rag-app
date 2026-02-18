from worker import parse_model_response


def test_parse_model_response_handles_fenced_json():
    raw = """```json
    {"edits": [], "validation_commands": ["pytest"], "answer": "Done."}
    ```"""

    parsed = parse_model_response(raw)

    assert parsed["answer"] == "Done."
    assert parsed["validation_commands"] == ["pytest"]


def test_parse_model_response_falls_back_to_answer_text():
    raw = "This is a plain-language answer."

    parsed = parse_model_response(raw)

    assert parsed["edits"] == []
    assert parsed["validation_commands"] == []
    assert parsed["answer"] == raw
