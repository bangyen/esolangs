"""The metadata a language declares about itself.

A generator module ends with ``LANGUAGE = Language(...)``; the registry
collects those, so a new language is registered where it is written.  This
module keeps declarations independent of example generation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from esolangs.generation.helpers import TEMPLATE_CHAR, Setters, check_setters
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._slug import canonical_id
from esolangs.runtime._definition import RuntimeSpec, SourceKind
from esolangs.runtime._program import Program

# ``generator(truth_table)`` returns a program computing it; the few that lay
# out two dimensions also take a ``width``, hence ``...``.
Generator = Callable[..., Program]
ProofFormula = tuple[Callable[[int, str], float], bool, tuple[int, ...]]
Payload = tuple[tuple[int, ...], tuple[int, ...], int, int]


class Shape(StrEnum):
    """How a generator's program grows with its table."""

    #: A decision tree: a table that ignores an input folds that subtree.
    TREE = "tree"
    #: A sum over the essential inputs: a degenerate table is a smaller one.
    REDUCING = "reducing"
    #: Branch-free: every table of one arity renders to about one length.
    LOOKUP = "lookup"


@dataclass(frozen=True)
class TemplateSpec:
    """How a Boolean backend embeds inputs, independently of its examples."""

    pair: tuple[str, str] | None = None
    setters: Callable[[str, int], Setters] | None = None
    char: str = TEMPLATE_CHAR
    #: Whether text is unfilled, where ``char`` is also source.
    unfilled: Callable[[str], bool] | None = None

    def __post_init__(self) -> None:
        """Require one binding rule and a single placeholder character."""
        if (self.pair is None) == (self.setters is None):
            raise ValueError("exactly one of pair and setters")
        if len(self.char) != 1:
            raise ValueError("template char must be one character")
        if self.pair is not None:
            check_setters((self.pair,))

    def bindings(self, template: str, inputs: int) -> Setters:
        """Return ordered zero/one substitutions for this template."""
        if self.pair is not None:
            return (self.pair,) * inputs
        assert self.setters is not None  # checked at declaration
        return self.setters(template, inputs)


@dataclass(frozen=True)
class Example:
    """Invocation and expected output of a committed example."""

    table: str = "0001"
    bits: tuple[int, ...] = (0, 1)
    expected: str = "0"
    expected_compared: bool = True
    kwargs: tuple[tuple[str, int], ...] = ()
    scale: int = 1
    #: Building it balanced is a medium-length run.
    slow_build: bool = False


@dataclass(frozen=True)
class Language:
    """Everything the package and its tests know about one language."""

    # Identity.  ``id`` defaults to :func:`canonical_id` of the name.
    name: str
    runtime: RuntimeSpec = field(default_factory=RuntimeSpec)
    id: str = ""
    #: Other names :func:`~esolangs.registry.resolve` accepts.
    aliases: tuple[str, ...] = ()
    #: The source is a 2D grid, judged by area (rows times the longest row):
    #: the default build races by area and Scaling states ``cells``.
    grid: bool = False
    # The Boolean generator, its limits, and how its programs read inputs
    # and give the answer (default: a 0/1 line per input, the bit printed).
    boolean: Generator | None = None
    template: TemplateSpec | None = None
    generator_max_inputs: int | None = None
    generator_restrictions: str = ""
    shape: Shape = Shape.TREE
    #: Why its ``GeneratorCapError`` stays internal; limitations.md's sizes.
    internal_cap: str = ""
    documented_sizes: tuple[int, int, float] | None = None
    contract: BooleanContract = field(default_factory=BooleanContract)
    #: ``wrap(program, width)``: a meaning-preserving reflow, if one exists.
    wrap: Callable[[str, int], str] | None = None
    wrap_multiline: bool = False
    #: ``wrap_balance(program)``: a language-owned source reflow for balance.
    wrap_balance: Callable[[str], str] | None = None
    #: Why ``wrap`` is absent, when a break would change the program.
    no_wrap: str = ""
    #: Whether a template is one of the generator's ``layout(width)``s of
    #: its default build ``plain``; default: equal up to wrapping newlines.
    same_layout: Callable[[str, str, Callable[[int], Any]], bool] | None = None
    #: ``balance(table, default)``: the squarest layout a reflow cannot find.
    balance: Callable[..., Any] | None = None
    #: The committed example, where the default AND reader does not fit.
    example: Example = field(default_factory=Example)
    # Growth checks: linear rungs, a size ceiling, a layout switch's arities.
    scaling_rungs: tuple[int, ...] = (8, 10, 12)
    size_bound: Callable[[int], int] | None = None
    layout_switch: tuple[int, ...] = ()
    #: Executable baseline controls when the default corpus exceeds a proved cap.
    benchmark_tables: tuple[str, ...] = ()
    proof_execution: ProofFormula | None = None
    proof_workspace: ProofFormula | None = None
    # Shared sweeps that run long for it: marked slow, or left to its tests.
    slow_scaling: bool = False
    slow_width_sweep: bool = False
    # Tooling: reader checks, payload split (data, control, pc, flag bits),
    # leak-sweep digits.
    reader_checked: bool = False
    payload: Callable[[Any], Payload] | None = None
    fuzz_max_digits: int | None = None

    def __post_init__(self) -> None:
        """Fill the id from the name when none is given."""
        if not self.id:
            object.__setattr__(self, "id", canonical_id(self.name))
        if self.wrap is not None and self.no_wrap:
            raise ValueError(f"{self.name}: wrap and no_wrap exclude each other")

    @property
    def source_suffix(self) -> str:
        """Return the file suffix this language's source is saved under."""
        if self.runtime.source_kind is SourceKind.RASTER:
            return ".png"
        return ".txt.gz" if self.runtime.compressed_source else ".txt"

    @property
    def parameterized(self) -> bool:
        """Whether the backend embeds inputs instead of reading stdin."""
        return self.template is not None
