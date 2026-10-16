"""Malbolge Boolean program generator: one source stub per table row.

``malbolge(truth_table)`` reads one ``0``/``1`` line per input and folds them
through a fixed five-cell branch-free mixer into a distinct address ``h(row)``.
The runtime then jumps to a three-cell stub at ``h(row)`` that prints the
row's answer.  The whole fixed-size source is the program: the mixer inits,
the navigation constants and the stubs are all source characters, so there is
no initializer.

``i``/``j`` let the pointer revisit a cell, but Malbolge re-enciphers every
cell it executes, so a data cell's value after the instruction pointer has
walked over it is ``g(a) = XLAT2[f(a) - 33]``, not the source character;
``f(a) = 33 + ((35 - a) % 94)`` is the unique NOP character at address ``a``.
Every data cell is placed at the address whose ``g`` value is wanted.

That stub construction covers ``n <= 10``: its readout cell is injective
with pairwise gap at least three only through ten bits.  ``n == 11`` uses the
pointer cascade below instead, which needs only *distinct* readouts: each row
owns one table cell holding a source character that points at a pointer cell
in the walked region, and the rows a first readout cannot separate are sent
through a second decoder that reads a second cell.  ``n == 12`` runs the
same fold over the first eleven inputs and lets the twelfth pick which of two
paths reads the readout (see below), ``n == 13`` keeps that build and lets
the answer stub read the thirteenth.  ``n == 14`` computes four copies'
readouts in the main code, lets inputs twelve and thirteen pick a copy and
the stub read the fourteenth, and resolves shared cells over three levels.
``n == 15`` and ``n == 16`` drop the hash for a collision-free positional
address (:mod:`esolangs.languages.malbolge.generator.digits`).

Size:
    Constant: the fixed 59049-cell memory at every arity; n=10 random 1847:
    59,049 chars, n=16 and: 59,049 chars.

Raises:
    GeneratorCapError: more than sixteen inputs.

Decisions:
    Folding or sharing stubs cannot shrink the fixed store.
"""

from __future__ import annotations

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.runtime.source_hints import with_hint

from .cascade import _CASCADE_N, _cascade_program, _table_char
from .core import _ANSWER
from .digits import _DIGITS_N, _digits_program
from .isa import _WORDS, _char_for, _program, _render
from .segments import _FOURTEEN_N, _fourteen
from .skeleton import _skeleton
from .thirteen import _THIRTEEN_N, _thirteen
from .wide import _WIDE_N, _wide_program

#: Fifteen and sixteen inputs: :mod:`esolangs.languages.malbolge.generator.digits`.
MAX_INPUTS = _DIGITS_N


def _thirteen_program(truth_table: str) -> str:
    code, data, level, tables, labels = _thirteen()
    program = _program(code)
    program.update(data)
    for x in (0, 1):
        for row, h in enumerate(tables[0][x]):
            i = 4 * row + 2 * x
            label = _ANSWER[truth_table[i : i + 2]]
            if level[x][row]:
                program[h] = _table_char(h, "N", labels)
                h2 = tables[1][x][row]
                program[h2] = _table_char(h2, label, labels)
            else:
                program[h] = _table_char(h, label, labels)
    return _render(program)


def _fourteen_program(truth_table: str) -> str:
    code, data, level, tables, labels = _fourteen()
    program = _program(code)
    program.update(data)
    for c in range(4):
        for row, k in enumerate(level[c]):
            i = 8 * row + 2 * c
            for lvl in range(k):
                h = tables[lvl][c][row]
                program[h] = _table_char(h, "N", labels)
            h = tables[k][c][row]
            program[h] = _table_char(h, _ANSWER[truth_table[i : i + 2]], labels)
    return _render(program)


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table`` (``n`` <= 16)."""
    n = _validate_truth_table(truth_table)
    if n > _DIGITS_N:
        raise with_hint(
            GeneratorCapError(
                f"Malbolge builds at most {_DIGITS_N} inputs, got {n}: every row "
                "pair owns a cell, and seventeen inputs would need 65,536 of the "
                "store's 59,049"
            ),
            (
                "use fewer inputs or check another generator's "
                "limits; width cannot enlarge Malbolge's store"
            ),
        )
    if n > _FOURTEEN_N:
        return _digits_program(truth_table, n)
    if n == _FOURTEEN_N:
        return _fourteen_program(truth_table)
    if n == _THIRTEEN_N:
        return _thirteen_program(truth_table)
    if n == _WIDE_N:
        return _wide_program(truth_table)
    if n == _CASCADE_N:
        return _cascade_program(truth_table)
    code, addresses = _skeleton(n)
    program = dict(code)
    for row, address in enumerate(addresses):
        program[address + 1] = "p" if truth_table[row] == "1" else "o"
        program[address + 2] = "<"
        program[address + 3] = "v"
    return "".join(
        chr(_char_for(program.get(address, "o"), address)) for address in range(_WORDS)
    )


LANGUAGE = Language(
    "Malbolge",
    "malbolge",
    category="program_based",
    # Every source loads into the fixed store, so every program -- this
    # generator's or any other -- is bounded by a constant.
    size_bound=lambda _n: 59_049,
    generator_max_inputs=MAX_INPUTS,
    boolean=malbolge,
    # Not a tree: straight-line code into the fixed store.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
    # Loader whitespace is discarded before assigning memory addresses.
    wrap=wrap_chars,
    eof="an exhausted read is the value 59048, not an error",
)
