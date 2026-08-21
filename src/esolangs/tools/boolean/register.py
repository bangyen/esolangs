"""Boolean-function generators for register-based languages."""

from typing import Any

from esolangs.tools.boolean.helpers import _maybe_complement, _validate_truth_table
from esolangs.tools.text.helpers import _cm_constants

# Dig blocks for one level of the decision tree.
_DIG_BRANCH = ">2$~;#@"  # read a bit, store it, then turn on it
_DIG_CONTINUE = "> "  # a child of a branch: keep facing right into its own block
_DIG_LEAF = ">$3{}:@"  # set the mole to the result and print it


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
    """
    n = _validate_truth_table(truth_table)

    # instructions: n reads, n*47 normalizations, and the tree
    # (2**n - 1 branches plus 2**n leaves of output+halt each).
    n_instr = n + 47 * n + 3 * 2**n - 1
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

    def node(level: int, row: int) -> None:
        if level == n:
            emit(-2, out49 if truth_table[row] == "1" else out48, 0)
            emit(0, 0, 10**9)
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
    mem[out48] = 48
    mem[out49] = 49
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
    values["C48"] = -48
    values["U"] = 0
    values["D48"] = 48
    values["D49"] = 49

    def build(level: int, rows: list[int]) -> None:
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            out = 48 if results.pop() == "0" else 49
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
    ``t = negativeOne x + one`` complements.  Each ``1`` row of the table
    contributes its minterm (the AND of each bit's equality indicator); the
    OR is ``1 - prod (1 - minterm)``, and ``48 + result`` is printed.  The
    byte constants come from the text generator's constant table.
    """
    n = _validate_truth_table(truth_table)
    if all(c == "0" for c in truth_table):
        return "\n".join([*_cm_constants({48}), "out = negativeOne x + k48, DO PRINT."])
    if all(c == "1" for c in truth_table):
        return "\n".join([*_cm_constants({49}), "out = negativeOne x + k49, DO PRINT."])

    lines = _cm_constants({48})
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
    for k in range(2**n):
        if truth_table[k] == "0":
            continue
        indicators = []
        for i in range(n):
            if (k >> (n - 1 - i)) & 1:
                reg = fresh()
                lines.append(f"{reg} = negativeOne x + b{i}, NOT PRINT.")
                indicators.append(reg)
            else:
                indicators.append(flip(f"b{i}"))
        minterm = indicators[0]
        for indicator in indicators[1:]:
            minterm = and_bits(minterm, indicator)
        complement = flip(minterm)
        nacc = fresh()
        lines.append(f"{nacc} = negativeOne x + {acc}, NOT PRINT.")
        lines.append(f"{nacc} = {complement} x + zero, NOT PRINT.")
        acc = nacc

    result = flip(acc)
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
        if depth == n:
            row = 0
            for bit in path:
                row = row * 2 + bit
            return f"#${48 + int(truth_table[row])},&"
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
    """
    n = _validate_truth_table(truth_table)
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

    # Row 0 is always written first (as the tree's root branch, or -- for
    # n == 0 -- its sole leaf), and both block kinds start with '>'; swap
    # that one cell for the mole's actual start marker rather than
    # special-casing row 0's emission in two different places above.
    lines[0] = "'" + lines[0][1:]
    return "\n".join(lines)


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
        lines.append(f"we {_qoibl_enc(i)} we et ry ey ry {_qoibl_enc(48)} we")
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
        for i in range(n):
            var = i if ((k >> (n - 1 - i)) & 1) else n + i
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
        lines.append(f"tt {_qoibl_enc(49)} ry ey ry qe {_qoibl_enc(2 * n)} qe tt")
    else:
        lines.append(f"tt qe {_qoibl_enc(2 * n)} qe ry ee ry {_qoibl_enc(48)} tt")
    return "\n".join(lines)


def polynomial(truth_table: str) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Polynomial programs are polynomials whose roots encode instructions, so
    the generator builds a decision tree of complex ``[a, b]`` (arithmetic,
    input, output) and real ``[val]`` (if/endif) roots and expands them into
    ``f(x) = ...``.  A subtree whose rows are all the same value is collapsed
    to its single output, so constant and near-constant tables skip the tree
    that would otherwise isolate every leaf.  Each instruction consumes a
    fresh prime, so the coefficients of a deeper tree grow quickly -- at
    ``n == 3`` they reach ~10**360 and at ``n == 4`` ~10**729.  The
    interpreter recovers roots by factoring the integer polynomial (exact,
    so the huge coefficients are no obstacle); ``n == 3`` runs in ~1s and
    ``n == 4`` in ~10s, while ``n == 5`` (degree 376, coefficients ~10**1746)
    does not factor in practical time.  ``n > 4`` is rejected.
    """
    n = _validate_truth_table(truth_table)
    if n > 4:
        raise ValueError(
            "the Polynomial boolean generator supports n <= 4: "
            "each instruction consumes a fresh prime, so a deeper tree's "
            "coefficients make the factorization impractically slow",
        )

    from esolangs.tools._polynomial import format_coeffs, multiply, primes

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
    on.  The result ``f`` feeds a fixed template -- ``LET g:=one-f`` then
    ``POINT loop`` / ``IF g BREAK loop`` / ``END loop`` -- where ``g`` is
    nonzero exactly when ``f`` is 0, so the loop breaks (and the program
    halts) exactly on the 0 outputs and spins forever on the 1 outputs.
    The constant tables skip the reads: all-0 emits a single no-op ``LET``
    (always halts) and all-1 emits the loop with a never-firing break.
    """
    n = _validate_truth_table(truth_table)
    if all(c == "0" for c in truth_table):
        return f"LET {_pb_name(0)}:=1"
    if all(c == "1" for c in truth_table):
        return "\n".join(
            [
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
    for k in range(2**n):
        if truth_table[k] == "0":
            continue
        factors = [
            _pb_name(1 + n + i) if not ((k >> (n - 1 - i)) & 1) else _pb_name(1 + i)
            for i in range(n)
        ]
        lines.append(f"LET {_pb_name(2 + 2 * n)}:={factors[0]}")
        for factor in factors[1:]:
            lines.append(f"LET {_pb_name(2 + 2 * n)}:={_pb_name(2 + 2 * n)}*{factor}")
        lines.append(
            f"LET {_pb_name(1 + 2 * n)}:={_pb_name(1 + 2 * n)}+{_pb_name(2 + 2 * n)}"
        )
    lines.append(f"LET {_pb_name(3 + 2 * n)}:={_pb_name(0)}-{_pb_name(1 + 2 * n)}")
    lines.extend(
        [
            "POINT loop",
            f"IF {_pb_name(3 + 2 * n)} BREAK loop",
            "END loop",
        ]
    )
    return "\n".join(lines)
