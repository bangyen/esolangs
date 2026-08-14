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
    as ``8n`` operands), one per internal node, so the decision tree caps at
    n == 5 (31 internal nodes).  For larger ``n`` the generator falls back
    to :func:`six_five_arithmetic`, which packs the inputs and the table
    into single cells and decodes the table entry arithmetically with a
    constant number of loop constructs.
    """
    if 2**n - 1 <= 35:
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
            return (
                "B" + "2" * 8 + "78" + "8" + _six_five_label(label) + sub0 + "4" + sub1
            )

        return build(list(range(2**n)), 1, 0)
    return six_five_arithmetic(truth_table, n)


class _SixFiveAsm:
    """Tiny 6-5 assembler: raw text, named ``4`` markers, named ``8n`` jumps."""

    def __init__(self) -> None:
        self._ops: list[tuple[str, str]] = []

    def raw(self, text: str) -> "_SixFiveAsm":
        self._ops.append(("raw", text))
        return self

    def m(self, name: str) -> "_SixFiveAsm":
        self._ops.append(("marker", name))
        return self

    def j(self, name: str) -> "_SixFiveAsm":
        self._ops.append(("jump", name))
        return self

    def build(self) -> str:
        """Resolve ``8n`` labels against the n-th ``4`` in the stream."""
        ordinals: dict[str, int] = {}
        stream: list[tuple[str, str] | str] = []
        count4 = 0
        for op, value in self._ops:
            if op == "marker":
                count4 += 1
                ordinals[value] = count4
                stream.append("4")
            elif op == "jump":
                stream.append(("J", value))
            else:
                stream.append(value)
        out: list[str] = []
        for token in stream:
            if isinstance(token, tuple):
                out.append("8" + _six_five_label(ordinals[token[1]]))
            else:
                out.append(token)
        return "".join(out)


def _six_five_nav(src: int, dst: int) -> str:
    """Pointer moves from cell ``src`` to ``dst`` (``1`` is +2, ``3`` is -1)."""
    if dst == src:
        return ""
    if dst < src:
        return "3" * (src - dst)
    delta = dst - src
    ups = (delta + 1) // 2
    return "1" * ups + "3" * (2 * ups - delta)


def _six_five_const(value: int) -> str:
    """Instructions adding ``value`` to the current cell.

    The ``+5/+6/-5/-6`` cell ops add at most 6 per instruction, so the
    shortest run is mostly ``6`` (one per unit) with a small tail: the old
    ``62`` pair encoding cost ``2 * value`` characters, this is ~``value / 6``.
    """
    q, r = divmod(value, 6)
    if r == 5:
        return "6" * q + "5"  # one +5 beats five +1 pairs
    return "6" * q + "62" * r


def six_five_arithmetic(truth_table: str, n: int) -> str:
    """Build a 6-5 program computing ``truth_table`` arithmetically.

    This is the fallback generator for ``n > 5``, where the decision tree's
    35 branch labels run out.  The inputs are packed into one cell ``x`` and
    the truth table into one cell ``T = sum table[i] * 2**i``, then
    ``f(x) = (T >> x) & 1`` is computed by halving ``T`` ``x`` times and
    reading the final parity.  The halving needs only equality tests: a
    parity pass (a copy loop that toggles a flag once per unit) selects an
    even loop (``while r2 != 0``) or an odd loop (``while r2 != 1``), both
    doing ``r2 -= 2; T += 1`` so the quotient is written back into ``T``.

    ``x`` is built by a loop (read, double into a scratch cell, add the bit,
    copy back), not unrolled per bit, so the marker count is constant in
    ``n`` and the generator is not label-capped.  The table, however, must
    be a single integer ``T``: 6-5 has no way to index an array by a
    computed offset (a loop's ``70`` check reads a fixed-position cell, so
    the pointer can never net-advance through the tape), so ``T`` is the
    only representation the halving arithmetic can address.  Setting an
    integer constant costs ``O(value)`` instructions with the ``+5/+6/-5/-6``
    cell ops, so the setup is about ``value / 6`` characters (via
    :func:`_six_five_const`): ``T`` ranges up to ``2**(2**n)``, and a dense
    table (whose bits at high indices are set) would need an unbuildable
    program.  The generator therefore refuses a setup longer than about
    2 MB (raised from the old ``T <= 2**20``, since the compact encoding is
    ~12x shorter) rather than try to materialize an exabyte string.

    Tables whose *complement* is cheap are supported too: if
    ``T' = (2**(2**n) - 1) - T`` is smaller than ``T``, the complement
    table is evaluated and the output is inverted, so "mostly-ones" tables
    (e.g. NAND-n) no longer need rejection.  What remains excluded is the
    region where both ``T`` and ``T'`` are large (``AND-n`` and friends),
    which no table-as-integer encoding can represent compactly.  The
    remaining practical limit is the runtime, which scales as ``O(x * T)``
    with ``x`` up to ``2**n``.
    """
    value = int(truth_table[::-1], 2)  # bit i of value is table[i] (combo i)
    invert = (2 ** (2**n) - 1 - value) < value
    if invert:
        value = 2 ** (2**n) - 1 - value
    q, r = divmod(value, 6)
    if q + (1 if r == 5 else 2 * r) > 2**21:  # ~2 MB of setup is impractical
        raise ValueError(
            "the 6-5 arithmetic fallback needs the table value T (or its "
            f"complement) small enough for a ~2 MB setup, got T == "
            f"{int(truth_table[::-1], 2)} at n == {n}",
        )
    setup = _six_five_const(value)
    a = _SixFiveAsm()
    a.raw(_six_five_nav(0, 1) + setup)  # T at cell 1
    a.raw(_six_five_nav(1, 7) + _six_five_const(n))  # N = n (bits left) at cell 7

    # read loop (control cell 7): fold each bit into x = 2x + (b - 8)
    a.j("R_END").m("R_START")
    a.raw(_six_five_nav(7, 6) + "B" + "2" * 8)  # read at cell 6 -> 8/9
    a.raw(_six_five_nav(6, 0))
    a.j("D_END").m("D_START")  # double x into x2 (cell 8)
    a.raw("95" + _six_five_nav(0, 8) + "6262" + _six_five_nav(8, 0))
    a.m("D_END").raw("70").j("D_START")
    a.raw(_six_five_nav(0, 6))
    a.raw("79").j("SKIP_ADD")  # b == 9: add 1 to x2
    a.raw(_six_five_nav(6, 8) + "62").j("ADD_DONE")
    a.m("SKIP_ADD").raw(_six_five_nav(6, 8)).m("ADD_DONE")
    a.j("B_END").m("B_START")  # copy x2 back into x
    a.raw("95" + _six_five_nav(8, 0) + "62" + _six_five_nav(0, 8))
    a.m("B_END").raw("70").j("B_START")
    a.raw(_six_five_nav(8, 7) + "95")  # N -= 1
    a.m("R_END").raw("70").j("R_START")
    a.raw(_six_five_nav(7, 0))

    def reset(name: str) -> None:
        # r2 and p hold only 0/1 here, so "71 8name 95 4" zeroes them
        a.raw("71").j(name).raw("95").m(name)

    # outer loop: while x != 0: halve T; x -= 1
    a.j("O_END").m("O_START")
    a.raw(_six_five_nav(0, 1))
    a.raw(_six_five_nav(1, 4))
    reset("RS_R2")
    a.raw(_six_five_nav(4, 5))
    reset("RS_P")
    a.raw(_six_five_nav(5, 1))
    # parity pass: copy T -> r2 while toggling p
    a.j("C_END").m("C_START")
    a.raw("95" + _six_five_nav(1, 4) + "62" + _six_five_nav(4, 5))
    a.raw("70").j("P_TO1")
    a.raw("62").j("P_DONE").m("P_TO1").raw("95").m("P_DONE")
    a.raw(_six_five_nav(5, 1))
    a.m("C_END").raw("70").j("C_START")
    # branch on the parity: even halves to 0, odd to 1
    a.raw(_six_five_nav(1, 5)).raw("70").j("ODD")
    a.raw(_six_five_nav(5, 4)).j("E_END").m("E_START")
    a.raw("9595" + _six_five_nav(4, 1) + "62" + _six_five_nav(1, 4))
    a.m("E_END").raw("70").j("E_START")
    a.j("E_DONE")
    a.m("ODD").raw(_six_five_nav(5, 4)).j("O_END2").m("O_START2")
    a.raw("9595" + _six_five_nav(4, 1) + "62" + _six_five_nav(1, 4))
    a.m("O_END2").raw("71").j("O_START2")
    a.m("E_DONE").raw(_six_five_nav(4, 0))
    a.raw("95")  # x -= 1
    a.m("O_END").raw("70").j("O_START")

    # final parity pass and output 48 + p
    a.raw(_six_five_nav(0, 1))
    a.raw(_six_five_nav(1, 5))
    reset("RS_P2")
    a.raw(_six_five_nav(5, 1))
    a.j("F_END").m("F_START")
    a.raw("95" + _six_five_nav(1, 5))
    a.raw("70").j("P2_TO1")
    a.raw("62").j("P2_DONE").m("P2_TO1").raw("95").m("P2_DONE")
    a.raw(_six_five_nav(5, 1))
    a.m("F_END").raw("70").j("F_START")
    if invert:
        # complement table: output 49 - p, so p == 0 prints '1' and p == 1 prints '0'
        a.raw(_six_five_nav(1, 5))
        a.raw("70").j("OUT_48")
        a.raw(_six_five_nav(5, 2) + "62" * 49 + "A0")
        a.m("OUT_48").raw(_six_five_nav(5, 2) + "62" * 48 + "A0")
    else:
        a.raw(_six_five_nav(1, 5) + "62" * 48 + "A0")
    return a.build()


def _bf_minterm(truth_table: str, n: int) -> str:
    """Build a brainfuck program evaluating ``truth_table`` via its minterms.

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


def bf(truth_table: str, n: int) -> str:
    """Build a brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Two generators exist with complementary strengths, and ``bf`` returns
    the shorter of the two for the given table:

    - ``_bf_minterm``: a branch-free sum of minterms (each input read and
      normalized to 0/1, the result ``48 + sum_k tt[k] * M_k``).  Best for
      sparse tables (few one-rows) — an all-zeros table is ~450 chars even
      at n == 8.
    - :func:`bf_tree`: a decision tree sharing the bit tests.  Best for
      dense tables — XOR-n is ~1000x smaller than the minterm at n == 8.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return min((_bf_minterm(truth_table, n), bf_tree(truth_table, n)), key=len)


def three_d_bf(truth_table: str, n: int) -> str:
    """Build a 3D Brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    3D Brainfuck's ``>``/``<`` set the generation pointer's heading (a no-op
    in this interpreter), so the array is walked along one axis with
    ``e``/``w`` instead; the brainfuck minterm and decision-tree strategies
    otherwise translate directly, and :func:`bf` picks the shorter of the
    two.
    """
    return bf(truth_table, n).translate(str.maketrans("><", "ew"))


# The interpreter's two substitution cycles, in the order the reference scans
# them: Painfuck source is pre-shifted here so the trans table recovers the
# intended commands.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck(truth_table: str, n: int) -> str:
    """Build a Painfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Painfuck is brainfuck-compatible: the commands ``a``/``b`` are while-
    nonzero loops, ``j`` reads a byte and ``u`` prints one.  The brainfuck
    minterm and decision-tree strategies translate directly, mapping BF's
    ``>``/``<`` (each one cell) to ``rl`` (+1) / ``l`` (-1), ``+``/``-`` to
    ``ps`` (+1) / ``s`` (-1), and ``[``/``]``/``,``/``.`` to ``a``/``b``/
    ``j``/``u``.  The interpreter then rewrites the source through two
    substitution cycles, so each emitted command is pre-shifted ``k`` steps
    back along its cycle (where ``k`` counts the commands so far) to undo it.
    """
    code = (
        bf(truth_table, n)
        .replace(">", "rl")
        .replace("<", "l")
        .replace("+", "ps")
        .replace("-", "s")
        .replace("[", "a")
        .replace("]", "b")
        .replace(",", "j")
        .replace(".", "u")
    )
    out: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            p = cycle.find(char)
            if p != -1:
                out.append(cycle[(p - k) % len(cycle)])
                k += 1
                break
        else:
            raise ValueError(f"Painfuck command {char!r} is not in a cycle")
    return "".join(out)


def bf_tree(truth_table: str, n: int) -> str:
    """Build a decision-tree brainfuck program for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Each input is read and normalized to 0/1 into cell ``2i``, its
    complement ``1 - b`` into cell ``2i + 1`` (via two temp cells), and a
    node tests ``[b]`` for the one-side and ``[1 - b]`` for the zero-side:
    the complement guards naturally exclude the sibling, so only the
    matching leaf fires.  Each branch clears its guard cell before its
    ``]``, so the loop exits after one pass, and a fired leaf clears the
    result cell, so every ``]`` on the way out sees zero.  The tree is
    O(2**n) characters (sharing the bit tests), versus the branch-free
    minterm evaluator's O(n * 2**n); for XOR-n it measures 1.4K..20K
    characters at n = 2..8 against the minterm's 1.4K..33M.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            cells.append(">")
            pos += 1
        while pos > target:
            cells.append("<")
            pos -= 1

    # read bits b_i at cell 2i, leaving the complements (cells 1, 3, ...) zero
    for i in range(n):
        cells.append(",")
        cells.extend("-" * 48)
        if i < n - 1:
            cells.append(">")
            cells.append(">")
            pos += 2

    # complements nb_i = 1 - b_i at cell 2i+1 (t1, t2 at 2n, 2n+1)
    for i in range(n):
        move(2 * n)
        cells.append("[-]")
        move(2 * n + 1)
        cells.append("[-]")
        move(2 * i)
        cells.append("[")
        move(2 * n)
        cells.append("+")
        move(2 * n + 1)
        cells.append("+")
        move(2 * i)
        cells.append("-")
        cells.append("]")  # b -> t1, t2
        move(2 * i + 1)
        cells.append("+")  # nb = 1
        move(2 * n + 1)
        cells.append("[")
        move(2 * i + 1)
        cells.append("-")
        move(2 * n + 1)
        cells.append("-")
        cells.append("]")  # nb -= t2
        move(2 * n)
        cells.append("[")
        move(2 * i)
        cells.append("+")
        move(2 * n)
        cells.append("-")
        cells.append("]")  # restore b from t1

    # decision tree: node i entered at cell 2i, exits at cell 2i+1
    result = 2 * n + 2

    def leaf(value: str) -> None:
        cells.extend("+" * (48 + int(value)))
        cells.append(".")
        cells.append("[-]")  # clear the result so every ] on the way out sees zero

    def node(i: int, combo: int) -> None:
        bit = 2 * i
        nxt = result if i == n - 1 else bit + 2
        move(bit)
        cells.append("[")  # one-side: if b_i
        move(nxt)
        if i == n - 1:
            leaf(truth_table[combo | (1 << (n - 1 - i))])
        else:
            node(i + 1, combo | (1 << (n - 1 - i)))
        move(bit)
        cells.append("[-]")  # clear b_i so this ] exits
        cells.append("]")
        move(bit + 1)
        cells.append("[")  # zero-side: if 1 - b_i
        move(nxt)
        if i == n - 1:
            leaf(truth_table[combo])
        else:
            node(i + 1, combo)
        move(bit + 1)
        cells.append("[-]")  # clear the complement so this ] exits
        cells.append("]")

    node(0, 0)
    return "".join(cells)


class _Dimensional:
    """Emits Dimensional code on dimension 0 with a fixed cell layout.

    A bare ``>``/``<`` takes its dimension from the current cell's value
    (usually nonzero mid-program), so every move is pinned with an explicit
    ``>0``/``<0``.

    Cells: 0 = result, 1..n = inputs (0/1), n+1..2n = NOT of each input,
    2n+1 = survivor, then four shared scratch cells (a, b, c, d).
    """

    def __init__(self, n: int) -> None:
        self.n = n
        self.code: list[str] = []
        self.ptr = 0
        self.inputs = list(range(1, n + 1))
        self.nots = list(range(n + 1, 2 * n + 1))
        self.survivor = 2 * n + 1
        self.a, self.b, self.c, self.d = (2 * n + 2, 2 * n + 3, 2 * n + 4, 2 * n + 5)

    def move(self, dst: int) -> None:
        delta = dst - self.ptr
        self.code.append(">0" * delta if delta >= 0 else "<0" * -delta)
        self.ptr = dst

    def zero(self, cell: int) -> None:
        self.move(cell)
        self.code.append("[-]")

    def copy(self, src: int, dst: int) -> None:
        """Copy ``src`` to ``dst`` preserving ``src`` (scratch a, b, c)."""
        self.zero(self.a)
        self.zero(self.b)
        self.zero(self.c)
        self.move(src)
        self.code.append("[")
        self.move(self.a)
        self.code.append("+")
        self.move(self.b)
        self.code.append("+")
        self.move(src)
        self.code.append("-]")
        self.move(self.a)
        self.code.append("[")
        self.move(src)
        self.code.append("+")
        self.move(self.a)
        self.code.append("-]")
        self.move(self.b)
        self.code.append("[")
        self.move(dst)
        self.code.append("+")
        self.move(self.b)
        self.code.append("-]")
        self.move(dst)

    def kill_survivor(self) -> None:
        """Survivor *= (scratch c == 0); consumes c."""
        self.move(self.c)
        self.code.append("[")
        self.move(self.survivor)
        self.code.append("[-]")
        self.move(self.c)
        self.code.append("-]")


def dimensional(truth_table: str, n: int) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Dimensional is brainfuck on a multidimensional tape and has no halt
    command, so a decision tree cannot rely on halting at the leaf.  Two
    generators exist with complementary strengths, and ``dimensional``
    returns the shorter of the two for the given table:

    - the survivor evaluator: each input is read and normalized to 0/1, the
      NOT of each bit is precomputed, and every row whose table entry is one
      is tested by a survivor cell (``S``), summed into the result cell, and
      printed as ``48 + sum`` (or ``49 - sum`` when the table's zeros are
      cheaper).  Best for sparse tables — an AND-8 is ~4.4K characters.
    - :func:`dimensional_tree`: a decision tree sharing the bit tests.
      Best for dense tables — XOR-8 is ~8x smaller than the survivor.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return min(
        (_dimensional_survivor(truth_table, n), dimensional_tree(truth_table, n)),
        key=len,
    )


def _dimensional_survivor(truth_table: str, n: int) -> str:
    """Build the survivor-cell evaluator for the given truth table."""
    use_complement = truth_table.count("1") > 2**n // 2
    table = (
        truth_table
        if not use_complement
        else "".join("1" if c == "0" else "0" for c in truth_table)
    )

    cell = _Dimensional(n)
    for i in cell.inputs:
        cell.move(i)
        cell.code.append(",")
        cell.code.append("-" * 48)
    for i in range(n):
        cell.copy(cell.inputs[i], cell.c)
        cell.zero(cell.d)
        cell.code.append("+")
        cell.move(cell.c)
        cell.code.append("[")
        cell.move(cell.d)
        cell.code.append("-")
        cell.move(cell.c)
        cell.code.append("-]")
        cell.copy(cell.d, cell.nots[i])
    cell.zero(0)
    for row, ch in enumerate(table):
        if ch == "0":
            continue
        cell.move(cell.survivor)
        cell.code.append("[-]+")
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            cell.copy(cell.nots[i] if bit else cell.inputs[i], cell.c)
            cell.kill_survivor()
        cell.move(cell.survivor)
        cell.code.append("[")
        cell.move(0)
        cell.code.append("+")
        cell.move(cell.survivor)
        cell.code.append("-]")
    cell.move(0)
    if use_complement:
        cell.zero(cell.a)
        cell.code.append("+")
        cell.move(0)
        cell.code.append("[")
        cell.move(cell.a)
        cell.code.append("-")
        cell.move(0)
        cell.code.append("-]")
        cell.zero(0)
        cell.code.append("+" * 48)
        cell.move(cell.a)
        cell.code.append("[")
        cell.move(0)
        cell.code.append("+")
        cell.move(cell.a)
        cell.code.append("-]")
        cell.move(0)
    else:
        cell.code.append("+" * 48)
    cell.code.append(".")
    return "".join(cell.code)


def dimensional_tree(truth_table: str, n: int) -> str:
    """Build a decision-tree Dimensional program for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    The same construction as :func:`bf_tree`, ported to Dimensional's tape:
    bit ``i`` lives at cell ``2i``, its complement at ``2i + 1``, a node
    tests ``[bit]`` for the one-side and ``[1 - bit]`` for the zero-side
    (complements naturally exclude the sibling), each branch clears its
    guard cell before its ``]``, and a fired leaf clears the result cell so
    every ``]`` on the way out sees zero.  Every move is pinned ``>0``/``<0``
    (a bare move would take the cell value as the dimension).  The tree is
    O(2**n) characters and wins on dense tables; the survivor evaluator
    (``_dimensional_survivor``) wins on sparse ones.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(">0" * delta if delta >= 0 else "<0" * -delta)
        pos = target

    for i in range(n):
        cells.append(",")
        cells.extend("-" * 48)
        if i < n - 1:
            move(pos + 2)

    # complements nb_i = 1 - b_i at cell 2i+1 (t1, t2 at 2n, 2n+1)
    for i in range(n):
        move(2 * n)
        cells.append("[-]")
        move(2 * n + 1)
        cells.append("[-]")
        move(2 * i)
        cells.append("[")
        move(2 * n)
        cells.append("+")
        move(2 * n + 1)
        cells.append("+")
        move(2 * i)
        cells.append("-")
        cells.append("]")  # b -> t1, t2
        move(2 * i + 1)
        cells.append("+")  # nb = 1
        move(2 * n + 1)
        cells.append("[")
        move(2 * i + 1)
        cells.append("-")
        move(2 * n + 1)
        cells.append("-")
        cells.append("]")  # nb -= t2
        move(2 * n)
        cells.append("[")
        move(2 * i)
        cells.append("+")
        move(2 * n)
        cells.append("-")
        cells.append("]")  # restore b from t1

    # decision tree: node i entered at cell 2i, exits at cell 2i+1
    result = 2 * n + 2

    def leaf(value: str) -> None:
        cells.extend("+" * (48 + int(value)))
        cells.append(".")
        cells.append("[-]")  # clear the result so every ] on the way out sees zero

    def node(i: int, combo: int) -> None:
        bit = 2 * i
        nxt = result if i == n - 1 else bit + 2
        move(bit)
        cells.append("[")  # one-side: if b_i
        move(nxt)
        if i == n - 1:
            leaf(truth_table[combo | (1 << (n - 1 - i))])
        else:
            node(i + 1, combo | (1 << (n - 1 - i)))
        move(bit)
        cells.append("[-]")  # clear b_i so this ] exits
        cells.append("]")
        move(bit + 1)
        cells.append("[")  # zero-side: if 1 - b_i
        move(nxt)
        if i == n - 1:
            leaf(truth_table[combo])
        else:
            node(i + 1, combo)
        move(bit + 1)
        cells.append("[-]")  # clear the complement so this ] exits
        cells.append("]")

    node(0, 0)
    return "".join(cells)


def basicfuck(truth_table: str, n: int) -> str:
    """Build a Basicfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Basicfuck's named variables behave like BF cells with an explicit
    arithmetic, so the program is a decision tree: each input is read with
    ``read -> a_i ;`` and normalized to 0/1 with ``a_i -= 48 ;``, then every
    internal node emits ``if (a_k) { ... }`` next to ``if !(a_k) { ... }``
    (the wiki spells negation ``!(<X>)``, with the bang before the parens).  A
    failed ``if`` falls through to its neighbour, so exactly one subtree runs
    per input combination.  Each leaf adds ``48 + entry`` to the ``out``
    variable (which starts at 0 and is touched by exactly one leaf) and
    prints it with ``write <- out ;``.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

    lines = ["#basicfuck t=unbounded r=0~255 o=wrap"]
    lines.append("#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out")
    for i in range(1, n + 1):
        lines.append(f"read -> a{i} ;")
        lines.append(f"a{i} -= 48 ;")

    def build(rows: list[int], k: int) -> str:
        if len(rows) == 1:
            value = int(truth_table[rows[0]])
            return f"out += {48 + value} ;\nwrite <- out ;\n"
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        var = f"a{k}"
        return (
            f"if ({var}) {{\n"
            + build(g1, k + 1)
            + "}\n"
            + f"if !({var}) {{\n"
            + build(g0, k + 1)
            + "}\n"
        )

    lines.append(build(list(range(2**n)), 1))
    return "\n".join(lines)


def sbleq(truth_table: str, n: int) -> str:
    """Build an S*bleq program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    S*bleq's instruction is ``a b c``: ``mem[a] -= mem[b]``, and when the
    result is ``<= 0`` the pointer jumps to the address stored at ``c``.
    The ``<= 0`` branch traps on zero, so a bit normalized to 0 would
    branch the wrong way; the generator instead normalizes each input to
    ``49 - byte`` (``'0'`` -> 1, ``'1'`` -> 0), which lands the two cases on
    opposite sides of zero.  Every branch level is then just two
    instructions:

        v -2 NXT     # v = -byte (always jumps, so NXT points at the next)
        v NEG49 ONE  # v = 49 - byte; a one jumps to ONE, a zero falls through

    where ``NEG49`` is a constant cell holding -49 and ``v`` is that level's
    value cell.  Leaves print ``-3 D 0`` (``D`` a constant 48/49 cell) and
    halt with ``0 0 HALT`` (``HALT`` holds -1, a negative jump target).
    Whole subtrees whose table entries are constant collapse to a leaf.

    S*bleq's operands are addresses, so a cell holding a transient 0/1 is
    misread as a jump target if any ``c`` references it.  The generator
    therefore keeps *constant* cells (``NEG49``, ``D48``, ``D49``, ``HALT``,
    and each node's ``NXT``/``ONE``, the only cells ever used as jump
    targets) strictly separate from *value* cells (each node's ``v``, written
    by the read and never used as a ``c`` operand).  Each node of the tree
    allocates its own ``v``/``NXT``/``ONE`` triple, and the ``NXT``/``ONE``
    values (the addresses of the node's normalize instruction and one-subtree)
    are back-patched after the code layout is known.  The normalize subtracts
    the constant in the ``b`` operand, which the ``store="b"``/``"ab"``
    variants would overwrite, so this generator targets base S*bleq
    (``store="a"``).
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

    instructions: list[tuple[int, int, int]] = []
    nodes: list[tuple[int, int, int]] = []  # (v offset, normalize addr, one addr)
    counter = 0

    def build(level: int, rows: list[int]) -> None:
        nonlocal counter
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            instructions.append((-3, 1 + int(results.pop()), 0))
            instructions.append((0, 0, 3))
            return
        nid = counter
        counter += 1
        instructions.append((4 + nid, -2, 0))  # read; c patched to this node's NXT
        normalize_addr = 3 * len(instructions)
        instructions.append((4 + nid, 0, 0))  # normalize; b and c patched below
        zero = [r for r in rows if not ((r >> (n - 1 - level)) & 1)]
        one = [r for r in rows if (r >> (n - 1 - level)) & 1]
        build(level + 1, zero)
        one_addr = 3 * len(instructions)
        build(level + 1, one)
        nodes.append((nid, normalize_addr, one_addr))

    build(0, list(range(2**n)))

    m = len(nodes)
    for nid, normalize_addr, _one_addr in nodes:
        instructions[normalize_addr // 3 - 1] = (4 + nid, -2, 4 + m + nid)
        instructions[normalize_addr // 3] = (4 + nid, 0, 4 + 2 * m + nid)

    data_base = 3 * len(instructions)
    cells: list[int] = []
    for a, b, c in instructions:
        if a == -3:  # output the constant at b
            cells += [-3, data_base + b, 0]
        elif a == 0 and b == 0:  # halt via the HALT constant at c
            cells += [0, 0, data_base + c]
        else:  # read/normalize: make every data-cell operand absolute
            cells += [data_base + a, -2 if b == -2 else data_base + b, data_base + c]
    data = [-49, 48, 49, -1] + [0] * (3 * m)
    for nid, normalize_addr, one_addr in nodes:
        data[4 + m + nid] = normalize_addr
        data[4 + 2 * m + nid] = one_addr
    cells += data
    return " ".join(map(str, cells))
