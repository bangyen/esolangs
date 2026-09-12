r"""Polynomial interpreter implementation."""

import functools
import math
import re
import sys
from collections.abc import Callable, Iterator, Sequence
from typing import NamedTuple

import sympy as sp

from esolangs.interpreters.io import IO


class _Root(NamedTuple):
    r"""A recovered root, exact: ``real + imag*i`` with integer parts."""

    real: int
    imag: int


def prime(number: int) -> bool:
    r"""Check if a number is prime."""
    if number < 2:
        return False
    return all(number % val for val in range(2, math.isqrt(number) + 1))


def brackets(string: list[list[int]], pointer: int) -> int:
    r"""Find matching bracket for control flow statements."""
    length = len(string[pointer]) == 1
    end = string[pointer][0] in [2, 6]
    direct = (1, -1)[length and end]
    count = direct
    while count:
        pointer += direct
        if pointer < 0 or pointer >= len(string):
            raise ValueError("unmatched control-flow bracket")
        if len(string[pointer]) == 1:
            if string[pointer][0] in [2, 6]:
                count -= 1
            else:
                count += 1
    return pointer


def convert(pre: Sequence[complex | _Root]) -> list[list[int]]:
    r"""Convert polynomial roots to instruction codes using prime encoding."""
    rounded_roots = [(round(k.real), round(k.imag)) for k in pre]
    # Sort by imaginary part, then.
    sorted_roots = sorted(rounded_roots, key=lambda x: (x[1], x[0]))
    post: list[list[int]] = []
    num = 2

    # A prime power p**v (v >= 1).
    # largest root magnitude no.
    if rounded_roots:
        limit = max(max(abs(im), abs(real)) for real, im in rounded_roots)
    else:
        limit = 0

    while sorted_roots and num <= limit + 1:
        if not prime(num):
            num += 1
            continue
        for root in sorted_roots[:]:  # Use slice to avoid.
            real, im = root
            if im:
                for val in range(1, 7):
                    if im == num**val:
                        sorted_roots.remove(root)
                        post.append([real, val])
                        break
            else:
                for val in range(1, 9):
                    if real == num**val:
                        sorted_roots.remove(root)
                        post.append([val])
                        break
        num += 1
    return post


def sanitize(code: str) -> list[int]:
    r"""Parse polynomial string into coefficient list."""
    longest = max((len(run) for run in re.findall(r"\d+", code)), default=0)
    limit = sys.get_int_max_str_digits()
    if longest <= limit:
        return _sanitize(code)
    sys.set_int_max_str_digits(longest + 1)
    try:
        return _sanitize(code)
    finally:
        sys.set_int_max_str_digits(limit)


def _sanitize(code: str) -> list[int]:
    r"""Parse polynomial string into coefficient list."""
    # Remove "f(x) = " prefix (with.
    match = re.match(r"f\(x\)\s*=\s*(.*)", code)
    if not match:
        return [0]

    code = match.group(1).strip()

    # Handle simple cases.
    if not code or code == "0":
        return [0]

    # Normalize the polynomial.
    code = code.replace(" ", "")

    # Add explicit coefficients and.
    code = re.sub(r"(?<!\d)x(?!\^)", "1x^1", code)  # x -> 1x^1.
    code = re.sub(r"x([+-])", r"x^1\1", code)  # x+ -> x^1+.

    # Find all terms with their.
    terms = {}

    # Find x^n terms first.
    for match in re.finditer(r"(-?\d*)x\^(\d+)", code):
        coeff_str = match.group(1)
        if not coeff_str:
            coeff = 1
        elif coeff_str == "-":
            coeff = -1
        else:
            coeff = int(coeff_str)
        degree = int(match.group(2))
        terms[degree] = coeff

    # Remove x terms from code to.
    code_without_x = re.sub(r"-?\d*x\^\d+", "", code)

    # Find constant terms.
    for match in re.finditer(r"-?\d+", code_without_x):
        coeff = int(match.group(0))
        terms[0] = coeff

    # If no terms found, return [0].
    if not terms:
        return [0]

    # Build coefficient list from.
    max_degree = max(terms.keys())
    return [terms.get(degree, 0) for degree in range(max_degree, -1, -1)]


# : Largest exponent a real.
# : ``range(1, 9)``.
# : enumerates ``p**v`` up to.
_PEEL_MAX_EXPONENT = 8

# : How many primes the peel.
# : degree.
# : instruction costs at least.
# : that can appear; the slack.
# : generated.
# : costs only that the root.
_PEEL_PRIME_SLACK = 2

# : Largest exponent a complex.
# : the ``range(1, 7)``.
_PEEL_MAX_IMAGINARY_EXPONENT = 6

# : Bound on the ``a`` a.
# : is a data operand -- a.
# : has no encoding bound the.
# : to something enormous is a.
# : real factor.
# : anything past it falls.
_PEEL_MAX_REAL_PART = 1 << 20

# : Prime the quadratic peel.
# : and that is not a detail: a.
# : square, so ``-q`` is a.
# : holds iff the modulus is.
# : encodable ``q`` admits the.
# : (mod 4)`` prime *none*.
# : Measured:.
# : while ``nextprime(2**32)``.
# : 4)`` -- recover none.
#: distinct mod it.
_PEEL_MODULUS = 18446744073709551629

# : Degree above which the.
# : instead of enumerating.
# : :data:`_PEEL_MODULUS`.
# : to evaluate the polynomial.
# : crossover and wins above it.
# : programs, enumerated.
# : 457ms, degree 118 is 687ms.
# : degree 314 is 5.3s against.
# : degree 2770 (dense n=10).
_NTT_MIN_DEGREE = 100

# : The two prime fields the.
# : k, g)`` with ``m = c * 2**k.
# : Both are ``1 (mod 4)`` so.
# : :data:`_PEEL_MODULUS`.
# : is where quadratic.
# : recoverable real part at.
# : and the second only.
# : pairs before the trial.
# : re-derives all four numbers.
_NTT_FIELDS = ((163841, 5, 15, 3), (65537, 1, 16, 3))

# : Modulus of the single-word.
# : candidate before the exact.
# : divides mod anything, so.
# : spurious candidate dies.
# : division over.
_TRIAL_MODULUS = (1 << 61) - 1

# : Nonzero bytes in a packed.
_NONZERO_BYTE = re.compile(rb"[^\x00]")


def _ntt_radix2(vec: list[int], modulus: int, root: int) -> list[int]:
    r"""Transform ``vec`` in place: ``out[t] = sum_j vec[j] * root**(j*t)``."""
    size = len(vec)
    j = 0
    for i in range(1, size):
        bit = size >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            vec[i], vec[j] = vec[j], vec[i]
    span = 2
    while span <= size:
        step = pow(root, size // span, modulus)
        half = span >> 1
        powers = [1] * half
        for i in range(1, half):
            powers[i] = powers[i - 1] * step % modulus
        for start in range(0, size, span):
            for i in range(half):
                low = vec[start + i]
                high = vec[start + i + half] * powers[i] % modulus
                vec[start + i] = (low + high) % modulus
                vec[start + i + half] = (low - high) % modulus
        span <<= 1
    return vec


def _roots_mod(coefficients: list[int], field: tuple[int, int, int, int]) -> set[int]:
    r"""Return every root of the polynomial in the prime field, exactly."""
    modulus, cofactor, log_size, generator = field
    group = modulus - 1
    size = 1 << log_size
    degree = len(coefficients) - 1
    folded = [0] * group
    for i, coefficient in enumerate(coefficients):
        j = (degree - i) % group
        folded[j] = (folded[j] + coefficient) % modulus
    sub_root = pow(generator, cofactor, modulus)
    parts = []
    for r in range(cofactor):
        part = folded[r::cofactor]
        part += [0] * (size - len(part))
        parts.append(_ntt_radix2(part, modulus, sub_root))
    if cofactor == 1:
        values = parts[0]
    else:
        values = [0] * group
        mask = size - 1
        for r, part in enumerate(parts):
            if r == 0:
                for t in range(group):
                    values[t] = part[t & mask]
            else:
                twiddle = pow(generator, r, modulus)
                w = 1
                for t in range(group):
                    values[t] = (values[t] + w * part[t & mask]) % modulus
                    w = w * twiddle % modulus
    roots = {pow(generator, t, modulus) for t, v in enumerate(values) if v == 0}
    if coefficients[-1] % modulus == 0:
        roots.add(0)
    return roots


def _iter_bits(mask: int, size: int) -> Iterator[int]:
    r"""Yield the set bit positions of ``mask``, a ``size``-bit integer."""
    raw = mask.to_bytes((size + 7) >> 3, "little")
    for match in _NONZERO_BYTE.finditer(raw):
        index = match.start()
        byte = raw[index]
        base = index << 3
        while byte:
            low = byte & -byte
            yield base + low.bit_length() - 1
            byte ^= low


def _quadratic_candidates_ntt(
    prime_count: int, root_sets: tuple[set[int], set[int]]
) -> set[tuple[int, int]]:
    r"""Propose ``(a, p**(2*b))`` pairs from the two fields' root sets."""
    (m0, _, _, g0), (m1, _, _, g1) = _NTT_FIELDS
    roots0, roots1 = root_sets
    i0 = pow(g0, (m0 - 1) // 4, m0)
    i1 = pow(g1, (m1 - 1) // 4, m1)
    mask0 = 0
    for r in roots0:
        mask0 |= 1 << r
    full = (1 << m0) - 1
    half = m0 // 2
    candidates: set[tuple[int, int]] = set()
    for index, base in enumerate(  # pragma: no branch
        sp.primerange(2, prime_count * prime_count + 3)
    ):
        if index >= prime_count:
            break
        power0 = base % m0
        power1 = base % m1
        square = base * base
        for _exponent in range(_PEEL_MAX_IMAGINARY_EXPONENT):
            delta = 2 * i0 * power0 % m0
            if delta:
                rotated = ((mask0 << delta) | (mask0 >> (m0 - delta))) & full
                hits = mask0 & rotated
                if hits:
                    offset0 = i0 * power0 % m0
                    offset1 = i1 * power1 % m1
                    for r in _iter_bits(hits, m0):
                        lifted = (r - offset0) % m0
                        real = lifted if lifted <= half else lifted - m0
                        if (real + offset1) % m1 in roots1 and (
                            real - offset1
                        ) % m1 in roots1:
                            candidates.add((real, square))
            power0 = power0 * base % m0
            power1 = power1 * base % m1
            square *= base * base
    return candidates


def _divide_quadratic_mod(
    coefficients: list[int], real: int, square: int
) -> list[int] | None:
    r""":func:`_divide_quadratic` over GF(:data:`_TRIAL_MODULUS`)."""
    modulus = _TRIAL_MODULUS
    b1 = -2 * real % modulus
    b0 = (real * real + square) % modulus
    size = len(coefficients)
    if size < 3:
        return None
    quotient: list[int] = []
    for index in range(size - 2):
        value = coefficients[index]
        if index >= 1:
            value -= b1 * quotient[index - 1]
        if index >= 2:
            value -= b0 * quotient[index - 2]
        quotient.append(value % modulus)
    linear = (coefficients[size - 2] - b1 * quotient[size - 3]) % modulus
    if size >= 4:
        linear = (linear - b0 * quotient[size - 4]) % modulus
    if linear:
        return None
    constant = (coefficients[size - 1] - b0 * quotient[size - 3]) % modulus
    if constant:
        return None
    return quotient


def _divide_out_quadratics(
    coefficients: list[int], candidates: set[tuple[int, int]]
) -> tuple[list[tuple[int, int]], list[int]]:
    r"""Divide the candidate quadratics out of the polynomial, exactly."""
    found: list[tuple[int, int]] = []
    remainder = coefficients
    remainder_mod = [k % _TRIAL_MODULUS for k in coefficients]
    for real, square in sorted(candidates):
        while len(remainder) >= 3:
            quotient_mod = _divide_quadratic_mod(remainder_mod, real, square)
            if quotient_mod is None:
                break
            quotient = _divide_quadratic(remainder, real, square)
            if quotient is None:
                break
            found.append((real, square))
            remainder = quotient
            remainder_mod = quotient_mod
    return found, remainder


def _divide_quadratic(
    coefficients: list[int], real: int, square: int
) -> list[int] | None:
    r"""Divide by ``(x - real)**2 + square`` exactly, or report that it."""
    b1 = -2 * real
    b0 = real * real + square
    size = len(coefficients)
    if size < 3:
        return None
    quotient: list[int] = []
    for index in range(size - 2):
        value = coefficients[index]
        if index >= 1:
            value -= b1 * quotient[index - 1]
        if index >= 2:
            value -= b0 * quotient[index - 2]
        quotient.append(value)
    # Both remainder positions have.
    # ``size >= 3`` from the guard.
    linear = coefficients[size - 2] - b1 * quotient[size - 3]
    if size >= 4:
        linear -= b0 * quotient[size - 4]
    if linear:
        return None
    constant = coefficients[size - 1] - b0 * quotient[size - 3]
    if constant:
        return None
    return quotient


def _peel_instruction_quadratics(
    coefficients: list[int],
) -> tuple[list[tuple[int, int]], list[int]]:
    r"""Divide out the complex instructions' quadratics, exactly."""
    if len(coefficients) < 3:
        return [], coefficients

    modulus = _PEEL_MODULUS
    x = sp.Symbol("x")
    try:
        field_poly = sp.Poly(coefficients, x, domain=sp.GF(modulus))
        _content, field_factors = field_poly.factor_list()
    except (sp.PolynomialError, NotImplementedError, ValueError):
        # The field factorization is.
        # nothing to peel and the.
        return [], coefficients

    roots: set[int] = set()
    for factor, _multiplicity in field_factors:
        if factor.degree() != 1:
            continue
        lead, constant = (int(k) % modulus for k in factor.all_coeffs())
        roots.add((-constant * pow(lead, -1, modulus)) % modulus)
    if not roots:
        return [], coefficients

    # One instruction is at least.
    # primes a program of this size.
    prime_count = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
    candidates: set[tuple[int, int]] = set()
    # `primerange(2, n*n + 3)`.
    # leaves on the `break` and.
    for index, base in enumerate(  # pragma: no branch
        sp.primerange(2, prime_count * prime_count + 3)
    ):
        if index >= prime_count:
            break
        for exponent in range(1, _PEEL_MAX_IMAGINARY_EXPONENT + 1):
            square = base ** (2 * exponent)
            root_of_negative = sp.sqrt_mod((-square) % modulus, modulus)
            if root_of_negative is None:
                # _PEEL_MODULUS is prime and 1.
                # residue; `square` is a.
                # a retuned modulus can land.
                # drop candidates.
                raise AssertionError(f"-{square} has no square root mod {modulus}")
            offset = int(root_of_negative)
            for root in roots:
                real_mod = (root - offset) % modulus
                # A genuine factor puts *both*.
                # ``real_mod + offset`` is.
                # other one is worth asking.
                if (real_mod - offset) % modulus not in roots:
                    continue
                real = real_mod if real_mod < modulus // 2 else real_mod - modulus
                if abs(real) > _PEEL_MAX_REAL_PART:
                    continue
                candidates.add((real, square))

    return _divide_out_quadratics(coefficients, candidates)


def _peel_prime_power_roots(
    coefficients: list[int],
    screen: Callable[[int], bool] | None = None,
) -> tuple[list[int], list[int]]:
    r"""Divide out the real roots that are prime powers, exactly."""
    found: list[int] = []
    limit = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
    # As above: the range always.
    for prime_index, base in enumerate(  # pragma: no branch
        sp.primerange(2, limit * limit + 3)
    ):
        if prime_index >= limit or len(coefficients) <= 1:
            break
        candidate = base
        for _exponent in range(_PEEL_MAX_EXPONENT):
            if screen is not None and not screen(candidate):
                candidate *= base
                continue
            while len(coefficients) > 1:
                # Horner: the polynomial's.
                value = 0
                for coefficient in coefficients:
                    value = value * candidate + coefficient
                if value:
                    break
                found.append(candidate)
                # Synthetic division by an.
                deflated = [coefficients[0]]
                for coefficient in coefficients[1:-1]:
                    deflated.append(coefficient + deflated[-1] * candidate)
                coefficients = deflated
            candidate *= base
    return found, coefficients


@functools.lru_cache(maxsize=256)
def _factor_roots(coefficients: tuple[int, ...]) -> tuple[_Root, ...]:
    r"""Recover the instruction roots by factoring the monic integer."""
    if len(coefficients) - 1 > _NTT_MIN_DEGREE:
        root_sets = tuple(_roots_mod(list(coefficients), f) for f in _NTT_FIELDS)

        def in_every_field(candidate: int) -> bool:
            return all(
                candidate % field[0] in roots
                for field, roots in zip(_NTT_FIELDS, root_sets, strict=True)
            )

        peeled, remainder = _peel_prime_power_roots(list(coefficients), in_every_field)
        roots = [_Root(root, 0) for root in peeled]
        if len(remainder) > 1:
            prime_count = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
            candidates = _quadratic_candidates_ntt(
                prime_count, (root_sets[0], root_sets[1])
            )
            quadratics, remainder = _divide_out_quadratics(remainder, candidates)
        else:
            quadratics = []
    else:
        peeled, remainder = _peel_prime_power_roots(list(coefficients))
        roots = [_Root(root, 0) for root in peeled]
        if len(remainder) > 1:
            quadratics, remainder = _peel_instruction_quadratics(remainder)
        else:
            quadratics = []

    for real, square in quadratics:
        imaginary = math.isqrt(square)
        roots.extend([_Root(real, imaginary), _Root(real, -imaginary)])
    if len(remainder) <= 1:
        return tuple(roots)

    x = sp.Symbol("x")
    poly = sp.Poly.from_list(remainder, x)
    _, factors = sp.factor_list(poly)

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
        # higher-degree factors encode.
    return tuple(roots)


def _find_roots(coefficients: list[int]) -> list[_Root]:
    r"""Find the roots of an exact-integer polynomial."""
    return list(_factor_roots(tuple(coefficients)))


@functools.lru_cache(maxsize=4)
def _parse_program(code: str) -> tuple[tuple[int, ...], ...]:
    r"""Recover the instruction list from a program's source, once."""
    cleaned_code = re.sub(r"[^\df(x)=+-^]", "", code)
    if cleaned_code[:5] != "f(x)=":
        raise ValueError("Polynomial program must start with 'f(x) = '")
    coefficients = sanitize(cleaned_code)
    roots = [k for k in _find_roots(coefficients) if k.imag >= 0]
    return tuple(tuple(instr) for instr in convert(roots))


# : The arithmetic.
# : Each is a function of the.
# : none of them reaches the.
_ARITH: tuple[Callable[[int, int], int], ...] = (
    lambda r, a: r + a,  # +=.
    lambda r, a: r - a,  # -=.
    lambda r, a: r * a,  # *=.
    lambda r, a: r // a,  # /=.
    lambda r, a: r % a,  # %=.
    lambda r, a: r**a,  # ^.
)

# : The branch conditions,.
# : instruction codes reach.
# : as the arithmetic above,.
# : to keep the indices lining.
# : hole and every entry has.
# :.
# : Key 1 -- the endif slot --.
# : reaches it.
# : final arm would need ``one.
# : would need a closer whose.
# : rejects as unmatched before.
# : every 2- and 3-instruction.
# : three register signs --.
# : calling the old slot.
_COND: dict[int, Callable[[int], bool]] = {
    0: lambda reg: reg > 0,
    2: lambda reg: reg < 0,
    3: lambda reg: not reg,
}

# : One instant of a run:.
# : the instruction cursor.
# : new pair rather than.
type _State = tuple[int, int]


def _advance(
    state: _State,
    instructions: list[list[int]],
    byte: int | None = None,
) -> tuple[_State, str | None]:
    r"""Return the state after one instruction, and anything it prints."""
    reg, ind = state
    instruction = instructions[ind]
    one = instruction[0]
    rest = instruction[1:] if len(instruction) > 1 else []
    output: str | None = None

    if two := ([*rest, 0])[0]:
        if one:
            reg = _ARITH[two - 1](reg, one)
        elif two - 1:
            reg = byte if byte else -1
        else:
            # Negative registers print as.
            # them, and clamping is this.
            output = chr(max(0, reg))
    elif one in [2, 6]:
        beg = instructions[brackets(instructions, ind)][0]
        if beg > 4 and _COND[(beg - 1) % 4](reg):
            ind = brackets(instructions, ind)
    elif not _COND[(one - 1) % 4](reg):
        ind = brackets(instructions, ind)

    return (reg, ind + 1), output


class _Machine:
    r"""Per-run Polynomial state: the instructions, the register, and the."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Recover ``code``'s instructions and start with a zero register."""
        self.io = io
        self.instructions = [list(instr) for instr in _parse_program(code)]
        self.ind = 0
        self.reg = 0

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the instructions."""
        return self.ind >= len(self.instructions)

    # The VM's language-shaped.
    # the register.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.reg]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.reg, self.io.position())

    def step(self) -> None:
        r"""Execute one instruction, advancing the cursor."""
        if self.halted:
            return
        instruction = self.instructions[self.ind]
        one = instruction[0]
        two = ([*instruction[1:], 0])[0]

        byte = None
        if two and not one and two - 1:
            # An empty line reads as -1,.
            # the original's ``input_str().
            # that NUL is 0, and ``0 or.
            val = self.io.input_str() + chr(0)
            byte = ord(val[0])

        (self.reg, self.ind), output = _advance(
            (self.reg, self.ind), self.instructions, byte
        )
        if output is not None:
            self.io.print_char(output)


def run(code: str, io: IO) -> None:
    r"""Execute a Polynomial program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
