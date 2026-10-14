"""Conservative resource estimates for Polynomial construction."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationEstimate:
    """Upper bounds before a factor product is expanded."""

    degree: int
    coefficient_digits: int
    rendered_chars: int
    peak_decimal_digits: int
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
