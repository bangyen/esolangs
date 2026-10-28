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
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: A combinator, or ``(function, argument)``.
type _Term = str | tuple[_Term, _Term]
#: The arguments, first on top: a persistent stack, so a step is O(1).
type _Args = tuple[_Term, _Args] | None
#: The head combinator and its arguments.
type _State = tuple[str, _Args]

#: How many arguments each rewrite takes.
ARITY = {"K": 2, "S": 3}
_EMPTY = "a Kiss program needs at least one combinator"


def _parse(code: str) -> _Term:
    """Return the one expression ``code`` spells, left-associated."""
    groups: list[list[_Term]] = [[]]
    for char in code:
        if char.isspace():
            continue
        if char == "(":
            groups.append([])
        elif char == ")":
            if len(groups) == 1:
                raise syntax_error(
                    "a Kiss ')' has no matching '('", "balance the parentheses"
                )
            items = groups.pop()
            if not items:
                raise syntax_error(
                    "Kiss parentheses must enclose an expression",
                    "remove the empty () or put a combinator inside",
                )
            groups[-1].append(_applied(items))
        elif char in ARITY:
            groups[-1].append(char)
        else:
            raise syntax_error(
                f"{char!r} is not a Kiss combinator",
                "use K, S, parentheses and whitespace",
            )
    if len(groups) > 1:
        raise syntax_error("a Kiss '(' has no matching ')'", "balance the parentheses")
    if not groups[0]:
        raise syntax_error(_EMPTY, "write at least one combinator, for example K")
    return _applied(groups[0])


def _applied(items: list[_Term]) -> _Term:
    """Return ``items`` applied left to right."""
    term = items[0]
    for item in items[1:]:
        term = (term, item)
    return term


def _unwind(term: _Term, args: _Args) -> _State:
    """Return ``term`` applied to ``args`` as a head and its arguments."""
    while not isinstance(term, str):
        term, args = term[0], (term[1], args)
    return term, args


def _count(args: _Args, limit: int) -> int:
    """Return how many arguments there are, counting at most ``limit``."""
    depth = 0
    while args is not None and depth < limit:
        depth, args = depth + 1, args[1]
    return depth


def _advance(state: _State, bit: int | None) -> tuple[_State | int, int | None]:
    """Return the next state, or the exit code, and the bit it outputs.

    Pure: ``bit`` is the input bit when the head is ``S`` with two arguments.
    """
    head, args = state
    depth = _count(args, ARITY[head])
    if depth == ARITY[head]:
        assert args is not None
        assert args[1] is not None
        if head == "K":
            return _unwind(args[0], args[1][1]), None
        x, (y, rest) = args[0], args[1]
        assert rest is not None
        z, tail = rest
        return _unwind(x, (z, ((y, z), tail))), None
    if depth == 0:
        return int(head == "S"), None
    assert args is not None
    if depth == 1:
        return _unwind(args[0], None), int(head == "S")
    assert args[1] is not None
    return _unwind(args[0] if bit == 0 else args[1][0], None), None


class _Machine:
    """The expression, the input stream's state and the exit code."""

    #: The term tree is rebuilt as it runs; ``ip`` is the argument count.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.state: _State = _unwind(_parse(code), None)
        self.ended = False
        self.bits = 0
        self.exit_code: int | None = None

    @property
    def halted(self) -> bool:
        return self.exit_code is not None

    @property
    def ip(self) -> tuple[int, ...]:
        """The number of arguments on the spine."""
        return (_count(self.state[1], 1 << 62),)

    @property
    def stack(self) -> list[object]:
        """The head, then its arguments, first argument first."""
        cells: list[object] = [self.state[0]]
        args = self.state[1]
        while args is not None:
            cells.append(args[0])
            args = args[1]
        return cells

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
        if head == "S" and _count(args, 3) == 2:
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
