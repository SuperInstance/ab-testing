# ab-testing

**Fleet-wide A/B testing** — statistical experiment framework for comparing agent behaviors with variant assignment, significance testing, and experiment reports.

## What This Gives You

- **Variant assignment** — random, weighted, and stratified (hash-based) strategies
- **Binary & continuous metrics** — auto-detected or explicitly specified
- **Statistical tests** — chi-squared (proportions) and Welch's t-test (continuous)
- **Confidence intervals** — Wilson score (proportions) and t-distribution (means)
- **Experiment reports** — significance, effect size, winner recommendation
- **Zero external dependencies** — only pytest for testing

## Installation

```bash
pip install ab-testing
```

## Quick Start

```python
from ab_testing import Experiment, Variant, ExperimentReport
from ab_testing.assignment import StratifiedAssignment

exp = Experiment("button-color", strategy=StratifiedAssignment())
exp.add_variant(Variant("green-button"))  # control
exp.add_variant(Variant("red-button"))    # treatment

for user_id in range(1000):
    exp.assign(f"user-{user_id}")

exp.record_conversion("user-0", True)
exp.record_conversion("user-1", False)

report = ExperimentReport.from_experiment(exp)
print(f"Winner: {report.winner}")
```

## Testing

```bash
pip install -e ".[test]"
pytest
```

## How It Fits

Experimentation layer for the SuperInstance agent fleet. Test agent configurations via `plato-training`, measure impact via `quality-gate-stream`, and deploy winners via `plato-fleet`.

## License

MIT
