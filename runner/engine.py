"""
Async simulation execution engine.

Runs scenarios in parallel worker pools with retry logic,
timeout enforcement, and structured result collection.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from scenarios.schema import Scenario

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class RunResult:
    scenario_id: str
    status: RunStatus
    duration_s: float
    metrics: dict = field(default_factory=dict)
    error: str | None = None
    retries: int = 0


class SimulationRunner:
    """
    Async batch runner for AV simulation scenarios.

    Supports configurable worker concurrency, per-scenario timeouts,
    retry on transient failures, and pluggable sim backend adapters.
    """

    def __init__(
        self,
        sim_adapter: Callable[[Scenario], dict] | None = None,
        workers: int = 4,
        timeout_s: float = 120.0,
        max_retries: int = 2,
    ):
        self._adapter = sim_adapter or _mock_sim_adapter
        self._workers = workers
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    async def run_suite(self, scenarios: list[Scenario]) -> list[RunResult]:
        """Run all scenarios concurrently up to worker limit."""
        if not scenarios:
            logger.warning("run_suite called with empty scenario list")
            return []
        semaphore = asyncio.Semaphore(self._workers)
        tasks = [self._run_with_semaphore(s, semaphore) for s in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    async def _run_with_semaphore(
        self, scenario: Scenario, sem: asyncio.Semaphore
    ) -> RunResult:
        async with sem:
            return await self._run_scenario(scenario)

    async def _run_scenario(self, scenario: Scenario) -> RunResult:
        attempt = 0
        while attempt <= self._max_retries:
            start = time.monotonic()
            try:
                metrics = await asyncio.wait_for(
                    asyncio.to_thread(self._adapter, scenario),
                    timeout=self._timeout_s,
                )
                elapsed = time.monotonic() - start
                status = RunStatus.PASSED if metrics.get("collision_count", 0) == 0 else RunStatus.FAILED
                logger.info("[%s] %s in %.2fs", status.value.upper(), scenario.scenario_id, elapsed)
                return RunResult(
                    scenario_id=scenario.scenario_id,
                    status=status,
                    duration_s=elapsed,
                    metrics=metrics,
                    retries=attempt,
                )
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                logger.warning("TIMEOUT %s after %.1fs (attempt %d)", scenario.scenario_id, elapsed, attempt + 1)
                if attempt == self._max_retries:
                    return RunResult(scenario.scenario_id, RunStatus.TIMEOUT, elapsed, retries=attempt)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.monotonic() - start
                logger.error("ERROR %s: %s (attempt %d)", scenario.scenario_id, exc, attempt + 1)
                if attempt == self._max_retries:
                    return RunResult(scenario.scenario_id, RunStatus.ERROR, elapsed, error=str(exc), retries=attempt)
            attempt += 1
            await asyncio.sleep(0.5 * attempt)  # exponential backoff

        # unreachable, but satisfies type checker
        return RunResult(scenario.scenario_id, RunStatus.ERROR, 0.0)


# ---------------------------------------------------------------------------
# Mock adapter — replace with real sim backend (CARLA, LGSVL, NVIDIA DRIVE Sim)
# ---------------------------------------------------------------------------

def _mock_sim_adapter(scenario: Scenario) -> dict:
    """
    Stub that simulates a scenario run and returns synthetic metrics.
    Replace with actual simulator SDK calls.
    """
    import random
    rng = random.Random(scenario.scenario_id)
    time.sleep(rng.uniform(0.05, 0.3))  # simulate variable run time

    collision_prob = 0.05
    if scenario.weather.rain_intensity > 0.7:
        collision_prob += 0.08
    if scenario.weather.fog_density > 0.7:
        collision_prob += 0.10

    return {
        "collision_count": 1 if rng.random() < collision_prob else 0,
        "min_ttc_s": rng.uniform(0.5, 8.0),
        "avg_jerk_mps3": rng.uniform(0.1, 3.5),
        "lane_deviation_m": rng.uniform(0.0, 0.8),
        "completion_rate": 1.0 if rng.random() > 0.02 else 0.0,
        "speed_limit_violations": rng.randint(0, 2),
    }
