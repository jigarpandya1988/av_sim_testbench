"""Tests for ML regression detection."""

from ml.regression_detector import MLRegressionDetector

BASE_METRICS = [
    {
        "collision_rate": 0.02,
        "min_ttc_s": 4.0,
        "avg_jerk_mps3": 1.0,
        "lane_deviation_m": 0.2,
        "completion_rate": 1.0,
    }
    for _ in range(30)
]


class TestMLRegressionDetector:
    def setup_method(self):
        self.detector = MLRegressionDetector()

    def test_identical_no_regression(self):
        comparisons = self.detector.compare(BASE_METRICS, BASE_METRICS)
        assert all(not c.regressed for c in comparisons)

    def test_collision_rate_regression_detected(self):
        bad = [{**m, "collision_rate": 0.15} for m in BASE_METRICS]
        comparisons = self.detector.compare(BASE_METRICS, bad)
        collision_cmp = next(c for c in comparisons if c.metric == "collision_rate")
        assert collision_cmp.regressed

    def test_improved_model_no_regression(self):
        better = [{**m, "min_ttc_s": 6.0, "avg_jerk_mps3": 0.5} for m in BASE_METRICS]
        comparisons = self.detector.compare(BASE_METRICS, better)
        assert all(not c.regressed for c in comparisons)

    def test_delta_pct_sign(self):
        worse = [{**m, "avg_jerk_mps3": 2.0} for m in BASE_METRICS]
        comparisons = self.detector.compare(BASE_METRICS, worse)
        jerk_cmp = next(c for c in comparisons if c.metric == "avg_jerk_mps3")
        assert jerk_cmp.delta_pct > 0  # candidate is worse (higher jerk)
