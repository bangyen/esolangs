"""Chicken Boolean program generator: the table is the program's own lines.

The answer is a line count read back out of the code region.  The rows sit
after the program as one line each, ``chicken`` for the minority value and a
blank line for the other, so a row is a cell holding 1 or 0.  The program
reads each essential input as ``input[p] == true`` (``"1"`` loosely equals
true; ``"0"`` and a missing character do not), folds the bits into a row
number by Horner's rule starting from a pushed base, and loads that cell.  The
base is the first multiple of ``2**(m-1)`` past the program, with blank lines
filling the gap, so no address constant grows with the program.  A table that
is mostly 1 stores its zeros as lines and subtracts the loaded cell from a 1
pushed first.

Size:
    ``8 * (ones or zeros, whichever is fewer) + (T - that) + O(n)`` characters
    for m essential inputs and ``T = 2**m`` rows, so linear in T; n=4
    parity: 1,678 chars

Decisions:
    * Rows are the cheaper of the two polarities, inverted only past the 112
      characters the inversion costs (see [ablations.polarity]).
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

#: Opcodes, as chickens a line.
_CHICKEN, _ADD, _SUB, _MUL, _CMP, _LOAD = 1, 2, 3, 4, 5, 6
_PUSH = 10
#: Ones past the zeros that repay what inversion adds ([ablations.polarity]).
_INVERT_MARGIN = 16


def _line(count: int) -> str:
    return " ".join(["chicken"] * count) + "\n"


def _push(value: int) -> str:
    return _line(_PUSH + value)


def _program(rows: str, positions: list[int]) -> str:
    """Return the program reading ``positions`` and answering ``rows[index]``.

    ``rows`` has one character a row; the minority character is the row
    value stored as a ``chicken`` line.
    """
    ones = rows.count("1")
    invert = 2 * ones - len(rows) > _INVERT_MARGIN
    cells = [_push(1)] if invert else []
    body = []
    for step, position in enumerate(positions):
        if step:
            body += [_push(2), _line(_MUL)]
        body += [
            _push(position),
            _line(_LOAD),
            _line(1),
            _line(_CHICKEN),
            _line(_CHICKEN),
            _line(_CMP),
            _line(_CMP),
        ]
        body.append(_line(_ADD))
    tail = [_line(_LOAD), "\n"] + ([_line(_SUB)] if invert else []) + ["\n"]
    stride = 1 << (len(positions) - 1)
    # Cells before the base: registers, the program, and the pushed base.
    used = 2 + len(cells) + 1 + len(body) + len(tail)
    base = -(-used // stride)
    program = [*cells, _push(base), *body, *tail]
    program.append("\n" * (base * stride - used))
    stored = "1" if not invert else "0"
    program += [_line(1) if row == stored else "\n" for row in rows]
    return "".join(program)


def chicken(truth_table: str) -> str:
    """Build a Chicken program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    if not essential:
        return _push(int(truth_table[0]))
    return _program(read_at(truth_table, essential, n), essential)


LANGUAGE = Language(
    "Chicken",
    "chicken",
    category="stack_based",
    boolean=chicken,
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
        note="Chicken's input is one string; input[i] is bit i",
    ),
    no_wrap="a line break is the instruction boundary and a blank line is a cell",
    eof="a short input is a shorter string; a missing bit is not 1, so reads 0",
)
