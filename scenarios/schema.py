"""Scenario data models."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScenarioCategory(str, Enum):
    HIGHWAY = "highway"
    URBAN = "urban"
    INTERSECTION = "intersection"
    PEDESTRIAN = "pedestrian"
    ADVERSE_WEATHER = "adverse_weather"
    CUT_IN = "cut_in"
    EMERGENCY_VEHICLE = "emergency_vehicle"
    REPLAY = "replay"


@dataclass
class Actor:
    actor_id: str
    actor_type: str          # "vehicle", "pedestrian", "cyclist"
    initial_speed_mps: float
    trajectory: list[dict]   # [{x, y, heading, t}]


@dataclass
class WeatherCondition:
    rain_intensity: float = 0.0   # 0.0 - 1.0
    fog_density: float = 0.0
    time_of_day: str = "day"      # "day", "dusk", "night"


@dataclass
class Scenario:
    scenario_id: str
    category: ScenarioCategory
    description: str
    ego_initial_speed_mps: float
    map_id: str
    actors: list[Actor] = field(default_factory=list)
    weather: WeatherCondition = field(default_factory=WeatherCondition)
    duration_s: float = 30.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
