"""RAM0 Boolean program generator: a shared decision tree over RAM cells.

Each input is stored once in its own RAM cell, the level-``k`` test in cell
``n-1-k``; tree nodes load the bit with indirect ``L`` (``z := ram[z]``), then
``C`` falls through to the zero-subtree or a ``goto`` reaches the
one-subtree.  A leaf sets the answer and jumps to a fixed low-address halt
trampoline.  A repeated subtree is emitted once and jumped to: a one-subtree
equal to one already emitted at its level costs nothing, a zero-subtree costs
one ``goto``, a leaf is shared the same way, and a test whose halves agree is
skipped, so the tree has one node per distinct subtable.  A node's leading
``A`` is the part of its address a taken ``C`` already holds (``z`` = 1), so
a jump enters one token in, and a leaf one is just ``A 2``.  Width 1 through
three inputs uses unary-address NAND circuits instead.

Size:
    O(T) tokens, O(n²) executed steps; n=10 random 1847: 3,885 chars,
    n=10 parity: 557 chars; constants: 4n+1+2b chars, 2n+2+b commands.
"""

from collections.abc import Sequence

from esolangs.generation.helpers import (
    _validate_truth_table,
    subtree_ids,
    subtree_slot,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_tokens,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.languages.ram0.descriptor import PAIR as PAIR

#: A fixed Z precedes each slot; the one-command pair selects zero or one.
#: RAM0 has no input command, so each input run is a fixed-length ``Z``,
#: ``Z``/``A`` unit independent of the incoming register (``Z`` resets
#: absolutely); a variable-length setter would shift the absolute ``goto``
#: operands.
_RAM0_INPUT = InputSlot(len(PAIR[0]))


def ram0(truth_table: str, width: int | None = None) -> str:
    """Build a RAM0 template; ``width=1`` through three inputs uses NAND circuits.

    Only final ``z`` is the answer. Constants execute every setter, then reset z.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None = None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        setter: list[TemplateToken] = ["Z", _RAM0_INPUT]
        tokens = setter * n + ["Z"]
        if truth_table[0] == "1":
            tokens.append("A")
        return layout_tokens(tokens, width)
    if width == 1 and len(truth_table) <= 8:  # three inputs
        return layout_tokens(_ram0_nand(truth_table), width)
    return layout_tokens(_ram0_ordered(truth_table, tuple(range(n)), share=True), width)


def _address(k: int, op: str) -> list[str]:
    """Return the unary address ``k`` (reset, ``k`` increments) then ``op``."""
    return ["Z", *["A"] * k, op]


def _ram0_nand(truth_table: str) -> list[TemplateToken]:
    """Build small Shannon circuits using unary addresses and NAND stores."""
    n = _validate_truth_table(truth_table)
    # RAM[0:2] implements NOT. A NAND writes NOT b to RAM[2+a], with
    # RAM[3] reset to 1: reading RAM[3] then returns NOT(a AND b).
    tokens: list[TemplateToken] = ["Z", "N", "A", "S"]

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

    ids = subtree_ids(truth_table) if n > 1 else []

    def tree(level: int, block: int) -> int:
        # Unary leaves lower straight to NAND refs, avoiding two recursive calls.
        if level == n - 1:
            zero = 1 - int(truth_table[2 * block])
            one = 1 - int(truth_table[2 * block + 1])
        else:
            key = ids[level][block]
            if key < 2:
                return 1 - key
            zero = tree(level + 1, 2 * block)
            one = tree(level + 1, 2 * block + 1)
        if zero == one:
            return zero
        bit = 4 + level
        inverted = nand(bit, bit)
        return nand(nand(inverted, zero), nand(bit, one))

    # A unary address would cost O(T squared) at unrestricted arity;
    # the three-input cap keeps this fallback uniformly O(T).
    load(tree(0, 0))
    return tokens


def _ram0_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = False
) -> list[TemplateToken]:
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
    tokens: list[TemplateToken] = ["C", "END@"]

    # Store the deepest, most repeated test at address zero.  Placeholders
    # remain in input-name order; only their destination cell changes.
    address_of = {input_index: n - 1 - level for level, input_index in enumerate(perm)}
    for i in range(n):
        address = address_of[i]
        tokens.extend(_address(address, "N"))
        # reset, then set the bit; ``Z N`` already left z at 0 for cell 0
        tokens.extend((_RAM0_INPUT,) if address == 0 else ("Z", _RAM0_INPUT))
        tokens.append("S")

    tokens.append("Z")  # the root is entered with z the last input bit
    emitter = _TreeEmitter(n, subtree_ids(truth_table), share=share, pos=len(tokens))
    emitter.emit(0, 0)
    tokens += emitter.tree
    end = emitter.addr()  # 1-based goto operand just past the last command
    tokens[1] = str(end)
    return tokens


class _TreeEmitter:
    """Recursive layout of one order's shared tree, as state plus methods.

    ``tree`` accumulates the tree tokens after the ``pos`` prefix tokens
    (the halt trampoline head and the input stores); ``placed`` maps each
    emitted subtree's slot (see :func:`subtree_slot`) to the 1-based
    address of its first token.
    """

    def __init__(
        self, n: int, ids: Sequence[Sequence[int]], *, share: bool, pos: int
    ) -> None:
        self.n = n
        self.ids = ids
        self.share = share
        self.pos = pos
        self.tree: list[str] = []
        self.placed: dict[tuple[int, int], int] = {}

    def addr(self) -> int:
        """Return the 1-based address the next emitted token will occupy."""
        return self.pos + len(self.tree) + 1

    def skips(self, slot: tuple[int, int]) -> int:
        """Return 1 when a subtree's leading ``A`` is skipped by a taken ``C``.

        ``C`` jumps with ``z`` = 1, so a leaf one needs no ``A`` and a node
        needs one ``A`` fewer; a zero leaf or the cell-0 node leads with ``Z``.
        """
        return int(slot[1] == 1) if slot[0] < 0 else int(slot[0] < self.n - 1)

    def resolve(self, level: int, block: int) -> tuple[int, int, tuple[int, int]]:
        """Return the canonical ``(level, block, slot)`` for a subtree.

        With sharing on, tests whose halves agree are skipped over to the
        surviving half (see :func:`subtree_slot`); the slot names the subtree
        for the ``placed`` lookup.
        """
        return subtree_slot(self.ids, level, block, skip=self.share)

    def emit(self, level: int, block: int) -> None:
        """Lay the subtree out where control falls in, or jump to its copy.

        A node is ``Z A.. L C <one>``: ``Z A.. L`` loads the level's test bit
        into ``z``, then ``C`` falls through into the zero subtree laid out
        next, or jumps to the one subtree -- an already-emitted copy when
        sharing, else the address the one subtree is about to occupy,
        backpatched into the head below.
        """
        level, block, slot = self.resolve(level, block)
        copy = self.placed.get(slot)
        if copy is not None:
            self.tree.append(str(copy))
            return
        if self.share:
            self.placed.setdefault(slot, self.addr())
        if slot[0] < 0:
            self.tree.extend(["A" if slot[1] else "Z", "2"])
            return
        at = len(self.tree)
        a = self.n - 1 - level
        head = [*(["A"] * a if a else ["Z"]), "L", "C"]
        # Reserve the head plus its goto operand; the one-subtree address is
        # backpatched once the fall-through zero subtree is laid out.
        self.tree.extend([""] * (len(head) + 1))
        self.emit(level + 1, 2 * block)
        # The one subtree is jumped to, so an earlier copy costs nothing.
        one_slot = self.resolve(level + 1, 2 * block + 1)[2]
        one = self.placed.get(one_slot)
        if one is None:
            one = self.addr()
            self.emit(level + 1, 2 * block + 1)
        one += self.skips(one_slot)
        self.tree[at : at + len(head) + 1] = [*head, str(one)]


def ram0_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def ram0_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Balance whole tokens, retaining the input slots across row breaks."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("RAM0 balancing needs a rendered template with slots")
    tokens = list(request.source.tokens())
    width = balanced_token_width(
        [
            " " * len(token) if isinstance(token, InputSlot) else token
            for token in tokens
        ],
        " ",
    )
    return layout_tokens(tokens, width)
