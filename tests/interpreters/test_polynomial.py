"""Unit tests for Polynomial interpreter.

Tests cover polynomial parsing, helper functions, and basic validation.
Polynomial is an esoteric language where programs are polynomial functions and
statements are executed based on the zeroes of the function.
"""

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.polynomial import (
    _divide_quadratic,
    _factor_roots,
    _Root,
    brackets,
    convert,
    prime,
    run,
    sanitize,
)
from tests.interpreters.contract import CycleContract, SnapshotContract

# Programs whose roots span orders of magnitude or repeat a wide delta -- the
# cases where a float64 solver rounds a root and drops or corrupts a
# character.  Kept as data because only the decode is under test.
_PRECISION_PROGRAMS: dict[str, str] = json.loads(
    (Path(__file__).parents[2] / "tests/fixtures/polynomial_precision.json").read_text()
)


class TestPolynomialHelperFunctions:
    """Test helper functions for polynomial processing."""

    def test_prime_function(self) -> None:
        """Test prime number detection."""
        assert prime(2) is True
        assert prime(3) is True
        assert prime(4) is False
        assert prime(5) is True
        assert prime(6) is False
        assert prime(7) is True
        assert prime(8) is False
        assert prime(9) is False
        assert prime(10) is False
        assert prime(11) is True

    def test_factor_skips_non_instruction_quadratic(self) -> None:
        """A quadratic factor whose q is negative encodes no instruction."""
        from esolangs.interpreters.register_based.polynomial import _factor_roots

        # x^3 - 5x + 2 = (x - 2)(x^2 + 2x - 1); the quadratic has q = -2,
        # so only the linear root survives.
        assert _factor_roots((1, 0, -5, 2)) == (_Root(2, 0),)

    def test_factor_skips_a_cubic_factor(self) -> None:
        """Only degree 1 and 2 factors encode instructions; higher ones do not.

        ``x^3 - 2`` is irreducible over the rationals, so it stays one cubic
        factor and contributes no root -- the loop moves on rather than
        decoding it.
        """
        from esolangs.interpreters.register_based.polynomial import _factor_roots

        assert _factor_roots((1, 0, 0, -2)) == ()

        # And a cubic alongside a decodable linear factor: (x^3 - 2)(x - 1)
        # keeps the 1 and still skips the cubic.
        assert _factor_roots((1, -1, 0, -2, 2)) == (_Root(1, 0),)

    def test_sanitize_simple_polynomial(self) -> None:
        """Test polynomial parsing for simple cases."""
        result = sanitize("f(x) = 3x^2 + x + 7")
        assert result == [3, 1, 7]

    def test_sanitize_complex_polynomial(self) -> None:
        """Test polynomial parsing for complex cases."""
        result = sanitize("f(x) = x^3 - 2x^2 + x - 1")
        assert result == [1, -2, 1, -1]

    def test_sanitize_missing_terms(self) -> None:
        """Test polynomial parsing with missing terms."""
        result = sanitize("f(x) = x^3 + 1")
        assert result == [1, 0, 0, 1]

    def test_brackets_simple(self) -> None:
        """Test bracket matching for simple cases."""
        code = [[1], [2]]  # if, endif
        assert brackets(code, 0) == 1

    def test_brackets_nested(self) -> None:
        """Test bracket matching for nested structures."""
        code = [[1], [1], [2], [2]]  # if, if, endif, endif
        assert brackets(code, 0) == 3
        assert brackets(code, 1) == 2

    def test_brackets_search_backwards_to_the_first_instruction(self) -> None:
        """A closer's partner may be instruction 0, which is in range.

        Every case above scans *forward* from an opener, so the bounds
        check only ever saw the right-hand end.  A backward scan landing
        on index 0 is legal, and a check that rejected it would call a
        matched pair unmatched.
        """
        assert brackets([[1], [2]], 1) == 0
        assert brackets([[1], [1], [2], [2]], 3) == 0
        assert brackets([[1], [1], [2], [2]], 2) == 1

    def test_brackets_reject_an_unmatched_partner_at_either_end(self) -> None:
        """Running off the left end and the right end both raise."""
        for code in ([[2]], [[1]]):
            with pytest.raises(ValueError, match="unmatched control-flow bracket"):
                brackets(code, 0)


class TestPolynomialValidation:
    """Test polynomial input validation."""

    def test_empty_program_validation(self) -> None:
        """Test that empty program is handled correctly."""
        from esolangs.interpreters.register_based.polynomial import run

        with pytest.raises(
            ValueError, match=r"Polynomial program must start with 'f\(x\) = '"
        ):
            run("", io=IO())

    def test_invalid_format_validation(self) -> None:
        """Test that invalid format raises ValueError."""
        from esolangs.interpreters.register_based.polynomial import run

        with pytest.raises(
            ValueError, match=r"Polynomial program must start with 'f\(x\) = '"
        ):
            run("invalid program", io=IO())


class TestPolynomialParsing:
    """Test polynomial parsing functionality."""

    def test_constant_polynomial_parsing(self) -> None:
        """Test parsing of constant polynomials."""
        result = sanitize("f(x) = 5")
        assert result == [5]

    def test_linear_polynomial_parsing(self) -> None:
        """Test parsing of linear polynomials."""
        result = sanitize("f(x) = x + 1")
        assert result == [1, 1]

    def test_quadratic_polynomial_parsing(self) -> None:
        """Test parsing of quadratic polynomials."""
        result = sanitize("f(x) = x^2 + 1")
        assert result == [1, 0, 1]

    def test_polynomial_with_negative_coefficients(self) -> None:
        """Test parsing of polynomials with negative coefficients."""
        result = sanitize("f(x) = -x^2 + 1")
        assert result == [-1, 0, 1]

    def test_polynomial_missing_constant(self) -> None:
        """Test parsing of polynomials missing constant term."""
        result = sanitize("f(x) = x^2 + x")
        assert result == [1, 1, 0]


class TestPolynomialMathematicalProperties:
    """Test polynomial mathematical properties."""

    def test_convert_empty_list(self) -> None:
        """An empty root list converts to an empty instruction list."""
        result = convert([])
        assert result == []


class TestPolynomialEdgeCases:
    """Test polynomial edge cases and error conditions."""

    def test_zero_polynomial_parsing(self) -> None:
        """Test parsing of zero polynomial."""
        result = sanitize("f(x) = 0")
        assert result == [0]

    def test_high_degree_polynomial_parsing(self) -> None:
        """Test parsing of high degree polynomial."""
        result = sanitize("f(x) = x^5 + x^3 + 1")
        assert result == [1, 0, 1, 0, 0, 1]

    def test_polynomial_with_large_coefficients(self) -> None:
        """Test parsing of polynomial with large coefficients."""
        result = sanitize("f(x) = 100x^2 + 50x + 25")
        assert result == [100, 50, 25]


class TestPolynomialSafety:
    """Test polynomial safety features.

    There is no per-run step cap to test here any more: ``run`` has no
    instruction limit of its own, so a non-terminating program is
    ``esolangs.run(timeout=)``'s concern, tested generically (through
    brainfuck) in test_api.py's test_run_timeout_halts_runaway_program.
    """

    def test_helper_functions_safe(self) -> None:
        """Test that helper functions are safe to call."""
        # Test prime function with various inputs
        assert prime(2) is True
        assert prime(1) is False  # 1 is not prime
        assert prime(0) is False  # 0 is not prime

        # Test sanitize function with various inputs
        assert sanitize("f(x) = 1") == [1]
        assert sanitize("f(x) = x^2") == [1, 0, 0]  # Avoid buggy "f(x) = x" case

        # Test brackets function with simple input
        code = [[1], [2]]
        assert brackets(code, 0) == 1


class TestPolynomialExecution:
    """Test that valid polynomial programs actually execute."""

    def test_output_instruction(self) -> None:
        """A root of 2i encodes an output instruction (reg starts at 0)."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run("f(x) = x^2+4", io=IO())
        assert buffer.getvalue() == "\x00"

    def test_arithmetic_then_output(self) -> None:
        """Roots encoding reg += 65 followed by output produce 'A'."""
        program = "f(x) = x^4 - 130x^3 + 4238x^2 - 1170x + 38061"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(program, io=IO())
        assert buffer.getvalue() == "A"

    def test_division_keeps_register_integer(self) -> None:
        """Reg /= a is integer division: 65 // 5 = 13, output as a char."""
        program = (
            "f(x) = 1x^6 - 140x^5 + 5819x^4 - 80080x^3 "
            "+ 1240639x^2 - 709380x + 10695141"
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(program, io=IO())
        assert buffer.getvalue() == "\r"

    def test_no_roots_no_output(self) -> None:
        for program in ["f(x) = 0", "f(x) = 1", "f(x) = x+1"]:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run(program, io=IO())
            assert buffer.getvalue() == ""

    def test_run_without_spaces(self) -> None:
        """The no-space form produced by run's sanitizer still executes."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run("f(x)=x^2+4", io=IO())
        assert buffer.getvalue() == "\x00"

    def test_control_flow_roots(self) -> None:
        """Real roots 2 and 4 encode an if-statement pair (reg is 0)."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run("f(x) = x^2 - 6x + 8", io=IO())
        assert buffer.getvalue() == ""

    def test_if_enters_when_condition_met(self) -> None:
        """If reg==0 { output } executes the body when reg is 0."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run("f(x) = x^3 - 16x^2 + 25x - 400", io=IO())
        assert buffer.getvalue() == "\x00"

    def test_if_skipped_when_condition_not_met(self) -> None:
        """The spec example: if reg>0 { output } skips the body when reg is 0."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run("f(x) = x^4 - 27x^3 + 59x^2 - 243x + 450", io=IO())
        assert buffer.getvalue() == ""

    def test_while_loop(self) -> None:
        """Add 3, while reg>0 { reg-=1 }, output decrements three times."""
        program = (
            "f(x) = x^8 - 117900x^7 + 29532615x^6 - 319727030x^5 + 22630555713x^4 "
            "- 146042691700x^3 + 2538566894185x^2 - 13198909291370x + 28151242605486"
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(program, io=IO())
        assert buffer.getvalue() == "\x00"

    def test_input_instruction(self) -> None:
        """A root of 4i encodes an input instruction (value stored in reg)."""
        import unittest.mock

        from esolangs.interpreters.register_based.polynomial import _Machine

        for text, expected in (("A", 65), ("z", 122)):
            with unittest.mock.patch("builtins.input", return_value=text):
                machine = _Machine("f(x) = x^2+16", IO())
                machine.step()
                assert machine.reg == expected

    def test_input_of_nul_reads_as_minus_one(self) -> None:
        """``ord(val[0]) or -1``: a NUL byte reads as 0, which the ``or``
        turns into -1 so the value stays distinguishable from an unset
        register.
        """
        import unittest.mock

        from esolangs.interpreters.register_based.polynomial import _Machine

        with unittest.mock.patch("builtins.input", return_value="\x00"):
            machine = _Machine("f(x) = x^2+16", IO())
            machine.step()
            assert machine.reg == -1


class TestPeelPrimePowerRoots:
    """The prime-power peel is a head start and must never change the answer.

    ``_factor_roots`` divides out real roots of the form ``p**v`` by Horner
    evaluation before ``factor_list`` sees the polynomial.  A candidate is
    accepted only because the polynomial vanishes there, so the factor is
    genuine whatever wrote the program -- but the enumeration is bounded, and
    what it misses has to survive in the remainder rather than disappear.
    These check the shapes the peel cannot see, which are exactly the ones a
    hand-written program may use.
    """

    @staticmethod
    def _reference(coefficients: tuple[int, ...]) -> list[_Root]:
        """Recover roots the way the interpreter did before the peel."""
        import math

        import sympy as sp

        x = sp.Symbol("x")
        _, factors = sp.factor_list(sp.Poly.from_list(list(coefficients), x))
        roots: list[_Root] = []
        # pylint: disable=duplicate-code  # independent oracle; see class docstring
        for factor, multiplicity in factors:
            degree = factor.degree()
            if degree == 1:
                a, b = (int(k) for k in factor.all_coeffs())
                roots.extend([_Root(-b // a, 0)] * multiplicity)
            elif degree == 2:
                a, b, c = (int(k) for k in factor.all_coeffs())
                if a != 1 or b % 2:
                    continue
                real = -b // 2
                q = c - real * real
                if q < 0:
                    continue
                imag = math.isqrt(q)
                if imag * imag != q:
                    continue
                roots.extend([_Root(real, imag), _Root(real, -imag)] * multiplicity)
        return sorted(roots, key=lambda z: (z.imag, z.real))

    @pytest.mark.parametrize(
        "description",
        [
            "composite_root",
            "prime_past_window",
            "exponent_past_cap",
            "negative_root",
            "irreducible",
            "repeated_prime_power",
        ],
    )
    def test_roots_match_factoring_alone(self, description: str) -> None:
        """Every shape the peel cannot enumerate still comes back."""
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _PEEL_MAX_EXPONENT,
            _factor_roots,
        )

        x = sp.Symbol("x")
        # A composite root and a negative one are not prime powers; a large
        # prime sits past the window the degree affords; and an exponent past
        # the cap is a prime power the enumeration stops short of.
        cases = {
            "composite_root": (x - 6) * (x - 8) * ((x - 3) ** 2 + 16),
            "prime_past_window": (x - int(sp.nextprime(10**4))) * (x - 4),
            "exponent_past_cap": (x - 2 ** (_PEEL_MAX_EXPONENT + 4)) * (x - 9),
            "negative_root": (x + 8) * (x - 8),
            "irreducible": x**3 - x - 1,
            "repeated_prime_power": (x - 8) ** 3 * (x - 27),
        }
        coefficients = tuple(
            int(k) for k in sp.Poly(cases[description], x).all_coeffs()
        )

        _factor_roots.cache_clear()
        recovered = sorted(_factor_roots(coefficients), key=lambda z: (z.imag, z.real))
        assert recovered == self._reference(coefficients)

    def test_peel_leaves_what_it_cannot_take(self) -> None:
        """A root outside the enumeration stays in the remainder.

        The soundness argument is that the peel is *incomplete*, never wrong,
        so the remainder must still carry the roots it skipped -- asserting on
        the returned pair rather than on the roots proves that directly.
        """
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _peel_prime_power_roots,
        )

        x = sp.Symbol("x")
        # 8 is a prime power the peel takes; 6 is not, so it must remain.
        poly = sp.Poly((x - 8) * (x - 6), x)
        coefficients = [int(k) for k in poly.all_coeffs()]
        peeled, remainder = _peel_prime_power_roots(coefficients)

        assert peeled == [8]
        # The remainder is the deflated quotient, x - 6.
        assert remainder == [1, -6]

    def test_peeled_roots_are_exact_factors(self) -> None:
        """Anything peeled divides the polynomial with no remainder.

        This is the whole licence for skipping ``factor_list`` on those
        roots, so it is asserted rather than trusted: dividing the original
        by every peeled factor must come out exact.
        """
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _peel_prime_power_roots,
        )

        x = sp.Symbol("x")
        poly = sp.Poly((x - 2**3) * (x - 3**2) * (x - 5) * ((x - 4) ** 2 + 2**6), x)
        coefficients = [int(k) for k in poly.all_coeffs()]
        peeled, _remainder = _peel_prime_power_roots(list(coefficients))

        assert peeled, "the polynomial has prime-power roots to take"
        product = sp.Poly(1, x)
        for root in peeled:
            product = product * sp.Poly(x - root, x)
        _quotient, rest = sp.div(poly, product)
        assert rest == sp.Poly(0, x), f"peeled {peeled} is not an exact divisor"


class TestFactorRootsRejections:
    """A quadratic factor only encodes an instruction in one exact shape.

    ``(x - a)**2 + p**(2*b)`` expands to a monic quadratic with an even
    linear term whose ``q = c - a**2`` is a positive perfect square.  Every
    other quadratic sympy hands back is some other polynomial's factor and
    carries no instruction, so it is skipped rather than decoded.
    """

    def test_a_non_square_imaginary_part_is_skipped(self) -> None:
        """``x**2 + 2`` has ``q = 2``, which is not a perfect square."""
        assert _factor_roots((1, 0, 2)) == ()

    def test_a_negative_imaginary_part_is_skipped(self) -> None:
        """``x**2 - 4`` factors into real roots, not an instruction pair."""
        assert _factor_roots((1, 0, -4)) == (_Root(2, 0), _Root(-2, 0))

    def test_an_odd_linear_term_is_skipped(self) -> None:
        """``x**2 + x + 1`` cannot be ``(x - a)**2 + square`` for integer ``a``."""
        assert _factor_roots((1, 1, 1)) == ()

    def test_the_shape_that_does_decode(self) -> None:
        """``x**2 + 4`` is ``(x - 0)**2 + 2**2``, so it yields its pair."""
        assert _factor_roots((1, 0, 4)) == (_Root(0, 2), _Root(0, -2))

    def test_a_pair_the_peels_miss_is_decoded_by_factor_list(self) -> None:
        """A real part past the peel's bound still decodes, one stage later.

        ``_peel_instruction_quadratics`` only accepts a real part within
        ``_PEEL_MAX_REAL_PART``, so a wider one survives into the remainder
        and is recovered by ``factor_list`` instead -- the path that makes
        the peels pure head starts rather than the whole search.
        """
        from esolangs.interpreters.register_based.polynomial import (
            _PEEL_MAX_REAL_PART,
        )

        real = _PEEL_MAX_REAL_PART + 10
        # (x - real)**2 + 4
        coefficients = (1, -2 * real, real * real + 4)
        assert _factor_roots(coefficients) == (
            _Root(real, 2),
            _Root(real, -2),
        )


class TestPeelQuadraticsFallback:
    """When the field factorization fails there is nothing to peel.

    The modular factor list is the whole search, so if sympy refuses it the
    function hands the coefficients back untouched and the caller's own
    ``factor_list`` still sees everything.
    """

    def test_a_refused_factorization_returns_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``PolynomialError`` from sympy leaves the coefficients alone."""
        import sympy as sp

        from esolangs.interpreters.register_based import polynomial as mod

        def refuse(*_args: object, **_kwargs: object) -> object:
            raise sp.PolynomialError("constructed")

        monkeypatch.setattr(mod.sp, "Poly", refuse)
        coefficients = [1, 0, 1, 0, 1]
        peeled = mod._peel_instruction_quadratics(coefficients)  # noqa: SLF001
        assert peeled == ([], coefficients)


class TestDivideQuadratic:
    """Exact division by ``(x - real)**2 + square``, and its refusals.

    The size guards matter because the caller feeds it whatever is left of
    the coefficient list: a list too short to hold a quadratic and a
    remainder has no quotient at all, and the two remainder positions are
    read from quotient entries that only exist above a certain size.
    """

    def test_a_list_too_short_to_divide_is_refused(self) -> None:
        """Below three coefficients there is no room for the quotient."""
        assert _divide_quadratic([1], 0, 1) is None
        assert _divide_quadratic([1, 2], 0, 1) is None

    def test_the_smallest_exact_division(self) -> None:
        """``x**2 + 1`` divided by itself is 1, with both remainders zero."""
        assert _divide_quadratic([1, 0, 1], 0, 1) == [1]

    def test_a_nonzero_linear_remainder_is_refused(self) -> None:
        """The linear position has to vanish, so a stray ``x`` term refuses."""
        assert _divide_quadratic([1, 5, 1], 0, 1) is None

    def test_a_nonzero_constant_remainder_is_refused(self) -> None:
        """The constant position has to vanish too."""
        assert _divide_quadratic([1, 0, 9], 0, 1) is None

    def test_a_longer_exact_division(self) -> None:
        """``(x**2 + 1)(x + 2)`` divides back to ``x + 2``.

        Four coefficients is the first size that reads a quotient entry two
        places back, which the three-coefficient case never does.
        """
        assert _divide_quadratic([1, 2, 1, 2], 0, 1) == [1, 2]


class TestWideCoefficientParsing:
    """A program whose coefficients are wider than CPython's digit cap.

    The cap is a DoS guard on ``int``/``str`` conversion, not anything
    Polynomial says, so the parser raises it for the width of the source it
    is handed and puts it straight back.
    """

    def test_a_number_past_the_digit_cap_still_parses(self) -> None:
        """``sanitize`` reads a coefficient wider than the default limit."""
        limit = sys.get_int_max_str_digits()
        digits = "9" * (limit + 5)
        coefficients = sanitize(f"f(x) = {digits}x^2 + 1")
        assert sys.get_int_max_str_digits() == limit, "the cap is handed back"
        # Reading the value back needs the cap raised again, which is the
        # whole reason the parser raises it in the first place.
        sys.set_int_max_str_digits(limit + 10)
        try:
            assert len(str(coefficients[0])) == limit + 5
        finally:
            sys.set_int_max_str_digits(limit)


class TestPeelInstructionQuadratics:
    """The quadratic peel is a head start too, under the same rules.

    A complex instruction is ``(x - a)**2 + p**(2*b)``, and ``a`` is solved
    for modulo :data:`_PEEL_MODULUS` rather than enumerated.  A pair is
    accepted only when it divides exactly, so what the search cannot see has
    to survive in the remainder instead of vanishing.
    """

    @staticmethod
    def _product(pairs: list[tuple[int, int]], extra: object = None) -> list[int]:
        import sympy as sp

        x = sp.Symbol("x")
        poly = sp.Poly(1, x)
        for real, square in pairs:
            poly = poly * sp.Poly((x - real) ** 2 + square, x)
        if extra is not None:
            poly = poly * extra
        return [int(k) for k in poly.all_coeffs()]

    def test_modulus_admits_every_encodable_square(self) -> None:
        """``_PEEL_MODULUS`` must be ``1 (mod 4)``, or the peel finds nothing.

        ``q`` is ``p**(2*b)``, a perfect square, so ``-q`` is a quadratic
        residue exactly when ``-1`` is -- which holds iff the modulus is
        ``1 (mod 4)``.  Under a ``3 (mod 4)`` modulus no ``q`` at all admits
        the square root the pairing needs and the peel quietly does nothing,
        which is why this is asserted rather than left to the constant.
        """
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _PEEL_MAX_IMAGINARY_EXPONENT,
            _PEEL_MODULUS,
        )

        assert _PEEL_MODULUS % 4 == 1, "a 3 (mod 4) modulus disables the peel"
        assert sp.isprime(_PEEL_MODULUS)
        for base in (2, 3, 5, 7, 11):
            for exponent in range(1, _PEEL_MAX_IMAGINARY_EXPONENT + 1):
                square = base ** (2 * exponent)
                assert sp.sqrt_mod((-square) % _PEEL_MODULUS, _PEEL_MODULUS) is not None

    @pytest.mark.parametrize(
        "description",
        [
            "square_not_a_prime_power",
            "real_part_past_window",
            "cubic_factor",
            "odd_leftover",
            "repeated_quadratic",
        ],
    )
    def test_nothing_skipped_is_lost(self, description: str) -> None:
        """What the peel cannot take stays in the remainder, exactly."""
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _PEEL_MAX_REAL_PART,
            _peel_instruction_quadratics,
        )

        x = sp.Symbol("x")
        cases = {
            # 15 is not p**(2*b), so this quadratic is unrecognisable.
            "square_not_a_prime_power": self._product([(3, 15)]),
            "real_part_past_window": self._product([(_PEEL_MAX_REAL_PART + 7, 4)]),
            "cubic_factor": self._product([(3, 4)], sp.Poly(x**3 - x - 1, x)),
            "odd_leftover": self._product([(5, 9)], sp.Poly(x - 7, x)),
            "repeated_quadratic": self._product([(4, 9), (4, 9)]),
        }
        coefficients = cases[description]

        found, remainder = _peel_instruction_quadratics(list(coefficients))

        # Whatever came out must divide the original exactly, and the
        # remainder must be precisely the cofactor -- nothing dropped.
        original = sp.Poly(coefficients, x)
        taken = sp.Poly(1, x)
        for real, square in found:
            taken = taken * sp.Poly((x - real) ** 2 + square, x)
        recomposed = taken * sp.Poly(remainder, x) if len(remainder) > 1 else taken
        assert recomposed == original

    def test_divide_quadratic_refuses_a_non_divisor(self) -> None:
        """The exact-division gate is what makes an accepted pair sound."""
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import _divide_quadratic

        x = sp.Symbol("x")
        coefficients = [int(k) for k in sp.Poly((x - 3) ** 2 + 4, x).all_coeffs()]
        assert _divide_quadratic(coefficients, 3, 4) == [1]
        assert _divide_quadratic(coefficients, 99, 7) is None
        # A quadratic sharing only the real part must not be taken either.
        assert _divide_quadratic(coefficients, 3, 9) is None


class TestNttRecovery:
    """The large-degree path: roots from exhaustive field evaluation.

    Past ``_NTT_MIN_DEGREE`` both peels take their candidates from the
    polynomial's roots over two fixed prime fields rather than enumerating
    or factoring over ``_PEEL_MODULUS``.  Acceptance is still exact
    division, so these check the search half: the fields' constants, the
    root sets, and that the whole path recovers a program exactly while
    leaving what encodes nothing.
    """

    @staticmethod
    def _program(pairs: list[tuple[int, int]], reals: list[int]) -> list[int]:
        """Integer coefficients of ``prod (x-a)^2+q * prod (x-r)``."""
        coefficients = [1]
        for real, square in pairs:
            b1, b0 = -2 * real, real * real + square
            nxt = [0] * (len(coefficients) + 2)
            for i, k in enumerate(coefficients):
                nxt[i] += k
                nxt[i + 1] += k * b1
                nxt[i + 2] += k * b0
            coefficients = nxt
        for root in reals:
            nxt = [0] * (len(coefficients) + 1)
            for i, k in enumerate(coefficients):
                nxt[i] += k
                nxt[i + 1] -= k * root
            coefficients = nxt
        return coefficients

    def test_ntt_field_constants(self) -> None:
        """Each field is ``(c * 2**k + 1, c, k, g)``, prime, ``1 (mod 4)``.

        The ``1 (mod 4)`` requirement is :data:`_PEEL_MODULUS`'s, for the
        same reason -- ``sqrt(-1)`` is what turns a quadratic's root pair
        into field elements -- and ``g`` must generate the whole group or
        :func:`_roots_mod` would evaluate only a subgroup and silently
        miss roots.
        """
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import _NTT_FIELDS

        seen = set()
        for modulus, cofactor, log_size, generator in _NTT_FIELDS:
            assert modulus == cofactor * 2**log_size + 1
            assert modulus % 4 == 1
            assert sp.isprime(modulus)
            assert sp.n_order(generator, modulus) == modulus - 1
            seen.add(modulus)
        assert len(seen) == len(_NTT_FIELDS), "the cross-check needs a second field"

    def test_roots_mod_is_the_exact_root_set(self) -> None:
        """Planted roots come back exactly -- no more, no fewer.

        A repeated root and roots past both moduli ride along: exhaustive
        evaluation needs no squarefreeness, and a wide root folds to its
        residue, which is all the candidate screens ask of it.
        """
        from esolangs.interpreters.register_based.polynomial import (
            _NTT_FIELDS,
            _roots_mod,
        )

        planted = [3, 3, 65539, 200003]
        coefficients = self._program([], planted)
        for field in _NTT_FIELDS:
            modulus = field[0]
            assert _roots_mod(coefficients, field) == {r % modulus for r in planted}

    def test_zero_is_reported_when_x_divides(self) -> None:
        """The one point outside the multiplicative group is still seen."""
        from esolangs.interpreters.register_based.polynomial import (
            _NTT_FIELDS,
            _roots_mod,
        )

        assert 0 in _roots_mod([1, -7, 0], _NTT_FIELDS[0])  # x(x - 7)

    def test_iter_bits_matches_bit_positions(self) -> None:
        """The byte-scan extraction is exactly ``bin()``'s set bits."""
        from esolangs.interpreters.register_based.polynomial import _iter_bits

        mask = (1 << 0) | (1 << 7) | (1 << 8) | (1 << 1000) | (1 << 163839)
        assert sorted(_iter_bits(mask, 163841)) == [0, 7, 8, 1000, 163839]
        assert list(_iter_bits(0, 163841)) == []

    def test_a_large_program_is_recovered_exactly(self) -> None:
        """Past the threshold, every planted factor comes back and nothing
        else -- the execution-gate witness for the search half.

        The factors mirror a generated program's: quadratics ``(a,
        p**(2*b))`` on consecutive primes with data-sized ``a`` including
        the negatives and zeros the DAG emits, plus real prime powers.
        The degree (259) sits past ``_NTT_MIN_DEGREE`` so this runs the
        NTT path, which the recovered multiset proves end to end.
        """
        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _NTT_MIN_DEGREE,
            _factor_roots,
            _Root,
        )

        primes = list(sp.primerange(2, 700))
        pairs = []
        reals = []
        for index, p in enumerate(primes[:100]):
            if index % 3 == 2:
                reals.append(p ** (1 + index % 4))
            else:
                a = (index * 37) % 800 - 400  # data operands, both signs
                pairs.append((a, p ** (2 * (1 + index % 3))))
        coefficients = self._program(pairs, reals)
        assert len(coefficients) - 1 > _NTT_MIN_DEGREE

        expected = [_Root(r, 0) for r in reals]
        for a, q in pairs:
            import math

            root = math.isqrt(q)
            expected.extend([_Root(a, root), _Root(a, -root)])

        _factor_roots.cache_clear()
        recovered = _factor_roots(tuple(coefficients))
        assert sorted(recovered) == sorted(expected)

    def test_what_the_large_path_cannot_take_reaches_factor_list(self) -> None:
        """The fallback stays wired on the NTT path.

        A real part past the lift window (half the pairing field) pairs to
        the wrong lift, fails the exact division, and survives to
        ``factor_list``, which decodes it anyway -- same bargain as the
        enumerated path's ``_PEEL_MAX_REAL_PART`` case.
        """
        import math

        import sympy as sp

        from esolangs.interpreters.register_based.polynomial import (
            _NTT_FIELDS,
            _NTT_MIN_DEGREE,
            _factor_roots,
            _Root,
        )

        wide = _NTT_FIELDS[0][0]  # a real part the lift cannot reach
        pairs = [(3, p * p) for p in sp.primerange(2, 800)]
        pairs = pairs[: (_NTT_MIN_DEGREE // 2) + 2]
        coefficients = self._program([*pairs, (wide, 9)], [])

        _factor_roots.cache_clear()
        recovered = _factor_roots(tuple(coefficients))
        expected = [_Root(wide, 3), _Root(wide, -3)]
        for a, q in pairs:
            root = math.isqrt(q)
            expected.extend([_Root(a, root), _Root(a, -root)])
        assert sorted(recovered) == sorted(expected)


class TestPolynomialHighPrecisionRoots:
    """Wide codepoint deltas and pathological root spreads are recovered
    exactly by factoring the integer polynomial (no floating point).
    """

    def _decode(self, text: str) -> str:
        """Run the fixture program for ``text`` and return what it printed."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(_PRECISION_PROGRAMS[text], io=IO())
        return buffer.getvalue()

    @pytest.mark.parametrize("text", ["😀t", "a中", "1😀+", "a日a日", "A中B"])
    def test_wide_codepoint_deltas_round_trip(self, text: str) -> None:
        """ASCII followed by CJK/emoji spans several orders of magnitude."""
        assert self._decode(text) == text

    def test_repeated_wide_deltas_round_trip(self) -> None:
        """The same wide delta repeated (a pathological root spread for any
        numeric solver) is recovered exactly by factoring.
        """
        text = "aあbいcう" * 2
        assert self._decode(text) == text

    def test_single_corrupted_delta_round_trip(self) -> None:
        """A mixed program where float64 silently corrupted one delta (19977
        -> 19971) is recovered exactly; the old numpy path emitted a wrong
        character.
        """
        text = "aWg{<$中Z一t"
        assert self._decode(text) == text

    def test_a_real_root_past_float64_still_decodes(self) -> None:
        """``251**8`` exceeds 2**53, where ``complex`` would round it.

        Roots used to ride through ``complex``, whose float64 mantissa
        rounds any integer past 2**53 -- ``convert``'s exact ``==`` against
        ``p**v`` then misses and the instruction silently vanishes.  Wide
        real roots are routine at high arity (the dense n=10 table reaches
        ``p**4`` near 3.7e16), so the pipeline carries exact pairs instead;
        this pins the decode end to end.
        """
        from esolangs.interpreters.register_based.polynomial import (
            _Root,
            convert,
        )

        root = 251**8
        assert float(root) != root, "the witness must not fit float64"
        assert convert([_Root(root, 0)]) == [[8]]

    def test_non_prime_power_roots_produce_no_instruction(self) -> None:
        """Roots that do not map to an instruction (not a prime power, or a
        prime power with no matching bracket) are handled like the wiki
        defines: they simply produce no executable instruction.
        """
        for expr in ["x - 6", "x^2 + 2", "x^2 + 8", "x^3 - 1"]:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run("f(x) = " + expr, io=IO())
            assert buffer.getvalue() == ""

    def test_unmatched_bracket_still_raises(self) -> None:
        """A real root that is a prime power but has no matching bracket is
        still a malformed program (the factor path preserves the check).
        """
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run("f(x) = x - 4", io=IO())


class TestConvertRealRoots:
    """Real roots encode instructions reached through later primes."""

    def test_prime_root(self) -> None:
        """A prime root like 5 matches at its own prime (skipping composites)."""
        assert convert([5]) == [[1]]

    def test_prime_power_root(self) -> None:
        """A prime power like 4 (2^2) encodes an if-statement code."""
        assert convert([4]) == [[2]]

    def test_non_standard_input(self) -> None:
        assert sanitize("invalid") == [0]

    def test_no_terms(self) -> None:
        assert sanitize("f(x) = +") == [0]


class TestStepMachine:
    def test_step_tracks_register_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.polynomial import _Machine

        machine = _Machine("f(x) = x^2+4", ScriptedIO())
        assert (machine.ind, machine.reg) == (0, 0)
        machine.step()  # the [0, 1] instruction prints the register
        assert machine.io.getvalue() == "\x00"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 1


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.polynomial import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "f(x) = x^2+4"
    halting_program = "f(x) = x^2+4"
