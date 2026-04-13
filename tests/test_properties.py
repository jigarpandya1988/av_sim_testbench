"""
Property-based tests using Hypothesis.

These tests verify invariants that must hold for ALL valid inputs,
not just the specific cases we thought to write manually.
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from cpp.metrics_bridge import compute_comfort_score, compute_lane_deviation_rms
from metrics.scoring import MetricsScorer
from runner.engine import RunResult, RunStatus

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_metrics = st.fixed_dictionaries(
    {
        "collision_count": st.integers(min_value=0, max_value=5),
        "min_ttc_s": st.floats(min_value=0.0, max_value=20.0, allow_nan=False),
        "avg_jerk_mps3": st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
        "lane_deviation_m": st.floats(min_value=0.0, max_value=2.0, allow_nan=False),
        "completion_rate": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        "speed_limit_violations": st.integers(min_value=0, max_value=5),
    }
)

run_result_strategy = st.builds(
    RunResult,
    scenario_id=st.text(
        min_size=1,
        max_size=32,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
    ),
    status=st.just(RunStatus.PASSED),
    duration_s=st.floats(min_value=0.01, max_value=300.0, allow_nan=False),
    metrics=valid_metrics,
    error=st.none(),
    retries=st.integers(min_value=0, max_value=3),
)


# ---------------------------------------------------------------------------
# MetricsScorer invariants
# ---------------------------------------------------------------------------


class TestScorerProperties:
    @given(results=st.lists(run_result_strategy, min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_pass_rate_always_in_0_1(self, results):
        scorer = MetricsScorer()
        report = scorer.score_suite(results)
        assert 0.0 <= report.pass_rate <= 1.0

    @given(results=st.lists(run_result_strategy, min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_weighted_score_always_in_0_1(self, results):
        scorer = MetricsScorer()
        report = scorer.score_suite(results)
        for s in report.scores:
            assert 0.0 <= s.weighted_score <= 1.0, (
                f"Score {s.weighted_score} out of range for {s.scenario_id}"
            )

    @given(results=st.lists(run_result_strategy, min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_total_equals_sum_of_parts(self, results):
        scorer = MetricsScorer()
        report = scorer.score_suite(results)
        assert report.total == report.passed + report.failed + report.timeout + report.error

    @given(metrics=valid_metrics)
    @settings(max_examples=300)
    def test_collision_always_fails(self, metrics):
        """Any scenario with collision_count > 0 must fail."""
        assume(metrics["collision_count"] > 0)
        result = RunResult("s1", RunStatus.PASSED, 1.0, metrics)
        scorer = MetricsScorer()
        report = scorer.score_suite([result])
        assert report.failed == 1
        assert report.passed == 0

    @given(
        jerk=st.floats(min_value=0.0, max_value=2.9, allow_nan=False),
        ttc=st.floats(min_value=1.5, max_value=20.0, allow_nan=False),
        dev=st.floats(min_value=0.0, max_value=0.49, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_zero_collision_and_good_ttc_can_pass(self, jerk, ttc, dev):
        """A scenario with no collision and metrics within thresholds must pass."""
        metrics = {
            "collision_count": 0,
            "min_ttc_s": ttc,
            "avg_jerk_mps3": jerk,
            "lane_deviation_m": dev,
            "completion_rate": 1.0,
            "speed_limit_violations": 0,
        }
        result = RunResult("s2", RunStatus.PASSED, 1.0, metrics)
        scorer = MetricsScorer()
        report = scorer.score_suite([result])
        assert report.passed == 1


# ---------------------------------------------------------------------------
# C++ bridge / Python fallback invariants
# ---------------------------------------------------------------------------


class TestMetricsBridgeProperties:
    @given(
        jerk=st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
        dev=st.floats(min_value=0.0, max_value=2.0, allow_nan=False),
    )
    @settings(max_examples=300)
    def test_comfort_score_in_range(self, jerk, dev):
        score = compute_comfort_score(jerk, dev)
        assert 0.0 <= score <= 1.0

    @given(
        jerk=st.floats(min_value=0.0, max_value=4.9, allow_nan=False),
        dev=st.floats(min_value=0.0, max_value=0.9, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_low_jerk_and_dev_gives_positive_score(self, jerk, dev):
        score = compute_comfort_score(jerk, dev)
        assert score > 0.0

    @given(errors=st.lists(st.floats(min_value=-5.0, max_value=5.0, allow_nan=False), min_size=1))
    @settings(max_examples=200)
    def test_lane_deviation_rms_non_negative(self, errors):
        rms = compute_lane_deviation_rms(errors)
        assert rms >= 0.0

    @given(errors=st.lists(st.floats(min_value=-5.0, max_value=5.0, allow_nan=False), min_size=1))
    @settings(max_examples=200)
    def test_lane_deviation_rms_bounded_by_max_abs(self, errors):
        rms = compute_lane_deviation_rms(errors)
        max_abs = max(abs(e) for e in errors)
        assert rms <= max_abs + 1e-9


# ---------------------------------------------------------------------------
# Scenario generator invariants
# ---------------------------------------------------------------------------


class TestScenarioGeneratorProperties:
    @given(
        n=st.integers(min_value=1, max_value=200),
        seed=st.integers(min_value=0, max_value=2**31),
    )
    @settings(max_examples=100)
    def test_fuzz_always_yields_n_scenarios(self, n, seed):
        from scenarios.generator import ScenarioGenerator

        gen = ScenarioGenerator()
        scenarios = list(gen.random_fuzz(n=n, seed=seed))
        assert len(scenarios) == n

    @given(seed=st.integers(min_value=0, max_value=2**31))
    @settings(max_examples=50)
    def test_fuzz_deterministic_for_same_seed(self, seed):
        from scenarios.generator import ScenarioGenerator

        gen = ScenarioGenerator()
        a = list(gen.random_fuzz(n=20, seed=seed))
        b = list(gen.random_fuzz(n=20, seed=seed))
        assert [s.scenario_id for s in a] == [s.scenario_id for s in b]
