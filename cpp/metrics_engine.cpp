/**
 * AV Metrics Engine — C++ core via pybind11
 *
 * High-performance computation of safety-critical AV metrics:
 *   - Time-To-Collision (TTC)
 *   - Jerk (rate of acceleration change)
 *   - Lane deviation RMS
 *   - Comfort score
 *
 * Exposed to Python via pybind11. Replace asyncio-thread adapter
 * with direct calls to this module for latency-sensitive pipelines.
 */
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <stdexcept>
#include <numeric>
#include <algorithm>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Time-To-Collision
// ---------------------------------------------------------------------------

/**
 * Compute minimum TTC over a trajectory.
 *
 * @param ego_positions    [{x, y}] ego vehicle positions over time
 * @param npc_positions    [{x, y}] NPC vehicle positions over time
 * @param ego_speeds       ego speed at each timestep (m/s)
 * @param npc_speeds       NPC speed at each timestep (m/s)
 * @param dt               timestep duration (s)
 * @param safety_radius_m  collision radius (m)
 * @return minimum TTC in seconds (capped at 999.0 if no collision risk)
 */
double compute_min_ttc(
    const std::vector<std::pair<double,double>>& ego_positions,
    const std::vector<std::pair<double,double>>& npc_positions,
    const std::vector<double>& ego_speeds,
    const std::vector<double>& npc_speeds,
    double dt,
    double safety_radius_m = 2.5
) {
    if (ego_positions.size() != npc_positions.size()) {
        throw std::invalid_argument("ego and npc position vectors must be same length");
    }

    double min_ttc = 999.0;
    size_t n = ego_positions.size();

    for (size_t i = 0; i < n; ++i) {
        double dx = npc_positions[i].first  - ego_positions[i].first;
        double dy = npc_positions[i].second - ego_positions[i].second;
        double dist = std::sqrt(dx*dx + dy*dy);

        if (dist < safety_radius_m) {
            // Already in collision zone
            min_ttc = 0.0;
            break;
        }

        double rel_speed = ego_speeds[i] - npc_speeds[i];
        if (rel_speed > 0.01) {
            double ttc = (dist - safety_radius_m) / rel_speed;
            min_ttc = std::min(min_ttc, ttc);
        }
    }
    return min_ttc;
}

// ---------------------------------------------------------------------------
// Jerk computation
// ---------------------------------------------------------------------------

/**
 * Compute average and peak jerk from an acceleration time series.
 *
 * @param accelerations  acceleration values (m/s²) at each timestep
 * @param dt             timestep duration (s)
 * @return {avg_jerk, peak_jerk} in m/s³
 */
std::pair<double, double> compute_jerk_stats(
    const std::vector<double>& accelerations,
    double dt
) {
    if (accelerations.size() < 2) {
        return {0.0, 0.0};
    }

    std::vector<double> jerks;
    jerks.reserve(accelerations.size() - 1);

    for (size_t i = 1; i < accelerations.size(); ++i) {
        jerks.push_back(std::abs(accelerations[i] - accelerations[i-1]) / dt);
    }

    double avg = std::accumulate(jerks.begin(), jerks.end(), 0.0) / jerks.size();
    double peak = *std::max_element(jerks.begin(), jerks.end());

    return {avg, peak};
}

// ---------------------------------------------------------------------------
// Lane deviation RMS
// ---------------------------------------------------------------------------

/**
 * Compute RMS lateral deviation from lane centerline.
 *
 * @param lateral_errors  signed lateral error at each timestep (m)
 * @return RMS deviation in meters
 */
double compute_lane_deviation_rms(const std::vector<double>& lateral_errors) {
    if (lateral_errors.empty()) return 0.0;

    double sum_sq = 0.0;
    for (double e : lateral_errors) {
        sum_sq += e * e;
    }
    return std::sqrt(sum_sq / lateral_errors.size());
}

// ---------------------------------------------------------------------------
// Composite comfort score  [0.0 = worst, 1.0 = perfect]
// ---------------------------------------------------------------------------

/**
 * Compute a composite comfort score from jerk and lateral deviation.
 *
 * Aligned with ISO 2631-1 vibration comfort guidelines.
 *
 * @param avg_jerk_mps3       average jerk (m/s³)
 * @param lane_deviation_rms  RMS lane deviation (m)
 * @param max_jerk_threshold  jerk above which score = 0 (default 5.0 m/s³)
 * @param max_dev_threshold   deviation above which score = 0 (default 1.0 m)
 * @return comfort score in [0.0, 1.0]
 */
double compute_comfort_score(
    double avg_jerk_mps3,
    double lane_deviation_rms,
    double max_jerk_threshold = 5.0,
    double max_dev_threshold = 1.0
) {
    double jerk_score = std::max(0.0, 1.0 - avg_jerk_mps3 / max_jerk_threshold);
    double dev_score  = std::max(0.0, 1.0 - lane_deviation_rms / max_dev_threshold);
    // Weighted: jerk 60%, lateral 40%
    return 0.6 * jerk_score + 0.4 * dev_score;
}

// ---------------------------------------------------------------------------
// pybind11 module
// ---------------------------------------------------------------------------

PYBIND11_MODULE(av_metrics_cpp, m) {
    m.doc() = "AV safety metrics engine — C++ core (pybind11)";

    m.def("compute_min_ttc", &compute_min_ttc,
        py::arg("ego_positions"),
        py::arg("npc_positions"),
        py::arg("ego_speeds"),
        py::arg("npc_speeds"),
        py::arg("dt"),
        py::arg("safety_radius_m") = 2.5,
        R"doc(
Compute minimum Time-To-Collision over a trajectory.

Args:
    ego_positions: List of (x, y) tuples for ego vehicle.
    npc_positions: List of (x, y) tuples for NPC vehicle.
    ego_speeds: Ego speed at each timestep (m/s).
    npc_speeds: NPC speed at each timestep (m/s).
    dt: Timestep duration (s).
    safety_radius_m: Collision radius (m). Default 2.5.

Returns:
    Minimum TTC in seconds (999.0 if no collision risk detected).
        )doc"
    );

    m.def("compute_jerk_stats", &compute_jerk_stats,
        py::arg("accelerations"),
        py::arg("dt"),
        R"doc(
Compute average and peak jerk from acceleration time series.

Returns:
    Tuple of (avg_jerk_mps3, peak_jerk_mps3).
        )doc"
    );

    m.def("compute_lane_deviation_rms", &compute_lane_deviation_rms,
        py::arg("lateral_errors"),
        "Compute RMS lateral deviation from lane centerline (meters)."
    );

    m.def("compute_comfort_score", &compute_comfort_score,
        py::arg("avg_jerk_mps3"),
        py::arg("lane_deviation_rms"),
        py::arg("max_jerk_threshold") = 5.0,
        py::arg("max_dev_threshold") = 1.0,
        "Compute composite comfort score [0.0-1.0] per ISO 2631-1."
    );
}
