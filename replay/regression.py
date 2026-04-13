"""
Replay-based regression testing.

Loads recorded real-world drive logs, converts them to sim scenarios,
runs them through the current AV stack, and compares against a stored baseline.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from metrics.scoring import MetricsScorer
from runner.engine import RunResult, RunStatus

logger = logging.getLogger(__name__)

# Shared scorer instance — scoring logic lives in one place only
_scorer = MetricsScorer()


@dataclass
class ReplayResult:
    log_id: str
    baseline_score: float
    current_score: float
    delta: float
    regressed: bool
    details: dict


class ReplayRegressionRunner:
    """
    Compare current AV stack performance against a stored baseline
    using replay logs.

    Regression is flagged when score drops more than `tolerance` points.
    Scoring is delegated to MetricsScorer — no duplicated logic.
    """

    def __init__(self, baseline_path: Path, tolerance: float = 0.05) -> None:
        self._baseline_path = baseline_path
        self._tolerance = tolerance
        self._baseline: dict[str, float] = self._load_baseline()

    def run(self, log_paths: list[Path]) -> list[ReplayResult]:
        """
        Run replay regression for a list of drive logs.

        Args:
            log_paths: Paths to recorded drive log files.

        Returns:
            List of ReplayResult with regression flags.
        """
        results = []
        for log_path in log_paths:
            log_id = log_path.stem
            logger.info("Running replay: %s", log_id)

            metrics = self._run_replay(log_path)
            current_score = self._score_metrics(log_id, metrics)

            baseline_score = self._baseline.get(log_id, current_score)
            delta = current_score - baseline_score
            regressed = delta < -self._tolerance

            if regressed:
                logger.warning(
                    "REGRESSION %s: %.3f → %.3f (Δ%.3f)",
                    log_id, baseline_score, current_score, delta,
                )

            results.append(ReplayResult(
                log_id=log_id,
                baseline_score=baseline_score,
                current_score=current_score,
                delta=delta,
                regressed=regressed,
                details=metrics,
            ))

        return results

    def update_baseline(self, results: list[ReplayResult]) -> None:
        """Promote current scores to baseline (after human review)."""
        for r in results:
            self._baseline[r.log_id] = r.current_score
        self._baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self._baseline_path.write_text(json.dumps(self._baseline, indent=2))
        logger.info("Baseline updated at %s", self._baseline_path)

    # --- Internal helpers ---

    def _load_baseline(self) -> dict[str, float]:
        if not self._baseline_path.exists():
            return {}
        try:
            return json.loads(self._baseline_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load baseline from %s: %s — starting fresh", self._baseline_path, exc)
            return {}

    def _run_replay(self, log_path: Path) -> dict:
        """Execute replay in sim and return raw metrics. Stub — replace with sim SDK."""
        import random
        rng = random.Random(log_path.stem)
        return {
            "collision_count": 0,
            "min_ttc_s": rng.uniform(2.0, 8.0),
            "avg_jerk_mps3": rng.uniform(0.2, 2.0),
            "lane_deviation_m": rng.uniform(0.0, 0.4),
            "completion_rate": 1.0,
            "speed_limit_violations": 0,
        }

    def _score_metrics(self, log_id: str, metrics: dict) -> float:
        """Score via MetricsScorer — single source of truth for scoring logic."""
        result = RunResult(
            scenario_id=log_id,
            status=RunStatus.PASSED,
            duration_s=0.0,
            metrics=metrics,
        )
        report = _scorer.score_suite([result])
        return round(report.scores[0].weighted_score, 4) if report.scores else 0.0
