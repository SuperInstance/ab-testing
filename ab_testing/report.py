"""ExperimentReport — summarises an experiment with statistical analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .experiment import Experiment
from .stats import (
    chi_squared_test,
    t_test,
    proportion_confidence_interval,
    mean_confidence_interval,
    ChiSquaredResult,
    TTestResult,
    ConfidenceInterval,
)


@dataclass
class VariantSummary:
    """Summary stats for one variant."""
    name: str
    assignment_count: int
    result_count: int
    mean: float | None
    std_dev: float | None
    conversion_rate: float | None
    confidence_interval: ConfidenceInterval | None


@dataclass
class ComparisonResult:
    """Statistical comparison between two variants."""
    control_name: str
    treatment_name: str
    test: ChiSquaredResult | TTestResult
    effect_size: float  # absolute difference (treatment - control) for means; lift % for proportions
    confidence_interval_diff: ConfidenceInterval | None = None


@dataclass
class ExperimentReport:
    """Full analysis report for an experiment.

    Builds summaries and runs statistical tests comparing each treatment
    to the control (first variant).
    """

    experiment_name: str
    summaries: list[VariantSummary] = field(default_factory=list)
    comparisons: list[ComparisonResult] = field(default_factory=list)
    recommendation: str = ""
    winner: str | None = None

    @classmethod
    def from_experiment(
        cls,
        experiment: Experiment,
        *,
        metric_type: str = "auto",
        alpha: float = 0.05,
        confidence: float = 0.95,
    ) -> "ExperimentReport":
        """Generate a report from a live experiment.

        Args:
            experiment: The experiment to analyse.
            metric_type: "binary" (conversion), "continuous", or "auto" (detect).
            alpha: Significance threshold.
            confidence: Confidence level for intervals.
        """
        report = cls(experiment_name=experiment.name)

        if len(experiment.variants) < 2:
            report.recommendation = "Need at least 2 variants to compare."
            return report

        # Detect metric type
        is_binary = metric_type == "binary"
        if metric_type == "auto":
            is_binary = cls._detect_binary(experiment.variants)

        # Build summaries
        for v in experiment.variants:
            summary = VariantSummary(
                name=v.name,
                assignment_count=v.assignment_count,
                result_count=v.result_count,
                mean=None,
                std_dev=None,
                conversion_rate=None,
                confidence_interval=None,
            )
            if v.result_count >= 1:
                summary.mean = v.mean
            if v.result_count >= 2:
                summary.std_dev = v.std_dev
            if is_binary and v.result_count >= 1:
                summary.conversion_rate = v.conversion_rate
                summary.confidence_interval = proportion_confidence_interval(
                    int(sum(v.results)), v.result_count, confidence=confidence,
                )
            elif v.result_count >= 2:
                summary.confidence_interval = mean_confidence_interval(
                    v.results, confidence=confidence,
                )
            report.summaries.append(summary)

        # Compare each treatment to control
        control = experiment.variants[0]
        for treatment in experiment.variants[1:]:
            comp = cls._compare(control, treatment, is_binary, alpha, confidence)
            if comp is not None:
                report.comparisons.append(comp)

        # Pick winner
        report.winner, report.recommendation = cls._pick_winner(
            experiment.variants, report.comparisons, alpha,
        )

        return report

    # ------------------------------------------------------------------

    @staticmethod
    def _detect_binary(variants: Sequence) -> bool:
        """If all results are 0 or 1, treat as binary."""
        for v in variants:
            for r in v.results:
                if r not in (0.0, 1.0):
                    return False
        return True

    @staticmethod
    def _compare(
        control: Variant,
        treatment: Variant,
        is_binary: bool,
        alpha: float,
        confidence: float,
    ) -> ComparisonResult | None:
        if control.result_count < 2 or treatment.result_count < 2:
            return None

        if is_binary:
            test = chi_squared_test(
                int(sum(control.results)), control.result_count,
                int(sum(treatment.results)), treatment.result_count,
                alpha=alpha,
            )
            cr = control.conversion_rate
            tr = treatment.conversion_rate
            effect_size = (tr - cr) / cr * 100 if cr > 0 else 0.0  # lift %
        else:
            test = t_test(control.results, treatment.results, alpha=alpha)
            effect_size = treatment.mean - control.mean

        return ComparisonResult(
            control_name=control.name,
            treatment_name=treatment.name,
            test=test,
            effect_size=effect_size,
        )

    @staticmethod
    def _pick_winner(
        variants: list[Variant],
        comparisons: list[ComparisonResult],
        alpha: float,
    ) -> tuple[str | None, str]:
        if not comparisons:
            return None, "Not enough data to determine a winner."

        # Find best significant treatment
        best = None
        best_effect = -float("inf")
        any_significant = False

        for comp in comparisons:
            if comp.test.significant:
                any_significant = True
                if comp.effect_size > best_effect:
                    best_effect = comp.effect_size
                    best = comp

        if not any_significant:
            return None, "No variant reached statistical significance. Continue the experiment or increase sample size."

        winner_name = best.treatment_name if best.effect_size > 0 else best.control_name
        if best.effect_size > 0:
            rec = (
                f"Winner: {best.treatment_name!r} — significant improvement "
                f"over {best.control_name!r} (effect={best.effect_size:.4f}, "
                f"p={best.test.p_value:.6f}). Recommend shipping."
            )
        else:
            rec = (
                f"Control {best.control_name!r} outperforms {best.treatment_name!r}. "
                f"No reason to switch."
            )
        return winner_name, rec

    # ------------------------------------------------------------------
    # Text report
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        """Human-readable text report."""
        lines = [
            f"Experiment: {self.experiment_name}",
            "=" * 50,
            "",
            "Variant Summaries:",
        ]
        for s in self.summaries:
            lines.append(f"  {s.name}: n={s.result_count}/{s.assignment_count}")
            if s.mean is not None:
                lines.append(f"    mean={s.mean:.4f}")
            if s.std_dev is not None:
                lines.append(f"    std={s.std_dev:.4f}")
            if s.conversion_rate is not None:
                lines.append(f"    conversion_rate={s.conversion_rate:.4f}")
            if s.confidence_interval is not None:
                lines.append(f"    95% CI: [{s.confidence_interval.lower:.4f}, {s.confidence_interval.upper:.4f}]")

        if self.comparisons:
            lines.append("")
            lines.append("Comparisons:")
            for c in self.comparisons:
                lines.append(f"  {c.control_name} vs {c.treatment_name}:")
                lines.append(f"    {c.test}")
                lines.append(f"    effect_size={c.effect_size:.4f}")

        lines.append("")
        lines.append(f"Recommendation: {self.recommendation}")
        if self.winner:
            lines.append(f"Winner: {self.winner}")

        return "\n".join(lines)
