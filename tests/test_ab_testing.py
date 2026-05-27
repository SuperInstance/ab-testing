"""Tests for ab_testing package."""

import math
import pytest

from ab_testing import (
    Variant,
    Experiment,
    ExperimentReport,
    RandomAssignment,
    WeightedAssignment,
    StratifiedAssignment,
    chi_squared_test,
    t_test,
    proportion_confidence_interval,
    mean_confidence_interval,
)


# ===================================================================
# Variant tests
# ===================================================================

class TestVariant:
    def test_create(self):
        v = Variant("control")
        assert v.name == "control"
        assert v.weight == 1.0
        assert v.assignment_count == 0

    def test_assign(self):
        v = Variant("A")
        v.assign("user-1")
        assert v.assignment_count == 1
        assert v.is_assigned("user-1")

    def test_assign_duplicate_raises(self):
        v = Variant("A")
        v.assign("user-1")
        with pytest.raises(ValueError, match="already assigned"):
            v.assign("user-1")

    def test_record_result(self):
        v = Variant("A")
        v.assign("u1")
        v.record_result("u1", 42.0)
        assert v.results == [42.0]
        assert v.mean == 42.0
        assert v.result_count == 1

    def test_record_result_unassigned_raises(self):
        v = Variant("A")
        with pytest.raises(ValueError, match="not assigned"):
            v.record_result("u1", 1.0)

    def test_record_conversion(self):
        v = Variant("A")
        v.assign("u1")
        v.assign("u2")
        v.record_conversion("u1", True)
        v.record_conversion("u2", False)
        assert v.conversion_rate == 0.5

    def test_mean_no_results_raises(self):
        v = Variant("A")
        with pytest.raises(ValueError):
            _ = v.mean

    def test_variance(self):
        v = Variant("A")
        for i in range(5):
            v.assign(f"u{i}")
            v.record_result(f"u{i}", float(i))
        # values: 0, 1, 2, 3, 4 -> var = (sum of (x-2)^2)/4 = (4+1+0+1+4)/4 = 2.5
        assert abs(v.variance - 2.5) < 1e-10

    def test_std_dev(self):
        v = Variant("A")
        for i in range(5):
            v.assign(f"u{i}")
            v.record_result(f"u{i}", float(i))
        assert abs(v.std_dev - math.sqrt(2.5)) < 1e-10

    def test_variance_single_result_raises(self):
        v = Variant("A")
        v.assign("u1")
        v.record_result("u1", 1.0)
        with pytest.raises(ValueError):
            _ = v.variance

    def test_subject_ids(self):
        v = Variant("A")
        v.assign("u1")
        v.assign("u2")
        assert set(v.subject_ids) == {"u1", "u2"}

    def test_repr(self):
        v = Variant("control", weight=2.0)
        r = repr(v)
        assert "control" in r
        assert "weight=2.0" in r


# ===================================================================
# Assignment strategy tests
# ===================================================================

class TestRandomAssignment:
    def test_returns_variant(self):
        variants = [Variant("A"), Variant("B")]
        s = RandomAssignment(seed=42)
        v = s.assign("user1", variants)
        assert v.name in {"A", "B"}

    def test_deterministic_with_seed(self):
        variants = [Variant("A"), Variant("B")]
        s1 = RandomAssignment(seed=99)
        s2 = RandomAssignment(seed=99)
        for i in range(100):
            assert s1.assign(f"u{i}", variants).name == s2.assign(f"u{i}", variants).name

    def test_empty_raises(self):
        s = RandomAssignment()
        with pytest.raises(ValueError):
            s.assign("u1", [])

    def test_approximately_balanced(self):
        variants = [Variant("A"), Variant("B")]
        s = RandomAssignment(seed=12345)
        counts = {"A": 0, "B": 0}
        for i in range(10000):
            v = s.assign(f"u{i}", variants)
            counts[v.name] += 1
        # Should be roughly 50/50, allow 10% margin
        assert 4000 < counts["A"] < 6000
        assert 4000 < counts["B"] < 6000


class TestWeightedAssignment:
    def test_70_30_split(self):
        a = Variant("A", weight=70)
        b = Variant("B", weight=30)
        s = WeightedAssignment(seed=42)
        counts = {"A": 0, "B": 0}
        for i in range(10000):
            v = s.assign(f"u{i}", [a, b])
            counts[v.name] += 1
        # Allow wider margin for randomness
        assert 6000 < counts["A"] < 8000
        assert 2000 < counts["B"] < 4000

    def test_empty_raises(self):
        s = WeightedAssignment()
        with pytest.raises(ValueError):
            s.assign("u1", [])

    def test_zero_weight_raises(self):
        v = Variant("A", weight=0)
        s = WeightedAssignment()
        with pytest.raises(ValueError, match="weight"):
            s.assign("u1", [v])


class TestStratifiedAssignment:
    def test_deterministic(self):
        variants = [Variant("A"), Variant("B")]
        s = StratifiedAssignment(salt="test")
        v1 = s.assign("user-123", variants)
        v2 = s.assign("user-123", variants)
        assert v1.name == v2.name

    def test_different_subjects_distribute(self):
        variants = [Variant("A"), Variant("B")]
        s = StratifiedAssignment(salt="test")
        names = set()
        for i in range(1000):
            v = s.assign(f"user-{i}", variants)
            names.add(v.name)
        assert "A" in names and "B" in names

    def test_empty_raises(self):
        s = StratifiedAssignment()
        with pytest.raises(ValueError):
            s.assign("u1", [])


# ===================================================================
# Experiment tests
# ===================================================================

class TestExperiment:
    def test_create(self):
        exp = Experiment("test-exp")
        assert exp.name == "test-exp"
        assert len(exp.variants) == 0
        assert exp.is_running

    def test_add_variant(self):
        exp = Experiment("test")
        exp.add_variant(Variant("control"))
        exp.add_variant(Variant("treatment"))
        assert len(exp.variants) == 2

    def test_add_duplicate_raises(self):
        exp = Experiment("test")
        exp.add_variant(Variant("control"))
        with pytest.raises(ValueError, match="already exists"):
            exp.add_variant(Variant("control"))

    def test_control_property(self):
        exp = Experiment("test")
        c = Variant("control")
        t = Variant("treatment")
        exp.add_variant(c)
        exp.add_variant(t)
        assert exp.control is c
        assert exp.treatments == [t]

    def test_control_empty(self):
        exp = Experiment("test")
        assert exp.control is None

    def test_assign(self):
        exp = Experiment("test", strategy=RandomAssignment(seed=1))
        exp.add_variant(Variant("A"))
        exp.add_variant(Variant("B"))
        v = exp.assign("u1")
        assert v.name in {"A", "B"}
        assert exp.total_assigned == 1

    def test_assign_idempotent(self):
        exp = Experiment("test", strategy=RandomAssignment(seed=1))
        exp.add_variant(Variant("A"))
        exp.add_variant(Variant("B"))
        v1 = exp.assign("u1")
        v2 = exp.assign("u1")
        assert v1.name == v2.name
        assert exp.total_assigned == 1

    def test_assign_batch(self):
        exp = Experiment("test", strategy=RandomAssignment(seed=1))
        exp.add_variant(Variant("A"))
        exp.add_variant(Variant("B"))
        result = exp.assign_batch(["u1", "u2", "u3"])
        assert len(result) == 3
        assert exp.total_assigned == 3

    def test_assign_after_stop_raises(self):
        exp = Experiment("test")
        exp.add_variant(Variant("A"))
        exp.stop()
        with pytest.raises(RuntimeError, match="stopped"):
            exp.assign("u1")

    def test_record_result(self):
        exp = Experiment("test", strategy=RandomAssignment(seed=1))
        exp.add_variant(Variant("A"))
        exp.add_variant(Variant("B"))
        exp.assign("u1")
        exp.record_result("u1", 42.0)
        # Find which variant u1 was assigned to
        v = exp.get_assignment("u1")
        assert v.results == [42.0]

    def test_record_conversion(self):
        exp = Experiment("test", strategy=RandomAssignment(seed=1))
        exp.add_variant(Variant("A"))
        exp.add_variant(Variant("B"))
        exp.assign("u1")
        exp.record_conversion("u1", True)

    def test_record_result_unassigned_raises(self):
        exp = Experiment("test")
        exp.add_variant(Variant("A"))
        with pytest.raises(ValueError, match="not assigned"):
            exp.record_result("u1", 1.0)

    def test_get_variant(self):
        exp = Experiment("test")
        exp.add_variant(Variant("A"))
        assert exp.get_variant("A").name == "A"

    def test_get_variant_missing(self):
        exp = Experiment("test")
        with pytest.raises(KeyError):
            exp.get_variant("missing")

    def test_repr(self):
        exp = Experiment("test")
        exp.add_variant(Variant("A"))
        r = repr(exp)
        assert "test" in r
        assert "running" in r


# ===================================================================
# Stats tests
# ===================================================================

class TestChiSquared:
    def test_clear_difference(self):
        # 10/100 vs 30/100 — should be significant
        result = chi_squared_test(10, 100, 30, 100)
        assert result.significant
        assert result.p_value < 0.05
        assert result.degrees_of_freedom == 1

    def test_no_difference(self):
        # 50/100 vs 50/100 — should not be significant
        result = chi_squared_test(50, 100, 50, 100)
        assert not result.significant
        assert result.p_value > 0.05

    def test_small_difference(self):
        # 50/1000 vs 55/1000 — likely not significant
        result = chi_squared_test(50, 1000, 55, 1000)
        assert not result.significant

    def test_zero_totals_raise(self):
        with pytest.raises(ValueError):
            chi_squared_test(0, 0, 0, 100)

    def test_repr(self):
        r = chi_squared_test(10, 100, 30, 100)
        s = repr(r)
        assert "chi2" in s
        assert "p=" in s


class TestTTest:
    def test_clear_difference(self):
        control = [1.0] * 50
        treatment = [3.0] * 50
        result = t_test(control, treatment)
        assert result.significant
        assert result.p_value < 0.05
        assert result.t_statistic > 0  # treatment > control

    def test_no_difference(self):
        import random
        rng = random.Random(42)
        a = [rng.gauss(5, 1) for _ in range(100)]
        b = [rng.gauss(5, 1) for _ in range(100)]
        result = t_test(a, b)
        assert not result.significant

    def test_too_few_raises(self):
        with pytest.raises(ValueError):
            t_test([1.0], [2.0])

    def test_identical_values(self):
        result = t_test([5.0] * 10, [5.0] * 10)
        assert result.t_statistic == 0.0
        assert result.p_value == 1.0

    def test_repr(self):
        r = t_test([1, 2, 3], [4, 5, 6])
        s = repr(r)
        assert "t=" in s
        assert "p=" in s


class TestConfidenceIntervals:
    def test_proportion_ci(self):
        ci = proportion_confidence_interval(50, 100)
        assert ci.confidence == 0.95
        assert ci.lower < 0.5 < ci.upper
        assert ci.lower > 0 and ci.upper < 1

    def test_proportion_ci_extreme(self):
        ci = proportion_confidence_interval(0, 100)
        assert ci.lower == 0.0
        ci2 = proportion_confidence_interval(100, 100)
        assert ci2.upper == 1.0

    def test_proportion_ci_zero_total_raises(self):
        with pytest.raises(ValueError):
            proportion_confidence_interval(0, 0)

    def test_mean_ci(self):
        ci = mean_confidence_interval([1, 2, 3, 4, 5])
        assert ci.confidence == 0.95
        assert ci.lower < 3.0 < ci.upper

    def test_mean_ci_too_few_raises(self):
        with pytest.raises(ValueError):
            mean_confidence_interval([1.0])

    def test_mean_ci_single_value_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            mean_confidence_interval([5.0])


# ===================================================================
# ExperimentReport tests
# ===================================================================

class TestExperimentReport:
    def _make_binary_experiment(self) -> Experiment:
        """Create an experiment with clear winner in binary metric."""
        exp = Experiment("button-color", strategy=StratifiedAssignment(salt="test"))
        control = Variant("green-button")
        treatment = Variant("red-button")
        exp.add_variant(control)
        exp.add_variant(treatment)

        # Control: 20% conversion
        rng = __import__("random").Random(42)
        for i in range(1000):
            exp.assign(f"u{i}")
            exp.record_conversion(f"u{i}", rng.random() < 0.20)

        # Override: force clear difference for deterministic test
        # Clear assignments and redo
        control._assignments.clear()
        treatment._assignments.clear()
        exp._assignments.clear()

        for i in range(500):
            control.assign(f"c{i}")
            control.record_conversion(f"c{i}", i < 100)  # 20%
        for i in range(500):
            treatment.assign(f"t{i}")
            treatment.record_conversion(f"t{i}", i < 150)  # 30%
        exp._assignments.update({f"c{i}": "green-button" for i in range(500)})
        exp._assignments.update({f"t{i}": "red-button" for i in range(500)})

        return exp

    def test_binary_report(self):
        exp = self._make_binary_experiment()
        report = ExperimentReport.from_experiment(exp, metric_type="binary")
        assert len(report.summaries) == 2
        assert len(report.comparisons) == 1
        assert report.comparisons[0].test.significant  # 20% vs 30%

    def test_winner_selected(self):
        exp = self._make_binary_experiment()
        report = ExperimentReport.from_experiment(exp, metric_type="binary")
        assert report.winner == "red-button"
        assert "red-button" in report.recommendation

    def test_continuous_report(self):
        exp = Experiment("page-load", strategy=RandomAssignment(seed=1))
        control = Variant("baseline")
        treatment = Variant("optimized")
        exp.add_variant(control)
        exp.add_variant(treatment)

        import random
        rng = random.Random(42)
        for i in range(100):
            exp.assign(f"u{i}")
        for i, sid in enumerate(control.subject_ids):
            control.record_result(sid, rng.gauss(500, 50))
        for sid in treatment.subject_ids:
            treatment.record_result(sid, rng.gauss(480, 50))

        report = ExperimentReport.from_experiment(exp, metric_type="continuous")
        assert len(report.summaries) == 2
        assert len(report.comparisons) == 1

    def test_to_text(self):
        exp = self._make_binary_experiment()
        report = ExperimentReport.from_experiment(exp, metric_type="binary")
        text = report.to_text()
        assert "button-color" in text
        assert "green-button" in text
        assert "red-button" in text

    def test_single_variant(self):
        exp = Experiment("single")
        exp.add_variant(Variant("only"))
        report = ExperimentReport.from_experiment(exp)
        assert "Need at least 2" in report.recommendation

    def test_insufficient_data(self):
        exp = Experiment("sparse")
        exp.add_variant(Variant("A"))
        exp.add_variant(Variant("B"))
        # No results
        report = ExperimentReport.from_experiment(exp)
        assert report.winner is None

    def test_auto_detect_binary(self):
        exp = Experiment("auto")
        c = Variant("c")
        t = Variant("t")
        exp.add_variant(c)
        exp.add_variant(t)
        for i in range(100):
            c.assign(f"cu{i}")
            c.record_result(f"cu{i}", 1.0 if i < 20 else 0.0)
        for i in range(100):
            t.assign(f"tu{i}")
            t.record_result(f"tu{i}", 1.0 if i < 30 else 0.0)
        report = ExperimentReport.from_experiment(exp)  # auto detect
        assert len(report.comparisons) == 1
        # Should have conversion_rate in summaries
        assert report.summaries[0].conversion_rate is not None
