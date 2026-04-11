"""
Scenario catalog — SQLite-backed persistence layer.

Stores scenario definitions, run history, and metric trends.
Enables:
  - Querying historical pass rates per category
  - Detecting flaky scenarios (high variance in outcomes)
  - Trend analysis across model versions
  - Deduplication of scenario runs
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id     TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    description     TEXT,
    map_id          TEXT,
    tags            TEXT,          -- JSON array
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id     TEXT NOT NULL,
    model_version   TEXT,
    status          TEXT NOT NULL,
    duration_s      REAL,
    metrics         TEXT,          -- JSON object
    violations      TEXT,          -- JSON array
    weighted_score  REAL,
    ran_at          TEXT NOT NULL,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_scenario ON runs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_runs_model    ON runs(model_version);
CREATE INDEX IF NOT EXISTS idx_runs_status   ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_ran_at   ON runs(ran_at);
"""


@dataclass
class RunRecord:
    scenario_id: str
    status: str
    duration_s: float
    metrics: dict
    violations: list[str]
    weighted_score: float
    model_version: str = "unknown"
    ran_at: str = ""

    def __post_init__(self) -> None:
        if not self.ran_at:
            self.ran_at = datetime.now(timezone.utc).isoformat()


class ScenarioCatalog:
    """
    SQLite-backed catalog for scenario definitions and run history.

    Thread-safe via per-call connection context managers.
    """

    def __init__(self, db_path: Path = Path("catalog/av_sim.db")) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(DB_SCHEMA)

    # --- Scenario registration ---

    def register_scenario(self, scenario) -> None:
        """Upsert a scenario definition into the catalog."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scenarios
                    (scenario_id, category, description, map_id, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario.scenario_id,
                    scenario.category.value,
                    scenario.description,
                    scenario.map_id,
                    json.dumps(scenario.tags),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def register_scenarios_bulk(self, scenarios: list) -> None:
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO scenarios
                    (scenario_id, category, description, map_id, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        s.scenario_id,
                        s.category.value,
                        s.description,
                        s.map_id,
                        json.dumps(s.tags),
                        datetime.now(timezone.utc).isoformat(),
                    )
                    for s in scenarios
                ],
            )

    # --- Run recording ---

    def record_run(self, record: RunRecord) -> int:
        """Insert a run result. Returns the new run_id."""
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs
                    (scenario_id, model_version, status, duration_s,
                     metrics, violations, weighted_score, ran_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.scenario_id,
                    record.model_version,
                    record.status,
                    record.duration_s,
                    json.dumps(record.metrics),
                    json.dumps(record.violations),
                    record.weighted_score,
                    record.ran_at,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def record_runs_bulk(self, records: list[RunRecord]) -> None:
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT INTO runs
                    (scenario_id, model_version, status, duration_s,
                     metrics, violations, weighted_score, ran_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.scenario_id, r.model_version, r.status, r.duration_s,
                        json.dumps(r.metrics), json.dumps(r.violations),
                        r.weighted_score, r.ran_at,
                    )
                    for r in records
                ],
            )

    # --- Queries ---

    def pass_rate_by_category(self, model_version: str | None = None) -> dict[str, float]:
        """Return pass rate per scenario category."""
        query = """
            SELECT s.category,
                   SUM(CASE WHEN r.status = 'passed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pass_rate
            FROM runs r
            JOIN scenarios s ON r.scenario_id = s.scenario_id
            {where}
            GROUP BY s.category
        """
        where = "WHERE r.model_version = ?" if model_version else ""
        params = (model_version,) if model_version else ()
        with self._conn() as conn:
            rows = conn.execute(query.format(where=where), params).fetchall()
        return {row["category"]: round(row["pass_rate"], 4) for row in rows}

    def flaky_scenarios(self, min_runs: int = 5, max_pass_rate: float = 0.8) -> list[dict]:
        """Return scenarios with inconsistent outcomes (potential flakiness)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT scenario_id,
                       COUNT(*) as total_runs,
                       SUM(CASE WHEN status='passed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as pass_rate
                FROM runs
                GROUP BY scenario_id
                HAVING total_runs >= ? AND pass_rate < ? AND pass_rate > 0.0
                ORDER BY pass_rate ASC
                """,
                (min_runs, max_pass_rate),
            ).fetchall()
        return [dict(r) for r in rows]

    def metric_trend(self, scenario_id: str, metric: str, last_n: int = 20) -> list[float]:
        """Return the last N values of a metric for a scenario (oldest first)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT metrics FROM runs
                WHERE scenario_id = ?
                ORDER BY ran_at DESC
                LIMIT ?
                """,
                (scenario_id, last_n),
            ).fetchall()
        values = []
        for row in reversed(rows):
            m = json.loads(row["metrics"])
            if metric in m:
                values.append(m[metric])
        return values

    def recent_runs(self, limit: int = 100, model_version: str | None = None) -> list[dict]:
        where = "WHERE model_version = ?" if model_version else ""
        params = (model_version, limit) if model_version else (limit,)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM runs {where} ORDER BY ran_at DESC LIMIT ?", params
            ).fetchall()
        return [dict(r) for r in rows]
