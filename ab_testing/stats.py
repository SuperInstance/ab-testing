"""Stats — statistical tests implemented from scratch (no external deps)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


# ---------------------------------------------------------------------------
# Helper: Standard normal CDF via Abramowitz & Stegun approximation
# ---------------------------------------------------------------------------

def _normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function (Φ)."""
    # Approximation 26.2.17 from Abramowitz & Stegun
    if x < -8:
        return 0.0
    if x > 8:
        return 1.0
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    t = 1.0 / (1.0 + p * abs(x))
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2.0)
    return 0.5 * (1.0 + sign * y)


# ---------------------------------------------------------------------------
# Helper: Regularised incomplete gamma function (for chi-squared CDF)
# ---------------------------------------------------------------------------

def _gamma_func(x: float) -> float:
    """Gamma function via Lanczos approximation."""
    if x < 0.5:
        return math.pi / (math.sin(math.pi * x) * _gamma_func(1 - x))
    x -= 1
    g = 7
    coefs = [
        0.99999999999980993, 676.5203681218851, -1259.1392167224028,
        771.32342877765313, -176.61502916214059, 12.507343278686905,
        -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
    ]
    s = coefs[0]
    for i in range(1, g + 2):
        s += coefs[i] / (x + i)
    t = x + g + 0.5
    return math.sqrt(2 * math.pi) * t ** (x + 0.5) * math.exp(-t) * s


def _lower_incomplete_gamma(s: float, x: float, iterations: int = 200) -> float:
    """Lower regularised incomplete gamma P(s, x)."""
    if x < 0:
        return 0.0
    if x == 0:
        return 0.0
    # Series expansion
    total = 1.0 / s
    term = 1.0 / s
    for n in range(1, iterations):
        term *= x / (s + n)
        total += term
    return total * x ** s * math.exp(-x) / _gamma_func(s)


# ---------------------------------------------------------------------------
# Chi-squared test (for proportions / binary outcomes)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChiSquaredResult:
    chi2: float
    p_value: float
    degrees_of_freedom: int
    significant: bool  # at alpha=0.05

    def __repr__(self) -> str:
        return (
            f"ChiSquaredResult(chi2={self.chi2:.4f}, p={self.p_value:.6f}, "
            f"df={self.degrees_of_freedom}, significant={self.significant})"
        )


def chi_squared_test(
    control_successes: int,
    control_total: int,
    treatment_successes: int,
    treatment_total: int,
    *,
    alpha: float = 0.05,
) -> ChiSquaredResult:
    """Two-proportion chi-squared test (Yates-corrected).

    Parameters:
        control_successes / control_total: conversions in the control arm.
        treatment_successes / treatment_total: conversions in the treatment arm.
        alpha: significance level.
    """
    if control_total <= 0 or treatment_total <= 0:
        raise ValueError("Group totals must be > 0")

    a = control_successes
    b = control_total - control_successes
    c = treatment_successes
    d = treatment_total - treatment_successes
    n = a + b + c + d
    if n == 0:
        raise ValueError("No observations")

    # Yates correction
    chi2 = n * (abs(a * d - b * c) - n / 2.0) ** 2 / (
        (a + b) * (c + d) * (a + c) * (b + d)
    ) if n > 0 else 0.0

    df = 1
    p_value = 1.0 - _lower_incomplete_gamma(df / 2.0, chi2 / 2.0)

    return ChiSquaredResult(
        chi2=chi2,
        p_value=p_value,
        degrees_of_freedom=df,
        significant=p_value < alpha,
    )


# ---------------------------------------------------------------------------
# t-test (for continuous metrics)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TTestResult:
    t_statistic: float
    p_value: float
    degrees_of_freedom: float
    significant: bool  # at alpha=0.05

    def __repr__(self) -> str:
        return (
            f"TTestResult(t={self.t_statistic:.4f}, p={self.p_value:.6f}, "
            f"df={self.degrees_of_freedom:.1f}, significant={self.significant})"
        )


def t_test(
    control: Sequence[float],
    treatment: Sequence[float],
    *,
    alpha: float = 0.05,
) -> TTestResult:
    """Welch's two-sample t-test (unequal variances)."""
    n1, n2 = len(control), len(treatment)
    if n1 < 2 or n2 < 2:
        raise ValueError("Each group needs at least 2 observations")

    m1 = sum(control) / n1
    m2 = sum(treatment) / n2
    v1 = sum((x - m1) ** 2 for x in control) / (n1 - 1)
    v2 = sum((x - m2) ** 2 for x in treatment) / (n2 - 1)

    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        # Both groups have zero variance; if means differ, it's infinitely significant
        if abs(m2 - m1) > 0:
            return TTestResult(
                t_statistic=float('inf'),
                p_value=0.0,
                degrees_of_freedom=float(n1 + n2 - 2),
                significant=True,
            )
        return TTestResult(t_statistic=0.0, p_value=1.0, degrees_of_freedom=n1 + n2 - 2, significant=False)

    t_stat = (m2 - m1) / se

    # Welch–Satterthwaite degrees of freedom
    num = (v1 / n1 + v2 / n2) ** 2
    denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    df = num / denom if denom > 0 else n1 + n2 - 2

    # Two-tailed p-value via normal approximation for large df
    # For moderate df, use t-distribution approximation
    p_value = _two_tailed_p(t_stat, df)

    return TTestResult(
        t_statistic=t_stat,
        p_value=p_value,
        degrees_of_freedom=df,
        significant=p_value < alpha,
    )


def _two_tailed_p(t: float, df: float) -> float:
    """Approximate two-tailed p-value for a t-distribution.

    Uses the normal approximation with a correction for small df.
    """
    # For very large df, t ≈ normal
    if df > 30:
        z = t
        p = 2 * (1 - _normal_cdf(abs(z)))
        return p

    # For smaller df, use Hill's approximation (approximation 26.7.10)
    # Simple approach: use normal with wider spread correction
    x = df / (df + t * t)
    # Beta function approximation for incomplete beta
    p = _incomplete_beta(df / 2.0, 0.5, x)
    return p


def _incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b) using continued fraction."""
    if x < 0 or x > 1:
        raise ValueError("x must be in [0, 1]")
    if x == 0:
        return 0.0
    if x == 1:
        return 1.0

    # Use continued fraction (Lentz's method)
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a

    # Continued fraction
    f = 1.0
    c = 1.0
    d = 1.0 - (a + 1) * x / (a + 1) if (a + 1) * x != 0 else 1.0
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    f = d

    for m in range(1, 101):
        # Even step
        numerator = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        f *= c * d

        # Odd step
        numerator = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = c * d
        f *= delta

        if abs(delta - 1.0) < 1e-10:
            break

    return front * f


# ---------------------------------------------------------------------------
# Confidence intervals
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfidenceInterval:
    lower: float
    upper: float
    confidence: float  # e.g. 0.95

    def __repr__(self) -> str:
        return f"CI([{self.lower:.4f}, {self.upper:.4f}], confidence={self.confidence:.0%})"


def proportion_confidence_interval(
    successes: int,
    total: int,
    *,
    confidence: float = 0.95,
) -> ConfidenceInterval:
    """Wilson-score confidence interval for a proportion."""
    if total <= 0:
        raise ValueError("Total must be > 0")
    p_hat = successes / total
    z = _z_for_confidence(confidence)
    n = total
    denom = 1 + z ** 2 / n
    centre = (p_hat + z ** 2 / (2 * n)) / denom
    spread = z * math.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2)) / denom
    return ConfidenceInterval(
        lower=max(0.0, centre - spread),
        upper=min(1.0, centre + spread),
        confidence=confidence,
    )


def mean_confidence_interval(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
) -> ConfidenceInterval:
    """Confidence interval for a mean (using t-distribution)."""
    n = len(values)
    if n < 2:
        raise ValueError("Need at least 2 values")
    m = sum(values) / n
    var = sum((x - m) ** 2 for x in values) / (n - 1)
    se = math.sqrt(var / n)
    t_crit = _t_critical(n - 1, confidence)
    return ConfidenceInterval(
        lower=m - t_crit * se,
        upper=m + t_crit * se,
        confidence=confidence,
    )


def _z_for_confidence(confidence: float) -> float:
    """Critical z-value for two-tailed *confidence* level."""
    alpha_half = (1 - confidence) / 2
    # Binary search for z where Φ(z) = 1 - alpha_half
    lo, hi = 0.0, 8.0
    target = 1 - alpha_half
    for _ in range(100):
        mid = (lo + hi) / 2
        if _normal_cdf(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _t_critical(df: float, confidence: float) -> float:
    """Approximate critical t-value.

    Uses the normal approximation with a correction for small samples.
    """
    z = _z_for_confidence(confidence)
    # Cornish-Fisher expansion correction
    g1 = (z ** 3 + z) / (4 * df)
    g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)
    return z + g1 + g2
