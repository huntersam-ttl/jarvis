"""Context engine — bounded, relevant context for each model call.

Never sends the whole repository. Selects: project profile summary, task,
keyword-matched file excerpts, recent action results, relevant skill
instructions, and failure digests. Everything size-capped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.agents.coding.project_analyzer import ProjectProfile
from app.core.logging import get_logger
from app.skills.base import Skill

logger = get_logger("jarvis.agents.coding.context")

MAX_FILES = 6
MAX_EXCERPT_CHARS = 1800
MAX_CONTEXT_CHARS = 9000

# words too generic for file matching
STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "with", "fix",
    "add", "build", "make", "run", "test", "tests", "all", "new", "update",
    "please", "jarvis", "project", "code", "file", "files",
}


@dataclass
class RelevantFile:
    path: str
    excerpt: str


def extract_keywords(instruction: str) -> List[str]:
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_.-]{2,}", instruction.lower())
    return [w for w in words if w not in STOP_WORDS][:12]


class ContextBuilder:
    def __init__(self, profile: ProjectProfile, skills: List[Skill]):
        self.profile = profile
        self.skills = skills

    def profile_summary(self) -> str:
        p = self.profile
        return (
            f"Stack: {', '.join(p.languages) or 'unknown'} | "
            f"Frameworks: {', '.join(p.frameworks) or 'none'} | "
            f"Package managers: {', '.join(p.package_managers) or 'none'}\n"
            f"Commands — test: {p.test_command or '-'} | lint: {p.lint_command or '-'} | "
            f"typecheck: {p.typecheck_command or '-'} | build: {p.build_command or '-'}\n"
            f"Git: {'repo' if p.has_git else 'NO REPO'}"
            f"{' (dirty)' if p.git_dirty else ''} | Dirs: {p.structure_summary}"
        )

    def find_relevant_files(self, instruction: str, root: Path) -> List[RelevantFile]:
        keywords = extract_keywords(instruction)
        scored: List[tuple] = []
        skip_dirs = {".git", "node_modules", ".venv", "__pycache__", ".next", "dist"}
        for path in root.rglob("*"):
            if not path.is_file() or len(scored) > 400:
                continue
            if skip_dirs & set(path.parts) or path.name.startswith(".env"):
                continue
            name = path.name.lower()
            score = sum(2 for kw in keywords if kw in name)
            rel = str(path.relative_to(root)).lower()
            score += sum(1 for kw in keywords if kw in rel)
            if score:
                scored.append((score, path))
        scored.sort(key=lambda t: -t[0])
        files: List[RelevantFile] = []
        for _, path in scored[:MAX_FILES]:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:MAX_EXCERPT_CHARS]
                files.append(RelevantFile(str(path.relative_to(root)), text))
            except OSError:
                continue
        return files

    def build(self, instruction: str, history: List[str], failures: str = "") -> str:
        root = Path(self.profile.path)
        sections: List[str] = [
            f"Project profile:\n{self.profile_summary()}",
            f"Task: {instruction}",
        ]
        files = self.find_relevant_files(instruction, root)
        if files:
            rendered = "\n\n".join(f"--- {f.path} ---\n{f.excerpt}" for f in files)
            sections.append(f"Relevant files (excerpts):\n{rendered}")
        if self.skills:
            sections.append(
                "Engineering skills for this task:\n"
                + "\n\n".join(f"[{s.name}] {s.body}" for s in self.skills)
            )
        if failures:
            sections.append(f"Current failures to fix:\n{failures[:2500]}")
        if history:
            sections.append("Recent actions (most recent last):\n" + "\n".join(history[-8:]))
        context = "\n\n".join(sections)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n... (context truncated)"
        return context

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)
