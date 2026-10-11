"""Boolean-function generator for A Painter Ant (parameterized convention).

For indexed tables, row -1 is the never-painted lane, row 0 the white
corridor, row +1 the answers. Each input is ``n`` (into the lane) or ``N``
(blocked), then
``E`` x ``2**(n-1-i)`` which only the corridor allows, then ``SN``; a pass
ends on the answer, or for a one on the white corridor above it.  The
corridor ends where the trailing run of equal answers starts: a walk halts
there, and every index past it shares its answer.  Interior runs stay: the
ant counts through every row, so no subtree folds or is shared.
Constant roots restore each input to one white origin, then leave it black or white.
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape
from esolangs.tools.constant_projection import balanced_projection
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
    mark_runs,
    unmark,
)
from esolangs.tools.wrap import balance_program, wrap_chars

__all__ = ["a_painter_ant"]


PAIR = ("n", "N")


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template: one run per input, weight in the ``E`` walk."""
    return _program(truth_table)


def _program(truth_table: str, *, keep_constant_walk: bool = False) -> str:
    """Build the indexed corridor or a constant origin with input resets."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1 and not keep_constant_walk:
        # n enters black north; N stays put. S returns to the white origin
        # in both cases, so the next setter sees the same two neighbours.
        return "P" + (TEMPLATE_CHAR + "S") * n + ("p" if truth_table[0] == "0" else "")
    # An ignored input walks no ``E``: the corridor is the essential inputs'.
    weights, table = input_weights(truth_table, n)
    size = len(table.rstrip(table[-1])) + 1
    # Pass 1 paints the origin; later ``N`` lifts off the answer, ``W`` returns.
    out = ["N", "W" * (size - 1), "P"]
    if table[0] == "1":
        out.append("sPN")
    for bit in table[1:size]:
        # ``e`` paints on pass 1, ``E`` enters white later: one cell per pass.
        out.append("ePE")
        if bit == "1":
            # Paints the answer cell on pass 1; harmless later.
            out.append("sPN")
    out.append("W" * (size - 1))
    for weight in weights:
        out.append(TEMPLATE_CHAR)
        out.append("E" * weight + "SN")
    # ``s`` steps onto a black answer; a white one leaves the ant on white.
    out.append("s")
    return "".join(out)


def balance_a_painter_ant(table: str, default: str) -> str:
    """Retain the old constant corridor when its wrapped shape balances better."""
    n = _validate_truth_table(table)
    pairs = (PAIR,) * n
    marked = mark_runs(default, TEMPLATE_CHAR, pairs)
    if len(set(table)) > 1:
        return unmark(balance_program(marked, "a_painter_ant"), TEMPLATE_CHAR, n)
    legacy = mark_runs(_program(table, keep_constant_walk=True), TEMPLATE_CHAR, pairs)
    return unmark(
        balanced_projection(marked, legacy, "a_painter_ant"), TEMPLATE_CHAR, n
    )


LANGUAGE = Language(
    "A Painter Ant",
    "grid_based.a_painter_ant",
    boolean=a_painter_ant,
    balance=balance_a_painter_ant,
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
    example=Example(pair=PAIR, expected="....\n####\n.o.#"),
)
