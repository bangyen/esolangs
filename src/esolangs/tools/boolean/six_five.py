"""Boolean-function generators for 6:5.

Two constructions share the language's assembler: :func:`six_five` routes a
decision tree, while :func:`six_five_arithmetic` evaluates the table as
arithmetic on the packed input instead, which is shorter for dense tables.
Both emit through :class:`_SixFiveAsm`, which tracks the accumulator and
cell pointer so the helpers can navigate by cell index.
"""

from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
)
from esolangs.tools.transpilers import _six_five_label

__all__ = ["six_five", "six_five_arithmetic"]


def six_five(truth_table: str) -> str:
    """Build a 6-5 program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Each input is read with ``B`` and normalized to 8/9 (subtracting 40 with
    eight ``2``s).  ``78`` branches: the ``7`` compares the cell to 8, so a
    zero bit skips the following ``8n`` jump and falls into the left subtree,
    while a one bit takes the jump to the n-th ``4`` marker holding the right
    subtree.  A leaf adds ``48 + value - base`` (8 for a left path, 9 for a
    right path) with a run of sixes plus ``62`` pairs (each ``6`` then ``2``
    nets ``+6 - 5 = +1``), prints with ``A``, and halts with ``0``.

    A subtree whose rows all hold the same value folds to a single leaf
    rather than the branches that would all reach it -- a constant table is
    17 characters against 226 at n == 3, and 19 against 946 at n == 5.  The
    fold still spends the reads it skipped, so a caller feeding several
    programs from one input stream stays in sync.  Those reads are why a
    folded leaf cannot use the 8/9 base: ``B`` overwrites the cell, so after
    the skipped reads it holds the last input character (48 or 49, differing
    per input) and no fixed run of cell ops maps both to one value.  The
    leaf steps to cell 1 instead -- untouched, since every tree path works in
    cell 0 and every leaf halts -- and builds the digit from zero there.

    The branch labels are the digits 0..9 then A..Z (values 1..35, consumed
    as ``8n`` operands), one per internal node, so the decision tree caps at
    n == 5 (31 internal nodes).  For larger ``n`` the generator falls back
    to :func:`six_five_arithmetic`, which packs the inputs and the table
    into single cells and decodes the table entry arithmetically with a
    constant number of loop constructs.
    """
    n = _validate_truth_table(truth_table)
    if 2**n - 1 <= 35:
        marker = 0

        def build(rows: list[int], bit: int, base: int) -> str:
            nonlocal marker
            if len(rows) == 1:
                delta = _ASCII_ZERO + int(truth_table[rows[0]]) - base
                q, r = divmod(delta, 6)
                return "6" * q + "62" * r + "A0"
            values = {truth_table[r] for r in rows}
            if len(values) == 1:
                # A constant subtree emits its value directly instead of the
                # branches that would all reach it.  The skipped reads still
                # happen (a caller feeding several programs from one stream
                # would otherwise desync), but their ``B``s leave the cell
                # holding the last input character -- 48 or 49, which differs
                # per input -- and every cell op adds an unconditional
                # constant, so no fixed suffix could bring both to one value.
                # The leaf therefore steps to cell 1, which no tree path ever
                # writes, and builds the digit from zero.
                reads = "B" * (n - bit + 1)
                value = _ASCII_ZERO + int(values.pop())
                return reads + "13" + _six_five_const(value) + "A0"
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
    return six_five_arithmetic(truth_table)


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


def six_five_arithmetic(truth_table: str) -> str:
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
    n = _validate_truth_table(truth_table)
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
        a.raw(_six_five_nav(5, 2) + "62" * _ASCII_ONE + "A0")
        a.m("OUT_48").raw(_six_five_nav(5, 2) + "62" * _ASCII_ZERO + "A0")
    else:
        a.raw(_six_five_nav(1, 5) + "62" * _ASCII_ZERO + "A0")
    return a.build()
