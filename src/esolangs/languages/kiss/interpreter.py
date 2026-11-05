"""Interpreter for Kiss.

Hakerh400's 2023 combinator calculus with I/O.  A program is one expression
over ``K`` and ``S``: juxtaposition is application, left-associative, and
parentheses group.  ``K a b -> a`` and ``S a b c -> a c (b c)``; once the
head of the main expression has too few arguments to reduce, the head
performs I/O.

Commands:
    ``K`` halts with exit code 0; ``S`` halts with a nonzero exit code.
    ``K a`` outputs bit 0 and continues as ``a``.
    ``S a`` outputs bit 1 and continues as ``a``.
    ``S a b`` reads a bit and continues as ``a`` on 0, ``b`` on 1.

Input/output:
    The input is a string of ``0``/``1`` characters, ended by a newline or
    EOF; a read past its end raises EOFError.  Each output bit prints as a
    ``0``/``1`` character.  ``run`` returns the exit code, 0 or 1.

Errors:
    ProgramError: an empty program, empty or unbalanced parentheses, and any
    character that is not ``K``, ``S``, a parenthesis or whitespace.
    InputExhaustedError: a read past the input string.
    ArgumentError: an input character other than ``0``, ``1`` or a newline.

Decisions:
    * Only the head is rewritten, leftmost-outermost.  The page lets the two
      rules apply anywhere, but combinatory logic is confluent, so a
      reduction inside an argument cannot change what the head does next;
      head reduction is the order that reaches the head form whenever any
      order does.
    * Bits are ``0``/``1`` characters, the page giving no framing: Hot,
      Hakerh400's other I/O calculus, frames its bits the same way.
    * The single-bit cat ``S (K K) (S K)`` echoes its bit and exits 0.
    * The nonzero exit code is 1.
"""

from __future__ import annotations

from esolangs.exceptions import ArgumentError, InputExhaustedError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.combinators import State as _State
from esolangs.runtime.combinators import count, parse, stack, unwind
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: How many arguments each rewrite takes.
ARITY = {"K": 2, "S": 3}


def _advance(state: _State, bit: int | None) -> tuple[_State | int, int | None]:
    """Return the next state, or the exit code, and the bit it outputs.

    Pure: ``bit`` is the input bit when the head is ``S`` with two arguments.
    """
    head, args = state
    arity = ARITY[head]
    depth = count(args, arity)
    if depth == arity:
        assert args is not None
        assert args[1] is not None
        if head == "K":
            return unwind(args[0], args[1][1]), None
        x, (y, rest) = args[0], args[1]
        assert rest is not None
        z, tail = rest
        return unwind(x, (z, ((y, z), tail))), None
    if depth == 0:
        return int(head == "S"), None
    assert args is not None
    if depth == 1:
        return unwind(args[0], None), int(head == "S")
    assert args[1] is not None
    return unwind(args[0] if bit == 0 else args[1][0], None), None


class _Machine:
    """The expression, the input stream's state and the exit code."""

    #: The term tree is rebuilt as it runs; ``ip`` is the argument count.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.state: _State = unwind(
            parse(code, "".join(ARITY), "Kiss", "use K, S, parentheses and whitespace"),
            None,
        )
        self.ended = False
        self.bits = 0
        self.exit_code: int | None = None

    @property
    def halted(self) -> bool:
        return self.exit_code is not None

    @property
    def ip(self) -> tuple[int, ...]:
        """The number of arguments on the spine."""
        return (count(self.state[1], 1 << 62),)

    @property
    def stack(self) -> list[object]:
        """The head, then its arguments, first argument first."""
        return stack(self.state)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.state, self.ended, self.bits, self.exit_code, self.io.progress())

    def _read(self) -> int:
        """Return the next input bit."""
        if self.ended:
            raise InputExhaustedError(self.bits, self.bits, unit="bit")
        try:
            char = chr(self.io.input_char())
        except EOFError:
            char = "\n"
        if char == "\n":
            self.ended = True
            raise InputExhaustedError(self.bits, self.bits, unit="bit")
        if char not in "01":
            raise syntax_error(
                f"Kiss input must be a binary string, got {char!r}",
                "supply 0 and 1 characters, for example 1011",
                error_type=ArgumentError,
            )
        self.bits += 1
        return int(char)

    def step(self) -> None:
        if self.halted:
            return
        head, args = self.state
        bit = None
        if head == "S" and count(args, 3) == 2:
            bit = self._read()
        result, out = _advance(self.state, bit)
        if isinstance(result, int):
            self.exit_code = result
            return
        self.state = result
        if out is not None:
            self.io.print_str(str(out))


def run(code: str, io: IO) -> int:
    """Run a Kiss program on the binary string read from ``io``.

    Returns the exit code: 0 after ``K``, 1 after ``S``.
    """
    machine = _Machine(code, io)
    drive(machine)
    assert machine.exit_code is not None
    return machine.exit_code


if __name__ == "__main__":
    script_main(run)
