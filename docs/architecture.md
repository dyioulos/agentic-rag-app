# Architecture Overview

## Services
- **frontend**: Responsive dark-mode UI with dashboard, file/run panels, diffs, and validation output.
- **backend**: FastAPI API for model discovery, run orchestration, audit data retrieval, and change acceptance.
- **worker**: Background agent loop polling queued runs, generating edits, and persisting diffs.
- **db**: Lightweight persistent volume holder for SQLite database at `/data/app.db`.
- **ollama (host service)**: Existing host Ollama instance reached from containers via `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`).

## Agent loop
1. Accept user task and selected models.
2. Persist run in SQLite and queue execution.
3. Worker logs plan and repository scan.
4. Worker requests structured edits from Ollama.
5. Changes are written with per-file diffs and audit logs.
6. Run transitions to `awaiting_review`.
7. UI allows per-file acceptance.

## Safety model
- Project path must be under mounted `/workspace`.
- Tool registry blocks path escapes.
- Shell tool checks allowlist before command execution.
- Network for shell commands defaults to disabled.
- Tool calls are always inserted into `run_logs`.

## Pick/Basic support
- `.basic` and `.bp` extensions are included in context selection.
- Prompt guidance enforces Pick/Basic-safe refactoring idioms.
- Validation commands are project-defined and surfaced in logs/UI.
