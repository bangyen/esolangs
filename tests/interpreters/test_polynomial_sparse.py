"""Cold parsing of arbitrary Polynomial sources in polynomial time.

``docs/proofs/polynomial.md`` ("Cold parsing of arbitrary programs") proves
that the instruction list of any source is computable in time polynomial in
its length: a sparse term map, the gap lemma, the ``x d/dx`` multiplicity
test, ``p``-adic lifting with a 2-D lattice for the roots of one chunk, and
proven primality in :func:`convert`.  These tests pin each step and hold the
whole parser to an independent oracle -- the parser this replaced, dense
coefficients through SymPy's ``factor_list`` and a ``convert`` that scans
every integer -- on a seeded corpus small enough for the oracle to finish.
"""

import math
import random
import re
import time

import pytest
import sympy as sp

from esolangs.interpreters.register_based._polynomial_roots import (
    _aks,
    _dense_gaussian_roots,
    _gap_chunks,
    _gauss_reduce,
    _integer_root,
    _is_proven_prime,
    _Root,
    _sparse_multiplicity,
    _sparse_roots,
)
from esolangs.interpreters.register_based.polynomial import (
    _parse_program,
    convert,
    sanitize,
    sanitize_terms,
)
from esolangs.tools._polynomial import format_coeffs
from esolangs.tools.polynomial import _polynomial_factors

X = sp.Symbol("x")


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


def _oracle_parse(code: str) -> tuple[tuple[int, ...], ...]:
    """Dense coefficients, ``factor_list``, scanning ``convert``."""
    cleaned = re.sub(r"[^\df(x)=+-^]", "", code)
    coefficients = sanitize(cleaned)
    if not any(coefficients):
        # The peel's quirk on an all-zero list: ``x - 2`` divides it
        # ``degree`` times.
        return ((1,),) * (len(coefficients) - 1)
    roots: list[tuple[int, int]] = []
    _, factors = sp.factor_list(sp.Poly.from_list(coefficients, X))
    for factor, multiplicity in factors:
        coeffs = [int(k) for k in factor.all_coeffs()]
        if len(coeffs) == 2 and coeffs[0] == 1:
            roots.extend([(-coeffs[1], 0)] * multiplicity)
        elif len(coeffs) == 3 and coeffs[0] == 1 and coeffs[1] % 2 == 0:
            real = -coeffs[1] // 2
            square = coeffs[2] - real * real
            imag = math.isqrt(square) if square > 0 else 0
            if imag and imag * imag == square:
                roots.extend([(real, imag)] * multiplicity)
    return tuple(tuple(k) for k in _oracle_convert(roots))


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


def _cofactor(rng: random.Random) -> list[list[int]]:
    """A factor that encodes nothing, or encodes on purpose, or repeats."""
    kind = rng.randrange(10)
    if kind == 0:
        return [[1, -rng.choice([0, 1, -1])]] * rng.randint(1, 3)
    if kind == 1:
        return [[rng.choice([2, 3, 5]), rng.choice([-1, 1, 3, -7])]]
    if kind == 2:
        return [rng.choice([[1, 0, 1], [1, -2, 2], [1, 2, 2]])]
    if kind == 3:
        root = rng.choice([2, 4, 8, 9, 27, 6, 12, -2, -9, 256, 3**8, 2**9])
        return [[1, -root]] * rng.randint(1, 3)
    if kind == 4:
        real = rng.randint(-50, 50)
        imag = rng.choice([2, 4, 3, 9, 6, 12, 2**7, 5, 1])
        return [[1, -2 * real, real * real + imag * imag]] * rng.randint(1, 3)
    if kind == 5:
        return [[rng.randint(-9, 9) or 1 for _ in range(rng.randint(2, 6))]]
    if kind == 6:
        return [[1, 0, 0, -2]]
    if kind == 7:
        return [[3, -30, 87]]  # 3((x-5)**2 + 4): content over a real pair
    if kind == 8:
        return [[rng.choice([2, -3]), 0]]
    return []


def _instructions(rng: random.Random) -> list[list[int]]:
    out: list[list[int]] = []
    for _ in range(rng.randint(0, 5)):
        if rng.random() < 0.5:
            out.append([rng.randint(1, 4)])
        else:
            out.append([rng.randint(-40, 40), rng.randint(1, 3)])
    return out


def _corpus(count: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    sources = []
    for _ in range(count):
        instructions = _instructions(rng)
        factors = _polynomial_factors(instructions) if instructions else []
        for _ in range(rng.randint(0, 3)):
            factors += _cofactor(rng)
        rng.shuffle(factors)
        coefficients = _expand(factors) if factors else [rng.randint(-5, 5)]
        source = format_coeffs(coefficients) if any(coefficients) else "f(x) = 0"
        quirk = rng.randrange(6)
        if quirk == 0:
            source = source.replace(" ", "")
        elif quirk == 1:
            # A later term for an existing degree wins.
            degree = rng.randrange(len(coefficients))
            extra = rng.randint(1, 9)
            source += f" + {extra}x^{degree}" if degree else f" + {extra}"
        elif quirk == 2:
            source += " + 7 - 3"  # the last bare number is the constant
        elif quirk == 3:
            source = source.replace("f(x) = ", f"f(x) = 0x^{len(coefficients) + 3} + ")
        elif quirk == 4:
            source = "comment " + source + " end"
        sources.append(source)
    return sources


def _forced_sparse(source: str) -> tuple[tuple[int, ...], ...] | None:
    """The sparse path on a source the dispatcher would parse densely."""
    terms = sanitize_terms(re.sub(r"[^\df(x)=+-^]", "", source))
    if not any(terms.values()):
        return None
    roots = [k for k in _sparse_roots(terms) if k.imag >= 0]
    return tuple(tuple(k) for k in convert(roots))


# --------------------------------------------------------------------------
# The whole parser against the oracle
# --------------------------------------------------------------------------


class TestDifferential:
    """New parse == old parse on a seeded corpus, both dispatch paths."""

    @pytest.mark.parametrize("seed", range(4))
    def test_parse_matches_the_factor_list_oracle(self, seed: int) -> None:
        _parse_program.cache_clear()
        for source in _corpus(25, seed):
            assert _parse_program(source) == _oracle_parse(source), source

    @pytest.mark.parametrize("seed", range(4))
    def test_forced_sparse_path_matches_the_oracle(self, seed: int) -> None:
        for source in _corpus(25, 100 + seed):
            forced = _forced_sparse(source)
            if forced is not None:
                assert forced == _oracle_parse(source), source

    @pytest.mark.medium
    def test_moderately_sparse_sources_match_the_oracle(self) -> None:
        """Exponents small enough for the dense oracle, large enough to gap."""
        rng = random.Random(7)
        for _ in range(6):
            poly = {0: 1}
            for _ in range(rng.randint(1, 2)):
                gap = rng.randint(20, 45)
                poly = _sparse_mul(poly, {gap: 1, 0: rng.choice([-1, 1])})
            factors = _polynomial_factors(_instructions(rng)) + _cofactor(rng)
            for factor in factors:
                poly = _sparse_mul(poly, _dense_to_sparse(factor))
            source = _render(poly)
            expected = _oracle_parse(source)
            _parse_program.cache_clear()
            assert _parse_program(source) == expected, source
            forced = _forced_sparse(source)
            assert forced is None or forced == expected, source


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
    def test_sanitize_terms_is_sanitize_without_the_list(self) -> None:
        for source in _corpus(60, 11):
            cleaned = re.sub(r"[^\df(x)=+-^]", "", source)
            terms = sanitize_terms(cleaned)
            dense = sanitize(cleaned)
            degree = max(terms, default=0)
            assert dense == [terms.get(d, 0) for d in range(degree, -1, -1)]

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

    @pytest.mark.parametrize("seed", range(3))
    def test_dense_gaussian_roots_match_sympy(self, seed: int) -> None:
        rng = random.Random(seed)
        for _ in range(15):
            factors = []
            for _ in range(rng.randint(1, 4)):
                factors += _cofactor(rng) or [[1, rng.randint(-20, 20)]]
            coefficients = _expand(factors)
            if not any(coefficients):
                continue
            expected = set()
            _, factors = sp.factor_list(sp.Poly.from_list(coefficients, X))
            for factor, _multiplicity in factors:
                coeffs = [int(k) for k in factor.all_coeffs()]
                if len(coeffs) == 2 and coeffs[0] == 1 and coeffs[1]:
                    expected.add((-coeffs[1], 0))
                elif len(coeffs) == 3 and coeffs[0] == 1 and coeffs[1] % 2 == 0:
                    real = -coeffs[1] // 2
                    square = coeffs[2] - real * real
                    imag = math.isqrt(square) if square > 0 else 0
                    if imag and imag * imag == square:
                        expected |= {(real, imag), (real, -imag)}
            assert _dense_gaussian_roots(coefficients) == expected, coefficients

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

    def test_aks_runs_its_congruences_on_a_prime_past_r(self) -> None:
        # 1009 > r here, so the answer comes from the (x + a)**n checks.
        assert _aks(1009)
        assert not _aks(561)  # Carmichael
        assert not _aks(1009 * 1013)

    def test_convert_above_the_deterministic_range(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Past the Miller--Rabin range a probable prime is certified by AKS."""
        import esolangs.interpreters.register_based._polynomial_roots as module

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


class TestConvert:
    @pytest.mark.parametrize("seed", range(3))
    def test_matches_the_scanning_convert(self, seed: int) -> None:
        rng = random.Random(seed)
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
