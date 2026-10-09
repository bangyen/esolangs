"""Native Boolfuck Boolean generator over single-bit cells.

Tape layout (head starts on cell 0, all cells start 0):

- cells ``2i`` / ``2i+1``: input bit ``x_i`` and its per-level flag
  (interleaved, so tests move the head only a couple of cells)
- cell ``2n``: result bit R; cell ``-1``: read scratch for the 7
  non-value bits of each input byte

Reads: under the Boolean input contract each input byte is ``'0'`` or
``'1'``, and the interpreter streams bytes little-endian, so the first
bit read is the value bit; it lands on the byte's own cell and the
other seven are read into scratch and forgotten (bytes consumed whole).

Tree: a decision tree re-choreographed for flip-only bit cells. Node
``i`` sets ``flag_i``, then ``[+`` on the bit cell clears a set bit and
runs the one-side (which clears the flag); ``[+`` on the flag then runs
the zero-side only when the flag survived (the bit was 0). Both sides
clear what they test, so every flag is 0 again when the node returns.
Constant subtrees fold to a leaf, exactly as in
``helpers.decision_tree_body``; a ``"1"`` leaf flips R, and only one
leaf ever executes, so R flips at most once. A repeated residual is deferred
to the unused first residual-level flag and emitted once after the prefix tree,
only when text shrinks and the unchanged command bound admits it.

Print: R prints as bit 0 of the answer byte; bits 1..3 print from a
cleared flag cell, bits 4..5 after flipping it, bits 6..7 cleared
again -- the ASCII ``'0'``/``'1'`` byte in exactly 8 prints.
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    move_text,
)
from esolangs.tools.shared_block import repeated_block
from esolangs.tools.shared_flag import flag_tree_body
from esolangs.tools.wrap import wrap_chars

_SCRATCH = -1


def boolfuck(truth_table: str) -> str:
    """Return a native Boolfuck program for an MSB-first truth table."""
    plain, _ = _boolfuck_tree(truth_table)
    shared = repeated_block(truth_table)
    if shared is None:
        return plain
    candidate, commands = _boolfuck_tree(truth_table, shared)
    n = _validate_truth_table(truth_table)
    return (
        candidate
        if commands <= 2 * n * n + 27 * n + 8 and len(candidate) < len(plain)
        else plain
    )


def _boolfuck_tree(
    truth_table: str, shared: tuple[int, int] | None = None
) -> tuple[str, int]:
    """Emit a tree, optionally deferring a block into its first unused flag."""
    n = _validate_truth_table(truth_table)
    result = 2 * n
    parts: list[str] = []
    count = 0

    def emit(code: str) -> None:
        nonlocal count
        parts.append(code)
        count += len(code)

    pos = 0  # cell the head is known to rest on

    def move(target: int) -> None:
        nonlocal pos
        emit(move_text(pos, target, ">", "<"))
        pos = target

    # Read phase: value bit of byte i to cell 2i, other 7 bits to scratch.
    for i in range(n):
        move(2 * i)
        emit(",")
        move(_SCRATCH)
        emit("," * 7)

    # Decision tree over the stored bits.
    read_cost = count
    body, tree_cost = flag_tree_body(
        truth_table, tuple(range(n)), pos, result, shared=shared, flip=True
    )
    emit(body)
    pos = result
    tail_start = count

    # Print the ASCII answer byte: R, 0,0,0, 1,1, 0,0 (little-endian).
    move(result)
    emit(";")
    move(1)  # every flag is 0 again here
    emit(";;;+;;+;;")

    return "".join(parts), read_cost + tree_cost + count - tail_start


LANGUAGE = Language(
    "Boolfuck",
    "tape_based.boolfuck",
    boolean=boolfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    eof="EOF supplies zero bits",
)
