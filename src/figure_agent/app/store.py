from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUSES = {"created", "normalizing", "analyzing", "searching_templates", "generating_candidates", "awaiting_review", "assembling", "inspecting", "exporting", "completed", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "figure-agent.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY, status TEXT NOT NULL, request_json TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT
            );
            CREATE TABLE IF NOT EXISTS task_inputs (
              input_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, path TEXT NOT NULL,
              sha256 TEXT NOT NULL, mime_type TEXT, size_bytes INTEGER NOT NULL,
              created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );
            CREATE TABLE IF NOT EXISTS task_versions (
              version_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, version_number INTEGER NOT NULL,
              kind TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
              artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, path TEXT NOT NULL,
              kind TEXT NOT NULL, sha256 TEXT NOT NULL, editable INTEGER NOT NULL DEFAULT 0,
              license TEXT, created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );
            CREATE TABLE IF NOT EXISTS review_actions (
              action_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, action_json TEXT NOT NULL,
              created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );
            CREATE TABLE IF NOT EXISTS llm_runs (
              run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, provider TEXT NOT NULL,
              model TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );
            """)

    def create_task(self, request: dict[str, Any]) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = _now()
        task_dir = self.root / "tasks" / task_id
        for name in ("input", "versions", "candidates", "assets", "reviews", "exports"):
            (task_dir / name).mkdir(parents=True, exist_ok=True)
        (task_dir / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        with self._connect() as db:
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)", (task_id, "created", json.dumps(request, ensure_ascii=False), now, now, None))
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        return result

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT task_id FROM tasks ORDER BY created_at DESC").fetchall()
        return [self.get_task(row["task_id"]) for row in rows]

    def update_status(self, task_id: str, status: str, error: str | None = None) -> dict[str, Any]:
        if status not in STATUSES:
            raise ValueError(f"unsupported task status: {status}")
        with self._connect() as db:
            cursor = db.execute("UPDATE tasks SET status = ?, updated_at = ?, error = ? WHERE task_id = ?", (status, _now(), error, task_id))
            if cursor.rowcount == 0:
                raise KeyError(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def record_review_action(self, task_id: str, action: dict[str, Any]) -> dict[str, Any]:
        if self.get_task(task_id) is None:
            raise KeyError(task_id)
        action_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute("INSERT INTO review_actions VALUES (?, ?, ?, ?)", (action_id, task_id, json.dumps(action, ensure_ascii=False), _now()))
        return {"action_id": action_id, "task_id": task_id, "action": action}

    def register_artifact(self, task_id: str, path: str | Path, kind: str, *, editable: bool = False, license: str | None = None) -> dict[str, Any]:
        if self.get_task(task_id) is None:
            raise KeyError(task_id)
        file_path = Path(path)
        payload = file_path.read_bytes()
        artifact_id = str(uuid.uuid4())
        record = {"artifact_id": artifact_id, "task_id": task_id, "path": str(file_path), "kind": kind, "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload), "mime_type": mimetypes.guess_type(file_path.name)[0], "editable": editable, "license": license, "created_at": _now()}
        with self._connect() as db:
            db.execute("INSERT INTO artifacts (artifact_id, task_id, path, kind, sha256, editable, license, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (artifact_id, task_id, str(file_path), kind, record["sha256"], int(editable), license, record["created_at"]))
        return record
