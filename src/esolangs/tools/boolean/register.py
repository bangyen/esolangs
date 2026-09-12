r"""Boolean-function generators for register-based languages."""

from typing import Any

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _cm_constants,
    _validate_truth_table,
    best_input_order,
    essential_inputs,
    minterm_sum,
    read_at,
    stored_inputs,
)

# Dig blocks for one level of.
# from the digit beside it and.
# count sits to the *right* of.
# from the left: the count.
# arms, which is why three.
_DIG_BRANCH = "$3~;#"  # arm three, read a bit, store.
_DIG_ENTER = ">"  # the root's turn out of the.
_DIG_CONTINUE = ">"  # a child of a branch: keep.
_DIG_RETURN = "<"  # the same, for a child the.
_DIG_PRINT = "{}:@"  # set the mole to the result.
# ``$`` reads its repeat count.
# under one ``$`` is at most.
_DIG_SPAN = 9
# Columns one level owns.
# so the child's ``>`` sits.
# child's own block, and the.
_DIG_STRIDE = len(_DIG_BRANCH)
# A banded level leaves one.
# able to share columns at all:.
_DIG_BAND = _DIG_STRIDE + 1
# Cells a mole walking over.
# scenery while the underground.
# which is what lets a corridor.
_DIG_OPAQUE = "^>'<#$@"
# Cells that hold a digit where.
# one.
# executed path it *is* a digit.
_DIG_DIGITS = "0123456789;"
_DIG_STRIDE = len(_DIG_BRANCH)


def decleq(truth_table: str) -> str:
    r"""Build a Decleq program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    def constant(level: int, row: int) -> bool:
        r"""Whether every row this subtree covers agrees."""
        span = 2 ** (n - level)
        return len(set(truth_table[row : row + span])) == 1

    def tree_instrs(level: int, row: int) -> int:
        r"""Instructions the subtree at ``(level, row)`` emits."""
        if level == n or constant(level, row):
            return 2  # output, then halt.
        return (
            1
            + tree_instrs(level + 1, row + 2 ** (n - 1 - level))
            + tree_instrs(
                level + 1,
                row,
            )
        )

    # Every input is read to.
    # which the table depends need.
    # of every other branch.
    essential = set(essential_inputs(truth_table, n))
    # instructions: n reads, one.
    # and the tree, whose size.
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

    # The halt jump has to name an.
    # until the data cells below.
    # placeholder and the real.
    # complete, so the sentinel is.
    # tree came out.
    halts: list[int] = []

    def node(level: int, row: int) -> None:
        # The fold has to stop in.
        # it sized the data cells from.
        # and not there would leave.
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
    # One past the last cell: the.
    # leaves memory, so this is the.
    # .
    # Deriving it from the cell.
    # however big the program gets.
    # len(mem) - 2 and len(mem) - 1.
    # always exists, and the two.
    # a power of ten).
    # least *twice* the next width,.
    # so the sentinel widens the.
    # the way the old constant.
    for addr in halts:
        mem[addr] = len(mem)
    return " ".join(map(str, mem))


def addsubjump(truth_table: str) -> str:
    r"""Build an AddSubJump program computing the given truth table."""
    return best_input_order(truth_table, _addsubjump_ordered)


def _addsubjump_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit one input order's AddSubJump program; see :func:`addsubjump`."""
    n = _validate_truth_table(truth_table)

    instructions: list[list[Any]] = []
    next_cells: list[str | None] = []
    values: dict[str, int | tuple[str, int]] = {}
    # The operand names in the.
    # as they are emitted.
    # and used to recover it by.
    # instruction -- 3.5M.
    # the order search pays once.
    named: list[str] = []

    def emit(a: object, b: object, c: object, d: int) -> int:
        idx = len(instructions)
        next_cells.append(f"NEXT{idx}" if c == "next" else None)
        instructions.append([a, b, c, d])
        for v in (a, b, c):
            if isinstance(v, str) and v != "next":
                named.append(v)
        return idx

    emit(-9, -6, "next", -7)  # enable flag mode.
    values["C48"] = -_ASCII_ZERO
    values["U"] = 0
    values["D48"] = _ASCII_ZERO
    values["D49"] = _ASCII_ONE

    stored = stored_inputs(truth_table, perm)

    # The reads, in stream order.
    # write-only scratch: the.
    # not that every value is kept.
    if any(i not in stored for i in range(n)):
        values["DUMP"] = 0
    for i in range(n):
        if i not in stored:
            emit("DUMP", -1, "next", -7)  # read and discard.
            continue
        bit = f"B{i}"
        values[bit] = 0
        emit(bit, -1, "next", -7)  # B += input byte (48/49).
        emit(bit, "C48", "next", -7)  # B += -48.
        emit(bit, bit, "next", -7)  # double.
        emit(bit, bit, "next", -7)  # double -> {0, 4}.

    # Rows split most significant.
    # contiguous.
    # in two.
    # used to be: the list rebuilt.
    # candidate, for spans the.
    def build(level: int, lo: int, hi: int) -> None:
        if truth_table.count(truth_table[lo], lo, hi) == hi - lo:
            # Every read already happened.
            # and halts with nothing to.
            out = _ASCII_ZERO + int(truth_table[lo])
            emit(-1, f"D{out}", -8, -7)
            return
        half = (hi - lo) // 2
        if perm[level] not in stored:
            # A discarded input has no cell.
            # the answer, so both halves.
            # into the zero half, keeping.
            build(level + 1, lo, lo + half)
            return
        base = len(instructions)
        bit = f"B{perm[level]}"
        jump = f"J{base}"
        # Two instructions precede the.
        # at the zero trampoline two.
        values[jump] = ("t0", base + 2)
        emit(jump, bit, "next", -7)  # J += B, the hoisted bit this.
        emit("U", "U", jump, -7)  # goto *J.
        ztarget = f"Z{base}"
        otarget = f"O{base}"
        emit("U", "U", ztarget, -7)  # zero trampoline.
        emit("U", "U", otarget, -7)  # one trampoline.
        zstart = len(instructions)
        build(level + 1, lo, lo + half)
        ostart = len(instructions)
        build(level + 1, lo + half, hi)
        values[ztarget] = ("addr", zstart)
        values[otarget] = ("addr", ostart)

    build(0, 0, 2**n)

    base_data = 4 * len(instructions)
    # Insertion-ordered name ->.
    # list spelling scanned twice.
    # which is O(names) on a table.
    # calls and 2.4s of a 3.8s.
    # ``dict`` preserves insertion.
    # the same one the scan.
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
    r"""Build a Collatz Multiverse program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    if all(c == truth_table[0] for c in truth_table):
        # A constant table needs no.
        # interface: skipping them.
        # input stream and drop the.
        # read every input, discard it,.
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
    # Each selected row costs a.
    # chain, and a flip -- so a.
    # Inverting is free here: the.
    # complement drops it rather.
    # A table that ignores some of.
    # minterm costs an indicator.
    # and shortens the rows that.
    # (the reads are the.
    # indicator.
    # essential inputs" to "the.

    # ``literal`` allocates a.
    # it is called in the same.
    # literal of a row, then its.
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

    # ``acc`` holds prod(1 -.
    # the minterms were the table's.
    result = acc if invert else flip(acc)
    out = fresh()
    lines.append(f"{out} = negativeOne x + {result}, NOT PRINT.")
    lines.append(f"{out} = k1 x + k48, DO PRINT.")
    return "\n".join(lines)


def sophie(truth_table: str) -> str:
    r"""Build a Sophie program computing the given truth table."""
    _validate_truth_table(truth_table)
    return _sophie_hybrid(truth_table)


# : Accumulator values a Sophie.
# :.
# : A read leaves the.
# : are against ``48``/``49``.
# : with either would fire on.
# : else is reserved: the.
# : they can climb as high as.
_SOPHIE_RESERVED = frozenset({_ASCII_ZERO, _ASCII_ONE})


def sophie_labels(retained: list[list[str]]) -> list[dict[str, int]]:
    r"""Return one label per retained state, unique across all levels."""
    labels: list[dict[str, int]] = []
    number = 1
    for states in retained:
        level: dict[str, int] = {}
        for state in states:
            while number in _SOPHIE_RESERVED:
                number += 1
            level[state] = number
            number += 1
        labels.append(level)
    return labels


def _sophie_hybrid(truth_table: str) -> str:
    r"""Emit a Sophie tree that labels only shared residual states."""
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
    labels = sophie_labels(retained)

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


def _dig_leaf(reads: int, value: int, *, aligned: bool) -> str:
    r"""Build a leaf that consumes ``reads`` inputs, then prints ``value``."""
    out = ""
    if not aligned:
        while reads > _DIG_SPAN - 3:
            take = min(_DIG_SPAN - 1, reads - (_DIG_SPAN - 3))
            out += f"${take + 1}" + "~" * take
            reads -= take
        return out + f"${reads + 3}" + "~" * reads + _DIG_PRINT.format(value)
    while reads > _DIG_BAND - 1:
        take = _DIG_BAND - 2
        out += f"${take + 1}" + "~" * take
        reads -= take
    pad = 1 - reads % 2
    tail = "~" * reads + " " * pad + _DIG_PRINT.format(value)
    return out + f"${reads + pad + 3}" + tail


def _dig_columns(n: int, split: int | None) -> tuple[int, int]:
    r"""Where the two bands start, or the one band if ``split`` is ``None``."""
    if split is None:
        return 1, 0
    # The west band ends four.
    # ``#`` stands, which is the.
    # one stride further back is.
    return 1, _DIG_BAND * (n - split) + 3


def _dig_grid(truth_table: str, n: int, split: int | None) -> str:
    r"""Lay the decision tree out, in one band east or two that turn round."""
    total = 2 ** (n + 1) - 1
    east, west = _dig_columns(n, split)
    cells: dict[tuple[int, int], str] = {}
    corridors: list[tuple[int, int, int]] = []

    def leftward(level: int) -> bool:
        r"""Whether this level's block is entered facing west."""
        return split is not None and level >= split

    def dollar(level: int) -> int:
        r"""Return the column of this level's ``$``, the cell the mole meets."""
        if split is None:
            return east + _DIG_STRIDE * level
        if level < split:
            return east + _DIG_BAND * level
        return west + 4 - _DIG_BAND * (level - split)

    def place(row: int, col: int, text: str) -> None:
        r"""Write ``text`` along ``row`` from ``col``, refusing an occupied."""
        for i, char in enumerate(text):
            if col + i < 0:
                raise AssertionError(f"cell off the left edge at row {row}")
            if (row, col + i) in cells:
                raise AssertionError(f"two cells at {(row, col + i)}")
            cells[row, col + i] = char

    def block(row: int, level: int, text: str) -> None:
        r"""Write a block so the mole meets its first cell first."""
        col = dollar(level)
        if leftward(level):
            place(row, col - len(text) + 1, text[::-1])
        else:
            place(row, col, text)

    def walk(row: int, level: int, lo: int, hi: int) -> None:
        r"""Lay the subtree for ``truth_table[lo:hi]`` at ``row``."""
        if level == n or len(set(truth_table[lo:hi])) == 1:
            # A constant slice cannot be.
            # this is a leaf and every row.
            # still reads what it did not.
            # count depended on its table.
            # several programs from one.
            reads = n - level
            block(
                row,
                level,
                _dig_leaf(reads, int(truth_table[lo]), aligned=split is not None),
            )
            return
        block(row, level, _DIG_BRANCH)
        col = dollar(level)
        hop = col - 4 if leftward(level) else col + 4
        step = 2 ** (n - level - 1)
        half = (hi - lo) // 2
        # ``#`` rotates one way on a 0.
        # is up and which is down.
        # sends an eastbound mole down.
        one, zero = (
            (row - step, row + step) if leftward(level) else (row + step, row - step)
        )
        for child, bounds in (
            (one, (lo + half, hi)),
            (zero, (lo, lo + half)),
        ):
            # the mole arrives here.
            # is the cell right before the.
            # goes in that column, pointing.
            place(child, hop, _DIG_RETURN if leftward(level + 1) else _DIG_CONTINUE)
            corridors.append((hop, row, child))
            walk(child, level + 1, *bounds)

    # The mole starts at (0, 0).
    # down column 0 and this is the.
    place(total // 2, east - 1, _DIG_ENTER)
    walk(total // 2, 0, 0, 2**n)
    _dig_clear(cells, corridors)

    if (0, 0) in cells:
        raise AssertionError("the start marker's cell is taken")
    cells[0, 0] = "'"
    span = max(col for _, col in cells) + 1
    grid = [[" "] * span for _ in range(total)]
    for (row, col), char in cells.items():
        grid[row][col] = char
    # Rows are painted into a.
    # past the last command on a.
    # trimmed rather than committed.
    return "\n".join("".join(row).rstrip() for row in grid)


def _dig_clear(
    cells: dict[tuple[int, int], str],
    corridors: list[tuple[int, int, int]],
) -> None:
    r"""Refuse a grid whose moles would be stopped on their way."""
    for col, start, end in corridors:
        low, high = sorted((start, end))
        for row in range(low + 1, high):
            char = cells.get((row, col))
            if char is not None and char in _DIG_OPAQUE:
                raise AssertionError(
                    f"mole from row {start} meets {char!r} at {(row, col)}"
                )
    for (row, col), char in cells.items():
        if char not in "$#":
            continue
        for step in (-1, 1):
            above = cells.get((row + step, col))
            if above is not None and above in _DIG_DIGITS:
                raise AssertionError(f"{char!r} at {(row, col)} reads {above!r} first")


def dig(truth_table: str, width: int | None = None) -> str:
    r"""Build a Dig program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    flat = _dig_grid(truth_table, n, None)
    if width is None or n < 2:
        return flat
    if max(len(line) for line in flat.split("\n")) <= width:
        return flat
    # The turn has to leave the.
    # the eastbound one starts its.
    # split rather than any search:.
    banded = _dig_grid(truth_table, n, -(-(n + 2) // 2))
    if max(len(line) for line in banded.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return banded
    return flat


def _qoibl_enc(n: int) -> str:
    r"""Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


def qoibl(truth_table: str) -> str:
    r"""Build a Qoibl program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    # A table that ignores some of.
    # minterm costs one ``qe``.
    # selected row, dropping an.
    # remain.
    # complement (they are the.
    # factor.
    # program and the minterm body.
    # here is reachable -- unlike.
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


# Largest instruction count.
# consumes a fresh prime and.
# -- and the cost of recovering.
# and nothing else.
# .
# The bound is the analytic.
# the state machine holds at.
# instructions each (5 fixed.
# 5 each less the final endif.
# table builds.
# it.
# refused.
# .
# The policy is still "admit.
# cost curve that moved twice.
# (~10s at the bound); the.
# Two interpreter changes moved.
# rows of one table share a.
# ``_NTT_MIN_DEGREE`` peel.
# enumeration and GF factoring.
# table verified against every.
# 256 rows where the old path.
# for all 1024 rows, 43.7s of.
# .
# The count, not the arity, is.
# collapses to few states is.
# past n == 10 inside the bound.
# .
# What the bound declines is.
# (2910 instructions) builds.
# 264.5s of that the single.
# 123609143-character program.
# 56s), 1.78x the instructions.
# price -- and 2910 is only the.
# n == 11 gives 3726, so even a.
# partial.
_POLYNOMIAL_MAX_INSTRS = 1934

# How far above the cheapest.
# is on characters, so the.
# screen picks wrong, because.
# the drained.
# machine is 30 instructions.
# ``k == 2`` build is 32 and.
# instructions consume larger.
# .
# The slack has to be measured.
# n <= 3 needs at most 6 (242.
# n == 4 reach 9, and 32 of.
# smaller corpus silently emits.
# n == 4 worst case with a.
# finding rather than a quiet.
# re-derives it.
_POLYNOMIAL_SCREEN_SLACK = 10


def polynomial(truth_table: str) -> str:
    r"""Build a Polynomial program computing the given truth table."""
    n = _validate_truth_table(truth_table)

    # Every construction here is.
    # ``k == n`` is the plain.
    # machine, and the interior.
    # below prepend a drain and.
    builders: list[tuple[int, Any]] = [
        (
            _polynomial_hybrid_cost(truth_table, level),
            lambda level=level: _polynomial_hybrid(truth_table, level),
        )
        for level in range(n, -1, -1)
    ]

    # A table that ignores some of.
    # generator cannot get there on.
    # register, so the construction.
    # ignored one still costs a.
    # input that matters.
    # them -- ``10101010`` costs 66.
    # it really is costs 12.
    # .
    # Reduction sidesteps that.
    # table before anything is.
    # so every path still consumes.
    # run can be handled this way.
    # essential one would be.
    # on the wrong bit (measured:.
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if lead:
        prefix: list[list[int]] = []
        for _ in range(lead):
            prefix.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48.
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
        # The machine cannot take the.
        # tests for zero, so a drained.
        # own drain divides the bit.
        # :func:`_polynomial_drained_dag.
        drained = _polynomial_drained_dag_cost(truth_table)
        # Only reached inside ``if.
        # there is no lead to drain, so.
        if drained is not None:  # pragma: no branch
            builders.append((drained, lambda: _polynomial_drained_dag(truth_table)))

    fits = [(cost, build) for cost, build in builders if cost <= _POLYNOMIAL_MAX_INSTRS]
    if not fits:
        raise GeneratorCapError(
            "the Polynomial boolean generator emits one instruction per "
            f"prime and caps at {_POLYNOMIAL_MAX_INSTRS}, but this table "
            f"needs {min(cost for cost, _ in builders)} under its cheapest "
            "construction, which costs more per row than checking a table "
            "of this width can afford",
        )

    # Selection is on *rendered.
    # characters disagree:.
    # instructions against the.
    # against 9507, since a longer.
    # larger primes.
    # .
    # So the instruction count only.
    # ``_POLYNOMIAL_SCREEN_SLACK``.
    # built.
    # which costs 2.54x there (0.3s.
    # n == 4 sample -- the arity.
    # The screen is a measured.
    # shorter from a further-out.
    # .
    # ``k`` descends so the tree is.
    # strict, so a table nothing.
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
    r"""Expand an instruction list into its ``f(x) = ...`` polynomial."""
    from esolangs.tools._polynomial import primes, render_product

    factors: list[list[int]] = []
    for instr, p in zip(instrs, primes(len(instrs)), strict=True):
        if len(instr) == 2:
            a, b = instr
            factors.append([1, -2 * a, a * a + p ** (2 * b)])
        else:
            factors.append([1, -(p ** instr[0])])
    # The expansion is the whole.
    # degree, and multiplying them.
    # polynomial whose coefficients.
    # the list into groups and.
    return str(render_product(factors))


def _polynomial_states(truth_table: str, n: int) -> list[list[str]]:
    r"""Return the distinct residual subfunctions at each level."""
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
    r"""Return :func:`_polynomial_dag`'s instruction count without emitting."""
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
    r"""Emit the state-machine instructions; see :func:`polynomial`."""
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    index = [{s: i for i, s in enumerate(level)} for level in levels]
    # Keeps a taken branch's.
    # chain.
    offset = max(len(level) for level in levels) + 1
    instrs: list[list[int]] = []

    for k in range(n):
        width = 2 ** (n - k - 1)
        states = levels[k]
        for i, state in enumerate(states):
            if i:
                instrs.append([1, 2])  # -= 1.
            instrs.append([4])  # if reg == 0.
            remaining = len(states) - 1 - i
            zero_index = index[k + 1][state[:width]]
            one_index = index[k + 1][state[width:]]
            zero_target = offset + zero_index + remaining
            instrs.append([0, 2])  # input.
            if zero_index == one_index:
                # Both children merge, so this.
                # Divide it away rather than.
                # interpreter would read as an.
                instrs.append([_ASCII_ZERO + 2, 4])  # //= 50 -> 0.
            else:
                instrs.append([_ASCII_ZERO, 2])  # -= 48, leaving 0 or 1.
                span = one_index - zero_index
                if span != 1:
                    instrs.append([span, 3])  # *= span, never zero here.
            instrs.append([zero_target, 1])  # += the child's parked value.
            instrs.append([2])  # endif.
        instrs.append([offset, 2])  # -= offset, recovering the.

    # The leaf states are one-wide.
    # guard is needed after.
    # one decrement a two-state.
    for i, state in enumerate(levels[n]):
        if i:
            instrs.append([1, 2])  # -= 1.
        instrs.append([4])  # if reg == 0.
        instrs.append([_ASCII_ZERO + int(state), 1])
        instrs.append([0, 1])  # output.
        instrs.append([2])  # endif.

    for instr in instrs:
        # ``a == 0`` is how the.
        # instruction computing a zero.
        # -- a wrong program rather.
        # one; this raises rather than.
        # ``-O``, where the trap it.
        if len(instr) == 2 and instr[0] == 0 and instr not in ([0, 1], [0, 2]):
            raise AssertionError(
                f"{instr} has a zero operand, which the interpreter reads as "
                "I/O rather than arithmetic",
            )
    return instrs


def _polynomial_hybrid(truth_table: str, k: int) -> list[list[int]]:
    r"""Emit ``k`` tree levels above a state machine per surviving residual."""
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
            instrs.append([0, 1])  # output.
            for _ in range(bit, n):
                instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48.
            emit_delta(1)
            return
        if bit == k:
            emit_delta(-last)  # the machine's chain tests for.
            instrs.extend(_polynomial_dag("".join(truth_table[r] for r in rows)))
            if bit:  # inside a tree arm; the top.
                instrs.append([1, 1])
            return
        instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48.
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0.
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0.
        build(g0, bit + 1, 0)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs


def _polynomial_drained_dag(truth_table: str) -> list[list[int]] | None:
    r"""Drain a leading run of ignored inputs, then run the machine."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if not lead:
        return None
    reduced = read_at(truth_table, list(range(lead, n)), n)
    # Exhausted over every table to.
    # essential input behind, so.
    if len(reduced) < 2:  # pragma: no cover - see above
        return None
    instrs: list[list[int]] = []
    for _ in range(lead):
        instrs.extend([[0, 2], [_ASCII_ZERO + 2, 4]])  # input; //= 50 -> 0.
    instrs.extend(_polynomial_dag(reduced))
    return instrs


def _polynomial_drained_dag_cost(truth_table: str) -> int | None:
    r"""Return :func:`_polynomial_drained_dag`'s instruction count."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if not lead:
        return None
    reduced = read_at(truth_table, list(range(lead, n)), n)
    # Exhausted over every table to.
    # essential input behind, so.
    if len(reduced) < 2:  # pragma: no cover - see above
        return None
    return 2 * lead + _polynomial_dag_cost(reduced)


def _polynomial_hybrid_cost(truth_table: str, k: int) -> int:
    r"""Return :func:`_polynomial_hybrid`'s instruction count without."""
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
            # The park is emitted only.
            return delta(-last) + _polynomial_dag_cost(residual) + (1 if bit else 0)
        split = n - 1 - bit
        g1 = [r for r in rows if ((r >> split) & 1) == 1]
        g0 = [r for r in rows if ((r >> split) & 1) == 0]
        return 6 + cost(g1, bit + 1, 1) + cost(g0, bit + 1, 0)

    return cost(list(range(2**n)), 0, 0)


def _pb_name(index: int) -> str:
    r"""Build the ``index``-th lowercase variable name (a, b, ..., z, aa,."""
    name = ""
    index += 1
    while index > 0:
        index -= 1
        name = chr(ord("a") + index % 26) + name
        index //= 26
    return name


def point_break(truth_table: str) -> str:
    r"""Build a Point Break program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    # The reads a constant table.
    # and the names are the ones.
    # nothing else about the.
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

    # Each selected row costs a.
    # a table with more ones than.
    # rows.
    # loop guard, so a complemented.
    # A table that ignores some of.
    # each selected row costs a.
    # rows and shortens the rows.
    # stay at the full arity, as.
    # ignored input is never named.
    # generalized from "no.
    # the docstring's rule -- only.
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
    # ``g`` is the loop guard,.
    # complement of the answer, and.
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
