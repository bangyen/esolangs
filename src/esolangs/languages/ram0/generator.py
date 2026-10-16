"""RAM0 Boolean program generator: a shared decision tree over RAM cells.

Each input is stored once in its own RAM cell, the level-``k`` test in cell
``n-1-k``; tree nodes load the bit with indirect ``L`` (``z := ram[z]``), then
``C`` falls through to the zero-subtree or a ``goto`` reaches the
one-subtree.  A leaf sets the answer and jumps to a fixed low-address halt
trampoline.  A repeated subtree is emitted once and jumped to: a one-subtree
equal to one already emitted at its level costs nothing, a zero-subtree costs
one ``goto``, a leaf is shared the same way, and a test whose halves agree is
skipped, so the tree has one node per distinct subtable.  Width 1 through
three inputs uses unary-address NAND circuits instead.

Size:
    O(T) tokens, O(n) executed steps; n=10 random 1847: 4,347 chars,
    n=10 parity: 595 chars.
"""

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    in_input_order,
    same_token_layout,
    subtree_ids,
    subtree_slot,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _join_tokens, balance_score, wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

#: A fixed Z precedes each slot; the one-command pair selects zero or one.
#: RAM0 has no input command, so each input run is a fixed-length ``Z``,
#: ``Z``/``A`` unit independent of the incoming register (``Z`` resets
#: absolutely); a variable-length setter would shift the absolute ``goto``
#: operands.
PAIR = ("Z", "A")
_RAM0_INPUT = TEMPLATE_CHAR * len(PAIR[0])

#: A leaf: set ``z`` to the answer and jump to the halt trampoline.
_LEAF = "Z A 2"


def ram0(truth_table: str, width: int | None = None) -> str:
    """Build a RAM0 template; ``width=1`` through three inputs uses NAND circuits.

    Only final ``z`` is the answer.
    """
    if width is None:
        return in_input_order(truth_table, _ram0_shared)

    if width == 1 and len(truth_table) <= 8:  # three inputs
        program = _ram0_nand(truth_table)
    else:
        program = in_input_order(truth_table, _ram0_shared)
    return wrap_space_delimited(program, width)


def _address(k: int, op: str) -> list[str]:
    """Return the unary address ``k`` (reset, ``k`` increments) then ``op``."""
    return ["Z", *["A"] * k, op]


def _ram0_nand(truth_table: str) -> str:
    """Build small Shannon circuits using unary addresses and NAND stores."""
    n = _validate_truth_table(truth_table)
    # RAM[0:2] implements NOT. A NAND writes NOT b to RAM[2+a], with
    # RAM[3] reset to 1: reading RAM[3] then returns NOT(a AND b).
    tokens = ["Z", "N", "A", "S"]

    def address_op(address: int, op: str) -> None:
        tokens.extend(_address(address, op))

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

    # A unary address would cost O(T squared) at unrestricted arity;
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

    # "END@" is a forward reference: leaves jump to command 2, and command 2
    # must hold the address just past the last tree token -- which is only
    # known once the tree is laid out.  The leading "C" skips its operand
    # while z is still zero, so the operand doubles as the halt trampoline:
    # a leaf's goto 2 lands on "goto end" and halts with z as the answer.
    tokens = ["C", "END@"]

    # Store the deepest, most repeated test at address zero.  Placeholders
    # remain in input-name order; only their destination cell changes.
    address_of = {input_index: n - 1 - level for level, input_index in enumerate(perm)}
    for i in range(n):
        address = address_of[i]
        tokens.extend(_address(address, "N"))
        tokens.extend(("Z", _RAM0_INPUT))  # reset, then set the bit
        tokens.append("S")

    pos = len(tokens)  # token count before the tree starts
    ids = subtree_ids(truth_table)
    tree: list[str] = []
    # First address of each emitted subtree, by :func:`subtree_slot` name.
    placed: dict[tuple[int, int], int] = {}

    def addr() -> int:
        """Return the 1-based address the next emitted token will occupy."""
        return pos + len(tree) + 1

    def resolve(level: int, block: int) -> tuple[int, int, tuple[int, int]]:
        """Return the canonical ``(level, block, slot)`` for a subtree.

        With sharing on, tests whose halves agree are skipped over to the
        surviving half (see :func:`subtree_slot`); the slot names the subtree
        for the ``placed`` lookup.
        """
        return subtree_slot(ids, level, block, skip=share)

    def emit(level: int, block: int) -> None:
        """Lay the subtree out where control falls in, or jump to its copy.

        A node is ``Z A.. L C <one>``: ``Z A.. L`` loads the level's test bit
        into ``z``, then ``C`` falls through into the zero subtree laid out
        next, or jumps to the one subtree -- an already-emitted copy when
        sharing, else the address the one subtree is about to occupy,
        backpatched into the head below.
        """
        level, block, slot = resolve(level, block)
        copy = placed.get(slot)
        # A goto is one token; re-emitting a leaf is three, so only jump to
        # a leaf copy while its address text is shorter than the leaf.
        if copy is not None and (slot[0] >= 0 or len(str(copy)) < len(_LEAF)):
            tree.append(str(copy))
            return
        if share:
            placed.setdefault(slot, addr())
        if slot[0] < 0:
            tree.extend(["Z", "A" if slot[1] else "Z", "2"])
            return
        at = len(tree)
        head = [*_address(n - 1 - level, "L"), "C"]
        # Reserve the head plus its goto operand; the one-subtree address is
        # backpatched once the fall-through zero subtree is laid out.
        tree.extend([""] * (len(head) + 1))
        emit(level + 1, 2 * block)
        # The one subtree is jumped to, so an earlier copy costs nothing.
        one = placed.get(resolve(level + 1, 2 * block + 1)[2])
        if one is None:
            one = addr()
            emit(level + 1, 2 * block + 1)
        tree[at : at + len(head) + 1] = [*head, str(one)]

    emit(0, 0)
    tokens += tree
    end = addr()  # 1-based goto operand just past the last command
    return " ".join(str(end) if t == "END@" else t for t in tokens)


def _balance(table: str, default: str) -> str:
    """Compare the width-one NAND form and ordinary operand row fits."""
    tokens = default.split()
    width = balanced_token_width(tokens, " ", minimum=2)
    return min(
        default, _join_tokens(tokens, width, " "), ram0(table, 1), key=balance_score
    )


LANGUAGE = Language(
    "RAM0",
    "ram0",
    category="register_based",
    boolean=ram0,
    same_layout=same_token_layout,
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"z: (\d+)",
        note="RAM0 has no output instruction and dumps its whole state "
        "at halt; the answer is the 'z' register",
    ),
    # Multi-character tokens (``vs``, ``0b1``, ``L C 19``); space is the
    # only safe break.
    wrap=wrap_space_delimited,
    balance=_balance,
    example=Example(pair=PAIR, expected="z: 0\nn: 0\nram: {\n    1: 0,\n    0: 1\n}"),
)
