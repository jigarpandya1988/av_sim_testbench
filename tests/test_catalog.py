"""Tests for the scenario catalog / SQLite persistence layer."""

import pytest

from catalog.store import RunRecord, ScenarioCatalog
from scenarios.generator import ScenarioGenerator


@pytest.fixture
def tmp_catalog(tmp_path):
    return ScenarioCatalog(db_path=tmp_path / "test.db")


@pytest.fixture
def scenarios():
    gen = ScenarioGenerator()
    return gen.pedestrian_crossing_suite()[:5]


class TestScenarioCatalog:
    def test_register_and_query(self, tmp_catalog, scenarios):
        tmp_catalog.register_scenarios_bulk(scenarios)
        rates = tmp_catalog.pass_rate_by_category()
        # No runs yet — should be empty
        assert rates == {}

    def test_record_run_and_pass_rate(self, tmp_catalog, scenarios):
        tmp_catalog.register_scenarios_bulk(scenarios)
        for s in scenarios:
            tmp_catalog.record_run(
                RunRecord(
                    scenario_id=s.scenario_id,
                    status="passed",
                    duration_s=1.0,
                    metrics={"collision_count": 0, "min_ttc_s": 4.0},
                    violations=[],
                    weighted_score=0.9,
                )
            )
        rates = tmp_catalog.pass_rate_by_category()
        assert "pedestrian" in rates
        assert rates["pedestrian"] == 1.0

    def test_mixed_pass_fail_rate(self, tmp_catalog, scenarios):
        tmp_catalog.register_scenarios_bulk(scenarios)
        for i, s in enumerate(scenarios):
            tmp_catalog.record_run(
                RunRecord(
                    scenario_id=s.scenario_id,
                    status="passed" if i % 2 == 0 else "failed",
                    duration_s=1.0,
                    metrics={},
                    violations=[],
                    weighted_score=0.5,
                )
            )
        rates = tmp_catalog.pass_rate_by_category()
        assert 0.0 < rates.get("pedestrian", 0) < 1.0

    def test_metric_trend(self, tmp_catalog, scenarios):
        s = scenarios[0]
        tmp_catalog.register_scenario(s)
        for i in range(5):
            tmp_catalog.record_run(
                RunRecord(
                    scenario_id=s.scenario_id,
                    status="passed",
                    duration_s=1.0,
                    metrics={"min_ttc_s": float(i + 1)},
                    violations=[],
                    weighted_score=0.8,
                )
            )
        trend = tmp_catalog.metric_trend(s.scenario_id, "min_ttc_s")
        assert len(trend) == 5
        assert trend == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_flaky_scenarios_detection(self, tmp_catalog, scenarios):
        s = scenarios[0]
        tmp_catalog.register_scenario(s)
        # 3 pass, 3 fail = 50% pass rate → flaky
        for i in range(6):
            tmp_catalog.record_run(
                RunRecord(
                    scenario_id=s.scenario_id,
                    status="passed" if i < 3 else "failed",
                    duration_s=1.0,
                    metrics={},
                    violations=[],
                    weighted_score=0.5,
                )
            )
        flaky = tmp_catalog.flaky_scenarios(min_runs=5, max_pass_rate=0.8)
        assert any(f["scenario_id"] == s.scenario_id for f in flaky)

    def test_bulk_record_runs(self, tmp_catalog, scenarios):
        tmp_catalog.register_scenarios_bulk(scenarios)
        records = [
            RunRecord(
                scenario_id=s.scenario_id,
                status="passed",
                duration_s=0.5,
                metrics={},
                violations=[],
                weighted_score=1.0,
            )
            for s in scenarios
        ]
        tmp_catalog.record_runs_bulk(records)
        recent = tmp_catalog.recent_runs(limit=10)
        assert len(recent) == len(scenarios)
