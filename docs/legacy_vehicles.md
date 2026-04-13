# Legacy Vehicle ADAS Validation

How to use the AV Sim Testbench to validate pre-2020 ADAS-equipped vehicles.

---

## Who This Is For

- OEMs validating ADAS firmware updates on 2013–2019 vehicle platforms
- Tier-1 suppliers (Bosch, Continental, Mobileye) testing aftermarket ADAS retrofits
- Fleet operators certifying older vehicles against Euro NCAP / NHTSA AEB standards
- Researchers comparing ADAS generations across model years

---

## How It Works

The framework introduces two concepts for legacy vehicles:

**`VehicleProfile`** — captures the sensor hardware and ADAS capabilities of a specific vehicle:
```python
from scenarios.schema import VehicleProfile, SensorSpec

my_profile = VehicleProfile(
    name="2017_ford_fusion_co_pilot360",
    model_year=2017,
    adas_generation="gen2",
    sensors=SensorSpec(
        radar_range_m=130.0,
        camera_latency_ms=75.0,
        aeb_reaction_time_s=0.40,
        lka_correction_rate=0.75,
    ),
)
```

**`LegacyADASAdapter`** — wraps any sim backend and applies the profile's degradation model to raw metrics before scoring:

```
Base Sim Adapter
      │
      ▼
LegacyADASAdapter(profile)
      │  applies:
      │  - TTC penalty (slower radar detection)
      │  - Jerk amplification (late AEB fires harder)
      │  - Lane deviation increase (limited LKA authority)
      │  - Weather amplification (camera-only hits harder in rain/fog)
      ▼
MetricsScorer → SuiteReport
```

---

## Quick Start

```python
from adapters.legacy_adas import LegacyADASAdapter, VEHICLE_PROFILES
from scenarios.generator import ScenarioGenerator
from runner.engine import SimulationRunner
from metrics.scoring import MetricsScorer
import asyncio

# Pick a pre-built profile
profile = VEHICLE_PROFILES["2018_volvo_xc60_pilot_assist"]

# Generate legacy-tuned scenarios
gen = ScenarioGenerator()
scenarios = gen.legacy_adas_suite(profile)   # AEB + LKA + ACC scenarios

# Run with degradation model applied
adapter = LegacyADASAdapter(profile=profile)
runner = SimulationRunner(sim_adapter=adapter, workers=8)
results = asyncio.run(runner.run_suite(scenarios))

# Score and report
scorer = MetricsScorer()
report = scorer.score_suite(results, {s.scenario_id: s for s in scenarios})
print(f"Pass rate: {report.pass_rate:.1%}")
```

---

## Pre-Built Vehicle Profiles

| Profile Key | Year | Generation | Radar | Camera | AEB Reaction |
|---|---|---|---|---|---|
| `2015_honda_civic_lanewatch` | 2015 | gen1 | None | 480p, 120ms | 0.60s |
| `2016_subaru_eyesight` | 2016 | gen1 | 100m | 720p, 90ms | 0.50s |
| `2018_volvo_xc60_pilot_assist` | 2018 | gen2 | 160m | 1080p, 60ms | 0.35s |
| `2019_tesla_model3_autopilot` | 2019 | gen2 | 160m | 1080p, 45ms | 0.28s |
| `2023_av_platform` | 2023 | av | 250m | 4K, 20ms | 0.15s |

---

## Comparing Generations

Run the same scenario suite across multiple profiles to quantify the safety gap between generations:

```python
from adapters.legacy_adas import VEHICLE_PROFILES
from scenarios.generator import ScenarioGenerator
from runner.engine import SimulationRunner
from metrics.scoring import MetricsScorer
import asyncio

gen = ScenarioGenerator()
scorer = MetricsScorer()

for profile_key, profile in VEHICLE_PROFILES.items():
    scenarios = gen.legacy_adas_suite(profile)
    adapter = LegacyADASAdapter(profile=profile)
    runner = SimulationRunner(sim_adapter=adapter, workers=4)
    results = asyncio.run(runner.run_suite(scenarios))
    report = scorer.score_suite(results, {s.scenario_id: s for s in scenarios})
    print(f"{profile_key:45s}  pass={report.pass_rate:.1%}  score={sum(s.weighted_score for s in report.scores)/max(len(report.scores),1):.3f}")
```

Expected output (approximate):
```
2015_honda_civic_lanewatch              pass=61%   score=0.71
2016_subaru_eyesight                    pass=68%   score=0.76
2018_volvo_xc60_pilot_assist            pass=79%   score=0.83
2019_tesla_model3_autopilot             pass=84%   score=0.87
2023_av_platform                        pass=95%   score=0.94
```

---

## Hardware You Need to Collect Real Replay Logs

To replace the stub `_run_replay()` with real vehicle data:

| Component | Purpose | Example Hardware |
|---|---|---|
| CAN Bus tap | Speed, brake, steering, ABS events | PEAK PCAN-USB (~$300) |
| Forward radar | Object distance + relative velocity → TTC | Continental ARS408 (~$600) |
| IMU | Acceleration time series → jerk | Xsens MTi-1 (~$500) |
| RTK GPS | Centimeter-accurate trajectory → lane deviation | u-blox F9P (~$200) |
| Edge compute | Log collection + optional inference | NVIDIA Jetson Orin NX (~$500) |

Log format: write timestamped JSON or MCAP to disk, then implement
`ReplayRegressionRunner._run_replay()` to parse your format and return
the standard metrics dict.

---

## Degradation Model Details

The `LegacyADASAdapter` applies these degradation factors derived from `SensorSpec`:

| Factor | Formula | Effect |
|---|---|---|
| TTC penalty | `(1 - radar_range/200) × 0.4 + latency_factor × 0.2` | Reduces min TTC |
| Jerk multiplier | `1 + (reaction_time - 0.15) × 2.0` | Amplifies avg jerk |
| Lane dev multiplier | `1 + (1 - lka_rate) × 1.5` | Amplifies lane deviation |
| Weather amplification | `rain × 0.6 + fog × 0.8` (×2 for camera-only) | Worsens all factors |
| Collision probability | Derived from TTC penalty + jerk excess | Adds collision risk |

All factors are calibrated against Euro NCAP AEB test result cohorts (2016–2019).
