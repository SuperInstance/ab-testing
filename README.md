# ab-testing

Fleet-wide A/B testing — statistical experiment framework for agent behavior comparison.

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from ab_testing import Experiment, Variant, ExperimentReport
from ab_testing.assignment import StratifiedAssignment

# Define experiment
exp = Experiment("button-color", strategy=StratifiedAssignment())
exp.add_variant(Variant("green-button"))   # control
exp.add_variant(Variant("red-button"))     # treatment

# Assign subjects
for user_id in range(1000):
    exp.assign(f"user-{user_id}")

# Record results
exp.record_conversion("user-0", True)
exp.record_conversion("user-1", False)
# ... etc

# Generate report
report = ExperimentReport.from_experiment(exp)
print(report.to_text())
print(f"Winner: {report.winner}")
```

## Features

- **Variant assignment** — random, weighted, and stratified (hash-based) strategies
- **Binary & continuous metrics** — auto-detected or explicitly specified
- **Statistical tests** — chi-squared (proportions) and Welch's t-test (continuous), from scratch
- **Confidence intervals** — Wilson score (proportions) and t-distribution (means)
- **Experiment reports** — significance, effect size, winner recommendation
- **Zero external dependencies** — only pytest for testing

## API

### `Variant(name, weight=1.0)`

A single arm of an experiment. Tracks assignments and results.

### `Experiment(name, strategy=RandomAssignment())`

Orchestrates variants and assignment. Methods: `add_variant()`, `assign()`, `assign_batch()`, `record_result()`, `record_conversion()`.

### `AssignmentStrategy`

- `RandomAssignment(seed=None)` — uniform random
- `WeightedAssignment(seed=None)` — weighted by `Variant.weight`
- `StratifiedAssignment(salt="ab-testing")` — deterministic hash-based

### `ExperimentReport.from_experiment(experiment, metric_type="auto")`

Generates a full statistical analysis with variant summaries, pairwise comparisons, and a recommendation.

### Statistical tests

- `chi_squared_test(ctrl_successes, ctrl_total, tx_successes, tx_total)` → `ChiSquaredResult`
- `t_test(control, treatment)` → `TTestResult`
- `proportion_confidence_interval(successes, total, confidence=0.95)` → `ConfidenceInterval`
- `mean_confidence_interval(values, confidence=0.95)` → `ConfidenceInterval`

## Testing

```bash
python -m pytest tests/ -q
```

## License

MIT — Superinstance & Lucineer (DiGennaro et al.)
