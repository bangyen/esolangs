"""Qrain Boolean program generator: a flag-dispatched decision tree on queues.

Input ``k`` is read by ``,`` into cell ``2k`` as the queue ``b,0,0,0,1,1,0,0``
(the ASCII ``0``/``1``, low bit first) and its flag is cell ``2k + 1``; the
result R is cell ``2n``.  With the output queue empty ``+`` enqueues the
negation of the front bit, so a flag is raised by ``+`` on an empty cell and
cleared by ``-``, and ``+-`` flips a one-bit queue (R starts as ``0``, built
by ``++-``).  A node raises its flag, ``[-`` consumes a set bit (the next bit
is 0, so the loop exits) and clears the flag before the one-side; ``[-`` on
the flag runs the zero-side.  Repeated residuals defer through level flags
as in the other flag trees (``esolangs.generation.shared_flag``).

The first byte is read beside R instead (cell ``2n + 1``, Z) and split: its low
bit moves to cell 0 as ``1`` or an empty queue, and Z keeps the seven bits
``0,0,0,1,1,0,0`` either way, through a flag (cell ``2n + 2``).  The answer
byte is R then Z: ``.`` on each completes ``0``/``1``.

Size:
    O(T): at most 19 characters a node, trips to R summing to 10T; the
    shared form is kept when shorter; n=4 parity: 278 chars.

Decisions:
    A tree cannot print Z unless its bits are fixed, and the tree consumes
    the first byte's low bit only when it is 1; the split frees that.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
    move_text,
)
from esolangs.generation.shared_block import repeated_block, repeated_blocks
from esolangs.generation.shared_flag import FlagDialect, flag_tree_body
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _command_budget(n: int) -> int:
    """Return the execution ceiling the ledger states; shared bodies stay under it."""
    return 36 * n + 60


def _move(here: int, there: int) -> str:
    return move_text(here, there, ">", "<")


#: ``+`` on an empty flag raises it, ``-`` clears it; a leaf flips R.
_DIALECT = FlagDialect(
    _move, one="+", zero="-", opener="[", closer="]", decrement="-", leaf="+-"
)


def _qrain_ordered(table: str, perm: tuple[int, ...]) -> str:
    """Emit the reads, the first byte's split, R, the tree and the print."""
    n = _validate_truth_table(table)
    result, z, g = 2 * n, 2 * n + 1, 2 * n + 2
    parts = [_move(0, z), ","]
    pos = z
    for k in range(1, n):
        parts.append(_move(pos, 2 * k) + ",")
        pos = 2 * k
    # Split Z: G=1; a set bit leaves Z and clears G and raises cell 0; else G pops Z.
    for cell, code in (
        (g, "+"),
        (z, "[-"),
        (g, "-"),
        (0, "+"),
        (z, "]"),
        (g, "[-"),
        (z, "-"),
        (g, "]"),
        (result, "++-"),
    ):
        parts.append(_move(pos, cell) + code)
        pos = cell
    header = "".join(parts)
    tail = _move(result, z) + "."
    budget = _command_budget(n) - len(header) - len(tail) - 1
    shared = repeated_block(table)
    forms = []
    if shared is not None:
        forms.append(
            flag_tree_body(table, perm, pos, result, shared=shared, dialect=_DIALECT)
        )
        blocks = repeated_blocks(table)
        if len(blocks) > 1:
            forms.append(
                flag_tree_body(
                    table, perm, pos, result, shared_blocks=blocks, dialect=_DIALECT
                )
            )
    # A shared form is always shorter than the plain tree (0 of 65,536 n=4
    # tables, 920 random n=4..8); the plain tree serves only tables with none.
    fits = [(body, c) for body, c in forms if c <= budget]
    if fits:
        best = min(fits, key=lambda form: len(form[0]))[0]
    else:
        best, cost = flag_tree_body(
            table, perm, pos, result, dialect=_DIALECT, fold_zero=True
        )
        if cost > budget:  # pragma: no cover - the plain tree stays under the ceiling
            raise AssertionError("plain tree exceeds the execution ceiling")
    return header + best + "." + tail


def qrain(truth_table: str) -> str:
    """Return a Qrain program for an MSB-first truth table."""
    return in_input_order(truth_table, _qrain_ordered)


LANGUAGE = Language(
    "Qrain",
    "qrain",
    category="queue_based",
    boolean=qrain,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_chars,
    eof="EOF supplies byte 0",
)
