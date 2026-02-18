# Agentic Coding Application (Docker + Ollama)

A local-first agentic coding platform for code generation, analysis, debugging, refactoring, and validation using an Ollama service already running on the host.

## Highlights
- Multi-container architecture (`frontend`, `backend`, `worker`, `db`) with backend/worker connecting to host Ollama.
- Full run history and audit logs in SQLite (`/data/app.db`).
- Host-mounted project workspace at `./mounted-workspace:/workspace`.
- Plan-first agent loop with explicit logs and diff review before acceptance.
- Tool registry with allowlisted shell commands and path-bound access controls.
- Pick/Basic support (`.basic`, `.bp`) with dedicated prompt guidance.

## Quick start
```bash
docker compose up --build
```

Then open:
- UI: http://localhost:8080
- Backend API docs: http://localhost:8000/docs
- Ollama API: provided by your host service (default backend target: `http://host.docker.internal:11434`)

## Configuration
Environment variables (backend):
- `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`)
- `DB_PATH` (default `/data/app.db`)
- `WORKSPACE_ROOT` (default `/workspace`)
- `SHELL_ALLOWLIST` (comma-separated command prefixes)
- `NETWORK_ENABLED` (default `false`)
- `COMMAND_TIMEOUT_S` (default `120`)

## UX flow
1. Select mounted project.
2. Enter prompt and optional fast/deep model names.
3. Run agent.
4. Inspect plan + execution logs.
5. Review per-file diffs.
6. Accept changes file-by-file.
7. Review validation output entries from tool logs.

## Notes
- The worker currently executes model-suggested edits and logs suggested validation commands. You can extend execution policy to run only approved commands from the allowlist.
- The stack expects Ollama to already be running on the host. Override `OLLAMA_BASE_URL` if your host endpoint differs.
