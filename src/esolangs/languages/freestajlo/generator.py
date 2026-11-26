"""Freestajlo Boolean program generator: a pushed string, picked at the row.

``"..."`` pushes the table read at the essential inputs, row 0 on top; ``;``
reads each into the row by Horner's rule (``2*;+``), ``;#`` drops an ignored
one, and ``&.`` prints the entry that deep.  a AND NOT b is ``"0010";2*;+&.``.  From
about 32 rows a packed literal is shorter: six entries a printable character,
and the row splits into the character ``&`` copies and the bit printed
([ablations.packed_literal]).  A symmetric table sums its reads instead and
picks one of m + 1 entries for m essential inputs
([ablations.symmetric_count]). ``balance=True`` cuts the literal into strings
of about ``sqrt(2 * len)`` entries, pushed last first; each pushes a 0 between
chunks, so the index ``i`` becomes ``i + i / c`` (``$c/+``). Uncut, the literal
set the floor width and balanced area grew as T^2.

Size:
    T/6 + 4n + 20 chars past the crossover; n=4 parity: 16 chars, n=10
    random 1847: 230 chars. Constants: n + 2 chars and commands.

Decisions:
    A literal shares nothing; constants read every input, then print a bare digit.
"""

from math import isqrt

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.lookup import symmetric_outputs
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.reflow import balance_program
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.runtime._program import Program

#: A string, ``'`` and its character, or a digit run is one unit: a break
#: inside pushes a newline or splits a number.


#: Table bits a packed character carries, and the code of its zero word: 64
#: printable codes from 35 skip ``"``, which ends the literal, and DEL.
_WORD = 6
_BASE = 35
#: Split the row into character and bit, copy the character, shift, print.
_DECODE = f"${_WORD}%\\{_WORD}/1+&{_BASE}-\\2\\^/2%:"


def freestajlo(truth_table: str) -> str:
    """Build a Freestajlo program printing ``truth_table[row]`` for the inputs."""
    return _program(truth_table)


def _reads(n: int, used: list[int], combine: str) -> str:
    reads = [";#"] * n
    for k, i in enumerate(used):
        reads[i] = combine if k else ";"
    return "".join(reads)


def _program(truth_table: str, *, balance: bool = False) -> str:
    """Reuse the projected lookup and reads when racing chunked layouts."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n)
    reduced = read_at(truth_table, used, n)
    if not used:
        constant = ";" * n + reduced + ":"
        return balance_program(constant, "freestajlo") if balance else constant

    tail = _reads(n, used, "2*;+")
    packed = _pack(reduced)
    forms = [f'"{reduced}"{tail}&.', f'"{packed}"{tail}{_DECODE}']
    if (
        len(used) >= 2
        and (symmetric := symmetric_outputs(reduced, len(used))) is not None
    ):
        # The count picks one of len(used) + 1 entries.
        # See [ablations.symmetric_count].
        forms.append(f'"{symmetric}"{_reads(n, used, ";+")}&.')
    default = min(forms, key=len)
    if not balance:
        return default

    literal, chunk = _cut(reduced)
    plain = f"{literal}{tail}${chunk}/+&."
    literal, chunk = _cut(packed)
    decode = _DECODE.replace("1+&", f"${chunk}/+1+&", 1)
    candidates = (default, plain, literal + tail + decode)
    return min(
        (balance_program(form, "freestajlo") for form in candidates),
        key=balance_score,
    )


def _cut(literal: str) -> tuple[str, int]:
    """Return ``literal`` as strings, the last chunk first, and the chunk size.

    A 0 sits between chunks, so row ``i`` lies ``i // chunk`` deeper.
    """
    chunk = max(1, isqrt(CELL_ASPECT * len(literal)))
    chunks = [literal[i : i + chunk] for i in range(0, len(literal), chunk)]
    return "".join(f'"{c}"' for c in reversed(chunks)), chunk


def _pack(table: str) -> str:
    """Return ``table`` as printable characters, entry ``i`` at bit ``i % 6``."""
    return "".join(
        chr(_BASE + int(table[start : start + _WORD][::-1], 2))
        for start in range(0, len(table), _WORD)
    )


def freestajlo_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.balance:
        return _program(request.table, balance=True)
    return freestajlo(request.table)
