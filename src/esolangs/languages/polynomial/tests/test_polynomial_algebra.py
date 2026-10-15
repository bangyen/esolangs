"""The packed polynomial multiplication agrees with the incremental one."""

from dataclasses import dataclass

import pytest

from esolangs.languages.polynomial.generator.algebra import (
    _PACKED_MIN_FACTORS,
    _normalise,
    _pack,
    _render_terms,
    _resign,
    format_coeffs,
    multiply,
    render_product,
)
from esolangs.languages.polynomial.generator.resources import (
    _decimal_digits_upper,
    estimate_generation,
)


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

        from esolangs.languages.polynomial.generator import (
            _polynomial_dag,
            _polynomial_factors,
        )
        from tests.support.witness_tables import dense as _dense

        module = importlib.import_module(
            "esolangs.languages.polynomial.generator.algebra"
        )
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
        from esolangs.languages.polynomial.generator import _polynomial_dag, polynomial

        assert polynomial("0101").startswith("f(x) = ")  # leading ignored input
        assert polynomial("0000").startswith("f(x) = ")  # one constant leaf
        assert _polynomial_dag("01")

    @pytest.mark.parametrize(
        "table",
        ["01", "0110", "01101001", "0110100110010110"],
    )
    def test_render_bound_holds_on_generator_corpus(self, table: str) -> None:
        from esolangs.languages.polynomial.generator import (
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


# Test-only oracle: nothing in src/ reads it, so it lives beside its test.
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


def estimate_cold_parse(coeffs: list[int]) -> ColdParseEstimate:
    """Bound the implemented fast peel; do not price the remainder root search."""
    from esolangs.languages.polynomial.interpreter.ntt import (
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
    # Any nonconstant arbitrary program may leave a remainder for
    # _remainder_roots, polynomial in the source but not priced here.
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


def test_cold_parse_estimate_covers_a_root_past_the_old_fixed_lift() -> None:
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
    from esolangs.languages.polynomial.generator import _polynomial_assemble

    module = importlib.import_module("esolangs.languages.polynomial.generator")
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

        from esolangs.runtime._digits import digit_limit_for

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

    module = importlib.import_module("esolangs.languages.polynomial.generator")
    monkeypatch.setattr(module, "_POLYNOMIAL_MAX_INSTRS", 15)
    assert evaluate_generated("Polynomial", "0101") == "0101"
