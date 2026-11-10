"""Immutable runnable programs and input-binding templates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from esolangs.compressed import CompressedText
from esolangs.exceptions import ArgumentError, ProgramError, TemplateError
from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    Setters,
    check_setters,
    fill_runs,
    runs,
)
from esolangs.raster import Raster
from esolangs.runtime._program import Program
from esolangs.runtime._validate import check_bits, check_provenance, check_scale

__all__ = ["Artifact", "ProgramArtifact", "TemplateArtifact", "TemplateBindings"]

from esolangs.settings import DialectSettings


def _origin(source: object, language: str, settings: DialectSettings | None) -> str:
    """Canonicalize provenance without interpreting the source."""
    name = check_provenance(language, settings)
    if name is None:
        raise ArgumentError("an artifact requires a language")
    retained = source.language if isinstance(source, (Raster, CompressedText)) else None
    if retained is not None and retained != name:
        raise ProgramError(f"source belongs to {retained}, not {name}")
    return name


@dataclass(frozen=True, slots=True)
class ProgramArtifact[Source: Program]:
    """Runnable source with its language and retained dialect choices."""

    source: Source
    language: str
    settings: DialectSettings | None = None
    scale: int | None = None

    def __post_init__(self) -> None:
        """Validate source storage and retain canonical provenance."""
        if isinstance(self.source, TemplateArtifact):
            raise TemplateError("fill the template before declaring runnable source")
        if not isinstance(self.source, (str, Raster, CompressedText)):
            raise ProgramError("a program needs text, compressed source, or a raster")
        object.__setattr__(
            self, "language", _origin(self.source, self.language, self.settings)
        )
        if self.settings is None and isinstance(self.source, (Raster, CompressedText)):
            retained = self.source.settings
            if retained is not None:
                check_provenance(self.language, retained)
                object.__setattr__(self, "settings", retained)
        if isinstance(self.source, Raster):
            scale = self.source.scale if self.scale is None else self.scale
            if scale is not None:
                check_scale(scale)
            object.__setattr__(self, "scale", scale)
        elif self.scale is not None:
            raise ArgumentError("scale is only supported for raster programs")


@dataclass(frozen=True, slots=True)
class TemplateBindings:
    """Ordered, equal-width input bindings, independent of source storage."""

    char: str = TEMPLATE_CHAR
    setters: Setters = ()

    def __post_init__(self) -> None:
        """Freeze bindings and require equal-width alternatives."""
        if not isinstance(self.char, str) or len(self.char) != 1:
            raise TemplateError("template char must be one character")
        try:
            setters = check_setters(self.setters)
            if any(not isinstance(item, str) for pair in setters for item in pair):
                raise TemplateError("setters must be pairs of strings")
            object.__setattr__(self, "setters", setters)
        except (TypeError, ValueError) as error:
            raise TemplateError(str(error)) from error

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
    # Re-parsing immutable spans added 20-26% to fills at n=2/4/6.
    _spans: tuple[tuple[int, int], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Require every placeholder to belong to an input."""
        if not isinstance(self.source, str) or not isinstance(
            self.bindings, TemplateBindings
        ):
            raise TemplateError("template needs text source and TemplateBindings")
        object.__setattr__(
            self, "language", _origin(self.source, self.language, self.settings)
        )
        try:
            object.__setattr__(
                self,
                "_spans",
                tuple(runs(self.source, self.bindings.char, self.bindings.setters)),
            )
        except (TypeError, ValueError) as error:
            raise TemplateError(str(error)) from error

    def fill(self, bits: Sequence[int]) -> ProgramArtifact[str]:
        """Bind inputs without rescanning the immutable template's runs."""
        return ProgramArtifact(
            self.bindings.fill(self.source, bits, spans=self._spans),
            self.language,
            self.settings,
        )


type Artifact = ProgramArtifact[Program] | TemplateArtifact
