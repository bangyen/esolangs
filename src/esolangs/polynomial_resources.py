"""Conservative resource estimates for Polynomial construction and parsing."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationEstimate:
    """Upper bounds before a factor product is expanded."""

    degree: int
    coefficient_digits: int
    rendered_chars: int
    peak_decimal_digits: int
    digit_work: int


@dataclass(frozen=True)
class ColdParseEstimate:
    """Upper bounds derived from parsed integer coefficients."""

    degree: int
    coefficient_digits: int
    real_lift_bound: int
    field_points: int
    field_count: int
    fallback_possible: bool
    peak_words: int
    digit_work: int


def _decimal_digits_upper(value: int) -> int:
    """Bound decimal width without converting a potentially huge integer."""
    return max(1, value.bit_length() * 30103 // 100000 + 1)


def estimate_generation(factors: list[list[int]]) -> GenerationEstimate:
    """Bound product text, packed storage, and schoolbook digit work.

    The product's coefficient 1-norm is the product of the factors' 1-norms.
    Adding their decimal widths therefore bounds every output coefficient
    without first constructing any large integer.
    """
    degree = sum(max(0, len(factor) - 1) for factor in factors)
    coefficient_digits = max(
        1,
        sum(
            _decimal_digits_upper(sum(abs(value) for value in factor))
            for factor in factors
        ),
    )
    exponent_chars = max(1, len(str(degree)) + 2)
    # Every coefficient may be present and carry `` - ``/`` + `` plus x^d.
    rendered_chars = 7 + (degree + 1) * (coefficient_digits + 3 + exponent_chars)
    # _merge's slot adds convolution-count and sign digits.  Three packed
    # decimals plus the coefficient strings can coexist at its high-water mark.
    slot_width = coefficient_digits + len(str(degree + 1)) + 2
    packed_digits = slot_width * (degree + 2)
    peak_decimal_digits = rendered_chars + 4 * packed_digits
    # A deliberately portable ceiling: every factor may trigger a full
    # degree-squared convolution of widest coefficients under schoolbook
    # decimal arithmetic.  Faster integer/Decimal paths only reduce it.
    digit_work = max(1, len(factors)) * (degree + 1) ** 2 * coefficient_digits**2
    return GenerationEstimate(
        degree,
        coefficient_digits,
        rendered_chars,
        peak_decimal_digits,
        digit_work,
    )


def estimate_cold_parse(coeffs: list[int]) -> ColdParseEstimate:
    """Bound the implemented fast peel; do not price its factoring fallback."""
    from esolangs.interpreters.register_based.polynomial import (
        _NTT_FIELDS,
        _ntt_real_bound,
    )

    degree = max(0, len(coeffs) - 1)
    nonzero = [abs(value) for value in coeffs if value]
    coefficient_digits = max(
        1, max((_decimal_digits_upper(value) for value in nonzero), default=1)
    )
    real_lift_bound = _ntt_real_bound(degree)
    field_points = sum(field[0] for field in _NTT_FIELDS)
    field_count = len(_NTT_FIELDS)
    # The two exhaustive transforms are fixed-size.  Coefficient reduction
    # still reads every input digit; the D**2 lift can propose O(D**3)
    # quadratics and each screen scans O(D) coefficients.
    transform_work = field_points * max(1, field_points.bit_length())
    arithmetic_digits = coefficient_digits + degree * len(str(degree + 1))
    peel_work = (degree + 1) ** 4 * arithmetic_digits**2
    prime_powers = max(1, 2 * degree) * 6
    # Before exact division, the implementation materialises candidate
    # ``(real, square)`` pairs.  One pair per real lift and prime power is a
    # deliberately loose upper bound; two payload integers price each tuple.
    candidate_count = (2 * real_lift_bound + 1) * prime_powers
    # Tuple/set headers and Python integers dominate their payload.  Sixty-four
    # words per degree bit is intentionally above the two integer digit arrays
    # plus container overhead on every supported CPython word size.
    words_per_candidate = 16 + 64 * max(1, (degree + 1).bit_length())
    candidate_words = candidate_count * words_per_candidate
    peak_words = field_points + (degree + 1) * coefficient_digits + candidate_words
    # Coefficients alone carry no provenance or factor-shape certificate.
    # Any nonconstant arbitrary program may leave a remainder for factor_list.
    fallback_possible = degree > 0
    return ColdParseEstimate(
        degree,
        coefficient_digits,
        real_lift_bound,
        field_points,
        field_count,
        fallback_possible,
        peak_words,
        transform_work + peel_work,
    )
