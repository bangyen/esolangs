"""A Painter Ant Boolean program generator: a corridor the inputs walk by weight.

For indexed tables, row -1 is the never-painted lane, row 0 the white
corridor, row +1 the answers. Each input is ``n`` (into the lane) or ``N``
(blocked), then
``E`` x ``2**(n-1-i)`` which only the corridor allows, then ``SN``; a pass
ends on the answer, or for a one on the white corridor above it.  The
corridor ends where the trailing run of equal answers starts: a walk halts
there, and every index past it shares its answer.  Constant roots restore
each input to one white origin, then leave it black or white.

A table whose leading run is longer than its trailing run walks the mirror
(:func:`_flipped`): the corridor holds the top index first, a zero input
walks the black lane east, and a white wall cell with its lane stopper
clamps the walk.  The shorter of the two ships.

Size:
    O(T) characters, one corridor cell per row; n=10 parity: 7,707 chars,
    n=10 and: 1,071 chars (6,174 unflipped).

Decisions:
    Interior runs stay: the ant counts through every row, so no subtree
    folds or is shared.
"""

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.a_painter_ant.proof_formulas import execution
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

__all__ = ["a_painter_ant"]


PAIR = ("n", "N")


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template: one run per input, weight in the ``E`` walk."""
    return _program(truth_table)


def _program(truth_table: str) -> str:
    """Build the indexed corridor or a constant origin with input resets."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # n enters black north; N stays put. S returns to the white origin
        # in both cases, so the next setter sees the same two neighbours.
        return "P" + (TEMPLATE_CHAR + "S") * n + ("p" if truth_table[0] == "0" else "")
    # An ignored input walks no ``E``: the corridor is the essential inputs'.
    weights, table = input_weights(truth_table, n)
    east = _east(table, weights)
    flipped = _flipped(table, weights)
    return min(east, flipped, key=len)


def _answers(out: list[str], bit: str) -> None:
    """Paint the answer cell under the ant on pass 1; harmless later."""
    if bit == "1":
        out.append("sPN")


def _east(table: str, weights: list[int]) -> str:
    """Corridor from index 0 east to the trailing run's first answer."""
    size = len(table.rstrip(table[-1])) + 1
    # Pass 1 paints the origin; later ``N`` lifts off the answer, ``W`` returns.
    out = ["N", "W" * (size - 1), "P"]
    _answers(out, table[0])
    for bit in table[1:size]:
        # ``e`` paints on pass 1, ``E`` enters white later: one cell per pass.
        out.append("ePE")
        _answers(out, bit)
    out.append("W" * (size - 1))
    for weight in weights:
        out.append(TEMPLATE_CHAR)
        out.append("E" * weight + "SN")
    # ``s`` steps onto a black answer; a white one leaves the ant on white.
    out.append("s")
    return "".join(out)


def _flipped(table: str, weights: list[int]) -> str:
    """Corridor from the top index, a zero input walking the lane east.

    Complemented inputs make AND-like tables (a long leading run) as cheap as
    OR-like ones.  The lane stays black, so ``e`` walks it; a white wall cell
    past the last answer and its lane stopper clamp that walk, and the wall
    refuses ``e`` for a one input, which stays in the corridor.
    """
    run = len(table) - len(table.lstrip(table[0]))
    cells = table[run - 1 :][::-1]
    out = ["N", "W" * (len(cells) - 1), "P"]
    _answers(out, cells[0])
    for bit in cells[1:]:
        out.append("ePE")
        _answers(out, bit)
    # Wall cell, then its lane stopper; ``S`` returns on pass 1 only.
    out.append("ePEnPS" + "W" * len(cells))
    for weight in weights:
        out.append(TEMPLATE_CHAR)
        out.append("e" * weight + "SN")
    out.append("s")
    return "".join(out)


LANGUAGE = Language(
    "A Painter Ant",
    "a_painter_ant",
    category="grid_based",
    boolean=a_painter_ant,
    # Not a tree: one corridor cell per row, walked by the inputs' weights.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"(?m)^[.#o@]*([o@])[.#o@]*$",
        answer_values=("o", "@"),
        note="A Painter Ant has no output: it paints a grid and the answer "
        "is the colour of the cell the ant rests on, "
        "shown by 'o' (on black, a zero) or '@' (on white, a one)",
    ),
    wrap=wrap_chars,
    example=Example(pair=PAIR, expected="..#\n###\n#o."),
    proof_execution=(execution, True, (3, 6)),
)
