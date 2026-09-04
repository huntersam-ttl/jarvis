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
    assert version == "3"
    # legacy data preserved and still readable
    assert store.get("legacy1")["id"] == "legacy1"
    # new writes work with recovery columns
    store.save({"id": "new1", "status": "working", "checkpoint": "TASK_CREATED",
                "phase": "RECOVERING", "project_path": "/tmp/x"})
    assert store.get("new1")["checkpoint"] == "TASK_CREATED"


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "idem.db"
    s1 = TaskStore(db)
    s1.save({"id": "a", "status": "working", "checkpoint": "TASK_CREATED",
             "phase": "RECOVERING", "project_path": "/tmp/x"})
    s2 = TaskStore(db)  # second open — migration must be a no-op
    version = s2._conn.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone()[0]
    assert version == "3"
    assert s2.get("a")["id"] == "a"


# ---------------------------------------------------------------- budget persistence
@pytest.mark.asyncio
async def test_execution_config_persists_on_submit(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    store = TaskStore(tmp_path / "tasks.db")

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    task = await agent.submit(
        "run checks", str(tmp_path), max_steps=7, max_repair_loops=3,
        max_reviewer_calls=0, max_cost_usd=1.5, auto_commit=False,
    )
    await _wait_done(task)
    assert task.status == "completed"

    persisted = store.get(task.id)
    cfg = persisted["execution_config"]
    assert cfg["max_steps"] == 7
    assert cfg["max_repair_loops"] == 3
    assert cfg["max_reviewer_calls"] == 0
    assert cfg["max_cost_usd"] == 1.5
    assert cfg["auto_commit"] is False


# ---------------------------------------------------------------- budget restore on recovery
@pytest.mark.asyncio
async def test_custom_max_repair_loops_survives_restart(git_ws):
    ws, branch, store_path = git_ws
    (ws / "test_bad.py").write_text("def test_bad():\n    assert False\n")  # pre-existing
    (ws / "code.py").write_text("x = 2\n")  # Jarvis change
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch=branch, changed_files=["code.py"],
        git_baseline={"branch": branch, "changed_files": ["test_bad.py"]},
        execution_config={"max_repair_loops": 0},
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    # zero repair loops => immediate completion denial, no repair attempt
    assert results[0]["status"] == "failed"
    persisted = store.get("rec001")
    assert "COMPLETION DENIED" in (persisted["last_error"] or "")
    assert persisted["repair_loops"] == 0


@pytest.mark.asyncio
async def test_custom_max_reviewer_calls_survives_restart(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    task = _make_task(
        ws, "VERIFICATION_COMPLETE",
        git_branch=branch, changed_files=[],
        verification={"passed": True, "summary": "all checks passed", "checks": []},
        execution_config={"max_reviewer_calls": 0},
    )
    store.save(task.model_dump())

    class MustNotCall:
        name = "fake"
        last_usage = None

        async def chat(self, message, model=None):
            raise AssertionError("reviewer budget of 0 must skip the review call")

    agent = CodingAgent(provider=MustNotCall(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"
    assert store.get("rec001")["review"] is None  # review skipped, not failed


@pytest.mark.asyncio
async def test_custom_max_cost_usd_survives_restart(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    task = _make_task(
        ws, "PLAN_COMPLETE",
        execution_config={"max_cost_usd": 0.5, "max_steps": 6},
    )
    store.save(task.model_dump())

    class CostlyProvider:
        name = "fake"
        last_usage = {"total_cost": 1.0, "total_tokens": 100}

        async def chat(self, message, model=None):
            return json.dumps({
                "thought": "inspect", "tool": "git_status", "args": {},
            }), "fake-model"

    agent = CodingAgent(provider=CostlyProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "Cost budget" in (store.get("rec001")["last_error"] or "")


# ---------------------------------------------------------------- git baseline
@pytest.mark.asyncio
async def test_baseline_captured_before_implementation(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    task = await agent.submit("run checks", str(ws), max_steps=5)
    await _wait_done(task)

    assert task.git_baseline is not None
    assert task.git_baseline.changed_files == []  # clean repo before mutation
    assert task.git_baseline.head  # HEAD hash recorded
    assert task.git_baseline.branch == branch


@pytest.mark.asyncio
async def test_clean_repo_baseline_recovery(git_ws):
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ws,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    task = _make_task(
        ws, "PLAN_COMPLETE",
        git_baseline={"branch": branch, "head": head, "changed_files": []},
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_preexisting_dirty_file_does_not_block_recovery(git_ws):
    """User's notes.md was dirty before the task; Jarvis changed app.py."""
    ws, branch, store_path = git_ws
    (ws / "notes.md").write_text("user edits\n")          # pre-existing dirty
    (ws / "backend").mkdir()
    (ws / "backend" / "app.py").write_text("x = 2\n")     # Jarvis change
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch=branch,
        changed_files=["backend/app.py"],
        git_baseline={"branch": branch, "changed_files": ["notes.md"]},
        execution_config={"auto_commit": False},  # never commit the user's file
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"
    # user's pre-existing change untouched and still uncommitted
    assert (ws / "notes.md").read_text() == "user edits\n"
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ws,
        capture_output=True, text=True, check=True,
    ).stdout
    assert "notes.md" in status  # never committed by Jarvis


@pytest.mark.asyncio
async def test_unexpected_new_changed_file_still_blocks(git_ws):
    ws, branch, store_path = git_ws
    (ws / "notes.md").write_text("user edits\n")       # baseline
    (ws / "backend").mkdir()
    (ws / "backend" / "app.py").write_text("x = 2\n")  # Jarvis
    (ws / "sneaky.py").write_text("???\n")             # neither — conflict
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch=branch,
        changed_files=["backend/app.py"],
        git_baseline={"branch": branch, "changed_files": ["notes.md"]},
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "unexpected changed files" in (store.get("rec001")["last_error"] or "")


@pytest.mark.asyncio
async def test_branch_mismatch_still_blocks_with_baseline(git_ws):
    ws, branch, store_path = git_ws
    (ws / "code.py").write_text("x = 2\n")
    store = TaskStore(store_path)
    task = _make_task(
        ws, "FILES_CHANGED",
        git_branch="feature/other", changed_files=["code.py"],
        git_baseline={"branch": "feature/other", "changed_files": []},
    )
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "branch changed" in (store.get("rec001")["last_error"] or "")


# ---------------------------------------------------------------- legacy compatibility
@pytest.mark.asyncio
async def test_legacy_task_without_baseline_or_budget_loads_safely(git_ws):
    """Pre-baseline persisted task: defaults used, no crash, baseline captured."""
    ws, branch, store_path = git_ws
    store = TaskStore(store_path)
    task = _make_task(ws, "PLAN_COMPLETE")  # no execution_config, no baseline
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "completed"
    persisted = store.get("rec001")
    assert persisted["execution_config"] is None  # defaults were used
    assert persisted["git_baseline"] is not None  # baseline captured going forward


@pytest.mark.asyncio
async def test_legacy_task_strict_rules_still_apply(git_ws):
    ws, branch, store_path = git_ws
    (ws / "code.py").write_text("x = 2\n")
    store = TaskStore(store_path)
    # no baseline: legacy exact-set rule — dirty repo on early checkpoint fails
    task = _make_task(ws, "PLAN_COMPLETE")
    store.save(task.model_dump())

    agent = CodingAgent(provider=DoneProvider(), on_update=store.save)
    service = _service(agent, ws, store)
    results = await service.recover_interrupted()

    assert results[0]["status"] == "failed"
    assert "unexpectedly dirty" in (store.get("rec001")["last_error"] or "")

