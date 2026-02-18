import asyncio
import json
import os
import re
import sqlite3
import time
from pathlib import Path

import httpx

DB_PATH = Path("/data/app.db")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
MAX_CONTEXT_FILES = int(os.getenv("MAX_CONTEXT_FILES", "40"))
MAX_CONTEXT_CHARS_PER_FILE = int(os.getenv("MAX_CONTEXT_CHARS_PER_FILE", "5000"))

SUPPORTED_CODE_EXTENSIONS = {
    ".b",
    ".bas",
    ".basic",
    ".bp",
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".json",
    ".kt",
    ".lua",
    ".md",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def is_probably_text(content: bytes) -> bool:
    if not content:
        return False
    if b"\x00" in content:
        return False

    sample = content[:1024]
    non_printable = sum(1 for b in sample if b < 9 or (13 < b < 32) or b == 127)
    return (non_printable / len(sample)) < 0.30


def should_include_file(file_path: Path, content: bytes) -> bool:
    if file_path.suffix.lower() in SUPPORTED_CODE_EXTENSIONS:
        return True
    return is_probably_text(content)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT NOT NULL,
                prompt TEXT NOT NULL,
                plan TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS file_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                diff TEXT NOT NULL,
                accepted INTEGER DEFAULT 0
            );
            """
        )


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def log(run_id: int, kind: str, msg: str):
    with conn() as c:
        c.execute("INSERT INTO run_logs(run_id,kind,message) VALUES(?,?,?)", (run_id, kind, msg))
        c.execute("UPDATE runs SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (run_id,))


def build_repo_context(path: Path) -> tuple[str, list[str]]:
    files = [p for p in sorted(path.glob("**/*")) if p.is_file()]
    included: list[str] = []
    chunks: list[str] = []

    for file_path in files:
        relative = file_path.relative_to(path)
        if len(included) >= MAX_CONTEXT_FILES:
            break

        try:
            raw_content = file_path.read_bytes()
        except Exception:
            continue

        if not should_include_file(file_path, raw_content):
            continue

        content = raw_content.decode("utf-8", errors="ignore").strip()
        if not content:
            continue

        if len(content) > MAX_CONTEXT_CHARS_PER_FILE:
            content = f"{content[:MAX_CONTEXT_CHARS_PER_FILE]}\n\n...[truncated]"

        included.append(str(relative))
        chunks.append(f"### FILE: {relative}\n{content}")

    return "\n\n".join(chunks), included


def build_worker_prompt(task_prompt: str, repo_context: str, included_files: list[str]) -> str:
    capabilities = (
        "You are a coding specialist optimized for code generation, code analysis/comprehension, "
        "debugging/root-cause analysis, refactoring, and test generation/validation across "
        "multiple languages including Pick/Basic."
    )
    instructions = (
        "Focus on technical correctness. If the task asks what code does, explain intent, input/output, "
        "data flow, and edge cases. Cite concrete details from the provided files. "
        "When evidence is incomplete, say what is uncertain instead of guessing."
    )

    return (
        f"{capabilities}\n"
        f"Task: {task_prompt}\n"
        f"Included files ({len(included_files)}): {', '.join(included_files) if included_files else 'none'}\n\n"
        f"{instructions}\n\n"
        "Return a single JSON object with keys:\n"
        "- edits: list of {file, content} for full-file replacements (or [] if no edits are needed)\n"
        "- validation_commands: list of commands to validate changes\n"
        "- answer: concise response to the user\n\n"
        f"Repository context:\n{repo_context or '[No readable code files found]'}"
    )


async def ollama_generate(model: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model or "qwen2.5-coder:7b", "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "")


def parse_model_response(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {"edits": [], "validation_commands": [], "answer": ""}

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return {"edits": [], "validation_commands": [], "answer": raw}


def write_change(run_id: int, file_path: str, before: str, after: str):
    import difflib

    diff = "\n".join(
        difflib.unified_diff(
            before.splitlines(), after.splitlines(), fromfile=f"a/{file_path}", tofile=f"b/{file_path}", lineterm=""
        )
    )
    with conn() as c:
        c.execute(
            "INSERT INTO file_changes(run_id,file_path,diff,accepted) VALUES(?,?,?,0)",
            (run_id, file_path, diff or "(no diff)"),
        )


async def process(run):
    run_id = run["id"]
    path = Path(run["project_path"])
    payload = json.loads(run["plan"] or "{}")
    fast_model = payload.get("fast_model") or "qwen2.5-coder:7b"
    deep_model = payload.get("deep_model") or fast_model

    log(run_id, "plan", "1) Inspect files+content 2) reason about task 3) propose edits 4) suggest validation")
    context, included_files = build_repo_context(path)
    log(run_id, "tool", f"loaded {len(included_files)} files into model context")

    prompt = build_worker_prompt(run["prompt"], context, included_files)
    raw = await ollama_generate(deep_model, prompt)
    log(run_id, "agent", "analysis generated")

    parsed = parse_model_response(raw)
    answer = str(parsed.get("answer") or parsed.get("notes") or "").strip()

    for edit in parsed.get("edits", []):
        target = (path / edit["file"]).resolve()
        if not str(target).startswith(str(path.resolve())):
            log(run_id, "security", f"blocked path {edit.get('file')}")
            continue
        before = target.read_text(errors="ignore") if target.exists() else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(edit.get("content", ""))
        write_change(run_id, edit["file"], before, edit.get("content", ""))
        log(run_id, "tool", f"write_file {edit['file']}")

    for cmd in parsed.get("validation_commands", []):
        log(run_id, "tool", f"validation suggested: {cmd}")

    if answer:
        log(run_id, "agent", f"answer: {answer}")

    status = "awaiting_review" if parsed.get("edits") else "completed"
    with conn() as c:
        c.execute("UPDATE runs SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, run_id))

    if status == "awaiting_review":
        log(run_id, "system", "Run complete; awaiting file-level acceptance")
    else:
        log(run_id, "system", "Run complete; no file changes proposed")


async def loop_forever():
    while True:
        with conn() as c:
            run = c.execute("SELECT * FROM runs WHERE status='queued' ORDER BY id ASC LIMIT 1").fetchone()
            if run:
                c.execute("UPDATE runs SET status='running', updated_at=CURRENT_TIMESTAMP WHERE id=?", (run["id"],))
        if run:
            try:
                await process(run)
            except Exception as exc:
                with conn() as c:
                    c.execute("UPDATE runs SET status='failed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (run["id"],))
                log(run["id"], "error", str(exc))
        time.sleep(2)


if __name__ == "__main__":
    init_db()
    asyncio.run(loop_forever())
