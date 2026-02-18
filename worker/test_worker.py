from worker import build_repo_context, build_worker_prompt, parse_model_response


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


def test_build_repo_context_includes_supported_files(tmp_path):
    (tmp_path / "example.basic").write_text("PRINT 'HELLO'")
    (tmp_path / "notes.bin").write_bytes(b"\x00\x01")

    context, files = build_repo_context(tmp_path)

    assert files == ["example.basic"]
    assert "### FILE: example.basic" in context


def test_build_worker_prompt_mentions_pick_basic_capability():
    prompt = build_worker_prompt(
        "What does this Pick/Basic code do?",
        '### FILE: sample.basic\nCRT "HI"',
        ["sample.basic"],
    )

    assert "including Pick/Basic" in prompt
    assert "What does this Pick/Basic code do?" in prompt


def test_build_repo_context_includes_bas_files(tmp_path):
    (tmp_path / "legacy.bas").write_text('PRINT "HELLO"')

    context, files = build_repo_context(tmp_path)

    assert files == ["legacy.bas"]
    assert "### FILE: legacy.bas" in context


def test_build_repo_context_includes_extensionless_text_files(tmp_path):
    (tmp_path / "PROGRAM").write_text('CRT "HELLO"')

    context, files = build_repo_context(tmp_path)

    assert files == ["PROGRAM"]
    assert "### FILE: PROGRAM" in context


def test_build_repo_context_skips_binary_files_without_extension(tmp_path):
    (tmp_path / "blob").write_bytes(b"\x00\x10\x80\xff")

    context, files = build_repo_context(tmp_path)

    assert files == []
    assert context == ""
