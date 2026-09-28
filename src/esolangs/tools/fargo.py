"""Boolean-function generator for Fargo.

``@ i`` returns the ``i``th bit of the input number, so no routing is
needed and the construction is the **algebraic normal form**
``f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...``,
coefficients from the Möbius transform (:func:`_anf_coefficients`).
The emitter factors each variable as ``p = p0 ^ (x & p1)``, so every
coefficient appears at most once and a dense ANF is O(T).  A second emitter
picks each node's arm locally (:func:`_arm_expression`); the shorter wins.

The program is ``% 0 <expression>`` then ``$``, writing exactly ``0`` or
``1``; a constant table emits the literal.  The harness feeds one line
holding ``int(bits, 2)``, so input ``i`` (most-significant-first) is bit
``n - 1 - i`` of that number -- the only place the mapping appears.  The
interpreter reads that line before execution, so every program consumes
exactly one input line.  Input reordering does not apply.
"""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["fargo"]


def _anf_coefficients(truth_table: str) -> list[int]:
    """Return the table's algebraic normal form coefficients.

    Möbius transform in place, one input at a time: ``n * 2**n`` rather
    than ``3**n``.  That Theta(T log T) is the construction's own cost (a
    pass per input), the one log factor the generator keeps.  Masks use the
    table's most-significant-first indexing; the caller converts to Fargo's
    LSB-first ``@`` once.
    """
    n = _validate_truth_table(truth_table)
    coeffs = [int(bit) for bit in truth_table]
    step = 1
    for _ in range(n):
        for start in range(0, 1 << n, step * 2):
            for offset in range(start, start + step):
                coeffs[offset + step] ^= coeffs[offset]
        step *= 2
    return coeffs


def _term(mask: int, n: int) -> str:
    """Return the AND-product of the inputs ``mask`` selects.

    Input ``i`` reads ``@ <n - 1 - i>`` in binary; ``k`` inputs need
    ``k - 1`` leading ``&``.
    """
    reads = [f"@ {(n - 1 - i):b}" for i in range(n) if mask >> (n - 1 - i) & 1]
    return "& " * (len(reads) - 1) + " ".join(reads)


def _name(index: int) -> str:
    """Return a short lowercase Fargo definition name."""
    out = ""
    while True:
        index, digit = divmod(index, 26)
        out = chr(ord("a") + digit) + out
        if not index:
            return out
        index -= 1


def _factored(masks: list[int], constant: int, n: int) -> str:
    """Return the ANF as short nullary definitions and one output call."""
    lines: list[str] = []

    def define(expression: str) -> str:
        name = _name(len(lines))
        lines.append(f"{name} {expression}")
        return name

    used = {i for mask in masks for i in range(n) if mask >> i & 1}
    reads = {i: define(f"@ {i:b}") for i in sorted(used)}

    def combine(parts: list[str], op: str) -> str:
        while len(parts) > 1:
            joined: list[str] = []
            for i in range(0, len(parts) - 1, 2):
                joined.append(define(f"{op} {parts[i]} {parts[i + 1]}"))
            if len(parts) % 2:
                joined.append(parts[-1])
            parts = joined
        return parts[0]

    terms = [
        combine(
            [reads[i] for i in range(n) if mask >> i & 1],
            "&",
        )
        for mask in masks
    ]
    if constant:
        terms.insert(0, "1")
    # The all-zero table has no terms and no constant, so ``combine`` would
    # index an empty list.  It is the constant program, same as the compact
    # path; only the width check sent it here.
    result = combine(terms, "^") if terms else "0"
    return "\n".join([*lines, f"% 0 {result}", "$", ""])


def _anf_expression(coeffs: list[int], n: int) -> str:
    """Return a recursively factored ANF expression in O(T) emitted size.

    Emitted into one flat piece list, O(T) time: whether a half is empty,
    or is the lone ``1`` (its only coefficient at its start), is read off
    the prefix counts before descending, so no subtree string is rebuilt
    per level.
    """
    nonzero = [0]
    for coefficient in coeffs:
        nonzero.append(nonzero[-1] + coefficient)
    pieces: list[str] = []

    def build(start: int, size: int, bit: int) -> None:
        """Emit the span, which is known to hold a nonzero coefficient."""
        if size == 1:
            pieces.append("1")
            return
        half = size // 2
        if nonzero[start + half] == nonzero[start + size]:
            build(start, half, bit - 1)
            return
        if nonzero[start] != nonzero[start + half]:
            pieces.append("^ ")
            build(start, half, bit - 1)
            pieces.append(" ")
        if nonzero[start + size] - nonzero[start + half] == 1 and coeffs[start + half]:
            pieces.append(f"@ {bit:b}")
        else:
            pieces.append(f"& @ {bit:b} ")
            build(start + half, half, bit - 1)

    if nonzero[-1] == 0:
        return "0"
    build(0, 1 << n, n - 1)
    return "".join(pieces)


def _arm_expression(truth_table: str, coeffs: list[int], n: int) -> str:
    """Return the factored expression with each node's arms chosen locally.

    The positive split ``f0 ^ (x & d)``, ``d = f0 ^ f1``, is why polarity
    matters: ``not x & g`` has ``d = f0 = g``, emitted twice at every level.
    A node here takes one of four splits, the complement ``^ 1 @ b`` costing
    four characters: ``f0 ^ (x & d)``, ``f1 ^ (not x & d)``, ``f0 | (x & f1)``
    when ``f0 <= f1``, and ``f1 | (not x & f0)`` when ``f1 <= f0``.

    The rule reads only the node's function: a zero 1-arm takes the negated
    split, a constant-one 1-arm ``f0 | x``, and otherwise the split whose
    children hold the fewest ANF terms wins, ties to no complement, then in
    that order.  ``f0`` and ``d`` hold the low and high coefficient halves
    and ``f1`` their xor, so a level costs O(T), like a transform pass.
    """
    pieces: list[str] = []

    def build(table: list[int], anf: list[int], bit: int) -> None:
        """Emit ``table`` (``anf`` its coefficients), known nonconstant."""
        half = len(table) // 2
        low, high = anf[:half], anf[half:]
        while not any(high):
            # The top input is inessential: descend into the 0-arm alone.
            table, anf, bit = table[:half], low, bit - 1
            half //= 2
            low, high = anf[:half], anf[half:]
        f0, f1 = table[:half], table[half:]
        one = [x ^ y for x, y in zip(low, high, strict=True)]
        w0, wd, w1 = sum(low), sum(high), sum(one)
        if not w1:
            choice = 1
        elif w1 == 1 and one[0] and w0:
            choice = 2
        else:
            # (terms, complemented, order): the positive split wins ties.
            options = [(w0 + wd, 0, 0), (w1 + wd, 1, 1)]
            if w0 and all(x <= y for x, y in zip(f0, f1, strict=True)):
                options.append((w0 + w1, 0, 2))
            if all(y <= x for x, y in zip(f0, f1, strict=True)):
                options.append((w0 + w1, 1, 3))
            choice = min(options)[2]
        d = [x ^ y for x, y in zip(f0, f1, strict=True)]
        # Each split's kept arm, its operator, and the literal's operand.
        kept, kept_anf, op, operand, operand_anf = (
            (f0, low, "^", d, high),
            (f1, one, "^", d, high),
            (f0, low, "|", f1, one),
            (f1, one, "|", f0, low),
        )[choice]
        literal = f"^ 1 @ {bit:b}" if choice % 2 else f"@ {bit:b}"
        if any(kept_anf):
            pieces.append(f"{op} ")
            leaf(kept, kept_anf, bit - 1)
            pieces.append(" ")
        if sum(operand_anf) == 1 and operand_anf[0]:
            pieces.append(literal)
        else:
            pieces.append(f"& {literal} ")
            leaf(operand, operand_anf, bit - 1)

    def leaf(table: list[int], anf: list[int], bit: int) -> None:
        """Emit ``table``, which is not constant zero."""
        if sum(anf) == 1 and anf[0]:
            pieces.append("1")
        else:
            build(table, anf, bit)

    if not any(coeffs):
        return "0"
    leaf([int(bit) for bit in truth_table], coeffs, n - 1)
    return "".join(pieces)


def fargo(truth_table: str, width: int | None = None) -> str:
    """Build a Fargo program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Emits the ANF (see the module
    docstring); a constant table emits ``% 0 0`` or ``% 0 1``, sound because
    the interpreter consumes the input line either way.
    """
    n = _validate_truth_table(truth_table)
    coeffs = _anf_coefficients(truth_table)
    # Two candidates, both O(T): the chosen arms are shorter on nearly every
    # table, and the positive factoring keeps the few it loses from growing.
    expression = min(
        _arm_expression(truth_table, coeffs, n),
        _anf_expression(coeffs, n),
        key=len,
    )
    compact = f"% 0 {expression}\n$\n"
    if width is None or max(map(len, compact.splitlines())) <= width:
        return compact
    masks = [mask for mask in range(1 << n) if coeffs[mask] and mask]
    return _factored(masks, coeffs[0], n)
