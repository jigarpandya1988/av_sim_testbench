"""Tests for scenario generation."""

from scenarios.generator import ScenarioGenerator
from scenarios.schema import ScenarioCategory


class TestScenarioGenerator:
    def setup_method(self):
        self.gen = ScenarioGenerator()

    def test_cut_in_suite_not_empty(self):
        scenarios = self.gen.highway_cut_in_suite()
        assert len(scenarios) > 0

    def test_cut_in_all_correct_category(self):
        for s in self.gen.highway_cut_in_suite():
            assert s.category == ScenarioCategory.CUT_IN

    def test_pedestrian_suite_actor_count(self):
        scenarios = self.gen.pedestrian_crossing_suite()
        for s in scenarios:
            assert len(s.actors) >= 1
            assert all(a.actor_type == "pedestrian" for a in s.actors)

    def test_full_suite_covers_multiple_categories(self):
        scenarios = self.gen.full_suite()
        categories = {s.category for s in scenarios}
        assert len(categories) >= 3

    def test_fuzz_generates_n_scenarios(self):
        scenarios = list(self.gen.random_fuzz(n=50, seed=42))
        assert len(scenarios) == 50

    def test_fuzz_is_deterministic(self):
        a = list(self.gen.random_fuzz(n=10, seed=99))
        b = list(self.gen.random_fuzz(n=10, seed=99))
        assert [s.scenario_id for s in a] == [s.scenario_id for s in b]

    def test_scenario_ids_are_unique(self):
        scenarios = self.gen.full_suite()
        ids = [s.scenario_id for s in scenarios]
        assert len(ids) == len(set(ids))
