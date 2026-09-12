r"""Interpreter for Factor."""

import re
import sys

import sympy

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.brainfuck import _Machine as _BFMachine

_RESIDUE = {1: ">", 2: "<", 3: "+", 4: "-", 5: ".", 6: ",", 7: "[", 8: "]"}

# : Factor has no execution.
type _State = _BFMachine


# : How far :func:`_factorint`.
# : while the residue is still.
# : ceiling on the primes it.
_SIEVE_CHUNK = 20000


def _parse(digits: str) -> int:
    r"""Read the program's integer, lifting CPython's digit limit to fit it."""
    limit = sys.get_int_max_str_digits()
    if len(digits) <= limit:
        return int(digits)
    sys.set_int_max_str_digits(len(digits) + 1)
    try:
        return int(digits)
    finally:
        sys.set_int_max_str_digits(limit)


def _factorint(number: int) -> dict[int, int]:
    r"""Factorize ``number``, dividing small primes out before sympy sees."""
    factors: dict[int, int] = {}
    start = 2
    checked = 0
    while number > 1:
        stop = start + _SIEVE_CHUNK
        divided = False
        for prime in sympy.sieve.primerange(start, stop):
            if number == 1:
                # The chunk finished the number.
                # test, and the root check.
                break
            if prime * prime > number:
                # Nothing below the root.
                # prime -- the one case worth.
                factors[number] = factors.get(number, 0) + 1
                return factors
            while not number % prime:
                factors[prime] = factors.get(prime, 0) + 1
                number //= prime
                divided = True
        if number == 1:
            break
        if divided:
            # The sieve is still finding.
            # pay ``isprime`` on a residue.
            start = stop
            continue
        # A barren chunk: every.
        # the residue's primality is.
        # only once per value, since.
        # otherwise re-ask the same.
        if number != checked:
            checked = number
            if sympy.isprime(number):
                factors[number] = factors.get(number, 0) + 1
                return factors
        # Composite, with every factor.
        # only sound move: handing it.
        # make the barren chunk a.
        # large composite that sends.
        # minutes -- the very failure.
        start = stop
    return factors


def decode(number: int) -> str:
    r"""Decode a Factor integer into its brainfuck instruction string."""
    factors = sorted(_factorint(number).items())
    return "".join(_RESIDUE[p % 11] * exp for p, exp in factors if p % 11 in _RESIDUE)


class _Machine:
    r"""Per-run Factor state: the decoded brainfuck machine."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Decode ``code`` and reset the underlying brainfuck machine."""
        self.io = io
        digits = re.sub(r"[^0-9]", "", code)
        number = _parse(digits) if digits else 1
        self.state: _State = _BFMachine(decode(number), io)

    @property
    def bf(self) -> _State:
        r"""The delegated Brainfuck state."""
        return self.state

    @property
    def halted(self) -> bool:
        return self.bf.halted

    # The VM's language-shaped.
    # the tape.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.bf.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.bf.tape)

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    # The growth detector's view,.
    # Factor has no execution.
    # to brainfuck and runs that --.
    # for.
    # of its own.

    @property
    def ptr(self) -> int:
        r"""The decoded machine's cell pointer."""
        return self.bf.ptr

    @property
    def tape(self) -> tuple[int, ...]:
        r"""The decoded machine's committed cells."""
        return self.bf.tape

    def input_position(self) -> int:
        r"""Report the decoded machine's input cursor."""
        return self.bf.input_position()

    def step(self) -> None:
        self.bf.step()

    def snapshot(self) -> tuple[object, ...]:
        return self.bf.snapshot()


def run(code: str, io: IO) -> None:
    r"""Run a Factor program, executing the brainfuck it decodes to."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
