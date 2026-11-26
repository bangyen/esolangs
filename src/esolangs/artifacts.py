"""Immutable runnable programs and input-binding templates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from inspect import getattr_static
from reprlib import recursive_repr

import esolangs
from esolangs._bindings import (
    TEMPLATE_CHAR,
    Setters,
    _stored_items,
    check_setters,
    fill_spans,
    validate_spans,
)
from esolangs.compressed import CompressedText, _freeze_compressed
from esolangs.exceptions import ArgumentError, EsolangError, ProgramError, TemplateError
from esolangs.limits import ExecutionLimits
from esolangs.raster import Raster
from esolangs.results import ExecutionResult
from esolangs.runtime._program import Program
from esolangs.runtime._proof import (
    CycleDecision,
    TerminationResult,
    checked_termination,
)
from esolangs.runtime._validate import (
    _has_backing_type,
    check_bit_count,
    check_bits,
    check_input_arity,
    check_scale,
    check_width,
)
from esolangs.runtime.memory import repr_value

__all__ = [
    "Artifact",
    "BooleanEvaluation",
    "BoundRow",
    "ProgramArtifact",
    "TemplateArtifact",
    "TemplateBindings",
]

from esolangs.settings import DialectSettings


@dataclass(frozen=True, slots=True)
class BooleanEvaluation:
    """Answer bit as ``read_answer`` spells it, the observed IO, and any proof."""

    answer: str
    observation: ExecutionResult
    termination: CycleDecision | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Require a bit backed by completed execution or a termination proof."""
        answer = self.answer
        if type(answer) is not str and _has_backing_type(answer, str):
            answer = str.__str__(answer)
            object.__setattr__(self, "answer", answer)
        if type(answer) is not str or answer not in ("0", "1"):
            raise ArgumentError("a Boolean evaluation requires an answer bit")
        if not _has_backing_type(self.observation, ExecutionResult):
            raise ArgumentError(
                "a Boolean evaluation requires an execution observation"
            )
        if self.termination is not None:
            try:
                checked_termination(
                    TerminationResult(self.observation, self.termination)
                )
            except ValueError as error:
                raise ArgumentError(str(error)) from error
        elif self.observation.completion is None:
            raise ArgumentError("a Boolean evaluation requires completion evidence")


def _origin(
    language: str, settings: DialectSettings | None
) -> tuple[str, DialectSettings | None]:
    """Validate provenance and retain the stored settings without subclass hooks."""
    if not _has_backing_type(language, str):
        raise ArgumentError("an artifact requires a language")
    language = str.__str__(language)
    if not language.strip():
        raise ArgumentError("an artifact requires a language")
    if settings is None:
        return language, None
    if not _has_backing_type(settings, DialectSettings):
        raise ArgumentError("settings must be a DialectSettings or None")
    schema = settings._schema  # noqa: SLF001
    owner = schema.language
    if owner != language:
        from esolangs.registry._catalog import _same_origin_spelling

        if not _same_origin_spelling(language, owner):
            raise ArgumentError(f"dialect settings belong to {owner}, not {language}")
    if type(settings) is DialectSettings:
        settings.options()
    else:
        settings = DialectSettings(schema, **dict(settings._items))  # noqa: SLF001
    return owner, settings


def _restore_artifact_slots(artifact: Artifact, state: list[object]) -> None:
    for item, value in zip(fields(artifact), state, strict=True):
        object.__setattr__(artifact, item.name, value)


@dataclass(frozen=True, slots=True)
class BoundRow:
    """Runnable artifact and literal stdin for one Boolean row."""

    program: ProgramArtifact[Program]
    stdin: str


class _CatalogOwner:
    """Live evaluation scope. Portable and pickle records carry source data only."""

    __slots__ = ("_catalog",)

    def _evaluation_catalog(
        self, catalog: esolangs.registry.Catalog | None
    ) -> esolangs.registry.Catalog | None:
        return catalog if catalog is not None else getattr(self, "_catalog", None)


@dataclass(frozen=True, slots=True)
class ProgramArtifact[Source: Program](_CatalogOwner):
    """Runnable source with its language and retained dialect choices."""

    source: Source
    language: str
    settings: DialectSettings | None = field(default=None, kw_only=True)
    scale: int | None = field(default=None, kw_only=True)
    input_arity: int | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Validate source storage and explicit provenance."""
        kind = type(self.source)
        if issubclass(kind, TemplateArtifact):
            raise TemplateError("fill the template before declaring runnable source")
        if not issubclass(kind, (str, Raster, CompressedText)):
            raise ProgramError("a program needs text, compressed source, or a raster")
        if _has_backing_type(self.source, str):
            object.__setattr__(self, "source", str.__str__(self.source))
        elif _has_backing_type(self.source, CompressedText):
            object.__setattr__(self, "source", _freeze_compressed(self.source))
        owner, settings = _origin(self.language, self.settings)
        object.__setattr__(self, "language", owner)
        if settings is not self.settings:
            object.__setattr__(self, "settings", settings)
        if self.input_arity is not None:
            arity = check_input_arity(self.input_arity)
            if type(self.input_arity) is not int:
                object.__setattr__(self, "input_arity", arity)
        if issubclass(kind, Raster):
            if self.scale is not None:
                object.__setattr__(self, "scale", check_scale(self.scale))
        elif self.scale is not None:
            raise ArgumentError("scale is only supported for raster programs")

    def __setstate__(self, state: list[object]) -> None:
        """Restore exactly the current pickle fields."""
        _restore_artifact_slots(self, state)

    @recursive_repr()
    def __repr__(self) -> str:
        """Represent source and metadata, including uncapped integer metadata."""
        return (
            f"{type(self).__qualname__}(source={self.source!r}, "
            f"language={self.language!r}, settings={self.settings!r}, "
            f"scale={repr_value(self.scale)}, "
            f"input_arity={repr_value(self.input_arity)})"
        )

    def bind(self, bits: list[int] | tuple[int, ...]) -> BoundRow:
        """Return this row's runnable program and stdin."""
        from esolangs.operations.evaluation import _row_binder

        _, _, bind = _row_binder(self, catalog=self._evaluation_catalog(None))
        return bind(bits)

    def evaluate(
        self,
        bits: list[int] | tuple[int, ...],
        *,
        limits: ExecutionLimits | None = None,
        catalog: esolangs.registry.Catalog | None = None,
    ) -> BooleanEvaluation:
        """Run a Boolean row in its owning catalog or an explicit override."""
        from esolangs.operations.evaluation import evaluate_artifact

        return evaluate_artifact(
            self, bits, limits=limits, catalog=self._evaluation_catalog(catalog)
        )


@dataclass(frozen=True, slots=True)
class TemplateBindings:
    """Ordered, equal-width input bindings, independent of source storage."""

    char: str = field(default=TEMPLATE_CHAR, kw_only=True)
    setters: Setters = field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        """Freeze bindings and require equal-width alternatives."""
        if not _has_backing_type(self.char, str) or str.__len__(self.char) != 1:
            raise TemplateError("template char must be one character")
        object.__setattr__(self, "char", str.__str__(self.char))
        try:
            setters = check_setters(self.setters)
            object.__setattr__(self, "setters", setters)
        except EsolangError:
            raise
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
        spans: Sequence[tuple[int, int]],
    ) -> str:
        """Bind integer bits in source, refusing missing or stray runs."""
        inputs = len(self.setters)
        bits = check_bits(bits, "bits", allow_empty=inputs == 0)
        check_bit_count(bits, inputs, "template")
        if not _has_backing_type(source, str):
            raise TemplateError("template source must be text")
        source = str.__str__(source)
        try:
            frozen = tuple(_freeze_span(span) for span in _stored_items(spans))
            validate_spans(source, self.char, self.setters, frozen)
            return fill_spans(source, self.setters, bits, frozen)
        except EsolangError:
            raise
        except (TypeError, ValueError) as error:
            raise TemplateError(str(error)) from error


def _freeze_span(span: tuple[int, int]) -> tuple[int, int]:
    """Freeze actual tuple offsets without dispatching subclass methods."""
    if not _has_backing_type(span, tuple):
        raise ValueError("template spans must be pairs of offsets")
    start, end = tuple.__iter__(span)
    return (
        int.__int__(start)
        if type(start) is not bool and _has_backing_type(start, int)
        else start,
        int.__int__(end)
        if type(end) is not bool and _has_backing_type(end, int)
        else end,
    )


@dataclass(frozen=True, slots=True)
class TemplateArtifact(_CatalogOwner):
    """Text with explicit input bindings; never runnable source.

    Generated templates retain the requested width and balance. Older records
    may have only a width or no layout metadata.
    """

    source: str
    language: str
    bindings: TemplateBindings
    settings: DialectSettings | None = field(default=None, kw_only=True)
    spans: tuple[tuple[int, int], ...] = field(kw_only=True)
    generation_width: int | None = field(
        default=None, kw_only=True, repr=False, compare=False
    )

    generation_balance: bool | None = field(
        default=None, kw_only=True, repr=False, compare=False
    )

    def _check_layout(self) -> None:
        width = check_width(self.generation_width)
        balance = self.generation_balance
        if balance is not None and type(balance) is not bool:
            raise TemplateError("generation_balance must be True, False or None")
        if balance and width is not None:
            raise TemplateError("balanced templates cannot have a generation width")
        object.__setattr__(self, "generation_width", width)

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Use named pickle state for frozen slotted dataclass subclasses."""
        super(TemplateArtifact, cls).__init_subclass__(**kwargs)
        methods = ("__getstate__", "__setstate__")
        # Frozen slots dataclasses otherwise replace inherited pickle hooks.
        if all(
            method not in cls.__dict__
            and getattr_static(cls, method) is TemplateArtifact.__dict__[method]
            for method in methods
        ):
            for method in methods:
                setattr(cls, method, TemplateArtifact.__dict__[method])

    def __post_init__(self) -> None:
        """Require every placeholder to belong to an input."""
        if not _has_backing_type(self.source, str) or not _has_backing_type(
            self.bindings, TemplateBindings
        ):
            raise TemplateError("template needs text source and TemplateBindings")
        object.__setattr__(self, "source", str.__str__(self.source))
        owner, settings = _origin(self.language, self.settings)
        object.__setattr__(self, "language", owner)
        if settings is not self.settings:
            object.__setattr__(self, "settings", settings)
        bindings = self.bindings
        if type(bindings) is not TemplateBindings:
            bindings = TemplateBindings(char=bindings.char, setters=bindings.setters)
            object.__setattr__(self, "bindings", bindings)
        try:
            if not _has_backing_type(self.spans, tuple):
                raise ValueError("template needs one span per input")
            spans = tuple(_freeze_span(span) for span in tuple.__iter__(self.spans))
            validate_spans(self.source, bindings.char, bindings.setters, spans)
            object.__setattr__(self, "spans", spans)
        except EsolangError:
            raise
        except (TypeError, ValueError) as error:
            raise TemplateError(str(error)) from error

        self._check_layout()

    def __getstate__(self) -> dict[str, object]:
        """Store template fields by name."""
        return {item.name: getattr(self, item.name) for item in fields(self)}

    def __setstate__(self, state: dict[str, object]) -> None:
        """Restore exactly the fields of the template being unpickled."""
        if isinstance(state, dict) and "generation_balance" not in state:
            state = {**state, "generation_balance": None}
        if not isinstance(state, dict) or state.keys() != {
            item.name for item in fields(self)
        }:
            raise ValueError("template pickle requires all named fields")
        for name, value in state.items():
            object.__setattr__(self, name, value)
        self._check_layout()

    def bind(self, bits: list[int] | tuple[int, ...]) -> BoundRow:
        """Return this row's runnable program and stdin."""
        from esolangs.operations.evaluation import _row_binder

        _, _, bind = _row_binder(self, catalog=self._evaluation_catalog(None))
        return bind(bits)

    def evaluate(
        self,
        bits: list[int] | tuple[int, ...],
        *,
        limits: ExecutionLimits | None = None,
        catalog: esolangs.registry.Catalog | None = None,
    ) -> BooleanEvaluation:
        """Run a Boolean row in its owning catalog or an explicit override."""
        from esolangs.operations.evaluation import evaluate_artifact

        return evaluate_artifact(
            self, bits, limits=limits, catalog=self._evaluation_catalog(catalog)
        )

    def fill(self, bits: list[int] | tuple[int, ...]) -> ProgramArtifact[str]:
        """Bind inputs without rescanning the immutable template's runs.

        Needs no catalog, unlike :func:`esolangs.Language.instantiate`, which also
        checks the language and table and re-wraps.
        """
        inputs = len(self.bindings.setters)
        bits = check_bits(bits, "bits", allow_empty=inputs == 0)
        check_bit_count(bits, inputs, f"{self.language} template")
        filled = ProgramArtifact(
            fill_spans(self.source, self.bindings.setters, bits, self.spans),
            self.language,
            settings=self.settings,
        )
        catalog = self._evaluation_catalog(None)
        return filled if catalog is None else bind_catalog(filled, catalog)


type Artifact = ProgramArtifact[Program] | TemplateArtifact


def bind_catalog[T: _CatalogOwner](
    artifact: T, catalog: esolangs.registry.Catalog
) -> T:
    """Attach the live catalog to a freshly constructed artifact."""
    object.__setattr__(artifact, "_catalog", catalog)
    return artifact
