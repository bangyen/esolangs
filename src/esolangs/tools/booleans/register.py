"""Boolean-function generators for register-based languages."""

from esolangs.tools.booleans.helpers import _maybe_complement, _validate_truth_table
from esolangs.tools.generators.helpers import _cm_constants

# Dig blocks for one level of the decision tree.
_DIG_BRANCH = ">2$~;#@"  # read a bit, store it, then turn on it
_DIG_CONTINUE = "> "  # a child of a branch: keep facing right into its own block
_DIG_LEAF = ">$3{}:@"  # set the mole to the result and print it


def decleq(truth_table: str, n: int) -> str:
    """Build a Decleq program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Decleq's only arithmetic is ``b = a - 1`` with a ``<= 0`` jump, so each
    input byte (48/49) is normalized to 1/2 by a 47-step decrement chain,
    which makes ``cell cell c`` a branch: a ``0`` bit (1) decrements to 0 and
    jumps to ``c``, a ``1`` bit (2) falls through.  The decision tree routes
    those branches to leaves that output 48 or 49 (placed in data cells of
    the self-modifying memory) and then halt.
    """
    _validate_truth_table(truth_table, n)

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


def collatz_multiverse(truth_table: str, n: int) -> str:
    """Build a Collatz Multiverse program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    A register holding 0 or 1 is always odd, so on such registers the Collatz
    rule is affine (``v`` becomes ``v*var2+var3``), which makes AND, NOT, and
    minterms buildable: ``t = src x + zero`` multiplies by a 0/1 ``src`` and
    ``t = negativeOne x + one`` complements.  Each ``1`` row of the table
    contributes its minterm (the AND of each bit's equality indicator); the
    OR is ``1 - prod (1 - minterm)``, and ``48 + result`` is printed.  The
    byte constants come from the text generator's constant table.
    """
    _validate_truth_table(truth_table, n)
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


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


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
    table, use_complement = _maybe_complement(truth_table, n)
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


def polynomial(truth_table: str, n: int) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
