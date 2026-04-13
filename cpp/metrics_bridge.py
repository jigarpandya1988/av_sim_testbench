"""
Python bridge for the C++ metrics engine.

Falls back to pure-Python implementations when the compiled
extension is not available (e.g., CI without build toolchain).
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

try:
    import av_metrics_cpp as _cpp  # type: ignore[import]

    _CPP_AVAILABLE = True
    logger.info("C++ metrics engine loaded (av_metrics_cpp)")
except ImportError:
    _CPP_AVAILABLE = False
    logger.warning("C++ metrics engine not available — using Python fallback")


def compute_min_ttc(
    ego_positions: list[tuple[float, float]],
    npc_positions: list[tuple[float, float]],
    ego_speeds: list[float],
    npc_speeds: list[float],
    dt: float,
    safety_radius_m: float = 2.5,
) -> float:
    if _CPP_AVAILABLE:
        return _cpp.compute_min_ttc(
            ego_positions, npc_positions, ego_speeds, npc_speeds, dt, safety_radius_m
        )
    return _py_min_ttc(ego_positions, npc_positions, ego_speeds, npc_speeds, safety_radius_m)


def compute_jerk_stats(accelerations: list[float], dt: float) -> tuple[float, float]:
    if _CPP_AVAILABLE:
        return _cpp.compute_jerk_stats(accelerations, dt)
    return _py_jerk_stats(accelerations, dt)


def compute_lane_deviation_rms(lateral_errors: list[float]) -> float:
    if _CPP_AVAILABLE:
        return _cpp.compute_lane_deviation_rms(lateral_errors)
    return _py_lane_dev_rms(lateral_errors)


def compute_comfort_score(
    avg_jerk_mps3: float,
    lane_deviation_rms: float,
    max_jerk_threshold: float = 5.0,
    max_dev_threshold: float = 1.0,
) -> float:
    if _CPP_AVAILABLE:
        return _cpp.compute_comfort_score(
            avg_jerk_mps3, lane_deviation_rms, max_jerk_threshold, max_dev_threshold
        )
    jerk_score = max(0.0, 1.0 - avg_jerk_mps3 / max_jerk_threshold)
    dev_score = max(0.0, 1.0 - lane_deviation_rms / max_dev_threshold)
    return 0.6 * jerk_score + 0.4 * dev_score


# ---------------------------------------------------------------------------
# Pure-Python fallbacks
# ---------------------------------------------------------------------------


def _py_min_ttc(ego_pos, npc_pos, ego_speeds, npc_speeds, radius):
    min_ttc = 999.0
    for i, (ep, np_) in enumerate(zip(ego_pos, npc_pos, strict=True)):
        dx, dy = np_[0] - ep[0], np_[1] - ep[1]
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < radius:
            return 0.0
        rel_speed = ego_speeds[i] - npc_speeds[i]
        if rel_speed > 0.01:
            ttc = (dist - radius) / rel_speed
            min_ttc = min(min_ttc, ttc)
    return min_ttc


def _py_jerk_stats(accs, dt):
    if len(accs) < 2:
        return 0.0, 0.0
    jerks = [abs(accs[i] - accs[i - 1]) / dt for i in range(1, len(accs))]
    return sum(jerks) / len(jerks), max(jerks)


def _py_lane_dev_rms(errors):
    if not errors:
        return 0.0
    return math.sqrt(sum(e * e for e in errors) / len(errors))
