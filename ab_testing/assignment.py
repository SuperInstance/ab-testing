"""Assignment strategies — how subjects are routed to variants."""

from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from .variant import Variant


class AssignmentStrategy(ABC):
    """Base class for assignment strategies."""

    @abstractmethod
    def assign(self, subject_id: str, variants: Sequence[Variant]) -> Variant:
        """Return the variant *subject_id* should be assigned to."""
        ...


class RandomAssignment(AssignmentStrategy):
    """Uniform random assignment, optionally seeded for reproducibility."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def assign(self, subject_id: str, variants: Sequence[Variant]) -> Variant:
        if not variants:
            raise ValueError("No variants provided")
        return self._rng.choice(variants)


class WeightedAssignment(AssignmentStrategy):
    """Weighted random assignment based on ``Variant.weight``."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def assign(self, subject_id: str, variants: Sequence[Variant]) -> Variant:
        if not variants:
            raise ValueError("No variants provided")
        total = sum(v.weight for v in variants)
        if total <= 0:
            raise ValueError("Total variant weight must be > 0")
        r = self._rng.uniform(0, total)
        cumulative = 0.0
        for v in variants:
            cumulative += v.weight
            if r <= cumulative:
                return v
        return variants[-1]  # floating-point edge case


class StratifiedAssignment(AssignmentStrategy):
    """Deterministic hash-based assignment ensuring consistent bucketing.

    Uses SHA-256 of the subject_id to pick a variant proportionally to weight.
    """

    def __init__(self, salt: str = "ab-testing") -> None:
        self.salt = salt

    def assign(self, subject_id: str, variants: Sequence[Variant]) -> Variant:
        if not variants:
            raise ValueError("No variants provided")
        total = sum(v.weight for v in variants)
        if total <= 0:
            raise ValueError("Total variant weight must be > 0")

        key = f"{self.salt}:{subject_id}".encode()
        h = int(hashlib.sha256(key).hexdigest(), 16)
        ratio = (h % 10_000) / 10_000.0 * total
        cumulative = 0.0
        for v in variants:
            cumulative += v.weight
            if ratio <= cumulative:
                return v
        return variants[-1]
