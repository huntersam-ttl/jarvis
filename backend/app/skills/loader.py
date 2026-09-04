"""Load skill playbooks from markdown files with simple frontmatter.

Format:
---
name: test-driven-development
purpose: One-line purpose
task_types: testing, bugfix
source: https://github.com/obra/superpowers
attribution: Adapted from obra/superpowers
version: 2026-01
---
<instruction body>
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.core.logging import get_logger
from app.skills.base import Skill

logger = get_logger("jarvis.skills.loader")

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent / "coding"


def parse_skill_file(path: Path) -> Skill | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("could not read skill %s: %s", path, exc)
        return None
    if not raw.startswith("---"):
        logger.warning("skill %s has no frontmatter; skipped", path.name)
        return None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    try:
        task_types = tuple(
            t.strip() for t in meta.get("task_types", "").split(",") if t.strip()
        )
        return Skill(
            name=meta.get("name", path.stem),
            purpose=meta.get("purpose", ""),
            task_types=task_types,
            source=meta.get("source", ""),
            attribution=meta.get("attribution", ""),
            version=meta.get("version", ""),
            body=parts[2].strip(),
            path=str(path),
        )
    except Exception as exc:  # defensive
        logger.warning("bad skill file %s: %s", path, exc)
        return None


def load_skills(skills_dir: Path | None = None) -> List[Skill]:
    directory = skills_dir or DEFAULT_SKILLS_DIR
    skills: List[Skill] = []
    if not directory.is_dir():
        return skills
    for path in sorted(directory.glob("*.md")):
        skill = parse_skill_file(path)
        if skill:
            skills.append(skill)
    logger.info(f"loaded {len(skills)} skills from {directory}")
    return skills
