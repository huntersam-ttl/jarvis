"""Skill registry — task-type detection and automatic skill selection.

Skills are injected into agent context only when their task types match
the detected task classification. Never all skills at once.
"""
from __future__ import annotations

import re
from typing import Dict, List

from app.core.logging import get_logger
from app.skills.base import Skill
from app.skills.loader import load_skills

logger = get_logger("jarvis.skills.registry")

# task-type -> keyword triggers (lowercased substring match on instruction)
TASK_TYPE_KEYWORDS: Dict[str, tuple] = {
    "debugging": ("fix", "broken", "bug", "error", "fail", "crash", "regression", "debug", "not working", "failing"),
    "frontend": ("frontend", "ui", "css", "styling", "style", "component", "react", "page", "layout", "design", "responsive", "tailwind"),
    "api": ("api", "endpoint", "route", "rest", "graphql", "interface", "backend", "service"),
    "testing": ("test", "pytest", "coverage", "tdd", "spec"),
    "specification": ("build", "create", "new", "scaffold", "implement", "add", "feature", "design", "prototype", "app", "website", "game", "saas", "tool"),
    "planning": ("plan", "refactor", "migrate", "migration", "architecture", "breakdown", "large", "project"),
    "implementation": ("implement", "write", "code", "build", "add", "create"),
    "security": ("security", "vulnerability", "hardening", "secret", "auth", "sanitize", "exploit", "injection"),
    "review": ("review", "refactor", "cleanup", "quality", "improve", "maintain"),
    "git": ("commit", "branch", "git", "merge", "rebase", "pr", "version"),
    "documentation": ("readme", "document", "docs", "changelog", "guide"),
    "verification": (),  # always applicable for code-changing tasks
}

# skills always included (cheap, high value)
ALWAYS_INCLUDE = ("verification-before-completion",)
# cap on skills injected per task (context efficiency)
MAX_SKILLS_PER_TASK = 4


class SkillRegistry:
    def __init__(self, skills: List[Skill] | None = None):
        self._skills: Dict[str, Skill] = {
            s.name: s for s in (skills if skills is not None else load_skills())
        }
        logger.info(f"skill registry ready: {sorted(self._skills)}")

    # ---- query ---------------------------------------------------------
    @property
    def skills(self) -> List[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def metadata(self) -> list[dict]:
        return [s.to_metadata() for s in self.skills]

    # ---- selection -------------------------------------------------------
    # Specific engineering types first; generic planning types fill the rest.
    TYPE_PRIORITY = [
        "debugging", "frontend", "api", "testing", "security",
        "review", "git", "documentation", "planning", "specification",
        "implementation",
    ]

    @staticmethod
    def detect_task_types(instruction: str) -> List[str]:
        text = instruction.lower()
        types = []
        for t, kws in TASK_TYPE_KEYWORDS.items():
            for kw in kws:
                # word-boundary match so "ui" doesn't match inside "build"
                if re.search(rf"\b{re.escape(kw)}", text):
                    types.append(t)
                    break
        if not types:
            types = ["specification", "implementation"]
        return types

    def select(self, instruction: str) -> List[Skill]:
        """Pick the few skills relevant to this instruction."""
        types = set(self.detect_task_types(instruction))
        selected: List[Skill] = []

        def matches(skill: Skill) -> bool:
            return bool(types & set(skill.task_types))

        def take(skill: Skill) -> None:
            if skill not in selected and len(selected) < MAX_SKILLS_PER_TASK:
                selected.append(skill)

        for skill in self.skills:
            if skill.name in ALWAYS_INCLUDE:
                take(skill)
        for t in self.TYPE_PRIORITY:
            for skill in self.skills:
                if t in skill.task_types and matches(skill):
                    take(skill)
        # guarantee verification skill presence
        if not any(s.name in ALWAYS_INCLUDE for s in selected):
            v = self.get("verification-before-completion")
            if v:
                selected.append(v)
        return selected[:MAX_SKILLS_PER_TASK]

    def render_for_prompt(self, selected: List[Skill]) -> str:
        """Compact rendering of selected skill instructions."""
        blocks = []
        for s in selected:
            blocks.append(f"### Skill: {s.name}\n{s.body}")
        return "\n\n".join(blocks)


# convenience singleton for API use
_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
