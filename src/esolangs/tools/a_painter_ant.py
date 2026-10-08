"""Boolean-function generator for A Painter Ant (parameterized convention).

Row -1 is the never-painted lane, row 0 the white corridor, row +1 the
answers.  Each input is ``n`` (into the lane) or ``N`` (blocked), then
``E`` x ``2**(n-1-i)`` which only the corridor allows, then ``SN``; a pass
ends on the answer, or for a one on the white corridor above it.  The
corridor ends where the trailing run of equal answers starts: a walk halts
there, and every index past it shares its answer.  Interior runs stay: the
ant counts through every row, so no subtree folds or is shared.
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
)
from esolangs.tools.wrap import wrap_chars

__all__ = ["a_painter_ant"]


PAIR = ("n", "N")


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template: one run per input, weight in the ``E`` walk."""
    n = _validate_truth_table(truth_table)
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


LANGUAGE = Language(
    "A Painter Ant",
    "grid_based.a_painter_ant",
    boolean=a_painter_ant,
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"(?m)^[.#o@]*([o@])[.#o@]*$",
        answer_values=("o", "@"),
        note="A Painter Ant has no output: it paints a grid and the answer "
        "is the answer cell the ant rests on below its white corridor, "
        "shown by 'o' (on black, a zero) or '@' (on white, a one)",
        parameterized=True,
    ),
    wrap=wrap_chars,
)
