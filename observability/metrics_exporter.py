"""
Prometheus metrics exporter for the AV simulation testbench.

Exposes counters, gauges, and histograms that can be scraped
by a Prometheus server or pushed to a Pushgateway in CI.

Metrics naming follows Prometheus best practices:
  av_sim_<subsystem>_<metric>_<unit>
"""

from __future__ import annotations

try:
    from prometheus_client import (
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        push_to_gateway,
        start_http_server,
    )

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False


class SimMetricsExporter:
    """
    Prometheus instrumentation for simulation runs.

    Usage:
        exporter = SimMetricsExporter()
        exporter.start_server(port=8000)   # optional scrape endpoint

        with exporter.scenario_timer(scenario_id, category):
            # run scenario
            pass
        exporter.record_result(scenario_id, category, passed=True, metrics={...})
    """

    def __init__(self, registry=None, namespace: str = "av_sim") -> None:
        if not _PROM_AVAILABLE:
            self._enabled = False
            return
        self._enabled = True
        reg = registry or REGISTRY
        ns = namespace

        self.scenarios_total = Counter(
            f"{ns}_scenarios_total",
            "Total scenarios executed",
            ["category", "status"],
            registry=reg,
        )
        self.scenario_duration = Histogram(
            f"{ns}_scenario_duration_seconds",
            "Scenario execution wall-clock time",
            ["category"],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
            registry=reg,
        )
        self.pass_rate = Gauge(
            f"{ns}_pass_rate",
            "Rolling pass rate across last suite run",
            registry=reg,
        )
        self.collision_rate = Gauge(
            f"{ns}_collision_rate",
            "Fraction of scenarios with at least one collision",
            registry=reg,
        )
        self.min_ttc_seconds = Histogram(
            f"{ns}_min_ttc_seconds",
            "Minimum time-to-collision per scenario",
            ["category"],
            buckets=[0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0],
            registry=reg,
        )
        self.avg_jerk = Histogram(
            f"{ns}_avg_jerk_mps3",
            "Average jerk per scenario (m/s³)",
            ["category"],
            buckets=[0.0, 0.5, 1.0, 2.0, 3.0, 5.0],
            registry=reg,
        )
        self.regression_events = Counter(
            f"{ns}_regression_events_total",
            "ML or replay regression events detected",
            ["type"],
            registry=reg,
        )
        self.worker_utilization = Gauge(
            f"{ns}_worker_utilization_ratio",
            "Fraction of workers currently busy",
            registry=reg,
        )

    def record_result(
        self,
        scenario_id: str,
        category: str,
        passed: bool,
        duration_s: float,
        metrics: dict,
    ) -> None:
        if not self._enabled:
            return
        status = "passed" if passed else "failed"
        self.scenarios_total.labels(category=category, status=status).inc()
        self.scenario_duration.labels(category=category).observe(duration_s)

        if "min_ttc_s" in metrics:
            self.min_ttc_seconds.labels(category=category).observe(metrics["min_ttc_s"])
        if "avg_jerk_mps3" in metrics:
            self.avg_jerk.labels(category=category).observe(metrics["avg_jerk_mps3"])

    def update_suite_summary(self, pass_rate: float, collision_rate: float) -> None:
        if not self._enabled:
            return
        self.pass_rate.set(pass_rate)
        self.collision_rate.set(collision_rate)

    def record_regression(self, regression_type: str) -> None:
        if not self._enabled:
            return
        self.regression_events.labels(type=regression_type).inc()

    def set_worker_utilization(self, active: int, total: int) -> None:
        if not self._enabled:
            return
        self.worker_utilization.set(active / max(total, 1))

    def start_server(self, port: int = 8000) -> None:
        """Start Prometheus HTTP scrape endpoint."""
        if not self._enabled:
            return
        start_http_server(port)

    def push(self, gateway: str, job: str = "av_sim_testbench") -> None:
        """Push metrics to a Prometheus Pushgateway (for CI use)."""
        if not self._enabled:
            return
        push_to_gateway(gateway, job=job, registry=REGISTRY)
