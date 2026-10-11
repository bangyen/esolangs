"""The metadata a language declares about itself.

A generator module ends with ``LANGUAGE = Language(...)``; the registry
collects those, so a new language is registered where it is written.  This
module imports nothing from the package, so any generator can import it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from esolangs._program import Program
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._slug import canonical_id

# ``generator(truth_table)`` returns a program computing it; the few that lay
# out two dimensions also take a ``width``, hence ``...``.
Generator = Callable[..., Program]
Payload = tuple[tuple[int, ...], tuple[int, ...], int, int]


class SourceKind(StrEnum):
    """The representation an interpreter consumes."""

    TEXT = "text"
    RASTER = "raster"


class Shape(StrEnum):
    """How a generator's program grows with its table."""

    #: A decision tree: a table that ignores an input folds that subtree.
    TREE = "tree"
    #: A sum over the essential inputs: a degenerate table is a smaller one.
    REDUCING = "reducing"
    #: Branch-free: every table of one arity renders to about one length.
    LOOKUP = "lookup"


@dataclass(frozen=True)
class Example:
    """How the committed AND example deviates from a plain reading program.

    ``pair`` or ``setters(template, n)`` makes it a template whose bits are
    embedded (``char`` marks the runs; empty means the shared one);
    ``expected`` is its whole output on the 0,1 row, and ``expected_compared``
    False where that output is junk around a halting answer.
    """

    expected: str = "0"
    pair: tuple[str, str] | None = None
    setters: Callable[[str, int], Any] | None = None
    char: str = ""
    expected_compared: bool = True
    kwargs: tuple[tuple[str, int], ...] = ()
    scale: int = 1
    #: Whether text is unfilled, where ``char`` is also source.
    unfilled: Callable[[str], bool] | None = None
    #: Building it balanced is a medium-length run.
    slow_build: bool = False


@dataclass(frozen=True)
class Language:
    """Everything the package and its tests know about one language."""

    # Identity.  ``id`` defaults to :func:`canonical_id` of the name.
    name: str
    interpreter: str | None = None
    id: str = ""
    #: Other names :func:`~esolangs.registry.resolve` accepts.
    aliases: tuple[str, ...] = ()
    # Source: ``split`` passes ``run()`` one string per line; ``extra`` is
    # the optional-dependency group its interpreter needs (``math``).
    split: bool = False
    #: Source that looks like a file path is still source.
    path_like_source: bool = False
    source_kind: SourceKind = SourceKind.TEXT
    extra: str = ""
    # The Boolean generator, its limits, and how its programs read inputs
    # and give the answer (default: a 0/1 line per input, the bit printed).
    boolean: Generator | None = None
    generator_max_inputs: int | None = None
    generator_restrictions: str = ""
    shape: Shape = Shape.TREE
    #: Why its ``GeneratorCapError`` stays internal; limitations.md's sizes.
    internal_cap: str = ""
    documented_sizes: tuple[int, int, float] | None = None
    #: Validates ``DialectSettings``: one defaulted keyword per setting.
    dialect: Callable[..., Any] | None = None
    #: Valid values per dialect setting, for the ``describe`` schema.
    dialect_values: Mapping[str, tuple[int | str, ...]] | None = None
    contract: BooleanContract = field(default_factory=BooleanContract)
    #: ``wrap(program, width)``: a meaning-preserving reflow, if one exists.
    wrap: Callable[[str, int], str] | None = None
    #: Why ``wrap`` is absent, when a break would change the program.
    no_wrap: str = ""
    #: Whether a template is one of the generator's ``layout(width)``s of
    #: its default build ``plain``; default: equal up to wrapping newlines.
    same_layout: Callable[[str, str, Callable[[int], Any]], bool] | None = None
    #: ``balance(table, default)``: the squarest layout a reflow cannot find.
    balance: Callable[..., Any] | None = None
    #: Some instruction draws at random (``run(seed=...)`` fixes it).
    random: bool = False
    #: What an exhausted read does instead of raising ``EOFError``.
    eof: str = ""
    #: An underfed program raises its own error rather than read past EOF.
    underfed_raises: bool = False
    #: The error an empty program raises, when the spec rejects one.
    empty_program: str = ""
    #: The committed AND example, where the default reader does not fit.
    example: Example = field(default_factory=Example)
    # Growth checks: linear rungs, a size ceiling, a layout switch's arities.
    scaling_rungs: tuple[int, ...] = (8, 10, 12)
    size_bound: Callable[[int], int] | None = None
    layout_switch: tuple[int, ...] = ()
    # Shared sweeps that run long for it: marked slow, or left to its tests.
    slow_scaling: bool = False
    slow_stepping: bool = False
    slow_width_sweep: bool = False
    # Tooling: reader checks, payload split (data, control, pc, flag bits),
    # leak-sweep digits, weekly mutation suites, the README's TUI frame.
    reader_checked: bool = False
    payload: Callable[[Any], Payload] | None = None
    fuzz_max_digits: int | None = None
    weekly_mutation: tuple[str, ...] = ()
    showcase: bool = False

    def __post_init__(self) -> None:
        """Fill the id from the name when none is given."""
        if not self.id:
            object.__setattr__(self, "id", canonical_id(self.name))
        # Embedded inputs are what a template example says: one fact, once.
        template = self.example.pair is not None or self.example.setters is not None
        if self.contract.parameterized and not template:
            raise ValueError(f"{self.name}: parameterized follows example=")
        object.__setattr__(
            self, "contract", replace(self.contract, parameterized=template)
        )
        if self.wrap is not None and self.no_wrap:
            raise ValueError(f"{self.name}: wrap and no_wrap exclude each other")
