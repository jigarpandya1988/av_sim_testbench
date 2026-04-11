# AV Sim Testbench

A scalable end-to-end simulation testing framework for Autonomous Vehicle (AV) software validation.

Designed to evaluate AV stack performance across thousands of synthetic and replay-based scenarios,
with automated analysis, CI/CD integration, and extensible infrastructure.

---

## Features

- **Scenario Generation** — Parameterized scenario builder for edge cases (cut-ins, pedestrians, adverse weather)
- **Simulation Runner** — Async batch execution engine with retry logic and timeout handling
- **Metrics & Scoring** — Collision rate, comfort score, TTC (time-to-collision), lane adherence
- **ML Regression Detection** — Baseline comparison to flag performance regressions across model versions
- **Replay Testing** — Run recorded real-world drives through the sim pipeline for regression validation
- **Scalable Infrastructure** — Docker-based workers, Bazel build system, Jenkins CI pipeline
- **Reporting** — JSON + HTML test reports with pass/fail per scenario category

---

## Project Structure

```
av_sim_testbench/
├── scenarios/          # Scenario definitions and generators
├── runner/             # Simulation execution engine
├── metrics/            # AV performance metrics and scoring
├── replay/             # Replay-based regression testing
├── ml/                 # ML model performance regression detection
├── infra/              # Docker, Bazel, Jenkins configs
├── tests/              # Unit and integration tests
├── reports/            # Output reports (gitignored)
└── main.py             # CLI entrypoint
```

---

## Quick Start

```bash
# Build with Bazel
bazel build //...

# Run with Docker
docker compose up --build

# Run all scenarios
python main.py --suite full

# Run a specific category
python main.py --suite highway --workers 8

# Run replay regression
python main.py --replay logs/drive_001.log
```

---

## CI/CD

Jenkins pipeline defined in `infra/Jenkinsfile` runs on every PR:
1. Lint + unit tests
2. Build Docker image
3. Run smoke scenario suite
4. Publish metrics report as artifact

---

## Tech Stack

- Python 3.11, C++ (metrics engine via pybind11)
- Bazel build system
- Docker + Docker Compose
- Jenkins declarative pipeline
- pytest, hypothesis (property-based testing)
