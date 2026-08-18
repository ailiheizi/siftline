from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Result, utc_now

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    query_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    query TEXT NOT NULL,
    params TEXT NOT NULL,
    cache TEXT NOT NULL,
    ttl INTEGER NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    outcome TEXT,
    provider_called INTEGER,
    error_codes TEXT
);
"""

# Stable machine-research outcomes for the ledger. Each row carries exactly one.
OUTCOMES = (
    "validation_failed",  # dispatched request rejected before a provider/transport call
    "cache_hit",  # served locally; provider_called is false
    "provider_succeeded",  # external provider/transport called and result usable
    "postprocess_failed",  # provider/transport returned but decode/parse/normalize failed
    "provider_failed",  # external provider/transport call attempted and failed
    "internal_failed",  # unexpected CLI or provider construction failure
)

_LEGACY_OUTCOME = "unknown"


def _as_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


class Storage:
    """SQLite-backed response cache + reproducible machine research ledger, one DB file.

    The query_log table is the backward-compatible machine ledger: pre-v4.1 rows
    (without outcome/provider_called/error_codes) survive migration and are read
    back as ``outcome="unknown"`` with a truthful ``provider_called=null`` instead
    of an invented call count.
    """

    def __init__(self, path: Path | str, ttl_seconds: int, enabled: bool = True) -> None:
        self.path = Path(path)
        self.ttl_seconds = int(ttl_seconds)
        self.enabled = enabled
        self._conn: sqlite3.Connection | None = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path), timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(_SCHEMA)
            self._migrate(conn)
            conn.commit()
            self._conn = conn
        return self._conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add v4.1 ledger columns without destroying existing rows.

        ``CREATE TABLE IF NOT EXISTS`` alone cannot add columns to an existing
        table, so inspect PRAGMA table_info and ALTER for each missing column.
        New columns stay nullable so pre-migration rows are honest unknowns.
        """
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(query_log)")}
        if "outcome" not in existing:
            conn.execute("ALTER TABLE query_log ADD COLUMN outcome TEXT")
        if "provider_called" not in existing:
            conn.execute("ALTER TABLE query_log ADD COLUMN provider_called INTEGER")
        if "error_codes" not in existing:
            conn.execute("ALTER TABLE query_log ADD COLUMN error_codes TEXT")

    # -- cache ---------------------------------------------------------------

    def cache_key(self, provider: str, operation: str, query: str, params: dict[str, Any]) -> str:
        blob = _json_dumps([provider, operation, query, params])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def cache_get(self, key: str) -> Result | None:
        if not self.enabled:
            return None
        row = self._db().execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        try:
            result = Result.model_validate_json(row["value"])
        except Exception:
            return None
        if self._expired(result.retrieved_at):
            self._db().execute("DELETE FROM cache WHERE key = ?", (key,))
            self._db().commit()
            return None
        return result

    def cache_set(self, key: str, result: Result) -> None:
        if not self.enabled:
            return
        self._db().execute(
            "INSERT OR REPLACE INTO cache (key, value, retrieved_at, created_at)"
            " VALUES (?, ?, ?, ?)",
            (key, result.model_dump_json(), result.retrieved_at, utc_now()),
        )
        self._db().commit()

    def _expired(self, retrieved_at: str) -> bool:
        try:
            age = datetime.now(UTC) - _as_utc(retrieved_at)
        except ValueError:
            return True
        return age.total_seconds() > self.ttl_seconds

    # -- machine research ledger (query_log) ----------------------------------

    def log_append(self, entry: dict[str, Any]) -> None:
        """Append one ledger row.

        Backward compatible: a dict without the v4.1 keys stores NULLs for
        ``outcome``/``provider_called``/``error_codes``, which read back as an
        honest ``unknown`` row rather than a fabricated call count.
        """
        codes = entry.get("error_codes")
        self._db().execute(
            "INSERT INTO query_log (ts, query_id, provider, operation, query, params, cache, ttl,"
            " elapsed_ms, item_count, error_count, outcome, provider_called, error_codes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.get("ts", utc_now()),
                entry.get("query_id", ""),
                entry.get("provider", ""),
                entry.get("operation", ""),
                entry.get("query", ""),
                _json_dumps(entry.get("params", {})),
                entry.get("cache", "miss"),
                int(entry.get("ttl", self.ttl_seconds)),
                int(entry.get("elapsed_ms", 0)),
                int(entry.get("item_count", 0)),
                int(entry.get("error_count", 0)),
                entry.get("outcome"),
                entry.get("provider_called"),
                None if codes is None else _json_dumps(codes),
            ),
        )
        self._db().commit()

    def log_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        """Raw, newest-first history (``siftline cache log``).

        Backward compatible with the pre-v4.1 shape while now exposing the added
        ledger fields (outcome, provider_called, error_codes, legacy).
        """
        rows = (
            self._db()
            .execute("SELECT * FROM query_log ORDER BY id DESC LIMIT ?", (int(limit),))
            .fetchall()
        )
        return [self._row_to_entry(row) for row in rows]

    def ledger(self, query_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Machine research ledger: stable summary plus newest-first entries.

        ``query_id`` filters by a stable research-run id; when omitted, recent
        history is returned. Summary counts are derived only from the returned
        entries, so legacy ``unknown`` rows surface as ``unclassified`` instead
        of being attributed to any outcome.
        """
        rows = (
            self._db()
            .execute(
                "SELECT * FROM query_log WHERE (? IS NULL OR query_id = ?)"
                " ORDER BY id DESC LIMIT ?",
                (query_id, query_id, int(limit)),
            )
            .fetchall()
        )
        entries = [self._row_to_entry(row) for row in rows]
        return {"summary": self._summarize(entries), "entries": entries}

    def _row_to_entry(self, row: sqlite3.Row) -> dict[str, Any]:
        entry = dict(row)
        try:
            entry["params"] = json.loads(entry.get("params") or "{}")
        except json.JSONDecodeError:
            entry["params"] = {}

        raw_codes = entry.get("error_codes")
        if raw_codes is None:
            entry["error_codes"] = None
        else:
            try:
                entry["error_codes"] = json.loads(raw_codes)
            except json.JSONDecodeError:
                entry["error_codes"] = None

        outcome = entry.get("outcome")
        legacy = outcome is None or outcome == ""
        entry["outcome"] = _LEGACY_OUTCOME if legacy else outcome
        entry["legacy"] = legacy

        provider_called = entry.get("provider_called")
        entry["provider_called"] = None if provider_called is None else bool(provider_called)
        return entry

    @staticmethod
    def _summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
        summary = {
            "attempts": len(entries),
            "provider_calls": 0,
            "unknown_provider_call_states": 0,
            "cache_hits": 0,
            "validation_failures": 0,
            "provider_successes": 0,
            "postprocess_failures": 0,
            "provider_failures": 0,
            "internal_failures": 0,
            "unclassified": 0,
        }
        outcome_keys = {
            "cache_hit": "cache_hits",
            "validation_failed": "validation_failures",
            "provider_succeeded": "provider_successes",
            "postprocess_failed": "postprocess_failures",
            "provider_failed": "provider_failures",
            "internal_failed": "internal_failures",
        }
        for entry in entries:
            # provider_calls counts only true; a null provider_called is an
            # honest unknown (legacy rows, or an unexpected exception escaping an
            # existing provider's run) and is counted separately instead of being
            # misread as either true or false.
            if entry.get("provider_called") is True:
                summary["provider_calls"] += 1
            elif entry.get("provider_called") is None:
                summary["unknown_provider_call_states"] += 1
            outcome = entry.get("outcome")
            key = outcome_keys.get(outcome) if isinstance(outcome, str) else None
            if key is None:
                summary["unclassified"] += 1
            else:
                summary[key] += 1
        return summary

    # -- administration ------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        db = self._db()
        cache_entries = db.execute("SELECT COUNT(*) AS c FROM cache").fetchone()["c"]
        log_entries = db.execute("SELECT COUNT(*) AS c FROM query_log").fetchone()["c"]
        size_bytes = os.path.getsize(self.path) if self.path.exists() else 0
        return {
            "path": str(self.path),
            "exists": self.path.exists(),
            "size_bytes": size_bytes,
            "cache_entries": int(cache_entries),
            "log_entries": int(log_entries),
            "ttl_seconds": self.ttl_seconds,
            "enabled": self.enabled,
        }

    def clear(self) -> dict[str, Any]:
        db = self._db()
        cache_removed = db.execute("DELETE FROM cache").rowcount
        log_removed = db.execute("DELETE FROM query_log").rowcount
        db.commit()
        return {"cache_removed": int(cache_removed), "log_removed": int(log_removed)}

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
