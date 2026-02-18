from pathlib import Path

from app.tools import ToolRegistry


def test_write_file_generates_diff(tmp_path: Path):
    events = []
    reg = ToolRegistry(str(tmp_path), lambda k, m: events.append((k, m)))
    result = reg.write_file("foo.py", "print('ok')\n")
    assert result.ok
    assert "+++ b/foo.py" in result.output
    assert events[-1][0] == "tool"


def test_safe_path_blocks_escape(tmp_path: Path):
    reg = ToolRegistry(str(tmp_path), lambda _k, _m: None)
    try:
        reg.read_file("../oops.txt")
        assert False, "Expected ValueError"
    except ValueError:
        assert True
