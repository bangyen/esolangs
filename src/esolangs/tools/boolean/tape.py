"""Boolean-function generators for tape-based languages."""

import sys
from collections.abc import Sequence
from typing import cast

# dimensional, rotfuck, and six_five each own a file because their
# construction (a survivor walk, a per-position rotation, an assembler)
# dwarfs the rest of the category; they are re-exported here so this
# module stays the import site the package and tests already use.
from esolangs.tools.boolean.dimensional import dimensional, dimensional_tree
from esolangs.tools.boolean.helpers import (
    _maybe_complement,
    _validate_truth_table,
    decision_tree_program,
)
from esolangs.tools.boolean.rotfuck import rotfuck
from esolangs.tools.boolean.six_five import six_five, six_five_arithmetic
from esolangs.tools.text.tape import _factor_encode

__all__ = [
    "basicfuck",
    "bf_tree",
    "brainfuck",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "dimensional",
    "dimensional_tree",
    "factor",
    "jaune",
    "jaune_multiply",
    "painfuck",
    "rotfuck",
    "sbleq",
    "six_five",
    "six_five_arithmetic",
    "suffolk",
    "three_d_brainfuck",
]


def brainif(truth_table: str) -> str:
    """Build a BrainIf program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    BrainIf reads each input into a cell with ``if 0 input``, then a
    recursive decision tree checks each cell with ``if 48/49 goto`` (the
    groups' checks sit adjacent so a failed check falls through to the next
    candidate).  Every leaf lands on a fresh cell (the last marker moved the
    pointer past the inputs), so it jumps to one of two shared output
    routines that build 48 or 49 in place and print it, instead of each leaf
    incrementing a fresh cell itself.
    """
    n = _validate_truth_table(truth_table)
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


def circlefuck(truth_table: str) -> str:
    """Build a Circlefuck program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Circlefuck reads each input with ``,`` and normalizes it to 0/1 with 48
    ``-``s, then a decision tree branches on the cells from the last input
    down. Each leaf starts from a cleared cell, so it sets the result with
    ``+``s, prints it, and halts with ``@`` -- halting at the leaf means the
    tree never needs to skip the sibling branch.  A boolean table is just
    the byte-valued generator with ``48 + bit`` outputs.
    """
    return circlefuck_byte([48 + int(bit) for bit in truth_table])


def circlefuck_byte(truth_table: Sequence[int]) -> str:
    """Build a Circlefuck program computing a byte-valued function.

    ``truth_table`` is a sequence of ``2**n`` byte values (0-255) indexed by
    the inputs (most significant first); the input count ``n`` is implied
    by the table length.  This is the boolean generator generalized to
    arbitrary byte outputs: each leaf prints ``chr(value)`` instead of
    ``chr(48 + bit)``.
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
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


def _bf_minterm(truth_table: str) -> str:
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
    n = _validate_truth_table(truth_table)
    table, use_complement = _maybe_complement(truth_table)

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


def brainfuck(truth_table: str) -> str:
    """Build a brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Two generators exist with complementary strengths, and ``bf`` returns
    the shorter of the two for the given table:

    - ``_bf_minterm``: a branch-free sum of minterms (each input read and
      normalized to 0/1, the result ``48 + sum_k tt[k] * M_k``).  Best for
      sparse tables (few one-rows) — an all-zeros table is ~450 chars even
      at n == 8.
    - :func:`bf_tree`: a decision tree sharing the bit tests.  Best for
      dense tables — XOR-n is ~1000x smaller than the minterm at n == 8.
    """
    return min((_bf_minterm(truth_table), bf_tree(truth_table)), key=len)


def factor(truth_table: str) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    A Factor program is a single integer whose prime factorization decodes
    to brainfuck, so the generator reuses :func:`brainfuck`'s truth-table
    program unchanged and encodes it with :func:`_factor_encode` -- the same
    prime-search the text generator uses (walk primes upward, handing each
    instruction the next one with the right residue mod 11; Dirichlet's
    theorem guarantees one always exists).

    This is a program-size cap, not an ``n`` cap: sparse tables (e.g. an
    all-zero or all-one table) stay small at any ``n``, while dense tables
    grow the underlying brainfuck program (and so the encoded integer)
    quickly.  CPython refuses to render an integer above
    ``sys.get_int_max_str_digits()`` decimal digits (a DoS guard, not a
    Factor property), and the Factor *interpreter* parses its input the
    same way, so a program past that limit would not just fail to print
    here -- it would fail to run.  The check estimates the digit count from
    the integer's bit length (``log10(2) ~= 0.30103``) to avoid paying for
    the same oversized conversion just to reject it.
    """
    number = _factor_encode(brainfuck(truth_table))
    limit = sys.get_int_max_str_digits()
    if limit and number.bit_length() * 0.30103 + 1 > limit:
        raise ValueError(
            "the Factor boolean generator's encoded integer would exceed "
            f"Python's {limit}-digit limit for integer-to-string conversion "
            "(sys.get_int_max_str_digits()) -- the Factor interpreter parses "
            "its program the same way, so this table's encoding could not "
            "be run even if it were rendered; try a sparser table",
        )
    return str(number)


def three_d_brainfuck(truth_table: str) -> str:
    """Build a 3D Brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    3D Brainfuck's ``>``/``<`` set the generation pointer's heading (a no-op
    in this interpreter), so the array is walked along one axis with
    ``e``/``w`` instead; the brainfuck minterm and decision-tree strategies
    otherwise translate directly, and :func:`bf` picks the shorter of the
    two.
    """
    return brainfuck(truth_table).translate(str.maketrans("><", "ew"))


# The interpreter's two substitution cycles, in the order the cross-check
# scans them: Painfuck source is pre-shifted here so the trans table recovers
# the intended commands.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck(truth_table: str) -> str:
    """Build a Painfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

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
        brainfuck(truth_table)
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


def bf_tree(truth_table: str) -> str:
    """Build a decision-tree brainfuck program for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The construction is :func:`decision_tree_program`, shared with
    :func:`dimensional_tree`.  The tree is O(2**n) characters (sharing the
    bit tests), versus the branch-free minterm evaluator's O(n * 2**n); for
    XOR-n it measures 1.4K..20K characters at n = 2..8 against the
    minterm's 1.4K..33M.
    """
    return decision_tree_program(truth_table, ">", "<")


def basicfuck(truth_table: str) -> str:
    """Build a Basicfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

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
    n = _validate_truth_table(truth_table)

    lines = ["#basicfuck t=unbounded r=0~255 o=wrap"]
    lines.append("#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out")
    for i in range(1, n + 1):
        lines.append(f"read -> a{i} ;")
        lines.append(f"a{i} -= 48 ;")

    def build(rows: list[int], k: int, depth: int) -> str:
        indent = "  " * depth
        if len(rows) == 1:
            value = int(truth_table[rows[0]])
            return f"{indent}out += {48 + value} ;\n{indent}write <- out ;\n"
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        var = f"a{k}"
        return (
            f"{indent}if ({var}) {{\n"
            + build(g1, k + 1, depth + 1)
            + f"{indent}}}\n"
            + f"{indent}if !({var}) {{\n"
            + build(g0, k + 1, depth + 1)
            + f"{indent}}}\n"
        )

    lines.append(build(list(range(2**n)), 1, 0).rstrip("\n"))
    return "\n".join(lines)


def sbleq(truth_table: str) -> str:
    """Build an S*bleq program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

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
    n = _validate_truth_table(truth_table)

    instructions: list[tuple[int, int, int]] = []
    nodes: list[tuple[int, int, int]] = []  # (v offset, normalize addr, one addr)
    counter = 0

    def build(level: int, rows: list[int]) -> None:
        nonlocal counter
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            instructions.append((-3, 1 + int(results.pop()), 0))
            # Drain the reads the untaken siblings would have made, after the
            # output so they cannot disturb it: an input-capable language reads
            # each of its n inputs exactly once per run whatever the table
            # says, or the caller's remaining bits stay on the input stream.
            # Each drained level allocates a node whose branches both continue
            # here, so the read happens and the control flow is unchanged.
            for _ in range(level, n):
                nid = counter
                counter += 1
                instructions.append((4 + nid, -2, 0))  # read; c patched to NXT
                normalize_addr = 3 * len(instructions)
                instructions.append((4 + nid, 0, 0))  # normalize; patched below
                nodes.append((nid, normalize_addr, 3 * len(instructions)))
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


def jaune(truth_table: str) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Jaune reads each input bit with ``v`` (a digit character, ``ord-48``) into
    a fresh cell and routes a decision tree with ``?``/``!`` jumps: ``v`` then
    ``N?`` jumps to label ``N`` when the cell is nonzero, else falls through,
    and each leaf builds 48 or 49 in a fresh cell and prints it with ``^``
    before jumping to a shared end label.  A subtree whose table slice is a
    constant collapses to a single leaf.
    """
    n = _validate_truth_table(truth_table)
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


def suffolk(truth_table: str) -> str:
    """Build a Suffolk program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Suffolk has no branch and no data-dependent jump, so this is a
    branch-free sum of minterms, run at ``limit=1`` (a single pass, one
    read per input -- the default 10-pass rerun would replay every ``,``
    with no more input left).  The only nonlinearity is ``!``, which
    computes ``max(0, cell + 1 - acc)``: with a preloaded 48-cell and
    ``acc = 48 + bit`` (one ``,`` read), it yields the complement
    ``1 - bit``; a second ``!`` from a zero cell complements again to
    recover ``bit``.  Summing ``n`` literals (complement when the row wants
    a 0, raw bit when it wants a 1) into ``acc`` and applying ``!`` to a
    zero cell gives ``max(0, 1 - sum)``, which is 1 only when every literal
    matches (an AND of that row's minterm) and 0 otherwise.  Every row's
    minterm cell is 0 except the one matching the actual inputs, so summing
    all of them plus a preloaded 49-cell into ``acc`` and printing
    (``.`` emits ``chr(acc - 1)``) prints ``48`` or ``49``.

    Constant tables need no reads at all: ``.`` prints ``chr(acc - 1)``, so
    the accumulator only has to hold 50 (all-ones, prints ``49``) or 49
    (all-zeros, prints ``48``) at the print.
    """
    n = _validate_truth_table(truth_table)

    def const(gap: int, value: int) -> str:
        """``(gap '>'s then '!') * value`` builds ``value`` at that cell.

        ``!`` resets the pointer to 0, so each repetition re-walks ``gap``
        steps out to the same cell before incrementing it.
        """
        return (">" * gap + "!") * value

    if len({*truth_table}) == 1:
        # A constant table needs no minterms, but the reads are the language's
        # interface: skipping them leaves the caller's bits unread on the input
        # stream.  Read each input into its own scratch cell and discard it.
        reads = "".join(const(2 + i, 48) + ">" * (2 + i) + "," + "!" for i in range(n))
        return const(1, 49 + int(truth_table[0])) + reads + ">" + "<" + "."

    code = const(1, 49)  # cell 1: the final additive constant
    # cells 2..2+n-1: complement of each input bit (1 - bit)
    for i in range(n):
        gap = 2 + i
        code += const(gap, 48) + ">" * gap + "," + "!"
    # cells 2+n..2+2n-1: the raw bit, recovered from the complement
    for i in range(n):
        gap = 2 + i
        raw_gap = 2 + n + i
        code += ">" * gap + "<" + ">" * raw_gap + "!"

    minterm_cells: list[int] = []
    next_cell = 2 + 2 * n
    for row in range(2**n):
        if truth_table[row] != "1":
            continue
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        literals = [(2 + i) if v else (2 + n + i) for i, v in enumerate(bits)]
        code += "".join(">" * c + "<" for c in literals)
        code += ">" * next_cell + "!"
        minterm_cells.append(next_cell)
        next_cell += 1

    code += "".join(">" * c + "<" for c in minterm_cells)
    code += ">" + "<"  # add the constant cell
    code += "."
    return code
