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

import pytest

from esolangs.tools._polynomial import (
    _PACKED_MIN_FACTORS,
    _normalise,
    _pack,
    _render_terms,
    _resign,
    estimate_product,
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


class TestResourceEstimate:
    def test_public_generator_covers_dispatch_resource_branches(self) -> None:
        from esolangs.tools.polynomial import _polynomial_dag, polynomial

        assert polynomial("0101").startswith("f(x) = ")  # leading ignored input
        assert polynomial("0000").startswith("f(x) = ")  # one constant leaf
        assert _polynomial_dag("01")

    @pytest.mark.parametrize(
        "table",
        ["01", "0110", "01101001", "0110100110010110"],
    )
    def test_render_bound_holds_on_generator_corpus(self, table: str) -> None:
        from esolangs.tools.polynomial import (
            _polynomial_factors,
            _polynomial_hybrid,
        )

        factors = _polynomial_factors(_polynomial_hybrid(table, 0))
        assert len(render_product(factors)) <= estimate_product(factors).rendered_chars

    def test_render_bound_holds_across_signed_boundary_cases(self) -> None:
        cases = [
            [[1, -2], [1, 3]],
            [[1, 0, -1], [1, -9]],
            _mixed_factors(5),
            [[1, 2 + i, 3 + i] for i in range(_PACKED_MIN_FACTORS + 8)],
        ]
        for factors in cases:
            estimate = estimate_product(factors)
            assert len(render_product(factors)) <= estimate.rendered_chars
            assert estimate.peak_decimal_digits >= estimate.rendered_chars

    def test_larger_coefficients_increase_every_resource_bound(self) -> None:
        small = estimate_product([[1, -2], [1, -3]])
        large = estimate_product([[1, -(10**20)], [1, -(10**30)]])
        assert large.rendered_chars > small.rendered_chars
        assert large.peak_decimal_digits > small.peak_decimal_digits
        assert large.digit_work > small.digit_work


def test_cold_parse_estimate_covers_a_root_past_the_old_fixed_lift() -> None:
    from esolangs.polynomial_resources import estimate_cold_parse

    coeffs = [1, *([0] * 399)]
    estimate = estimate_cold_parse(coeffs)
    assert estimate.real_lift_bound > 163_841 // 2
    assert estimate.field_count == 2
    assert estimate.fallback_possible
    assert estimate.peak_words >= len(coeffs) * estimate.coefficient_digits
    assert estimate.digit_work > 0


def test_assemble_refuses_an_oversized_estimate_before_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    from esolangs.exceptions import GeneratorCapError
    from esolangs.tools.polynomial import _polynomial_assemble

    module = importlib.import_module("esolangs.tools.polynomial")
    monkeypatch.setattr(module, "_POLYNOMIAL_MAX_ESTIMATED_CHARS", 100)
    with pytest.raises(GeneratorCapError, match="live decimal digits"):
        _polynomial_assemble([[10**40, 1]])


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


class TestBranchesTheGeneratorNoLongerReaches:
    """The generator now parks negative operands, so its products are signed.

    Two branches the old all-alternating builds exercised for free are still
    live code -- a widest coefficient past CPython's 4300-digit cap, and a
    merge of two non-negative sides -- so they are driven directly.
    """

    def test_the_digit_cap_is_lifted_and_restored(self) -> None:
        import sys

        from esolangs.tools._polynomial import _digit_limit_for

        before = sys.get_int_max_str_digits()
        with _digit_limit_for(before + 200):
            assert len(str(10 ** (before + 100))) == before + 101
        assert sys.get_int_max_str_digits() == before

    def test_two_non_negative_sides_merge_without_a_bias(self) -> None:
        """All-positive factors neither alternate nor carry a minus, so the
        product's slots are read straight off, with no bias decimal."""
        factors = [[1, 2 + i, 3 + i] for i in range(_PACKED_MIN_FACTORS + 8)]
        assert render_product(factors) == _incremental(factors)
