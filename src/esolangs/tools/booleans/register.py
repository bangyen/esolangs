"""Boolean-function generators for register-based languages."""

# Dig blocks for one level of the decision tree.
_DIG_BRANCH = ">2$~;#@"  # read a bit, store it, then turn on it
_DIG_CONTINUE = "> "  # a child of a branch: keep facing right into its own block
_DIG_LEAF = ">$3{}:@"  # set the mole to the result and print it


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
    use_complement = truth_table.count("1") > 2**n // 2
    table = (
        truth_table
        if not use_complement
        else "".join("1" if c == "0" else "0" for c in truth_table)
    )
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
    ``f(x) = ...``.  Each instruction consumes a fresh prime, so the
    coefficients of a deeper tree grow quickly -- at ``n == 3`` they reach
    ~10**360 and at ``n == 4`` ~10**729.  The interpreter recovers roots by
    factoring the integer polynomial (exact, so the huge coefficients are no
    obstacle); ``n == 3`` is verified to run in ~1s and ``n == 4`` in ~10s.
    ``n > 4`` is rejected to keep the boolean tests tractable.
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
        if len(rows) == 1:
            v = int(truth_table[rows[0]])
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
