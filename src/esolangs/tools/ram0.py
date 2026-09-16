"""Boolean-function generator for RAM0."""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    decision_tree_tokens,
)


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
    template's ``{Xi}`` placeholders become a fixed-length two-command
    setter — ``Z Z`` for a zero, ``Z A`` for a one — independent of the
    incoming register (``Z`` resets absolutely).  The earlier wall's
    variable-length setter (``Z`` vs ``Z A``) was what shifted the absolute
    ``goto`` operands; the padded setter removes that.

    A load phase stores each bit once in its own RAM cell,
    so the inputs are embedded exactly ``n`` times; the decision tree then
    *loads* each bit with RAM0's indirect ``L`` (``z := ram[z]``) rather than
    re-embedding it, so the tree nodes contain no substitution.  Each node
    sets ``z`` to its address, loads the bit, and ``C`` skips the following
    ``goto`` when ``z`` is zero (the zero-subtree falls through in place)
    while the ``goto`` jumps to the one-subtree otherwise.  A leaf sets
    ``z`` to the answer and jumps to a fixed low-address halt trampoline, so
    the final ``z`` read from the state dump is the answer.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    Folding a subtree needs the rows it covers to agree, and which rows a
    subtree covers is what the split order decides; RAM0 also spells an
    input as a run of ``A`` as long as its *address*, so a cheap order here
    additionally benefits from low addresses at deep, oft-repeated levels.
    That assignment is fixed optimally by depth: level ``n-1`` uses address
    zero, up to the root at ``n-1``.  The load remains in input order, so the
    ``{Xi}`` placeholders and their positions are untouched.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _ram0_ordered)
    return _ram0_linear(truth_table)


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
        emit("N", "{X" + str(i) + "}", "S")

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
        extra.append(extra[-1] + token.startswith("{X"))
    for at, target in jumps:
        target_at = labels[target]
        tokens[at] = str(target_at + extra[target_at] + 1)
    return " ".join(tokens)


def _ram0_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's RAM0 template; see :func:`ram0`.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame.  ``perm`` decides which named input is loaded into each
    depth-assigned cell; nodes use address ``n - 1 - level``.
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
        tokens.append("{X" + str(i) + "}")  # expands to "Z A" / "Z Z"
        pos += 2
        tokens.append("S")
        pos += 1

    def leaf_tokens(_level: int, row: int) -> list[str]:
        return ["Z", "A" if truth_table[row] == "1" else "Z", "2"]

    def node(level: int, zero: list[str], one: list[str], at: int) -> list[str]:
        # ``Z``, the level's ``A`` run, ``L``, ``C`` and the ``ONE@`` slot all
        # precede the subtrees, which is the node's own width; the one subtree
        # therefore starts a further ``len(zero)`` along, 1-based.
        return [
            "Z",
            *("A" for _ in range(n - 1 - level)),
            "L",
            "C",
            f"ONE@{at + width(level) + len(zero) + 1}",
            *zero,
            *one,
        ]

    # Every tree token is one command (unlike the load block's ``{Xi}``, which
    # expands to two), so the tree's command count is its token count.
    tree = decision_tree_tokens(
        truth_table,
        leaf_tokens,
        node,
        parent_width=width,
        start=pos,
        collapse=True,
    )
    tokens += tree
    end = pos + len(tree) + 1  # 1-based goto operand just past the last command
    return " ".join(
        str(end) if t == "END@" else str(int(t[4:])) if t.startswith("ONE@") else t
        for t in tokens
    )
