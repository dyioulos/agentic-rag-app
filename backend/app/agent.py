from __future__ import annotations

import json
from pathlib import Path

from .ollama_client import generate
from .tools import ToolRegistry


PICK_BASIC_GUIDANCE = """
Pick/BASIC support rules:
- Treat field marks/value marks/subvalue marks idioms as first-class constructs.
- Preserve GOSUB/RETURN and numbered labels when refactoring legacy programs.
- Prefer incremental modernization suggestions and compatibility-safe edits.
"""


def chunk_file(path: Path, max_chars: int = 4000) -> list[str]:
    text = path.read_text(errors="ignore")
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


async def build_plan(prompt: str, model: str) -> str:
    plan_prompt = (
        "Create a short explicit execution plan as numbered steps for this coding task:\n"
        f"{prompt}\n"
        "Include verification and diff review steps."
    )
    return await generate(model, plan_prompt)


async def run_agent_loop(
    prompt: str,
    project_path: str,
    fast_model: str,
    deep_model: str,
    logger,
):
    tools = ToolRegistry(project_path, logger)
    tree = tools.list_dir(".").output

    context_lines = []
    for entry in tree.splitlines()[:30]:
        f = Path(project_path) / entry
        if f.is_file() and f.suffix in {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".bp", ".basic"}:
            snippets = chunk_file(f, 1000)
            context_lines.append(f"FILE {entry} chunk0:\n{snippets[0]}")

    context = "\n\n".join(context_lines)
    analysis_prompt = (
        f"Task: {prompt}\n"
        f"Repository context:\n{context}\n"
        f"{PICK_BASIC_GUIDANCE}\n"
        "Return JSON with keys: actions (list), validation_commands (list), notes (string)."
    )
    raw = await generate(deep_model or fast_model, analysis_prompt)
    logger("agent", "Generated plan and analysis")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"actions": [], "validation_commands": [], "notes": raw}

    results = []
    for action in parsed.get("actions", []):
        kind = action.get("tool")
        if kind == "read_file":
            results.append(tools.read_file(action["path"]).output)
        elif kind == "write_file":
            results.append(tools.write_file(action["path"], action["content"]).output)
        elif kind == "search":
            results.append(tools.search(action["pattern"]).output)

    validations = []
    for cmd in parsed.get("validation_commands", []):
        validations.append({"cmd": cmd, "result": tools.shell(cmd).output})

    return {
        "analysis": parsed,
        "tool_results": results,
        "validations": validations,
    }
