"""The metadata a language declares about itself.

A generator module ends with ``LANGUAGE = Language(...)``; the registry
collects those, so a new language is registered where it is written.  This
module imports nothing from the package, so any generator can import it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from esolangs._program import Program
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._slug import canonical_id

# ``generator(truth_table)`` returns a program computing it; the few that lay
# out two dimensions (LaserFuck) also take a ``width``, hence ``...``.
Generator = Callable[..., Program]


class SourceKind(StrEnum):
    """The representation an interpreter consumes."""

    TEXT = "text"
    RASTER = "raster"


@dataclass(frozen=True)
class Example:
    """How the committed AND example deviates from a plain reading program.

    ``pair`` or ``setters(template, n)`` makes it a template whose bits are
    embedded (``char`` marks the runs; empty means the shared one);
    ``expected`` is its whole output on the 0,1 row, and ``expected_compared``
    False where that output is junk around a halting answer.
    """

    expected: str = "0"
    inputs: tuple[str, ...] = ("0", "1")
    pair: tuple[str, str] | None = None
    setters: Callable[[str, int], Any] | None = None
    char: str = ""
    expected_compared: bool = True
    kwargs: tuple[tuple[str, int], ...] = ()
    scale: int = 1


@dataclass(frozen=True)
class Language:
    """Language name, interpreter, source shape, id, and optional generator.

    ``id`` defaults to :func:`canonical_id` of the name; ``contract`` to the
    one-``0``/``1``-line-per-input, printed-bit default.
    """

    name: str
    interpreter: str | None = None
    split: bool = False
    id: str = ""
    boolean: Generator | None = None
    source_kind: SourceKind = SourceKind.TEXT
    generator_max_inputs: int | None = None
    generator_restrictions: str = ""
    contract: BooleanContract = field(default_factory=BooleanContract)
    #: ``wrap(program, width)``: a meaning-preserving reflow, if one exists.
    wrap: Callable[[str, int], str] | None = None
    #: ``balance(table, default)``: the squarest layout, for width-taking
    #: generators whose regimes a plain reflow cannot compare.
    balance: Callable[..., Any] | None = None
    #: Why ``wrap`` is absent, when a break would change the program.
    no_wrap: str = ""
    #: What an exhausted read does instead of raising ``EOFError``.
    eof: str = ""
    #: The error an empty program raises, when the spec rejects one.
    empty_program: str = ""
    example: Example = field(default_factory=Example)

    def __post_init__(self) -> None:
        """Fill the id from the name when none is given."""
        if not self.id:
            object.__setattr__(self, "id", canonical_id(self.name))
        if self.wrap is not None and self.no_wrap:
            raise ValueError(f"{self.name}: wrap and no_wrap exclude each other")
