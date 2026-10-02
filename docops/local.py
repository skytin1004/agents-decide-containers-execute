"""Durable local rehearsal transport. It does not emulate Foundry or Azure."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from .checks import execute, markdown_report
from .contracts import RequestConflict, WorkRequest


class LocalStore:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.db = directory / "work.db"
        with self.transaction() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS work (id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL, owner TEXT, result TEXT, error TEXT)")

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self.db, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def submit(self, request: WorkRequest) -> dict:
        if not request.actions:
            return {"request_id": request.request_id, "status": "no_action"}
        with self.transaction() as conn:
            prior = conn.execute("SELECT * FROM work WHERE id=?", (request.request_id,)).fetchone()
            if prior:
                if prior["digest"] != request.digest:
                    raise RequestConflict("request_id is already bound to a different payload")
                return {"request_id": request.request_id, "status": "duplicate", "existing_status": prior["status"]}
            conn.execute("INSERT INTO work (id,digest,payload,status) VALUES (?,?,?,'queued')",
                         (request.request_id, request.digest, request.canonical_json()))
        return {"request_id": request.request_id, "status": "queued"}

    def claim(self, now=None, lease_seconds=60):
        now = time.time() if now is None else now
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM work WHERE status='queued' OR (status='running' AND lease_until<?) ORDER BY rowid LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            owner = uuid.uuid4().hex
            conn.execute("UPDATE work SET status='running',attempts=attempts+1,lease_until=?,owner=? WHERE id=?",
                         (now + lease_seconds, owner, row["id"]))
            return WorkRequest.parse(json.loads(row["payload"])), owner

    def finish(self, request: WorkRequest, owner: str, result: dict):
        with self.transaction() as conn:
            changed = conn.execute("UPDATE work SET status='completed',result=?,error=NULL,lease_until=NULL WHERE id=? AND owner=? AND status='running' AND lease_until>=?",
                                   (json.dumps(result), request.request_id, owner, time.time())).rowcount
            if changed != 1:
                raise RuntimeError("Worker lost its lease; it cannot complete this request")
        self.export(request.request_id)

    def export(self, request_id: str):
        row = self.get(request_id)
        if row is None or row["status"] != "completed":
            raise ValueError("No completed report for this request")
        out = self.directory / "reports" / request_id
        out.mkdir(parents=True, exist_ok=True)
        result = json.loads(row["result"])
        (out / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (out / "report.md").write_text(markdown_report(result), encoding="utf-8")
        return out

    def fail(self, request: WorkRequest, owner: str, error: str):
        with self.transaction() as conn:
            conn.execute("UPDATE work SET status=CASE WHEN attempts>=3 THEN 'poison' ELSE 'queued' END,error=?,lease_until=NULL WHERE id=? AND owner=? AND status='running'",
                         (error, request.request_id, owner))

    def get(self, request_id: str):
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM work WHERE id=?", (request_id,)).fetchone()
            return dict(row) if row else None

    def run_one(self, fail_once=False):
        claim = self.claim()
        if claim is None:
            return {"status": "idle"}
        request, owner = claim
        try:
            if fail_once:
                raise RuntimeError("Injected rehearsal failure before checks")
            result = execute(request)
            self.finish(request, owner, result)
            return result
        except Exception as exc:
            self.fail(request, owner, str(exc))
            raise
