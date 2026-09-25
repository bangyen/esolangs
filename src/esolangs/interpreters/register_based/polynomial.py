"""Polynomial interpreter implementation.

Polynomial programs are polynomial functions ``f(x) = ...``; real zeroes
are control flow and complex zeroes register operations on a single
integer register, in ascending-prime order.  The wiki's cat notes output
ignores negatives; this clamps to zero (a NUL), and EOF stores -1 as
specified -- as does reading a NUL byte, which keeps the register
distinguishable from an unset one.
Malformed programs raise :class:`ValueError`.  No instruction cap: a
growing register never repeats, and ``esolangs.run``'s ``timeout`` is
the guard.

Root recovery is exact: ``[a, b]`` is ``(x-a)^2 + p**(2*b)`` and ``[v]``
is ``x - p**v``, so the Gaussian integer roots are recovered exactly and
the values read off (a real root ``p**v`` passes 2**53 at ``p**8`` for
``p >= 100``, where ``complex`` would round).  The recovery lives in
:mod:`._polynomial_roots`: past ``_NTT_MIN_DEGREE`` candidates come from
roots modulo two small prime fields found by NTT; acceptance is exact
division either way.  Whatever the peels leave, and every sparse source,
goes through ``p``-adic lifting and a 2-D lattice behind the gap lemma,
so a cold parse is polynomial in the source length for every source.
:func:`_advance` is pure over ``(register,
cursor)``; the instructions are factored once when the machine is built.
"""

import functools
import re
import sys
from collections.abc import Callable, Sequence

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based._polynomial_roots import (
    _PEEL_MAX_EXPONENT,
    _PEEL_MAX_IMAGINARY_EXPONENT,
    _find_roots,
    _prime_power,
    _require_sympy,
    _Root,
    _sparse_roots,
)
from esolangs.interpreters.register_based._polynomial_roots import (
    prime as prime,
)


def _bracket_pairs(string: list[list[int]]) -> dict[int, int]:
    """Pair every control-flow bracket with its partner, in one pass.

    Codes 2 and 6 close, other single-element instructions open.  An
    unmatched bracket is left out: :func:`brackets` raises when it is
    *reached*, and rejecting at load would be a different language.
    """
    pairs: dict[int, int] = {}
    open_at: list[int] = []
    for i, instruction in enumerate(string):
        if len(instruction) != 1:
            continue
        if instruction[0] in (2, 6):
            if open_at:
                beg = open_at.pop()
                pairs[beg] = i
                pairs[i] = beg
        else:
            open_at.append(i)
    return pairs


def brackets(string: list[list[int]], pointer: int) -> int:
    """Find matching bracket for control flow statements.

    Raises :class:`ValueError` on an unmatched bracket.
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


def convert(pre: Sequence[complex | _Root]) -> list[list[int]]:
    """Convert polynomial roots to instruction codes using prime encoding.

    Compares plain integers, so an exact :class:`_Root` matches however wide.
    A real root ``p**v`` (``1 <= v <= 8``) is ``[v]``; a root ``a + p**b i``
    (``1 <= b <= 6``) is ``[a, b]``; anything else is dropped.  The codes
    come out grouped by ascending ``p`` and, within one prime, in
    ``(imag, real)`` order -- what scanning every integer up to the largest
    root did, but with each root recognised by its integer ``v``-th roots and
    a proven primality test, so the cost is polynomial in the roots' bits
    rather than in their values.
    """
    keyed: list[tuple[int, int, int, list[int]]] = []
    for root in pre:
        real, imag = round(root.real), round(root.imag)
        if imag:
            match = _prime_power(imag, _PEEL_MAX_IMAGINARY_EXPONENT)
            if match is not None:
                keyed.append((match[0], imag, real, [real, match[1]]))
        else:
            match = _prime_power(real, _PEEL_MAX_EXPONENT)
            if match is not None:
                keyed.append((match[0], 0, real, [match[1]]))
    keyed.sort(key=lambda entry: entry[:3])
    return [entry[3] for entry in keyed]


def sanitize(code: str) -> list[int]:
    """Parse polynomial string into coefficient list.

    CPython's 4300-digit cap is raised to the widest number here and put
    back, as the generator's ``format_coeffs`` does.
    """
    return _with_digit_limit(_sanitize, code)


def sanitize_terms(code: str) -> dict[int, int]:
    """Parse polynomial string into its sparse ``{degree: coefficient}`` map.

    Exactly the terms :func:`sanitize` densifies (an empty map is its
    ``[0]``), without the ``max_degree + 1`` list: ``x^1000000000000 - 1``
    is two entries here and a terabyte there.
    """
    return _with_digit_limit(_sanitize_terms, code)


def _with_digit_limit[T](parse: Callable[[str], T], code: str) -> T:
    """Run ``parse`` with CPython's digit cap lifted past ``code``'s widest number."""
    longest = max((len(run) for run in re.findall(r"\d+", code)), default=0)
    limit = sys.get_int_max_str_digits()
    if longest <= limit:
        return parse(code)
    sys.set_int_max_str_digits(longest + 1)
    try:
        return parse(code)
    finally:
        sys.set_int_max_str_digits(limit)


def _sanitize(code: str) -> list[int]:
    """Parse polynomial string into coefficient list."""
    terms = _sanitize_terms(code)
    # If no terms found, return [0]
    if not terms:
        return [0]

    # Build coefficient list from highest to lowest degree
    max_degree = max(terms.keys())
    return [terms.get(degree, 0) for degree in range(max_degree, -1, -1)]


def _sanitize_terms(code: str) -> dict[int, int]:
    """Parse polynomial string into ``{degree: coefficient}``, sparse.

    The last term written for a degree wins, and the last bare number is
    the constant even over an explicit ``x^0``.  Zero coefficients are
    kept: ``0x^5`` still sets the dense list's length.
    """
    # Remove "f(x) = " prefix (with or without surrounding spaces)
    match = re.match(r"f\(x\)\s*=\s*(.*)", code)
    if not match:
        return {}

    code = match.group(1).strip()

    # Handle simple cases
    if not code or code == "0":
        return {}

    # Normalize the polynomial string
    code = code.replace(" ", "")

    # Add explicit coefficients and degrees for x terms
    code = re.sub(r"(?<!\d)x(?!\^)", "1x^1", code)  # x -> 1x^1
    code = re.sub(r"x([+-])", r"x^1\1", code)  # x+ -> x^1+

    # Find all terms with their degrees and coefficients
    terms: dict[int, int] = {}

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

    return terms


#: A source whose degree is at most this many times its length is parsed
#: densely, through :func:`_find_roots` and its peels; the dense list is then
#: linear in the source.  Anything sparser -- ``x^1000000000000 - 1`` --
#: goes to :func:`_sparse_roots`, whose cost does not see the degree.
_DENSE_DEGREE_PER_CHAR = 2


@functools.lru_cache(maxsize=4)
def _parse_program(code: str) -> tuple[tuple[int, ...], ...]:
    """Recover the instruction list from a program's source, once.

    Keyed on the source: re-parsing a tens-of-megabytes program cost 0.9s
    per row on dense n=8.  Polynomial time in the source length for every
    source (``docs/proofs/polynomial.md``, "Cold parsing of arbitrary
    programs"): a dense source takes the peels, a sparse one never builds
    its coefficient list.
    """
    cleaned_code = re.sub(r"[^\df(x)=+-^]", "", code)
    if cleaned_code[:5] != "f(x)=":
        raise ValueError("Polynomial program must start with 'f(x) = '")
    _require_sympy()
    terms = sanitize_terms(cleaned_code)
    degree = max(terms, default=0)
    if degree <= _DENSE_DEGREE_PER_CHAR * len(cleaned_code):
        dense = [terms.get(power, 0) for power in range(degree, -1, -1)]
        roots = _find_roots(dense)
    elif not any(terms.values()):
        # The dense list would be ``degree + 1`` zeros, and the real peel
        # divides ``x - 2`` out of zero ``degree`` times: ``degree`` copies
        # of code ``[1]``, an output as long as the degree itself.
        return ((1,),) * degree
    else:
        roots = _sparse_roots(terms)
    return tuple(tuple(instr) for instr in convert([k for k in roots if k.imag >= 0]))


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


def _partner(
    instructions: list[list[int]], ind: int, pairs: dict[int, int] | None
) -> int:
    """Return ``ind``'s matching bracket, from the table where there is one.

    Falls back to the scan, which raises on an unmatched bracket as before.
    """
    if pairs is not None and ind in pairs:
        return pairs[ind]
    return brackets(instructions, ind)


def _advance(
    state: _State,
    instructions: list[list[int]],
    byte: int | None = None,
    pairs: dict[int, int] | None = None,
) -> tuple[_State, str | None]:
    """Return the state after one instruction, and anything it prints.

    Pure.  The cursor always advances by one, including after a taken jump
    lands on the bracket, so the body runs rather than the bracket re-testing.
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
        # One lookup, not two: the partner was being found twice over to
        # read its code and then to jump to it.
        partner = _partner(instructions, ind, pairs)
        beg = instructions[partner][0]
        if beg > 4 and _COND[(beg - 1) % 4](reg):
            ind = partner
    elif not _COND[(one - 1) % 4](reg):
        ind = _partner(instructions, ind, pairs)

    return (reg, ind + 1), output


class _Machine:
    """Per-run Polynomial state: the instructions, the register, and the cursor.

    ``halted`` once the cursor reaches the end; register and cursor are the
    complete state.
    """

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        """Recover ``code``'s instructions and start with a zero register."""
        self.io = io
        self.instructions = [list(instr) for instr in _parse_program(code)]
        # Bracket partners, paired once instead of scanned for per jump.
        self._pairs = _bracket_pairs(self.instructions)
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

        The shell: the byte is read before the transition, the character printed after.
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
            try:
                val = self.io.input_str() + chr(0)
            except EOFError:
                val = chr(0)
            byte = ord(val[0])

        (self.reg, self.ind), output = _advance(
            (self.reg, self.ind), self.instructions, byte, self._pairs
        )
        if output is not None:
            self.io.print_char(output)


def run(code: str, io: IO) -> None:
    """Execute a Polynomial program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
