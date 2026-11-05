"""Execution choices shared by runners and machine constructors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.settings import DialectSettings


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Explicit options for one execution; reproducible machines use runtime seeds."""

    scale: int | None = None
    seed: int | None = None
    reproducible: bool = False
    settings: DialectSettings | None = None
