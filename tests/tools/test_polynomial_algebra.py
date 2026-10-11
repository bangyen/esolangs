"""The packed polynomial multiplication agrees with the incremental one."""

import pytest

from esolangs.tools.polynomial.algebra import (
    _PACKED_MIN_FACTORS,
    _normalise,
    _pack,
    _render_terms,
    _resign,
    format_coeffs,
    multiply,
    render_product,
)
from esolangs.tools.polynomial.resources import estimate_generation


def _incremental(factors: list[list[int]]) -> str:
    """Expand ``factors`` the simple way: the oracle for the packed path."""
    coeffs = [1]
    for factor in factors:
        coeffs = multiply(coeffs, factor)
    return format_coeffs(coeffs)


def _mixed_factors(break_at: int) -> list[list[int]]:
    """Enough factors to force the packed path, with the signs broken once."""
    factors = [[1, -(3 + i)] for i in range(_PACKED_MIN_FACTORS + 8)]
    factors[break_at] = [1, 7]
    return factors


class TestPackedAgainstIncremental:
    def test_the_two_paths_render_the_same_bytes(self) -> None:
        """The claim render_product's docstring makes, executed."""
        factors = _mixed_factors(5)
        assert render_product(factors) == _incremental(factors)

    def test_a_normalised_side_merges_with_a_signed_one(self) -> None:
        """Breaking the signs late leaves one merge operand still normalised."""
        factors = _mixed_factors(-3)
        assert render_product(factors) == _incremental(factors)

    def test_a_zero_coefficient_survives_the_packed_path(self) -> None:
        """``(x*x - 1)`` contributes a zero coefficient to the product."""
        factors = _mixed_factors(4)
        factors[0] = [1, 0, -1]
        assert render_product(factors) == _incremental(factors)


class TestResourceEstimate:
    @pytest.mark.medium
    def test_generated_root_merge_exceeds_fnt_cutoff(self, monkeypatch) -> None:
        """A generated balanced root sends two wide operands to libmpdec."""
        import decimal
        import importlib

        from esolangs.tools.polynomial import _polynomial_dag, _polynomial_factors
        from tests.support.witness_tables import dense as _dense

        module = importlib.import_module("esolangs.tools.polynomial.algebra")
        original = _pack
        packed_digits: list[int] = []

        def traced_pack(coeffs: list[str], width: int) -> decimal.Decimal:
            value = original(coeffs, width)
            packed_digits.append(len(str(abs(value))))
            return value

        monkeypatch.setattr(module, "_pack", traced_pack)
        factors = _polynomial_factors(_polynomial_dag(_dense(7)))
        program = render_product(factors)
        left, right = packed_digits[-2:]
        assert min(left, right) > 256 * 19
        assert max(left, right) < 2 * min(left, right)
        assert max(left, right) <= len(program)

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
        assert (
            len(render_product(factors)) <= estimate_generation(factors).rendered_chars
        )

    def test_render_bound_holds_across_signed_boundary_cases(self) -> None:
        cases = [
            [[1, -2], [1, 3]],
            [[1, 0, -1], [1, -9]],
            _mixed_factors(5),
            [[1, 2 + i, 3 + i] for i in range(_PACKED_MIN_FACTORS + 8)],
        ]
        for factors in cases:
            estimate = estimate_generation(factors)
            assert len(render_product(factors)) <= estimate.rendered_chars
            assert estimate.peak_decimal_digits >= estimate.rendered_chars

    def test_larger_coefficients_increase_every_resource_bound(self) -> None:
        small = estimate_generation([[1, -2], [1, -3]])
        large = estimate_generation([[1, -(10**20)], [1, -(10**30)]])
        assert large.rendered_chars > small.rendered_chars
        assert large.peak_decimal_digits > small.peak_decimal_digits
        assert large.digit_work > small.digit_work


def test_cold_parse_estimate_covers_a_root_past_the_old_fixed_lift() -> None:
    from esolangs.tools.polynomial.resources import estimate_cold_parse

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
        """A positive odd-index coefficient breaks the pattern."""
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
    """The generator now parks negative operands, so its products are signed."""

    def test_the_digit_cap_is_lifted_and_restored(self) -> None:
        import sys

        from esolangs._digits import digit_limit_for

        before = sys.get_int_max_str_digits()
        with digit_limit_for(before + 200):
            assert len(str(10 ** (before + 100))) == before + 101
        assert sys.get_int_max_str_digits() == before

    def test_two_non_negative_sides_merge_without_a_bias(self) -> None:
        """All-positive factors neither alternate nor carry a minus, so the
        product's slots are read straight off, with no bias decimal."""
        factors = [[1, 2 + i, 3 + i] for i in range(_PACKED_MIN_FACTORS + 8)]
        assert render_product(factors) == _incremental(factors)


def test_draining_remains_available_at_the_instruction_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A leading drain preserves tables excluded by the ordinary builders."""
    import importlib

    from tests.support.generator_support import evaluate_generated

    module = importlib.import_module("esolangs.tools.polynomial")
    monkeypatch.setattr(module, "_POLYNOMIAL_MAX_INSTRS", 15)
    assert evaluate_generated("Polynomial", "0101") == "0101"
