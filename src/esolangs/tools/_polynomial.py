"""Polynomial algebra for the Polynomial generator.

Each instruction gets a prime ``p`` ascending in program order (see
``_polynomial_assemble``) and becomes a root ``a + p**b*i``; conjugate
pairs keep the coefficients integral.
"""

import contextlib
import decimal
import sys
from collections.abc import Iterator

from esolangs.polynomial_resources import GenerationEstimate, estimate_generation


@contextlib.contextmanager
def _digit_limit_for(digits: int) -> Iterator[None]:
    """Raise CPython's ``int``/``str`` digit cap to fit ``digits``, then restore.

    The 4300 default is a DoS guard; a 462-instruction table exceeds it.
    Same borrow as Factor's ``_parse`` and boolean ``factor``.
    """
    limit = sys.get_int_max_str_digits()
    if digits <= limit:
        yield
        return
    sys.set_int_max_str_digits(digits + 1)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)


def primes(count: int) -> list[int]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        if all(candidate % p for p in primes):
            primes.append(candidate)
        candidate += 1
    return primes


def multiply(a: list[int], b: list[int]) -> list[int]:
    result: list[int] = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            result[i + j] += ai * bj
    return result


# Above this many factors the product goes through :func:`_packed_product`
# instead of the incremental ``multiply`` loop.  That loop is cubic in the
# factor count -- every step rescans a polynomial whose coefficients have
# grown -- and it owns the whole cost past boolean n == 7: on the dense
# n=10 fixture (1382 factors, degree 2260, 16.9 MB of text) it spent 18.6s
# multiplying and 4.7s in ``str``.  Below the threshold the loop is cheaper
# than packing, and keeping it there also keeps the small-table corpus on
# the path it was measured against.  Measured on random factor lists: at 128
# factors the loop still wins by 11%, at 192 the packing wins by 9%.
_PACKED_MIN_FACTORS = 160

# How many factors one leaf group holds.  The leaves stay on the cubic loop,
# so their cost falls as ``1 / groups**2``, while each extra merge level
# moves about the same total digits as the one below it and so costs about
# the same -- the two balance near a group the size of the threshold above.
# Measured on dense n=10 (1382 factors): 4 groups 5.77s, 8 groups 5.02s,
# 16 groups 4.91s, and the leaves are 1.88s / 0.52s / 0.14s of that.
#
# The *count* is rounded down to a power of two so the merge tree is
# balanced.  An odd count leaves a node unpaired, which is carried up and
# merged against a much larger one later -- at 1382 factors that cost 8.3s
# against 6.3s for the balanced shapes either side of it.
_PACKED_GROUP_SIZE = 96


def render_product(factors: list[list[int]]) -> str:
    """Multiply the ``factors`` together and render the ``f(x) = ...`` text.

    Small products take ``multiply``; large ones :func:`_packed_product`.
    Both are exact, so they render the same bytes.
    """
    if len(factors) < _PACKED_MIN_FACTORS:
        coeffs = [1]
        for factor in factors:
            coeffs = multiply(coeffs, factor)
        return format_coeffs(coeffs)
    return _render_terms(*_packed_product(factors))


def estimate_product(factors: list[list[int]]) -> GenerationEstimate:
    """Return the conservative pre-expansion resource estimate."""
    return estimate_generation(factors)


def _packed_product(factors: list[list[int]]) -> tuple[list[str], bool]:
    """Expand ``factors`` by packing whole polynomials into single decimals.

    Kronecker substitution at ``10**width``; coefficients stay decimal
    strings because ``int`` conversion is quadratic.  ``Decimal`` because
    libmpdec uses an NTT where ``int`` stops at Karatsuba: 1.6s against
    roughly a minute at 25M digits a side.  Leaves stay on the incremental
    loop.  Returns coefficients highest degree first, signed, or with the
    flag as magnitudes whose sign is ``(-1)**index``.
    """
    # An upper bound on any coefficient anywhere in the tree: a product's
    # widest coefficient has at most the sum of its factors' widest digit
    # counts, plus a carry digit per factor.  Sizing it once here lifts
    # CPython's ``int``/``str`` cap for every ``str`` in the leaves.
    widest = sum(max(abs(coeff) for coeff in factor).bit_length() for factor in factors)
    digits = int(widest * 0.30103) + len(factors) + 2

    groups = 1 << max(1, (len(factors) // _PACKED_GROUP_SIZE).bit_length() - 1)
    size = -(-len(factors) // groups)
    with _digit_limit_for(digits):
        nodes = [
            _normalise(_expand_group(factors[start : start + size]))
            for start in range(0, len(factors), size)
        ]
    while len(nodes) > 1:
        nodes = [
            _merge(nodes[i], nodes[i + 1]) if i + 1 < len(nodes) else nodes[i]
            for i in range(0, len(nodes), 2)
        ]
    return nodes[0]


def _expand_group(factors: list[list[int]]) -> list[str]:
    """Expand one group on the incremental loop, as signed decimal strings."""
    coeffs = [1]
    for factor in factors:
        coeffs = multiply(coeffs, factor)
    return [str(coeff) for coeff in coeffs]


def _normalise(coeffs: list[str]) -> tuple[list[str], bool]:
    """Drop the signs from a coefficient list whose signs alternate.

    Alternating signs are closed under multiplication, so :func:`_merge`
    can slice without biasing.  The generator's negative ``b == 1``
    operands break it for most leaves: on dense n=10, 7 of 11 nodes
    normalise and 4 carry signs; the render is still 1.8x faster than the
    previous builder's.
    """
    if all(c == "0" or (c[0] == "-") == (i % 2 == 1) for i, c in enumerate(coeffs)):
        return [c[1:] if c[0] == "-" else c for c in coeffs], True
    return coeffs, False


def _resign(magnitudes: list[str]) -> list[str]:
    """Put alternating signs back onto :func:`_normalise`'s magnitudes."""
    return ["-" + m if i % 2 and m != "0" else m for i, m in enumerate(magnitudes)]


def _pack(coeffs: list[str], width: int) -> "decimal.Decimal":
    """Pack signed coefficient strings into the polynomial's value at ``10**width``.

    Positives and negatives are packed separately and subtracted.
    """
    if not any(c[0] == "-" for c in coeffs):
        return decimal.Decimal("".join(c.rjust(width, "0") for c in coeffs))
    zero = "0" * width
    plus = "".join(zero if c[0] == "-" else c.rjust(width, "0") for c in coeffs)
    minus = "".join(c[1:].rjust(width, "0") if c[0] == "-" else zero for c in coeffs)
    return decimal.Decimal(plus) - decimal.Decimal(minus)


def _merge(
    left: tuple[list[str], bool], right: tuple[list[str], bool]
) -> tuple[list[str], bool]:
    """Multiply two polynomials packed as single decimals, and unpack the product.

    Normalised sides multiply as magnitudes; otherwise slots hold signed
    coefficients, the width carries one extra digit (a product coefficient
    sums at most ``min(len(left), len(right))`` products), and every slot is
    biased by half its range; the leading digit says which biased form to
    read.
    """
    (lhs, normalised), (rhs, right_normalised) = left, right
    if normalised != right_normalised:
        if normalised:
            lhs, normalised = _resign(lhs), False
        else:
            rhs = _resign(rhs)
    signed = not normalised and (
        any(c[0] == "-" for c in lhs) or any(c[0] == "-" for c in rhs)
    )
    magnitude = max(len(c) - (c[0] == "-") for c in lhs) + max(
        len(c) - (c[0] == "-") for c in rhs
    )
    width = magnitude + len(str(min(len(lhs), len(rhs)))) + signed
    terms = len(lhs) + len(rhs) - 1
    with decimal.localcontext() as ctx:
        # Exact or nothing -- a rounded product would spell a wrong program.
        # ``Decimal(str)`` never rounds; only the arithmetic below can.
        ctx.prec = width * (terms + 1)
        ctx.Emax = decimal.MAX_EMAX
        ctx.Emin = decimal.MIN_EMIN
        ctx.traps[decimal.Inexact] = True
        ctx.traps[decimal.Rounded] = True
        product = _pack(lhs, width) * _pack(rhs, width)
        if not signed:
            # Two non-negative polynomials have a non-negative product, so
            # every slot is already its own coefficient.  Worth the branch:
            # the bias below is a second decimal as wide as the product.
            slots = str(product).rjust(width * terms, "0")
            out = [
                slots[start : start + width].lstrip("0") or "0"
                for start in range(0, width * terms, width)
            ]
            return (out, True) if normalised else _normalise(out)
        bias = decimal.Decimal(("5" + "0" * (width - 1)) * terms)
        raised = str(product + bias).rjust(width * terms, "0")
        lowered = str(bias - product).rjust(width * terms, "0")
    out = []
    for start in range(0, width * terms, width):
        slot = raised[start : start + width]
        if slot[0] >= "5":
            # ``slot`` is the coefficient plus half the slot's range, and the
            # bias is a single leading 5, so undoing it never borrows.
            out.append((chr(ord(slot[0]) - 5) + slot[1:]).lstrip("0") or "0")
        else:
            slot = lowered[start : start + width]
            out.append("-" + (chr(ord(slot[0]) - 5) + slot[1:]).lstrip("0"))
    return _normalise(out)


def _render_terms(coeffs: list[str], alternating: bool) -> str:  # noqa: FBT001 - internal
    """Render coefficient strings, highest degree first.

    ``alternating`` means magnitudes with sign ``(-1)**index``.  Mirrors
    :func:`_format_coeffs` without building the integers.
    """
    degree = len(coeffs) - 1
    out = ["f(x) = "]
    first = True
    for i, coeff in enumerate(coeffs):
        if coeff == "0":
            continue
        d = degree - i
        negative = i % 2 == 1 if alternating else coeff[0] == "-"
        magnitude = coeff[1:] if coeff[0] == "-" else coeff
        if first:
            out.append("-" if negative else "")
        else:
            out.append(" - " if negative else " + ")
        if magnitude != "1" or d == 0:
            out.append(magnitude)
        out.append(f"x^{d}" if d > 1 else ("x" if d == 1 else ""))
        first = False
    return "".join(out)


def format_coeffs(coeffs: list[int]) -> str:
    """Render the coefficient list as the program's ``f(x) = ...`` text.

    The digit cap is estimated from the bit length (``log10(2) ~= 0.30103``).
    """
    widest = max((abs(coeff) for coeff in coeffs), default=0)
    digits = int(widest.bit_length() * 0.30103) + 2
    with _digit_limit_for(digits):
        return _format_coeffs(coeffs)


def _format_coeffs(coeffs: list[int]) -> str:
    terms: list[str] = []
    degree = len(coeffs) - 1
    for i, coeff in enumerate(coeffs):
        d = degree - i
        if coeff == 0:
            continue
        prefix = (
            ""
            if coeff == 1 and d > 0
            else ("-" if coeff == -1 and d > 0 else str(coeff))
        )
        power = f"x^{d}" if d > 1 else ("x" if d == 1 else "")
        terms.append(f"{prefix}{power}")
    return "f(x) = " + " + ".join(terms).replace("+ -", "- ")
