"""
Tests for legacy ADAS vehicle profiles, degradation model, and scenario generator.
"""
from __future__ import annotations

import asyncio
import pytest

from adapters.legacy_adas import LegacyADASAdapter, VEHICLE_PROFILES, _compute_degradation
from scenarios.generator import ScenarioGenerator
from scenarios.schema import ScenarioCategory, SensorSpec, VehicleProfile, WeatherCondition
from runner.engine import SimulationRunner
from metrics.scoring import MetricsScorer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gen1_profile():
    return VEHICLE_PROFILES["2015_honda_civic_lanewatch"]

@pytest.fixture
def gen2_profile():
    return VEHICLE_PROFILES["2018_volvo_xc60_pilot_assist"]

@pytest.fixture
def av_profile():
    return VEHICLE_PROFILES["2023_av_platform"]

@pytest.fixture
def generator():
    return ScenarioGenerator()


# ---------------------------------------------------------------------------
# VehicleProfile & SensorSpec
# ---------------------------------------------------------------------------

class TestVehicleProfiles:

    def test_all_profiles_have_required_fields(self):
        for key, profile in VEHICLE_PROFILES.items():
            assert profile.name, f"{key} missing name"
            assert profile.model_year > 0
            assert profile.adas_generation in ("gen1", "gen2", "av")
            assert profile.sensors is not None

    def test_gen1_has_worse_specs_than_gen2(self, gen1_profile, gen2_profile):
        assert gen1_profile.sensors.aeb_reaction_time_s > gen2_profile.sensors.aeb_reaction_time_s
        assert gen1_profile.sensors.lka_correction_rate < gen2_profile.sensors.lka_correction_rate

    def test_av_profile_has_best_specs(self, av_profile, gen2_profile):
        assert av_profile.sensors.radar_range_m > gen2_profile.sensors.radar_range_m
        assert av_profile.sensors.aeb_reaction_time_s < gen2_profile.sensors.aeb_reaction_time_s
        assert av_profile.sensors.has_lidar is True


# ---------------------------------------------------------------------------
# Degradation model
# ---------------------------------------------------------------------------

class TestDegradationModel:

    def test_no_degradation_for_perfect_sensors(self):
        perfect = SensorSpec(
            radar_range_m=200.0,
            camera_latency_ms=20.0,
            aeb_reaction_time_s=0.15,
            lka_correction_rate=1.0,
        )
        d = _compute_degradation(perfect, 0.0, 0.0)
        assert d.ttc_penalty < 0.05
        assert abs(d.jerk_multiplier - 1.0) < 0.01
        assert abs(d.lane_dev_multiplier - 1.0) < 0.01

    def test_camera_only_worse_in_rain(self, gen1_profile):
        d_dry = _compute_degradation(gen1_profile.sensors, 0.0, 0.0)
        d_rain = _compute_degradation(gen1_profile.sensors, 0.8, 0.0)
        assert d_rain.ttc_penalty > d_dry.ttc_penalty
        assert d_rain.collision_prob_add > d_dry.collision_prob_add

    def test_gen2_less_degraded_than_gen1_in_fog(self, gen1_profile, gen2_profile):
        d1 = _compute_degradation(gen1_profile.sensors, 0.0, 0.7)
        d2 = _compute_degradation(gen2_profile.sensors, 0.0, 0.7)
        assert d1.ttc_penalty > d2.ttc_penalty

    def test_degradation_factors_bounded(self, gen1_profile):
        d = _compute_degradation(gen1_profile.sensors, 1.0, 1.0)
        assert 0.0 <= d.ttc_penalty <= 1.0
        assert d.jerk_multiplier >= 1.0
        assert d.lane_dev_multiplier >= 1.0
        assert 0.0 <= d.collision_prob_add <= 0.4


# ---------------------------------------------------------------------------
# LegacyADASAdapter
# ---------------------------------------------------------------------------

class TestLegacyADASAdapter:

    def test_av_profile_returns_unmodified_metrics(self, av_profile):
        """AV generation should pass through without degradation."""
        adapter = LegacyADASAdapter(profile=av_profile)
        gen = ScenarioGenerator()
        scenario = gen.highway_cut_in_suite()[0]
        scenario.vehicle_profile = av_profile

        # Run multiple times — should be consistent (no random degradation)
        results = [adapter(scenario) for _ in range(5)]
        ttcs = [r["min_ttc_s"] for r in results]
        assert max(ttcs) - min(ttcs) < 0.01  # deterministic for AV

    def test_gen1_produces_higher_degradation_factors_than_gen2(self, gen1_profile, gen2_profile):
        """Verify degradation model: gen1 has worse factors than gen2 (deterministic)."""
        d1 = _compute_degradation(gen1_profile.sensors, 0.0, 0.0)
        d2 = _compute_degradation(gen2_profile.sensors, 0.0, 0.0)
        assert d1.ttc_penalty >= d2.ttc_penalty
        assert d1.jerk_multiplier >= d2.jerk_multiplier
        assert d1.lane_dev_multiplier >= d2.lane_dev_multiplier

    def test_adapter_adds_profile_metadata(self, gen2_profile):
        gen = ScenarioGenerator()
        scenario = gen.highway_cut_in_suite()[0]
        scenario.vehicle_profile = gen2_profile

        adapter = LegacyADASAdapter(profile=gen2_profile)
        metrics = adapter(scenario)

        assert "vehicle_profile" in metrics
        assert "adas_generation" in metrics
        assert metrics["adas_generation"] == "gen2"

    def test_scenario_profile_overrides_adapter_profile(self, gen1_profile, gen2_profile):
        """Scenario-level profile takes precedence over adapter-level profile."""
        gen = ScenarioGenerator()
        scenario = gen.highway_cut_in_suite()[0]
        scenario.vehicle_profile = gen2_profile  # scenario says gen2

        adapter = LegacyADASAdapter(profile=gen1_profile)  # adapter says gen1
        metrics = adapter(scenario)

        assert metrics["adas_generation"] == "gen2"  # scenario wins


# ---------------------------------------------------------------------------
# Legacy scenario generator
# ---------------------------------------------------------------------------

class TestLegacyScenarioGenerator:

    def test_legacy_suite_generates_all_three_categories(self, generator, gen2_profile):
        scenarios = generator.legacy_adas_suite(gen2_profile)
        categories = {s.category for s in scenarios}
        assert ScenarioCategory.LEGACY_AEB in categories
        assert ScenarioCategory.LEGACY_LKA in categories
        assert ScenarioCategory.LEGACY_ACC in categories

    def test_all_scenarios_have_vehicle_profile(self, generator, gen1_profile):
        for s in generator.legacy_adas_suite(gen1_profile):
            assert s.vehicle_profile is not None
            assert s.vehicle_profile.name == gen1_profile.name

    def test_legacy_suite_ids_are_unique(self, generator, gen2_profile):
        scenarios = generator.legacy_adas_suite(gen2_profile)
        ids = [s.scenario_id for s in scenarios]
        assert len(ids) == len(set(ids))

    def test_legacy_suite_ids_are_deterministic(self, generator, gen2_profile):
        a = [s.scenario_id for s in generator.legacy_adas_suite(gen2_profile)]
        b = [s.scenario_id for s in generator.legacy_adas_suite(gen2_profile)]
        assert a == b

    def test_aeb_scenarios_have_actors(self, generator, gen1_profile):
        scenarios = generator._legacy_aeb_suite(gen1_profile)
        for s in scenarios:
            assert len(s.actors) == 1
            assert s.actors[0].actor_type == "vehicle"

    def test_legacy_tags_include_generation(self, generator, gen2_profile):
        for s in generator.legacy_adas_suite(gen2_profile):
            assert "legacy" in s.tags
            assert gen2_profile.adas_generation in s.tags


# ---------------------------------------------------------------------------
# End-to-end: legacy suite through runner + scorer
# ---------------------------------------------------------------------------

class TestLegacyEndToEnd:

    def _run_profile(self, profile):
        gen = ScenarioGenerator()
        scorer = MetricsScorer()
        scenarios = gen.legacy_adas_suite(profile)
        adapter = LegacyADASAdapter(profile=profile)
        runner = SimulationRunner(sim_adapter=adapter, workers=4)
        results = asyncio.run(runner.run_suite(scenarios))
        return scorer.score_suite(results, {s.scenario_id: s for s in scenarios})

    def test_all_profiles_produce_valid_reports(self):
        """Smoke test: every profile runs end-to-end without error."""
        for key, profile in VEHICLE_PROFILES.items():
            report = self._run_profile(profile)
            assert report.total > 0, f"{key} produced no results"
            assert 0.0 <= report.pass_rate <= 1.0

    def test_av_profile_has_no_degradation_metadata(self):
        """AV profile scenarios should not have vehicle_profile key in metrics."""
        av = VEHICLE_PROFILES["2023_av_platform"]
        gen = ScenarioGenerator()
        scenarios = gen.legacy_adas_suite(av)
        adapter = LegacyADASAdapter(profile=av)
        # AV adapter returns metrics unchanged — no vehicle_profile key added
        metrics = adapter(scenarios[0])
        assert "vehicle_profile" not in metrics  # AV path skips degradation

    def test_gen1_degradation_factors_worse_than_gen2(self):
        """Degradation model is deterministic — gen1 always worse than gen2."""
        gen1 = VEHICLE_PROFILES["2015_honda_civic_lanewatch"]
        gen2 = VEHICLE_PROFILES["2018_volvo_xc60_pilot_assist"]
        d1 = _compute_degradation(gen1.sensors, 0.0, 0.0)
        d2 = _compute_degradation(gen2.sensors, 0.0, 0.0)
        assert d1.ttc_penalty > d2.ttc_penalty
        assert d1.collision_prob_add >= d2.collision_prob_add
