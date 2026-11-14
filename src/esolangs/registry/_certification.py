"""Proof formulas, witnesses and verification policy owned by a language."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.registry._language import LanguageDeclaration

Payload = tuple[tuple[int, ...], tuple[int, ...], int, int]


@dataclass(frozen=True)
class CertificationSpec:
    """Evidence and verification settings, independent of backend operation."""

    #: Why a generator cap remains internal to certification.
    internal_cap: str = ""
    scaling_rungs: tuple[int, ...] = (8, 10, 12)
    size_bound: Callable[[int], int] | None = None
    #: Admitted controls when a generic corpus exceeds a proved cap.
    benchmark_tables: tuple[str, ...] = ()
    slow_scaling: bool = False
    slow_width_sweep: bool = False
    reader_checked: bool = False
    #: Split a snapshot into data, control, program counter and flag bits.
    payload: Callable[[Any], Payload] | None = None
    fuzz_max_digits: int | None = None


_DEFAULT = CertificationSpec()


def load(language: LanguageDeclaration) -> CertificationSpec:
    """Load language-owned evidence only when verification requests it."""
    package = f"esolangs.languages.{language.id}"
    module = package + ".certification"
    try:
        record = import_module(module).CERTIFICATION
    except ModuleNotFoundError as error:
        if error.name not in (package, module):
            raise
        return _DEFAULT
    if not isinstance(record, CertificationSpec):
        raise TypeError(f"{module}.CERTIFICATION must be a CertificationSpec")
    return record
