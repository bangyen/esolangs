"""Boolean-function generator for RAM0."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    best_input_order,
    subtree_ids,
    subtree_slot,
)

#: How each input is set: ``Z`` resets the register absolutely, so ``Z Z``
#: leaves a zero and ``Z A`` a one whatever came before.  The template
#: spells each input as a run of :data:`TEMPLATE_CHAR` this wide -- one
#: token that instantiates to two commands.
PAIR = ("Z Z", "Z A")
_RAM0_INPUT = TEMPLATE_CHAR * len(PAIR[0])

#: A leaf: set ``z`` to the answer and jump to the halt trampoline.
_LEAF = "Z A 2"


def _ram0_width(address: int) -> int:
    """Commands a RAM0 tree node spends before its subtrees.

    ``Z``, an ``A`` per unit of the cell address, ``L``, ``C``, and the
    ``goto`` that reaches the one-subtree.  Addresses descend with depth,
    putting the most repeated tests in the shortest cells.
    """
    return address + 4


def ram0(truth_table: str) -> str:
    """Build a RAM0 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    RAM0 has no input command, so this is a parameterized generator: the
    template's input runs become a fixed-length two-command
    setter — ``Z Z`` for a zero, ``Z A`` for a one — independent of the
    incoming register (``Z`` resets absolutely).  The earlier wall's
    variable-length setter (``Z`` vs ``Z A``) was what shifted the absolute
    ``goto`` operands; the padded setter removes that.

    The load stores each bit once in its own RAM cell. Tree nodes use indirect
    ``L`` (``z := ram[z]``), then ``C`` falls through to the zero-subtree or a
    ``goto`` reaches the one-subtree. A leaf sets the answer and jumps to a
    fixed low-address halt trampoline; the state dump's final ``z`` is the
    answer.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    Folding a subtree needs the rows it covers to agree, and which rows a
    subtree covers is what the split order decides; RAM0 also spells an
    input as a run of ``A`` as long as its *address*, so a cheap order here
    additionally benefits from low addresses at deep, oft-repeated levels.
    That assignment is fixed optimally by depth: level ``n-1`` uses address
    zero, up to the root at ``n-1``.  The load remains in input order, so the
    input runs and their positions are untouched.

    **A repeated subtree is emitted once and jumped to.**  A node assumes
    nothing on entry (it sets ``z`` and loads its own bit), so a one-subtree
    equal to one already emitted at its level costs nothing -- its ``goto``
    names the copy -- and a zero-subtree costs one ``goto`` in place of
    itself; a leaf is shared the same way, and a test whose halves agree is
    skipped. That caps the tree at its distinct subtables, O(T) with addresses.
    The plain tree is a candidate through 16 entries and the linear lookup
    past them; at five inputs the shared tree is a fifth of the lookup.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _ram0_best)
    tree = best_input_order(truth_table, _ram0_shared)
    lookup = _ram0_linear(truth_table)
    return tree if len(tree) < len(lookup) else lookup


def _ram0_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's shared tree; see :func:`_ram0_ordered`."""
    return _ram0_ordered(truth_table, perm, share=True)


def _ram0_best(truth_table: str, perm: tuple[int, ...]) -> str:
    """Return the shorter of one order's plain and shared trees."""
    plain = _ram0_ordered(truth_table, perm)
    shared = _ram0_shared(truth_table, perm)
    return shared if len(shared) < len(plain) else plain


def _ram0_linear(truth_table: str) -> str:
    """Emit a linear straight-line RAM initializer and indexed lookup."""
    n = _validate_truth_table(truth_table)
    tokens: list[str] = []
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    def emit(*commands: str) -> None:
        tokens.extend(commands)

    def mark(name: str) -> None:
        labels[name] = len(tokens)

    def jump(target: str) -> None:
        jumps.append((len(tokens), target))
        tokens.append("@")

    def unary(value: int) -> None:
        emit("Z", *("A" for _ in range(value)))

    def store_constant(address: int, value: int) -> None:
        unary(address)
        emit("N")
        unary(value)
        emit("S")

    # Cells 0/1 hold the initializer's address counter and the selected table
    # pointer; cells 2..n+1 hold the parameterized inputs.
    for i in range(n):
        unary(i + 2)
        emit("N", _RAM0_INPUT, "S")

    table_base = n + 2
    store_constant(0, table_base - 1)
    store_constant(1, table_base)

    # Advance cell 0, using the new address as a temporary copy of itself,
    # then store one table bit there.  This is constant work per row.
    for bit in truth_table:
        emit("Z", "L", "A", "N", "S")
        emit("Z", "N", "Z", "L", "A", "L", "S")
        emit("Z", "L", "N", "Z")
        if bit == "1":
            emit("A")
        emit("S")

    # Add each set bit's weight to the selected table pointer.  Across all
    # inputs the unary runs contain 2T-2 commands.
    for i in range(n):
        unary(i + 2)
        emit("L", "C")
        one = f"input_{i}_one"
        after = f"input_{i}_after"
        jump(one)
        jump(after)
        mark(one)
        unary(1)
        emit("N", "Z", "A", "L")
        emit(*("A" for _ in range(1 << (n - 1 - i))))
        emit("S")
        mark(after)

    emit("Z", "A", "L", "L")
    extra: list[int] = [0]
    for token in tokens:
        extra.append(extra[-1] + (token == _RAM0_INPUT))
    for at, target in jumps:
        target_at = labels[target]
        tokens[at] = str(target_at + extra[target_at] + 1)
    return " ".join(tokens)


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

    def width(level: int) -> int:
        return _ram0_width(n - 1 - level)

    # Initial z == 0 makes C skip the widening end target.  Leaves jump to
    # that target through fixed 1-based address 2.
    tokens = ["C", "END@"]
    pos = len(tokens)  # instantiated command index of the next command

    # Store the deepest, most repeated test at address zero.  Placeholders
    # remain in input-name order; only their destination cell changes.
    address_of = {input_index: n - 1 - level for level, input_index in enumerate(perm)}
    for i in range(n):
        address = address_of[i]
        tokens.append("Z")
        tokens.extend("A" for _ in range(address))
        tokens.append("N")
        pos += 1 + address + 1
        tokens.append(_RAM0_INPUT)  # expands to "Z A" / "Z Z"
        pos += 2
        tokens.append("S")
        pos += 1

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
        # A jump is one token; a leaf's three only lose to a long address.
        if copy is not None and (slot[0] >= 0 or len(str(copy)) < len(_LEAF)):
            tree.append(str(copy))
            return
        if share:
            placed.setdefault(slot, pos + len(tree) + 1)
        if slot[0] < 0:
            tree.extend(["Z", "A" if slot[1] else "Z", "2"])
            return
        at = len(tree)
        tree.extend([""] * width(level))
        emit(level + 1, 2 * block)
        # The one subtree is jumped to, so an earlier copy costs nothing.
        one = placed.get(resolve(level + 1, 2 * block + 1)[2])
        if one is None:
            one = pos + len(tree) + 1
            emit(level + 1, 2 * block + 1)
        tree[at : at + width(level)] = [
            "Z",
            *("A" for _ in range(n - 1 - level)),
            "L",
            "C",
            str(one),
        ]

    emit(0, 0)
    tokens += tree
    end = pos + len(tree) + 1  # 1-based goto operand just past the last command
    return " ".join(str(end) if t == "END@" else t for t in tokens)
