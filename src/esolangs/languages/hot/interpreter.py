"""Interpreter for Hot.

Hakerh400's 2021 Zot-inspired combinator calculus.  A program is one
expression over the combinators ``K S F A B C D 0 1``: juxtaposition is
application, left-associative, and parentheses group.  Only the head of the
main expression is ever rewritten, one rule a step; when the head has fewer
arguments than its rule takes, ``F`` combinators are appended until it has
enough.

Commands:
    ``K x y -> x``, ``S x y z -> x z (y z)``, ``0 x y -> y``, ``1 -> K``.
    ``F x -> x B A``.
    ``A x -> x #``, ``#`` the next input bit as ``0`` or ``1``.
    ``B x -> x D C``; ``C x -> x`` outputs 0, ``D x -> x`` outputs 1.

Input/output:
    The input is a string of ``0``/``1`` characters, ended by a newline or
    EOF; the program reads each bit preceded by a 1, then 0s forever.  An
    output 0 at an even (0-indexed) position halts; the bits at odd
    positions are printed as ``0``/``1`` characters.

Errors:
    ProgramError: an empty program, empty or unbalanced parentheses, and any
    character that is not a combinator, a parenthesis or whitespace.
    ArgumentError: an input character other than ``0``, ``1`` or a newline.

Decisions:
    * The overview's trace of ``K`` keeps reducing past ``C C A A``; under
      the I/O section's rule that 0 at position 2 halts, so ``K`` prints
      ``1``.  The I/O section governs, as the truth machine's trace does.
    * Whitespace is ignored: the overview writes ``0 (C K) (D K)``.
    * A newline ends the input string, so a trailing newline adds no bits.
"""

from __future__ import annotations

from esolangs.exceptions import ArgumentError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime.combinators import Args as _Args
from esolangs.runtime.combinators import State as _State
from esolangs.runtime.combinators import Term as _Term
from esolangs.runtime.combinators import parse, stack
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: How many arguments each rule takes.
ARITY = {"K": 2, "S": 3, "F": 1, "A": 1, "B": 1, "C": 1, "D": 1, "0": 2, "1": 0}


def _settle(term: _Term, args: _Args) -> _State:
    """Return ``term`` applied to ``args`` as a head with enough arguments."""
    while not isinstance(term, str):
        term, args = term[0], (term[1], args)
    arity = ARITY[term]
    depth, rest = 0, args
    while rest is not None and depth < arity:
        depth, rest = depth + 1, rest[1]
    if depth < arity:
        # Appending at the far end: the stack has fewer than three cells.
        cells: list[_Term] = []
        while args is not None:
            cells.append(args[0])
            args = args[1]
        args = None
        for cell in reversed([*cells, *"F" * (arity - depth)]):
            args = (cell, args)
    return term, args


def _advance(state: _State, bit: int | None) -> tuple[_State, int | None]:
    """Return the state after one rewrite, and the bit it outputs.

    Pure: ``bit`` is the input bit when the head is ``A``.
    """
    head, args = state
    out = None
    if head == "1":
        return _settle("K", args), None
    assert args is not None
    x, rest = args
    if head == "K":
        assert rest is not None
        term, args = x, rest[1]
    elif head == "S":
        assert rest is not None
        assert rest[1] is not None
        y, (z, tail) = rest[0], rest[1]
        term, args = x, (z, ((y, z), tail))
    elif head == "0":
        assert rest is not None
        term, args = rest[0], rest[1]
    elif head == "F":
        term, args = x, ("B", ("A", rest))
    elif head == "A":
        term, args = x, (str(bit), rest)
    elif head == "B":
        term, args = x, ("D", ("C", rest))
    else:
        term, args, out = x, rest, int(head == "D")
    return _settle(term, args), out


class _Machine:
    """The expression, the input stream's position, and the output parity."""

    #: Past the input string the stream is 0s, so a read never fails.
    eof_is_a_value = True
    #: The term tree is rebuilt as it runs; ``ip`` is the argument count.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.state = _settle(
            parse(
                code,
                "".join(ARITY),
                "Hot",
                "use K S F A B C D 0 1, parentheses and whitespace",
            ),
            None,
        )
        #: The bit owed after a marker 1, or ``None``.
        self.pending: int | None = None
        self.ended = False
        self.odd = False
        self.halted = False

    @property
    def ip(self) -> tuple[int, ...]:
        """The number of arguments on the spine."""
        depth, args = 0, self.state[1]
        while args is not None:
            depth, args = depth + 1, args[1]
        return (depth,)

    @property
    def stack(self) -> list[object]:
        """The head, then its arguments, first argument first."""
        return stack(self.state)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.state,
            self.pending,
            self.ended,
            self.odd,
            self.halted,
            self.io.progress(),
        )

    def _read(self) -> int:
        """Return the next stream bit: a marker 1 before each input bit."""
        if self.pending is not None:
            bit, self.pending = self.pending, None
            return bit
        if self.ended:
            return 0
        try:
            char = chr(self.io.input_char())
        except EOFError:
            char = "\n"
        if char == "\n":
            self.ended = True
            return 0
        if char not in "01":
            raise syntax_error(
                f"Hot input must be a binary string, got {char!r}",
                "supply 0 and 1 characters, for example 1011",
                error_type=ArgumentError,
            )
        self.pending = int(char)
        return 1

    def step(self) -> None:
        if self.halted:
            return
        bit = self._read() if self.state[0] == "A" else None
        self.state, out = _advance(self.state, bit)
        if out is None:
            return
        if self.odd:
            self.io.print_str(str(out))
        elif not out:
            self.halted = True
        self.odd = not self.odd


def _execute(code: str, io: IO) -> CompletionReport:
    """Run a Hot program on the binary string read from ``io``."""
    return drive(_Machine(code, io))


def run(code: str, io: IO) -> None:
    """Run a Hot program on the binary string read from ``io``."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
