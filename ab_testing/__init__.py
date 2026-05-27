"""ab-testing — Statistical A/B testing framework for experiment comparison."""

from .variant import Variant
from .assignment import AssignmentStrategy, RandomAssignment, WeightedAssignment, StratifiedAssignment
from .experiment import Experiment
from .stats import chi_squared_test, t_test, proportion_confidence_interval, mean_confidence_interval
from .report import ExperimentReport

__version__ = "0.1.0"
__all__ = [
    "Variant",
    "AssignmentStrategy", "RandomAssignment", "WeightedAssignment", "StratifiedAssignment",
    "Experiment",
    "chi_squared_test", "t_test", "proportion_confidence_interval", "mean_confidence_interval",
    "ExperimentReport",
]
