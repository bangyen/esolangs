"""Boolean-function generators for tape-based languages."""

from collections.abc import Sequence
from typing import cast

from esolangs.tools.booleans.helpers import _maybe_complement, _validate_truth_table
from esolangs.tools.transpilers import _six_five_label


def brainif(truth_table: str, n: int) -> str:
    """Build a BrainIf program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    BrainIf reads each input into a cell with ``if 0 input``, then a
    recursive decision tree checks each cell with ``if 48/49 goto`` (the
    groups' checks sit adjacent so a failed check falls through to the next
    candidate).  Every leaf lands on a fresh cell (the last marker moved the
    pointer past the inputs), so it jumps to one of two shared output
    routines that build 48 or 49 in place and print it, instead of each leaf
    incrementing a fresh cell itself.
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
            return [("cmd", f"if 0 goto OUT{r}")]
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
    # two shared output routines: every leaf's pointer is on a fresh cell
    for r in (0, 1):
        entries.append(("out", r))
        entries.append(("cmd", "if 48 move right"))
        entries.append(("cmd", "if 49 move right"))
        entries += [("cmd", f"if {v} increment") for v in range(48 + r)]
        entries.append(("cmd", f"if {48 + r} output"))
        entries.append(("cmd", f"if {48 + r} goto end"))
    entries.append(("end",))

    # resolve labels from the actual line sequence (the "out" markers emit
    # no line, so the marker's target is the next line that does)
    labels: dict[int, int] = {}
    out_labels: dict[int, int] = {}
    line_no = 0
    pending: int | None = None
    for entry in entries:
        if entry[0] == "out":
            pending = cast(int, entry[1])
            continue
        line_no += 1
        if pending is not None:
            out_labels[pending] = line_no
            pending = None
        if entry[0] == "mr":
            labels[cast(int, entry[2])] = line_no
    end_line = line_no + 1

    lines: list[str] = []
    for entry in entries:
        if entry[0] == "cmd":
            s = cast(str, entry[1])
            if "goto OUT" in s:
                r = int(s.split("OUT")[1])
                s = f"if 0 goto {out_labels[r]}"
            elif "goto end" in s:
                s = s.replace("goto end", f"goto {end_line}")
            lines.append(s)
        elif entry[0] == "if":
            lines.append(f"if {entry[1]} goto {labels[cast(int, entry[2])]}")
        elif entry[0] == "mr":
            lines.append(f"if {entry[1]} move right")
        elif entry[0] == "out":
            continue
        else:
            lines.append("")
    return "\n".join(lines)


def circlefuck(truth_table: str, n: int) -> str:
    """Build a Circlefuck program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Circlefuck reads each input with ``,`` and normalizes it to 0/1 with 48
    ``-``s, then a decision tree branches on the cells from the last input
    down. Each leaf starts from a cleared cell, so it sets the result with
    ``+``s, prints it, and halts with ``@`` -- halting at the leaf means the
    tree never needs to skip the sibling branch.  A boolean table is just
    the byte-valued generator with ``48 + bit`` outputs.
    """
    return circlefuck_byte([48 + int(bit) for bit in truth_table], n)


def circlefuck_byte(truth_table: Sequence[int], n: int) -> str:
    """Build a Circlefuck program computing a byte-valued function.

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
    table, use_complement = _maybe_complement(truth_table, n)

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


def brainfuck(truth_table: str, n: int) -> str:
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
    _validate_truth_table(truth_table, n)
    return min((_bf_minterm(truth_table, n), bf_tree(truth_table, n)), key=len)


def three_d_brainfuck(truth_table: str, n: int) -> str:
    """Build a 3D Brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    3D Brainfuck's ``>``/``<`` set the generation pointer's heading (a no-op
    in this interpreter), so the array is walked along one axis with
    ``e``/``w`` instead; the brainfuck minterm and decision-tree strategies
    otherwise translate directly, and :func:`bf` picks the shorter of the
    two.
    """
    return brainfuck(truth_table, n).translate(str.maketrans("><", "ew"))


# The interpreter's two substitution cycles, in the order the cross-check
# scans them: Painfuck source is pre-shifted here so the trans table recovers
# the intended commands.
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
        brainfuck(truth_table, n)
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
            # every command the brainfuck generator emits maps to a command
            # in _CYCLES, so this branch is unreachable by construction
            raise ValueError(
                f"Painfuck command {char!r} is not in a cycle"
            )  # pragma: no cover
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
    _validate_truth_table(truth_table, n)

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
    _validate_truth_table(truth_table, n)
    return min(
        (_dimensional_survivor(truth_table, n), dimensional_tree(truth_table, n)),
        key=len,
    )


def _dimensional_survivor(truth_table: str, n: int) -> str:
    """Build the survivor-cell evaluator for the given truth table."""
    table, use_complement = _maybe_complement(truth_table, n)

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
    _validate_truth_table(truth_table, n)

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
    _validate_truth_table(truth_table, n)

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
    _validate_truth_table(truth_table, n)

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


# Minifuck reachable programs, found by search (see docs/limitations.md): all
# four one-input functions and the eight 0-preserving two-input tables.
_MINIFUCK_N1 = {
    "00": "<[<[<[[<.<[<<<[<[[[",
    "01": "[<.<<<[<<.<[<",
    "10": "<[<[<[[[<[.[<.[[.",
    "11": "<[<<[[[.[[[.[<.[[<.<<",
}
_MINIFUCK_N2 = {
    "0000": "<[<.[<[<[<[<[<[<[<.<<[<[.[<.[",
    "0001": "<[<.[<[<[<[<[<[<[<.<<[<.<",
    "0010": "<[<.[<[<[<[<[<[<[<.[[<<<[<<[<.[<[",
    "0011": "<[<.[<[<[<[<[<[<[<.[<<<[<[.[[<.<",
    "0100": "<[<.[<[<[<[<[<[<[<.<[<[.[[<.<",
    "0101": "<[<.[<[<[<[<[<[<[<..",
    "0110": "<[<.[<[<[<[<[<[<[<.<.[<[[[.[[<<[",
    "0111": "<[<.[<[<[<[<[<[<[<.<[[<.<",
}


def minifuck(truth_table: str, n: int) -> str:
    """Build a Minifuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    The documented reachable set (re-verified in ``docs/limitations.md``) is
    all four one-input functions plus the eight 0-preserving two-input tables
    (``tt[0] == 0``): AND, OR, XOR, both echoes, and const-0 among them.  The
    non-0-preserving two-input tables (XNOR, NAND, NOR, NOT-b0, NOT-b1,
    const-1) are unreachable — the decode suffix pins the pointer orientation
    so a complemented read cannot select them — and n >= 3 has no general
    construction.  The programs below were found by search.
    """
    _validate_truth_table(truth_table, n)
    if n == 1:
        return _MINIFUCK_N1[truth_table]
    if n == 2:
        if truth_table not in _MINIFUCK_N2:
            raise ValueError(
                "Minifuck cannot compute a non-0-preserving two-input table",
            )
        return _MINIFUCK_N2[truth_table]
    raise ValueError("Minifuck has no boolean generator for n >= 3 inputs")


# ROTfuck rotates the whole program after every command, so a brainfuck-style
# decision tree does not survive: the bracket that fires seeks its partner in
# the *rotated* program, at a rotation state that depends on the step count.
# The construction below is the discovered escape, verified against the
# interpreter: each ``[`` body is a *straight-line* ``+-><``-only block (no
# brackets), and the closing ``]`` is a phantom character whose position is
# encoded so that the ``[``-fire seek finds it at the right rotation state.
#
# A block is ``[ body ]`` at positions ``p``..``q`` where ``len(body)``
# satisfies ``len(body) + 1 ≡ 0 (mod 8)``:
#
# - skip path (cell == 0): the ``[`` fires, rotates once, seeks forward for
#   ``]`` at depth 1, and lands at ``q + 1`` with rotation state ``p + 1``;
# - body path (cell != 0): the body runs (straight-line, pointer starts and
#   ends on the tested cell, which stays nonzero), and at ``q`` the phantom
#   shows ``rot^len(body)(']')`` = ``'['`` (since ``len(body) ≡ 7``), which
#   does not fire on the nonzero cell, so it advances to ``q + 1`` with state
#   ``q + 1 ≡ p + 1 (mod 8)``.
#
# Both paths therefore re-converge at ``q + 1`` in the same rotation state,
# so the rest of the program can be encoded position-wise.  A body command at
# relative offset ``j`` must also satisfy ``rot^{-j}(cmd)`` not a bracket, so
# the ``[``-fire seek (at state ``p + 1``) sees no bracket inside the body.
#
# The generator is a branch-free minterm sum over an idempotent-zeroing
# indirection: each input bit ``b_i`` (cell ``i``) and its complement ``c_i``
# (cell ``n + i``, set to 1) guard blocks that count mismatches into cells
# ``mc_k``; one block per minterm then zeroes ``m_k`` (cell
# ``2n + 1 + 2**n + k``) iff ``mc_k != 0``, so ``m_k == 1`` exactly when the
# input is ``k``; and blocks guarded by the ``1``-rows accumulate into the
# result cell, which is printed as ``48 + r``.

# The eight-step rotation cycle: + -> - -> > -> < -> , -> . -> [ -> ] -> +.
_ROTFUCK_CHAIN = "+-><,.[]"


def _rotfuck_rot(char: str, steps: int) -> str:
    """Advance ``char`` ``steps`` steps along the ROTfuck rotation cycle."""
    index = _ROTFUCK_CHAIN.index(char)
    return _ROTFUCK_CHAIN[(index + steps) % 8]


def _rotfuck_allowed(offset: int) -> list[str]:
    """Commands a body may place at relative offset ``offset``.

    At the ``[``-fire seek state ``p + 1``, a body command at relative offset
    ``j`` shows ``rot^{-j}(cmd)``, which must not be a bracket (else the
    seek's depth count changes).  So ``cmd`` must not be ``rot^{j}`` of a
    bracket.
    """
    bad = {_rotfuck_rot("[", offset), _rotfuck_rot("]", offset)}
    return [c for c in "+-><" if c not in bad]


def _rotfuck_neutral(offset: int) -> str:
    """Return a two-char net-neutral pair usable at ``offset``.

    The pair is ``+-``/``-+`` or ``><``/``<>``, both of whose characters are
    allowed at ``offset`` and ``offset + 1``.
    """
    for pair in ("+-", "-+", "><", "<>"):
        if all(c in _rotfuck_allowed(offset + i) for i, c in enumerate(pair)):
            return pair
    raise ValueError(  # pragma: no cover - a neutral pair exists at every offset
        "ROTfuck body padding is impossible at this offset"
    )


def _rotfuck_move(ptr: int, goal: int, offset: int, direction: str) -> str:
    """Emit ``>``/``<`` to move ``ptr`` toward ``goal``.

    The direction command is forbidden at some offsets, so a net-neutral
    padding pair is inserted there to shift past them while every command
    stays at an allowed offset.
    """
    out: list[str] = []
    while ptr < goal if direction == ">" else ptr > goal:
        if direction in _rotfuck_allowed(offset % 8):
            out.append(direction)
            ptr += 1 if direction == ">" else -1
            offset += 1
        else:
            pad = _rotfuck_neutral(offset % 8)
            out.append(pad)
            offset += 2
    return "".join(out)


def _rotfuck_body(guard: int, target: int, op: str) -> str:
    """Build a body that moves the pointer from ``guard`` to ``target``.

    The body applies ``op`` to the target cell and returns to ``guard``.  It
    is straight-line ``+-><`` only, has length ``L`` with
    ``L + 1 ≡ 0 (mod 8)``, and every command sits at an allowed offset.  The
    tested cell (``guard``) stays nonzero, so the phantom ``[`` at the block
    end does not fire on the body path.
    """
    out: list[str] = []
    offset = 0
    ptr = guard
    if target > guard:
        out.append(_rotfuck_move(ptr, target, offset, ">"))
        offset += len(out[-1])
        ptr = target
    else:
        out.append(_rotfuck_move(ptr, target, offset, "<"))
        offset += len(out[-1])
        ptr = target
    if op not in _rotfuck_allowed(offset % 8):
        pad = _rotfuck_neutral(offset % 8)
        out.append(pad)
        offset += 2
        if op not in _rotfuck_allowed(offset % 8):
            # padding always shifts a +/- op off both its forbidden offsets
            raise ValueError(
                "ROTfuck body op lands on a forbidden offset"
            )  # pragma: no cover
    out.append(op)
    offset += 1
    if guard > target:
        out.append(_rotfuck_move(ptr, guard, offset, ">"))
    else:
        out.append(_rotfuck_move(ptr, guard, offset, "<"))
    offset += len(out[-1])
    body = "".join(out)
    need = (8 - (len(body) + 1) % 8) % 8
    while need:
        pad = _rotfuck_neutral(offset % 8)
        body += pad
        offset += 2
        need -= 2
    return body


def rotfuck(truth_table: str, n: int) -> str:
    """Build a ROTfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    ROTfuck rotates the program after every command, which defeats the
    brainfuck decision-tree strategy (a firing bracket seeks its partner in
    the rotated program).  The generator instead lays out one ``[ body ]``
    block per guard, where the body is a straight-line ``+-><`` walk that
    moves the pointer from the tested cell to a target, applies one
    ``+``/``-``, and returns.  The closing ``]`` is a *phantom*: its source
    character is the inverse rotation of ``]`` at the ``[``-fire seek state,
    so the skip path (tested cell == 0) finds it and jumps past the block,
    while the body path (tested cell != 0) sees it as a non-firing ``[``.
    Both paths re-converge after the block in the same rotation state because
    every body length is ``7 (mod 8)``.

    The truth table is evaluated as a minterm sum: the input bits are read
    and normalized into cells ``0..n-1``, their complements into
    ``n..2n-1``, each minterm's mismatch count into ``2n+1..2n+2**n``, and
    each minterm into ``2n+1+2**n..2n+1+2*2**n``.  Per-input a single
    ``-``-guarded block zeroes the matching minterm, ``1``-rows accumulate
    into the result cell, and ``48 + r`` is printed.
    """
    _validate_truth_table(truth_table, n)

    b = list(range(n))
    c = list(range(n, 2 * n))
    r = 2 * n
    mc = list(range(2 * n + 1, 2 * n + 1 + 2**n))
    m = list(range(2 * n + 1 + 2**n, 2 * n + 1 + 2 * 2**n))

    eff: list[str] = []
    phantoms: dict[int, int] = {}

    def emit(cmds: list[str]) -> None:
        eff.extend(cmds)

    # Read the bits (each on its own line), normalize to 0/1, set the
    # complements to 1, set the minterm cells to 1 (mismatch cells start 0).
    for i in range(n):
        emit([","])
        emit(["-"] * 48)
        if i < n - 1:
            emit([">"])
    emit([">"] * (c[0] - (n - 1)))
    for i in range(n):
        emit(["+"])
        if i < n - 1:
            emit([">"])
    emit([">"] * (m[0] - c[-1]))
    for k in range(2**n):
        emit(["+"])
        if k < 2**n - 1:
            emit([">"])

    # Block layout: for each minterm, each input bit guards a mismatch count;
    # a single block then zeroes the minterm iff its count is nonzero; and
    # each 1-row guards an accumulation into the result cell.
    block_specs: list[tuple[int, int, str]] = []
    for i in range(n):
        block_specs.append((b[i], c[i], "-"))  # complement c_i = 1 - b_i
    for k in range(2**n):
        for i in range(n):
            guard = c[i] if ((k >> (n - 1 - i)) & 1) else b[i]
            block_specs.append((guard, mc[k], "+"))  # mismatch count
        block_specs.append((mc[k], m[k], "-"))  # zero minterm on any mismatch
    for k in range(2**n):
        if truth_table[k] == "1":
            block_specs.append((m[k], r, "+"))  # accumulate 1-rows

    ptr = m[-1]
    for guard, target, op in block_specs:
        while ptr < guard:
            emit([">"])
            ptr += 1
        while ptr > guard:
            emit(["<"])
            ptr -= 1
        p = len(eff)
        emit(["["])
        body = _rotfuck_body(guard, target, op)
        emit(list(body))
        emit(["]"])
        phantoms[p + len(body) + 1] = p

    while ptr < r:  # pragma: no cover - the last block's guard sits above r
        emit([">"])
        ptr += 1
    while ptr > r:
        emit(["<"])
        ptr -= 1
    emit(["+"] * 48)
    emit(["."])

    return "".join(
        (
            _rotfuck_rot("]", -(phantoms[i] + 1))
            if i in phantoms
            else _rotfuck_rot(cmd, -i)
        )
        for i, cmd in enumerate(eff)
    )


def jaune(truth_table: str, n: int) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Jaune reads each input bit with ``v`` (a digit character, ``ord-48``) into
    a fresh cell and routes a decision tree with ``?``/``!`` jumps: ``v`` then
    ``N?`` jumps to label ``N`` when the cell is nonzero, else falls through,
    and each leaf builds 48 or 49 in a fresh cell and prints it with ``^``
    before jumping to a shared end label.  A subtree whose table slice is a
    constant collapses to a single leaf.
    """
    _validate_truth_table(truth_table, n)
    label = [1]

    def fresh() -> int:
        label[0] += 1
        return label[0]

    def leaf(value: str, end: int) -> str:
        # move to a fresh cell, build 0 or 1, print, then force nonzero and jump
        body = ">+^" if value == "1" else ">^"
        return body + f"+{end}?"

    def node(level: int, lo: int, hi: int, end: int) -> str:
        if level == n or len(set(truth_table[lo:hi])) == 1:
            return leaf(truth_table[lo], end)
        then_lbl = fresh()
        mid = (lo + hi) // 2
        then = node(level + 1, mid, hi, end)
        else_ = node(level + 1, lo, mid, end)
        return f"v{then_lbl}?{else_}{then_lbl}:{then}"

    end = fresh()
    return node(0, 0, 2**n, end) + f"{end}:."


def jaune_multiply() -> str:
    """Build a Jaune program reading two decimal numbers and printing their product.

    The program reads decimal digits (most-significant first, one per input
    line) into the first operand until a ``*`` line, then digits into the
    second operand until a ``#`` line, and prints the product as a decimal
    number with no leading zeros.  The single construction handles *any*
    number of digits, so the generator takes no ``n`` parameter: multiplying
    is one function ``a * b``, and the operand lengths are a property of the
    input, not of the function (unlike a boolean truth table, where ``n``
    selects a different function space).

    Jaune is the language the multiply capability needs: its cells do not
    wrap (the author's JauneJS stores each cell as a JavaScript number with
    plain ``+=``/``-=``, and this interpreter uses Python ``int``), so each
    operand fits in a single cell with no digit-per-cell carry, and ``^``
    prints the current cell as a decimal number directly.  Each read loop
    runs on a dedicated always-one
    cell: the ``?``/``!`` jumps are conditional, so a cell permanently set to
    1 gives the loop-back jump an unconditional trigger (the sentinel check
    is the only exit).  A digit is folded into the operand with ``v+`` (read
    a digit and add it), ``#`` (copy the current cell to hold) and a run of
    nine ``&`` (add the hold cell), which multiplies the accumulated value by
    10; a sentinel is detected by adding its offset from a digit (``*`` is
    42, so ``6+`` zeroes it) and jumping on zero.  The product is then a
    repeated-addition loop over the second operand.  Cells 0/1/2/3/4 hold
    the first operand, the digit scratch, the second operand, the result,
    and the always-one trigger.
    """
    out: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            out.append(">")
            pos += 1
        while pos > target:
            out.append("<")
            pos -= 1

    def cmd(s: str) -> None:
        out.append(s)

    def fold(operand: int) -> None:
        # accumulate the digit in the scratch cell into the operand cell
        move(operand)
        cmd("#")
        cmd("&" * 9)
        move(1)
        cmd("#")
        move(operand)
        cmd("&")
        move(4)
        cmd(f"{4 if operand == 2 else 1}?")

    move(4)
    cmd("1+")  # cell 4 = 1: the unconditional loop-back trigger
    # read the first operand until '*': label 1 at cell 4
    cmd("1:")
    move(1)
    cmd("v")
    cmd("6+")  # '*' is 42, so ord-48 == -6; +6 zeroes it
    cmd("2!")  # a zero (the sentinel) exits to label 2
    cmd("6-")
    move(0)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(0)
    cmd("&")
    move(4)
    cmd("1?")  # always jump back to label 1
    cmd("2:")  # first operand done; the '*' was read at cell 1
    pos = 1
    move(4)
    # read the second operand until '#': label 4 at cell 4
    cmd("4:")
    move(1)
    cmd("v")
    cmd("13+")  # '#' is 35, so ord-48 == -13; +13 zeroes it
    cmd("3!")  # a zero (the sentinel) exits to label 3
    cmd("13-")
    move(2)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(2)
    cmd("&")
    move(4)
    cmd("4?")  # always jump back to label 4
    cmd("3:")  # second operand done; the '#' was read at cell 1
    pos = 1
    move(2)
    # multiply: while cell 2 != 0: cell 3 += cell 0; cell 2 -= 1
    cmd("5:")
    cmd("6!")
    move(0)
    cmd("#")
    move(3)
    cmd("&")
    move(2)
    cmd("1-")
    cmd("5?")
    cmd("6:")
    pos = 2
    move(3)
    cmd("^")
    cmd(".")
    return "".join(out)
