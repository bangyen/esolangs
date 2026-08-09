"""Generate programs that compute a boolean function from a truth table.

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given.
"""

from collections.abc import Sequence
from typing import cast

from esolangs.tools.transpilers import _six_five_label, bf_to_ascii_art

# Dig blocks for one level of the decision tree.
_DIG_BRANCH = ">2$~;#@"  # read a bit, store it, then turn on it
_DIG_CONTINUE = "> "  # a child of a branch: keep facing right into its own block
_DIG_LEAF = ">$3{}:@"  # set the mole to the result and print it

# 6-5 jump labels: ``8n`` jumps to the n-th ``4`` marker counted from the
# program start.  The label character is consumed as the ``8n`` operand, so it
# must not be a command: the digits 0..9 then A..Z (values 1..35) provide the
# k-th marker's label via ``_six_five_label``.


def sophie(truth_table: str, n: int) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@$48{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. Each leaf sets the
    result with ``#$48``/``#$49`` and prints it before halting.
    """

    def build(path: list[int]) -> str:
        depth = len(path)
        if depth == n:
            row = 0
            for bit in path:
                row = row * 2 + bit
            return f"#${48 + int(truth_table[row])},&"
        return ";" + "@$48{" + build([*path, 0]) + "}" + "{" + build([*path, 1]) + "}"

    return build([])


def modulous(truth_table: str, n: int) -> str:
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """

    def build(S: list[int], k: int) -> str:
        if len(S) == 1:
            return f"[PSH INT {truth_table[S[0]]}][PRT INT][END]"
        g0 = [r for r in S if ((r >> (n - k)) & 1) == 0]
        g1 = [r for r in S if ((r >> (n - k)) & 1) == 1]
        sub0 = build(g0, k - 1)
        sub1 = build(g1, k - 1)
        d = 2 + sub0.count("[")
        return f"[JMP F 2 IF 0][JMP F {d} IF 1][POP]{sub0}[POP]{sub1}"

    return "[INP INT]" * n + build(list(range(2**n)), n)


def brainif(truth_table: str, n: int) -> str:
    """Build a BrainIf program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    BrainIf reads each input into a cell with ``if 0 input``, then a
    recursive decision tree checks each cell with ``if 48/49 goto`` (the
    groups' checks sit adjacent so a failed check falls through to the next
    candidate). Each leaf moves to a fresh cell, increments it to 48+r, and
    outputs it.
    """

    entries: list[tuple[object, ...]] = []
    for i in range(n):
        entries.append(("cmd", "if 0 input"))
        if i < n - 1:
            entries.append(("cmd", "if 48 move right"))
            entries.append(("cmd", "if 49 move right"))
    for _ in range(n - 1):
        entries.append(("cmd", "if 48 move left"))
        entries.append(("cmd", "if 49 move left"))

    counter = [0]

    def build(rows: list[int], k: int) -> list[tuple[object, ...]]:
        if len(rows) == 1:
            r = int(truth_table[rows[0]])
            block: list[tuple[object, ...]] = [
                ("cmd", "if 48 move right"),
                ("cmd", "if 49 move right"),
            ]
            block += [("cmd", f"if {v} increment") for v in range(48 + r)]
            block.append(("cmd", f"if {48 + r} output"))
            block.append(("if_goto", 48 + r))
            return block
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        l0, l1 = counter[0], counter[0] + 1
        counter[0] += 2
        sub0 = build(g0, k + 1)
        sub1 = build(g1, k + 1)
        return [
            ("if", 48, l0),
            ("if", 49, l1),
            ("mr", 48, l0),
            *sub0,
            ("mr", 49, l1),
            *sub1,
        ]

    entries += build(list(range(2**n)), 1)
    entries.append(("end",))
    labels = {
        cast(int, entry[2]): i + 1
        for i, entry in enumerate(entries)
        if entry[0] == "mr"
    }
    end_line = len(entries)

    lines: list[str] = []
    for entry in entries:
        if entry[0] == "cmd":
            lines.append(cast(str, entry[1]))
        elif entry[0] == "if":
            lines.append(f"if {entry[1]} goto {labels[cast(int, entry[2])]}")
        elif entry[0] == "mr":
            lines.append(f"if {entry[1]} move right")
        elif entry[0] == "if_goto":
            lines.append(f"if {entry[1]} goto {end_line}")
        else:
            lines.append("")
    return "\n".join(lines)


def nevermind(truth_table: str, n: int) -> str:
    """Build a Nevermind program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Nevermind reads each input with ``input,?`` into its own variable, then a
    decision tree of nested ``if``/``endif`` blocks prints the result for the
    matching combination.
    """
    lines: list[str] = []
    for i in range(n):
        lines.append("input,?")
        lines.append(f"make,{chr(ord('a') + i)},$answer")

    def build(k: int, row: int) -> None:
        if k == n:
            lines.append(f"print,{truth_table[row]}")
            return
        for bit in (0, 1):
            lines.append(f"if,${chr(ord('a') + k)},==,{bit}")
            build(k + 1, row * 2 + bit)
            lines.append("endif")

    build(0, 0)
    return "\n".join(lines)


def circlefuck(truth_table: str, n: int) -> str:
    """Build a CircleFuck program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    CircleFuck reads each input with ``,`` and normalizes it to 0/1 with 48
    ``-``s, then a decision tree branches on the cells from the last input
    down. Each leaf starts from a cleared cell, so it sets the result with
    ``+``s, prints it, and halts with ``@`` -- halting at the leaf means the
    tree never needs to skip the sibling branch.
    """

    def emit(c: str) -> None:
        prog.append(c)

    prog: list[str] = []
    for _ in range(n):
        emit(",")
        prog.extend("-" * 48)
        emit(">")
    prog.pop()  # the trailing ">" would leave the pointer past the last input

    def build(k: int, row: int) -> None:
        if k < 0:
            prog.extend("+" * (48 + int(truth_table[row])))
            emit(".")
            emit("@")
            return
        emit("[")
        emit("[-]")
        if k:
            emit("<")
        build(k - 1, row + 2 ** (n - 1 - k))
        emit("]")
        if k:
            emit("<")
        build(k - 1, row)

    build(n - 1, 0)
    return "".join(prog)


def circlefuck_byte(truth_table: Sequence[int], n: int) -> str:
    """Build a CircleFuck program computing a byte-valued function.

    ``truth_table`` is a sequence of ``2**n`` byte values (0-255) indexed by
    the inputs (most significant first), and ``n`` is the number of bit
    inputs.  This is the boolean generator generalized to arbitrary byte
    outputs: each leaf prints ``chr(value)`` instead of ``chr(48 + bit)``.
    """

    prog: list[str] = []

    def emit(c: str) -> None:
        prog.append(c)

    for _ in range(n):
        emit(",")
        prog.extend("-" * 48)
        emit(">")
    prog.pop()  # the trailing ">" would leave the pointer past the last input

    def build(k: int, row: int) -> None:
        if k < 0:
            value = truth_table[row]
            if value:
                prog.extend("+" * value)
            emit(".")
            emit("@")
            return
        emit("[")
        emit("[-]")
        if k:
            emit("<")
        build(k - 1, row + 2 ** (n - 1 - k))
        emit("]")
        if k:
            emit("<")
        build(k - 1, row)

    build(n - 1, 0)
    return "".join(prog)


def _reorder_tt(tt: str, n: int) -> str:
    """Reorder truth table entries for the even/odd selection scheme.

    Even-reduce levels (0 .. n-2) put the 1-group first; the final
    odd-reduce level puts the 0-group first.  Sorting by
    ``(-(i >> 1), i & 1)`` satisfies both.
    """
    indices = sorted(range(2**n), key=lambda i: (-(i >> 1), i & 1))
    return "".join(tt[i] for i in indices)


def _even_reduce(pairs: int, level: int, n: int) -> str:
    """Even-reduction block: select half the value pairs, keep all inputs."""
    processed = level
    ahead = n - level
    total = n
    rot = 2 * pairs + 2 + processed
    return (
        "e" * rot
        + "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )


# Odd-reduce block for the final two-value selection (committed n=2 pattern).
_SEL1_N2: str = (
    "e" * 7
    + "gy"
    + "e" * 3
    + "gz"
    + "e" * 3
    + "gy"
    + "e" * 3
    + "gz"
    + "ff"
    + "gy"
    + "e" * 4
    + "gz"
    + "e"
    + "a"
    + "e" * 4
    + "i"
)


def _build_padded_tt(truth_table: str, n_effective: int) -> str:
    """Pad truth table for ghost-scheme: ghost=1 entries are all zero."""
    half = 2 ** (n_effective - 1)
    return truth_table.ljust(half * 2, "0")


def _validate_tt(truth_table: str, n: int) -> None:
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}"
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    """Odd-reduction: zero prev, swap, even-reduce.  Does NOT pop.

    The ZS adds an extra ghost cell at the front, so the even-reduce
    inside uses ``ahead = n - level + 1`` instead of ``n - level``.
    """
    processed = level
    ahead = n - level + 1  # +1 for the ghost cell added by the swap
    total = n
    qlen = 2 * pairs + 2 + total
    rot = 2 * pairs + 2 + (processed - 1) if processed > 0 else 0
    zero = "gy" + "j" + "e" * (qlen - 1) + "gz"
    swap = "e" + "gy" + "j" + "e" * (qlen - 2) + "j" + "gz"
    bring = "e" * (qlen - 1)
    er = (
        "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )
    return "e" * rot + zero + swap + bring + er


def taglate(truth_table: str, n: int) -> str:
    """Build a Taglate program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    ``n == 1`` reads the single input with ``h`` and computes the affine
    combination ``base + bit * coeff``.

    For ``n >= 2`` the queue is seeded and a prefix of ``h``/``e``/``b``/
    ``d``/``j`` builds the selection layout.  Odd ``n`` prepends a fake
    zero input (ghost digit).  Even levels use even-reduce (select half,
    keep all inputs); odd levels zero the previous input, swap, even-
    reduce on the ghost-encoded value, and pop both inputs.  The final
    odd-reduction block reuses the proven ``n==2`` pattern and prints
    the result.
    """
    if n == 1:
        _validate_tt(truth_table, n)
        base = 48 + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    _validate_tt(truth_table, n)

    # For odd n, prepend a fake zero-input (ghost) to make the stride land
    # on a separator.  n_effective is the number of h-reads and levels.
    if n % 2 == 1 and n > 1:
        n_eff = n + 1
        full_tt = _build_padded_tt(truth_table, n_eff)
    else:
        n_eff = n
        full_tt = truth_table

    seed = "1" * (n_eff - 1) + "0" * (2 ** (n_eff + 2) + 2) + "1"

    ordered = _reorder_tt(full_tt, n_eff)
    selectors = "".join("bd" if c == "1" else "bb" for c in ordered)

    prefix = (
        "he" * (n_eff - 1)
        + "h"
        + selectors
        + "ee"
        + "b" * n_eff
        + "e" * (2 ** (n_eff + 1) + 2)
        + "j" * n_eff
    )

    select_parts: list[str] = []
    for level in range(n_eff - 1):
        pairs = 2 ** (n_eff - level)
        if level % 2 == 0:
            select_parts.append(_even_reduce(pairs, level, n_eff))
        else:
            select_parts.append(_odd_reduce(pairs, level, n_eff))

    if n_eff > 2:
        # Drop the first n_eff-2 already-used inputs, then rotate the
        # remaining two inputs so the queue matches the 8-cell [0, w0, 0,
        # w1, 48, 48, prev, curr] layout that the committed n=2 odd
        # selector (_SEL1_N2) expects.
        select_parts.append("e" * 6 + "f" * (n_eff - 2) + "e" * 2)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result


def dig(truth_table: str, n: int) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    The tree is laid out so the mole starts in the top-left corner (``'``)
    facing down into the root.  Each branch block reads one input bit:
    ``~`` inputs it, ``;`` stores it in the grid, and ``#`` turns the mole
    down or up on that bit.  The two children of a node keep facing right
    into the next level's branch, and the leaves print the function's value
    for the input combination they stand for.
    """
    total = 2 ** (n + 1) - 1
    lines = ["" for _ in range(total)]
    rows = [total // 2]

    for level in range(n + 1):
        if level < n:
            step = 2 ** (n - level - 1)
            children = [row + step for row in rows] + [row - step for row in rows]
            for row in range(total):
                if row in rows:
                    block = _DIG_BRANCH
                elif row in children:
                    # the mole arrives here vertically from the parent's "#";
                    # right-justify the turn so the ">" sits under that "#"
                    block = _DIG_CONTINUE.rjust(len(_DIG_BRANCH))
                else:
                    block = " " * len(_DIG_BRANCH)
                lines[row] += block
            rows = children
        else:
            for k in range(2**n):
                lines[2 * k] += _DIG_LEAF.format(int(truth_table[k]))

    # the mole starts at the top-left corner facing down into the root
    lines[0] = "'" + lines[0][1:]
    return "\n".join(lines)


def six_five(truth_table: str, n: int) -> str:
    """Build a 6-5 program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Each input is read with ``B`` and normalized to 8/9 (subtracting 40 with
    eight ``2``s).  ``78`` branches: the ``7`` compares the cell to 8, so a
    zero bit skips the following ``8n`` jump and falls into the left subtree,
    while a one bit takes the jump to the n-th ``4`` marker holding the right
    subtree.  A leaf adds ``48 + value - base`` (8 for a left path, 9 for a
    right path) with a run of sixes plus ``62`` pairs (each ``6`` then ``2``
    nets ``+6 - 5 = +1``), prints with ``A``, and halts with ``0``.

    The branch labels are the digits 0..9 then A..Z (values 1..35, consumed
    as ``8n`` operands), one per internal node, so the generator caps at
    n == 5 (31 internal nodes).
    """
    if 2**n - 1 > 35:
        raise ValueError("the 6-5 boolean generator supports n <= 5 only")
    marker = 0

    def build(rows: list[int], bit: int, base: int) -> str:
        nonlocal marker
        if len(rows) == 1:
            delta = 48 + int(truth_table[rows[0]]) - base
            q, r = divmod(delta, 6)
            return "6" * q + "62" * r + "A0"
        g0 = [r for r in rows if ((r >> (n - bit)) & 1) == 0]
        g1 = [r for r in rows if ((r >> (n - bit)) & 1) == 1]
        sub0 = build(g0, bit + 1, 8)
        label = marker + 1
        marker += 1
        sub1 = build(g1, bit + 1, 9)
        return "B" + "2" * 8 + "78" + "8" + _six_five_label(label) + sub0 + "4" + sub1

    return build(list(range(2**n)), 1, 0)


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return bin(n)[2:].replace("0", "e").replace("1", "y")


def qoibl(truth_table: str, n: int) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Each input is read with ``et`` and normalized to 0/1 (``ry ey ry 48``),
    and each one's complement ``1 - bit`` is stored too.  The function is then
    evaluated as the sum over its minterms: every ``1`` row contributes the
    product of the bits (or complements) that select it, accumulated into a
    sum variable, and ``tt`` prints ``48 + sum``.  Qoibl's ``ry`` chains parse
    right-associatively from the leftmost ``ry``, so each minterm is a chain
    of plain ``qe`` reads (no operator inside a factor).

    When the table has more ``1``s than ``0``s the complement is evaluated
    instead (fewer minterms) and ``49 - sum`` is printed, keeping the program
    under the size of the sparser half.
    """
    use_complement = truth_table.count("1") > 2**n // 2
    table = (
        truth_table
        if not use_complement
        else "".join("1" if c == "0" else "0" for c in truth_table)
    )
    lines = []
    for i in range(n):
        lines.append(f"we {_qoibl_enc(i)} we et ry ey ry {_qoibl_enc(48)} we")
    for i in range(n):
        lines.append(
            f"we {_qoibl_enc(n + i)} we {_qoibl_enc(1)} ry ey ry qe {_qoibl_enc(i)} qe we"
        )
    lines.append(f"we {_qoibl_enc(2 * n)} we {_qoibl_enc(0)} we")
    for k in range(2**n):
        if table[k] == "0":
            continue
        factors = []
        for i in range(n):
            var = i if ((k >> (n - 1 - i)) & 1) else n + i
            factors.append(f"qe {_qoibl_enc(var)} qe")
        product = factors[0]
        for factor in factors[1:]:
            product = f"{product} ry ye ry {factor}"
        lines.append(f"we {_qoibl_enc(2 * n + 1)} we {product} we")
        lines.append(
            f"we {_qoibl_enc(2 * n)} we qe {_qoibl_enc(2 * n)} qe ry ee ry qe {_qoibl_enc(2 * n + 1)} qe we"
        )
    if use_complement:
        lines.append(f"tt {_qoibl_enc(49)} ry ey ry qe {_qoibl_enc(2 * n)} qe tt")
    else:
        lines.append(f"tt qe {_qoibl_enc(2 * n)} qe ry ee ry {_qoibl_enc(48)} tt")
    return "\n".join(lines)


def _bf_minterm(truth_table: str, n: int) -> str:
    """A brainfuck program that evaluates ``truth_table`` via its minterms.

    The output is ``48 + sum_k tt[k] * M_k`` where ``M_k`` is the product of
    the input bits (or their complements) that select row ``k``.  BF has no
    branching that would let leaves skip siblings, so a branch-free sum of
    minterms (each computed with 0/1 copies and ANDs) is used instead.
    Cells: inputs at 1..n, the running sum at n+1, and fresh scratch cells
    allocated above that.

    When the table has more ``1``s than ``0``s the complement is evaluated
    instead (fewer minterms) and ``49 - sum`` is printed.
    """
    use_complement = truth_table.count("1") > 2**n // 2
    table = (
        truth_table
        if not use_complement
        else "".join("1" if c == "0" else "0" for c in truth_table)
    )

    class _Cell:
        def __init__(self, n: int) -> None:
            self.n = n
            self.inputs = list(range(1, n + 1))
            self.sum = n + 1
            self.next_cell = n + 2
            self.code: list[str] = []
            self.ptr = 0

        def alloc(self) -> int:
            cell = self.next_cell
            self.next_cell += 1
            return cell

        def move(self, dst: int) -> None:
            delta = dst - self.ptr
            self.code.append(">" * delta if delta >= 0 else "<" * -delta)
            self.ptr = dst

        def zero(self, cell: int) -> None:
            self.move(cell)
            self.code.append("[-]")

        def copy(self, src: int, dst: int) -> None:
            """Copy ``src`` to ``dst`` preserving ``src`` (two scratch cells)."""
            a, b = self.alloc(), self.alloc()
            self.zero(a)
            self.zero(b)
            self.move(src)
            self.code.append("[")
            self.move(a)
            self.code.append("+")
            self.move(b)
            self.code.append("+")
            self.move(src)
            self.code.append("-]")
            self.move(a)
            self.code.append("[")
            self.move(src)
            self.code.append("+")
            self.move(a)
            self.code.append("-]")
            self.move(b)
            self.code.append("[")
            self.move(dst)
            self.code.append("+")
            self.move(b)
            self.code.append("-]")
            self.move(dst)

    cell = _Cell(n)
    for i in cell.inputs:
        cell.move(i)
        cell.code.append(",")
        cell.code.append("-" * 48)
    cell.zero(cell.sum)
    for k in range(2**n):
        if table[k] == "0":
            continue
        factors: list[int] = []
        for i in range(n):
            f = cell.alloc()
            cell.zero(f)
            if (k >> (n - 1 - i)) & 1:
                cell.copy(cell.inputs[i], f)
            else:
                cell.move(f)
                cell.code.append("[-]+")
                tmp = cell.alloc()
                cell.copy(cell.inputs[i], tmp)
                cell.move(tmp)
                cell.code.append("[")
                cell.move(f)
                cell.code.append("-")
                cell.move(tmp)
                cell.code.append("-]")
            factors.append(f)
        prod = factors[0]
        for factor in factors[1:]:
            newp = cell.alloc()
            cell.zero(newp)
            t1 = cell.alloc()
            cell.zero(t1)
            cell.copy(prod, t1)
            t2 = cell.alloc()
            cell.zero(t2)
            cell.copy(factor, t2)
            cell.move(t1)
            cell.code.append("[")
            cell.move(t2)
            cell.code.append("[")
            cell.move(newp)
            cell.code.append("+")
            cell.move(t2)
            cell.code.append("-]")
            cell.move(t1)
            cell.code.append("-]")
            prod = newp
        tmp = cell.alloc()
        cell.zero(tmp)
        cell.copy(prod, tmp)
        cell.move(tmp)
        cell.code.append("[")
        cell.move(cell.sum)
        cell.code.append("+")
        cell.move(tmp)
        cell.code.append("-]")
    cell.move(cell.sum)
    if use_complement:
        # The sum holds 0/1 for the complement; print 49 - sum via a fresh
        # cell to the right (cleared, set to 49, decremented by the sum).
        cell.code.append(">[-]" + "+" * 49 + "<[>-<-]>.")
    else:
        cell.code.append("+" * 48)
        cell.code.append(".")
    return "".join(cell.code)


def ascii_art(truth_table: str, n: int) -> str:
    """Build an ASCII-art program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    ASCII art is brainfuck with an art alphabet, so the program is the
    ``_bf_minterm`` brainfuck program rendered as art blocks.
    """
    return bf_to_ascii_art(_bf_minterm(truth_table, n))


def _bfstack_encoder(n: int) -> str:
    """BFStack code turning the n inputs into the number ``1 + sum(bit*2^k)``.

    Each input is read with ``,`` and normalized to 0/1 with 48 ``-``s; if it
    is one, ``[<+w>]`` adds its weight ``w`` to the accumulator below it.
    The ``+1`` offset keeps the result nonzero so the decoder's outer ``[``
    always runs (a ``0`` result would be ambiguous with a skipped loop).
    """
    prog = ">>+"  # result cell (0) below the accumulator (1)
    for k in range(n):
        weight = 2 ** (n - 1 - k)
        prog += "," + "-" * 48 + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_decoder(truth_table: str) -> str:
    """BFStack code mapping the encoded number to the table's result.

    The output is 1 for every input except the rows where the table is 0.
    Each such row maps to a distinct value of the ``+1``-offset number, so the
    decoder tests them by cumulative subtraction: ``[`` opens a ``while`` that
    only reaches the inner ``[<+>]`` (setting the result to 1) when the number
    survives every subtraction; hitting a zero row's value subtracts to 0 and
    skips the ``[<+>]`` instead, leaving the result 0.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    if not zeros:
        return "[<+>]"  # always 1
    prog = "["
    prev = 0
    for z in zeros:
        prog += "-" * (z - prev) + "["
        prev = z
    prog += "[<+>]"
    prog += "]" * (len(zeros) + 1)
    return prog


def bfstack(truth_table: str, n: int) -> str:
    """Build a BFStack program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    BFStack is a pure stack machine, so the generator avoids branching
    entirely: it encodes the n inputs as the number ``1 + sum(bit*2^k)``
    (each ``,`` reads and normalizes a bit, ``[<+w>]`` adds its weight), then
    decodes it with nested ``[`` loops that only set the result to 1 when the
    number is not one of the table's zero rows.
    """
    return _bfstack_encoder(n) + _bfstack_decoder(truth_table) + "<" + "+" * 48 + "."


def polynomial(truth_table: str, n: int) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Polynomial programs are polynomials whose roots encode instructions, so
    the generator builds a decision tree of complex ``[a, b]`` (arithmetic,
    input, output) and real ``[val]`` (if/endif) roots and expands them into
    ``f(x) = ...``.  ``n > 2`` overflows the interpreter's float root-finder:
    each instruction consumes a fresh prime, so the coefficients of a deeper
    tree exceed ``numpy``'s float64 range.
    """
    if n > 2:
        raise ValueError(
            "the Polynomial boolean generator supports n == 2 only: "
            "each instruction consumes a fresh prime, so the expanded "
            "coefficients of a deeper tree overflow the interpreter's "
            "float root-finder"
        )

    from esolangs.tools._polynomial import format_coeffs, multiply, primes

    instrs: list[list[int]] = []

    def emit_delta(delta: int) -> None:
        if delta > 0:
            instrs.append([delta, 1])
        elif delta < 0:
            instrs.append([-delta, 2])

    def build(rows: list[int], bit: int, last: int) -> None:
        if len(rows) == 1:
            v = int(truth_table[rows[0]])
            emit_delta(48 + v - last)
            instrs.append([0, 1])  # output
            emit_delta(1 - (48 + v))  # restore reg to nonzero so the else skips
            return
        instrs.extend([[0, 2], [48, 2]])  # input; -= 48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0 -> the one-bit subtree
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0 -> the zero-bit subtree
        build(g0, bit + 1, 0)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    coeffs = [1]
    for instr, p in zip(instrs, primes(len(instrs)), strict=True):
        if len(instr) == 2:
            a, b = instr
            coeffs = multiply(coeffs, [1, -2 * a, a * a + p ** (2 * b)])
        else:
            coeffs = multiply(coeffs, [1, -(p ** instr[0])])
    return str(format_coeffs(coeffs))
