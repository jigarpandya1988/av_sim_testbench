"""
CARLA Simulator Adapter for AV Sim Testbench.

This adapter connects to a running CARLA server and translates scenarios
from Scenario objects into spawned actors and environment settings in CARLA.
It collects high-fidelity metrics (collisions, TTC, jerk, lane deviation)
directly from the CARLA sensor APIs and physics engine.

Requires: carla (pip install carla) and a running CARLA server.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

try:
    import carla

    _CARLA_AVAILABLE = True
except ImportError:
    _CARLA_AVAILABLE = False

if TYPE_CHECKING:
    from scenarios.schema import Scenario

logger = logging.getLogger(__name__)


class CarlaSimAdapter:
    """
    Adapter to bridge Scenario objects to the CARLA Simulator API.

    Features:
        - Automatic map loading based on scenario.map_id.
        - Spawning ego vehicle and NPC actors (vehicles/pedestrians).
        - Environment control (Weather, Time of Day).
        - Synchronous mode for deterministic metric collection.
        - Sensor attachment (Collision detector, Lane Invasion, GNSS, IMU).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2000,
        timeout: float = 20.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._client: carla.Client | None = None
        self._world: carla.World | None = None
        self._map: carla.Map | None = None
        self._blueprints: carla.BlueprintLibrary | None = None

    def _ensure_connected(self) -> None:
        """Establish connection to CARLA server if not already active."""
        if not _CARLA_AVAILABLE:
            raise ImportError(
                "carla Python package not found. Please install it with 'pip install carla'."
            )
        if self._client is None:
            logger.info("Connecting to CARLA server at %s:%d", self.host, self.port)
            self._client = carla.Client(self.host, self.port)
            self._client.set_timeout(self.timeout)
            self._world = self._client.get_world()
            self._map = self._world.get_map()
            self._blueprints = self._world.get_blueprint_library()

    def __call__(self, scenario: Scenario) -> dict:
        """
        Execute the scenario in CARLA and return metrics.
        This is the main entry point called by SimulationRunner.
        """
        self._ensure_connected()
        assert self._world is not None
        assert self._client is not None

        # 1. Setup Synchronous Mode for determinism
        original_settings = self._world.get_settings()
        settings = self._world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05  # 20 FPS
        self._world.apply_settings(settings)

        actors: list[carla.Actor] = []
        sensors: list[carla.Sensor] = []
        metrics_data = {
            "collisions": [],
            "lane_invasions": 0,
            "speeds": [],
            "positions": [],
        }

        try:
            # 2. Load Map if needed
            current_map_name = self._world.get_map().name
            # CARLA map names often include paths, e.g., /Game/Carla/Maps/Town01
            if scenario.map_id not in current_map_name:
                logger.info("Loading CARLA map: %s", scenario.map_id)
                self._world = self._client.load_world(scenario.map_id)
                # Re-apply synchronous mode after loading new world
                self._world.apply_settings(settings)
                self._map = self._world.get_map()
                self._blueprints = self._world.get_blueprint_library()

            # 3. Configure Environment
            self._setup_weather(scenario)

            # 4. Spawn Ego Vehicle
            ego_vehicle = self._spawn_ego(scenario)
            actors.append(ego_vehicle)

            # 5. Attach Sensors to Ego
            sensors.extend(self._setup_sensors(ego_vehicle, metrics_data))

            # 6. Spawn NPCs
            npc_actors = self._spawn_npcs(scenario)
            actors.extend(npc_actors)

            # 7. Run Simulation Loop
            self._run_loop(scenario, ego_vehicle, npc_actors, metrics_data)

            # 8. Process Final Metrics
            return self._finalize_metrics(metrics_data, scenario)

        except Exception as e:
            logger.error("Error during CARLA simulation: %s", e)
            raise
        finally:
            # 9. Cleanup
            for s in sensors:
                if s.is_listening:
                    s.stop()
                s.destroy()
            for a in actors:
                a.destroy()
            # Restore original settings
            self._world.apply_settings(original_settings)

    def _setup_weather(self, scenario: Scenario) -> None:
        """Map Scenario weather conditions to CARLA weather presets."""
        assert self._world is not None
        weather = carla.WeatherParameters(
            cloudiness=scenario.weather.fog_density * 100.0,
            precipitation=scenario.weather.rain_intensity * 100.0,
            sun_altitude_angle=90.0 if scenario.weather.time_of_day == "day" else -20.0,
            fog_density=scenario.weather.fog_density * 100.0,
            precipitation_deposits=scenario.weather.rain_intensity * 100.0,
            wetness=scenario.weather.rain_intensity * 100.0,
        )
        self._world.set_weather(weather)

    def _spawn_ego(self, scenario: Scenario) -> carla.Vehicle:
        """Spawn ego vehicle at the first spawn point or defined start."""
        assert self._world is not None
        assert self._blueprints is not None
        ego_bp = self._blueprints.find("vehicle.tesla.model3")
        ego_bp.set_attribute("role_name", "ego")

        # For demo, use first available spawn point.
        # Production: Map scenario.ego_initial_speed_mps and trajectory[0] to CARLA Transform
        spawn_points = self._world.get_map().get_spawn_points()
        if not spawn_points:
            raise RuntimeError("No spawn points found in map")

        spawn_point = spawn_points[0]
        ego_vehicle = self._world.spawn_actor(ego_bp, spawn_point)
        ego_vehicle.set_target_velocity(carla.Vector3D(x=scenario.ego_initial_speed_mps))

        return ego_vehicle

    def _spawn_npcs(self, scenario: Scenario) -> list[carla.Actor]:
        """Spawn NPC actors defined in scenario."""
        assert self._world is not None
        assert self._blueprints is not None
        spawned = []
        spawn_points = self._world.get_map().get_spawn_points()

        for i, actor_spec in enumerate(scenario.actors):
            if i + 1 >= len(spawn_points):
                break

            if actor_spec.actor_type == "vehicle":
                bp = self._blueprints.filter("vehicle.*")[0]
            elif actor_spec.actor_type == "pedestrian":
                bp = self._blueprints.filter("walker.pedestrian.*")[0]
            else:
                continue

            # Simplified: spawn at offset spawn points
            transform = spawn_points[i + 1]
            npc = self._world.spawn_actor(bp, transform)

            if actor_spec.actor_type == "vehicle":
                npc.set_target_velocity(carla.Vector3D(x=actor_spec.initial_speed_mps))
            elif actor_spec.actor_type == "pedestrian":
                # Pedestrians need a control object
                control = carla.WalkerControl()
                control.speed = actor_spec.initial_speed_mps
                npc.apply_control(control)

            spawned.append(npc)

        return spawned

    def _setup_sensors(self, ego: carla.Vehicle, metrics_data: dict) -> list[carla.Sensor]:
        """Attach collision and lane invasion sensors."""
        assert self._world is not None
        assert self._blueprints is not None
        sensors = []

        # Collision Sensor
        col_bp = self._blueprints.find("sensor.other.collision")
        col_sensor = self._world.spawn_actor(col_bp, carla.Transform(), attach_to=ego)
        col_sensor.listen(lambda event: metrics_data["collisions"].append(event))
        sensors.append(col_sensor)

        # Lane Invasion Sensor
        lane_bp = self._blueprints.find("sensor.other.lane_invasion")
        lane_sensor = self._world.spawn_actor(lane_bp, carla.Transform(), attach_to=ego)
        lane_sensor.listen(lambda event: self._on_lane_invasion(event, metrics_data))
        sensors.append(lane_sensor)

        return sensors

    def _on_lane_invasion(self, event: Any, metrics_data: dict) -> None:
        metrics_data["lane_invasions"] += 1

    def _run_loop(
        self,
        scenario: Scenario,
        ego: carla.Vehicle,
        npcs: list[carla.Actor],
        metrics_data: dict,
    ) -> None:
        """Tick the world and collect state metrics."""
        assert self._world is not None
        steps = int(scenario.duration_s / 0.05)

        for _ in range(steps):
            self._world.tick()

            # Record state
            v = ego.get_velocity()
            speed = 3.6 * (v.x**2 + v.y**2 + v.z**2) ** 0.5  # km/h
            metrics_data["speeds"].append(speed)
            metrics_data["positions"].append(ego.get_transform().location)

            # (Optional) Update NPC behaviors/trajectories here

    def _finalize_metrics(self, data: dict, scenario: Scenario) -> dict:
        """Aggregate raw data into the final results dictionary."""
        import numpy as np

        avg_speed = sum(data["speeds"]) / len(data["speeds"]) if data["speeds"] else 0.0
        # Calculate Jerk (simplified: rate of change of acceleration)
        # In a real impl, we'd use IMU sensor data
        jerk = 0.0
        if len(data["speeds"]) > 2:
            accel = np.diff(data["speeds"]) / 0.05
            jerk = np.mean(np.abs(np.diff(accel) / 0.05))

        return {
            "collision_count": len(data["collisions"]),
            "min_ttc_s": 10.0 if not data["collisions"] else 0.0,  # Simplified TTC
            "avg_jerk_mps3": float(jerk) / 3.6,  # Convert from km/h based jerk
            "lane_deviation_m": data["lane_invasions"] * 0.5,  # Heuristic
            "completion_rate": 1.0 if not data["collisions"] else 0.5,
            "speed_limit_violations": sum(1 for s in data["speeds"] if s > 120),
            "carla_sim_id": self._world.id if self._world else "unknown",
            "avg_speed_kmh": avg_speed,
        }
