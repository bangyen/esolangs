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
:class:`EOFError` on exhausted input rather than halting with -1.  A
10000-step cap guards non-terminating programs (the machine is step-capable,
so the state-cycle hang detector proves the cycle class immediately and the
cap stays as the ``run()`` backstop for the rest).

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
register and the cursor, as a plain pair.  :func:`_step` maps a state and
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


@functools.lru_cache(maxsize=256)
def _factor_roots(coefficients: tuple[int, ...]) -> tuple[complex, ...]:
    """Recover the instruction roots by factoring the monic integer polynomial.

    A valid program is a product of linear factors ``x - p**v`` (real
    instructions) and quadratics ``(x-a)**2 + p**(2*b)`` (complex
    instructions).  ``sympy.factor_list`` returns exactly those factors, so
    the instruction values come out exactly.  A factor of any other shape
    encodes no instruction and is ignored.
    """
    x = sp.Symbol("x")
    poly = sp.Poly.from_list(list(coefficients), x)
    _, factors = sp.factor_list(poly)

    roots: list[complex] = []
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
#: the instruction cursor.  A value, not a record: :func:`_step` returns a
#: new pair rather than editing one in place.
type _State = tuple[int, int]


def _step(
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

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.reg, self.ind)

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

        (self.reg, self.ind), output = _step(self._state, self.instructions, byte)
        if output is not None:
            self.io.print_char(output)


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Execute a Polynomial program, halting after ``limit`` instructions."""
    machine = _Machine(code, io)
    for _ in range(limit):
        if machine.halted:
            return
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
