"""
audit_log.py — Persistent audit logging to SQLite.

Requirement: "Log all API calls and reasoning steps for auditability"

Every search is written to audit_log.db with:
  - timestamp, query, origin, destination, date, budget
  - options_count, recommendation
  - full reasoning_trace (JSON)
  - was_blocked (ethics flag) + block_reason
  - session_id (to group multi-turn conversations)
"""

import sqlite3
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("audit_log.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT,
                timestamp       TEXT,
                query           TEXT,
                origin          TEXT,
                destination     TEXT,
                travel_date     TEXT,
                budget          TEXT,
                options_count   INTEGER,
                recommendation  TEXT,
                reasoning_trace TEXT,
                was_blocked     INTEGER DEFAULT 0,
                block_reason    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id     INTEGER,
                timestamp     TEXT,
                tool_name     TEXT,
                origin        TEXT,
                destination   TEXT,
                travel_date   TEXT,
                result_count  INTEGER,
                error         TEXT,
                FOREIGN KEY (search_id) REFERENCES searches(id)
            )
        """)
        conn.commit()
    logger.info("Audit DB initialised at %s", DB_PATH.resolve())


def log_search(
    session_id: str,
    query: str,
    state: dict,
    was_blocked: bool = False,
    block_reason: str = "",
) -> int:
    """
    Write one complete search interaction to the DB.
    Returns the inserted row id (used to attach tool_call rows).
    """
    recommendation = state.get("recommendation", {})
    reasoning_trace = state.get("reasoning_trace", [])

    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO searches
              (session_id, timestamp, query, origin, destination,
               travel_date, budget, options_count, recommendation,
               reasoning_trace, was_blocked, block_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                query,
                state.get("origin"),
                state.get("destination"),
                state.get("date"),
                str(state.get("budget", "")),
                len(state.get("travel_options", [])),
                json.dumps(recommendation),
                json.dumps(reasoning_trace),
                int(was_blocked),
                block_reason,
            ),
        )
        conn.commit()
        return cur.lastrowid


def log_tool_call(
    search_id: int,
    tool_name: str,
    origin: str,
    destination: str,
    travel_date: str,
    result_count: int,
    error: str = "",
) -> None:
    """Log an individual MCP tool invocation (called from tool_node)."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tool_calls
              (search_id, timestamp, tool_name, origin, destination,
               travel_date, result_count, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                search_id,
                datetime.now(timezone.utc).isoformat(),
                tool_name,
                origin,
                destination,
                travel_date,
                result_count,
                error,
            ),
        )
        conn.commit()


def get_recent_searches(limit: int = 20) -> list[dict]:
    """Fetch recent searches for the admin view in app.py."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM searches ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]