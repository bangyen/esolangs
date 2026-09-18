"""Boolean-function generator for Fargo.

``@ i`` returns the ``i``th bit of the input number, so no routing is
needed and the construction is the **algebraic normal form**
``f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...``,
coefficients from the Möbius transform (:func:`_anf_coefficients`).
The emitter factors each variable as ``p = p0 ^ (x & p1)``, so every
coefficient appears at most once and a dense ANF is O(T).

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
    result = combine(terms, "^")
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


def fargo(truth_table: str, width: int | None = None) -> str:
    """Build a Fargo program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Emits the ANF (see the module
    docstring); a constant table emits ``% 0 0`` or ``% 0 1``, sound because
    the interpreter consumes the input line either way.
    """
    n = _validate_truth_table(truth_table)
    coeffs = _anf_coefficients(truth_table)
    expression = _anf_expression(coeffs, n)
    compact = f"% 0 {expression}\n$\n"
    if width is None or max(map(len, compact.splitlines())) <= width:
        return compact
    masks = [mask for mask in range(1 << n) if coeffs[mask] and mask]
    return _factored(masks, coeffs[0], n)
