"""Known factors check both root recovery and its Gaussian-rational oracle."""

from collections import Counter

import pytest
import sympy as sp

from esolangs.interpreters.register_based.polynomial.roots import _factor_roots, _Root
from tests.interpreters.test_polynomial import TestPeelPrimePowerRoots as _PeelTests


@pytest.mark.parametrize("real", [6])
@pytest.mark.parametrize("imag", [0, 4])
@pytest.mark.parametrize("multiplicity", [1, 3])
def test_known_roots_survive_scaling_and_noninteger_factors(
    real: int, imag: int, multiplicity: int
) -> None:
    x = sp.Symbol("x")
    factor = x - real if imag == 0 else (x - real) ** 2 + imag**2
    # Rational, nonintegral Gaussian, irrational, and cubic roots are excluded.
    noise = (
        (2 * x - 1)
        * (4 * x**2 + 1)
        * ((2 * x - 1) ** 2 + 16)
        * (x**2 - 2)
        * (x**3 - x - 1)
    )
    polynomial = sp.Poly(-3 * factor**multiplicity * noise, x)
    coefficients = tuple(int(c) for c in polynomial.all_coeffs())
    known = [_Root(real, imag)] * multiplicity
    if imag:
        known += [_Root(real, -imag)] * multiplicity
    expected = Counter(known)
    assert Counter(_PeelTests._reference(coefficients)) == expected  # noqa: SLF001
    assert Counter(_factor_roots(coefficients)) == expected
