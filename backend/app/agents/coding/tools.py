"""Deterministic tools for the Coding Agent.

Every operation is validated against an approved workspace root:

- all paths must resolve inside the workspace
- secret files (.env, keys, credentials) can never be read or modified
- shell commands are screened by an allow/deny safety layer
- destructive operations always require explicit approval

These tools are pure Python — no LLM involved. The LLM only chooses
which tool to call with which arguments.
"""
from __future__ import annotations

import fnmatch
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger("jarvis.agents.coding.tools")

MAX_OUTPUT_CHARS = 6000
MAX_FILE_BYTES = 512 * 1024


class ToolError(Exception):
    """A tool call failed validation or execution."""


class ApprovalRequired(ToolError):
    """The operation is destructive and was not explicitly approved."""


# ---------------------------------------------------------------- security
SECRET_PATTERNS = [
    ".env*", "*.pem", "*.key", "id_rsa*", "id_ed25519*",
    "*credentials*", "*secret*", ".npmrc", ".netrc",
]

# git subcommands that are safe to auto-run
SAFE_GIT_SUBCOMMANDS = {"status", "diff", "log", "add", "commit"}

# command heads allowed without approval (non-destructive dev commands)
SAFE_COMMAND_HEADS = {
    "pytest", "python", "python3", "pip", "pip3", "npm", "npx", "node",
    "tsc", "ruff", "black", "mypy", "eslint", "prettier", "make",
    "ls", "grep", "cat", "head", "tail", "find", "wc", "which",
}

# patterns that must never be approved, even with explicit user approval
NEVER_APPROVE_PATTERNS = [
    "sudo", "mkfs", "curl | sh", "curl | bash", "wget | sh", "wget | bash",
    "| sh", "| bash", "|zsh", "eval ", "shutdown", "reboot",
]

# patterns that mark a command as destructive / dangerous
DESTRUCTIVE_PATTERNS = [
    "rm ", "rm -", "rmdir", "unlink", "shred", "dd if=",
    "git reset --hard", "git clean", "git push -f", "git push --force",
    "git push", "git restore", "git branch -d", "git branch -D",
    "git rebase", "git filter-branch", "chmod 777", "chown",
    "dropdb", "aws ", "gcloud ", "terraform ",
]


@dataclass
class ToolContext:
    """Execution context for one task: the approved workspace + approvals."""

    project_root: Path
    allow_destructive: bool = False

    # ---- path validation -------------------------------------------
    def resolve_in_workspace(self, path: str | Path) -> Path:
        raw = Path(path).expanduser()
        if not raw.is_absolute():
            raw = self.project_root / raw
        resolved = raw.resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            raise ToolError("Path is outside the approved workspace")
        return resolved

    def is_secret_path(self, path: Path) -> bool:
        rel = str(path.relative_to(self.project_root))
        return any(
            fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(path.name, p)
            for p in SECRET_PATTERNS
        )

    # ---- command safety --------------------------------------------
    def check_command(self, command: str) -> None:
        """Raise ApprovalRequired if the command needs approval, allow otherwise."""
        lowered = " " + command.lower().strip()
        for pat in NEVER_APPROVE_PATTERNS:
            if pat in lowered:
                raise ToolError(f"Forbidden command (matched '{pat.strip()}')")
        for pat in DESTRUCTIVE_PATTERNS:
            if pat in lowered:
                if self.allow_destructive:
                    logger.warning("destructive command approved by user: %s", command)
                    return
                raise ApprovalRequired(
                    f"Command requires explicit approval (matched '{pat.strip()}')"
                )

        head = shlex.split(command)[0] if command.strip() else ""
        if head == "git":
            parts = shlex.split(command)
            sub = parts[1] if len(parts) > 1 else ""
            if sub not in SAFE_GIT_SUBCOMMANDS:
                raise ApprovalRequired(f"git '{sub}' requires explicit approval")
            return
        if head in SAFE_COMMAND_HEADS:
            return
        raise ApprovalRequired(f"Command '{head}' requires explicit approval")


class CodingTools:
    """The deterministic tool set the Coding Agent can invoke."""

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx

    # ---- fs tools ----------------------------------------------------
    def list_files(self, path: str = ".") -> str:
        root = self.ctx.resolve_in_workspace(path)
        entries: List[str] = []
        skip_dirs = {".git", "node_modules", ".venv", "__pycache__", ".next", "dist"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for name in filenames[:200]:
                full = Path(dirpath) / name
                if self.ctx.is_secret_path(full):
                    continue
                entries.append(str(full.relative_to(root)))
            if len(entries) > 500:
                break
        return "\n".join(sorted(entries)[:500]) or "(empty)"

    def read_file(self, path: str) -> str:
        f = self.ctx.resolve_in_workspace(path)
        if self.ctx.is_secret_path(f):
            raise ToolError("Refusing to read secret/credential files")
        if not f.is_file():
            raise ToolError(f"Not a file: {path}")
        return f.read_bytes()[:MAX_FILE_BYTES].decode("utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> str:
        f = self.ctx.resolve_in_workspace(path)
        if self.ctx.is_secret_path(f):
            raise ToolError("Refusing to modify secret/credential files")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
        return f"Wrote {f.relative_to(self.ctx.project_root)} ({len(content)} chars)"

    def replace_text(self, path: str, old_text: str, new_text: str) -> str:
        f = self.ctx.resolve_in_workspace(path)
        if self.ctx.is_secret_path(f):
            raise ToolError("Refusing to modify secret/credential files")
        text = f.read_text(encoding="utf-8")
        if old_text not in text:
            raise ToolError("old_text not found in file")
        text = text.replace(old_text, new_text, 1)
        f.write_text(text, encoding="utf-8")
        return f"Edited {f.relative_to(self.ctx.project_root)}"

    # ---- shell --------------------------------------------------------
    def run_command(self, command: str, timeout: int = 120) -> Tuple[str, bool]:
        """Run a validated shell command inside the workspace. Returns (output, ok)."""
        self.ctx.check_command(command)
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.ctx.project_root,
            capture_output=True,
            text=True,
            timeout=min(max(timeout, 5), 600),
        )
        out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
        truncated = out[:MAX_OUTPUT_CHARS]
        if len(out) > MAX_OUTPUT_CHARS:
            truncated += f"\n... (truncated, {len(out)} chars total)"
        return truncated, proc.returncode == 0

    # ---- git ------------------------------------------------------------
    def git_status(self) -> str:
        out, ok = self.run_command("git status --short --branch", timeout=15)
        if not ok:
            raise ToolError("git status failed")
        return out or "(clean)"

    def git_diff(self, staged: bool = False) -> str:
        out, _ = self.run_command("git diff --cached" if staged else "git diff", timeout=15)
        return out or "(no changes)"

    def git_log(self, limit: int = 10) -> str:
        out, ok = self.run_command(f"git log --oneline -{min(max(limit, 1), 30)}", timeout=15)
        if not ok:
            raise ToolError("git log failed")
        return out

    def git_add(self, paths: str = "-A") -> str:
        out, ok = self.run_command(f"git add {paths}", timeout=15)
        if not ok:
            raise ToolError(f"git add failed: {out}")
        return f"Staged {paths}"

    def git_commit(self, message: str) -> str:
        message = message.replace('"', "'").replace("\n", " ").strip()[:200]
        out, ok = self.run_command(f'git commit -m "{message}"', timeout=30)
        if not ok:
            raise ToolError(f"git commit failed: {out}")
        return out or "Committed"

    # ---- extended fs tools ------------------------------------------------
    def search_files(self, pattern: str, glob: str = "*") -> str:
        """Grep-like text search inside the workspace (excludes secrets)."""
        import subprocess as sp

        if any(p in pattern for p in NEVER_APPROVE_PATTERNS):
            raise ToolError("Refusing to search for dangerous pattern")
        try:
            proc = sp.run(
                ["grep", "-rn", "--include", glob, "-m", "20", "--", pattern, "."],
                cwd=self.ctx.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, sp.TimeoutExpired) as exc:
            raise ToolError(f"search failed: {exc}")
        lines = [
            ln for ln in proc.stdout.splitlines()
            if ".env" not in ln and "node_modules" not in ln and ".venv" not in ln
        ]
        out = "\n".join(lines[:60])
        return out or "(no matches)"

    def read_file_lines(self, path: str, start: int, end: int) -> str:
        f = self.ctx.resolve_in_workspace(path)
        if self.ctx.is_secret_path(f):
            raise ToolError("Refusing to read secret/credential files")
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start)
        end = min(len(lines), max(end, start))
        return "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))

    def create_directory(self, path: str) -> str:
        d = self.ctx.resolve_in_workspace(path)
        d.mkdir(parents=True, exist_ok=True)
        return f"Created {d.relative_to(self.ctx.project_root)}"

    def move_path(self, src: str, dst: str) -> str:
        import shutil

        s = self.ctx.resolve_in_workspace(src)
        d = self.ctx.resolve_in_workspace(dst)
        if self.ctx.is_secret_path(s) or self.ctx.is_secret_path(d):
            raise ToolError("Refusing to move secret/credential files")
        if s == self.ctx.project_root or self.ctx.project_root in (s, d):
            raise ToolError("Refusing to move the project root")
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return f"Moved {s.name} -> {d.relative_to(self.ctx.project_root)}"

    def git_branch(self, name: str, create: bool = True) -> str:
        name = name.replace(" ", "-").strip()[:60]
        if not re.fullmatch(r"[A-Za-z0-9/._-]+", name or ""):
            raise ToolError("Invalid branch name")
        cmd = f"git branch {name}" if create else f"git branch --list {name}"
        out, ok = self.run_command(cmd, timeout=15)
        if not ok:
            raise ToolError(f"git branch failed: {out}")
        return out or f"Branch {name} ready"

    def git_checkout(self, name: str, create: bool = False) -> str:
        name = name.replace(" ", "-").strip()[:60]
        if not re.fullmatch(r"[A-Za-z0-9/._-]+", name or ""):
            raise ToolError("Invalid branch name")
        cmd = f"git checkout {'-b ' if create else ''}{name}"
        out, ok = self.run_command(cmd, timeout=15)
        if not ok:
            raise ToolError(f"git checkout failed: {out}")
        return out or f"On branch {name}"

    # ---- test / build -----------------------------------------------------
    def run_tests(self, command: Optional[str] = None) -> Tuple[str, bool]:
        return self.run_command(command or "pytest -q", timeout=300)

    def run_build(self, command: Optional[str] = None) -> Tuple[str, bool]:
        return self.run_command(command or "npm run build", timeout=300)


TOOL_NAMES = [
    "list_files", "read_file", "write_file", "replace_text",
    "run_command", "git_status", "git_diff", "git_log",
    "git_add", "git_commit", "run_tests", "run_build",
    "search_files", "read_file_lines", "create_directory", "move_path",
    "git_branch", "git_checkout",
]

