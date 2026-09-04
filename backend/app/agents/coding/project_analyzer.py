"""Deterministic project analysis — builds a ProjectProfile per project.

Detects languages, frameworks, package managers, test/lint/typecheck/build
commands from real config files. Never invents checks a project does not
support. Results are cached per project path (cheap to refresh).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger("jarvis.agents.coding.analyzer")


@dataclass
class ProjectProfile:
    path: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    test_command: Optional[str] = None
    lint_command: Optional[str] = None
    typecheck_command: Optional[str] = None
    build_command: Optional[str] = None
    config_files: List[str] = field(default_factory=list)
    has_git: bool = False
    git_dirty: bool = False
    docs: List[str] = field(default_factory=list)
    deploy_hints: List[str] = field(default_factory=list)
    structure_summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def verification_checks(self) -> List[str]:
        """Deterministic checks in execution order (fast -> slow)."""
        checks: List[str] = []
        if self.lint_command:
            checks.append(self.lint_command)
        if self.typecheck_command:
            checks.append(self.typecheck_command)
        if self.test_command:
            checks.append(self.test_command)
        if self.build_command:
            checks.append(self.build_command)
        return checks


def _run(cmd: List[str], cwd: Path, timeout: int = 15) -> Optional[str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return proc.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _npm_script(pkg: dict, name: str) -> Optional[str]:
    scripts = pkg.get("scripts") or {}
    return f"npm run {name}" if name in scripts else None


def analyze_project(path: str | Path) -> ProjectProfile:
    root = Path(path).expanduser().resolve()
    profile = ProjectProfile(path=str(root))
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    names = {p.name for p in root.iterdir()}
    known_configs = {
        "package.json", "pyproject.toml", "requirements.txt", "tsconfig.json",
        "next.config.mjs", "tailwind.config.js", "postcss.config.js",
        "pytest.ini", "setup.cfg", "Makefile", "vite.config.ts", "Cargo.toml",
        "go.mod", "eslint.config.mjs", ".eslintrc.json", "vercel.json",
        "Dockerfile", "railway.toml", "package-lock.json",
    }
    profile.config_files = sorted(p for p in names if p in known_configs)

    # ---- Python --------------------------------------------------------
    py_dirs = [root, root / "backend"]
    has_py = (
        "pyproject.toml" in names or "requirements.txt" in names or "pytest.ini" in names
        or any(any(d.glob("*.py")) for d in py_dirs if d.is_dir())
    )
    if has_py:
        profile.languages.append("python")
        profile.package_managers.append("pip")
        if "pytest.ini" in names or "pyproject.toml" in names or (root / "tests").is_dir():
            profile.test_command = "pytest -q"
        cfg = root / "pyproject.toml"
        if cfg.exists():
            text = cfg.read_text(encoding="utf-8", errors="ignore")
            if "ruff" in text:
                profile.lint_command = "ruff check ."
            if "mypy" in text:
                profile.typecheck_command = "mypy ."

    # ---- Node / JS -------------------------------------------------------
    pkg_path = root / "package.json"
    if not pkg_path.exists() and (root / "frontend" / "package.json").exists():
        pkg_path = root / "frontend" / "package.json"
    pkg: dict = {}
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pkg = {}
        pkg_text = json.dumps(pkg)
        profile.languages.append("typescript" if "typescript" in pkg_text else "javascript")
        for pm in ("pnpm-lock.yaml", "yarn.lock"):
            if (root / pm).exists():
                profile.package_managers.append(pm.split("-")[0])
        if "package-lock.json" in names or not profile.package_managers:
            profile.package_managers.append("npm")
        deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
        if "next" in deps:
            profile.frameworks.append("Next.js")
        if "react" in deps:
            profile.frameworks.append("React")
        profile.lint_command = profile.lint_command or _npm_script(pkg, "lint")
        profile.typecheck_command = profile.typecheck_command or _npm_script(pkg, "typecheck")
        profile.test_command = profile.test_command or _npm_script(pkg, "test")
        profile.build_command = _npm_script(pkg, "build")

    if "tsconfig.json" in names and not profile.typecheck_command:
        if (root / "node_modules" / ".bin" / "tsc").exists():
            profile.typecheck_command = "npx tsc --noEmit"

    # ---- docs / deploy ---------------------------------------------------
    profile.docs = sorted(
        p for p in names if p.lower() in ("readme.md", "docs", "changelog.md", "contributing.md")
    )
    for hint, marker in (("vercel", "vercel.json"), ("docker", "Dockerfile"), ("railway", "railway.toml")):
        if marker in names:
            profile.deploy_hints.append(hint)

    # ---- git ---------------------------------------------------------------
    has_git = (root / ".git").exists()
    if not has_git:
        # workspace may live inside a parent repository (e.g. monorepo layout)
        for parent in root.parents:
            if (parent / ".git").exists():
                has_git = True
                break
    profile.has_git = has_git
    if has_git:
        status = _run(["git", "status", "--porcelain"], root)
        profile.git_dirty = bool(status)
    else:
        logger.info(f"project {root} has no git repo")

    # ---- structure -----------------------------------------------------------
    dirs = sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and p.name not in ("node_modules", "__pycache__", ".venv", ".next")
    )[:12]
    profile.structure_summary = ", ".join(dirs) or "(flat)"
    return profile
