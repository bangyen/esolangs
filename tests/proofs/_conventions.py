"""Parse the roadmap's parameterized-generator conventions audit.

``docs/roadmap.md`` carries a second live table beside the scaling audit:
one row per embedding generator with a convention still open -- single
embed, constant width, slot order, no spaces, uniform -- with a verdict
per column.  Rows leave as they close, so the table is exactly the open
set, and a generator absent from it is claimed to hold all five.

As with :mod:`tests.proofs._roadmap`, the suite reads the table rather than
carrying its own copy, and the parser adapts to the document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tests.proofs._roadmap import DOC, _unescape

#: The verdict that settles a column.
HOLDS = "Holds"

#: The verdicts the "No spaces" column may carry while open: ``Open`` means
#: the interpreter ignores the spaces (a program with them deleted runs to
#: the same answer), ``Language`` means it reads them as a delimiter or a
#: grid cell.
OPEN = "Open"
LANGUAGE = "Language"

COLUMNS = ("Single embed", "Constant width", "Slot order", "No spaces", "Uniform")


@dataclass(frozen=True)
class ConventionRow:
    """One language's row in the live conventions audit."""

    generator: str
    single_embed: str
    constant_width: str
    slot_order: str
    no_spaces: str
    uniform: str

    @property
    def verdicts(self) -> tuple[str, str, str, str, str]:
        """The five cells, in column order."""
        return (
            self.single_embed,
            self.constant_width,
            self.slot_order,
            self.no_spaces,
            self.uniform,
        )

    @property
    def is_open(self) -> bool:
        """Whether any convention is still unsettled."""
        return any(v != HOLDS for v in self.verdicts)


@dataclass(frozen=True)
class Conventions:
    """The live conventions audit table."""

    rows: tuple[ConventionRow, ...]

    def by_name(self) -> dict[str, ConventionRow]:
        """Rows keyed by the generator's registry display name."""
        return {row.generator: row for row in self.rows}


def load(path: Path | None = None) -> Conventions:
    """Read and parse the live conventions audit."""
    text = (path or DOC).read_text(encoding="utf-8")
    header = re.search(
        r"^\s*\|\s*Language\s*\|\s*" + r"\s*\|\s*".join(COLUMNS) + r"\s*\|\s*$",
        text,
        re.MULTILINE,
    )
    assert header, f"{DOC} no longer carries the conventions audit table"

    rows = []
    for line in text[header.end() :].splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if stripped:
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if set("".join(cells)) <= {"-", " "}:
            continue
        assert len(cells) == 6, f"unexpected conventions row: {line!r}"
        rows.append(ConventionRow(_unescape(cells[0]), *cells[1:]))

    assert rows, f"{DOC} has a conventions audit header but no rows"
    return Conventions(rows=tuple(rows))
