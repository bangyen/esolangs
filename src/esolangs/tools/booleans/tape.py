"""Boolean-function generators for tape-based languages."""

from collections.abc import Sequence
from typing import cast

from esolangs.tools.transpilers import _six_five_label, bf_to_ascii_art


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
