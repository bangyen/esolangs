"""Proof formulas, witnesses and verification policy owned by a language."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Payload = tuple[tuple[int, ...], tuple[int, ...], int, int]


@dataclass(frozen=True)
class CertificationSpec:
    """Evidence and verification settings, independent of backend operation."""

    #: Why a generator cap remains internal to certification.
    internal_cap: str = ""
    documented_sizes: tuple[int, int, float] | None = None
    scaling_rungs: tuple[int, ...] = (8, 10, 12)
    size_bound: Callable[[int], int] | None = None
    layout_switch: tuple[int, ...] = ()
    #: Admitted controls when a generic corpus exceeds a proved cap.
    benchmark_tables: tuple[str, ...] = ()
    slow_scaling: bool = False
    slow_width_sweep: bool = False
    reader_checked: bool = False
    #: Split a snapshot into data, control, program counter and flag bits.
    payload: Callable[[Any], Payload] | None = None
    fuzz_max_digits: int | None = None
