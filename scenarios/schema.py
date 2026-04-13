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
    LEGACY_AEB = "legacy_aeb"           # Automatic Emergency Braking validation
    LEGACY_LKA = "legacy_lka"           # Lane Keeping Assist validation
    LEGACY_ACC = "legacy_acc"           # Adaptive Cruise Control validation


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
class SensorSpec:
    """
    Describes the sensing capabilities of a vehicle's ADAS hardware.

    Used to model perception degradation in legacy vehicles vs modern AV platforms.
    All range/accuracy values are approximate real-world specs for each generation.
    """
    # Radar
    radar_range_m: float = 200.0          # detection range
    radar_range_accuracy_m: float = 0.5   # range measurement error (1-sigma)
    radar_velocity_accuracy_mps: float = 0.1

    # Camera
    camera_fov_deg: float = 120.0         # horizontal field of view
    camera_resolution: str = "1080p"      # "480p", "720p", "1080p"
    camera_latency_ms: float = 50.0       # perception pipeline latency

    # Reaction / actuation
    aeb_reaction_time_s: float = 0.3      # time from detection to brake apply
    lka_correction_rate: float = 1.0      # 1.0 = full authority, <1 = limited

    # Derived flag — set automatically
    has_lidar: bool = False
    has_rtk_gps: bool = False


@dataclass
class VehicleProfile:
    """
    Captures the hardware generation and ADAS capability of a test vehicle.

    Attach to a Scenario to drive the sim adapter's degradation model.
    Pre-built profiles for common vehicle generations are in
    adapters/legacy_adas.py::VEHICLE_PROFILES.
    """
    name: str                             # e.g. "2017_honda_civic_sensing"
    model_year: int
    adas_generation: str                  # "none", "gen1", "gen2", "av"
    sensors: SensorSpec = field(default_factory=SensorSpec)
    notes: str = ""


@dataclass
class Scenario:
    scenario_id: str
    category: ScenarioCategory
    description: str
    ego_initial_speed_mps: float
    map_id: str
    actors: list[Actor] = field(default_factory=list)
    weather: WeatherCondition = field(default_factory=WeatherCondition)
    vehicle_profile: VehicleProfile | None = None   # None = modern AV (no degradation)
    duration_s: float = 30.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
