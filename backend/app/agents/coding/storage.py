"""Lightweight SQLite persistence for engineering tasks.

Schema is intentionally tiny: one JSON payload column per task, versioned
by a schema marker row. No secrets are ever stored (task payloads contain
no keys). Tasks survive a backend restart.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger

logger = get_logger("jarvis.agents.coding.storage")

SCHEMA_VERSION = 2


class TaskStore:
    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY, value TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Deterministic in-place schema migration. Never drops data."""
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        version = int(row[0]) if row else 1
        if version < 2:
            # v2: recovery columns for indexed checkpoint/phase queries.
            for column in (
                "checkpoint TEXT DEFAULT ''",
                "phase TEXT",
                "status TEXT",
                "project_path TEXT",
            ):
                try:
                    self._conn.execute(f"ALTER TABLE tasks ADD COLUMN {column}")
                except sqlite3.OperationalError:
                    pass  # column already exists — idempotent migration
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)"
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '2')"
            )
            self._conn.commit()

    def save(self, task_dict) -> None:
        if hasattr(task_dict, "model_dump"):
            task_dict = task_dict.model_dump()
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks "
                "(id, updated_at, payload, checkpoint, phase, status, project_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    task_dict["id"],
                    task_dict.get("finished_at") or task_dict.get("started_at") or "",
                    json.dumps(task_dict),
                    task_dict.get("checkpoint", ""),
                    task_dict.get("phase", ""),
                    task_dict.get("status", ""),
                    task_dict.get("project_path", ""),
                ),
            )
            self._conn.commit()
        except Exception:
            logger.exception("failed to persist task %s", task_dict.get("id"))

    def get(self, task_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT payload FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def load_all(self) -> List[dict]:
        rows = self._conn.execute(
            "SELECT payload FROM tasks ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
