# Contributing to AV Sim Testbench

## Development Setup

```bash
git clone https://github.com/jigarpandya1988/av_sim_testbench
cd av_sim_testbench
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html

# Property-based tests only
pytest tests/test_properties.py -v

# Single module
pytest tests/test_metrics_scoring.py -v
```

## Code Style

We use `ruff` for linting and formatting:

```bash
ruff check .          # lint
ruff check . --fix    # auto-fix
```

Type checking with `mypy`:

```bash
mypy . --ignore-missing-imports
```

## Adding a New Scenario Category

1. Add the category to `scenarios/schema.py` → `ScenarioCategory`
2. Add a generator method to `scenarios/generator.py`
3. Add it to `full_suite()` in the same file
4. Add a test in `tests/test_scenario_generator.py`

## Adding a New Metric

1. Add threshold to `metrics/scoring.py` → `THRESHOLDS`
2. Add hard-fail check in `MetricsScorer._score_result()`
3. Add weight in `MetricsScorer._WEIGHTS` (ensure weights sum to 1.0)
4. Add C++ implementation in `cpp/metrics_engine.cpp` + Python bridge in `cpp/metrics_bridge.py`
5. Update `tests/test_metrics_scoring.py`

## Plugging in a Real Simulator

Replace the mock adapter in `runner/engine.py`:

```python
def my_sim_adapter(scenario: Scenario) -> dict:
    # Call CARLA / LGSVL / NVIDIA DRIVE Sim SDK here
    result = my_sdk.run(scenario.scenario_id, scenario.map_id, ...)
    return {
        "collision_count": result.collisions,
        "min_ttc_s": result.min_ttc,
        ...
    }

runner = SimulationRunner(sim_adapter=my_sim_adapter, workers=16)
```

## Pull Request Checklist

- [ ] Tests pass: `pytest tests/ -v`
- [ ] No lint errors: `ruff check .`
- [ ] New features have tests
- [ ] Docstrings updated
- [ ] CHANGELOG entry added (if user-facing change)

## Branch Strategy

- `master` — stable, CI-gated
- `feature/<name>` — feature branches, PR into master
- `release/<version>` — release prep branches
