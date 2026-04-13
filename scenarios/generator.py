"""
Parameterized scenario generator.

Produces combinatorial scenario suites for edge-case coverage,
supporting both structured generation and random fuzzing.
"""

import hashlib
import itertools
import random
from collections.abc import Iterator

from .schema import Actor, Scenario, ScenarioCategory, VehicleProfile, WeatherCondition


def _stable_id(prefix: str, *parts) -> str:
    """Deterministic 8-char ID from prefix + content hash. No random UUID."""
    key = f"{prefix}:{'|'.join(str(p) for p in parts)}"
    return f"{prefix}_{hashlib.sha1(key.encode()).hexdigest()[:8]}"  # noqa: S324


class ScenarioGenerator:
    """Generate AV test scenarios from parameter grids or random sampling."""

    # Default parameter space for combinatorial generation
    _SPEED_RANGE_MPS = [8.0, 15.0, 25.0, 33.0]  # ~30, 55, 90, 120 km/h
    _WEATHER_PRESETS = [
        WeatherCondition(0.0, 0.0, "day"),
        WeatherCondition(0.5, 0.0, "day"),
        WeatherCondition(0.0, 0.6, "night"),
        WeatherCondition(0.8, 0.2, "dusk"),
    ]
    _MAPS = ["highway_101", "urban_grid_sf", "intersection_4way", "suburban_loop"]

    def highway_cut_in_suite(self) -> list[Scenario]:
        """Generate cut-in scenarios across speed and weather combinations."""
        scenarios = []
        for speed, weather in itertools.product(self._SPEED_RANGE_MPS, self._WEATHER_PRESETS):
            side = "left" if speed % 2 == 0 else "right"  # deterministic side from speed
            actor = Actor(
                actor_id="npc_0",
                actor_type="vehicle",
                initial_speed_mps=speed + 5.0,
                trajectory=self._cut_in_trajectory(side=side),
            )
            s = Scenario(
                scenario_id=_stable_id(
                    "cut_in", speed, weather.time_of_day, weather.rain_intensity
                ),
                category=ScenarioCategory.CUT_IN,
                description=f"Cut-in at {speed} m/s, weather={weather.time_of_day}",
                ego_initial_speed_mps=speed,
                map_id="highway_101",
                actors=[actor],
                weather=weather,
                duration_s=20.0,
                tags=["cut_in", "highway", "smoke", weather.time_of_day],
            )
            scenarios.append(s)
        return scenarios

    def pedestrian_crossing_suite(self) -> list[Scenario]:
        """Generate pedestrian crossing scenarios at varying speeds and densities."""
        scenarios = []
        for num_peds in [1, 3, 5]:
            for speed in [5.0, 10.0, 15.0]:
                actors = [
                    Actor(
                        actor_id=f"ped_{i}",
                        actor_type="pedestrian",
                        initial_speed_mps=1.2,
                        trajectory=self._pedestrian_crossing_trajectory(offset=i * 1.5),
                    )
                    for i in range(num_peds)
                ]
                s = Scenario(
                    scenario_id=_stable_id("ped_cross", num_peds, speed),
                    category=ScenarioCategory.PEDESTRIAN,
                    description=f"{num_peds} pedestrians crossing at ego {speed} m/s",
                    ego_initial_speed_mps=speed,
                    map_id="urban_grid_sf",
                    actors=actors,
                    duration_s=15.0,
                    tags=["pedestrian", "urban", "smoke"],
                )
                scenarios.append(s)
        return scenarios

    def adverse_weather_suite(self) -> list[Scenario]:
        """Stress-test perception under heavy rain and fog."""
        scenarios = []
        for rain, fog, tod in [(0.9, 0.0, "day"), (0.0, 0.9, "night"), (0.7, 0.5, "dusk")]:
            weather = WeatherCondition(rain, fog, tod)
            s = Scenario(
                scenario_id=_stable_id("weather", rain, fog, tod),
                category=ScenarioCategory.ADVERSE_WEATHER,
                description=f"Adverse weather: rain={rain}, fog={fog}, {tod}",
                ego_initial_speed_mps=15.0,
                map_id="suburban_loop",
                weather=weather,
                duration_s=60.0,
                tags=["weather", "smoke", tod],
            )
            scenarios.append(s)
        return scenarios

    def full_suite(self) -> list[Scenario]:
        return (
            self.highway_cut_in_suite()
            + self.pedestrian_crossing_suite()
            + self.adverse_weather_suite()
        )

    def legacy_adas_suite(self, profile: "VehicleProfile") -> list[Scenario]:  # noqa: F821
        """
        Generate scenarios tuned for pre-2020 ADAS-equipped vehicles.

        Speed ranges, scenario durations, and categories are calibrated to
        the operational design domain of Gen1/Gen2 ADAS systems:
          - Lower ego speeds (ADAS typically disengages above ~130 km/h)
          - AEB-focused: stationary/slow lead vehicle, pedestrian crossing
          - LKA-focused: gentle curves, lane departure at highway speeds
          - ACC-focused: follow distance, cut-in at moderate speed

        Args:
            profile: VehicleProfile to attach to each scenario.
                     The LegacyADASAdapter will use this to apply degradation.
        """
        return (
            self._legacy_aeb_suite(profile)
            + self._legacy_lka_suite(profile)
            + self._legacy_acc_suite(profile)
        )

    def _legacy_aeb_suite(self, profile: "VehicleProfile") -> list[Scenario]:  # noqa: F821
        """AEB scenarios: ego approaching stationary/slow target."""
        scenarios = []
        # Speeds typical for AEB test protocols (Euro NCAP CCRs/CCRm)
        for ego_speed in [10.0, 20.0, 30.0, 40.0 / 3.6 * 10]:  # 10–40 km/h range
            for target_speed in [0.0, 5.0]:  # stationary or slow-moving target
                actor = Actor(
                    actor_id="target_0",
                    actor_type="vehicle",
                    initial_speed_mps=target_speed,
                    trajectory=[
                        {"x": 40.0, "y": 0.0, "heading": 0.0, "t": 0.0},
                        {"x": 40.0 + target_speed * 5, "y": 0.0, "heading": 0.0, "t": 5.0},
                    ],
                )
                s = Scenario(
                    scenario_id=_stable_id("legacy_aeb", profile.name, ego_speed, target_speed),
                    category=ScenarioCategory.LEGACY_AEB,
                    description=(
                        f"AEB [{profile.name}]: ego {ego_speed:.1f} m/s → "
                        f"target {target_speed:.1f} m/s"
                    ),
                    ego_initial_speed_mps=ego_speed,
                    map_id="highway_101",
                    actors=[actor],
                    vehicle_profile=profile,
                    duration_s=10.0,
                    tags=["legacy", "aeb", profile.adas_generation, profile.name],
                )
                scenarios.append(s)
        return scenarios

    def _legacy_lka_suite(self, profile: "VehicleProfile") -> list[Scenario]:  # noqa: F821
        """LKA scenarios: lane departure on straight and curved road."""
        scenarios = []
        for speed in [20.0, 25.0, 30.0]:  # 72–108 km/h — LKA operational range
            for weather in [
                WeatherCondition(0.0, 0.0, "day"),
                WeatherCondition(0.5, 0.0, "night"),  # faded lane markings + dark
            ]:
                s = Scenario(
                    scenario_id=_stable_id("legacy_lka", profile.name, speed, weather.time_of_day),
                    category=ScenarioCategory.LEGACY_LKA,
                    description=(
                        f"LKA [{profile.name}]: {speed:.0f} m/s, "
                        f"{weather.time_of_day}, rain={weather.rain_intensity}"
                    ),
                    ego_initial_speed_mps=speed,
                    map_id="suburban_loop",
                    weather=weather,
                    vehicle_profile=profile,
                    duration_s=30.0,
                    tags=["legacy", "lka", profile.adas_generation, weather.time_of_day],
                )
                scenarios.append(s)
        return scenarios

    def _legacy_acc_suite(self, profile: "VehicleProfile") -> list[Scenario]:  # noqa: F821
        """ACC scenarios: following distance and cut-in at moderate speed."""
        scenarios = []
        for ego_speed, follow_gap_m in [(20.0, 30.0), (25.0, 40.0), (30.0, 50.0)]:
            actor = Actor(
                actor_id="lead_0",
                actor_type="vehicle",
                initial_speed_mps=ego_speed - 3.0,  # lead vehicle slightly slower
                trajectory=[
                    {"x": follow_gap_m, "y": 0.0, "heading": 0.0, "t": 0.0},
                    {
                        "x": follow_gap_m + (ego_speed - 3.0) * 20,
                        "y": 0.0,
                        "heading": 0.0,
                        "t": 20.0,
                    },
                ],
            )
            s = Scenario(
                scenario_id=_stable_id("legacy_acc", profile.name, ego_speed, follow_gap_m),
                category=ScenarioCategory.LEGACY_ACC,
                description=(
                    f"ACC [{profile.name}]: ego {ego_speed:.0f} m/s, gap {follow_gap_m:.0f} m"
                ),
                ego_initial_speed_mps=ego_speed,
                map_id="highway_101",
                actors=[actor],
                vehicle_profile=profile,
                duration_s=20.0,
                tags=["legacy", "acc", profile.adas_generation],
            )
            scenarios.append(s)
        return scenarios

    def random_fuzz(self, n: int = 100, seed: int | None = None) -> Iterator[Scenario]:
        """Yield n randomly parameterized scenarios for fuzz testing."""
        rng = random.Random(seed)
        categories = list(ScenarioCategory)
        for i in range(n):
            cat = rng.choice(categories)
            yield Scenario(
                scenario_id=f"fuzz_{seed}_{i}_{rng.randint(0, 0xFFFFFF):06x}",
                category=cat,
                description=f"Fuzz scenario [{cat}]",
                ego_initial_speed_mps=rng.uniform(0.0, 35.0),
                map_id=rng.choice(self._MAPS),
                weather=WeatherCondition(
                    rain_intensity=rng.random(),
                    fog_density=rng.random(),
                    time_of_day=rng.choice(["day", "dusk", "night"]),
                ),
                duration_s=rng.uniform(10.0, 60.0),
                tags=["fuzz"],
            )

    # --- Trajectory helpers ---

    def _cut_in_trajectory(self, side: str) -> list[dict]:
        sign = 1 if side == "left" else -1
        return [
            {"x": 0.0, "y": sign * 3.5, "heading": 0.0, "t": 0.0},
            {"x": 30.0, "y": sign * 1.5, "heading": -sign * 0.1, "t": 3.0},
            {"x": 60.0, "y": 0.0, "heading": 0.0, "t": 6.0},
        ]

    def _pedestrian_crossing_trajectory(self, offset: float = 0.0) -> list[dict]:
        return [
            {"x": 20.0 + offset, "y": -5.0, "heading": 1.57, "t": 0.0},
            {"x": 20.0 + offset, "y": 0.0, "heading": 1.57, "t": 4.0},
            {"x": 20.0 + offset, "y": 5.0, "heading": 1.57, "t": 8.0},
        ]
