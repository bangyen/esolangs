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
leaf ever executes, so R flips at most once.

Print: R prints as bit 0 of the answer byte; bits 1..3 print from a
cleared flag cell, bits 4..5 after flipping it, bits 6..7 cleared
again -- the ASCII ``'0'``/``'1'`` byte in exactly 8 prints.
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    move_text,
    subtree_ids,
)
from esolangs.tools.wrap import wrap_chars

_SCRATCH = -1


def boolfuck(truth_table: str) -> str:
    """Return a native Boolfuck program for an MSB-first truth table."""
    n = _validate_truth_table(truth_table)

    result = 2 * n
    ids = subtree_ids(truth_table)
    is_constant = constant_span_test(truth_table)

    def bit(i: int) -> int:
        return 2 * i

    def flag(i: int) -> int:
        return 2 * i + 1

    parts: list[str] = []
    pos = 0  # cell the head is known to rest on

    def move(target: int) -> None:
        nonlocal pos
        parts.append(move_text(pos, target, ">", "<"))
        pos = target

    def constant(i: int, combo: int) -> str | None:
        """Shared value of the level-``i`` subtree at ``combo``, else None."""
        span = 1 << (n - i)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(i: int, combo: int) -> None:
        """Emit one side of node ``i``: a folded leaf or the child subtree."""
        value = constant(i + 1, combo)
        if value is None:
            node(i + 1, combo)
        elif value == "1":
            move(result)
            parts.append("+")
        # value == "0": the leaf emits nothing

    def node(i: int, combo: int) -> None:
        """Emit node ``i``: test bit ``i``, run one side, leave flag_i = 0."""
        bit_cell = bit(i)
        flg = flag(i)
        one = combo | (1 << (n - 1 - i))
        below = ids[i + 1]
        if below[combo >> (n - i - 1)] == below[one >> (n - i - 1)]:
            branch(i, combo)  # halves agree: bit i cannot matter
            return
        move(flg)
        parts.append("+")  # flag_i = 1 (it is 0 by invariant)
        move(bit_cell)
        parts.append("[+")  # a set bit clears itself and enters the one-side
        move(flg)
        parts.append("+")  # the one-side ran: flag_i = 0
        branch(i, one)
        move(bit_cell)
        parts.append("]")  # bit is 0 now, so this exits
        move(flg)
        parts.append("[+")  # the flag survived only when the bit was 0
        branch(i, combo)
        move(flg)
        parts.append("]")

    # Read phase: value bit of byte i to cell 2i, other 7 bits to scratch.
    for i in range(n):
        move(bit(i))
        parts.append(",")
        move(_SCRATCH)
        parts.append("," * 7)

    # Decision tree over the stored bits.
    node(0, 0)

    # Print the ASCII answer byte: R, 0,0,0, 1,1, 0,0 (little-endian).
    move(result)
    parts.append(";")
    move(flag(0))  # every flag is 0 again here
    parts.append(";;;+;;+;;")

    return "".join(parts)


LANGUAGE = Language(
    "Boolfuck",
    "tape_based.boolfuck",
    boolean=boolfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
