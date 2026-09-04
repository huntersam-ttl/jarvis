"""Skill model — metadata + instruction body."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    name: str
    purpose: str
    task_types: tuple[str, ...]
    source: str  # source repository URL
    attribution: str
    version: str
    body: str = ""  # instruction text injected into context
    path: str = ""

    def to_metadata(self) -> dict:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "task_types": list(self.task_types),
            "source": self.source,
            "attribution": self.attribution,
            "version": self.version,
        }
