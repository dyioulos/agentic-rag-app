import asyncio
import json
import sqlite3
import os
import time
import re
from pathlib import Path

import httpx

DB_PATH = Path("/data/app.db")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")


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

    log(run_id, "plan", "1) Inspect repo 2) propose edit 3) validate 4) show diff")
    files = [p for p in path.glob("**/*") if p.is_file()][:25]
    context = "\n".join([f"{f.relative_to(path)}" for f in files])
    log(run_id, "tool", f"scanned {len(files)} files")

    prompt = (
        f"Task: {run['prompt']}\nFiles:\n{context}\n"
        "Return JSON object with key edits as list of {file,content} and validation_commands list."
    )
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
