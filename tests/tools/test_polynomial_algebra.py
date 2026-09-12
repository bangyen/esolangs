r"""The packed polynomial multiplication agrees with the incremental."""

from esolangs.tools._polynomial import (
    _PACKED_MIN_FACTORS,
    _normalise,
    _pack,
    _render_terms,
    _resign,
    format_coeffs,
    multiply,
    render_product,
)


def _incremental(factors: list[list[int]]) -> str:
    r"""Expand ``factors`` the simple way: the oracle for the packed path."""
    coeffs = [1]
    for factor in factors:
        coeffs = multiply(coeffs, factor)
    return format_coeffs(coeffs)


def _mixed_factors(break_at: int) -> list[list[int]]:
    r"""Enough factors to force the packed path, with the signs broken once."""
    factors = [[1, -(3 + i)] for i in range(_PACKED_MIN_FACTORS + 8)]
    factors[break_at] = [1, 7]
    return factors


class TestPackedAgainstIncremental:
    def test_the_two_paths_render_the_same_bytes(self) -> None:
        r"""The claim render_product's docstring makes, executed."""
        factors = _mixed_factors(5)
        assert render_product(factors) == _incremental(factors)

    def test_a_normalised_side_merges_with_a_signed_one(self) -> None:
        r"""Breaking the signs late leaves one merge operand still normalised."""
        factors = _mixed_factors(-3)
        assert render_product(factors) == _incremental(factors)

    def test_a_zero_coefficient_survives_the_packed_path(self) -> None:
        r"""``(x*x - 1)`` contributes a zero coefficient to the product."""
        factors = _mixed_factors(4)
        factors[0] = [1, 0, -1]
        assert render_product(factors) == _incremental(factors)


class TestNormalise:
    def test_alternating_signs_are_stripped(self) -> None:
        assert _normalise(["1", "-2", "3"]) == (["1", "2", "3"], True)

    def test_a_list_whose_signs_do_not_alternate_is_left_alone(self) -> None:
        r"""A positive odd-index coefficient breaks the pattern."""
        assert _normalise(["1", "2"]) == (["1", "2"], False)


class TestResign:
    def test_odd_indices_regain_their_sign_and_zero_does_not(self) -> None:
        r"""``-0`` is not a coefficient, so the zero is left bare."""
        assert _resign(["1", "2", "0", "4"]) == ["1", "-2", "0", "-4"]


class TestPack:
    def test_all_positive_coefficients_pack_into_one_decimal(self) -> None:
        assert _pack(["1", "2"], 3) == 1002

    def test_a_negative_coefficient_packs_as_a_subtraction(self) -> None:
        r"""No digit slot can hold a minus sign, so the negatives pack."""
        assert _pack(["1", "-2"], 3) == 998


class TestRenderTerms:
    def test_a_zero_coefficient_contributes_no_term(self) -> None:
        assert _render_terms(["1", "0", "-1"], False) == "f(x) = x^2 - 1"  # noqa: FBT003

    def test_alternating_signs_come_from_the_index(self) -> None:
        r"""With the flag set the strings are magnitudes; index 2 is even, so."""
        assert _render_terms(["1", "0", "1"], True) == "f(x) = x^2 + 1"  # noqa: FBT003


class TestFormatCoeffs:
    def test_a_zero_coefficient_contributes_no_term(self) -> None:
        r"""``(x - 1)(x + 1)`` is ``x^2 - 1``: the linear term drops out."""
        assert format_coeffs([1, 0, -1]) == "f(x) = x^2 - 1"
