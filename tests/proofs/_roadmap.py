"""Parse the roadmap's live scaling audit into the set the linearity test uses.

``docs/roadmap.md`` carries the live audit table for the "Linear Boolean
generators" item: one row per language whose scaling is not yet settled, with a
verdict for generation time and for output size.  Rows are *deleted* from it as
they close, so the table is exactly the open set -- `350d2e2e` trimmed twenty-one
rows that had been confirmed linear.

The linearity contract reads that table rather than carrying its own list, for
the same reason :mod:`tests.proofs._ledger` reads ``proofs.md``: a duplicated
list is free to drift, and this one has drifted before.  Closing a row then
means one edit, to the doc, and the contract immediately starts *demanding*
linearity of the generator that left.

The parser adapts to the document, never the other way round.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Resolved from this file, not the working directory: the suite runs from the
#: repo root, from ``just``, and from a worktree.
DOC = Path(__file__).resolve().parents[2] / "docs" / "roadmap.md"

#: Verdicts that settle a column as linear.  Two spellings are in use -- the
#: trimmed table wrote ``O(T)`` for LaserFuck and ``Linear`` for the rest --
#: and both are affirmative, so both are read rather than one being normalized
#: away in the doc.
SETTLED = frozenset({"Linear", "O(T)"})


@dataclass(frozen=True)
class AuditRow:
    """One language's row in the live scaling audit."""

    generator: str
    generation_time: str
    output_size: str

    @property
    def size_is_settled(self) -> bool:
        """Whether the Output size column claims a linear bound."""
        return self.output_size in SETTLED


@dataclass(frozen=True)
class Audit:
    """The live scaling audit table."""

    rows: tuple[AuditRow, ...]

    def by_name(self) -> dict[str, AuditRow]:
        """Rows keyed by the generator's registry display name."""
        return {row.generator: row for row in self.rows}

    @property
    def unsettled(self) -> frozenset[str]:
        """Generators whose output size the roadmap does not claim is linear.

        These are the expected failures of the linearity contract.  A generator
        absent from the table is one the roadmap has already closed, and is
        therefore held to the bound.
        """
        return frozenset(row.generator for row in self.rows if not row.size_is_settled)


def _unescape(cell: str) -> str:
    r"""Undo the markdown escaping a table cell needs (``S\*bleq``)."""
    return re.sub(r"\\(.)", r"\1", cell).strip()


def load(path: Path | None = None) -> Audit:
    """Read and parse the live scaling audit."""
    text = (path or DOC).read_text(encoding="utf-8")

    # The table sits inside an indented list item, so the pipes are not at
    # column zero; anchor on the header rather than on line starts.
    header = re.search(
        r"^\s*\|\s*Language\s*\|\s*Generation time\s*\|\s*Output size\s*\|\s*$",
        text,
        re.MULTILINE,
    )
    assert header, f"{DOC} no longer carries the live scaling audit table"

    rows = []
    for line in text[header.end() :].splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if stripped:
                break  # the table ended at the following prose
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if set("".join(cells)) <= {"-", " "}:
            continue  # the ``| --- |`` separator
        assert len(cells) == 3, f"unexpected audit row: {line!r}"
        rows.append(AuditRow(_unescape(cells[0]), cells[1], cells[2]))

    assert rows, f"{DOC} has a scaling audit header but no rows"
    return Audit(rows=tuple(rows))
