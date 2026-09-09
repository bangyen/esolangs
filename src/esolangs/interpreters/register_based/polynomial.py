"""Polynomial interpreter implementation.

Polynomial is an esoteric programming language in which each program
is a polynomial function. Language statements are executed based on the zeroes of the
function, with both real and complex zeroes allowed. The language operates on a single
integer register with operations determined by the mathematical properties of the roots.

The language features:
- Programs as polynomial functions in the form f(x) = ...
- Real zeroes for control flow (if/while statements)
- Complex zeroes for register operations (arithmetic, I/O)
- Special encoding using ascending primes for execution order
- Single integer register for all operations

The wiki's cat program notes that output ignores negative register values;
this interpreter clamps them to zero (printing a NUL) instead, and it raises
:class:`EOFError` on exhausted input rather than halting with -1.

There is no per-run instruction cap here.  The machine is step-capable, so
``run_until_halt_or_cycle`` proves a hang immediately for the ordinary case
-- a fixed instruction list and a register cycling through a bounded set of
values revisits a state -- but a loop that keeps growing the register
without bound never does, and the state-cycle detector cannot terminate on
that class by construction.  ``esolangs.run``'s wall-clock ``timeout`` is
the uniform guard for it, rather than a step count local to this
interpreter.

Root recovery: every instruction contributes a factor of a known shape to the
program's monic integer polynomial -- a complex instruction ``[a, b]`` is the
quadratic ``(x-a)^2 + p**(2*b)`` (so the linear coefficient gives ``a`` and the
constant term minus ``a^2`` is an exact square ``p**(2*b)``), and a real
instruction ``[v]`` is the linear factor ``x - p**v``.  The interpreter
therefore factors the polynomial over the integers with ``sympy`` and reads the
instruction values straight off the factors, exactly -- no floating point, so
the wide root spreads that defeated float64 root-finding are irrelevant.

Malformed programs raise :class:`ValueError`.

The interpreter runs on a :class:`_Machine` (the recovered instructions, the
integer register, and the instruction cursor), so it is step-capable:
``step()`` executes one instruction and ``halted`` is true once the cursor
reaches the end of the instructions.

The execution model is a pure function over an immutable ``_State``: the
register and the cursor, as a plain pair.  :func:`_advance` maps a state and
the instruction table to the next state and never mutates what it is given;
:meth:`_Machine.step` rebinds the two fields from what it returned, so the
mutation lives in exactly one place.

The instructions stay out of the state -- Polynomial never rewrites its own
program, and recovering them means factoring the polynomial, which is done
once when the machine is built.  The two ports stay in the shell: an
instruction prints or reads at most once, so the byte can be read before
the transition and the printed value handed back after it.
"""

import functools
import math
import re
import sys
from collections.abc import Callable

import sympy as sp

from esolangs.interpreters.io import IO


def prime(number: int) -> bool:
    """Check if a number is prime."""
    if number < 2:
        return False
    return all(number % val for val in range(2, math.isqrt(number) + 1))


def brackets(string: list[list[int]], pointer: int) -> int:
    """Find matching bracket for control flow statements.

    Raises :class:`ValueError` if the bracket has no partner: the wiki defines
    control-flow brackets only for matched pairs, so an unmatched one is a
    malformed program.
    """
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


def convert(pre: list[complex]) -> list[list[int]]:
    """Convert polynomial roots to instruction codes using prime encoding."""
    rounded_roots = [complex(round(k.real), round(k.imag)) for k in pre]
    # Sort by imaginary part, then by real part
    sorted_roots = sorted(rounded_roots, key=lambda x: (x.imag, x.real))
    post: list[list[int]] = []
    num = 2

    # A prime power p**v (v >= 1) is always >= p, so once num exceeds the
    # largest root magnitude no further root can match.
    if rounded_roots:
        limit = max(max(abs(k.imag), abs(k.real)) for k in rounded_roots)
    else:
        limit = 0

    while sorted_roots and num <= limit + 1:
        if not prime(num):
            num += 1
            continue
        for root in sorted_roots[:]:  # Use slice to avoid modification during iteration
            if im := root.imag:
                for val in range(1, 7):
                    if im == num**val:
                        sorted_roots.remove(root)
                        post.append([int(root.real), val])
                        break
            else:
                for val in range(1, 9):
                    if root.real == num**val:
                        sorted_roots.remove(root)
                        post.append([val])
                        break
        num += 1
    return post


def sanitize(code: str) -> list[int]:
    """Parse polynomial string into coefficient list.

    CPython's ``int``/``str`` digit cap (4300 by default) is a DoS guard
    against quadratic conversions rather than anything Polynomial says, and a
    program's coefficients grow with its instruction count -- so the cap is
    raised to fit the widest number in this source text and put straight
    back, the way the generator's ``format_coeffs`` does on the way out.
    Without it a program the generator can write is one the interpreter
    refuses to read.
    """
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
    """Parse polynomial string into coefficient list."""
    # Remove "f(x) = " prefix (with or without surrounding spaces)
    match = re.match(r"f\(x\)\s*=\s*(.*)", code)
    if not match:
        return [0]

    code = match.group(1).strip()

    # Handle simple cases
    if not code or code == "0":
        return [0]

    # Normalize the polynomial string
    code = code.replace(" ", "")

    # Add explicit coefficients and degrees for x terms
    code = re.sub(r"(?<!\d)x(?!\^)", "1x^1", code)  # x -> 1x^1
    code = re.sub(r"x([+-])", r"x^1\1", code)  # x+ -> x^1+

    # Find all terms with their degrees and coefficients
    terms = {}

    # Find x^n terms first
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

    # Remove x terms from code to find constants
    code_without_x = re.sub(r"-?\d*x\^\d+", "", code)

    # Find constant terms (remaining numbers)
    for match in re.finditer(r"-?\d+", code_without_x):
        coeff = int(match.group(0))
        terms[0] = coeff

    # If no terms found, return [0]
    if not terms:
        return [0]

    # Build coefficient list from highest to lowest degree
    max_degree = max(terms.keys())
    return [terms.get(degree, 0) for degree in range(max_degree, -1, -1)]


#: Largest exponent a real instruction's root can carry, from the
#: ``range(1, 9)`` :func:`convert` reads them back with.  The peel below
#: enumerates ``p**v`` up to this, so the two agree by construction.
_PEEL_MAX_EXPONENT = 8

#: How many primes the peel enumerates, as a multiple of the polynomial's
#: degree.  A program assigns its k-th instruction the k-th prime and each
#: instruction costs at least one degree, so the degree bounds the primes
#: that can appear; the slack covers a program written by hand rather than
#: generated.  Candidates are cheap -- one Horner pass each -- and a miss
#: costs only that the root stays in the tail.
_PEEL_PRIME_SLACK = 2

#: Largest exponent a complex instruction's imaginary part can carry, from
#: the ``range(1, 7)`` :func:`convert` reads it back with.
_PEEL_MAX_IMAGINARY_EXPONENT = 6

#: Bound on the ``a`` a quadratic peel will lift out of its residue.  ``a``
#: is a data operand -- a table index, an offset, a codepoint delta -- so it
#: has no encoding bound the way an exponent does, and a residue that lifts
#: to something enormous is a pairing that happened to line up rather than a
#: real factor.  Generously past the ``-3 .. 50`` a dense n=6 table uses;
#: anything past it falls through to ``factor_list`` like any other miss.
_PEEL_MAX_REAL_PART = 1 << 20

#: Prime the quadratic peel finds roots modulo.  It must be ``1 (mod 4)``,
#: and that is not a detail: a factor's ``q`` is ``p**(2*b)``, a perfect
#: square, so ``-q`` is a quadratic residue exactly when ``-1`` is -- which
#: holds iff the modulus is ``1 (mod 4)``.  Under such a prime *every*
#: encodable ``q`` admits the square root the pairing needs; under a ``3
#: (mod 4)`` prime *none* does, and the peel silently finds nothing.
#: Measured: ``nextprime(2**64)`` recovers 51 of 51 sampled ``q`` values,
#: while ``nextprime(2**32)`` and ``nextprime(2**128)`` -- both ``3 (mod
#: 4)`` -- recover none.  Wide enough that distinct small ``a`` stay
#: distinct mod it.
_PEEL_MODULUS = 18446744073709551629


def _divide_quadratic(
    coefficients: list[int], real: int, square: int
) -> list[int] | None:
    """Divide by ``(x - real)**2 + square`` exactly, or report that it does not.

    Long division by the monic quadratic ``x**2 + b1*x + b0``, on the integer
    coefficient list rather than a ``Poly``: each quotient coefficient is the
    dividend's minus what the two previous quotient coefficients contribute
    at that position.  Staying with plain integers is the whole point -- the
    same reason :func:`_peel_prime_power_roots` is cheap -- since a ``Poly``
    division at this degree costs orders of magnitude more.

    ``None`` means a nonzero remainder, so the caller must not take it.
    """
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
    # Both remainder positions have to vanish for this to be a factor.
    # ``size >= 3`` from the guard above, so that much always applies.
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
    """Divide out the complex instructions' quadratics, exactly.

    A complex instruction contributes ``(x - a)**2 + p**(2*b)``, and unlike a
    real one its root needs *two* parameters: ``b`` is small (at most
    :data:`_PEEL_MAX_IMAGINARY_EXPONENT`) but ``a`` is a data operand with no
    encoding bound, so enumerating pairs is hopeless -- a dense n=6 table
    would need ~158000 trial divisions against a degree-254 polynomial.

    So ``a`` is *solved for* rather than guessed.  Modulo
    :data:`_PEEL_MODULUS` the factor's roots are ``a ± sqrt(-q)``, so one
    root-finding pass over the field yields every root, and for each
    candidate ``q`` a root ``r`` proposes ``a = r - sqrt(-q)`` -- confirmed
    only when the partner root is present too.  That search is integer
    arithmetic and set lookups; no polynomial is touched until a candidate
    survives it.

    Soundness is the same bargain the real peel strikes: a pair is accepted
    only because ``(x - a)**2 + q`` divides the polynomial *exactly*, which
    makes it a genuine factor whatever wrote the program.  Everything the
    search cannot see -- a ``q`` that is not ``p**(2*b)``, an ``a`` past
    :data:`_PEEL_MAX_REAL_PART`, a factor of degree other than two, roots
    that do not pair -- stays in the returned remainder for ``factor_list``.
    Incomplete, never wrong.

    Measured on the dense n=6 table's degree-254 remainder: 3.16s to find
    the roots, 0.26s to build candidates (1524 residue tests yielding
    exactly 127 candidates for 127 quadratics), 0.02s to verify, against
    35.55s for ``factor_list`` on the same input.
    """
    if len(coefficients) < 3:
        return [], coefficients

    modulus = _PEEL_MODULUS
    x = sp.Symbol("x")
    try:
        field_poly = sp.Poly(coefficients, x, domain=sp.GF(modulus))
        _content, field_factors = field_poly.factor_list()
    except (sp.PolynomialError, NotImplementedError, ValueError):
        # The field factorization is the whole search; without it there is
        # nothing to peel and the caller's factor_list still sees everything.
        return [], coefficients

    roots: set[int] = set()
    for factor, _multiplicity in field_factors:
        if factor.degree() != 1:
            continue
        lead, constant = (int(k) % modulus for k in factor.all_coeffs())
        roots.add((-constant * pow(lead, -1, modulus)) % modulus)
    if not roots:
        return [], coefficients

    # One instruction is at least two degrees, so the degree bounds the
    # primes a program of this size can have reached.
    prime_count = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
    candidates: set[tuple[int, int]] = set()
    # `primerange(2, n*n + 3)` always holds more than `n` primes, so the loop
    # leaves on the `break` and never by running out.
    for index, base in enumerate(  # pragma: no branch
        sp.primerange(2, prime_count * prime_count + 3)
    ):
        if index >= prime_count:
            break
        for exponent in range(1, _PEEL_MAX_IMAGINARY_EXPONENT + 1):
            square = base ** (2 * exponent)
            root_of_negative = sp.sqrt_mod((-square) % modulus, modulus)
            if root_of_negative is None:
                # _PEEL_MODULUS is prime and 1 mod 4, so -1 is a quadratic
                # residue; `square` is a square, so -square is one too.  Only
                # a retuned modulus can land here, and skipping would silently
                # drop candidates.
                raise AssertionError(f"-{square} has no square root mod {modulus}")
            offset = int(root_of_negative)
            for root in roots:
                real_mod = (root - offset) % modulus
                # A genuine factor puts *both* of its roots in the set.
                # ``real_mod + offset`` is ``root`` itself, so only the
                # other one is worth asking about.
                if (real_mod - offset) % modulus not in roots:
                    continue
                real = real_mod if real_mod < modulus // 2 else real_mod - modulus
                if abs(real) > _PEEL_MAX_REAL_PART:
                    continue
                candidates.add((real, square))

    found: list[tuple[int, int]] = []
    remainder = coefficients
    for real, square in sorted(candidates):
        while len(remainder) >= 3:
            quotient = _divide_quadratic(remainder, real, square)
            if quotient is None:
                break
            found.append((real, square))
            remainder = quotient
    return found, remainder


def _peel_prime_power_roots(
    coefficients: list[int],
) -> tuple[list[int], list[int]]:
    """Divide out the real roots that are prime powers, exactly.

    A real instruction contributes ``x - p**v``, so its root is a prime
    power -- and finding those needs no factorization at all.  Evaluating
    the polynomial at a candidate (Horner, one pass) proves the factor when
    the result is zero, and synthetic division then deflates the degree by
    one.  Both are exact integer arithmetic.

    This is only ever a *head start*: a candidate is accepted solely because
    the polynomial vanishes there, which makes ``x - candidate`` a genuine
    factor whatever wrote the program.  Anything the enumeration misses -- a
    root that is not a prime power, a prime past the window, an exponent past
    :data:`_PEEL_MAX_EXPONENT`, a negative root -- simply stays in the
    returned remainder, which its caller still hands to ``factor_list``.  So
    the peel can be incomplete but never wrong, and the recovered root
    multiset is what factoring alone would have produced.

    Worth it because factoring is superlinear in the degree while a peel is
    linear: on the dense n=6 table (degree 314, a 1677-digit constant term)
    it removes 60 roots in 0.66s, and the 82.65s factorization of the whole
    becomes 35.27s on the degree-254 remainder.
    """
    found: list[int] = []
    limit = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
    # As above: the range always outlasts `limit`, so this ends on the `break`.
    for prime_index, base in enumerate(  # pragma: no branch
        sp.primerange(2, limit * limit + 3)
    ):
        if prime_index >= limit or len(coefficients) <= 1:
            break
        candidate = base
        for _exponent in range(_PEEL_MAX_EXPONENT):
            while len(coefficients) > 1:
                # Horner: the polynomial's value at ``candidate``.
                value = 0
                for coefficient in coefficients:
                    value = value * candidate + coefficient
                if value:
                    break
                found.append(candidate)
                # Synthetic division by an exact root, so it stays exact.
                deflated = [coefficients[0]]
                for coefficient in coefficients[1:-1]:
                    deflated.append(coefficient + deflated[-1] * candidate)
                coefficients = deflated
            candidate *= base
    return found, coefficients


@functools.lru_cache(maxsize=256)
def _factor_roots(coefficients: tuple[int, ...]) -> tuple[complex, ...]:
    """Recover the instruction roots by factoring the monic integer polynomial.

    A valid program is a product of linear factors ``x - p**v`` (real
    instructions) and quadratics ``(x-a)**2 + p**(2*b)`` (complex
    instructions).  ``sympy.factor_list`` returns exactly those factors, so
    the instruction values come out exactly.  A factor of any other shape
    encodes no instruction and is ignored.

    Both instruction shapes are divided out first, by
    :func:`_peel_prime_power_roots` and then
    :func:`_peel_instruction_quadratics`, so ``factor_list`` sees only what
    neither recognised.  Both are pure head starts -- each accepts a factor
    only on an exact division, and leaves what it cannot see in the
    remainder -- so see those functions for why they cannot change the
    answer.  On a generated program they usually account for everything and
    ``factor_list`` is never called at all.
    """
    peeled, remainder = _peel_prime_power_roots(list(coefficients))
    roots: list[complex] = [complex(root, 0) for root in peeled]
    if len(remainder) <= 1:
        return tuple(roots)

    quadratics, remainder = _peel_instruction_quadratics(remainder)
    for real, square in quadratics:
        imaginary = math.isqrt(square)
        roots.extend([complex(real, imaginary), complex(real, -imaginary)])
    if len(remainder) <= 1:
        return tuple(roots)

    x = sp.Symbol("x")
    poly = sp.Poly.from_list(remainder, x)
    _, factors = sp.factor_list(poly)

    for factor, multiplicity in factors:
        degree = factor.degree()
        if degree == 1:
            a, b = (int(k) for k in factor.all_coeffs())
            roots.extend([complex(-b // a, 0)] * multiplicity)
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
            roots.extend([complex(real, imag), complex(real, -imag)] * multiplicity)
        # higher-degree factors encode no instruction; skip
    return tuple(roots)


def _find_roots(coefficients: list[int]) -> list[complex]:
    """Find the roots of an exact-integer polynomial."""
    return list(_factor_roots(tuple(coefficients)))


#: The arithmetic instructions, in the order their codes select them.
#: Each is a function of the register and the instruction's operand, so
#: none of them reaches the machine the way the old bound lambdas did.
_ARITH: tuple[Callable[[int, int], int], ...] = (
    lambda r, a: r + a,  # +=
    lambda r, a: r - a,  # -=
    lambda r, a: r * a,  # *=
    lambda r, a: r // a,  # /=
    lambda r, a: r % a,  # %=
    lambda r, a: r**a,  # ^
)

#: The branch conditions, keyed by ``(code - 1) % 4`` the way the
#: instruction codes reach them.  The old table held these in the same list
#: as the arithmetic above, with an integer ``0`` wedged into the endif slot
#: to keep the indices lining up; splitting them means neither table has a
#: hole and every entry has one signature.
#:
#: Key 1 -- the endif slot -- is deliberately absent, because nothing
#: reaches it.  ``convert`` emits single-element codes 1..8 only, so the
#: final arm would need ``one == 10`` and cannot get it, and the bracket arm
#: would need a closer whose *partner* is also a 6, which ``brackets``
#: rejects as unmatched before any condition is consulted.  Enumerating
#: every 2- and 3-instruction table over 1..8 from every cursor and all
#: three register signs -- 4992 combinations -- reaches it zero times, and
#: calling the old slot directly does raise, so the sweep's probe fires.
_COND: dict[int, Callable[[int], bool]] = {
    0: lambda reg: reg > 0,
    2: lambda reg: reg < 0,
    3: lambda reg: not reg,
}

#: One instant of a run: ``(reg, ind)`` -- the single integer register and
#: the instruction cursor.  A value, not a record: :func:`_advance` returns a
#: new pair rather than editing one in place.
type _State = tuple[int, int]


def _advance(
    state: _State,
    instructions: list[list[int]],
    byte: int | None = None,
) -> tuple[_State, str | None]:
    """Return the state after one instruction, and anything it prints.

    Pure: it reads ``state`` and returns a new one, and reaches no ``IO``.
    The character an output instruction would write is reported to the
    caller rather than printed here, and an input instruction's byte
    arrives as ``byte``.

    The cursor always advances by one at the end, including after a branch
    has moved it to its partner -- a taken jump lands *on* the bracket and
    steps past it, which is what makes the body run rather than the bracket
    re-test itself.
    """
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
            # Negative registers print as NUL: the wiki says output ignores
            # them, and clamping is this interpreter's documented reading.
            output = chr(max(0, reg))
    elif one in [2, 6]:
        beg = instructions[brackets(instructions, ind)][0]
        if beg > 4 and _COND[(beg - 1) % 4](reg):
            ind = brackets(instructions, ind)
    elif not _COND[(one - 1) % 4](reg):
        ind = brackets(instructions, ind)

    return (reg, ind + 1), output


class _Machine:
    """Per-run Polynomial state: the instructions, the register, and the cursor.

    ``step()`` executes one instruction; ``halted`` is true once the cursor
    reaches the end of the instructions.  The VM and the state-cycle hang
    detector expose this object (the instruction list is fixed, so the
    register and cursor are the complete state).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Recover ``code``'s instructions and start with a zero register."""
        self.io = io
        # Clean the input code
        cleaned_code = re.sub(r"[^\df(x)=+-^]", "", code)
        if cleaned_code[:5] != "f(x)=":
            raise ValueError("Polynomial program must start with 'f(x) = '")

        # Parse polynomial and get coefficients
        coefficients = sanitize(cleaned_code)

        # Find roots and filter for non-negative imaginary parts
        roots = [k for k in _find_roots(coefficients) if k.imag >= 0]

        # Convert roots to instruction codes
        self.instructions = convert(roots)

        self.ind = 0
        self.reg = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the instructions."""
        return self.ind >= len(self.instructions)

    # The VM's language-shaped view: Single register + cursor; ip the cursor, memory
    # the register.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.reg]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.reg, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the cursor.

        The two ports live here rather than in the transition: this is the
        shell.  An instruction reads or prints at most once, so the byte can
        be read before the transition runs and the character it reports
        printed after.
        """
        if self.halted:
            return
        instruction = self.instructions[self.ind]
        one = instruction[0]
        two = ([*instruction[1:], 0])[0]

        byte = None
        if two and not one and two - 1:
            # An empty line reads as -1, which is what the trailing NUL in
            # the original's ``input_str() + chr(0)`` produced: ``ord`` of
            # that NUL is 0, and ``0 or -1`` is -1.
            val = self.io.input_str() + chr(0)
            byte = ord(val[0])

        (self.reg, self.ind), output = _advance(
            (self.reg, self.ind), self.instructions, byte
        )
        if output is not None:
            self.io.print_char(output)


def run(code: str, io: IO) -> None:
    """Execute a Polynomial program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
