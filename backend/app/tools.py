from __future__ import annotations

import difflib
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import settings


@dataclass
class ToolResult:
    ok: bool
    output: str


class ToolRegistry:
    def __init__(self, project_path: str, logger: Callable[[str, str], None]):
        self.project_path = Path(project_path).resolve()
        self.logger = logger

    def _safe(self, path: str) -> Path:
        full = (self.project_path / path).resolve()
        if not str(full).startswith(str(self.project_path)):
            raise ValueError("Path escapes mounted project")
        return full

    def list_dir(self, path: str = ".") -> ToolResult:
        p = self._safe(path)
        items = sorted([x.name for x in p.iterdir()])
        self.logger("tool", f"list_dir {path}")
        return ToolResult(True, "\n".join(items))

    def read_file(self, path: str) -> ToolResult:
        p = self._safe(path)
        self.logger("tool", f"read_file {path}")
        return ToolResult(True, p.read_text(errors="ignore"))

    def write_file(self, path: str, new_content: str) -> ToolResult:
        p = self._safe(path)
        old = p.read_text(errors="ignore") if p.exists() else ""
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new_content)
        diff = "\n".join(
            difflib.unified_diff(
                old.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        self.logger("tool", f"write_file {path}")
        return ToolResult(True, diff or "(no diff)")

    def search(self, pattern: str) -> ToolResult:
        self.logger("tool", f"search {pattern}")
        proc = subprocess.run(
            ["rg", "-n", pattern, str(self.project_path)],
            capture_output=True,
            text=True,
            timeout=settings.command_timeout_s,
        )
        return ToolResult(proc.returncode in (0, 1), proc.stdout + proc.stderr)

    def git(self, args: str) -> ToolResult:
        self.logger("tool", f"git {args}")
        proc = subprocess.run(
            ["git", *shlex.split(args)],
            cwd=self.project_path,
            capture_output=True,
            text=True,
            timeout=settings.command_timeout_s,
        )
        return ToolResult(proc.returncode == 0, proc.stdout + proc.stderr)

    def shell(self, command: str) -> ToolResult:
        if not any(command.startswith(prefix) for prefix in settings.shell_allowlist):
            return ToolResult(False, f"Command not allowlisted: {command}")

        self.logger("tool", f"shell {command}")
        env = os.environ.copy()
        if not settings.network_enabled:
            env["NO_PROXY"] = "*"
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.project_path,
            capture_output=True,
            text=True,
            timeout=settings.command_timeout_s,
            env=env,
        )
        return ToolResult(proc.returncode == 0, proc.stdout + proc.stderr)
