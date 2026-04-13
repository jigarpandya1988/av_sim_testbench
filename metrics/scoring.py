"""
AV performance metrics scoring and suite-level reporting.

Computes per-scenario scores and aggregates into a SuiteReport
with pass/fail thresholds aligned to ISO 21448 (SOTIF) guidance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runner.engine import RunResult


# ---------------------------------------------------------------------------
# Thresholds (tune per program requirements)
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "collision_count": 0,  # zero tolerance
    "min_ttc_s": 1.5,  # must stay above 1.5 s
    "avg_jerk_mps3": 3.0,  # comfort limit
    "lane_deviation_m": 0.5,  # max lateral error
    "completion_rate": 1.0,  # must complete scenario
    "speed_limit_violations": 0,
}


@dataclass
class ScenarioScore:
    scenario_id: str
    passed: bool
    violations: list[str]
    raw_metrics: dict
    weighted_score: float  # 0.0 (worst) – 1.0 (perfect)


@dataclass
class SuiteReport:
    total: int
    passed: int
    failed: int
    timeout: int
    error: int
    pass_rate: float
    scores: list[ScenarioScore] = field(default_factory=list)
    category_breakdown: dict[str, dict] = field(default_factory=dict)

    def to_json(self, path: Path | None = None) -> str:
        data = {
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "timeout": self.timeout,
                "error": self.error,
                "pass_rate": round(self.pass_rate, 4),
            },
            "category_breakdown": self.category_breakdown,
            "scenarios": [
                {
                    "id": s.scenario_id,
                    "passed": s.passed,
                    "score": round(s.weighted_score, 4),
                    "violations": s.violations,
                    "metrics": s.raw_metrics,
                }
                for s in self.scores
            ],
        }
        out = json.dumps(data, indent=2)
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(out, encoding="utf-8")
            except OSError as exc:
                import logging

                logging.getLogger(__name__).error("Failed to write report to %s: %s", path, exc)
                raise
        return out


class MetricsScorer:
    """Score simulation results and produce a SuiteReport."""

    # Metric weights for composite score (must sum to 1.0)
    _WEIGHTS = {
        "collision_count": 0.40,
        "min_ttc_s": 0.20,
        "avg_jerk_mps3": 0.15,
        "lane_deviation_m": 0.15,
        "completion_rate": 0.10,
    }

    def score_suite(
        self,
        results: list[RunResult],
        scenarios_by_id: dict[str, Scenario] | None = None,  # noqa: F821
    ) -> SuiteReport:
        from runner.engine import RunStatus

        scores = []
        category_stats: dict[str, dict] = {}

        passed = failed = timeout = error = 0

        for result in results:
            if result.status == RunStatus.TIMEOUT:
                timeout += 1
                continue
            if result.status == RunStatus.ERROR:
                error += 1
                continue

            score = self._score_result(result)
            scores.append(score)

            if score.passed:
                passed += 1
            else:
                failed += 1

            # Category breakdown
            cat = "unknown"
            if scenarios_by_id and result.scenario_id in scenarios_by_id:
                cat = scenarios_by_id[result.scenario_id].category.value
            stats = category_stats.setdefault(cat, {"total": 0, "passed": 0})
            stats["total"] += 1
            if score.passed:
                stats["passed"] += 1

        total = passed + failed + timeout + error
        pass_rate = passed / max(passed + failed, 1)

        # Add pass_rate to each category
        for stats in category_stats.values():
            stats["pass_rate"] = round(stats["passed"] / max(stats["total"], 1), 4)

        return SuiteReport(
            total=total,
            passed=passed,
            failed=failed,
            timeout=timeout,
            error=error,
            pass_rate=pass_rate,
            scores=scores,
            category_breakdown=category_stats,
        )

    def _score_result(self, result: RunResult) -> ScenarioScore:
        m = result.metrics
        violations = []

        # Hard-fail checks
        if m.get("collision_count", 0) > THRESHOLDS["collision_count"]:
            violations.append(f"collision_count={m['collision_count']}")
        if m.get("min_ttc_s", 99) < THRESHOLDS["min_ttc_s"]:
            violations.append(f"min_ttc_s={m['min_ttc_s']:.2f} < {THRESHOLDS['min_ttc_s']}")
        if m.get("completion_rate", 1.0) < THRESHOLDS["completion_rate"]:
            violations.append("scenario_incomplete")
        if m.get("speed_limit_violations", 0) > THRESHOLDS["speed_limit_violations"]:
            violations.append(f"speed_limit_violations={m['speed_limit_violations']}")

        # Soft metrics (contribute to score but don't hard-fail)
        component_scores = {
            "collision_count": 1.0 if m.get("collision_count", 0) == 0 else 0.0,
            "min_ttc_s": min(m.get("min_ttc_s", 0) / 5.0, 1.0),
            "avg_jerk_mps3": max(0.0, 1.0 - m.get("avg_jerk_mps3", 0) / 5.0),
            "lane_deviation_m": max(0.0, 1.0 - m.get("lane_deviation_m", 0) / 1.0),
            "completion_rate": m.get("completion_rate", 0.0),
        }
        weighted = sum(
            self._WEIGHTS[k] * v for k, v in component_scores.items() if k in self._WEIGHTS
        )

        return ScenarioScore(
            scenario_id=result.scenario_id,
            passed=len(violations) == 0,
            violations=violations,
            raw_metrics=m,
            weighted_score=weighted,
        )
