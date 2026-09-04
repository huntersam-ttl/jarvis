"""Task complexity classification + structured plan generation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.logging import get_logger
from app.providers.base import Provider

logger = get_logger("jarvis.agents.coding.planner")

COMPLEXITY_LEVELS = ("TRIVIAL", "SMALL", "MEDIUM", "LARGE")

# large-scope verbs and multi-part signals
LARGE_SIGNALS = (
    "build", "create", "scaffold", "migrate", "rewrite", "design", "full",
    "application", "website", "game", "saas", "service", "project", "from scratch",
)
MEDIUM_SIGNALS = ("add", "implement", "refactor", "feature", "integrate", "multiple", "and fix", "update")
TRIVIAL_SIGNALS = ("typo", "rename", "tweak", "comment", "log line", "one line", "small fix")

PLAN_SYSTEM = """You are Jarvis's engineering planner. Given a task and project \
profile, produce a small, verifiable plan. Reply with ONLY JSON:
{"objective": "...", "assumptions": ["..."], "files": ["..."], "steps": [{"title": "...", "verify": "command or check"}], "risks": ["..."], "verification": ["commands"], "rollback": "..."}
Steps must each be independently verifiable. No more than 8 steps."""


@dataclass
class PlanStep:
    title: str
    verify: str = ""


@dataclass
class Plan:
    objective: str
    complexity: str  # TRIVIAL | SMALL | MEDIUM | LARGE
    assumptions: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    steps: List[PlanStep] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    verification: List[str] = field(default_factory=list)
    rollback: str = ""
    model: str = ""


def classify_complexity(instruction: str) -> str:
    text = instruction.lower()
    words = len(text.split())
    if any(s in text for s in LARGE_SIGNALS) or words > 40:
        return "LARGE"
    if any(s in text for s in TRIVIAL_SIGNALS) or words <= 4:
        return "TRIVIAL"
    if any(s in text for s in MEDIUM_SIGNALS) or words > 10:
        return "MEDIUM"
    return "SMALL"


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("planner did not return JSON")
    return json.loads(match.group(0))


def trivial_plan(instruction: str, complexity: str = "TRIVIAL") -> Plan:
    """No LLM call — trivial tasks get a minimal deterministic plan."""
    return Plan(
        objective=instruction[:300],
        complexity=complexity,
        steps=[PlanStep(title="Apply the requested change", verify="run project checks")],
        verification=["project checks"],
    )


async def generate_plan(
    provider: Provider,
    instruction: str,
    profile_summary: str,
    model: Optional[str] = None,
) -> Plan:
    complexity = classify_complexity(instruction)
    if complexity in ("TRIVIAL", "SMALL"):
        return trivial_plan(instruction, complexity)
    prompt = (
        f"Project profile:\n{profile_summary}\n\n"
        f"Task: {instruction}\n\nComplexity: {complexity}\nProduce the plan JSON now."
    )
    try:
        reply, used_model = await provider.chat(prompt, model=model)
        data = _parse(reply)
    except Exception as exc:
        logger.warning("plan generation failed (%s) — falling back to minimal plan", exc)
        plan = trivial_plan(instruction, complexity)
        plan.assumptions.append("Plan generation failed; using minimal plan")
        return plan
    return Plan(
        objective=str(data.get("objective", instruction))[:500],
        complexity=complexity,
        assumptions=[str(a) for a in data.get("assumptions", [])[:8]],
        files=[str(f) for f in data.get("files", [])[:15]],
        steps=[
            PlanStep(title=str(s.get("title", ""))[:200], verify=str(s.get("verify", ""))[:120])
            for s in data.get("steps", [])[:8]
            if isinstance(s, dict)
        ],
        risks=[str(r) for r in data.get("risks", [])[:6]],
        verification=[str(v) for v in data.get("verification", [])[:6]],
        rollback=str(data.get("rollback", ""))[:300],
        model=used_model,
    )
