"""Tests for the Engineering Agent upgrade: skills, analysis, verification
gate, debugging loop, reviewer, persistence, and cost controls."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.agents.base import AgentError
from app.agents.coding.agent import CodingAgent
from app.agents.coding.project_analyzer import analyze_project
from app.agents.coding.storage import TaskStore
from app.agents.coding.verifier import run_verification
from app.skills.loader import load_skills
from app.skills.registry import SkillRegistry


# ---------------------------------------------------------------- helpers
async def _wait_done(task, timeout=30):
    for _ in range(int(timeout / 0.05)):
        if task.status != "working":
            return
        await asyncio.sleep(0.05)


class DoneProvider:
    name = "fake"
    last_usage = None

    def __init__(self, summary="done"):
        self._summary = summary

    async def chat(self, message, model=None):
        return json.dumps(
            {"thought": "nothing to do", "done": True, "summary": self._summary}
        ), "fake-model"


class ScriptedProvider:
    """Replays scripted replies, then repeats the last one."""

    name = "fake"
    last_usage = None

    def __init__(self, replies):
        self.replies = list(replies)
        self._last = None

    async def chat(self, message, model=None):
        if self.replies:
            self._last = self.replies.pop(0)
        return self._last, "fake-model"


# ---------------------------------------------------------------- skills
def test_all_twelve_skills_load():
    skills = load_skills()
    names = {s.name for s in skills}
    assert len(skills) >= 12
    assert "systematic-debugging" in names
    assert "verification-before-completion" in names


def test_skill_metadata_has_attribution():
    for s in load_skills():
        assert s.source.startswith("https://github.com/")
        assert s.attribution
        assert s.task_types


def test_debugging_task_selects_debugging_skills():
    reg = SkillRegistry()
    names = [s.name for s in reg.select("Fix the broken frontend styling")]
    assert "systematic-debugging" in names
    assert "frontend-ui-engineering" in names
    assert "verification-before-completion" in names
    assert len(names) <= 4  # context efficiency cap


def test_api_task_selects_spec_and_security_skills():
    reg = SkillRegistry()
    names = [s.name for s in reg.select("Build a new API with endpoints")]
    assert "api-and-interface-design" in names
    assert "test-driven-development" in names


def test_detection_fallback_for_ambiguous_tasks():
    assert SkillRegistry.detect_task_types("do the thing")


# ---------------------------------------------------------------- project analysis
def test_profile_detects_node_project():
    profile = analyze_project("/Users/cc/jarvis/frontend")
    assert "javascript" in profile.languages or "typescript" in profile.languages
    assert "Next.js" in profile.frameworks
    assert profile.lint_command == "npm run lint"
    assert profile.build_command == "npm run build"
    assert profile.has_git


def test_profile_detects_python_project(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    profile = analyze_project(tmp_path)
    assert "python" in profile.languages
    assert profile.test_command == "pytest -q"


def test_profile_does_not_invent_checks(tmp_path):
    (tmp_path / "data.txt").write_text("hello")
    profile = analyze_project(tmp_path)
    assert profile.verification_checks == []


def test_verification_passes_and_fails(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    assert run_verification(analyze_project(tmp_path)).passed

    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert False\n")
    result = run_verification(analyze_project(tmp_path))
    assert not result.passed
    assert "pytest" in result.failure_digest()


# ---------------------------------------------------------------- verification gate
@pytest.mark.asyncio
async def test_failed_verification_denies_completion(tmp_path):
    """Failing deterministic checks must block COMPLETED."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert False\n")
    agent = CodingAgent(provider=DoneProvider(summary="i think i am done"))
    task = await agent.submit("fix it", str(tmp_path), max_steps=5, max_repair_loops=1)
    await _wait_done(task)
    assert task.status == "failed"
    assert "COMPLETION DENIED" in (task.last_error or "")
    assert task.verification is not None and task.verification.passed is False


@pytest.mark.asyncio
async def test_passing_verification_allows_completion(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    agent = CodingAgent(provider=DoneProvider(summary="verified work"))
    task = await agent.submit("run checks", str(tmp_path), max_steps=5)
    await _wait_done(task)
    assert task.status == "completed"
    assert task.result == "verified work"
    assert task.verification.passed is True


# ---------------------------------------------------------------- lifecycle fields
@pytest.mark.asyncio
async def test_task_lifecycle_metadata(tmp_path):
    agent = CodingAgent(provider=DoneProvider(summary="ok"))
    task = await agent.submit(
        "add a small feature to the app", str(tmp_path), max_steps=5
    )
    await _wait_done(task)
    assert task.status == "completed"
    assert task.phase == "COMPLETED"
    assert task.skills_used
    assert task.plan is not None and task.plan.objective
    assert task.model_calls >= 1


@pytest.mark.asyncio
async def test_planner_skips_llm_for_trivial_tasks(tmp_path):
    agent = CodingAgent(provider=DoneProvider())
    task = await agent.submit("typo", str(tmp_path), max_steps=5)
    await _wait_done(task)
    assert task.plan.complexity == "TRIVIAL"


# ---------------------------------------------------------------- debugging transitions
@pytest.mark.asyncio
async def test_debug_repair_loop_recovers(tmp_path):
    """First verify fails; scripted provider fixes it; second verify passes."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert False\n")
    fix = json.dumps({
        "thought": "fix the test", "tool": "write_file",
        "args": {"path": "test_bad.py", "content": "def test_bad():\n    assert True\n"},
    })
    provider = ScriptedProvider([
        json.dumps({"thought": "done impl", "done": True, "summary": "attempted"}),
        fix,
        json.dumps({"thought": "done", "done": True, "summary": "fixed and verified"}),
    ])
    agent = CodingAgent(provider=provider)
    task = await agent.submit(
        "make tests pass", str(tmp_path), max_steps=5, max_repair_loops=2
    )
    await _wait_done(task)
    assert task.status == "completed"
    assert task.repair_loops >= 1
    assert task.verification.passed is True


# ---------------------------------------------------------------- reviewer
@pytest.mark.asyncio
async def test_reviewer_block_prevents_completion(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "code.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    (tmp_path / "code.py").write_text("x = 2  # changed\n")

    class BlockingProvider:
        name = "fake"
        last_usage = None

        async def chat(self, message, model=None):
            if "Diff to review" in message:
                reply = json.dumps({
                    "findings": [{"severity": "CRITICAL", "file": "code.py",
                                  "issue": "data loss", "suggestion": "fix"}],
                    "verdict": "block", "summary": "dangerous",
                })
            else:
                reply = json.dumps({"thought": "d", "done": True, "summary": "did it"})
            return reply, "fake-model"

    agent = CodingAgent(provider=BlockingProvider())
    task = await agent.submit("change code", str(tmp_path), max_steps=5)
    await _wait_done(task)
    assert task.status == "failed"
    assert "Review blocked" in (task.last_error or "")
    assert task.review.verdict == "block"


# ---------------------------------------------------------------- malformed / limits
@pytest.mark.asyncio
async def test_malformed_json_retries_then_fails(tmp_path):
    provider = ScriptedProvider(["this is not json at all"])
    agent = CodingAgent(provider=provider)
    task = await agent.submit("do something", str(tmp_path), max_steps=5)
    await _wait_done(task)
    assert task.status == "failed"
    assert "malformed" in (task.last_error or "").lower()


@pytest.mark.asyncio
async def test_cost_budget_enforced(tmp_path):
    class CostlyProvider(DoneProvider):
        last_usage = {"total_cost": 1.0, "total_tokens": 500}

        async def chat(self, message, model=None):
            return json.dumps({
                "thought": "inspect", "tool": "git_status", "args": {},
            }), "fake-model"

    agent = CodingAgent(provider=CostlyProvider())
    task = await agent.submit(
        "something long running", str(tmp_path), max_steps=5, max_cost_usd=0.5
    )
    await _wait_done(task)
    assert task.status == "failed"
    assert "Cost budget" in (task.last_error or "")


# ---------------------------------------------------------------- persistence
def test_task_store_roundtrip(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    payload = {"id": "abc123", "status": "completed", "phase": "COMPLETED", "x": 1}
    store.save(payload)
    store.save({**payload, "status": "failed"})  # upsert
    assert store.get("abc123")["status"] == "failed"
    assert any(t["id"] == "abc123" for t in store.load_all())
    assert store.get("missing") is None


# ---------------------------------------------------------------- tools regression
def test_new_tools_respect_security(tmp_path):
    from app.agents.coding.tools import CodingTools, ToolContext, ToolError

    tools = CodingTools(ToolContext(project_root=tmp_path))
    tools.create_directory("src/deep")
    assert (tmp_path / "src" / "deep").is_dir()
    with pytest.raises(ToolError):
        tools.move_path("../outside.txt", "inside.txt")
    with pytest.raises(ToolError):
        tools.git_checkout("bad name; rm -rf")
