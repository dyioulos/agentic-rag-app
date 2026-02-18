from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import get_conn, init_db
from .models import AcceptChangeRequest, RunCreate
from .ollama_client import list_models

app = FastAPI(title="Agentic Coding Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    Path(settings.workspace_root).mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/models")
async def models():
    return {"models": await list_models()}


@app.get("/projects")
def projects():
    root = Path(settings.workspace_root)
    return {
        "projects": [
            str(p)
            for p in sorted(root.iterdir())
            if p.is_dir() and not p.name.startswith(".")
        ]
    }


@app.post("/runs")
def create_run(payload: RunCreate):
    if not str(Path(payload.project_path).resolve()).startswith(
        str(Path(settings.workspace_root).resolve())
    ):
        raise HTTPException(status_code=400, detail="Project path must be in mounted workspace")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs(project_path,prompt,status,plan) VALUES(?,?,?,?)",
            (payload.project_path, payload.prompt, "queued", json.dumps({"fast_model": payload.fast_model, "deep_model": payload.deep_model})),
        )
        run_id = cur.lastrowid
        conn.execute(
            "INSERT INTO run_logs(run_id,kind,message) VALUES(?,?,?)",
            (run_id, "system", "Run queued"),
        )
    return {"id": run_id, "status": "queued"}


@app.get("/runs")
def list_runs():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,project_path,prompt,status,created_at,updated_at FROM runs ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return {"runs": [dict(r) for r in rows]}


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    with get_conn() as conn:
        run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        logs = conn.execute(
            "SELECT kind,message,created_at FROM run_logs WHERE run_id=? ORDER BY id ASC", (run_id,)
        ).fetchall()
        changes = conn.execute(
            "SELECT id,file_path,diff,accepted FROM file_changes WHERE run_id=? ORDER BY id ASC", (run_id,)
        ).fetchall()
    return {"run": dict(run), "logs": [dict(x) for x in logs], "changes": [dict(x) for x in changes]}


@app.post("/changes/{change_id}/accept")
def accept_change(change_id: int, payload: AcceptChangeRequest):
    with get_conn() as conn:
        conn.execute(
            "UPDATE file_changes SET accepted=? WHERE id=?",
            (1 if payload.accepted else 0, change_id),
        )
    return {"ok": True}
