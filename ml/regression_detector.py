"""
ML model regression detection for AV perception/planning models.

Compares metric distributions between model versions using
statistical tests to flag regressions with confidence bounds.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelComparison:
    metric: str
    baseline_mean: float
    candidate_mean: float
    delta_pct: float
    p_value: float
    regressed: bool
    note: str


class MLRegressionDetector:
    """
    Detect regressions in AV model performance across simulation runs.

    Uses Welch's t-test for statistical significance and configurable
    delta thresholds per metric.
    """

    # Max allowed degradation per metric (negative = lower is worse)
    _REGRESSION_THRESHOLDS = {
        "collision_rate": 0.01,       # absolute increase
        "min_ttc_s": -0.3,            # seconds drop
        "avg_jerk_mps3": 0.5,         # m/s³ increase
        "lane_deviation_m": 0.1,      # meter increase
        "completion_rate": -0.02,     # fraction drop
    }

    def compare(
        self,
        baseline_metrics: list[dict],
        candidate_metrics: list[dict],
        alpha: float = 0.05,
    ) -> list[ModelComparison]:
        """
        Compare two sets of per-scenario metric dicts.

        Args:
            baseline_metrics: Metrics from baseline model runs.
            candidate_metrics: Metrics from candidate model runs.
            alpha: Significance level for t-test.

        Returns:
            List of ModelComparison results, one per metric.
        """
        comparisons = []
        all_keys = set(baseline_metrics[0].keys()) if baseline_metrics else set()

        for key in all_keys:
            base_vals = [m[key] for m in baseline_metrics if key in m]
            cand_vals = [m[key] for m in candidate_metrics if key in m]

            if not base_vals or not cand_vals:
                continue

            base_mean = _mean(base_vals)
            cand_mean = _mean(cand_vals)
            delta = cand_mean - base_mean
            delta_pct = (delta / base_mean * 100) if base_mean != 0 else 0.0

            p_value = _welch_t_test(base_vals, cand_vals)
            threshold = self._REGRESSION_THRESHOLDS.get(key)

            regressed = False
            note = "ok"
            if threshold is not None and p_value < alpha:
                if threshold >= 0 and delta > threshold:
                    regressed = True
                    note = f"increased by {delta:.4f} (threshold +{threshold})"
                elif threshold < 0 and delta < threshold:
                    regressed = True
                    note = f"dropped by {abs(delta):.4f} (threshold {threshold})"

            if regressed:
                logger.warning("ML REGRESSION [%s]: %s", key, note)

            comparisons.append(ModelComparison(
                metric=key,
                baseline_mean=round(base_mean, 4),
                candidate_mean=round(cand_mean, 4),
                delta_pct=round(delta_pct, 2),
                p_value=round(p_value, 4),
                regressed=regressed,
                note=note,
            ))

        return comparisons


# ---------------------------------------------------------------------------
# Stats helpers (no scipy dependency)
# ---------------------------------------------------------------------------

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals)


def _variance(vals: list[float]) -> float:
    m = _mean(vals)
    return sum((v - m) ** 2 for v in vals) / max(len(vals) - 1, 1)


def _welch_t_test(a: list[float], b: list[float]) -> float:
    """Return approximate two-tailed p-value using Welch's t-test."""
    n1, n2 = len(a), len(b)
    v1, v2 = _variance(a), _variance(b)
    if v1 == 0 and v2 == 0:
        return 1.0
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        return 1.0
    t = (_mean(a) - _mean(b)) / se
    # Approximate p-value via normal CDF for large n
    p = 2 * (1 - _norm_cdf(abs(t)))
    return max(0.0, min(1.0, p))


def _norm_cdf(x: float) -> float:
    """Approximation of standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
