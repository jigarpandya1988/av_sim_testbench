"""
Distributed simulation runner using Ray.

Scales scenario execution across a Ray cluster — local multicore
or remote (AWS, GCP, on-prem) with zero code changes.

Falls back to the async SimulationRunner when Ray is not installed.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from scenarios.schema import Scenario
from runner.engine import RunResult, RunStatus, _mock_sim_adapter

logger = logging.getLogger(__name__)

try:
    import ray
    _RAY_AVAILABLE = True
except ImportError:
    _RAY_AVAILABLE = False
    logger.warning("Ray not installed — distributed runner unavailable. pip install ray")


def run_suite_distributed(
    scenarios: list[Scenario],
    sim_adapter: Callable[[Scenario], dict] | None = None,
    num_cpus: int | None = None,
    timeout_s: float = 120.0,
    max_retries: int = 2,
) -> list[RunResult]:
    """
    Run a scenario suite distributed across a Ray cluster.

    Args:
        scenarios: List of scenarios to execute.
        sim_adapter: Callable that runs one scenario and returns metrics dict.
                     Defaults to mock adapter.
        num_cpus: CPUs to request per task. None = Ray default.
        timeout_s: Per-scenario timeout.
        max_retries: Retry count on transient failure.

    Returns:
        List of RunResult in same order as input scenarios.
    """
    if not _RAY_AVAILABLE:
        logger.warning("Falling back to async runner (Ray not available)")
        import asyncio
        from runner.engine import SimulationRunner
        runner = SimulationRunner(
            sim_adapter=sim_adapter,
            workers=8,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )
        return asyncio.run(runner.run_suite(scenarios))

    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
        logger.info("Ray initialized: %s", ray.cluster_resources())

    adapter = sim_adapter or _mock_sim_adapter

    @ray.remote(num_cpus=num_cpus or 1, max_retries=max_retries)
    def _remote_run(scenario: Scenario) -> RunResult:
        start = time.monotonic()
        try:
            metrics = adapter(scenario)
            elapsed = time.monotonic() - start
            status = RunStatus.PASSED if metrics.get("collision_count", 0) == 0 else RunStatus.FAILED
            return RunResult(
                scenario_id=scenario.scenario_id,
                status=status,
                duration_s=elapsed,
                metrics=metrics,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            return RunResult(
                scenario_id=scenario.scenario_id,
                status=RunStatus.ERROR,
                duration_s=elapsed,
                error=str(exc),
            )

    logger.info("Submitting %d scenarios to Ray cluster", len(scenarios))
    futures = [_remote_run.remote(s) for s in scenarios]

    results = []
    done_count = 0
    while futures:
        ready, futures = ray.wait(futures, num_returns=min(10, len(futures)), timeout=timeout_s)
        for ref in ready:
            try:
                result = ray.get(ref)
            except Exception as exc:  # noqa: BLE001
                result = RunResult(
                    scenario_id="unknown",
                    status=RunStatus.ERROR,
                    duration_s=0.0,
                    error=str(exc),
                )
            results.append(result)
            done_count += 1
            if done_count % 50 == 0:
                logger.info("Progress: %d / %d scenarios complete", done_count, len(scenarios))

    logger.info("Distributed run complete: %d results", len(results))
    return results
