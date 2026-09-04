"""Durable checkpoint + restart-recovery tests for the Engineering Agent."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess

import pytest

from app.agents.coding.agent import CodingAgent
from app.agents.coding.schemas import CodingTask
from app.agents.coding.service import CodingAgentService
from app.agents.coding.storage import TaskStore


async def _wait_done(task, timeout=30):
    for _ in range(int(timeout / 0.05)):
        if task.status != "working":
            return
        await asyncio.sleep(0.05)


class DoneProvider:
    name = "fake"
    last_usage = None

    async def chat(self, message, model=None):
        return json.dumps(
            {"thought": "ok", "done": True, "summary": "recovered"}
        ), "fake-model"


def _git_repo(path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "pytest.ini").write_text("[pytest]\n")
    (path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=path, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return branch


def _make_task(ws, checkpoint, **overrides) -> CodingTask:
    fields = dict(
        id="rec001",
        status="working",
        phase="RECOVERING",
        checkpoint=checkpoint,
        current_task="run the tests",
        project_path=str(ws),
        started_at="2026-01-01T00:00:00+00:00",
    )
    fields.update(overrides)
    return CodingTask(**fields)


def _service(agent, ws, store) -> CodingAgentService:
    return CodingAgentService(
        agent=agent, allowed_projects=[str(ws)], store=store
    )


@pytest.fixture()
def git_ws(tmp_path):
    """Git repo in a subdir; the task store lives OUTSIDE it so the
    porcelain status only reflects real project changes."""
    ws = tmp_path / "proj"
    ws.mkdir()
    branch = _git_repo(ws)
    store_path = tmp_path / "tasks.db"
    return ws, branch, store_path


# ---------------------------------------------------------------- lifecycle checkpoints
@pytest.mark.asyncio
async def test_checkpoints_written_through_lifecycle(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    seen = []

    agent = CodingAgent(
        provider=DoneProvider(), on_update=lambda t: seen.append(t.checkpoint)
    )
    task = await agent.submit("run checks", str(tmp_path), max_steps=5)
    await _wait_done(task)

    assert task.status == "completed"
    assert seen[0] == "TASK_CREATED"
    for cp in ("ANALYSIS_COMPLETE", "PLAN_COMPLETE", "VERIFICATION_COMPLETE", "COMPLETED"):
        assert cp in seen
    assert seen[-1] == "COMPLETED"


# ---------------------------------------------------------------- early checkpoints
@pytest.mark.asyncio
@pytest.mark.parametrize("checkpoint", ["TASK_CREATED", "ANALYSIS_COMPLETE", "PLAN_COMPLETE"])
async def test_early_checkpoint_resumes_to_completion(tmp_path, checkpoint):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    store = TaskStore(tmp_path / "tasks.db")
    task = _make_task(tmp_path, checkpoint)
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, tmp_path, store)
    results = await service.recover_interrupted()

    assert len(results) == 1 and results[0]["status"] == "completed"
    persisted = store.get("rec001")
    assert persisted["status"] == "completed"
    assert persisted["checkpoint"] == "COMPLETED"


# ---------------------------------------------------------------- FILES_CHANGED
@pytest.mark.asyncio
async def test_files_changed_resumes_verification(git_ws):
    ws, branch, store_path = git_ws
    (ws / "code.py").write_text("x = 2\n")  # dirty change
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch=branch, changed_files=["code.py"],
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"
    persisted = store.get("rec001")
    assert persisted["verification"]["passed"] is True
    assert persisted["review"]["verdict"] == "approve"
    assert persisted["checkpoint"] == "COMPLETED"


# ---------------------------------------------------------------- VERIFICATION_COMPLETE
@pytest.mark.asyncio
async def test_verification_complete_resumes_review(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    task = _make_task(
        ws, "VERIFICATION_COMPLETE",
        git_branch=branch, changed_files=[],
        verification={"passed": True, "summary": "all checks passed", "checks": []},
    )
    store.save(task.model_dump())

    calls = []

    class ReviewProvider:
        name = "fake"
        last_usage = None

        async def chat(self, message, model=None):
            calls.append(message)
            return json.dumps({
                "findings": [], "verdict": "approve", "summary": "clean",
            }), "fake-model"

    agent = CodingAgent(provider=ReviewProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"
    # exactly one fresh-context review call; verification was NOT re-run
    assert len(calls) == 1 and "Diff to review" in calls[0]
    persisted = store.get("rec001")
    assert persisted["review"]["verdict"] == "approve"
    assert persisted["checkpoint"] == "COMPLETED"


# ---------------------------------------------------------------- REVIEW_COMPLETE
@pytest.mark.asyncio
async def test_review_complete_finalizes_without_llm(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    task = _make_task(
        ws, "REVIEW_COMPLETE",
        git_branch=branch, changed_files=[],
        verification={"passed": True, "summary": "all checks passed", "checks": []},
        review={"verdict": "approve", "summary": "clean", "findings": []},
    )
    store.save(task.model_dump())

    class MustNotCall:
        name = "fake"
        last_usage = None

        async def chat(self, message, model=None):
            raise AssertionError("no LLM calls allowed for REVIEW_COMPLETE finalize")

    agent = CodingAgent(provider=MustNotCall(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"
    assert store.get("rec001")["checkpoint"] == "COMPLETED"


@pytest.mark.asyncio
async def test_review_complete_fails_safely_if_rules_no_longer_pass(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    task = _make_task(
        ws, "REVIEW_COMPLETE",
        git_branch=branch, changed_files=[],
        verification={"passed": False, "summary": "failed", "checks": []},
        review={"verdict": "approve", "summary": "clean", "findings": []},
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "safety" in (store.get("rec001")["last_error"] or "").lower()


# ---------------------------------------------------------------- git safety
@pytest.mark.asyncio
async def test_branch_mismatch_fails_safely(git_ws):
    ws, branch, store_path = git_ws
    (ws / "code.py").write_text("x = 2\n")
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch="feature/other", changed_files=["code.py"],
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "branch changed" in (store.get("rec001")["last_error"] or "")


@pytest.mark.asyncio
async def test_changed_files_mismatch_fails_safely(git_ws):
    ws, branch, store_path = git_ws
    (ws / "code.py").write_text("x = 2\n")
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch=branch, changed_files=["totally_other.py"],
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "changed files differ" in (store.get("rec001")["last_error"] or "")


@pytest.mark.asyncio
async def test_dirty_repo_fails_safely_for_early_checkpoint(git_ws):
    ws, branch, store_path = git_ws
    (ws / "code.py").write_text("x = 2\n")  # dirty, but checkpoint predates changes
    store = TaskStore(store_path)
    task = _make_task(ws, "PLAN_COMPLETE")
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "unexpectedly dirty" in (store.get("rec001")["last_error"] or "")


# ---------------------------------------------------------------- terminal states
@pytest.mark.asyncio
async def test_terminal_tasks_never_resume(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    for status in ("completed", "failed", "cancelled"):
        task = _make_task(tmp_path, "VERIFICATION_COMPLETE", status=status)
        store.save({**task.model_dump(), "id": f"t-{status}"})

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, tmp_path, store)
    results = await service.recover_interrupted()

    assert results == []
    for status in ("completed", "failed", "cancelled"):
        assert store.get(f"t-{status}")["status"] == status


@pytest.mark.asyncio
async def test_task_without_checkpoint_fails_safely(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = _make_task(tmp_path, "")
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, tmp_path, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "no checkpoint" in (store.get("rec001")["last_error"] or "")


# ---------------------------------------------------------------- SQLite migration
def test_existing_v1_database_migrates(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO meta VALUES ('schema_version', '1')")
    conn.execute(
        "INSERT INTO tasks VALUES ('legacy1', '2026-01-01', "
        "'{\"id\": \"legacy1\", \"status\": \"completed\"}')"
    )
    conn.commit()
    conn.close()

    store = TaskStore(db)  # triggers migration
    cols = [r[1] for r in store._conn.execute("PRAGMA table_info(tasks)")]
    assert "checkpoint" in cols and "phase" in cols and "status" in cols
    version = store._conn.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone()[0]
    assert version == "2"
    # legacy data preserved and still readable
    assert store.get("legacy1")["id"] == "legacy1"
    # new writes work with recovery columns
    store.save({"id": "new1", "status": "working", "checkpoint": "TASK_CREATED",
                "phase": "RECOVERING", "project_path": "/tmp/x"})
    assert store.get("new1")["checkpoint"] == "TASK_CREATED"

