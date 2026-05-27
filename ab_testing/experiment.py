"""Experiment — orchestrates variants and assignment."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Sequence

from .assignment import AssignmentStrategy, RandomAssignment
from .variant import Variant


@dataclass
class Experiment:
    """An A/B test experiment.

    Attributes:
        name: Human-readable name.
        description: Optional description.
        variants: Variants in this experiment.
        strategy: Assignment strategy (default: random).
    """

    name: str
    description: str = ""
    variants: list[Variant] = field(default_factory=list)
    strategy: AssignmentStrategy = field(default_factory=RandomAssignment)
    _id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _created_at: float = field(default_factory=time.time)
    _assignments: dict[str, str] = field(default_factory=dict, repr=False)  # subject_id -> variant name
    _running: bool = field(default=True, repr=False)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def add_variant(self, variant: Variant) -> None:
        if any(v.name == variant.name for v in self.variants):
            raise ValueError(f"Variant {variant.name!r} already exists")
        self.variants.append(variant)

    def get_variant(self, name: str) -> Variant:
        for v in self.variants:
            if v.name == name:
                return v
        raise KeyError(f"No variant named {name!r}")

    @property
    def control(self) -> Variant | None:
        """Return the first variant (conventionally the control), or None."""
        return self.variants[0] if self.variants else None

    @property
    def treatments(self) -> list[Variant]:
        """All variants except the first."""
        return self.variants[1:]

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assign(self, subject_id: str, **kwargs: Any) -> Variant:
        """Assign *subject_id* to a variant using the configured strategy."""
        if not self._running:
            raise RuntimeError("Experiment has been stopped")
        if subject_id in self._assignments:
            return self.get_variant(self._assignments[subject_id])

        variant = self.strategy.assign(subject_id, self.variants)
        variant.assign(subject_id, metadata=kwargs)
        self._assignments[subject_id] = variant.name
        return variant

    def assign_batch(self, subject_ids: Sequence[str], **kwargs: Any) -> dict[str, Variant]:
        """Assign multiple subjects at once."""
        return {sid: self.assign(sid, **kwargs) for sid in subject_ids}

    def get_assignment(self, subject_id: str) -> Variant | None:
        name = self._assignments.get(subject_id)
        if name is None:
            return None
        return self.get_variant(name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def total_assigned(self) -> int:
        return len(self._assignments)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def record_result(self, subject_id: str, value: float) -> None:
        """Record a result for a subject (auto-routes to the right variant)."""
        variant = self.get_assignment(subject_id)
        if variant is None:
            raise ValueError(f"Subject {subject_id!r} is not assigned to this experiment")
        variant.record_result(subject_id, value)

    def record_conversion(self, subject_id: str, converted: bool) -> None:
        variant = self.get_assignment(subject_id)
        if variant is None:
            raise ValueError(f"Subject {subject_id!r} is not assigned to this experiment")
        variant.record_conversion(subject_id, converted)

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return (
            f"Experiment({self.name!r}, variants={len(self.variants)}, "
            f"assigned={self.total_assigned}, {status})"
        )
