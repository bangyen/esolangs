"""Cold parsing of arbitrary Polynomial sources in polynomial time."""

import math
import random
import time

import pytest
import sympy as sp

from esolangs.languages.polynomial.generator import _polynomial_factors
from esolangs.languages.polynomial.generator.algebra import format_coeffs
from esolangs.languages.polynomial.interpreter import (
    _parse_program,
    convert,
    primality,
    sanitize_terms,
)
from esolangs.languages.polynomial.interpreter import roots as roots_module
from esolangs.languages.polynomial.interpreter.gaussian import (
    _dense_gaussian_roots,
    _gap_chunks,
    _gauss_reduce,
    _gaussian_pow,
    _sparse_multiplicity,
)
from esolangs.languages.polynomial.interpreter.primality import (
    _aks,
    _aks_modulus,
    _integer_root,
    _is_proven_prime,
    _totient,
)
from esolangs.languages.polynomial.interpreter.roots import _Root, _sparse_roots

# --------------------------------------------------------------------------
# The oracle: the pre-sparse parser, kept only as a specification
# --------------------------------------------------------------------------


def _oracle_convert(roots: list[tuple[int, int]]) -> list[list[int]]:
    """The scanning ``convert``: every integer up to the widest root."""
    ordered = sorted(roots, key=lambda r: (r[1], r[0]))
    post: list[list[int]] = []
    limit = max((max(abs(a), abs(b)) for a, b in roots), default=0)
    num = 2
    while ordered and num <= limit + 1:
        if all(num % k for k in range(2, math.isqrt(num) + 1)):
            for root in ordered[:]:
                real, imag = root
                exponents = range(1, 7) if imag else range(1, 9)
                target = imag or real
                for val in exponents:
                    if target == num**val:
                        ordered.remove(root)
                        post.append([real, val] if imag else [val])
                        break
        num += 1
    return post


def _expand(factors: list[list[int]]) -> list[int]:
    poly = [1]
    for factor in factors:
        out = [0] * (len(poly) + len(factor) - 1)
        for i, left in enumerate(poly):
            for j, right in enumerate(factor):
                out[i + j] += left * right
        poly = out
    return poly


def _sparse_mul(left: dict[int, int], right: dict[int, int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for e1, c1 in left.items():
        for e2, c2 in right.items():
            out[e1 + e2] = out.get(e1 + e2, 0) + c1 * c2
    return {e: c for e, c in out.items() if c}


def _dense_to_sparse(coefficients: list[int]) -> dict[int, int]:
    degree = len(coefficients) - 1
    return {degree - i: c for i, c in enumerate(coefficients) if c}


def _render(poly: dict[int, int]) -> str:
    text = " ".join(
        f"{'-' if c < 0 else '+'} {abs(c)}x^{e}"
        if e
        else f"{'-' if c < 0 else '+'} {abs(c)}"
        for e, c in sorted(poly.items(), reverse=True)
    )
    return "f(x) = " + (text[2:] if text.startswith("+ ") else "-" + text[2:])


# --------------------------------------------------------------------------
# Sparse sources the dense parser could never allocate
# --------------------------------------------------------------------------


class TestHugeExponents:
    """``x^1000000000000`` is two entries of a term map and nothing more."""

    def test_the_known_construction_decodes(self) -> None:
        big = 10**12
        poly = {big: 1, 0: -1}
        for factor in ([1, -2], [1, -2], [1, -2], [1, -2, 10], [1, -9]):
            poly = _sparse_mul(poly, _dense_to_sparse(factor))
        source = _render(poly)
        _parse_program.cache_clear()
        start = time.perf_counter()
        # (x-2)**3 -> [1] x3; x - 9 = 3**2 -> [2]; (x-1)**2 + 3**2 -> [1, 1].
        assert _parse_program(source) == ((1,), (1,), (1,), (2,), (1, 1))
        assert time.perf_counter() - start < 0.5

    def test_a_generated_program_times_a_huge_binomial(self) -> None:
        """Every factor of a real program survives multiplication by ``x^N+1``."""
        instructions = [[1], [0, 1], [5, 2], [2], [3], [-7, 1], [2], [0, 2]]
        factors = _polynomial_factors(instructions)
        poly = _dense_to_sparse(_expand(factors))
        dense_source = format_coeffs(_expand(factors))
        for exponent in (10**15, 3 * 10**9 + 7):
            source = _render(_sparse_mul(poly, {exponent: 1, 0: 1}))
            _parse_program.cache_clear()
            assert _parse_program(source) == _parse_program(dense_source)

    def test_repeated_roots_across_a_huge_gap(self) -> None:
        """Multiplicity through ``x d/dx``: ``(x-4)**3 (x**N - 7)``."""
        poly = _sparse_mul(_dense_to_sparse(_expand([[1, -4]] * 3)), {10**11: 1, 0: -7})
        assert _parse_program(_render(poly)) == ((2,), (2,), (2,))

    def test_a_common_root_needs_every_chunk(self) -> None:
        """``(x-2)(x^N) + (x-3)``: each chunk has a root, but not a common one."""
        poly = _sparse_mul({1: 1, 0: -2}, {10**9: 1})
        poly.update({1: 1, 0: -3})
        assert _parse_program(_render(poly)) == ()

    def test_a_zero_source_keeps_its_degree(self) -> None:
        """All-zero terms: the peel's ``degree`` copies of ``[1]``, both paths."""
        assert _parse_program("f(x) = 0x^3") == ((1,),) * 3
        assert _parse_program("f(x) = 0x^700") == ((1,),) * 700

    def test_a_lone_monomial_has_no_instruction(self) -> None:
        assert _parse_program("f(x) = 5x^123456789") == ()


# --------------------------------------------------------------------------
# The steps
# --------------------------------------------------------------------------


class TestSteps:
    def test_duplicate_degrees_and_constants(self) -> None:
        assert sanitize_terms("f(x)=3x^2+5x^2+1+x^0-4") == {2: 5, 0: -4}

    def test_gap_chunks_cut_only_unbridgeable_gaps(self) -> None:
        # 3 then x: a gap of 1 against mass 3 (bit length 2) cannot cut, but
        # a gap of 1 against mass 1 does: 2**1 > 1.
        assert len(_gap_chunks([(0, 3), (1, 1)])) == 1
        assert len(_gap_chunks([(0, 1), (1, 3)])) == 2
        # 3 + x has mass 4 (bit length 3): a further gap of 2 stays, 3 cuts.
        assert len(_gap_chunks([(0, 3), (1, 1), (3, 1)])) == 1
        assert len(_gap_chunks([(0, 3), (1, 1), (4, 1)])) == 2
        assert len(_gap_chunks([(0, -1), (10**12, 1)])) == 2

    def test_multiplicity_by_the_euler_operator(self) -> None:
        terms = sorted(_dense_to_sparse(_expand([[1, -2]] * 4 + [[1, 0, 9]])).items())
        assert _sparse_multiplicity(terms, (2, 0)) == 4
        assert _sparse_multiplicity(terms, (0, 3)) == 1
        assert _sparse_multiplicity(terms, (3, 0)) == 0

    def test_dense_gaussian_roots_ignore_zero_padding(self) -> None:
        # Leading zeros are no degree; a trailing one is the root 0, left out.
        assert _dense_gaussian_roots([0, 0, 1, -2, 0]) == {(2, 0)}

    def test_gauss_reduce_keeps_an_ordered_basis(self) -> None:
        assert _gauss_reduce((1, 0), (3, 5)) == ((1, 0), (0, 5))
        assert _gauss_reduce((3, 5), (1, 0)) == ((1, 0), (0, 5))

    def test_integer_root_is_exact(self) -> None:
        rng = random.Random(5)
        for _ in range(200):
            number = rng.getrandbits(rng.randint(1, 400))
            degree = rng.randint(1, 8)
            root = _integer_root(number, degree)
            assert root**degree <= number < (root + 1) ** degree


class TestProvenPrimality:
    def test_aks_agrees_with_the_sieve(self) -> None:
        assert [n for n in range(-2, 90) if _aks(n)] == list(sp.primerange(2, 90))

    def test_totient_counts_repeated_and_even_factors(self) -> None:
        # 4 and 9 are squares (factor * factor == rest); 6 needs the exact
        # ``result // factor``; even inputs need the factor 2.
        assert [_totient(n) for n in (4, 6, 9, 12)] == [2, 2, 6, 4]

    def test_aks_runs_its_congruences_on_a_prime_past_r(self) -> None:
        # 1009 > r here, so the answer comes from the (x + a)**n checks.
        assert _aks(1009)
        assert not _aks(561)  # Carmichael
        assert not _aks(1009 * 1013)

    def test_aks_asks_for_order_above_the_squared_bit_length(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The proof needs ord_r(n) > log2(n)**2; a weaker bound accepted every
        # tested composite too, so only the bound itself can be checked.
        asked: list[tuple[int, int]] = []
        found = _aks_modulus

        def spy(number: int, square: int) -> int:
            asked.append((number, square))
            return found(number, square)

        monkeypatch.setattr(primality, "_aks_modulus", spy)
        assert _aks(1009)
        assert asked == [(1009, (1009).bit_length() ** 2)]
        r = found(1009, 100)
        assert min(k for k in range(1, r) if pow(1009, k, r) == 1) > 100

    def test_convert_above_the_deterministic_range(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Past the Miller--Rabin range a probable prime is certified by AKS."""
        import esolangs.languages.polynomial.interpreter.primality as module

        monkeypatch.setattr(module, "_EXACT_ISPRIME_LIMIT", 100)
        calls: list[int] = []
        original = module._aks  # noqa: SLF001

        def recording(number: int) -> bool:
            calls.append(number)
            return original(number)

        monkeypatch.setattr(module, "_aks", recording)
        assert _is_proven_prime(101)
        assert not _is_proven_prime(143)
        roots = [_Root(101**2, 0), _Root(5, 103), _Root(143**2, 0), _Root(7, 3)]
        assert convert(roots) == [[7, 1], [2], [5, 1]]
        assert 101 in calls
        assert 103 in calls
        assert 143 not in calls  # BPSW's "composite" is already a proof


class TestRootHelpers:
    def test_a_gaussian_power_squares_its_base(self) -> None:
        """``(3 + i)**2 = 8 + 6i``: the squaring step, then the multiply."""
        assert _gaussian_pow((3, 1), 2) == (8, 6)

    def test_a_two_term_sparse_source_has_its_root(self) -> None:
        """``x^3 - 8`` has two terms, the fewest a root can need."""
        assert _sparse_roots({3: 1, 0: -8}) == [_Root(2, 0)]

    def test_a_chunk_far_from_zero_is_densified_from_its_lowest_term(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The dense list spans ``high - low + 1``, not ``high + low + 1``."""
        seen: list[list[int]] = []

        def record(dense: list[int]) -> set[tuple[int, int]]:
            seen.append(dense)
            return set()

        monkeypatch.setattr(roots_module, "_dense_gaussian_roots", record)
        _sparse_roots({10**6 + 3: 1, 10**6: -8})
        assert seen == [[1, 0, 0, -8]]

    def test_the_lift_modulus_covers_a_root_at_the_bound(self) -> None:
        """Lead 2, others at most 2: Cauchy's ``B`` is 2, and ``1 +- i`` is a root."""
        poly = [2, -2, 2, 1, 2, 2]
        assert _dense_gaussian_roots(poly) == {(1, 1), (1, -1)}


class TestConvert:
    def test_matches_the_scanning_convert(self) -> None:
        rng = random.Random(0)
        # The oracle scans every integer up to the widest root, so keep it small.
        powers = [p**v for p in (2, 3, 5, 7, 11, 13) for v in range(1, 9)]
        powers = [k for k in powers if k < 5000]
        for _ in range(200):
            roots = []
            for _ in range(rng.randint(0, 8)):
                if rng.random() < 0.5:
                    real = rng.choice(
                        [
                            rng.randint(-300, 3000),
                            rng.choice(powers),
                        ]
                    )
                    roots.append((real, 0))
                else:
                    imag = rng.choice([rng.randint(-60, 600), rng.choice(powers)])
                    roots.append((rng.randint(-50, 50), imag))
            expected = _oracle_convert(roots)
            assert convert([_Root(a, b) for a, b in roots]) == expected

    def test_a_huge_prime_power_is_recognised_without_scanning(self) -> None:
        big_prime = 2**61 - 1
        start = time.perf_counter()
        assert convert([_Root(big_prime**3, 0), _Root(-4, big_prime)]) == [
            [3],
            [-4, 1],
        ]
        assert time.perf_counter() - start < 0.5
