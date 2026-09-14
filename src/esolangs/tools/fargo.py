"""Boolean-function generator for Fargo.

Fargo is the one language in the suite whose *input interface* is already a
truth table's index: ``@ i`` returns the ``i``th bit of the input number, so
the generator never has to read, normalize and store bits before it can test
them.  What every other generator spends on routing -- a decision tree, a
minterm sum, a grid walk -- Fargo spends on nothing at all.

That makes an **algebraic normal form** the natural construction rather than
a decision tree. Every boolean function has exactly one ANF::

    f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...

The coefficients come from the Möbius transform
(:func:`_anf_coefficients`). The emitter recursively factors each variable:
``p = p0 ^ (x & p1)``. Thus every coefficient and factor appears at most
once, keeping even a dense ANF O(T) for a T-entry table. Variables with wide
binary indices occur near the root; the heavily repeated deep variables have
the shortest indices.

The emitted program is two lines::

    % 0 <expression>
    $

setting bit 0 of the output number to the function's value and printing the
output number, so the program writes exactly ``0`` or ``1``.  A constant
table needs no expression at all and emits the literal.

**The input convention.**  Fargo takes one input *number* fixed before the
run, not a stream of bits, so the harness feeds a single line holding
``int(bits, 2)`` -- the table's row index.  Input ``i`` counted
most-significant-first is therefore bit ``n - 1 - i`` of that number, which
is the only place the mapping appears.  Because the number is read once by
the interpreter before execution, every program consumes exactly one input
line whatever the table says, constant tables included.

Input reordering does not apply: ``@`` indexes the input number directly.
"""

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["fargo"]


def _anf_coefficients(truth_table: str) -> list[int]:
    """Return the table's algebraic normal form coefficients.

    The Möbius transform: ``coeff[s]`` is the XOR of every table entry whose
    row is a subset of the mask ``s``.  Computed in place, one input at a
    time, so it costs ``n * 2**n`` rather than the ``3**n`` of summing each
    subset separately.

    ``truth_table`` is indexed most-significant-first while a mask's bit
    ``i`` is the ``i``th input counted the same way, so both sides use one
    convention and the caller converts to Fargo's LSB-first ``@`` once.
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

    Input ``i`` (most-significant-first) is bit ``n - 1 - i`` of the input
    number, so it reads ``@ <n - 1 - i>`` with the index in binary, since
    Fargo's literals are binary.  A product of ``k`` inputs needs ``k - 1``
    ``&`` operators, written prefix, so they all lead.
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
    """Return a recursively factored ANF expression in O(T) emitted size."""
    nonzero = [0]
    for coefficient in coeffs:
        nonzero.append(nonzero[-1] + coefficient)

    def build(start: int, size: int, bit: int) -> str | None:
        if nonzero[start] == nonzero[start + size]:
            return None
        if size == 1:
            return "1"
        half = size // 2
        low = build(start, half, bit - 1)
        high = build(start + half, half, bit - 1)
        if high is None:
            return low
        product = f"@ {bit:b}" if high == "1" else f"& @ {bit:b} {high}"
        return product if low is None else f"^ {low} {product}"

    expression = build(0, 1 << n, n - 1)
    return "0" if expression is None else expression


def fargo(truth_table: str, width: int | None = None) -> str:
    """Build a Fargo program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program is the table's algebraic normal form (see the module
    docstring): ``% 0 <expr>`` then ``$``, where ``expr`` XORs together one
    AND-product per nonzero ANF coefficient.  A constant table has only the
    degree-zero coefficient, so it emits ``% 0 0`` or ``% 0 1`` and skips
    the reads entirely -- which is sound here because Fargo's input is read
    by the *interpreter* before the program starts, so the input line is
    consumed either way and the read-count contract holds.
    """
    n = _validate_truth_table(truth_table)
    coeffs = _anf_coefficients(truth_table)
    expression = _anf_expression(coeffs, n)
    compact = f"% 0 {expression}\n$\n"
    if width is None or max(map(len, compact.splitlines())) <= width:
        return compact
    masks = [mask for mask in range(1 << n) if coeffs[mask] and mask]
    return _factored(masks, coeffs[0], n)
