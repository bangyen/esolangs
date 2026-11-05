"""Explicit program and template records behind source compatibility adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from esolangs.exceptions import TemplateError
from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    Setters,
    check_setters,
    fill_runs,
    runs,
)
from esolangs.runtime._program import Program
from esolangs.runtime._validate import check_bits

if TYPE_CHECKING:
    from esolangs.settings import DialectSettings


@dataclass(frozen=True, slots=True)
class ProgramArtifact[Source: Program]:
    """Runnable source with its language and retained dialect choices."""

    source: Source
    language: str
    settings: DialectSettings | None = None
    scale: int | None = None


@dataclass(frozen=True, slots=True)
class TemplateBindings:
    """Ordered, equal-width input bindings, independent of source storage."""

    char: str = TEMPLATE_CHAR
    setters: Setters = ()

    def __post_init__(self) -> None:
        """Freeze bindings and require equal-width alternatives."""
        object.__setattr__(self, "setters", check_setters(self.setters))

    @property
    def inputs(self) -> int:
        """How many inputs the template embeds."""
        return len(self.setters)

    def fill(
        self,
        source: str,
        bits: Sequence[int],
        *,
        spans: Sequence[tuple[int, int]] | None = None,
    ) -> str:
        """Bind integer bits in source, refusing missing or stray runs."""
        bits = check_bits(bits, "bits")
        if len(bits) != self.inputs:
            raise TemplateError(
                f"this template has {self.inputs} inputs, but {len(bits)} "
                f"bits were given"
            )
        return fill_runs(source, self.char, self.setters, bits, spans=spans)


@dataclass(frozen=True, slots=True)
class TemplateArtifact:
    """Text with explicit input bindings; never runnable source."""

    source: str
    language: str
    bindings: TemplateBindings
    settings: DialectSettings | None = None
    # Re-parsing on adapter conversion added 20-26% to fills at n=2/4/6.
    _spans: tuple[tuple[int, int], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Require every placeholder to belong to an input."""
        object.__setattr__(
            self,
            "_spans",
            tuple(runs(self.source, self.bindings.char, self.bindings.setters)),
        )

    def fill(self, bits: Sequence[int]) -> ProgramArtifact[str]:
        """Bind inputs without rescanning the immutable template's runs."""
        return ProgramArtifact(
            self.bindings.fill(self.source, bits, spans=self._spans),
            self.language,
            self.settings,
        )


type Artifact = ProgramArtifact[Program] | TemplateArtifact
