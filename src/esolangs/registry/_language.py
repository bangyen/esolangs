"""The metadata a language declares about itself.

A generator module ends with ``LANGUAGE = Language(...)``; the registry
collects those, so a new language is registered where it is written.  This
module imports nothing from the package, so any generator can import it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from esolangs._program import Program
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._slug import canonical_id

# A generator: ``generator(truth_table)`` returns a program computing it.
# Most take only the table; the few that lay their program out in two
# dimensions (LaserFuck, which folds its beam's track) also accept a
# ``width`` bounding the columns, since a shape cannot be reflowed after the
# fact the way a single long line can.  ``...`` keeps both arities callable
# with the table alone, which is how every width-less caller invokes them.
Generator = Callable[..., Program]


class SourceKind(StrEnum):
    """The representation an interpreter consumes."""

    TEXT = "text"
    RASTER = "raster"


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

    def __post_init__(self) -> None:
        """Fill the id from the name when none is given."""
        if not self.id:
            object.__setattr__(self, "id", canonical_id(self.name))
