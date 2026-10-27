"""Tiangou Boolean program generator: one marker per true row.

Jumps go backward only, so a counter walks the table marking each true row
(``: <``), and ``" : >`` jumps back to marker ``row + 1``.  A true row
re-runs the walk's tail to ``[T + 1, T + 1]``; a false row stays at
``[T + 1, row + 1]``.  The tail's ``- >`` loops on equal tops to print 1, and
prints 0 otherwise.  Ignored inputs are read as 0 and dropped, so a
constant table walks one row.

Size:
    6T + 4w + 34n + 57 chars for w true rows, every input essential;
    n=4 parity: 321 chars
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.registry._language import Language, Shape

#: Negate the top: ``p : -`` pushes 0, and ``-`` pops it first.
_NEG = "p : - -"


def tiangou(truth_table: str) -> str:
    """Build a Tiangou program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    parts = ["p p p : - p : -"]
    for i in range(n):
        # acc -> 2 * acc + bit; an ignored read is zeroed and subtracted.
        parts.append(
            f': {_NEG} " - i {_NEG} - {_NEG}' if i in essential else 'i : - " -'
        )
    parts.append(f"p {_NEG} - {_NEG} p")
    table = read_at(truth_table, essential, n)
    parts += [': < q " -' if bit == "1" else 'q " -' for bit in table]
    parts.append('" : > p : - < - > o')
    return " ".join(parts)


LANGUAGE = Language(
    "Tiangou",
    "tiangou",
    category="stack_based",
    boolean=tiangou,
    # Not a tree: one command group per row of the essential-input table.
    shape=Shape.LOOKUP,
    wrap=wrap_space_delimited,
)
