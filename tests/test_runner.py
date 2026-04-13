"""Tests for the async simulation runner."""

import asyncio

import pytest

from runner.engine import RunStatus, SimulationRunner
from scenarios.generator import ScenarioGenerator


@pytest.fixture
def small_suite():
    gen = ScenarioGenerator()
    return gen.pedestrian_crossing_suite()[:3]


class TestSimulationRunner:
    def test_run_suite_returns_all_results(self, small_suite):
        runner = SimulationRunner(workers=2)
        results = asyncio.run(runner.run_suite(small_suite))
        assert len(results) == len(small_suite)

    def test_all_results_have_valid_status(self, small_suite):
        runner = SimulationRunner(workers=2)
        results = asyncio.run(runner.run_suite(small_suite))
        valid = set(RunStatus)
        for r in results:
            assert r.status in valid

    def test_timeout_handled_gracefully(self):
        from scenarios.schema import Scenario, ScenarioCategory

        def slow_adapter(s):
            import time

            time.sleep(10)
            return {}

        runner = SimulationRunner(sim_adapter=slow_adapter, timeout_s=0.1, max_retries=0)
        scenario = Scenario(
            scenario_id="timeout_test",
            category=ScenarioCategory.HIGHWAY,
            description="timeout test",
            ego_initial_speed_mps=20.0,
            map_id="highway_101",
        )
        results = asyncio.run(runner.run_suite([scenario]))
        assert results[0].status == RunStatus.TIMEOUT

    def test_error_handled_gracefully(self):
        from scenarios.schema import Scenario, ScenarioCategory

        def bad_adapter(s):
            raise RuntimeError("sim crashed")

        runner = SimulationRunner(sim_adapter=bad_adapter, max_retries=0)
        scenario = Scenario(
            scenario_id="error_test",
            category=ScenarioCategory.URBAN,
            description="error test",
            ego_initial_speed_mps=10.0,
            map_id="urban_grid_sf",
        )
        results = asyncio.run(runner.run_suite([scenario]))
        assert results[0].status == RunStatus.ERROR
        assert results[0].error is not None
