"""Hoisted subtract-and-branch trees with direct or indirect jump targets."""

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    subtree_ids,
    subtree_slot,
)


def hoisted_tree(
    truth_table: str,
    perm: tuple[int, ...],
    *,
    share: bool = False,
    direct: bool = False,
) -> str:
    """Emit one input order's hoisted program; with shared residuals.

    ``perm[k]`` is the input the tree tests at level ``k``; the read block
    stays in input order, so the program consumes its input stream exactly
    as the node-read build did.  ``share`` jumps to a subtree already
    emitted instead of repeating it. ``direct`` renders byte I/O
    and immediate jump targets from the same folded instructions.
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

    if direct:
        return _direct_tree(instructions, n)

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


def _direct_tree(instructions: list[tuple[int, int, str, int]], n: int) -> str:
    """Render hoisted reads and a shared tree with direct byte I/O."""
    # D residual tests need at most D zero-edge jumps and four leaf commands.
    # Three commands per read give <=3n+2D+4 instructions, plus 7+n prefix cells.
    data_base = 3
    code_base = 7 + n

    def address(index: int) -> int:
        return code_base + 3 * (index + 2 * min(index, n))

    cells = [0, 0, code_base, -_ASCII_ONE, _ASCII_ZERO, _ASCII_ONE, 0] + [0] * n
    for index, (a, b, kind, arg) in enumerate(instructions):
        if kind == "nxt":
            # the reader takes +byte; negate it before the tree tests 49-byte.
            value = data_base + a
            pc = address(index)
            cells += [-1, 6, pc + 3, value, value, pc + 6, 6, value, pc + 9]
        elif kind == "out":
            cells += [data_base + b, -1, address(index + 1)]
        elif kind == "halt":
            cells += [0, 0, -1]
        elif kind == "jump":
            cells += [0, 0, address(arg)]
        else:
            cells += [data_base + b, data_base + a, address(arg)]
    return " ".join(map(str, cells))
