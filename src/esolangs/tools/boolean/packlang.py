"""Boolean-function generator for Packlang.

Packlang's expression language is *affine*: ``^`` is XOR and ``!`` is
negation, and neither can build an AND, so a truth table cannot be written
as one expression.  What the language does have is a statement nesting --
``If a Then { If b Then { ... } }`` fires only when every guard is true --
so an AND-product is a chain of ``If``s rather than an operator.

That makes the **algebraic normal form** the construction that fits, and
it is the same ANF the roadmap points at: the XOR of the AND-products the
Möbius transform selects (:func:`~esolangs.tools.boolean.fargo
._anf_coefficients`, imported rather than re-derived -- Fargo and Super
SNUSP each already carry one)::

    f(x) = c0 XOR (c1 & x0) XOR (c2 & x1) XOR (c3 & x0 & x1) XOR ...

Each nonzero coefficient becomes one ``If`` chain, nested as deep as the
term's degree, whose body is a single ``INCR acc``.  The accumulator is
declared ``Integer(0, 1, 1, 0)``, so incrementing past its maximum wraps
to 0: ``INCR`` on it *is* XOR-with-1, and the terms accumulate mod 2 with
no addition operator involved.  The answer prints as ``charPut(48 ^ acc)``
-- the dependency example's own trick for turning a bit into its digit,
with 48 in decimal per this repo's literal-base resolution.

Size tracks the function's *algebraic* complexity rather than ``2**n``: a
table depending on one input is one term whatever its arity, parity is
``n`` terms (one per single-variable coefficient), and a dense ANF is the
worst case at up to ``2**n - 1``.  A term of degree ``d`` costs ``d``
nested ``If``s, so the program is the polynomial written out.

**The reads are unconditional and come first**, one ``charGet`` per input
before any term, so a constant table consumes exactly as many inputs as a
dense one.  Skipping them for a constant table would leave the caller's
bits on the input stream, which is what
``tests/tools/test_boolean_contract.py`` pins.

An input arrives as the digit ``'0'`` or ``'1'`` (48 or 49), so each is
normalized to 0/1 by ``x ^ 48`` at the guard rather than stored twice.
"""

from esolangs.tools.boolean.fargo import _anf_coefficients
from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["packlang"]

_INDENT = "  "


def _term_inputs(mask: int, n: int) -> list[int]:
    """Return the inputs the term ``mask`` ANDs, most-significant-first.

    The truth table and the mask share one convention -- input ``i`` is bit
    ``n - 1 - i`` -- so this is the only place the mapping is spelled.
    """
    return [i for i in range(n) if mask >> (n - 1 - i) & 1]


def _term(mask: int, n: int, depth: int) -> str:
    """Emit one ANF term as a nest of ``If``s ending in ``INCR acc``.

    A degree-``d`` term needs ``d`` guards, since Packlang has no AND
    operator; the degree-zero term (the constant) is an unguarded ``INCR``.
    Each guard normalizes its digit input with ``^ 48``, so the test is on
    the bit rather than on the character code.
    """
    pad = _INDENT * depth
    inputs = _term_inputs(mask, n)
    lines = [
        f"{pad}{_INDENT * k}If x{i} ^ {_ASCII_ZERO} Then {{"
        for k, i in enumerate(inputs)
    ]
    inner = _INDENT * (depth + len(inputs))
    lines.append(f"{inner}INCR acc;")
    lines += [f"{pad}{_INDENT * k}}}" for k in reversed(range(len(inputs)))]
    return "\n".join(lines)


def packlang(truth_table: str) -> str:
    """Build a Packlang program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program reads ``n`` digits with ``charGet``, accumulates the
    table's ANF into a wrapping ``Integer(0, 1, 1, 0)``, and prints the
    result digit.  See the module docstring for why the terms are ``If``
    nests rather than an expression.
    """
    n = _validate_truth_table(truth_table)
    coefficients = _anf_coefficients(truth_table)

    declarations = "".join(f"  Char x{i};\n" for i in range(n))
    reads = "".join(f"{_INDENT * 2}charGet(x{i});\n" for i in range(n))
    terms = "\n".join(_term(mask, n, 2) for mask in range(1 << n) if coefficients[mask])
    body = f"{terms}\n" if terms else ""
    return (
        "Package : IO {\n"
        f"{declarations}"
        "  Integer(0, 1, 1, 0) acc;\n"
        "  Integer main {\n"
        f"{_INDENT * 2}INIT acc;\n"
        f"{reads}"
        f"{body}"
        f"{_INDENT * 2}charPut({_ASCII_ZERO} ^ acc);\n"
        f"{_INDENT * 2}0;\n"
        "  }\n"
        "} truthTable;\n"
    )
