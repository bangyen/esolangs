"""Boolean-function generators for register-based languages."""

from typing import Any

from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    essential_inputs,
    minterm_sum,
    read_at,
    stored_inputs,
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

    Every input is still read, so the program consumes exactly ``n`` input
    bytes.  But an ignored input never controls a non-folded branch, so it
    needs no 47-step normalization chain: the fixed cost is
    ``47 * len(essential_inputs)`` rather than ``47 * n``.
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

        The data cells sit above the code, so their addresses depend on the
        tree's length -- which folding changes.  The count has to come from
        the same walk that emits, or every leaf would name the wrong output
        cell.
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

    # Every input is read to preserve the interface, but only inputs on
    # which the table depends need normalizing: folding makes both outcomes
    # of every other branch equivalent.
    essential = set(essential_inputs(truth_table, n))
    # instructions: n reads, one normalization chain per essential input,
    # and the tree, whose size depends on how much of it folds away.
    n_instr = n + 47 * len(essential) + tree_instrs(0, 0)
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
    for i, rc in enumerate(read_cells):
        if i not in essential:
            continue
        for _ in range(47):
            emit(rc, rc, pc() + 3)

    # The halt jump has to name an address past the end of memory, unknown
    # until the data cells below have been appended.  Each leaf emits this
    # placeholder and the real address is substituted once the program is
    # complete, so the sentinel is exactly one past the last cell however the
    # tree came out.
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
    # Deriving it from the cell count also keeps it out of wrap_grid's way,
    # however big the program gets.  Every leaf names out48 or out49 --
    # len(mem) - 2 and len(mem) - 1 -- so a token within two of the sentinel
    # always exists, and the two can differ by at most one digit (only across
    # a power of ten).  _cell_width drops an outlier only while it is at
    # least *twice* the next width, which one digit never is above 9 cells,
    # so the sentinel widens the cell at worst and never spans two of them
    # the way the old constant 10**9 did.
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
    so the generator routes a decision tree through two trampolines: a jump
    cell initialized to the zero trampoline's address is advanced by
    ``4 * bit``, and ``goto *jump`` lands on the zero or one trampoline,
    which jumps to the corresponding subtree.  Leaves print 48/49 and halt
    via ``c = -8`` (a special address).  Subtrees whose table entries are
    constant collapse to a leaf.

    **All ``n`` bits are read up front**, each into a cell of its own and
    normalized there once from 48/49 to ``{0, 4}`` (subtract 48, double
    twice).  A node then spends two instructions -- ``J += B`` naming
    whichever bit it tests, and ``goto *J``.  Reading at the node instead
    would repeat the four-instruction normalization at every node and make a
    folded leaf drain the reads its untaken siblings skipped; hoisting pays
    for both once, 25.1% of the program at n == 3 before any reordering.

    **The tree then splits on its inputs in whichever order emits the
    shortest program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`),
    which the hoist enables: with every bit in its own cell, ``J += *b`` can
    name any of them, so a node is not tied to the bit just read.  The reads
    stay in stream order, so the program consumes its input exactly as
    before.  Reordering adds 8.9% on top of the hoist at n == 3, for 31.7%
    together, rising to 41.0% at n == 4 and 47.8% at n == 5.

    Only the inputs the tree actually branches on get a cell; one no node
    tests is read into write-only scratch, so a constant table still
    consumes every input without storing any.
    """
    return best_input_order(truth_table, _addsubjump_ordered)


def _addsubjump_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's AddSubJump program; see :func:`addsubjump`.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame; ``perm`` surfaces only where a node names the *stream*
    input whose cell it tests.

    Cells are named by the input they hold (``B{i}`` for stream input ``i``),
    not by the instruction index that allocated them.  The node-read build
    keyed its names off ``len(instructions)``, which a reorder shifts; naming
    by input keeps every reference stable however the tree comes out.
    """
    n = _validate_truth_table(truth_table)

    instructions: list[list[Any]] = []
    next_cells: list[str | None] = []
    values: dict[str, int | tuple[str, int]] = {}
    # The operand names in the order the instructions mention them, recorded
    # as they are emitted.  The numbering pass below wants exactly this list
    # and used to recover it by re-scanning every operand of every
    # instruction -- 3.5M ``isinstance`` calls on a six-input build, which
    # the order search pays once per candidate.
    named: list[str] = []

    def emit(a: object, b: object, c: object, d: int) -> int:
        idx = len(instructions)
        next_cells.append(f"NEXT{idx}" if c == "next" else None)
        instructions.append([a, b, c, d])
        for v in (a, b, c):
            if isinstance(v, str) and v != "next":
                named.append(v)
        return idx

    emit(-9, -6, "next", -7)  # enable flag mode
    values["C48"] = -_ASCII_ZERO
    values["U"] = 0
    values["D48"] = _ASCII_ZERO
    values["D49"] = _ASCII_ONE

    stored = stored_inputs(truth_table, perm)

    # The reads, in stream order.  An input no node tests is read into
    # write-only scratch: the contract is that every input is *consumed*,
    # not that every value is kept.
    if any(i not in stored for i in range(n)):
        values["DUMP"] = 0
    for i in range(n):
        if i not in stored:
            emit("DUMP", -1, "next", -7)  # read and discard
            continue
        bit = f"B{i}"
        values[bit] = 0
        emit(bit, -1, "next", -7)  # B += input byte (48/49)
        emit(bit, "C48", "next", -7)  # B += -48
        emit(bit, bit, "next", -7)  # double
        emit(bit, bit, "next", -7)  # double -> {0, 4}

    # Rows split most significant first, so the span a node covers is the
    # contiguous ``truth_table[lo:hi]`` and its two halves are that slice cut
    # in two.  Carried as a pair rather than as the list of row indices it
    # used to be: the list rebuilt itself at every node, O(n * 2**n) per
    # candidate, for spans the slice bounds already name.
    def build(level: int, lo: int, hi: int) -> None:
        if truth_table.count(truth_table[lo], lo, hi) == hi - lo:
            # Every read already happened up front, so a folded leaf prints
            # and halts with nothing to drain.
            out = _ASCII_ZERO + int(truth_table[lo])
            emit(-1, f"D{out}", -8, -7)
            return
        half = (hi - lo) // 2
        if perm[level] not in stored:
            # A discarded input has no cell to test.  Its bit cannot change
            # the answer, so both halves are the same function -- descend
            # into the zero half, keeping the row span halving with level.
            build(level + 1, lo, lo + half)
            return
        base = len(instructions)
        bit = f"B{perm[level]}"
        jump = f"J{base}"
        # Two instructions precede the trampolines, so the jump cell starts
        # at the zero trampoline two slots on.
        values[jump] = ("t0", base + 2)
        emit(jump, bit, "next", -7)  # J += B, the hoisted bit this node tests
        emit("U", "U", jump, -7)  # goto *J
        ztarget = f"Z{base}"
        otarget = f"O{base}"
        emit("U", "U", ztarget, -7)  # zero trampoline
        emit("U", "U", otarget, -7)  # one trampoline
        zstart = len(instructions)
        build(level + 1, lo, lo + half)
        ostart = len(instructions)
        build(level + 1, lo + half, hi)
        values[ztarget] = ("addr", zstart)
        values[otarget] = ("addr", ostart)

    build(0, 0, 2**n)

    base_data = 4 * len(instructions)
    # Insertion-ordered name -> index.  A dict rather than a list because the
    # list spelling scanned twice per call -- ``in`` and then ``.index`` --
    # which is O(names) on a table that calls this once per operand: 1.6M
    # calls and 2.4s of a 3.8s six-input build, the generator's whole cost.
    # ``dict`` preserves insertion order, so the numbering it hands out is
    # the same one the scan produced.
    names: dict[str, int] = {}

    def cell(name: str) -> int:
        index = names.get(name)
        if index is None:
            index = names[name] = len(names)
        return base_data + index

    for name in named:
        names.setdefault(name, len(names))
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
    a minterm costs an indicator per input plus an AND chain.  Inverting the
    answer costs nothing: the OR already ends on the ``flip`` that turns
    ``prod (1 - minterm)`` into the result, so a complemented table keeps the
    accumulator as it stands.
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
    # A table that ignores some of its inputs is a smaller table, and since a
    # minterm costs an indicator *per input*, dropping an input removes rows
    # and shortens the rows that remain.  Every input keeps its ``b{i}`` read
    # (the reads are the interface); an ignored one is never turned into an
    # indicator.  This is the constant branch above generalized from "no
    # essential inputs" to "the ones that matter".

    # ``literal`` allocates a register and emits for a non-negated input, so
    # it is called in the same order the hand-written loop called it: every
    # literal of a row, then its product, then the accumulate.
    def literal(i: int, negated: bool) -> str:  # noqa: FBT001 - a literal's sign, from minterm_literals
        if negated:
            return flip(f"b{i}")
        reg = fresh()
        lines.append(f"{reg} = negativeOne x + b{i}, NOT PRINT.")
        return reg

    def product(factors: list[str]) -> str:
        minterm = factors[0]
        for factor in factors[1:]:
            minterm = and_bits(minterm, factor)
        return flip(minterm)

    def accumulate(row: str) -> None:
        nonlocal acc
        nacc = fresh()
        lines.append(f"{nacc} = negativeOne x + {acc}, NOT PRINT.")
        lines.append(f"{nacc} = {row} x + zero, NOT PRINT.")
        acc = nacc

    _used, _width, invert = minterm_sum(truth_table, literal, product, accumulate)

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

    :func:`_sophie_hybrid` nests unshared residual states like a tree and
    labels only states reached from multiple parents. It therefore keeps
    constant-subtree folding while merging equal residual subfunctions.

    The hybrid only pays a label where sharing needs it, so it cannot lose
    the tree's compact unshared regions.

    **Reordering the inputs is not available here**, unlike most tree
    generators: ``;`` and ``:`` *assign* to the accumulator, ``#`` loads only
    a literal, and nothing else writes it, so a bit can only be branched on
    before the next read and the test order is the stream order.  The merge
    collects the saving a reorder would have found.
    """
    _validate_truth_table(truth_table)
    return _sophie_hybrid(truth_table)


# leaves test against.
_SOPHIE_BANDS = ((1, 20), (21, 40))


def _sophie_hybrid(truth_table: str) -> str:
    """Emit a Sophie tree that labels only shared residual states."""
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    references: list[dict[str, int]] = [{} for _ in levels]
    for k in range(n - 1):
        width = 2 ** (n - k - 1)
        for state in levels[k]:
            if len(set(state)) == 1:
                continue
            for child in {state[:width], state[width:]}:
                references[k + 1][child] = references[k + 1].get(child, 0) + 1

    retained = [
        [
            state
            for state in states
            if k == 0 or (len(set(state)) > 1 and references[k].get(state, 0) > 1)
        ]
        for k, states in enumerate(levels)
    ]
    labels = [
        {state: _SOPHIE_BANDS[k % 2][0] + index for index, state in enumerate(states)}
        for k, states in enumerate(retained)
    ]

    def body(k: int, state: str) -> str:
        if len(set(state)) == 1:
            return ";" * (n - k) + f"#${_ASCII_ZERO + int(state[0])},&"
        width = 2 ** (n - k - 1)
        zero, one = state[:width], state[width:]
        if k + 1 == n:
            return (
                f";@$48{{#${_ASCII_ZERO + int(zero)},&}}"
                f"{{#${_ASCII_ZERO + int(one)},&}}"
            )

        def next_body(child: str) -> str:
            if child in labels[k + 1]:
                return f"#${labels[k + 1][child]}"
            return body(k + 1, child)

        if zero == one:
            return ";" + next_body(zero)
        return f";@$48{{{next_body(zero)}}}{{{next_body(one)}}}"

    out = []
    for k, states in enumerate(retained):
        for state in states:
            block = body(k, state)
            out.append(block if k == 0 else f"@${labels[k][state]}{{{block}}}")
    return "".join(out)


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
    have filled are never written -- which is what the walk buys over filling
    the grid level by level, where a pruned row still had to be skipped by
    hand.  A constant table collapses to a single line.

    A folded leaf still reads the inputs it never branched on, since a
    program whose input count depended on its table would desync a caller
    feeding several programs from one stream.  Those reads are cheap: a
    branch spends ``;`` to store its bit for its own ``#``, and a leaf turns
    nowhere, so the read is bare -- and ``$`` covers a run of cells at once,
    so they need no block each.  ``$`` takes its count from the digit beside
    it, so a run is at most nine cells and longer ones chain, each window
    spending one cell on the ``>`` that opens the next.
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

        ``$`` makes the cells after it commands, as many as the digit beside
        it says, so the reads a folded leaf still owes need no block each:
        one ``$`` covers every ``~`` plus the three cells that print.

        Its count is a single digit, so a window holds at most nine cells.
        Past that the windows chain -- each spends one of its nine on the
        ``>`` that opens the next -- staying linear in the reads where a
        block apiece is four characters each.
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

    # The root branch sits at row ``total // 2``, so row 0 is only ever a
    # leaf or a deep fragment and its column 0 is blank or left padding --
    # every block on it starts at level 1 or deeper.  Overwrite that one
    # free cell with the mole's start marker rather than special-casing
    # row 0's emission in two different places above.
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
    # A table that ignores some of its inputs is a smaller table, and since a
    # minterm costs one ``qe`` factor *per input* on top of two lines per
    # selected row, dropping an input removes rows and shortens the rows that
    # remain.  Every input keeps its ``et`` read, its normalization and its
    # complement (they are the interface); an ignored one is never named as a
    # factor.  Measured at ``n == 3``, that setup is 29% of a one-dependency
    # program and the minterm body the other 71%, so most of the arity cost
    # here is reachable -- unlike ``suffolk``, whose per-input setup is 96%
    # of the program.
    lines = []
    for i in range(n):
        lines.append(f"we {_qoibl_enc(i)} we et ry ey ry {_qoibl_enc(_ASCII_ZERO)} we")
    for i in range(n):
        lines.append(
            f"we {_qoibl_enc(n + i)} we {_qoibl_enc(1)} "
            f"ry ey ry qe {_qoibl_enc(i)} qe we",
        )
    lines.append(f"we {_qoibl_enc(2 * n)} we {_qoibl_enc(0)} we")

    def literal(i: int, negated: bool) -> str:  # noqa: FBT001 - a literal's sign, from minterm_literals
        return f"qe {_qoibl_enc(n + i if negated else i)} qe"

    def product(factors: list[str]) -> str:
        out = factors[0]
        for factor in factors[1:]:
            out = f"{out} ry ye ry {factor}"
        return out

    def accumulate(row: str) -> None:
        lines.append(f"we {_qoibl_enc(2 * n + 1)} we {row} we")
        lines.append(
            f"we {_qoibl_enc(2 * n)} we qe {_qoibl_enc(2 * n)} "
            f"qe ry ee ry qe {_qoibl_enc(2 * n + 1)} qe we",
        )

    _used, _width, use_complement = minterm_sum(
        truth_table, literal, product, accumulate
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
# -- and the cost of recovering the instructions from it -- tracks this count
# and nothing else.
#
# The bound is the analytic worst case over n == 10 tables: level ``k`` of
# the state machine holds at most ``min(2**k, 2**2**(10 - k))`` states at 7
# instructions each (5 fixed plus at most 2 transitions), and the leaf level
# 5 each less the final endif -- ``7*275 + 5*2 - 1 = 1934``, so every n=10
# table builds.  ``test_polynomial_cap_admits_every_n10_table`` re-derives
# it.  The dense n=10 fixture needs 1638; dense n=11 needs 2910 and is
# refused.
#
# The policy is still "admit what a suite can afford to check", against a
# cost curve that moved twice.  At 138 recovery was a bare ``factor_list``
# (~10s at the bound); the exact peels bought 328 (n=7 dense, 21.1s a row).
# Two interpreter changes moved it again: recovery is cached per program --
# rows of one table share a single factorization and parse -- and past
# ``_NTT_MIN_DEGREE`` peel candidates come from NTT root sets rather than
# enumeration and GF factoring.  Measured on the dense fixtures, whole
# table verified against every row: n=8 (541 instructions) 3.5s for all
# 256 rows where the old path took 115s for the *first*, n=10 (1638) 44s
# for all 1024 rows, 43.7s of it the one factorization.
#
# The count, not the arity, is still what this measures: a table that
# collapses to few states is cheap at any width, and parity renders far
# past n == 10 inside the bound.
#
# What the bound declines is measured, not assumed: past it, dense n=11
# (2910 instructions) builds and runs all 2048 rows correctly in 267s --
# 264.5s of that the single factorization, then 0.001s a row -- for a
# 123609143-character program.  Against n=10 on the same machine (1638,
# 56s), 1.78x the instructions costs 4.7x the time.  Left at 1934 on that
# price.
_POLYNOMIAL_MAX_INSTRS = 1934

# How far above the cheapest candidate the dispatch still renders.  Selection
# is on characters, so the instruction count only screens -- and a strict
# screen picks wrong, because the two disagree.  ``01100110`` is the case:
# the drained
# machine is 30 instructions and renders 5267 characters, while a drained
# ``k == 2`` build is 32 and renders 4814, since a longer program's later
# instructions consume larger primes.
#
# The slack has to be measured per arity, not guessed: every table at
# n <= 3 needs at most 6 (242 of 256 need 0), but 1000 sampled tables at
# n == 4 reach 9, and 32 of them need more than 6 -- a slack fitted to the
# smaller corpus silently emits the worse program on those.  Held at the
# n == 4 worst case with a margin of one, so a table needing more is a real
# finding rather than a quiet regression; ``test_polynomial_screen_slack``
# re-derives it.
_POLYNOMIAL_SCREEN_SLACK = 10


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

    Every construction here is :func:`_polynomial_hybrid` at some ``k``:
    ``k == n`` branches every bit and never reaches a machine (a plain
    decision tree, collapsing a constant subtable to its output), ``k == 0``
    hands the whole table to one machine, and the interior branches ``k``
    bits and gives each surviving residual its own machine.  The reduced
    variants prepend a drain for a leading run of ignored inputs and rebuild
    on the smaller table.

    The machine merges any two prefixes with the *same residual
    subfunction* rather than only constant ones -- an ordered BDD where the
    tree is a plain tree.  That merge is strictly stronger than the fold and
    the gap grows with ``n``: parity is the tree's worst case at every width
    (``2**n - 1`` internal nodes, 2298 instructions at n == 8) and needs just
    two states per level, so ``k == 0`` is *linear* there -- 13 instructions
    per input, 106 at n == 8.  Small or near-constant tables still favour the
    tree end.

    The interior is where neither endpoint serves: a table whose residuals
    merge *within* a top-level split but not *across* it defeats both, since
    the tree cannot merge them at all and the machine pays a full state level
    for the split.  ``00000101`` is 43 instructions at ``k == n`` and 39 at
    ``k == 0``, but 36 at ``k == 1``.  Against the two-construction dispatch
    this family shortens 36 of 256 tables at n == 3 (median 3.6%, best
    30.3%) and 3846 of 65536 at n == 4 (median 6.5%, best 39.8%), and grows
    none.

    **The order the tree tests its inputs in is not free here**, unlike
    every other decision-tree generator: a read *assigns* to the single
    register, so nothing survives it and the tested bit is always the one
    just read.  Every construction consumes input in stream order, so
    reordering is unreachable rather than merely unhelpful.  What the machine
    recovers is the *saving* a reorder would have bought -- the residual
    merge subsumes the folds a better order would have exposed.

    Selection is on *rendered characters* rather than instruction count,
    because the two disagree; the count screens which candidates are worth
    rendering.  See the dispatch below.

    A table needing more than ``_POLYNOMIAL_MAX_INSTRS`` instructions under
    both constructions raises :class:`ValueError`: the interpreter recovers
    instructions by factoring the polynomial, and that is what becomes
    impractical.  The bound is on instructions rather than on ``n``, but it
    is sized so every n == 10 table fits; a table that collapses to few
    states renders at any width beyond that.
    """
    n = _validate_truth_table(truth_table)

    # Every construction here is :func:`_polynomial_hybrid` at some ``k``.
    # ``k == n`` is the plain decision tree, ``k == 0`` the plain state
    # machine, and the interior splits the difference; the reduced variants
    # below prepend a drain and rebuild on a smaller table.
    builders: list[tuple[int, Any]] = [
        (
            _polynomial_hybrid_cost(truth_table, level),
            lambda level=level: _polynomial_hybrid(truth_table, level),
        )
        for level in range(n, -1, -1)
    ]

    # A table that ignores some of its inputs is a smaller table, and this
    # generator cannot get there on its own: a read *assigns* to the single
    # register, so the construction consumes inputs in stream order and an
    # ignored one still costs a full level of branching before reaching the
    # input that matters.  Folding collapses subtrees, not the levels above
    # them -- ``10101010`` costs 66 instructions where the one-input table
    # it really is costs 12.
    #
    # Reduction sidesteps that because it is *order-blind*: it rewrites the
    # table before anything is built.  The ignored inputs are drained first,
    # so every path still consumes exactly ``n`` inputs.  Only a *leading*
    # run can be handled this way -- an ignored input sitting after an
    # essential one would be drained out of turn and the build would branch
    # on the wrong bit (measured: 92 wrong rows over 26 tables).
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if lead:
        prefix: list[list[int]] = []
        for _ in range(lead):
            prefix.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
        reduced = read_at(truth_table, list(range(lead, n)), n)
        reduced_n = n - lead
        builders += [
            (
                len(prefix) + _polynomial_hybrid_cost(reduced, level),
                lambda level=level, r=reduced, pre=prefix: (
                    pre + _polynomial_hybrid(r, level)
                ),
            )
            for level in range(reduced_n, 0, -1)
        ]
        # The machine cannot take the ``-= 48`` drain above: its entry chain
        # tests for zero, so a drained 1 fell past every state test.  Its
        # own drain divides the bit away instead; see
        # :func:`_polynomial_drained_dag`.
        drained = _polynomial_drained_dag_cost(truth_table)
        # Only reached inside ``if lead:``, and the cost is None only when
        # there is no lead to drain, so it always answers here.
        if drained is not None:  # pragma: no branch
            builders.append((drained, lambda: _polynomial_drained_dag(truth_table)))

    fits = [(cost, build) for cost, build in builders if cost <= _POLYNOMIAL_MAX_INSTRS]
    if not fits:
        raise ValueError(
            "the Polynomial boolean generator emits one instruction per "
            f"prime and caps at {_POLYNOMIAL_MAX_INSTRS}, but this table "
            f"needs {min(cost for cost, _ in builders)} under its cheapest "
            "construction, which costs more per row than checking a table "
            "of this width can afford",
        )

    # Selection is on *rendered characters*, because instructions and
    # characters disagree: `01100000` and three relatives are 42
    # instructions against the tree's 43 and still render 11008 characters
    # against 9507, since a longer program's later instructions consume
    # larger primes.
    #
    # So the instruction count only screens: a candidate more than
    # ``_POLYNOMIAL_SCREEN_SLACK`` above the cheapest cannot win and is not
    # built.  That renders 604 of 1064 candidates over the n == 3 corpus,
    # which costs 2.54x there (0.3s across 256 programs) and 1.09x on an
    # n == 4 sample -- the arity where generation time actually lives.
    # The screen is a measured bound, not a proof: a candidate rendering
    # shorter from a further-out instruction count would be skipped.
    #
    # ``k`` descends so the tree is tried first, and the comparison is
    # strict, so a table nothing shortens emits what it always emitted.
    cheapest = min(cost for cost, _ in fits)
    program: str | None = None
    for cost, build in fits:
        if cost > cheapest + _POLYNOMIAL_SCREEN_SLACK:
            continue
        candidate = _polynomial_assemble(build())
        if program is None or len(candidate) < len(program):
            program = candidate
    if program is None:  # pragma: no cover - the cheapest member always fits
        raise AssertionError(
            "the Polynomial screen dropped every candidate, which the "
            "cheapest member cannot do",
        )
    return program


def _polynomial_assemble(instrs: list[list[int]]) -> str:
    """Expand an instruction list into its ``f(x) = ...`` polynomial.

    The k-th instruction takes the k-th prime ``p``: a complex instruction
    ``[a, b]`` contributes ``(x - a)**2 + p**(2*b)`` and a real one ``[v]``
    contributes ``x - p**v``, so the roots the interpreter factors back out
    are exactly the instructions.
    """
    from esolangs.tools._polynomial import primes, render_product

    factors: list[list[int]] = []
    for instr, p in zip(instrs, primes(len(instrs)), strict=True):
        if len(instr) == 2:
            a, b = instr
            factors.append([1, -2 * a, a * a + p ** (2 * b)])
        else:
            factors.append([1, -(p ** instr[0])])
    # The expansion is the whole cost past n == 7 -- the factor count is the
    # degree, and multiplying them in one incremental sweep rescans a
    # polynomial whose coefficients keep growing.  ``render_product`` cuts
    # the list into groups and merges them packed; see there.
    return str(render_product(factors))


def _polynomial_states(truth_table: str, n: int) -> list[list[str]]:
    """Return the distinct residual subfunctions at each level.

    Level ``k``'s states are the distinct subtables of width ``2**(n-k)``
    reachable after reading ``k`` bits.  Two prefixes that leave the same
    subtable are the *same* state and share one continuation -- the merge a
    decision tree cannot make, since it can only collapse a constant
    subtable.
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


def _polynomial_dag_cost(truth_table: str) -> int:
    """Return :func:`_polynomial_dag`'s instruction count without emitting it."""
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    index = [{state: i for i, state in enumerate(level)} for level in levels]
    total = 0
    for k in range(n):
        width = 2 ** (n - k - 1)
        states = levels[k]
        transitions = 0
        for state in states:
            zero = index[k + 1][state[:width]]
            one = index[k + 1][state[width:]]
            transitions += 1 if zero == one or one - zero == 1 else 2
        total += 5 * len(states) + transitions
    return total + 5 * len(levels[n]) - 1


def _polynomial_dag(truth_table: str) -> list[list[int]]:
    """Emit the state-machine instructions; see :func:`polynomial`.

    The register is the only storage and a read *assigns* to it, so nothing
    survives a read except the instruction cursor.  The state is therefore
    carried as *which branch is running*: each level is a chain of
    ``-= 1`` / ``if == 0`` tests over the live states, and the branch that
    fires reads its bit and moves to the child state's index.

    Two details are required.

    **``[0, b]`` is I/O, not arithmetic.**  The interpreter tests ``a == 0``
    before the opcode, so ``[0, 3]`` reads a character rather than
    multiplying by zero -- exactly the instruction a naive builder wants when
    both children merge.  That case instead reads and divides the bit away
    (``//= 50``), and an assertion below keeps any other ``a == 0`` from
    being emitted.

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
        # instruction computing a zero operand would silently become a read
        # -- a wrong program rather than a failure.  The builder never emits
        # one; this raises rather than asserting so the guard survives
        # ``-O``, where the trap it catches would be silent.
        if len(instr) == 2 and instr[0] == 0 and instr not in ([0, 1], [0, 2]):
            raise AssertionError(
                f"{instr} has a zero operand, which the interpreter reads as "
                "I/O rather than arithmetic",
            )
    return instrs


def _polynomial_hybrid(truth_table: str, k: int) -> list[list[int]]:
    """Emit ``k`` tree levels above a state machine per surviving residual.

    This is the whole construction family, not a third option beside two
    others.  ``k == n`` never reaches the machine and emits exactly what a
    plain decision tree emits; ``k == 0`` hands the whole table to one
    machine.  Between them the tree branches the top ``k`` bits and each
    surviving residual gets its own machine.

    The endpoints are worth having as one function because the interior is
    where the wins are.  The tree cannot merge two prefixes leaving the same
    residual; the machine pays for a level of states even where the table's
    top split is the only structure there is.  A table whose residuals merge
    *within* a top-level split but not *across* it is served by neither --
    ``00000101`` costs 43 instructions at ``k == n`` and 39 at ``k == 0``,
    but 36 at ``k == 1``.

    The splice has one requirement.  The machine's entry chain opens with
    ``if reg == 0`` on its first state, while a tree arm arrives holding the
    bit it branched on, so each arm normalizes to 0 first (``last`` is what
    it carries).  Inside a tree arm the register is then parked nonzero,
    exactly as a collapsed leaf parks it, so the enclosing ``else`` skips;
    at the top level there is no enclosing ``else``, so the park is dropped
    and ``k == 0`` is the machine itself.
    """
    n = _validate_truth_table(truth_table)
    instrs: list[list[int]] = []

    def emit_delta(delta: int) -> None:
        if delta > 0:
            instrs.append([delta, 1])
        elif delta < 0:
            instrs.append([-delta, 2])

    def build(rows: list[int], bit: int, last: int) -> None:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            emit_delta(_ASCII_ZERO + v - last)
            instrs.append([0, 1])  # output
            for _ in range(bit, n):
                instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
            emit_delta(1)
            return
        if bit == k:
            emit_delta(-last)  # the machine's chain tests for zero
            instrs.extend(_polynomial_dag("".join(truth_table[r] for r in rows)))
            if bit:  # inside a tree arm; the top level has no else to skip
                instrs.append([1, 1])
            return
        instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0
        build(g0, bit + 1, 0)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs


def _polynomial_drained_dag(truth_table: str) -> list[list[int]] | None:
    """Drain a leading run of ignored inputs, then run the machine.

    The reduction the tree gets above is available to the machine too, but
    only once the drain stops leaving a bit behind.  ``input; -= 48`` leaves
    0 or 1, and the machine's entry chain opens by testing for zero, so a
    drained ``1`` fell past every state test -- the combination answered
    correctly only while the drained bit was 0.  Draining with the
    ``//= 50`` pair the machine already uses for a merged child lands on 0
    either way, for the same two instructions per level.

    Returns ``None`` when no input is ignored, or when the reduction leaves
    a single row (a constant, which the tree already spells cheaply).
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if not lead:
        return None
    reduced = read_at(truth_table, list(range(lead, n)), n)
    # Exhausted over every table to four inputs: a nonzero lead leaves an
    # essential input behind, so the reduction always holds two rows.
    if len(reduced) < 2:  # pragma: no cover - see above
        return None
    instrs: list[list[int]] = []
    for _ in range(lead):
        instrs.extend([[0, 2], [_ASCII_ZERO + 2, 4]])  # input; //= 50 -> 0
    instrs.extend(_polynomial_dag(reduced))
    return instrs


def _polynomial_drained_dag_cost(truth_table: str) -> int | None:
    """Return :func:`_polynomial_drained_dag`'s instruction count."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if not lead:
        return None
    reduced = read_at(truth_table, list(range(lead, n)), n)
    # Exhausted over every table to four inputs: a nonzero lead leaves an
    # essential input behind, so the reduction always holds two rows.
    if len(reduced) < 2:  # pragma: no cover - see above
        return None
    return 2 * lead + _polynomial_dag_cost(reduced)


def _polynomial_hybrid_cost(truth_table: str, k: int) -> int:
    """Return :func:`_polynomial_hybrid`'s instruction count without emitting it.

    A deliberate mirror of the emitter above: the dispatch screens on this
    before rendering, so a drift between the two would screen out a table
    the emitter would have won.  ``test_polynomial_hybrid_cost_mirrors_build``
    asserts they agree over the whole ``n <= 3`` corpus.
    """
    n = _validate_truth_table(truth_table)

    def delta(value: int) -> int:
        return 1 if value else 0

    def cost(rows: list[int], bit: int, last: int) -> int:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            return delta(_ASCII_ZERO + v - last) + 1 + 2 * (n - bit) + delta(1)
        if bit == k:
            residual = "".join(truth_table[r] for r in rows)
            # The park is emitted only inside a tree arm; see the emitter.
            return delta(-last) + _polynomial_dag_cost(residual) + (1 if bit else 0)
        split = n - 1 - bit
        g1 = [r for r in rows if ((r >> split) & 1) == 1]
        g0 = [r for r in rows if ((r >> split) & 1) == 0]
        return 6 + cost(g1, bit + 1, 1) + cost(g0, bit + 1, 0)

    return cost(list(range(2**n)), 0, 0)


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
    halts) exactly on the 0 outputs and spins forever on the 1 outputs.  A
    constant table needs none of the sum and emits the template directly --
    all-0 a ``LET`` that always halts, all-1 the loop with a never-firing
    break -- but it still *reads* its ``n`` inputs first and discards them.
    A program whose input count depended on its truth table would leave the
    caller's remaining bits on the stream for whatever ran next; the reads
    are the interface, and only the body may shrink.
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
    # A table that ignores some of its inputs is a smaller table, and since
    # each selected row costs a ``LET`` per factor, dropping an input removes
    # rows and shortens the rows that remain.  The reads and the complements
    # stay at the full arity, as the constant branch above keeps them; an
    # ignored input is never named as a factor.  This is that branch
    # generalized from "no essential inputs" to "the ones that matter", and
    # the docstring's rule -- only the body may shrink -- makes it safe.
    def literal(i: int, negated: bool) -> str:  # noqa: FBT001 - a literal's sign, from minterm_literals
        return _pb_name(1 + n + i) if negated else _pb_name(1 + i)

    def product(factors: list[str]) -> str:
        lines.append(f"LET {_pb_name(2 + 2 * n)}:={factors[0]}")
        for factor in factors[1:]:
            lines.append(f"LET {_pb_name(2 + 2 * n)}:={_pb_name(2 + 2 * n)}*{factor}")
        return _pb_name(2 + 2 * n)

    def accumulate(row: str) -> None:
        lines.append(f"LET {_pb_name(1 + 2 * n)}:={_pb_name(1 + 2 * n)}+{row}")

    _used, _width, invert = minterm_sum(truth_table, literal, product, accumulate)
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
