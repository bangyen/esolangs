"""Boolean-function generator for RAM0."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    in_input_order,
    subtree_ids,
    subtree_slot,
)

#: A fixed Z precedes each slot; the one-command pair selects zero or one.
PAIR = ("Z", "A")
_RAM0_INPUT = TEMPLATE_CHAR * len(PAIR[0])

#: A leaf: set ``z`` to the answer and jump to the halt trampoline.
_LEAF = "Z A 2"


def ram0(truth_table: str, width: int | None = None) -> str:
    """Build a RAM0 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  ``width=1`` through three inputs uses
    unary-address NAND circuits; otherwise the shared tree.  Only final ``z``
    is the answer.

    RAM0 has no input command, so each input run becomes a fixed-length
    ``Z``, ``Z``/``A`` unit independent of the incoming register (``Z`` resets
    absolutely); a variable-length setter would shift the absolute ``goto``
    operands.

    The load stores each bit once in its own RAM cell, the level-``k`` test in
    cell ``n-1-k``.  Tree nodes use indirect ``L`` (``z := ram[z]``), then
    ``C`` falls through to the zero-subtree or a ``goto`` reaches the
    one-subtree.  A leaf sets the answer and jumps to a fixed low-address halt
    trampoline.

    A repeated subtree is emitted once and jumped to: a one-subtree equal to
    one already emitted at its level costs nothing, a zero-subtree costs one
    ``goto``, a leaf is shared the same way, and a test whose halves agree is
    skipped.  That caps the tree at its distinct subtables.
    """
    if width is None:
        return in_input_order(truth_table, _ram0_shared)
    from esolangs.tools.wrap import wrap_space_delimited

    if width == 1 and len(truth_table) <= 8:  # three inputs
        program = _ram0_nand(truth_table)
    else:
        program = in_input_order(truth_table, _ram0_shared)
    return wrap_space_delimited(program, width)


def _ram0_nand(truth_table: str) -> str:
    """Build small Shannon circuits using unary addresses and NAND stores."""
    n = _validate_truth_table(truth_table)
    # RAM[0:2] implements NOT. A NAND writes NOT b to RAM[2+a], with
    # RAM[3] reset to 1: reading RAM[3] then returns NOT(a AND b).
    tokens = ["Z", "N", "A", "S"]

    def address_op(address: int, op: str) -> None:
        tokens.extend(["Z", *("A" for _ in range(address)), op])

    def target(address: int) -> None:
        address_op(address, "N")

    def load(address: int) -> None:
        address_op(address, "L")

    for i in range(n):
        target(4 + i)
        tokens.extend(["Z", _RAM0_INPUT, "S"])
    gates: dict[tuple[int, int], int] = {}
    next_address = 4 + n

    def nand(left: int, right: int) -> int:
        nonlocal next_address
        if left == 1 or right == 1:
            return 0
        # Two true constants use the store kernel, avoiding self-recursion.
        if left == 0 and right != 0:
            return nand(right, right)
        if right == 0 and left != 0:
            return nand(left, left)
        pair = (min(left, right), max(left, right))
        if pair in gates:
            return gates[pair]
        result = next_address
        next_address += 1
        target(3)
        tokens.extend(["Z", "A", "S"])
        load(left)
        tokens.extend(["A", "A", "N"])
        load(right)
        tokens.extend(["L", "S"])
        target(result)
        load(3)
        tokens.append("S")
        gates[pair] = result
        return result

    def tree(rows: str, level: int) -> int:
        if rows == rows[0] * len(rows):
            return 1 - int(rows[0])
        half = len(rows) // 2
        zero = tree(rows[:half], level + 1)
        one = tree(rows[half:], level + 1)
        if zero == one:
            return zero
        bit = 4 + level
        inverted = nand(bit, bit)
        return nand(nand(inverted, zero), nand(bit, one))

    # Unary addresses would cost O(T squared) at unrestricted arity;
    # the three-input cap keeps this fallback uniformly O(T).
    load(tree(truth_table, 0))
    return " ".join(tokens)


def _ram0_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's shared tree; see :func:`_ram0_ordered`."""
    return _ram0_ordered(truth_table, perm, share=True)


def _ram0_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = False
) -> str:
    """Emit one input order's RAM0 template; see :func:`ram0`.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame.  ``perm`` decides which named input is loaded into each
    depth-assigned cell; nodes use address ``n - 1 - level``.  ``share``
    jumps to a subtree already emitted instead of repeating it.
    """
    n = _validate_truth_table(truth_table)

    # Initial z == 0 makes C skip the widening end target.  Leaves jump to
    # that target through fixed 1-based address 2.
    tokens = ["C", "END@"]

    # Store the deepest, most repeated test at address zero.  Placeholders
    # remain in input-name order; only their destination cell changes.
    address_of = {input_index: n - 1 - level for level, input_index in enumerate(perm)}
    for i in range(n):
        address = address_of[i]
        tokens.append("Z")
        tokens.extend("A" for _ in range(address))
        tokens.append("N")
        tokens.extend(("Z", _RAM0_INPUT))  # reset, then set the bit
        tokens.append("S")

    pos = len(tokens)  # instantiated command index of the next command
    ids = subtree_ids(truth_table)
    tree: list[str] = []
    # First address of each emitted subtree, by :func:`subtree_slot` name.
    placed: dict[tuple[int, int], int] = {}

    def resolve(level: int, block: int) -> tuple[int, int, tuple[int, int]]:
        return subtree_slot(ids, level, block, skip=share)

    def emit(level: int, block: int) -> None:
        """Lay the subtree out where control falls in, or jump to its copy."""
        level, block, slot = resolve(level, block)
        copy = placed.get(slot)
        # A jump is one token; a leaf is 3, so jump to it only if copy has <3 digits.
        if copy is not None and (slot[0] >= 0 or len(str(copy)) < len(_LEAF)):
            tree.append(str(copy))
            return
        if share:
            placed.setdefault(slot, pos + len(tree) + 1)
        if slot[0] < 0:
            tree.extend(["Z", "A" if slot[1] else "Z", "2"])
            return
        at = len(tree)
        head = ["Z", *("A" for _ in range(n - 1 - level)), "L", "C"]
        tree.extend([""] * (len(head) + 1))
        emit(level + 1, 2 * block)
        # The one subtree is jumped to, so an earlier copy costs nothing.
        one = placed.get(resolve(level + 1, 2 * block + 1)[2])
        if one is None:
            one = pos + len(tree) + 1
            emit(level + 1, 2 * block + 1)
        tree[at : at + len(head) + 1] = [*head, str(one)]

    emit(0, 0)
    tokens += tree
    end = pos + len(tree) + 1  # 1-based goto operand just past the last command
    return " ".join(str(end) if t == "END@" else t for t in tokens)


LANGUAGE = Language(
    "RAM0",
    "register_based.ram0",
    boolean=ram0,
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"z: (\d+)",
        note="RAM0 has no output instruction and dumps its whole state "
        "at halt; the answer is the 'z' register",
        parameterized=True,
    ),
)
