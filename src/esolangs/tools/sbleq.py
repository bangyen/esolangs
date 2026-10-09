"""Boolean-function generator for s*bleq."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    in_input_order,
    subtree_ids,
    subtree_slot,
)
from esolangs.tools.packed_decoder import packed_decoder
from esolangs.tools.wrap import wrap_grid


def sbleq(truth_table: str) -> str:
    """Build an S*bleq program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the
    inputs (most significant first); the table length implies ``n``.

    S*bleq's instruction is ``a b c``: ``mem[a] -= mem[b]``, and when the
    result is ``<= 0`` the pointer jumps to the address stored at ``c``.
    A bit normalized to 0 would trap on that test, so each input is tested
    as ``49 - byte`` (``'0'`` -> 1, ``'1'`` -> 0), landing the two cases on
    opposite sides of zero.

    **The reads are hoisted above the tree**, one instruction per input
    (``v_i -2 NXT``: ``v_i = -byte``, always ``<= 0``, so control falls to
    the next read), which lets the tree split in any input order.  A branch
    is then one destructive instruction on ``v_j`` that subtracts the
    ``-49`` constant and jumps on a one.  Each path tests an input at most
    once, so destroying ``v_j`` is safe; it needs base S*bleq
    (``store="a"``), since ``b`` holds the constant.  Reads happen once per
    input for the whole program, with no per-leaf drain.

    Leaves print ``-3 D 0`` (``D`` a constant 48/49 cell) and halt with
    ``0 0 3``; an entry trampoline keeps -1 in fixed low cell 3.  Subtrees
    with constant table entries collapse to a leaf.

    Operands are addresses, so a transient 0/1 in a cell that any ``c``
    references would be misread as a jump target.  *Constant* cells (the
    ``-49``, the 48/49 digits, -1, and the jump-target cells, the only
    ``c`` operands) are therefore kept separate from *value* cells (each
    input's ``v``); targets are back-patched once the layout is known.

    **A repeated subtree is emitted once and jumped to.**  Every path
    through the shared diagram still tests each input once, so the
    destructive test stays safe.  A one-subtree equal to an earlier copy is
    reached through the copy's target cell (branches to one copy share a
    cell), a zero-subtree becomes ``0 0 c`` (cell 0 is always zero, so the
    jump is taken), a leaf is emitted once per answer, and a test whose
    halves agree is skipped.  Shared, the tree is O(T), so it runs past 16
    entries against :func:`packed_decoder`, which it undercuts through about
    nine inputs.
    """
    _validate_truth_table(truth_table)
    tree = in_input_order(truth_table, _sbleq_shared)
    if len(truth_table) <= 16:
        return tree
    packed = packed_decoder(truth_table)
    return tree if len(tree) < len(packed) else packed


def _sbleq_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's shared tree; see :func:`_sbleq_hoisted`."""
    return _sbleq_hoisted(truth_table, perm, share=True)


def _sbleq_hoisted(
    truth_table: str, perm: tuple[int, ...], *, share: bool = False
) -> str:
    """Emit one input order's hoisted S*bleq program; see :func:`sbleq`.

    ``perm[k]`` is the input the tree tests at level ``k``; the read block
    stays in input order, so the program consumes its input stream exactly
    as the node-read build did.  ``share`` jumps to a subtree already
    emitted instead of repeating it.
    """
    n = _validate_truth_table(truth_table)
    neg49 = 0
    vbase = 4
    nxtbase = vbase + n

    # (a operand, b operand, kind, kind's argument); ``a``/``b`` are data
    # offsets made absolute below, and ``kind`` picks how ``c`` is filled.
    # A ``one`` or ``jump`` argument is the instruction index it goes to.
    instructions: list[tuple[int, int, str, int]] = [
        (vbase + i, -2, "nxt", i) for i in range(n)
    ]
    ids = subtree_ids(truth_table)
    # First instruction of each emitted subtree, by :func:`subtree_slot` name.
    placed: dict[tuple[int, int], int] = {}

    def resolve(level: int, block: int) -> tuple[int, int, tuple[int, int]]:
        return subtree_slot(ids, level, block, skip=share)

    def emit(level: int, block: int) -> None:
        """Lay the subtree out where control falls in, or jump to its copy.

        The jump ``0 0 c`` empties the always-zero cell 0, so it is taken.
        """
        level, block, slot = resolve(level, block)
        if slot in placed:
            instructions.append((0, 0, "jump", placed[slot]))
            return
        if share:
            placed[slot] = len(instructions)
        if slot[0] < 0:
            instructions.append((-3, 1 + slot[1], "out", 0))
            instructions.append((0, 0, "halt", 0))
            return
        at = len(instructions)
        instructions.append((0, 0, "", 0))  # the branch, once its target is known
        emit(level + 1, 2 * block)
        # The one subtree is branched to, so an earlier copy costs nothing.
        one = placed.get(resolve(level + 1, 2 * block + 1)[2])
        if one is None:
            one = len(instructions)
            emit(level + 1, 2 * block + 1)
        instructions[at] = (vbase + perm[level], neg49, "one", one)

    emit(0, 0)

    onebase = nxtbase + n
    # One target cell per distinct target: two branches to one copy share it.
    targets = dict.fromkeys(
        arg for _a, _b, kind, arg in instructions if kind in {"one", "jump"}
    )
    slot_of = {arg: i for i, arg in enumerate(targets)}
    data_base = 9
    code_base = data_base + onebase + len(targets)

    cells: list[int] = []
    for a, b, kind, arg in instructions:
        if kind == "out":
            cells += [-3, data_base + b, 0]
        elif kind == "halt":
            cells += [0, 0, 3]
        elif kind == "nxt":
            cells += [data_base + a, -2, data_base + nxtbase + arg]
        elif kind == "jump":
            cells += [0, 0, data_base + onebase + slot_of[arg]]
        else:
            cells += [data_base + a, data_base + b, data_base + onebase + slot_of[arg]]

    data = (
        [-_ASCII_ONE, _ASCII_ZERO, _ASCII_ONE, -1]
        + [0] * n
        + [code_base + 3 * (i + 1) for i in range(n)]
        + [code_base + 3 * arg for arg in targets]
    )
    # Instruction 0 jumps over inert low-address data to the code.  Keeping
    # the data first shortens every repeated a/b/c operand; the large code
    # targets remain values stored once in that data.
    prelude = [0, 0, 6, -1, 0, 0, code_base, 0, 0]
    cells = prelude + data + cells
    return " ".join(map(str, cells))


LANGUAGE = Language(
    "S*bleq",
    "tape_based.sbleq",
    boolean=sbleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    eof="a failed read leaves the cell alone and the program runs on",
)
