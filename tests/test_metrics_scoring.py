"""Tests for metrics scoring and suite reporting."""
import pytest
from runner.engine import RunResult, RunStatus
from metrics.scoring import MetricsScorer, THRESHOLDS


def _make_result(scenario_id: str, metrics: dict, status: RunStatus = RunStatus.PASSED) -> RunResult:
    return RunResult(scenario_id=scenario_id, status=status, duration_s=1.0, metrics=metrics)


CLEAN_METRICS = {
    "collision_count": 0,
    "min_ttc_s": 4.0,
    "avg_jerk_mps3": 1.0,
    "lane_deviation_m": 0.2,
    "completion_rate": 1.0,
    "speed_limit_violations": 0,
}

COLLISION_METRICS = {**CLEAN_METRICS, "collision_count": 1}
LOW_TTC_METRICS = {**CLEAN_METRICS, "min_ttc_s": 0.5}


class TestMetricsScorer:
    def setup_method(self):
        self.scorer = MetricsScorer()

    def test_clean_run_passes(self):
        result = _make_result("s1", CLEAN_METRICS)
        report = self.scorer.score_suite([result])
        assert report.passed == 1
        assert report.failed == 0

    def test_collision_fails(self):
        result = _make_result("s2", COLLISION_METRICS)
        report = self.scorer.score_suite([result])
        assert report.failed == 1
        assert any("collision" in v for v in report.scores[0].violations)

    def test_low_ttc_fails(self):
        result = _make_result("s3", LOW_TTC_METRICS)
        report = self.scorer.score_suite([result])
        assert report.failed == 1

    def test_timeout_counted_separately(self):
        result = _make_result("s4", {}, status=RunStatus.TIMEOUT)
        report = self.scorer.score_suite([result])
        assert report.timeout == 1
        assert report.passed == 0

    def test_pass_rate_calculation(self):
        results = [
            _make_result("s5", CLEAN_METRICS),
            _make_result("s6", CLEAN_METRICS),
            _make_result("s7", COLLISION_METRICS),
        ]
        report = self.scorer.score_suite(results)
        assert abs(report.pass_rate - 2 / 3) < 0.001

    def test_weighted_score_range(self):
        result = _make_result("s8", CLEAN_METRICS)
        report = self.scorer.score_suite([result])
        score = report.scores[0].weighted_score
        assert 0.0 <= score <= 1.0

    def test_json_report_serializable(self):
        import json
        result = _make_result("s9", CLEAN_METRICS)
        report = self.scorer.score_suite([result])
        raw = report.to_json()
        parsed = json.loads(raw)
        assert "summary" in parsed
        assert parsed["summary"]["total"] == 1
