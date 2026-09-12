"""The packed polynomial multiplication agrees with the incremental one.

:func:`~esolangs.tools._polynomial.render_product` has two paths over the
same factors -- an incremental ``multiply`` loop below
``_PACKED_MIN_FACTORS`` and Kronecker substitution above it -- and its
docstring's claim is that both "render the same bytes".  That claim is the
oracle here: the incremental loop is simple enough to trust, so the packed
path is checked against it rather than against a frozen string.

These paths lost their exerciser when the text generators went.  A boolean
table's factors are short and uniformly signed, so nothing in the suite
reached the packed path's signed branches -- the bias/unbias slicing, the
two-operand subtraction in :func:`_pack`, or a merge of a normalised side
with a signed one.  They are real numeric edge cases rather than dead code,
so they are driven directly.
"""

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
    """Expand ``factors`` the simple way: the oracle for the packed path."""
    coeffs = [1]
    for factor in factors:
        coeffs = multiply(coeffs, factor)
    return format_coeffs(coeffs)


def _mixed_factors(break_at: int) -> list[list[int]]:
    """Enough factors to force the packed path, with the signs broken once.

    ``[1, -k]`` is the shape Polynomial's own factors have, and a product of
    them alternates.  One factor with a *positive* index-1 coefficient
    breaks that, which is what pushes the merge onto its signed branches --
    :func:`_normalise` returns False for the node holding it, and the merge
    then has to bias its slots to keep them sliceable.
    """
    factors = [[1, -(3 + i)] for i in range(_PACKED_MIN_FACTORS + 8)]
    factors[break_at] = [1, 7]
    return factors


class TestPackedAgainstIncremental:
    def test_the_two_paths_render_the_same_bytes(self) -> None:
        """The claim render_product's docstring makes, executed."""
        factors = _mixed_factors(5)
        assert render_product(factors) == _incremental(factors)

    def test_a_normalised_side_merges_with_a_signed_one(self) -> None:
        """Breaking the signs late leaves one merge operand still normalised.

        The two sides then disagree about their form, so the merge has to
        put the signs back on the normalised one before multiplying; with
        the break early both sides are signed and that path is never taken.
        """
        factors = _mixed_factors(-3)
        assert render_product(factors) == _incremental(factors)

    def test_a_zero_coefficient_survives_the_packed_path(self) -> None:
        """``(x*x - 1)`` contributes a zero coefficient to the product."""
        factors = _mixed_factors(4)
        factors[0] = [1, 0, -1]
        assert render_product(factors) == _incremental(factors)


class TestNormalise:
    def test_alternating_signs_are_stripped(self) -> None:
        assert _normalise(["1", "-2", "3"]) == (["1", "2", "3"], True)

    def test_a_list_whose_signs_do_not_alternate_is_left_alone(self) -> None:
        """A positive odd-index coefficient breaks the pattern.

        The pair is returned unchanged with the flag clear, which is what
        tells :func:`_merge` its slots may go negative.
        """
        assert _normalise(["1", "2"]) == (["1", "2"], False)


class TestResign:
    def test_odd_indices_regain_their_sign_and_zero_does_not(self) -> None:
        """``-0`` is not a coefficient, so the zero is left bare."""
        assert _resign(["1", "2", "0", "4"]) == ["1", "-2", "0", "-4"]


class TestPack:
    def test_all_positive_coefficients_pack_into_one_decimal(self) -> None:
        assert _pack(["1", "2"], 3) == 1002

    def test_a_negative_coefficient_packs_as_a_subtraction(self) -> None:
        """No digit slot can hold a minus sign, so the negatives pack
        separately and are subtracted: ``1000 - 2``."""
        assert _pack(["1", "-2"], 3) == 998


class TestRenderTerms:
    def test_a_zero_coefficient_contributes_no_term(self) -> None:
        assert _render_terms(["1", "0", "-1"], False) == "f(x) = x^2 - 1"  # noqa: FBT003

    def test_alternating_signs_come_from_the_index(self) -> None:
        """With the flag set the strings are magnitudes; index 2 is even,
        so its term is added rather than subtracted."""
        assert _render_terms(["1", "0", "1"], True) == "f(x) = x^2 + 1"  # noqa: FBT003


class TestFormatCoeffs:
    def test_a_zero_coefficient_contributes_no_term(self) -> None:
        """``(x - 1)(x + 1)`` is ``x^2 - 1``: the linear term drops out."""
        assert format_coeffs([1, 0, -1]) == "f(x) = x^2 - 1"
