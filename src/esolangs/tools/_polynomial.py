"""Polynomial algebra for the Polynomial generator.

A Polynomial program is a polynomial whose roots encode instructions: the
k-th instruction uses the k-th prime p, turned into a complex root
``a + p**b*i``. Conjugate pairs are included so the expanded coefficients
stay integers.
"""

import contextlib
import decimal
import sys
from collections.abc import Iterator


@contextlib.contextmanager
def _digit_limit_for(digits: int) -> Iterator[None]:
    """Raise CPython's ``int``/``str`` digit cap to fit ``digits``, then restore.

    ``sys.get_int_max_str_digits()`` defaults to 4300 and is a DoS guard
    against quadratic conversions, not anything Polynomial says.  A
    program's coefficients grow with its instruction count -- a 541
    instruction table needs more than that -- so at some arity the guard
    stops the generator from rendering a program the interpreter could run.
    It is process-global and ours to borrow, so it is raised to what this
    render needs and handed straight back, exactly as Factor's ``_parse``
    and boolean ``factor`` already do for the same reason.
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


# Above this many factors the.
# instead of the incremental.
# factor count -- every step.
# grown -- and it owns the.
# n=10 fixture (1638 factors,.
# multiplying and 4.7s in.
# than packing, and keeping it.
# the path it was measured.
# factors the loop still wins.
_PACKED_MIN_FACTORS = 160

# How many factors one leaf.
# so their cost falls as ``1 /.
# moves about the same total.
# the same -- the two balance.
# Measured on dense n=10 (1638.
# 16 groups 4.91s, and the.
# .
# The *count* is rounded down.
# balanced.
# merged against a much larger.
# against 6.3s for the balanced.
_PACKED_GROUP_SIZE = 96


def render_product(factors: list[list[int]]) -> str:
    """Multiply the ``factors`` together and render the ``f(x) = ...`` text.

    Each factor is a coefficient list, highest degree first.  Small products
    take the incremental ``multiply`` loop; large ones take
    :func:`_packed_product`.  Both are exact integer arithmetic over the
    same factors, so they render the same bytes.
    """
    if len(factors) < _PACKED_MIN_FACTORS:
        coeffs = [1]
        for factor in factors:
            coeffs = multiply(coeffs, factor)
        return format_coeffs(coeffs)
    return _render_terms(*_packed_product(factors))


def _packed_product(factors: list[list[int]]) -> tuple[list[str], bool]:
    """Expand ``factors`` by packing whole polynomials into single decimals.

    Padding every coefficient to a common width and concatenating spells the
    polynomial evaluated at ``10**width``, so one integer multiplication of
    two such strings is one polynomial multiplication (Kronecker
    substitution) and slicing the product's digits apart recovers the
    coefficients.  Coefficients are carried as decimal *strings* throughout:
    ``int``/``Decimal`` conversion is quadratic in both directions, while
    ``str`` in either direction is linear, so nothing here ever builds the
    integers.

    ``Decimal`` rather than ``int`` because libmpdec multiplies with a
    number-theoretic transform where CPython's ``int`` stops at Karatsuba --
    measured at 25M digits a side, 1.6s against roughly a minute.

    The leaves stay on the incremental loop: it is cheap while the
    coefficients are short, and packing costs a ``str`` per coefficient that
    only pays for itself once the operands are long.

    Returns the coefficients highest degree first, as signed decimal strings
    -- or, with the flag set, as magnitudes whose sign is ``(-1)**index``.
    """
    # An upper bound on any.
    # widest coefficient has at.
    # counts, plus a carry digit.
    # CPython's ``int``/``str`` cap.
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

    Signs that alternate with the index are closed under multiplication, so
    a node in that form stays in it all the way up the tree and its slots are
    never negative -- which is what lets :func:`_merge` slice a product apart
    without first biasing it.

    Polynomial's factors *nearly* have the property by construction
    (``[1, -2a, a*a + p**(2*b)]``, ``[1, -p**v]``): an operand carries a
    magnitude and its sign lives in the opcode.  The exception is
    multiply-by-span, whose operand is a difference of two state indices.
    Products still come out alternating because a factor's constant term is
    a prime power and swamps the span -- measured on dense n=10, 67 of 1638
    factors break the pattern and all 31 nodes of the tree still have it --
    but that is an argument about magnitudes, not a guarantee, so it is
    detected here rather than assumed.
    """
    if all(c == "0" or (c[0] == "-") == (i % 2 == 1) for i, c in enumerate(coeffs)):
        return [c[1:] if c[0] == "-" else c for c in coeffs], True
    return coeffs, False


def _resign(magnitudes: list[str]) -> list[str]:
    """Put alternating signs back onto :func:`_normalise`'s magnitudes."""
    return ["-" + m if i % 2 and m != "0" else m for i, m in enumerate(magnitudes)]


def _pack(coeffs: list[str], width: int) -> "decimal.Decimal":
    """Pack signed coefficient strings into the polynomial's value at ``10**width``.

    A negative coefficient cannot be spelled in a digit slot, so the
    positive and negative coefficients are packed into two non-negative
    decimals and subtracted -- one linear pass each, where a per-coefficient
    ``int`` would be quadratic.
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

    Each side is :func:`_normalise`'s pair.  Two normalised sides multiply as
    magnitudes and stay normalised; otherwise the signs come back and the
    slots have to hold a *signed* coefficient, so the width carries one digit
    more than the bound -- a product coefficient is a sum of at most
    ``min(len(left), len(right))`` pairwise products, so its digit count is at
    most the two widest inputs' plus that count's.  Biasing every slot by half
    its range makes those slots non-negative and so sliceable; the two biased
    forms differ only in which sign decodes without a borrow, and a slot's
    leading digit says which one to read.
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
        # Exact or nothing -- a rounded.
        # ``Decimal(str)`` never.
        ctx.prec = width * (terms + 1)
        ctx.Emax = decimal.MAX_EMAX
        ctx.Emin = decimal.MIN_EMIN
        ctx.traps[decimal.Inexact] = True
        ctx.traps[decimal.Rounded] = True
        product = _pack(lhs, width) * _pack(rhs, width)
        if not signed:
            # Two non-negative polynomials.
            # every slot is already its own.
            # the bias below is a second.
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
            # ``slot`` is the coefficient.
            # bias is a single leading 5,.
            out.append((chr(ord(slot[0]) - 5) + slot[1:]).lstrip("0") or "0")
        else:
            slot = lowered[start : start + width]
            out.append("-" + (chr(ord(slot[0]) - 5) + slot[1:]).lstrip("0"))
    return _normalise(out)


def _render_terms(coeffs: list[str], alternating: bool) -> str:  # noqa: FBT001 - internal
    """Render coefficient strings, highest degree first.

    ``alternating`` says the strings are magnitudes whose sign is
    ``(-1)**index``; otherwise they carry their own leading ``-``.

    A mirror of :func:`_format_coeffs` that never builds the integers: a
    leading ``-`` and the ``" + "`` separator collapse into the one ``" - "``
    that :func:`_format_coeffs` reaches by rewriting ``"+ -"``.
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

    The widest coefficient sets how far CPython's digit cap has to be lifted
    for the ``str`` calls below; it is estimated from the bit length
    (``log10(2) ~= 0.30103``) so sizing it does not pay for the very
    conversion it is about to allow.
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
