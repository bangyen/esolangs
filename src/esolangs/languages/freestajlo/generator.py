"""Freestajlo Boolean program generator: a pushed string, picked at the row.

``"..."`` pushes the table read at the essential inputs, row 0 on top; ``;``
reads each into the row by Horner's rule (``2*;+``), ``;#`` drops an ignored
one, and ``&.`` prints the entry that deep.  AND is ``"0001";2*;+&.``.  From
about 32 rows a packed literal is shorter: six entries a printable character,
and the row splits into the character ``&`` copies and the bit printed
([ablations.packed_literal]).

Size:
    T/6 + 4n + 20 chars past the crossover; n=4 parity: 33 chars, n=10
    random 1847: 230 chars.

Decisions:
    A literal shares nothing; a constant is ``'c``, printed with no index.
"""

from esolangs.generation.helpers import _validate_truth_table, essential_inputs, read_at
from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._language import Language, Shape

#: A string, ``'`` and its character, or a digit run is one unit: a break
#: inside pushes a newline or splits a number.
_UNIT = r'"[^"]*"|\'[\s\S]|\d+|[\s\S]'


#: Table bits a packed character carries, and the code of its zero word: 64
#: printable codes from 35 skip ``"``, which ends the literal, and DEL.
_WORD = 6
_BASE = 35
#: Split the row into character and bit, copy the character, shift, print.
_DECODE = f"${_WORD}%\\{_WORD}/1+&{_BASE}-\\2\\^/2%:"


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
    plain = f'"{reduced}"' + "".join(reads) + "&."
    packed = f'"{_pack(reduced)}"' + "".join(reads) + _DECODE
    return min(plain, packed, key=len)


def _pack(table: str) -> str:
    """Return ``table`` as printable characters, entry ``i`` at bit ``i % 6``."""
    return "".join(
        chr(_BASE + int(table[start : start + _WORD][::-1], 2))
        for start in range(0, len(table), _WORD)
    )


LANGUAGE = Language(
    "Freestajlo",
    "freestajlo",
    category="stack_based",
    boolean=freestajlo,
    shape=Shape.LOOKUP,
    wrap=TokenWrapper(_UNIT),
    eof="an exhausted ',' is the spec's -1, an exhausted ';' its 0",
)
