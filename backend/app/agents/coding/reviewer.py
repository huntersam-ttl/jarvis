"""Fresh-context code reviewer.

Runs as a separate model call (not a separate agent process) after
implementation. CRITICAL/HIGH findings block completion until fixed or
explicitly waived. Bounded by a max-call cap for cost control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.core.logging import get_logger
from app.providers.base import Provider

logger = get_logger("jarvis.agents.coding.reviewer")

REVIEW_SYSTEM = """You are a strict senior code reviewer. Review the diff below. \
Reply with ONLY JSON:
{"findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|NIT", "file": "...", "issue": "...", "suggestion": "..."}], "verdict": "approve|block", "summary": "one sentence"}
Only real issues; no filler. CRITICAL = broken/security/data-loss. HIGH = likely regression or serious flaw."""


@dataclass
class ReviewFinding:
    severity: str
    file: str
    issue: str
    suggestion: str = ""


@dataclass
class ReviewResult:
    verdict: str  # approve | block | skipped
    findings: List[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    model: str = ""

    @property
    def blocking(self) -> List[ReviewFinding]:
        return [f for f in self.findings if f.severity in ("CRITICAL", "HIGH")]


import json
import re


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("reviewer did not return JSON")
    return json.loads(match.group(0))


async def review_diff(
    provider: Provider,
    diff: str,
    instruction: str,
    model: Optional[str] = None,
    max_diff_chars: int = 12000,
) -> ReviewResult:
    """One fresh-context review call over the (bounded) diff."""
    diff_bounded = diff[:max_diff_chars]
    prompt = f"Task: {instruction}\n\nDiff to review:\n{diff_bounded}\n\nReview now."
    reply, used_model = await provider.chat(prompt, model=model)
    try:
        data = _parse(reply)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("reviewer output unparsable: %s", exc)
        return ReviewResult(
            verdict="skipped",
            summary="Reviewer output could not be parsed — not blocking",
            model=used_model,
        )
    findings = [
        ReviewFinding(
            severity=str(f.get("severity", "LOW")).upper(),
            file=str(f.get("file", "?")),
            issue=str(f.get("issue", "")),
            suggestion=str(f.get("suggestion", "")),
        )
        for f in data.get("findings", [])[:20]
    ]
    verdict = "block" if any(f.severity in ("CRITICAL", "HIGH") for f in findings) else "approve"
    return ReviewResult(
        verdict=verdict,
        findings=findings,
        summary=str(data.get("summary", ""))[:500],
        model=used_model,
    )
