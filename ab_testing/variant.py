"""Variant — a single arm of an experiment (control or treatment)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Variant:
    """A single variant (arm) in an A/B test.

    Tracks assignment of subjects and per-subject results.

    Attributes:
        name: Human-readable name (e.g. "control", "treatment").
        weight: Relative weight for traffic splitting (default 1.0).
        metadata: Arbitrary extra info.
    """

    name: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    _assignments: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assign(self, subject_id: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Record that *subject_id* was assigned to this variant."""
        if subject_id in self._assignments:
            raise ValueError(f"Subject {subject_id!r} already assigned to variant {self.name!r}")
        self._assignments[subject_id] = {
            "assigned_at": time.time(),
            "metadata": metadata or {},
            "result": None,
        }

    def is_assigned(self, subject_id: str) -> bool:
        return subject_id in self._assignments

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)

    @property
    def subject_ids(self) -> list[str]:
        return list(self._assignments.keys())

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def record_result(self, subject_id: str, value: float) -> None:
        """Record a numeric result for *subject_id*."""
        if subject_id not in self._assignments:
            raise ValueError(f"Subject {subject_id!r} not assigned to variant {self.name!r}")
        self._assignments[subject_id]["result"] = value

    def record_conversion(self, subject_id: str, converted: bool) -> None:
        """Record a binary conversion result (convenience wrapper)."""
        self.record_result(subject_id, float(converted))

    @property
    def results(self) -> list[float]:
        """All recorded results, in assignment order."""
        return [
            rec["result"] for rec in self._assignments.values()
            if rec["result"] is not None
        ]

    @property
    def result_count(self) -> int:
        return len(self.results)

    # ------------------------------------------------------------------
    # Quick stats
    # ------------------------------------------------------------------

    @property
    def mean(self) -> float:
        r = self.results
        if not r:
            raise ValueError("No results recorded")
        return sum(r) / len(r)

    @property
    def conversion_rate(self) -> float:
        """For binary (0/1) results, returns the proportion of 1s."""
        return self.mean

    @property
    def variance(self) -> float:
        r = self.results
        if len(r) < 2:
            raise ValueError("Need at least 2 results for variance")
        m = self.mean
        return sum((x - m) ** 2 for x in r) / (len(r) - 1)

    @property
    def std_dev(self) -> float:
        return self.variance ** 0.5

    def __repr__(self) -> str:
        return (
            f"Variant(name={self.name!r}, weight={self.weight}, "
            f"assigned={self.assignment_count}, results={self.result_count})"
        )
