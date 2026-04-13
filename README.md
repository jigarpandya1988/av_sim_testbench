# AV Sim Testbench

[![CI](https://github.com/jigarpandya1988/av_sim_testbench/actions/workflows/ci.yml/badge.svg)](https://github.com/jigarpandya1988/av_sim_testbench/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

A production-grade, scalable end-to-end simulation testing framework for Autonomous Vehicle (AV) software validation.

Designed to evaluate AV stack performance across thousands of synthetic and replay-based scenarios with automated analysis, statistical regression detection, distributed execution, and full CI/CD integration.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AV Sim Testbench                             │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────────────────────────────┐  │
│  │  Scenario    │    │           Execution Layer                │  │
│  │  Generator   │───▶│  AsyncRunner (local)  │  Ray (cluster)  │  │
│  │  (combinat.) │    │  workers=N, retry,    │  horizontal      │  │
│  │  (fuzz)      │    │  timeout, backoff     │  scale-out       │  │
│  └──────────────┘    └──────────────┬───────────────────────────┘  │
│                                     │                               │
│  ┌──────────────┐    ┌──────────────▼───────────────────────────┐  │
│  │  C++ Metrics │    │           Scoring Layer                  │  │
│  │  Engine      │◀───│  MetricsScorer (ISO 21448 thresholds)    │  │
│  │  (pybind11)  │    │  TTC · Jerk · Lane Dev · Comfort Score   │  │
│  └──────────────┘    └──────────────┬───────────────────────────┘  │
│                                     │                               │
│  ┌──────────────┐    ┌──────────────▼───────────────────────────┐  │
│  │  Replay      │    │           Analysis Layer                 │  │
│  │  Regression  │    │  ML Regression (Welch t-test)            │  │
│  │  Runner      │    │  Replay Regression (baseline delta)      │  │
│  └──────────────┘    └──────────────┬───────────────────────────┘  │
│                                     │                               │
│  ┌──────────────┐    ┌──────────────▼───────────────────────────┐  │
│  │  Scenario    │    │           Persistence & Observability    │  │
│  │  Catalog     │◀───│  SQLite Catalog · Prometheus Metrics     │  │
│  │  (SQLite)    │    │  Structlog JSON · HTML Reports           │  │
│  └──────────────┘    └──────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    CI/CD Pipeline                           │   │
│  │  GitHub Actions (lint→test→smoke→docker)                   │   │
│  │  Jenkins (PR gate → artifact publish)                      │   │
│  │  Bazel (hermetic builds, per-module targets)               │   │
│  │  Docker (multi-stage, worker image)                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Details |
|---|---|
| 3D Simulation | **CARLA Simulator** integration for high-fidelity 3D validation |
| Scenario Generation | Combinatorial + fuzz (cut-in, pedestrian, weather, intersection) |
| Async Runner | Worker pool, per-scenario timeout, exponential backoff retry |
| Distributed Runner | Ray cluster scale-out, zero code change from local |
| C++ Metrics Engine | TTC, jerk, lane deviation, comfort score via pybind11 |
| ISO 21448 Scoring | Weighted composite score with hard-fail thresholds |
| Replay Regression | Baseline delta detection on real-world drive logs |
| ML Regression | Welch's t-test statistical significance across model versions |
| Scenario Catalog | SQLite persistence — trend analysis, flaky scenario detection |
| Observability | Prometheus counters/histograms, structlog JSON, Pushgateway |
| HTML Reports | Self-contained visual report, Jenkins artifact ready |
| CI/CD | GitHub Actions (multi-Python matrix) + Jenkins declarative pipeline |
| Build System | Bazel with per-module BUILD targets + CMake for C++ extension |
| Property Tests | Hypothesis fuzz testing of scorer, generator, and metrics bridge |

---

## Local CI Testing
To ensure your changes pass the GitHub CI pipeline, you can run the local CI script:

```bash
# On Windows
./check_ci.bat

# On Linux/macOS
python scripts/check_ci.py
```

This script runs linting, type checking, unit tests with coverage, and the smoke scenario suite.

## Build and Auto-Linting
To keep your code clean and ensure everything is built correctly:

```bash
# To automatically fix linting errors and format code
./lint.bat  (or python scripts/auto_lint.py)

# To run a full build (linting + tests + type checking)
./build.bat (or python scripts/build_project.py)
```

## CARLA 3D Simulation
The testbench now supports 3D visualization using the CARLA simulator.

1. **Install CARLA:** Download and install the [CARLA Simulator](https://carla.org/).
2. **Install Python Client:** `pip install carla`
3. **Start CARLA Server:** Run `CarlaUE4.exe` (Windows) or `./CarlaUE4.sh` (Linux).
4. **Run Testbench with CARLA:**
   ```bash
   python main.py --suite smoke --sim carla --workers 1
   ```
   *Note: Running multiple workers with CARLA requires a high-performance GPU.*

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Smoke suite (8 scenarios, fast)
python main.py --suite smoke --workers 4

# Full suite with JSON + HTML reports
python main.py --suite full --workers 8 \
    --report reports/latest.json \
    --html-report reports/latest.html

# Distributed (requires: pip install ray)
python main.py --suite full --distributed --workers 16

# Replay regression
python main.py --replay logs/drive_001.log \
    --replay-baseline baselines/baseline.json

# With Prometheus metrics endpoint
python main.py --suite full --metrics-port 8000
```

## Docker

```bash
# Build and run
docker compose -f infra/docker-compose.yml up --build

# Run tests in container
docker compose -f infra/docker-compose.yml run test
```

## Bazel

```bash
bazel build //...
bazel test //...
```

## C++ Extension (optional, for production performance)

```bash
pip install pybind11

# Linux / macOS
cd cpp && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --parallel
cp av_metrics_cpp*.so ../../       # Linux: .so  |  macOS: .dylib

# Windows (PowerShell)
cd cpp; mkdir build; cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release --parallel
Copy-Item av_metrics_cpp*.pyd ../..
```

> The Python bridge (`cpp/metrics_bridge.py`) falls back to pure Python automatically
> if the compiled extension is not present — no build required to run the framework.

---

## Project Structure

```
av_sim_testbench/
├── scenarios/          # Scenario definitions, schema, generator
├── runner/             # Async + Ray distributed execution engine
├── metrics/            # ISO 21448-aligned scoring and reporting
├── replay/             # Replay-based regression testing
├── ml/                 # ML model regression detection (Welch t-test)
├── catalog/            # SQLite scenario catalog and run history
├── observability/      # Prometheus exporter + structlog JSON logging
├── reports/            # HTML report generator (Jinja2)
├── cpp/                # C++ metrics engine (pybind11 + CMake + Bazel)
├── infra/              # Dockerfile, docker-compose, Jenkinsfile
├── tests/              # pytest unit + Hypothesis property-based tests
├── .github/workflows/  # GitHub Actions CI pipeline
├── BUILD               # Root Bazel build target
├── WORKSPACE           # Bazel workspace + Python rules
└── pyproject.toml      # Package config, ruff, mypy, pytest settings
```

---

## Plugging in a Real Simulator

The mock adapter in `runner/engine.py` is a drop-in replacement point for any sim SDK:

```python
from runner.engine import SimulationRunner

def nvidia_drive_sim_adapter(scenario):
    # Call NVIDIA DRIVE Sim / CARLA / LGSVL SDK
    result = sdk.run_scenario(scenario.scenario_id, ...)
    return {"collision_count": result.collisions, "min_ttc_s": result.ttc, ...}

runner = SimulationRunner(sim_adapter=nvidia_drive_sim_adapter, workers=32)
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
