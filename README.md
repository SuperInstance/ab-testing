# ab-testing

**A zero-dependency statistical A/B testing framework in pure Python.**

Run controlled experiments with variant assignment, significance testing, confidence intervals, and automated winner selection — all without reaching for SciPy, NumPy, or any external statistical library.

---

## What This Does

`ab-testing` gives you a complete A/B testing pipeline:

1. **Define variants** (control + one or more treatments)
2. **Assign subjects** using random, weighted, or deterministic hash-based strategies
3. **Record results** — binary conversions (clicked / didn't click) or continuous metrics (page load time in ms)
4. **Generate a report** with statistical significance tests, confidence intervals, effect sizes, and a winner recommendation

Everything is implemented from scratch: chi-squared CDF via the regularised incomplete gamma function, Welch's t-test via the regularised incomplete beta function, Wilson-score confidence intervals for proportions, Cornish-Fisher corrected critical values for small-sample t-intervals. No NumPy. No SciPy. Just Python's `math` module.

---

## Key Idea

Most A/B testing libraries are thin wrappers around SciPy. This one isn't. Every statistical function — the normal CDF (Abramowitz & Stegun approximation 26.2.17), the incomplete gamma function (series expansion), the incomplete beta function (Lentz continued-fraction method), chi-squared p-values, t-distribution p-values, Wilson-score intervals — is implemented from first principles.

This makes the library:
- **Auditable**: you can read and verify every mathematical step
- **Portable**: runs anywhere Python 3.10+ does, no compiled extensions
- **Educational**: each function is a clean reference implementation

---

## Installation

```bash
pip install ab-testing
```

Or install from source:

```bash
git clone https://github.com/SuperInstance/ab-testing.git
cd ab-testing
pip install -e ".[test]"
```

Requires **Python ≥ 3.10**. No runtime dependencies.

---

## Quick Start

### Binary metric (conversion rate)

```python
from ab_testing import Experiment, Variant, ExperimentReport
from ab_testing.assignment import StratifiedAssignment

# 1. Set up the experiment
exp = Experiment("button-color", strategy=StratifiedAssignment())
exp.add_variant(Variant("green-button"))   # control (first variant)
exp.add_variant(Variant("red-button"))     # treatment

# 2. Assign subjects
for user_id in range(1000):
    exp.assign(f"user-{user_id}")

# 3. Record conversions
import random
rng = random.Random(42)
for user_id in range(1000):
    variant = exp.get_assignment(f"user-{user_id}")
    if variant.name == "green-button":
        exp.record_conversion(f"user-{user_id}", rng.random() < 0.20)
    else:
        exp.record_conversion(f"user-{user_id}", rng.random() < 0.30)

# 4. Analyze
report = ExperimentReport.from_experiment(exp)
print(report.to_text())
print(f"\nWinner: {report.winner}")
```

### Continuous metric (e.g., page load time)

```python
from ab_testing import Experiment, Variant, ExperimentReport
from ab_testing.assignment import WeightedAssignment

exp = Experiment("page-load", strategy=WeightedAssignment(seed=42))
exp.add_variant(Variant("baseline", weight=70))
exp.add_variant(Variant("optimized", weight=30))

for user_id in range(1000):
    exp.assign(f"user-{user_id}")

# Record continuous values (auto-detected as non-binary)
for sid in exp.get_variant("baseline").subject_ids:
    exp.record_result(sid, rng.gauss(500, 50))
for sid in exp.get_variant("optimized").subject_ids:
    exp.record_result(sid, rng.gauss(480, 50))

report = ExperimentReport.from_experiment(exp)  # metric_type="auto" detects continuous
print(report.to_text())
```

---

## API Reference

### `Variant`

A single arm of an experiment (control or treatment).

```python
v = Variant("control", weight=1.0, metadata={"color": "blue"})
v.assign("user-1")              # assign a subject
v.record_result("user-1", 42.0) # record a numeric result
v.record_conversion("user-1", True)  # or a binary conversion
```

| Property / Method | Description |
|---|---|
| `name` | Human-readable identifier |
| `weight` | Relative weight for traffic splitting (default `1.0`) |
| `metadata` | Arbitrary dict of extra info |
| `assign(subject_id)` | Record assignment; raises `ValueError` on duplicate |
| `record_result(subject_id, value)` | Record a numeric result |
| `record_conversion(subject_id, bool)` | Record a binary result (convenience: `float(converted)`) |
| `results` → `list[float]` | All recorded results in assignment order |
| `mean`, `conversion_rate` | Sample mean / proportion of 1s |
| `variance`, `std_dev` | Bessel-corrected sample variance and std dev |
| `assignment_count`, `result_count` | Counts |
| `subject_ids` → `list[str]` | All assigned subject IDs |

### Assignment Strategies

All strategies implement `AssignmentStrategy.assign(subject_id, variants) → Variant`.

| Strategy | Behavior |
|---|---|
| `RandomAssignment(seed=None)` | Uniform random choice; seedable for reproducibility |
| `WeightedAssignment(seed=None)` | Weighted random proportional to `Variant.weight` |
| `StratifiedAssignment(salt="ab-testing")` | Deterministic SHA-256 hash-based bucketing; same subject always gets same variant |

### `Experiment`

Orchestrates variants and assignment.

```python
exp = Experiment("my-test", strategy=StratifiedAssignment())
exp.add_variant(Variant("control"))
exp.add_variant(Variant("treatment-v2"))

v = exp.assign("user-1")           # assign subject; idempotent
exp.assign_batch(["u1", "u2", "u3"])  # batch assign
exp.record_result("user-1", 3.14) # auto-routes to correct variant
exp.record_conversion("user-1", True)
exp.stop()                         # freeze: no more assignments

exp.control       # first variant
exp.treatments    # all except first
exp.total_assigned
exp.is_running
```

### `ExperimentReport`

Generates statistical analysis from a live experiment.

```python
report = ExperimentReport.from_experiment(
    exp,
    metric_type="auto",   # "binary", "continuous", or "auto" (detect from data)
    alpha=0.05,           # significance level
    confidence=0.95,      # confidence level for intervals
)

report.summaries       # list[VariantSummary] — per-variant stats
report.comparisons     # list[ComparisonResult] — each treatment vs control
report.winner          # name of winning variant (or None)
report.recommendation  # human-readable recommendation string
report.to_text()       # formatted text report
```

**`VariantSummary`**: `name`, `assignment_count`, `result_count`, `mean`, `std_dev`, `conversion_rate`, `confidence_interval`

**`ComparisonResult`**: `control_name`, `treatment_name`, `test` (ChiSquaredResult or TTestResult), `effect_size`

### Statistical Functions

Direct access to the raw tests (no experiment object needed):

```python
from ab_testing import chi_squared_test, t_test
from ab_testing import proportion_confidence_interval, mean_confidence_interval

# Chi-squared test for two proportions
result = chi_squared_test(control_successes=10, control_total=100,
                          treatment_successes=30, treatment_total=100)
# → ChiSquaredResult(chi2=11.38, p=0.000741, df=1, significant=True)

# Welch's t-test for continuous metrics
result = t_test(control=[1.0]*50, treatment=[3.0]*50)
# → TTestResult(t=inf, p=0.000000, df=98.0, significant=True)

# Wilson-score CI for a proportion
ci = proportion_confidence_interval(successes=50, total=100, confidence=0.95)
# → CI([0.4038, 0.5962], confidence=95%)

# t-distribution CI for a mean
ci = mean_confidence_interval([1, 2, 3, 4, 5], confidence=0.95)
# → CI([1.44, 4.56], confidence=95%)
```

---

## How It Works

### Architecture

```
                    ┌─────────────┐
  subject_id ──────►│  Experiment  │
                    │  (orchestr)  │
                    └──────┬───────┘
                           │ uses
                    ┌──────▼───────┐
                    │  Assignment   │
                    │  Strategy     │  ← Random / Weighted / Stratified
                    └──────┬───────┘
                           │ picks
                    ┌──────▼───────┐
                    │   Variant    │  ← stores subjects + results
                    │   (arm)      │
                    └──────┬───────┘
                           │ feeds into
                    ┌──────▼───────┐
                    │   Stats      │  ← chi-squared / Welch's t / CIs
                    │  (from       │
                    │   scratch)   │
                    └──────┬───────┘
                           │ produces
                    ┌──────▼───────┐
                    │  Experiment  │
                    │  Report      │  ← summaries, comparisons, winner
                    └──────────────┘
```

### Assignment Flow

1. You call `exp.assign("user-42")`.
2. The `AssignmentStrategy` picks a `Variant`.
3. The subject is recorded in both the variant and the experiment's master map.
4. Re-assigning the same subject is idempotent — returns the same variant.

### Metric Detection

`ExperimentReport.from_experiment(metric_type="auto")` checks all recorded results. If every value is `0.0` or `1.0`, it treats the metric as binary and runs a **chi-squared test**. Otherwise it treats it as continuous and runs **Welch's t-test**.

### Winner Selection

1. Each treatment is compared to the control (first variant).
2. Only comparisons where `p < alpha` (default 0.05) are considered.
3. Among significant results, the one with the largest positive effect size wins.
4. If no comparison is significant, the report recommends continuing the experiment.

---

## The Math

### Chi-Squared Test (Yates-Corrected)

For two proportions $p_1$ (control) and $p_2$ (treatment), construct a 2×2 contingency table:

| | Success | Failure |
|---|---|---|
| Control | a | b |
| Treatment | c | d |

$$\chi^2 = \frac{n(|ad - bc| - n/2)^2}{(a+b)(c+d)(a+c)(b+d)}$$

where $n = a + b + c + d$. The $-n/2$ term is **Yates' continuity correction** for 2×2 tables.

The p-value is $1 - P(k/2, \chi^2/2)$ where $P$ is the regularised lower incomplete gamma function, computed via series expansion:

$$P(s, x) = \frac{x^s e^{-x}}{\Gamma(s)} \sum_{n=0}^{\infty} \frac{x^n}{\prod_{k=0}^{n}(s+k)}$$

The gamma function $\Gamma(s)$ itself uses the **Lanczos approximation** (9 coefficients, $g=7$).

### Welch's t-Test

For two independent samples with possibly unequal variances:

$$t = \frac{\bar{X}_2 - \bar{X}_1}{\sqrt{s_1^2/n_1 + s_2^2/n_2}}$$

with **Welch–Satterthwaite** degrees of freedom:

$$\nu = \frac{(s_1^2/n_1 + s_2^2/n_2)^2}{(s_1^2/n_1)^2/(n_1-1) + (s_2^2/n_2)^2/(n_2-1)}$$

The two-tailed p-value uses the regularised **incomplete beta function** $I_x(a, b)$:

$$p = I_{\nu/(\nu + t^2)}\!\left(\frac{\nu}{2},\, \frac{1}{2}\right)$$

computed via **Lentz's continued-fraction method** (up to 100 iterations, convergence at $|\delta - 1| < 10^{-10}$).

For large $\nu > 30$, the t-distribution is approximated by the standard normal, using the CDF from Abramowitz & Stegun approximation 26.2.17 (max error $< 1.5 \times 10^{-7}$).

### Wilson-Score Confidence Interval (Proportions)

For a sample proportion $\hat{p} = k/n$ at confidence level $1-\alpha$:

$$\text{centre} = \frac{\hat{p} + z^2/(2n)}{1 + z^2/n}, \qquad \text{spread} = \frac{z\sqrt{\hat{p}(1-\hat{p})/n + z^2/(4n^2)}}{1 + z^2/n}$$

where $z = \Phi^{-1}(1 - \alpha/2)$ is found by binary search over the normal CDF. The interval is clamped to $[0, 1]$.

### t-Distribution Confidence Interval (Means)

$$\bar{x} \pm t^*_{n-1} \cdot \frac{s}{\sqrt{n}}$$

The critical value $t^*$ is approximated from $z^*$ via the **Cornish-Fisher expansion**:

$$t^* \approx z + \frac{z^3 + z}{4\nu} + \frac{5z^5 + 16z^3 + 3z}{96\nu^2}$$

---

## Testing

```bash
pip install -e ".[test]"
pytest
```

**60 tests** covering:
- **Variant** — creation, assignment, duplicate prevention, results, conversions, mean/variance/std_dev, edge cases
- **Assignment strategies** — `RandomAssignment` (seed determinism, approximate balance), `WeightedAssignment` (70/30 split), `StratifiedAssignment` (deterministic hash, distribution)
- **Experiment** — variant management, assignment, idempotency, batch assignment, lifecycle (stop), convenience recording
- **Chi-squared test** — clear difference (10% vs 30%), no difference, small difference, edge cases
- **Welch's t-test** — clear difference, no difference (same distribution), too few observations, identical values
- **Confidence intervals** — Wilson-score for proportions (normal, extreme 0%/100%), t-interval for means, edge cases
- **ExperimentReport** — binary reports, winner selection, continuous reports, text output, single-variant edge case, insufficient data, auto-detection of binary vs continuous

---

## License

MIT
