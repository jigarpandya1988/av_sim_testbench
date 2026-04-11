"""
Parameterized scenario generator.

Produces combinatorial scenario suites for edge-case coverage,
supporting both structured generation and random fuzzing.
"""
import itertools
import random
import uuid
from typing import Iterator

from .schema import Actor, Scenario, ScenarioCategory, WeatherCondition


class ScenarioGenerator:
    """Generate AV test scenarios from parameter grids or random sampling."""

    # Default parameter space for combinatorial generation
    _SPEED_RANGE_MPS = [8.0, 15.0, 25.0, 33.0]   # ~30, 55, 90, 120 km/h
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
            actor = Actor(
                actor_id="npc_0",
                actor_type="vehicle",
                initial_speed_mps=speed + 5.0,
                trajectory=self._cut_in_trajectory(side=random.choice(["left", "right"])),
            )
            s = Scenario(
                scenario_id=f"cut_in_{uuid.uuid4().hex[:8]}",
                category=ScenarioCategory.CUT_IN,
                description=f"Cut-in at {speed} m/s, weather={weather.time_of_day}",
                ego_initial_speed_mps=speed,
                map_id="highway_101",
                actors=[actor],
                weather=weather,
                duration_s=20.0,
                tags=["cut_in", "highway", weather.time_of_day],
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
                    scenario_id=f"ped_cross_{uuid.uuid4().hex[:8]}",
                    category=ScenarioCategory.PEDESTRIAN,
                    description=f"{num_peds} pedestrians crossing at ego {speed} m/s",
                    ego_initial_speed_mps=speed,
                    map_id="urban_grid_sf",
                    actors=actors,
                    duration_s=15.0,
                    tags=["pedestrian", "urban"],
                )
                scenarios.append(s)
        return scenarios

    def adverse_weather_suite(self) -> list[Scenario]:
        """Stress-test perception under heavy rain and fog."""
        scenarios = []
        for rain, fog, tod in [(0.9, 0.0, "day"), (0.0, 0.9, "night"), (0.7, 0.5, "dusk")]:
            weather = WeatherCondition(rain, fog, tod)
            s = Scenario(
                scenario_id=f"weather_{uuid.uuid4().hex[:8]}",
                category=ScenarioCategory.ADVERSE_WEATHER,
                description=f"Adverse weather: rain={rain}, fog={fog}, {tod}",
                ego_initial_speed_mps=15.0,
                map_id="suburban_loop",
                weather=weather,
                duration_s=60.0,
                tags=["weather", tod],
            )
            scenarios.append(s)
        return scenarios

    def full_suite(self) -> list[Scenario]:
        return (
            self.highway_cut_in_suite()
            + self.pedestrian_crossing_suite()
            + self.adverse_weather_suite()
        )

    def random_fuzz(self, n: int = 100, seed: int | None = None) -> Iterator[Scenario]:
        """Yield n randomly parameterized scenarios for fuzz testing."""
        rng = random.Random(seed)
        categories = list(ScenarioCategory)
        for _ in range(n):
            cat = rng.choice(categories)
            yield Scenario(
                scenario_id=f"fuzz_{uuid.uuid4().hex[:8]}",
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
