from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from backend.schemas import AuditEvent, CaseRecord, CaseStatus, LoopRunRecord


class SQLiteStore:
    def __init__(self, db_path: str):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._initialise()

    def _initialise(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    route TEXT NOT NULL,
                    record_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    node TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS loop_runs (
                    run_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    loop_name TEXT NOT NULL,
                    terminal_state TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    record_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
                CREATE INDEX IF NOT EXISTS idx_audit_case_time ON audit_events(case_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_loop_case_time ON loop_runs(case_id, started_at);
                CREATE INDEX IF NOT EXISTS idx_loop_name_state ON loop_runs(loop_name, terminal_state);
                """
            )

    def save_case(self, record: CaseRecord) -> None:
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO cases(case_id, created_at, updated_at, status, route, record_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    route=excluded.route,
                    record_json=excluded.record_json
                """,
                (
                    record.case_id,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.status.value,
                    record.risk.route.value,
                    payload,
                ),
            )

    def get_case(self, case_id: str) -> CaseRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT record_json FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
        if row is None:
            return None
        return CaseRecord.model_validate(json.loads(row["record_json"]))

    def list_cases(self, *, statuses: set[CaseStatus] | None = None) -> list[CaseRecord]:
        with self._lock:
            if statuses:
                values = sorted(status.value for status in statuses)
                placeholders = ",".join("?" for _ in values)
                rows = self._conn.execute(
                    f"SELECT record_json FROM cases WHERE status IN ({placeholders}) ORDER BY created_at DESC",
                    values,
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT record_json FROM cases ORDER BY created_at DESC"
                ).fetchall()
        return [CaseRecord.model_validate(json.loads(row["record_json"])) for row in rows]

    def append_audit(self, event: AuditEvent) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO audit_events(event_id, case_id, timestamp, event_type, node, message, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.case_id,
                    event.timestamp.isoformat(),
                    event.event_type,
                    event.node,
                    event.message,
                    json.dumps(event.details, ensure_ascii=False, default=str),
                ),
            )

    def get_audit(self, case_id: str) -> list[AuditEvent]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT event_id, case_id, timestamp, event_type, node, message, details_json
                FROM audit_events WHERE case_id = ? ORDER BY timestamp, rowid
                """,
                (case_id,),
            ).fetchall()
        return [
            AuditEvent.model_validate(
                {
                    "event_id": row["event_id"],
                    "case_id": row["case_id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "node": row["node"],
                    "message": row["message"],
                    "details": json.loads(row["details_json"]),
                }
            )
            for row in rows
        ]

    def save_loop_run(self, run: LoopRunRecord) -> None:
        payload = json.dumps(run.model_dump(mode="json"), ensure_ascii=False, default=str)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO loop_runs(run_id, case_id, loop_name, terminal_state, decision, started_at, ended_at, record_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    terminal_state=excluded.terminal_state,
                    decision=excluded.decision,
                    ended_at=excluded.ended_at,
                    record_json=excluded.record_json
                """,
                (
                    run.run_id,
                    run.case_id,
                    run.loop_name,
                    run.terminal_state,
                    run.decision,
                    run.started_at.isoformat(),
                    run.ended_at.isoformat(),
                    payload,
                ),
            )

    def get_loop_runs(self, case_id: str | None = None, *, limit: int = 500) -> list[LoopRunRecord]:
        with self._lock:
            if case_id:
                rows = self._conn.execute(
                    "SELECT record_json FROM loop_runs WHERE case_id = ? ORDER BY started_at, rowid LIMIT ?",
                    (case_id, max(1, min(limit, 2000))),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT record_json FROM loop_runs ORDER BY started_at DESC, rowid DESC LIMIT ?",
                    (max(1, min(limit, 2000)),),
                ).fetchall()
        return [LoopRunRecord.model_validate(json.loads(row["record_json"])) for row in rows]

    def loop_summary(self, *, case_id: str | None = None) -> dict:
        runs = self.get_loop_runs(case_id=case_id, limit=2000)
        by_state: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        by_loop: dict[str, int] = {}
        unauthorized = 0
        no_progress = 0
        bounded = 0
        retries = 0
        elapsed = 0
        for run in runs:
            by_state[run.terminal_state] = by_state.get(run.terminal_state, 0) + 1
            by_decision[run.decision] = by_decision.get(run.decision, 0) + 1
            by_loop[run.loop_name] = by_loop.get(run.loop_name, 0) + 1
            unauthorized += len(run.unauthorized_tool_attempts)
            no_progress += int(run.no_progress_detected)
            bounded += int(run.bounded)
            retries += max(0, run.attempt_number - 1)
            elapsed += run.elapsed_ms
        total = len(runs)
        return {
            "case_id": case_id,
            "total_runs": total,
            "bounded_runs": bounded,
            "bounded_rate": (bounded / total) if total else 1.0,
            "total_retries": retries,
            "unauthorized_tool_attempts": unauthorized,
            "no_progress_stops": no_progress,
            "average_elapsed_ms": round(elapsed / total) if total else 0,
            "by_terminal_state": by_state,
            "by_decision": by_decision,
            "by_loop": by_loop,
        }


    def summary(self) -> dict:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS count FROM cases").fetchone()["count"]
            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) AS count FROM cases GROUP BY status ORDER BY status"
            ).fetchall()
            route_rows = self._conn.execute(
                "SELECT route, COUNT(*) AS count FROM cases GROUP BY route ORDER BY route"
            ).fetchall()
        return {
            "total": int(total),
            "by_status": {row["status"]: int(row["count"]) for row in status_rows},
            "by_route": {row["route"]: int(row["count"]) for row in route_rows},
        }

    def delete_all(self) -> dict[str, int]:
        with self._lock, self._conn:
            audit_count = self._conn.execute(
                "SELECT COUNT(*) AS count FROM audit_events"
            ).fetchone()["count"]
            case_count = self._conn.execute(
                "SELECT COUNT(*) AS count FROM cases"
            ).fetchone()["count"]
            loop_count = self._conn.execute(
                "SELECT COUNT(*) AS count FROM loop_runs"
            ).fetchone()["count"]
            self._conn.execute("DELETE FROM loop_runs")
            self._conn.execute("DELETE FROM audit_events")
            self._conn.execute("DELETE FROM cases")
        return {
            "cases_deleted": int(case_count),
            "audit_events_deleted": int(audit_count),
            "loop_runs_deleted": int(loop_count),
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
