"""Freestajlo Boolean program generator: a pushed string, picked at the row.

``"..."`` pushes the table read at the essential inputs, row 0 on top; ``;``
reads each into the row by Horner's rule (``2*;+``), ``;#`` drops an ignored
one, and ``&.`` prints the entry that deep.  AND is ``"0001";2*;+&.``.

Size:
    T + 4n chars; n=4 parity: 33 chars, n=10 random 1847: 1,065 chars.

Decisions:
    A literal shares nothing; a constant is ``'c``, printed with no index.
"""

from esolangs.generation.helpers import _validate_truth_table, essential_inputs, read_at
from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._language import Language, Shape

#: A string, ``'`` and its character, or a digit run is one unit: a break
#: inside pushes a newline or splits a number.
_UNIT = r'"[^"]*"|\'[\s\S]|\d+|[\s\S]'


def freestajlo(truth_table: str) -> str:
    """Build a Freestajlo program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n)
    reduced = read_at(truth_table, used, n)
    if not used:
        return f"'{reduced}" + ";#" * n + "."
    reads = [";#" for _ in range(n)]
    for k, i in enumerate(used):
        reads[i] = "2*;+" if k else ";"
    return f'"{reduced}"' + "".join(reads) + "&."


LANGUAGE = Language(
    "Freestajlo",
    "freestajlo",
    category="stack_based",
    boolean=freestajlo,
    shape=Shape.LOOKUP,
    wrap=TokenWrapper(_UNIT),
    eof="an exhausted ',' is the spec's -1, an exhausted ';' its 0",
)
