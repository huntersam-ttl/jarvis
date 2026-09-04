"""Deterministic verification gate.

A code-changing task can ONLY become COMPLETED when the project's own
configured checks (lint / typecheck / tests / build — per ProjectProfile)
pass. The LLM cannot override this. Failed verification feeds errors back
into a bounded DEBUGGING repair loop.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.agents.coding.project_analyzer import ProjectProfile
from app.core.logging import get_logger

logger = get_logger("jarvis.agents.coding.verifier")

MAX_OUTPUT = 4000


@dataclass
class CheckResult:
    command: str
    ok: bool
    output: str = ""
    duration_ms: float = 0.0


@dataclass
class VerificationResult:
    passed: bool
    checks: List[CheckResult] = field(default_factory=list)
    summary: str = ""

    @property
    def failures(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.ok]

    def failure_digest(self, max_chars: int = 2500) -> str:
        """Compact failure text fed back to the model (bounded context)."""
        parts = []
        size = 0
        for f in self.failures:
            chunk = f"$ {f.command}\n{f.output[-1200:]}\n"
            if size + len(chunk) > max_chars:
                chunk = chunk[: max_chars - size]
            parts.append(chunk)
            size += len(chunk)
            if size >= max_chars:
                break
        return "\n".join(parts) or "(no failure output)"


def run_verification(profile: ProjectProfile, cwd: str | None = None) -> VerificationResult:
    """Run every configured check. Missing config => that check is skipped."""
    results: List[CheckResult] = []
    for command in profile.verification_checks:
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd or profile.path,
                capture_output=True,
                text=True,
                timeout=600,
            )
            ok = proc.returncode == 0
            out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            ok, out = False, f"Check failed to run: {exc}"
        results.append(
            CheckResult(
                command=command,
                ok=ok,
                output=out[:MAX_OUTPUT],
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        )
    passed = bool(results) and all(r.ok for r in results)
    failed = [r.command for r in results if not r.ok]
    summary = "all checks passed" if passed else f"failed: {', '.join(failed)}"
    if not results:
        # Nothing deterministic configured to gate on — cannot deny completion
        # for checks the project does not support.
        summary = "no verification checks configured"
        passed = True
    logger.info(f"verification for {profile.path}: {summary}")
    return VerificationResult(passed=passed, checks=results, summary=summary)
