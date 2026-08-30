"""Boolean-function generator for Fargo.

Fargo is the one language in the suite whose *input interface* is already a
truth table's index: ``@ i`` returns the ``i``th bit of the input number, so
the generator never has to read, normalize and store bits before it can test
them.  What every other generator spends on routing -- a decision tree, a
minterm sum, a grid walk -- Fargo spends on nothing at all.

That makes an **algebraic normal form** the natural construction rather than
a tree.  Every boolean function has exactly one ANF, the XOR of a subset of
the AND-products of its inputs::

    f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...

which maps onto ``^``, ``&`` and ``@`` one operator per node, so the program
is the polynomial and its size tracks the function's *algebraic* complexity
rather than ``2**n``.  A table depending on one input is one term whatever
its arity; parity is the worst case at ``n`` terms, since parity's ANF is
the sum of all ``n`` single-variable terms.  The coefficients come from the
Möbius transform (:func:`_anf_coefficients`), which is the table's own
XOR-prefix over subsets.

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

Input *reordering* does not apply here: ``@`` indexes a bit directly, so no
order of reads exists to permute and every arrangement of the same ANF has
the same length.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table

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


def fargo(truth_table: str) -> str:
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
    terms = [_term(mask, n) for mask in range(1 << n) if coeffs[mask] and mask]
    constant = coeffs[0]
    if not terms:
        return f"% 0 {constant}\n$\n"
    # ``^`` is binary and prefix, so combining k terms needs k - 1 of them
    # up front; a nonzero constant is one more thing to XOR in.
    if constant:
        terms.insert(0, "1")
    expression = "^ " * (len(terms) - 1) + " ".join(terms)
    return f"% 0 {expression}\n$\n"
