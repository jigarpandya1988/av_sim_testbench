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

logger = logging.getLogger(__name__)


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
    """

    def __init__(self, baseline_path: Path, tolerance: float = 0.05):
        self._baseline_path = baseline_path
        self._tolerance = tolerance
        self._baseline: dict[str, float] = self._load_baseline()

    def run(self, log_paths: list[Path], scorer) -> list[ReplayResult]:
        """
        Run replay regression for a list of drive logs.

        Args:
            log_paths: Paths to recorded drive log files.
            scorer: MetricsScorer instance for scoring results.

        Returns:
            List of ReplayResult with regression flags.
        """
        results = []
        for log_path in log_paths:
            log_id = log_path.stem
            logger.info("Running replay: %s", log_id)

            # Convert log → scenario → run → score
            scenario = self._log_to_scenario(log_path)
            metrics = self._run_replay(scenario)
            current_score = self._compute_score(metrics)

            baseline_score = self._baseline.get(log_id, current_score)
            delta = current_score - baseline_score
            regressed = delta < -self._tolerance

            if regressed:
                logger.warning(
                    "REGRESSION detected in %s: %.3f → %.3f (Δ%.3f)",
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
        if self._baseline_path.exists():
            return json.loads(self._baseline_path.read_text())
        return {}

    def _log_to_scenario(self, log_path: Path) -> dict:
        """Parse a drive log into a scenario descriptor. Stub implementation."""
        return {"log_id": log_path.stem, "path": str(log_path)}

    def _run_replay(self, scenario: dict) -> dict:
        """Execute replay in sim and return raw metrics. Stub — replace with sim SDK."""
        import random
        rng = random.Random(scenario["log_id"])
        return {
            "collision_count": 0,
            "min_ttc_s": rng.uniform(2.0, 8.0),
            "avg_jerk_mps3": rng.uniform(0.2, 2.0),
            "lane_deviation_m": rng.uniform(0.0, 0.4),
            "completion_rate": 1.0,
            "speed_limit_violations": 0,
        }

    def _compute_score(self, metrics: dict) -> float:
        """Simple weighted score — mirrors MetricsScorer logic."""
        weights = {"min_ttc_s": 0.3, "avg_jerk_mps3": 0.2, "lane_deviation_m": 0.2, "completion_rate": 0.3}
        score = (
            weights["min_ttc_s"] * min(metrics.get("min_ttc_s", 0) / 5.0, 1.0)
            + weights["avg_jerk_mps3"] * max(0.0, 1.0 - metrics.get("avg_jerk_mps3", 0) / 5.0)
            + weights["lane_deviation_m"] * max(0.0, 1.0 - metrics.get("lane_deviation_m", 0))
            + weights["completion_rate"] * metrics.get("completion_rate", 0.0)
        )
        if metrics.get("collision_count", 0) > 0:
            score *= 0.0  # hard zero on collision
        return round(score, 4)
