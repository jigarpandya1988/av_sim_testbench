"""
AV Sim Testbench — CLI entrypoint.

Usage:
    python main.py --suite full --workers 8
    python main.py --suite smoke --report reports/out.json --html-report reports/out.html
    python main.py --replay logs/drive_001.log --replay-baseline baselines/baseline.json
    python main.py --suite full --distributed --workers 16
    python main.py --suite full --metrics-port 8000
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from observability.logger import configure_logging, get_logger
from scenarios.generator import ScenarioGenerator
from runner.engine import SimulationRunner
from metrics.scoring import MetricsScorer
from replay.regression import ReplayRegressionRunner
from catalog.store import ScenarioCatalog, RunRecord
from observability.metrics_exporter import SimMetricsExporter
from reports.html_reporter import HTMLReporter

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AV Simulation Testbench")
    p.add_argument(
        "--suite",
        choices=["full", "smoke", "highway", "pedestrian", "weather"],
        default="smoke",
    )
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--report", type=Path, default=None, help="JSON report output path")
    p.add_argument("--html-report", type=Path, default=None, help="HTML report output path")
    p.add_argument("--replay", type=Path, nargs="*")
    p.add_argument("--replay-baseline", type=Path, default=Path("baselines/baseline.json"))
    p.add_argument("--distributed", action="store_true", help="Use Ray distributed runner")
    p.add_argument("--metrics-port", type=int, default=None, help="Prometheus scrape port")
    p.add_argument("--db", type=Path, default=Path("catalog/av_sim.db"), help="Catalog DB path")
    p.add_argument("--model-version", type=str, default="dev", help="Model version tag for catalog")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def build_suite(suite_name: str):
    gen = ScenarioGenerator()
    match suite_name:
        case "full":      return gen.full_suite()
        case "smoke":     return gen.highway_cut_in_suite()[:5] + gen.pedestrian_crossing_suite()[:3]
        case "highway":   return gen.highway_cut_in_suite()
        case "pedestrian":return gen.pedestrian_crossing_suite()
        case "weather":   return gen.adverse_weather_suite()
        case _:           return gen.full_suite()


async def run_sim_suite(args: argparse.Namespace) -> int:
    scenarios = build_suite(args.suite)
    logger.info("suite_start", suite=args.suite, total=len(scenarios), workers=args.workers)

    exporter = SimMetricsExporter()
    if args.metrics_port:
        exporter.start_server(port=args.metrics_port)
        logger.info("prometheus_server_started", port=args.metrics_port)

    catalog = ScenarioCatalog(db_path=args.db)
    catalog.register_scenarios_bulk(scenarios)

    if args.distributed:
        from runner.distributed import run_suite_distributed
        results = run_suite_distributed(scenarios, workers=args.workers, timeout_s=args.timeout)
    else:
        runner = SimulationRunner(workers=args.workers, timeout_s=args.timeout)
        results = await runner.run_suite(scenarios)

    scorer = MetricsScorer()
    scenarios_by_id = {s.scenario_id: s for s in scenarios}
    # Build duration lookup once — avoids O(n²) linear scans below
    duration_by_id = {r.scenario_id: r.duration_s for r in results}
    report = scorer.score_suite(results, scenarios_by_id)

    run_records = [
        RunRecord(
            scenario_id=score.scenario_id,
            status="passed" if score.passed else "failed",
            duration_s=duration_by_id.get(score.scenario_id, 0.0),
            metrics=score.raw_metrics,
            violations=score.violations,
            weighted_score=score.weighted_score,
            model_version=args.model_version,
        )
        for score in report.scores
    ]
    catalog.record_runs_bulk(run_records)

    collision_count = sum(1 for s in report.scores if any("collision" in v for v in s.violations))
    exporter.update_suite_summary(
        pass_rate=report.pass_rate,
        collision_rate=collision_count / max(report.total, 1),
    )
    for score in report.scores:
        cat = scenarios_by_id.get(score.scenario_id)
        exporter.record_result(
            scenario_id=score.scenario_id,
            category=cat.category.value if cat else "unknown",
            passed=score.passed,
            duration_s=duration_by_id.get(score.scenario_id, 0.0),
            metrics=score.raw_metrics,
        )

    logger.info(
        "suite_complete",
        passed=report.passed,
        failed=report.failed,
        timeout=report.timeout,
        error=report.error,
        pass_rate=round(report.pass_rate * 100, 1),
    )

    # Reports
    if args.report:
        report.to_json(args.report)
        logger.info("json_report_written", path=str(args.report))

    if args.html_report:
        HTMLReporter().generate(report, args.html_report, suite_name=args.suite)
        logger.info("html_report_written", path=str(args.html_report))

    # Category trend from catalog
    rates = catalog.pass_rate_by_category(model_version=args.model_version)
    logger.info("category_pass_rates", rates=rates)

    return 0 if report.failed == 0 and report.error == 0 else 1


def run_replay(args: argparse.Namespace) -> int:
    log_paths = args.replay or []
    if not log_paths:
        logger.warning("no_replay_logs_provided")
        return 0

    exporter = SimMetricsExporter()
    runner = ReplayRegressionRunner(baseline_path=args.replay_baseline)
    results = runner.run(log_paths)  # scorer is internal now

    regressions = [r for r in results if r.regressed]
    for _ in regressions:
        exporter.record_regression("replay")

    logger.info("replay_complete", total=len(results), regressions=len(regressions))
    for r in regressions:
        logger.warning("regression_detected", log_id=r.log_id,
                       baseline=r.baseline_score, current=r.current_score)

    return 1 if regressions else 0


def main() -> int:
    args = parse_args()
    configure_logging(level=args.log_level)  # single call, after args parsed

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if args.replay:
        return run_replay(args)
    return asyncio.run(run_sim_suite(args))


if __name__ == "__main__":
    sys.exit(main())
