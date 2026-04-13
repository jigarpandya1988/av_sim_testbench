"""
Legacy ADAS simulation adapter.

Models the degraded perception and actuation characteristics of pre-2020
vehicles equipped with Gen1/Gen2 ADAS systems (AEB, LKA, ACC).

Architecture
------------
The adapter wraps any base sim adapter and applies a VehicleProfile's
SensorSpec to degrade the raw metrics before they reach the scorer.
This keeps the degradation logic in one place and fully composable:

    base_adapter  →  LegacyADASAdapter(profile)  →  MetricsScorer

Pre-built profiles cover the most common ADAS generations:
  - gen1 (2013–2016): camera-only, slow reaction, limited LKA authority
  - gen2 (2017–2019): radar + camera fusion, faster reaction, better LKA
  - av   (2020+):     full sensor suite, no degradation applied

Real-world sensor specs sourced from:
  - Euro NCAP AEB test protocols (2016–2019)
  - Mobileye EyeQ2/EyeQ3 datasheet latency figures
  - Continental ARS408 radar datasheet
  - Bosch iBooster reaction time specs
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from scenarios.schema import Scenario, SensorSpec, VehicleProfile


# ---------------------------------------------------------------------------
# Pre-built vehicle profiles
# ---------------------------------------------------------------------------

VEHICLE_PROFILES: dict[str, VehicleProfile] = {
    # --- Gen1: camera-only ADAS (Mobileye EyeQ2 era) ---
    "2015_honda_civic_lanewatch": VehicleProfile(
        name="2015_honda_civic_lanewatch",
        model_year=2015,
        adas_generation="gen1",
        sensors=SensorSpec(
            radar_range_m=0.0,            # no radar — camera only
            radar_range_accuracy_m=999.0,
            radar_velocity_accuracy_mps=999.0,
            camera_fov_deg=50.0,          # narrow forward camera
            camera_resolution="480p",
            camera_latency_ms=120.0,      # EyeQ2 pipeline latency
            aeb_reaction_time_s=0.6,      # slow: camera-only detection
            lka_correction_rate=0.5,      # limited steering authority
            has_lidar=False,
            has_rtk_gps=False,
        ),
        notes="Camera-only AEB. No radar. LKA is advisory only.",
    ),

    # --- Gen1: basic radar + camera (Bosch mid-range radar) ---
    "2016_subaru_eyesight": VehicleProfile(
        name="2016_subaru_eyesight",
        model_year=2016,
        adas_generation="gen1",
        sensors=SensorSpec(
            radar_range_m=100.0,
            radar_range_accuracy_m=2.0,
            radar_velocity_accuracy_mps=0.5,
            camera_fov_deg=60.0,
            camera_resolution="720p",
            camera_latency_ms=90.0,
            aeb_reaction_time_s=0.5,
            lka_correction_rate=0.6,
            has_lidar=False,
            has_rtk_gps=False,
        ),
        notes="Stereo camera fusion. Radar limited to 100m. EyeSight Gen2.",
    ),

    # --- Gen2: radar + camera fusion (Continental ARS408 era) ---
    "2018_volvo_xc60_pilot_assist": VehicleProfile(
        name="2018_volvo_xc60_pilot_assist",
        model_year=2018,
        adas_generation="gen2",
        sensors=SensorSpec(
            radar_range_m=160.0,
            radar_range_accuracy_m=0.8,
            radar_velocity_accuracy_mps=0.2,
            camera_fov_deg=100.0,
            camera_resolution="1080p",
            camera_latency_ms=60.0,
            aeb_reaction_time_s=0.35,
            lka_correction_rate=0.85,
            has_lidar=False,
            has_rtk_gps=False,
        ),
        notes="Pilot Assist II. Radar+camera fusion. Strong LKA authority.",
    ),

    "2019_tesla_model3_autopilot": VehicleProfile(
        name="2019_tesla_model3_autopilot",
        model_year=2019,
        adas_generation="gen2",
        sensors=SensorSpec(
            radar_range_m=160.0,
            radar_range_accuracy_m=0.5,
            radar_velocity_accuracy_mps=0.15,
            camera_fov_deg=120.0,
            camera_resolution="1080p",
            camera_latency_ms=45.0,       # HW2.5 neural net pipeline
            aeb_reaction_time_s=0.28,
            lka_correction_rate=0.95,
            has_lidar=False,
            has_rtk_gps=False,
        ),
        notes="Autopilot HW2.5. Camera-primary, radar secondary. No lidar.",
    ),

    # --- Modern AV baseline (no degradation) ---
    "2023_av_platform": VehicleProfile(
        name="2023_av_platform",
        model_year=2023,
        adas_generation="av",
        sensors=SensorSpec(
            radar_range_m=250.0,
            radar_range_accuracy_m=0.1,
            radar_velocity_accuracy_mps=0.05,
            camera_fov_deg=360.0,
            camera_resolution="4k",
            camera_latency_ms=20.0,
            aeb_reaction_time_s=0.15,
            lka_correction_rate=1.0,
            has_lidar=True,
            has_rtk_gps=True,
        ),
        notes="Full AV sensor suite. Used as baseline for comparison.",
    ),
}


# ---------------------------------------------------------------------------
# Degradation model
# ---------------------------------------------------------------------------

@dataclass
class _DegradationFactors:
    """Computed degradation multipliers derived from a SensorSpec."""
    ttc_penalty: float        # fraction subtracted from TTC (0 = none, 1 = total loss)
    lane_dev_multiplier: float  # lane deviation amplification (1.0 = no change)
    jerk_multiplier: float    # jerk amplification from late/harsh braking
    collision_prob_add: float # additional collision probability


def _compute_degradation(spec: SensorSpec, weather_rain: float, weather_fog: float) -> _DegradationFactors:
    """
    Derive degradation factors from sensor spec and weather conditions.

    Logic mirrors real-world ADAS performance degradation documented in
    Euro NCAP AEB test results (2016–2019 cohort).
    """
    # Radar range penalty: reduced range → later detection → worse TTC
    radar_factor = min(spec.radar_range_m / 200.0, 1.0)  # normalised to 200m baseline
    ttc_penalty = (1.0 - radar_factor) * 0.4             # up to 40% TTC reduction

    # Camera latency penalty: higher latency → later reaction
    latency_factor = max(0.0, 1.0 - (spec.camera_latency_ms - 20.0) / 120.0)
    ttc_penalty += (1.0 - latency_factor) * 0.2          # up to 20% additional

    # Reaction time penalty: slower AEB → harsher braking when it fires
    reaction_excess = max(0.0, spec.aeb_reaction_time_s - 0.15)  # excess over AV baseline
    jerk_multiplier = 1.0 + reaction_excess * 2.0         # more jerk from late hard braking

    # LKA authority: lower authority → more lane deviation
    lane_dev_multiplier = 1.0 + (1.0 - spec.lka_correction_rate) * 1.5

    # Weather amplification: rain/fog hits camera harder than radar
    weather_severity = weather_rain * 0.6 + weather_fog * 0.8
    if spec.radar_range_m < 50.0:  # camera-only — weather hits much harder
        weather_severity *= 2.0
    ttc_penalty = min(ttc_penalty + weather_severity * 0.15, 0.85)
    lane_dev_multiplier *= 1.0 + weather_severity * 0.3

    # Collision probability increase from all degradation
    collision_prob_add = ttc_penalty * 0.12 + (jerk_multiplier - 1.0) * 0.03

    return _DegradationFactors(
        ttc_penalty=ttc_penalty,
        lane_dev_multiplier=lane_dev_multiplier,
        jerk_multiplier=jerk_multiplier,
        collision_prob_add=min(collision_prob_add, 0.4),
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class LegacyADASAdapter:
    """
    Wraps a base sim adapter and applies VehicleProfile degradation.

    Usage:
        adapter = LegacyADASAdapter(
            profile=VEHICLE_PROFILES["2018_volvo_xc60_pilot_assist"]
        )
        runner = SimulationRunner(sim_adapter=adapter, workers=8)

    The adapter is transparent when scenario.vehicle_profile is None
    (modern AV — no degradation applied).
    """

    def __init__(
        self,
        profile: VehicleProfile | None = None,
        base_adapter: Callable[[Scenario], dict] | None = None,
    ) -> None:
        self._profile = profile
        # Import here to avoid circular dependency
        from runner.engine import _mock_sim_adapter
        self._base = base_adapter or _mock_sim_adapter

    def __call__(self, scenario: Scenario) -> dict:
        # Run base simulation
        metrics = self._base(scenario)

        # Resolve profile: scenario-level overrides adapter-level
        profile = scenario.vehicle_profile or self._profile
        if profile is None or profile.adas_generation == "av":
            return metrics  # no degradation for modern AV

        return self._apply_degradation(metrics, profile, scenario)

    def _apply_degradation(
        self,
        metrics: dict,
        profile: VehicleProfile,
        scenario: Scenario,
    ) -> dict:
        """Apply sensor degradation model to raw sim metrics."""
        spec = profile.sensors
        rain = scenario.weather.rain_intensity
        fog = scenario.weather.fog_density
        d = _compute_degradation(spec, rain, fog)

        rng = random.Random(f"{scenario.scenario_id}:{profile.name}")
        degraded = dict(metrics)  # shallow copy — metrics values are scalars

        # TTC: degraded perception means we detect threats later
        if "min_ttc_s" in degraded:
            degraded["min_ttc_s"] = max(
                0.0,
                degraded["min_ttc_s"] * (1.0 - d.ttc_penalty)
                + rng.gauss(0, spec.radar_range_accuracy_m * 0.05),
            )

        # Jerk: late AEB fires harder
        if "avg_jerk_mps3" in degraded:
            degraded["avg_jerk_mps3"] = min(
                degraded["avg_jerk_mps3"] * d.jerk_multiplier,
                10.0,  # physical cap
            )

        # Lane deviation: limited LKA authority
        if "lane_deviation_m" in degraded:
            degraded["lane_deviation_m"] = min(
                degraded["lane_deviation_m"] * d.lane_dev_multiplier,
                2.0,
            )

        # Collision: additional probability from degraded perception
        if "collision_count" in degraded and degraded["collision_count"] == 0:
            if rng.random() < d.collision_prob_add:
                degraded["collision_count"] = 1

        # Reaction latency: add to duration metadata
        degraded["aeb_reaction_time_s"] = spec.aeb_reaction_time_s
        degraded["vehicle_profile"] = profile.name
        degraded["adas_generation"] = profile.adas_generation

        return degraded
