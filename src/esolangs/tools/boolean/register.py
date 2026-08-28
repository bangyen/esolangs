"""Boolean-function generators for register-based languages."""

from typing import Any

from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _maybe_complement,
    _validate_truth_table,
    minterm_literals,
)
from esolangs.tools.text.helpers import _cm_constants

# Dig blocks for one level of the decision tree.
_DIG_BRANCH = ">2$~;#@"  # read a bit, store it, then turn on it
_DIG_CONTINUE = "> "  # a child of a branch: keep facing right into its own block
_DIG_LEAF = ">$3{}:@"  # set the mole to the result and print it
# ``$`` reads its repeat count from the digit beside it, so a run of cells
# under one ``$`` is at most nine long.
_DIG_SPAN = 9


def decleq(truth_table: str) -> str:
    """Build a Decleq program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Decleq's only arithmetic is ``b = a - 1`` with a ``<= 0`` jump, so each
    input byte (48/49) is normalized to 1/2 by a 47-step decrement chain,
    which makes ``cell cell c`` a branch: a ``0`` bit (1) decrements to 0 and
    jumps to ``c``, a ``1`` bit (2) falls through.  The decision tree routes
    those branches to leaves that output 48 or 49 (placed in data cells of
    the self-modifying memory) and then halt.

    A subtree whose rows all agree becomes a leaf rather than branching on
    bits that cannot change the answer.  Rows split most-significant-first,
    so a subtree is a contiguous run and ``11110000`` folds to a single
    branch -- unlike the generators that split the other way, where that
    table folds nothing.

    The fold has to be counted *before* it is emitted.  ``data_base`` sits
    above the code, so the output cells' addresses depend on how long the
    tree came out; :func:`tree_instrs` walks it first and must stop in
    exactly the places :func:`node` will.  When it does, the code ends
    exactly at ``data_base`` and the ``extend`` below allocates only the
    ``n`` read cells and the two output cells -- every cell in the program
    holds either an instruction or live data.

    Getting the count wrong does not produce a *broken* program: the
    ``extend`` fills out to whatever address was reserved, so the leaves
    still resolve and the output is still correct.  It silently inserts a
    run of dead zero cells instead (63 of them at ``n == 3`` if the tree is
    sized as though nothing folded), which is why the test pins the cell
    count rather than the output -- an output-based test cannot see it.

    The 47-step normalize chains are a fixed ``47 * n`` cost the fold
    cannot touch, so the saving grows with ``n`` as the tree overtakes
    them: 7% at ``n == 2`` against 44% at ``n == 6``.
    """
    n = _validate_truth_table(truth_table)

    def constant(level: int, row: int) -> bool:
        """Whether every row this subtree covers agrees.

        Rows split most-significant-first, so a subtree covers the
        contiguous run of ``2 ** (n - level)`` rows starting at ``row``.
        """
        span = 2 ** (n - level)
        return len(set(truth_table[row : row + span])) == 1

    def tree_instrs(level: int, row: int) -> int:
        """Instructions the subtree at ``(level, row)`` emits.

        The data cells sit above the code, so their addresses depend on
        how long the tree turns out to be -- which folding changes.  The
        count has to come from the same walk that emits, or every leaf
        would name the wrong output cell.
        """
        if level == n or constant(level, row):
            return 2  # output, then halt
        return (
            1
            + tree_instrs(level + 1, row + 2 ** (n - 1 - level))
            + tree_instrs(
                level + 1,
                row,
            )
        )

    # instructions: n reads, n*47 normalizations, and the tree, whose size
    # depends on how much of it folds away.
    n_instr = n + 47 * n + tree_instrs(0, 0)
    data_base = 3 * n_instr
    read_cells = [data_base + i for i in range(n)]
    out48 = data_base + n
    out49 = out48 + 1

    mem: list[int] = []

    def emit(a: int, b: int, c: int) -> None:
        mem.extend([a, b, c])

    def pc() -> int:
        return len(mem)

    def patch(addr: int, c: int) -> None:
        mem[addr + 2] = c

    for rc in read_cells:
        emit(-1, rc, pc() + 3)
    for rc in read_cells:
        for _ in range(47):
            emit(rc, rc, pc() + 3)

    # The halt jump has to name an address past the end of memory, which is
    # not known until the data cells below have been appended.  Each leaf
    # emits this placeholder and the real address is substituted once the
    # program is complete, so the sentinel is exactly one past the last cell
    # however the tree came out.
    halts: list[int] = []

    def node(level: int, row: int) -> None:
        # The fold has to stop in exactly the places tree_instrs stopped:
        # it sized the data cells from that walk, so a check applied here
        # and not there would leave every leaf naming the wrong address.
        if level == n or constant(level, row):
            emit(-2, out49 if truth_table[row] == "1" else out48, 0)
            emit(0, 0, 0)
            halts.append(pc() - 1)
            return
        rc = read_cells[level]
        emit(rc, rc, 0)
        branch = pc() - 3
        node(level + 1, row + 2 ** (n - 1 - level))
        target = pc()
        node(level + 1, row)
        patch(branch, target)

    node(0, 0)

    mem.extend([0] * (out49 - len(mem) + 1))
    mem[out48] = _ASCII_ZERO
    mem[out49] = _ASCII_ONE
    # One past the last cell: the interpreter halts as soon as the pointer
    # leaves memory, so this is the smallest address that stops the program.
    #
    # Being derived from the cell count is also what keeps it out of
    # wrap_grid's way, however big the program gets.  Every leaf names
    # out48 or out49 -- len(mem) - 2 and len(mem) - 1 -- so a token within
    # two of the sentinel always exists, and the two can differ by at most
    # one digit (only across a power of ten).  _cell_width drops an outlier
    # only while it is at least *twice* the next width, which one digit
    # never is above 9 cells, so the sentinel widens the cell at worst and
    # never spans two of them the way the old constant 10**9 did.
    for addr in halts:
        mem[addr] = len(mem)
    return " ".join(map(str, mem))


def addsubjump(truth_table: str) -> str:
    """Build an AddSubJump program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ASJ's instruction is ``a b c d``: ``*a += *b`` (when ``*d <= 0``) or
    ``*a -= *b`` (when ``*d > 0``), then ``goto *c``, where ``c`` is a cell
    holding the next instruction pointer.  There is no data-testable jump,
    so the generator routes a decision tree through the negative flag: with
    flag mode enabled (writing ``-9``), ``t -6 ... d`` (``d`` = the bit cell)
    sets the flag from the bit, but the branch itself is ``jump += 4 * bit``
    onto two consecutive trampolines.  Each bit (48/49) is normalized to
    ``{0, 4}`` (subtract 48, double twice), a jump cell initialized to the
    zero trampoline's address is advanced by that value, and ``goto *jump``
    lands on the zero or one trampoline, which jumps to the corresponding
    subtree.  Leaves print 48/49 and halt via ``c = -8`` (a special
    address).  Subtrees whose table entries are constant collapse to a leaf.
    """
    n = _validate_truth_table(truth_table)

    instructions: list[list[Any]] = []
    next_cells: list[str | None] = []
    values: dict[str, int | tuple[str, int]] = {}

    def emit(a: object, b: object, c: object, d: int) -> int:
        idx = len(instructions)
        next_cells.append(f"NEXT{idx}" if c == "next" else None)
        instructions.append([a, b, c, d])
        return idx

    emit(-9, -6, "next", -7)  # enable flag mode
    values["C48"] = -_ASCII_ZERO
    values["U"] = 0
    values["D48"] = _ASCII_ZERO
    values["D49"] = _ASCII_ONE
    values["DUMP"] = 0  # scratch the collapsed leaves read into and discard

    def build(level: int, rows: list[int]) -> None:
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            # Drain the reads the untaken siblings would have made: an
            # input-capable language reads each of its n inputs exactly once
            # per run whatever the table says, or the caller's remaining bits
            # are left on the input stream.  DUMP is write-only scratch.
            for _ in range(level, n):
                emit("DUMP", -1, "next", -7)  # DUMP += input byte, discarded
            out = _ASCII_ZERO + int(results.pop())
            emit(-1, f"D{out}", -8, -7)
            return
        base = len(instructions)
        bit = f"B{base}"
        jump = f"J{base}"
        zero = [r for r in rows if not ((r >> (n - 1 - level)) & 1)]
        one = [r for r in rows if (r >> (n - 1 - level)) & 1]
        values[bit] = 0
        values[jump] = ("t0", base + 6)
        emit(bit, -1, "next", -7)  # B += input byte (48/49)
        emit(bit, "C48", "next", -7)  # B += -48
        emit(bit, bit, "next", -7)  # double
        emit(bit, bit, "next", -7)  # double -> {0, 4}
        emit(jump, bit, "next", -7)  # J += B
        emit("U", "U", f"J{base}", -7)  # goto *J
        ztarget = f"Z{base}"
        otarget = f"O{base}"
        emit("U", "U", ztarget, -7)  # zero trampoline
        emit("U", "U", otarget, -7)  # one trampoline
        zstart = len(instructions)
        build(level + 1, zero)
        ostart = len(instructions)
        build(level + 1, one)
        values[ztarget] = ("addr", zstart)
        values[otarget] = ("addr", ostart)

    build(0, list(range(2**n)))

    base_data = 4 * len(instructions)
    names: list[str] = []

    def cell(name: str) -> int:
        if name not in names:
            names.append(name)
        return base_data + names.index(name)

    for ins in instructions:
        for v in ins:
            if isinstance(v, str) and v != "next":
                cell(v)
    for name in values:
        cell(name)
    for nc in next_cells:
        if nc:
            cell(nc)

    mem = [0] * (base_data + len(names))
    for i, ins in enumerate(instructions):
        row = []
        for v in ins:
            if v == "next":
                ncname = next_cells[i]
                if ncname is None:
                    raise AssertionError("no next cell for instruction")
                row.append(cell(ncname))
            elif isinstance(v, str):
                row.append(cell(v))
            else:
                row.append(v)
        mem[4 * i : 4 * i + 4] = row
    for name, val in values.items():
        idx = cell(name)
        mem[idx] = 4 * val[1] if isinstance(val, tuple) else val
    for i, nc in enumerate(next_cells):
        if nc:
            mem[cell(nc)] = 4 * (i + 1)
    return " ".join(map(str, mem))


def collatz_multiverse(truth_table: str) -> str:
    """Build a Collatz Multiverse program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    A register holding 0 or 1 is always odd, so on such registers the Collatz
    rule is affine (``v`` becomes ``v*var2+var3``), which makes AND, NOT, and
    minterms buildable: ``t = src x + zero`` multiplies by a 0/1 ``src`` and
    ``t = negativeOne x + one`` complements.  Each selected row of the table
    contributes its minterm (the AND of each bit's equality indicator); the
    OR is ``1 - prod (1 - minterm)``, and ``48 + result`` is printed.  The
    byte constants come from the text generator's constant table.

    A table with more ones than zeros selects its *zero* rows instead, since
    a minterm costs an indicator per input plus an AND chain.  Inverting
    the answer costs nothing: the OR already ends on the ``flip`` that turns
    ``prod (1 - minterm)`` into the result, so a complemented table simply
    keeps the accumulator as it stands.
    """
    n = _validate_truth_table(truth_table)
    if all(c == truth_table[0] for c in truth_table):
        # A constant table needs no evaluation, but the reads are the language's
        # interface: skipping them would leave the caller's bits unread on the
        # input stream and drop the prompts a prompting interpreter emits.  So
        # read every input, discard it, and print the constant.
        const = _ASCII_ZERO + int(truth_table[0])
        lines = _cm_constants({const})
        lines += [f"b{i} = negativeOne x + input, NOT PRINT." for i in range(n)]
        lines.append(f"out = negativeOne x + k{const}, DO PRINT.")
        return "\n".join(lines)

    lines = _cm_constants({_ASCII_ZERO})
    for i in range(n):
        lines.append(f"b{i} = negativeOne x + input, NOT PRINT.")

    next_reg = 0

    def fresh() -> str:
        nonlocal next_reg
        reg = f"r{next_reg}"
        next_reg += 1
        return reg

    def flip(src: str) -> str:
        reg = fresh()
        lines.append(f"{reg} = negativeOne x + {src}, NOT PRINT.")
        lines.append(f"{reg} = negativeOne x + k1, NOT PRINT.")
        return reg

    def and_bits(x: str, y: str) -> str:
        reg = fresh()
        lines.append(f"{reg} = negativeOne x + {x}, NOT PRINT.")
        lines.append(f"{reg} = {y} x + zero, NOT PRINT.")
        return reg

    acc = "acc"
    lines.append("acc = negativeOne x + k1, NOT PRINT.")
    # Each selected row costs a minterm -- an indicator per input, an AND
    # chain, and a flip -- so a dense table is built from its zeros.
    # Inverting is free here: the OR already ends on a ``flip``, so the
    # complement drops it rather than adding one.
    table, invert = _maybe_complement(truth_table)
    for k in range(2**n):
        if table[k] == "0":
            continue
        indicators = []
        for i, negated in minterm_literals(k, n):
            if negated:
                indicators.append(flip(f"b{i}"))
            else:
                reg = fresh()
                lines.append(f"{reg} = negativeOne x + b{i}, NOT PRINT.")
                indicators.append(reg)
        minterm = indicators[0]
        for indicator in indicators[1:]:
            minterm = and_bits(minterm, indicator)
        complement = flip(minterm)
        nacc = fresh()
        lines.append(f"{nacc} = negativeOne x + {acc}, NOT PRINT.")
        lines.append(f"{nacc} = {complement} x + zero, NOT PRINT.")
        acc = nacc

    # ``acc`` holds prod(1 - minterm), so the answer is its flip -- unless
    # the minterms were the table's zeros, when ``acc`` is already it.
    result = acc if invert else flip(acc)
    out = fresh()
    lines.append(f"{out} = negativeOne x + {result}, NOT PRINT.")
    lines.append(f"{out} = k1 x + k48, DO PRINT.")
    return "\n".join(lines)


def sophie(truth_table: str) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@$48{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. Each leaf sets the
    result with ``#$48``/``#$49`` and prints it before halting.
    """
    n = _validate_truth_table(truth_table)

    def build(path: list[int]) -> str:
        depth = len(path)
        row = 0
        for bit in path:
            row = row * 2 + bit
        # A short path has its unconsumed bits still to come, so it names
        # the start of the run they span rather than a row outright.
        row <<= n - depth
        if depth == n or len(set(truth_table[row : row + 2 ** (n - depth)])) == 1:
            # Sophie reads inside the tree -- a node is ``;`` then its
            # branch -- so a folded leaf still spends the reads it skipped.
            # A program whose input count depended on its table would
            # desync a caller feeding several programs from one stream.
            reads = ";" * (n - depth)
            return f"{reads}#${_ASCII_ZERO + int(truth_table[row])},&"
        return ";" + "@$48{" + build([*path, 0]) + "}" + "{" + build([*path, 1]) + "}"

    return build([])


def dig(truth_table: str) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The tree is laid out so the mole starts in the top-left corner (``'``)
    facing down into the root.  Each branch block reads one input bit:
    ``~`` inputs it, ``;`` stores it in the grid, and ``#`` turns the mole
    down or up on that bit.  The two children of a node keep facing right
    into the next level's branch, and the leaves print the function's value
    for the input combination they stand for.

    A subtree whose rows all agree becomes a leaf, and the rows it would
    have filled are simply never written -- which is what the walk buys
    over filling the grid level by level, where a pruned row still had to
    be skipped by hand.  A constant table collapses to a single line.

    A folded leaf still reads the inputs it never branched on, since a
    program whose input count depended on its table would desync a caller
    feeding several programs from one stream.  Those reads are cheap: a
    branch spends ``;`` to store its bit for its own ``#``, and a leaf
    turns nowhere, so the read is bare -- and ``$`` covers a run of cells
    at once, so they need no block each.  ``$`` takes its count from the
    digit beside it, so a run is at most nine cells and longer ones chain,
    each window spending one cell on the ``>`` that opens the next.
    """
    n = _validate_truth_table(truth_table)
    total = 2 ** (n + 1) - 1
    lines = ["" for _ in range(total)]
    width = len(_DIG_BRANCH)

    def place(row: int, level: int, block: str) -> None:
        """Write ``block`` on ``row``, in the column ``level`` owns."""
        lines[row] = lines[row].ljust(level * width) + block

    def leaf(reads: int, value: int) -> str:
        """Build a leaf that consumes ``reads`` inputs, then prints ``value``.

        ``$`` makes the cells after it commands, as many as the digit
        beside it says, so the reads a folded leaf still owes need no block
        each: one ``$`` covers every ``~`` plus the three cells that print.

        Its count is a single digit, so a window holds at most nine cells.
        Past that the windows chain -- each spends one of its nine on the
        ``>`` that opens the next -- which stays linear in the reads where
        a block apiece is four characters each.
        """
        if reads == 0:
            return _DIG_LEAF.format(value)
        out = ""
        while reads + 3 > _DIG_SPAN:
            take = _DIG_SPAN - 3
            out += f">${take + 1}" + "~" * take
            reads -= take
        return out + f">${reads + 3}" + "~" * reads + f"{value}:@"

    def walk(row: int, level: int, lo: int, hi: int) -> None:
        """Lay the subtree for ``truth_table[lo:hi]`` at ``row``."""
        if level == n or len(set(truth_table[lo:hi])) == 1:
            # A constant slice cannot be told apart by more branching, so
            # this is a leaf and every row below it goes unwritten.  It
            # still reads what it did not branch on: a program whose input
            # count depended on its table would desync a caller feeding
            # several programs from one stream.
            place(row, level, leaf(n - level, int(truth_table[lo])))
            return
        place(row, level, _DIG_BRANCH)
        step = 2 ** (n - level - 1)
        half = (hi - lo) // 2
        for child, bounds in (
            (row + step, (lo + half, hi)),
            (row - step, (lo, lo + half)),
        ):
            # the mole arrives here vertically from the parent's "#";
            # right-justify the turn so the ">" sits under that "#"
            place(child, level, _DIG_CONTINUE.rjust(width))
            walk(child, level + 1, *bounds)

    walk(total // 2, 0, 0, 2**n)

    # Row 0 is always written first (as the tree's root branch, or -- for
    # n == 0 -- its sole leaf), and both block kinds start with '>'; swap
    # that one cell for the mole's actual start marker rather than
    # special-casing row 0's emission in two different places above.
    lines[0] = "'" + lines[0][1:]
    # Rows are padded to a common width while the blocks are laid out, but the
    # mole never walks past the last command on a row, so the trailing filler
    # is inert and is trimmed rather than committed.
    return "\n".join(line.rstrip() for line in lines)


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


def qoibl(truth_table: str) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

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
    n = _validate_truth_table(truth_table)
    table, use_complement = _maybe_complement(truth_table)
    lines = []
    for i in range(n):
        lines.append(f"we {_qoibl_enc(i)} we et ry ey ry {_qoibl_enc(_ASCII_ZERO)} we")
    for i in range(n):
        lines.append(
            f"we {_qoibl_enc(n + i)} we {_qoibl_enc(1)} "
            f"ry ey ry qe {_qoibl_enc(i)} qe we",
        )
    lines.append(f"we {_qoibl_enc(2 * n)} we {_qoibl_enc(0)} we")
    for k in range(2**n):
        if table[k] == "0":
            continue
        factors = []
        for i, negated in minterm_literals(k, n):
            var = n + i if negated else i
            factors.append(f"qe {_qoibl_enc(var)} qe")
        product = factors[0]
        for factor in factors[1:]:
            product = f"{product} ry ye ry {factor}"
        lines.append(f"we {_qoibl_enc(2 * n + 1)} we {product} we")
        lines.append(
            f"we {_qoibl_enc(2 * n)} we qe {_qoibl_enc(2 * n)} "
            f"qe ry ee ry qe {_qoibl_enc(2 * n + 1)} qe we",
        )
    if use_complement:
        lines.append(
            f"tt {_qoibl_enc(_ASCII_ONE)} ry ey ry qe {_qoibl_enc(2 * n)} qe tt"
        )
    else:
        lines.append(
            f"tt qe {_qoibl_enc(2 * n)} qe ry ee ry {_qoibl_enc(_ASCII_ZERO)} tt"
        )
    return "\n".join(lines)


# Largest instruction count :func:`polynomial` will emit.  Each instruction
# consumes a fresh prime and contributes a factor, so the polynomial's degree
# -- and the cost of the sympy factorization the interpreter runs to recover
# the instructions -- tracks this count and nothing else.  One run measured
# on the interpreter: 52 instructions in 1.0s, 78 in 4.0s, 116 in 15s, 128 in
# 20s, 207 in 110s.  The bound sits just past the old gate's worst accepted
# case (an n == 4 tree, ~138 instructions at ~10s), which keeps every
# renderable table runnable in about the time this generator always cost.
#
# It replaces an ``n <= 4`` gate, which measured the wrong thing: the cost is
# instructions, not inputs, so a table that collapses to few states is cheap
# at any width -- parity renders through n == 8 at 106 instructions, where
# the old gate refused it from n == 5.
_POLYNOMIAL_MAX_INSTRS = 138


def polynomial(truth_table: str) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Polynomial programs are polynomials whose roots encode instructions, so
    both constructions below emit complex ``[a, b]`` (arithmetic, input,
    output) and real ``[val]`` (if/endif) roots that expand into
    ``f(x) = ...``.  Each instruction consumes a fresh prime, so the
    program's size and the interpreter's factorization cost both track the
    *instruction count* -- which is what the two constructions compete on.

    :func:`_polynomial_tree` is a decision tree that collapses a constant
    subtable to its output.  :func:`_polynomial_dag` is a state machine
    whose state lives in the instruction cursor, merging any two prefixes
    with the *same residual subfunction* rather than only constant ones --
    an ordered BDD where the tree is a plain tree.  **The shortest wins,
    with the tree first so ties keep the emission this generator already
    had.**

    The merge is strictly stronger than the fold and the gap grows with
    ``n``: parity is the tree's worst case at every width (``2**n - 1``
    internal nodes, 2298 instructions at n == 8) and needs just two states
    per level, so the machine is *linear* -- 13 instructions per input, 106
    at n == 8.  Over random tables the machine wins from n == 3 up (median
    0.87x the tree's instructions at n == 3, 0.43x at n == 6), while small
    or near-constant tables still favour the tree, which is why both are
    built and measured.  Measured over all 256 tables at n == 3, the
    dispatch is 18.4% shorter than the tree alone, improving 112 and
    growing none.

    **The order the tree tests its inputs in is not free here**, unlike
    every other decision-tree generator: a read *assigns* to the single
    register, so nothing survives it and the tested bit is always the one
    just read.  Both constructions therefore consume input in stream order,
    and reordering is unreachable rather than merely unhelpful.  What the
    machine recovers is the *saving* a reorder would have bought -- the
    residual merge subsumes the folds a better order would have exposed.

    A table needing more than ``_POLYNOMIAL_MAX_INSTRS`` instructions under
    both constructions raises :class:`ValueError`: the interpreter recovers
    instructions by factoring the polynomial, and that is what becomes
    impractical.  The bound is on instructions rather than on ``n``, so a
    table that collapses to few states renders at any width -- parity, the
    old gate's worst case, now renders through n == 8.
    """
    _validate_truth_table(truth_table)
    candidates = [_polynomial_tree(truth_table), _polynomial_dag(truth_table)]
    fits = [c for c in candidates if len(c) <= _POLYNOMIAL_MAX_INSTRS]
    if not fits:
        raise ValueError(
            "the Polynomial boolean generator emits one instruction per "
            f"prime and caps at {_POLYNOMIAL_MAX_INSTRS}, but this table "
            f"needs {min(len(c) for c in candidates)} under its cheaper "
            "construction, which the interpreter cannot factor in "
            "practical time",
        )
    # The tree is first and the comparison is strict, so a table the state
    # machine does not shorten emits exactly what it emitted before.
    return _polynomial_assemble(min(fits, key=len))


def _polynomial_assemble(instrs: list[list[int]]) -> str:
    """Expand an instruction list into its ``f(x) = ...`` polynomial.

    The k-th instruction takes the k-th prime ``p``: a complex instruction
    ``[a, b]`` contributes ``(x - a)**2 + p**(2*b)`` and a real one ``[v]``
    contributes ``x - p**v``, so the roots the interpreter factors back out
    are exactly the instructions.
    """
    from esolangs.tools._polynomial import format_coeffs, multiply, primes

    coeffs = [1]
    for instr, p in zip(instrs, primes(len(instrs)), strict=True):
        if len(instr) == 2:
            a, b = instr
            coeffs = multiply(coeffs, [1, -2 * a, a * a + p ** (2 * b)])
        else:
            coeffs = multiply(coeffs, [1, -(p ** instr[0])])
    return str(format_coeffs(coeffs))


def _polynomial_tree(truth_table: str) -> list[list[int]]:
    """Emit the decision-tree instructions; see :func:`polynomial`.

    A subtree whose rows are all the same value is collapsed to its single
    output, so constant and near-constant tables skip the tree that would
    otherwise isolate every leaf.  A collapsed leaf still drains the reads
    its untaken siblings would have made, so every path consumes ``n``.
    """
    n = _validate_truth_table(truth_table)
    instrs: list[list[int]] = []

    def emit_delta(delta: int) -> None:
        if delta > 0:
            instrs.append([delta, 1])
        # The tree walks the accumulator up from zero and every answer is 0
        # or 1, so the deltas the builder emits are never negative; the
        # subtract instruction is here for a builder that needs one.
        elif delta < 0:  # pragma: no cover - the tree only ever steps upward
            instrs.append([-delta, 2])

    def build(rows: list[int], bit: int, last: int) -> None:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            emit_delta(_ASCII_ZERO + v - last)
            instrs.append([0, 1])  # output
            # Drain the reads the untaken siblings would have made, *after*
            # printing so they cannot disturb the value being output: an
            # input-capable language reads each of its n inputs exactly once
            # per run whatever the table says, or the caller's remaining bits
            # are left on the input stream.
            for _ in range(bit, n):
                instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
            emit_delta(1)  # reg back to nonzero so the enclosing else skips
            return
        instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0 -> the one-bit subtree
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0 -> the zero-bit subtree
        build(g0, bit + 1, 0)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs


def _polynomial_states(truth_table: str, n: int) -> list[list[str]]:
    """Return the distinct residual subfunctions at each level.

    Level ``k``'s states are the distinct subtables of width ``2**(n-k)``
    reachable after reading ``k`` bits.  Two prefixes that leave the same
    subtable are the *same* state and share one continuation -- the merge
    a decision tree cannot make, since it can only collapse a subtable that
    is constant.
    """
    levels = [[truth_table]]
    for k in range(n):
        width = 2 ** (n - k - 1)
        nxt: list[str] = []
        for state in levels[k]:
            for half in (state[:width], state[width:]):
                if half not in nxt:
                    nxt.append(half)
        levels.append(nxt)
    return levels


def _polynomial_dag(truth_table: str) -> list[list[int]]:
    """Emit the state-machine instructions; see :func:`polynomial`.

    The register is the only storage and a read *assigns* to it, so nothing
    survives a read except the instruction cursor.  The state is therefore
    carried as *which branch is running*: each level is a chain of
    ``-= 1`` / ``if == 0`` tests over the live states, and the branch that
    fires reads its bit and moves to the child state's index.

    Two details are load-bearing.

    **``[0, b]`` is I/O, not arithmetic.**  The interpreter tests ``a == 0``
    before the opcode, so ``[0, 3]`` reads a character rather than
    multiplying by zero -- which is exactly the instruction a naive builder
    wants when both children merge.  That case instead reads and divides the
    bit away (``//= 50``), and an assertion below keeps any other ``a == 0``
    from being emitted.

    **A chain of equality tests re-fires.**  A taken branch leaves the
    register holding its child state, and the chain's remaining ``-= 1``
    steps keep running, so a later test can zero it and fire too.  Every
    branch therefore parks the register at ``offset + child + remaining``,
    so the trailing decrements bring each to the same ``offset + child`` and
    the value is never zero mid-chain; the next level's chain subtracts
    ``offset`` to recover the index.

    Exactly one branch fires per level, and every branch reads once, so each
    path consumes ``n`` inputs by construction rather than by draining.
    """
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    index = [{s: i for i, s in enumerate(level)} for level in levels]
    # Keeps a taken branch's register clear of every later test in its own
    # chain.  Only widens literals, never the instruction count that costs.
    offset = max(len(level) for level in levels) + 1
    instrs: list[list[int]] = []

    for k in range(n):
        width = 2 ** (n - k - 1)
        states = levels[k]
        for i, state in enumerate(states):
            if i:
                instrs.append([1, 2])  # -= 1
            instrs.append([4])  # if reg == 0
            remaining = len(states) - 1 - i
            zero_index = index[k + 1][state[:width]]
            one_index = index[k + 1][state[width:]]
            zero_target = offset + zero_index + remaining
            instrs.append([0, 2])  # input
            if zero_index == one_index:
                # Both children merge, so this bit cannot change the answer.
                # Divide it away rather than multiplying by zero, which the
                # interpreter would read as an input instruction.
                instrs.append([_ASCII_ZERO + 2, 4])  # //= 50 -> 0
            else:
                instrs.append([_ASCII_ZERO, 2])  # -= 48, leaving 0 or 1
                span = one_index - zero_index
                if span != 1:
                    instrs.append([span, 3])  # *= span, never zero here
            instrs.append([zero_target, 1])  # += the child's parked value
            instrs.append([2])  # endif
        instrs.append([offset, 2])  # -= offset, recovering the child index

    # The leaf states are one-wide subtables, so each *is* its answer.  No
    # guard is needed after printing: the register holds 48 or 49 and the
    # one decrement a two-state chain can still apply leaves 47 or 48.
    for i, state in enumerate(levels[n]):
        if i:
            instrs.append([1, 2])  # -= 1
        instrs.append([4])  # if reg == 0
        instrs.append([_ASCII_ZERO + int(state), 1])
        instrs.append([0, 1])  # output
        instrs.append([2])  # endif

    for instr in instrs:
        # ``a == 0`` is how the interpreter spells I/O, so an arithmetic
        # instruction that computed a zero operand would silently become a
        # read -- a wrong program rather than a failure.  The builder never
        # emits one; this raises rather than asserting so the guard survives
        # ``-O``, where the trap it catches would be silent.
        if len(instr) == 2 and instr[0] == 0 and instr not in ([0, 1], [0, 2]):
            raise AssertionError(
                f"{instr} has a zero operand, which the interpreter reads as "
                "I/O rather than arithmetic",
            )
    return instrs


def _pb_name(index: int) -> str:
    """Build the ``index``-th lowercase variable name (a, b, ..., z, aa, ...)."""
    name = ""
    index += 1
    while index > 0:
        index -= 1
        name = chr(ord("a") + index % 26) + name
        index //= 26
    return name


def point_break(truth_table: str) -> str:
    """Build a Point Break program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Point Break has no output command, so the generator uses the
    termination convention: the program halts iff the function's value is
    0 and loops forever iff it is 1 -- the wiki's own truth-machine
    semantics.  Each input is read with ``?``, every bit is complemented
    (``1 - bit``), and the function is evaluated as the sum of its
    minterms, each a product of bits and complements; every computation is
    a single-operation ``LET`` so no expression-precedence rule is relied
    on.

    A table with more ones than zeros sums its *zero* rows instead, since
    each row costs a ``LET`` per factor.  Inverting is free rather than one
    more line: ``g`` breaks the loop on a nonzero, so it is already the
    complement of the answer, and a complemented sum *is* ``g`` -- the
    subtraction is dropped rather than added to.

    The result ``f`` feeds a fixed template -- ``LET g:=one-f`` then
    ``POINT loop`` / ``IF g BREAK loop`` / ``END loop`` -- where ``g`` is
    nonzero exactly when ``f`` is 0, so the loop breaks (and the program
    halts) exactly on the 0 outputs and spins forever on the 1 outputs.
    A constant table needs none of the sum, so it emits the template
    directly -- all-0 a ``LET`` that always halts, all-1 the loop with a
    never-firing break -- but it still *reads* its ``n`` inputs first and
    discards them.  A program whose input count depended on its truth table
    would leave the caller's remaining bits on the stream for whatever ran
    next; the reads are the interface, and only the body may shrink.
    """
    n = _validate_truth_table(truth_table)
    # The reads a constant table makes and throws away.  ``?`` is the read,
    # and the names are the ones the non-constant path would have used, so
    # nothing else about the template shifts.
    discards = [f"LET {_pb_name(1 + i)}:=?" for i in range(n)]
    if all(c == "0" for c in truth_table):
        return "\n".join([*discards, f"LET {_pb_name(0)}:=1"])
    if all(c == "1" for c in truth_table):
        return "\n".join(
            [
                *discards,
                f"LET {_pb_name(0)}:=0",
                "POINT loop",
                f"IF {_pb_name(0)} BREAK loop",
                "END loop",
            ]
        )

    lines = [f"LET {_pb_name(0)}:=1"]
    for i in range(n):
        lines.append(f"LET {_pb_name(1 + i)}:=?")
    for i in range(n):
        lines.append(f"LET {_pb_name(1 + n + i)}:={_pb_name(0)}-{_pb_name(1 + i)}")
    lines.append(f"LET {_pb_name(1 + 2 * n)}:=0")
    # Each selected row costs a ``LET`` per factor plus one to add it in, so
    # a table with more ones than zeros is cheaper summed over its *zero*
    # rows.  Inverting is free: the tail already needs ``1 - f`` for the
    # loop guard, so a complemented sum *is* that guard.
    table, invert = _maybe_complement(truth_table)
    for k in range(2**n):
        if table[k] == "0":
            continue
        factors = [
            _pb_name(1 + n + i) if negated else _pb_name(1 + i)
            for i, negated in minterm_literals(k, n)
        ]
        lines.append(f"LET {_pb_name(2 + 2 * n)}:={factors[0]}")
        for factor in factors[1:]:
            lines.append(f"LET {_pb_name(2 + 2 * n)}:={_pb_name(2 + 2 * n)}*{factor}")
        lines.append(
            f"LET {_pb_name(1 + 2 * n)}:={_pb_name(1 + 2 * n)}+{_pb_name(2 + 2 * n)}"
        )
    # ``g`` is the loop guard, which breaks on a nonzero -- so it is the
    # complement of the answer, and a complemented sum already holds it.
    if invert:
        lines.append(f"LET {_pb_name(3 + 2 * n)}:={_pb_name(1 + 2 * n)}")
    else:
        lines.append(f"LET {_pb_name(3 + 2 * n)}:={_pb_name(0)}-{_pb_name(1 + 2 * n)}")
    lines.extend(
        [
            "POINT loop",
            f"IF {_pb_name(3 + 2 * n)} BREAK loop",
            "END loop",
        ]
    )
    return "\n".join(lines)
