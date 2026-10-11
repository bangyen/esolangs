"""Read the structured scaling audit used by proof contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Verdicts that settle a column as linear.  Two spellings are in use -- the
#: trimmed table wrote ``O(T)`` for LaserFuck and ``Linear`` for the rest --
#: and both are affirmative, so both are read rather than one being normalized
#: away in the doc.
SETTLED = frozenset({"Linear", "O(T)"})

#: The totality column's settled verdict.  The other spellings a row may carry
#: are the ``proofs/index.md`` ledger's own labels, ``Cap`` and ``Exception``.
TOTAL = "Total"


@dataclass(frozen=True)
class AuditRow:
    """One language's row in the live scaling audit."""

    generator: str
    totality: str
    generation_time: str
    output_size: str

    @property
    def size_is_settled(self) -> bool:
        """Whether the Output size column claims a linear bound."""
        return self.output_size in SETTLED

    @property
    def is_open(self) -> bool:
        """Whether any of the three axes is still unsettled."""
        return not (
            self.totality == TOTAL
            and self.generation_time in SETTLED
            and self.output_size in SETTLED
        )


@dataclass(frozen=True)
class Audit:
    """The live scaling audit table."""

    rows: tuple[AuditRow, ...]

    def by_name(self) -> dict[str, AuditRow]:
        """Rows keyed by the generator's registry display name."""
        return {row.generator: row for row in self.rows}

    @property
    def unsettled(self) -> frozenset[str]:
        """Generators exempt from the measured size regression."""
        return frozenset(
            row.generator
            for row in self.rows
            if not row.size_is_settled and row.output_size != "Measured"
        )


def load(path: Path | None = None) -> Audit:
    """Read and parse the live scaling audit."""
    from scripts.generate import load as load_status

    _, rows = load_status() if path is None else load_status(path)
    return Audit(
        rows=tuple(
            AuditRow(
                row.generator,
                row.totality,
                row.generation_time,
                row.output_size,
            )
            for row in rows
        )
    )
