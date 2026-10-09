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
    constant_span_test,
    move_text,
    subtree_ids,
)
from esolangs.tools.shared_block import (
    BranchCost,
    add_cost,
    dispatch_cost,
    merge_cost,
    normal_cost,
    repeated_block,
)
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
    fold_zero = shared is not None
    pending = 2 * shared[0] + 1 if shared is not None else 2 * n - 1
    ids = subtree_ids(truth_table)
    is_constant = constant_span_test(truth_table)

    def bit(i: int) -> int:
        return 2 * i

    def flag(i: int) -> int:
        return 2 * i + 1

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

    def constant(i: int, combo: int) -> str | None:
        """Shared value of the level-``i`` subtree at ``combo``, else None."""
        span = 1 << (n - i)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(i: int, combo: int) -> BranchCost:
        """Emit one side of node ``i``: a folded leaf or the child subtree."""
        start = count
        value = constant(i + 1, combo)
        if value is None:
            return node(i + 1, combo)
        if value == "1":
            move(result)
            emit("+")
        # value == "0": the leaf emits nothing
        return count - start, None

    def node(i: int, combo: int) -> BranchCost:
        """Emit node ``i``: test bit ``i``, run one side, leave flag_i = 0."""
        start = count
        if (
            shared is not None
            and i == shared[0]
            and ids[i][combo >> (n - i)] == ids[i][shared[1] >> (n - i)]
        ):
            move(pending)
            emit("+")
            return None, count - start
        bit_cell = bit(i)
        flg = flag(i)
        one = combo | (1 << (n - 1 - i))
        below = ids[i + 1]
        if below[combo >> (n - i - 1)] == below[one >> (n - i - 1)]:
            return branch(i, combo)  # halves agree: bit i cannot matter
        if fold_zero and constant(i + 1, combo) == "0":
            move(bit_cell)
            emit("[")
            common = count - start
            emit("+")
            body_start = count
            one_cost = branch(i, one)
            one_flat = count - body_start
            move(bit_cell)
            emit("]")
            return merge_cost(
                add_cost(one_cost, count - start - one_flat + 1),
                (common, None),
            )
        move(flg)
        emit("+")  # flag_i = 1 (it is 0 by invariant)
        move(bit_cell)
        emit("[")
        one_start = count
        emit("+")  # a set bit clears itself and enters the one-side
        move(flg)
        emit("+")  # the one-side ran: flag_i = 0
        body_start = count
        one_cost = branch(i, one)
        one_flat = count - body_start
        move(bit_cell)
        emit("]")  # bit is 0 now, so this exits
        one_cost = add_cost(one_cost, count - one_start - one_flat + 1)
        between = count
        move(flg)
        emit("[")
        common = one_start - start + count - between
        zero_start = count
        emit("+")  # the flag survived only when the bit was 0
        body_start = count
        zero_cost = branch(i, combo)
        zero_flat = count - body_start
        move(flg)
        emit("]")
        zero_cost = add_cost(zero_cost, count - zero_start - zero_flat + 1)
        return add_cost(merge_cost(one_cost, zero_cost), common)

    # Read phase: value bit of byte i to cell 2i, other 7 bits to scratch.
    for i in range(n):
        move(bit(i))
        emit(",")
        move(_SCRATCH)
        emit("," * 7)

    # Decision tree over the stored bits.
    read_cost = count
    tree_cost = node(0, 0)
    tail_start = count
    if shared is not None:
        depth, row = shared
        move(pending)
        dispatch_test = count - tail_start + 1
        emit("[+")
        body_start = count
        shared = None
        body_cost = node(depth, row)
        body_flat = count - body_start
        move(pending)
        emit("]")
        active = count - tail_start - body_flat + normal_cost(body_cost) + 1
        tree_cost = dispatch_cost(tree_cost, active, dispatch_test)
        tail_start = count

    # Print the ASCII answer byte: R, 0,0,0, 1,1, 0,0 (little-endian).
    move(result)
    emit(";")
    move(flag(0))  # every flag is 0 again here
    emit(";;;+;;+;;")

    return "".join(parts), read_cost + normal_cost(tree_cost) + count - tail_start


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
