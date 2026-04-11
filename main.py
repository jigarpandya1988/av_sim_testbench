"""
AV Sim Testbench — CLI entrypoint.

Usage:
    python main.py --suite full --workers 8
    python main.py --suite smoke --report reports/out.json
    python main.py --replay logs/drive_001.log --replay-baseline baselines/baseline.json
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from scenarios.generator import ScenarioGenerator
from runner.engine import SimulationRunner
from metrics.scoring import MetricsScorer
from replay.regression import ReplayRegressionRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AV Simulation Testbench")
    p.add_argument(
        "--suite",
        choices=["full", "smoke", "highway", "pedestrian", "weather"],
        default="smoke",
        help="Scenario suite to run",
    )
    p.add_argument("--workers", type=int, default=4, help="Parallel sim workers")
    p.add_argument("--timeout", type=float, default=120.0, help="Per-scenario timeout (s)")
    p.add_argument("--report", type=Path, default=None, help="Path to write JSON report")
    p.add_argument("--replay", type=Path, nargs="*", help="Drive log files for replay regression")
    p.add_argument("--replay-baseline", type=Path, default=Path("baselines/baseline.json"))
    return p.parse_args()


def build_suite(suite_name: str):
    gen = ScenarioGenerator()
    match suite_name:
        case "full":
            return gen.full_suite()
        case "smoke":
            return gen.highway_cut_in_suite()[:5] + gen.pedestrian_crossing_suite()[:3]
        case "highway":
            return gen.highway_cut_in_suite()
        case "pedestrian":
            return gen.pedestrian_crossing_suite()
        case "weather":
            return gen.adverse_weather_suite()
        case _:
            return gen.full_suite()


async def run_sim_suite(args: argparse.Namespace) -> int:
    scenarios = build_suite(args.suite)
    logger.info("Running suite '%s': %d scenarios, %d workers", args.suite, len(scenarios), args.workers)

    runner = SimulationRunner(workers=args.workers, timeout_s=args.timeout)
    results = await runner.run_suite(scenarios)

    scorer = MetricsScorer()
    scenarios_by_id = {s.scenario_id: s for s in scenarios}
    report = scorer.score_suite(results, scenarios_by_id)

    logger.info(
        "Results: %d passed / %d failed / %d timeout / %d error  (pass rate: %.1f%%)",
        report.passed, report.failed, report.timeout, report.error,
        report.pass_rate * 100,
    )

    if args.report:
        report.to_json(args.report)
        logger.info("Report written to %s", args.report)

    return 0 if report.failed == 0 and report.error == 0 else 1


def run_replay(args: argparse.Namespace) -> int:
    log_paths = args.replay or []
    if not log_paths:
        logger.warning("No replay logs provided, skipping.")
        return 0

    scorer = MetricsScorer()
    runner = ReplayRegressionRunner(baseline_path=args.replay_baseline)
    results = runner.run(log_paths, scorer)

    regressions = [r for r in results if r.regressed]
    logger.info("Replay: %d logs, %d regressions", len(results), len(regressions))

    for r in regressions:
        logger.warning("  REGRESSION %s: %.3f → %.3f", r.log_id, r.baseline_score, r.current_score)

    return 1 if regressions else 0


def main() -> int:
    args = parse_args()

    if args.replay:
        return run_replay(args)

    return asyncio.run(run_sim_suite(args))


if __name__ == "__main__":
    sys.exit(main())
