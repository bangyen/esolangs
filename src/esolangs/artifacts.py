"""Immutable runnable programs and input-binding templates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

from esolangs._bindings import (
    TEMPLATE_CHAR,
    Setters,
    check_setters,
    fill_runs,
    runs,
    validate_spans,
)
from esolangs.compressed import CompressedText
from esolangs.exceptions import ArgumentError, ProgramError, TemplateError
from esolangs.limits import ExecutionLimits
from esolangs.raster import Raster
from esolangs.results import ExecutionResult
from esolangs.runtime._program import Program
from esolangs.runtime._proof import CycleDecision
from esolangs.runtime._validate import check_bit_count, check_bits, check_scale

__all__ = [
    "Artifact",
    "BooleanEvaluation",
    "ProgramArtifact",
    "TemplateArtifact",
    "TemplateBindings",
]

from esolangs.settings import DialectSettings


class BooleanEvaluation(NamedTuple):
    """Answer with the observed IO and, for termination answers, a proof."""

    bit: str
    observation: ExecutionResult
    termination: CycleDecision | None = None


def _origin(language: str, settings: DialectSettings | None) -> str:
    """Validate explicit provenance without consulting the language catalog."""
    if not isinstance(language, str) or not language.strip():
        raise ArgumentError("an artifact requires a language")
    if settings is not None:
        if not isinstance(settings, DialectSettings):
            raise ArgumentError("settings must be a DialectSettings or None")
        if settings.language != language:
            raise ArgumentError(
                f"dialect settings belong to {settings.language}, not {language}"
            )
        settings.options(language)
    return language


@dataclass(frozen=True, slots=True)
class ProgramArtifact[Source: Program]:
    """Runnable source with its language and retained dialect choices."""

    source: Source
    language: str
    settings: DialectSettings | None = None
    scale: int | None = None
    input_arity: int | None = None

    def __post_init__(self) -> None:
        """Validate source storage and explicit provenance."""
        if isinstance(self.source, TemplateArtifact):
            raise TemplateError("fill the template before declaring runnable source")
        if not isinstance(self.source, (str, Raster, CompressedText)):
            raise ProgramError("a program needs text, compressed source, or a raster")
        object.__setattr__(self, "language", _origin(self.language, self.settings))
        if self.input_arity is not None and (
            type(self.input_arity) is not int or self.input_arity < 1
        ):
            raise ArgumentError("input_arity must be a positive integer")
        if isinstance(self.source, Raster):
            if self.scale is not None:
                check_scale(self.scale)
        elif self.scale is not None:
            raise ArgumentError("scale is only supported for raster programs")

    def evaluate(
        self,
        bits: list[int] | tuple[int, ...],
        *,
        limits: ExecutionLimits | None = None,
    ) -> BooleanEvaluation:
        """Run one Boolean row and return its answer and execution evidence."""
        from esolangs.operations.evaluation import evaluate

        return evaluate(self, bits, limits=limits)


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
        bits: list[int] | tuple[int, ...],
        *,
        spans: Sequence[tuple[int, int]] | None = None,
    ) -> str:
        """Bind integer bits in source, refusing missing or stray runs."""
        bits = check_bits(bits, "bits")
        check_bit_count(bits, self.inputs, "template")
        return fill_runs(source, self.char, self.setters, bits, spans=spans)


@dataclass(frozen=True, slots=True)
class TemplateArtifact:
    """Text with explicit input bindings; never runnable source."""

    source: str
    language: str
    bindings: TemplateBindings
    settings: DialectSettings | None = None
    spans: tuple[tuple[int, int], ...] | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Require every placeholder to belong to an input."""
        if not isinstance(self.source, str) or not isinstance(
            self.bindings, TemplateBindings
        ):
            raise TemplateError("template needs text source and TemplateBindings")
        object.__setattr__(self, "language", _origin(self.language, self.settings))
        try:
            if self.spans is None:
                spans = tuple(
                    runs(self.source, self.bindings.char, self.bindings.setters)
                )
                object.__setattr__(self, "spans", spans)
            else:
                validate_spans(
                    self.source, self.bindings.char, self.bindings.setters, self.spans
                )
        except (TypeError, ValueError) as error:
            raise TemplateError(str(error)) from error

    def evaluate(
        self,
        bits: list[int] | tuple[int, ...],
        *,
        limits: ExecutionLimits | None = None,
    ) -> BooleanEvaluation:
        """Run one Boolean row and return its answer and execution evidence."""
        from esolangs.operations.evaluation import evaluate

        return evaluate(self, bits, limits=limits)

    def fill(self, bits: list[int] | tuple[int, ...]) -> ProgramArtifact[str]:
        """Bind inputs without rescanning the immutable template's runs."""
        bits = check_bits(bits, "bits")
        check_bit_count(bits, self.bindings.inputs, f"{self.language} template")
        return ProgramArtifact(
            self.bindings.fill(self.source, bits, spans=self.spans),
            self.language,
            self.settings,
        )


type Artifact = ProgramArtifact[Program] | TemplateArtifact
