"""Typed requests crossing the generator/backend boundary."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from esolangs._dialect import Scalar
from esolangs.compressed import CompressedText, _freeze_compressed
from esolangs.exceptions import ArgumentError, EsolangError, ProgramError
from esolangs.generation.algebraic import AffineForm, affine_form
from esolangs.generation.helpers import _validate_truth_table, check_table_text
from esolangs.generation.projection import essential_inputs
from esolangs.generation.template import TemplateLayout
from esolangs.raster import Raster
from esolangs.runtime._program import Program
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.memory import repr_value

type LayoutChoice = Literal["default", "balanced"] | int


def layout_choice(width: int | None, *, balance: bool) -> LayoutChoice:
    """Resolve a request to a default, balanced, or fixed-width layout."""
    if balance:
        return "balanced"
    return "default" if width is None else width


type GeneratedProgram = Program | TemplateLayout


def call_backend[**P, T](
    hook: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    """Expose a backend's value rejection through the public error family."""
    try:
        return hook(*args, **kwargs)
    except EsolangError:
        raise
    except ValueError as error:
        raise ArgumentError(str(error)) from error


@dataclass(frozen=True, slots=True)
class Options:
    """Complete, immutable dialect choices validated by the operation layer."""

    values: tuple[tuple[str, Scalar], ...] = ()

    def __repr__(self) -> str:
        """Represent integer dialect options beyond the decimal digit cap."""
        return f"{type(self).__qualname__}(values={repr_value(self.values)})"

    def integer(self, name: str) -> int:
        """Return a declared integer option; bool is not an integer choice."""
        value = dict(self.values).get(name)
        if type(value) is not int:
            raise ArgumentError(f"backend option {name} requires an integer")
        return value

    def text(self, name: str) -> str:
        """Return a declared string option."""
        value = dict(self.values).get(name)
        if not isinstance(value, str):
            raise ArgumentError(f"backend option {name} requires text")
        return value


@dataclass(frozen=True, slots=True)
class TruthTable:
    """Validated output bits in row order and their input arity."""

    bits: str
    arity: int = field(init=False)
    _essential: tuple[int, ...] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _affine: AffineForm | Literal[False] | None = field(
        default=False, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        """Freeze validated output bits and their arity."""
        bits = check_table_text(self.bits)
        object.__setattr__(self, "bits", bits)
        object.__setattr__(self, "arity", _validate_truth_table(bits))

    def essential_inputs(self) -> tuple[int, ...]:
        """Return the positions that can change the output."""
        result = self._essential
        if result is None:
            result = tuple(essential_inputs(self.bits, self.arity))
            object.__setattr__(self, "_essential", result)
        return result

    def affine(self) -> AffineForm | None:
        """Return the affine form in input order when one exists."""
        result = self._affine
        if result is False:
            result = affine_form(self.bits, self.arity)
            object.__setattr__(self, "_affine", result)
        return result


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """A validated table, layout request and complete dialect choices."""

    table: str
    width: int | None = None
    options: Options = Options()
    balance: bool = False
    truth_table: TruthTable = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Expose the same validated bits to text-based backends."""
        value = TruthTable(self.table)
        object.__setattr__(self, "table", value.bits)
        object.__setattr__(self, "truth_table", value)

    def __repr__(self) -> str:
        """Represent the request even when its integer width exceeds the digit cap."""
        return (
            f"{type(self).__qualname__}(table={self.table!r}, "
            f"width={repr_value(self.width)}, options={self.options!r}"
            f"{', balance=True' if self.balance else ''})"
        )


@dataclass(frozen=True, slots=True)
class BalanceRequest:
    """A table and emitted source to lay out under the same dialect choices."""

    table: str
    source: GeneratedProgram
    options: Options = Options()

    def text_source(self) -> str:
        """Return working text for a declared text balancer, including gzip."""
        source = self.source
        if _has_backing_type(source, TemplateLayout):
            return source.source
        if _has_backing_type(source, CompressedText):
            return "".join(_freeze_compressed(source).chunks())
        if _has_backing_type(source, str):
            return source
        raise ProgramError("text layout requires text source")

    def raster_source(self) -> Raster:
        """Return pixels for a declared raster balancer."""
        source = self.source
        if not _has_backing_type(source, Raster):
            raise ProgramError("raster layout requires raster source")
        return source

    def template_source(self) -> TemplateLayout:
        """Return the template's source and ordered slots for reflow."""
        source = self.source
        if not isinstance(source, TemplateLayout):
            raise TypeError("balancing needs a rendered template with slots")
        return source
