"""Bitwise Cyclic Tag Boolean program generator: the table as a forward walk.

BCT has no branch, so all an input can change is how much data is appended, and
so how far the pointer has moved when a later bit is read.  Input ``i`` appends
three zeros per unit of its place value over pairs of rows, the lowest input two,
and a sentinel ``1`` lands behind them.  A cell ``1 a 0 b 1 0 0`` holds two rows
and eats three zeros whatever ``b`` is (``b`` is a delete when 0, the operand of
the next ``1`` when 1), so the walk arrives at cell ``index // 2``; the sentinel
fires ``a`` or, two zeros later, ``b``, and the trailing ``00`` eats a 1 answer
so no indexed row cascades; a 0 answer is inert and the next delete eats it.
Constants delete the embedded inputs and a literal answer with a cyclic ``0``.
Emission is ``program,data``; the count and why a cell needs seven characters:
``docs/proofs/index.md``.

Size:
    Theta(T) chars, 13/2 per row, independent of the table's values;
    n=10 random 1847: 6,679 chars, n=12 random 1847: 26,651 chars.
"""

from __future__ import annotations

from esolangs.generation.helpers import (
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    layout_fragments,
)

_INPUT = InputSlot(1)

#: The constant bit held behind the inputs, read after every walk zero.
_SENTINEL = "1"


def _read(weight: int) -> str:
    """One input's command: zeros it appends when set, then the ``0`` eating its bit."""
    if weight == 1:
        return "10" * 2 + "0"
    return "10" * (3 * (weight // 2)) + "0"


def bitwise_cyclic_tag(truth_table: str) -> str:
    """Return the BCT template computing ``truth_table``."""
    return _layout(truth_table).source


def _layout(truth_table: str) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return layout_fragments(("0,", *(_INPUT,) * n, truth_table[0]))
    # An ignored input appends nothing either way: its command is a bare ``0``.
    weights, table = input_weights(truth_table, n)
    reads = "".join(_read(weight) for weight in weights)
    rows = "".join(
        "1" + table[i] + "0" + table[i + 1] + "100" for i in range(0, len(table), 2)
    )
    return layout_fragments((f"{reads}1{_SENTINEL}0{rows},", *(_INPUT,) * n, _SENTINEL))


def bitwise_cyclic_tag_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table)
