r"""Interpreter for FALSE.

Wouter van Oortmerssen's 1993 stack language: digits push, ``'c`` pushes a
character, ``$%\@`` and ``O`` (``ø``) shuffle the stack, ``+-*/_`` and
``&|~`` compute, ``>`` and ``=`` compare with ``-1`` for true, ``a``-``z``
push a variable reference that ``:`` stores into and ``;`` reads back,
``[...]`` pushes a lambda that ``!`` runs, ``?`` runs on a true flag and
``#`` drives as ``[cond][body]#``, ``.`` prints a number, ``,`` a
character, ``"..."`` a string, ``^`` reads one, ``B`` (``ß``) flushes and
``{...}`` is a comment.

Integers wrap to signed 32 bits, the width the specification gives ("all
variables (and also stack-items) are 32bits"), and ``/`` truncates toward
zero, as C and the 68000 the language was written on do.  ``O`` is accepted
as an ASCII spelling of ``ø``, which the spec's table does not list: the
command is a non-ASCII character, and a source that cannot carry one has no
other way to write it.  An unterminated ``[``, ``"`` or ``{``, and a ``'``
at the end of the source, raise :class:`ValueError`.  Popping an
empty stack, dividing by zero, running a number as a lambda, computing on
a lambda, and reading an unset variable raise
:class:`~esolangs.exceptions.HaltError`.

``^`` consumes the next Unicode character, including newlines; end of input
is the spec's ``-1``, which the shell reaches by catching the
port's ``EOFError``.  Raising instead would make the reference's own cat
loop -- which tests ``^`` against ``-1`` -- a crash.

Three points the specification leaves open are decided here.  ``ø`` counts
from zero, so ``0ø`` is ``$``: the description ("dup the nth stack item")
does not say where the count starts.  A variable read before it is stored
raises rather than inventing a value, since the spec gives no initial one.
And a character that is no command is ignored, the way whitespace is --
the spec says only that whitespace is ignored and is silent about the rest.
A lambda is a span into the source rather than a copied string, which is
why ``ip`` stays a real offset even inside one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_VARS = len(_LETTERS)


@dataclass(frozen=True)
class _Lambda:
    """A ``[...]`` body, as the half-open span of source it occupies."""

    start: int
    end: int


#: A stack or variable value: a wrapped integer, or a lambda's span.
type _Value = int | _Lambda


@dataclass(frozen=True)
class _Frame:
    """One running body: the program itself, or a ``!``/``?`` lambda."""

    pc: int
    end: int


@dataclass(frozen=True)
class _Loop(_Frame):
    """One pass of a ``[cond][body]#``, carrying both spans.

    A subclass rather than two optional fields on :class:`_Frame`: the pass
    that finishes has to push the next one, so it needs both spans, and
    making that a separate type is what lets the reader -- and the checker --
    see that a loop frame always has them.
    """

    cond: _Lambda
    body: _Lambda
    #: Whether this pass is running the condition rather than the body.
    testing: bool = True


#: The whole run as an immutable value: the stack, the 26 variables, and
#: the frame stack.  ``None`` in the variables is "never stored", which
#: halts rather than reading as zero -- the reference leaves the slot
#: uninitialized, so a program that reads one has no defined value to get.
type _State = tuple[tuple[_Value, ...], tuple[_Value | None, ...], tuple[_Frame, ...]]

#: What one step may hand back for the shell to write.
type _Effect = tuple[str, object] | None


def _wrap32(value: int) -> int:
    """Wrap ``value`` to a signed 32-bit integer, the spec's width."""
    return (value + 2**31) % 2**32 - 2**31


def _trunc_div(left: int, right: int) -> int:
    """Divide truncating toward zero, as C and the 68000 do."""
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


def _closers(code: str) -> dict[int, int]:
    """Return each ``[``'s index mapped to its matching ``]``.

    One pass, because the nesting has to be read through the constructs
    that quote a bracket: ``{}`` comments, ``"`` strings and ``'c``.
    Scanning for brackets alone made ``{[}`` an unterminated lambda.
    """
    open_indices: list[int] = []
    pairs: dict[int, int] = {}
    index = 0
    while index < len(code):
        char = code[index]
        if char == "'":
            if index + 1 >= len(code):
                raise ValueError(
                    "a FALSE source cannot end in a quote, which takes the "
                    "character after it"
                )
            index += 2
            continue
        if char in '{"':
            closer = "}" if char == "{" else '"'
            found = code.find(closer, index + 1)
            if found < 0:
                raise ValueError(f"unterminated {char!r} in a FALSE program")
            index = found + 1
            continue
        if char == "[":
            open_indices.append(index)
        elif char == "]":
            if not open_indices:
                raise ValueError("a FALSE ']' closes a '[' that is not there")
            pairs[open_indices.pop()] = index
        index += 1
    if open_indices:
        raise ValueError("unterminated '[' in a FALSE program")
    return pairs


def _pop(stack: tuple[_Value, ...]) -> tuple[_Value, tuple[_Value, ...]]:
    """Return the top of ``stack`` and the rest, halting when it is empty."""
    if not stack:
        raise HaltError("the stack is empty, so there is nothing to pop")
    return stack[-1], stack[:-1]


def _number(value: _Value, what: str) -> int:
    """Return ``value`` as an integer, halting when it is a lambda."""
    if isinstance(value, _Lambda):
        raise HaltError(f"{what} needs a number, but that stack entry is a lambda")
    return value


def _variable(value: _Value) -> int:
    """Return the variable index ``value`` names, halting when it is not one."""
    index = _number(value, "a variable reference")
    if not 0 <= index < _VARS:
        raise HaltError(f"{index} is not one of FALSE's 26 variable references")
    return index


def _literal(code: str, pc: int, end: int) -> tuple[int, int]:
    """Return the integer literal starting at ``pc``, and the index past it."""
    stop = pc
    value = 0
    while stop < end and code[stop].isdigit():
        # Bounded accumulation avoids Python's decimal conversion limit.
        value = _wrap32(value * 10 + int(code[stop]))
        stop += 1
    return value, stop


def _binary(char: str, stack: tuple[_Value, ...]) -> tuple[_Value, ...]:
    """Return ``stack`` with the top two replaced by ``char``'s result."""
    right, rest = _pop(stack)
    left, rest = _pop(rest)
    two = _number(right, f"{char!r}")
    one = _number(left, f"{char!r}")
    if char == "+":
        return (*rest, _wrap32(one + two))
    if char == "-":
        return (*rest, _wrap32(one - two))
    if char == "*":
        return (*rest, _wrap32(one * two))
    if char == "/":
        if two == 0:
            raise HaltError("FALSE divides by zero here")
        return (*rest, _wrap32(_trunc_div(one, two)))
    if char == "&":
        return (*rest, _wrap32(one & two))
    if char == "|":
        return (*rest, _wrap32(one | two))
    if char == ">":
        return (*rest, -1 if one > two else 0)
    # The caller admits only the eight operators above and ``=``.
    return (*rest, -1 if one == two else 0)


def _at(frame: _Frame, pc: int) -> _Frame:
    """Return ``frame`` with its cursor moved to ``pc``, keeping its kind."""
    return replace(frame, pc=pc)


def _pass(loop: _Loop, *, testing: bool) -> _Loop:
    """Return the loop's next pass: its condition, or its body."""
    span = loop.cond if testing else loop.body
    return _Loop(span.start, span.end, loop.cond, loop.body, testing)


def _finalize(state: _State) -> _State:
    """Retire finished frames, re-arming a ``#`` that has another pass.

    A ``cond`` frame that ran out has left its flag on the stack: a true
    one pushes the body, a false one ends the loop.  A finished ``body``
    frame pushes the condition again.
    """
    stack, variables, frames = state
    while frames and frames[-1].pc >= frames[-1].end:
        frame = frames[-1]
        frames = frames[:-1]
        if not isinstance(frame, _Loop):
            continue
        if frame.testing:
            flag, stack = _pop(stack)
            if _number(flag, "'#'"):
                frames = (*frames, _pass(frame, testing=False))
        else:
            frames = (*frames, _pass(frame, testing=True))
    return (stack, variables, frames)


def _advance(
    state: _State, code: str, closers: dict[int, int], line: str | None = None
) -> tuple[_State, _Effect]:
    """Return the state after one command, and what to write.

    Pure: ``^``'s line arrives as ``line`` and every write leaves as the
    effect, so the frame bookkeeping is testable without a port.
    """
    state = _finalize(state)
    stack, variables, frames = state
    if not frames:
        return state, None
    frame = frames[-1]
    char = code[frame.pc]
    frames = (*frames[:-1], _at(frame, frame.pc + 1))

    if char.isdigit():
        value, stop = _literal(code, frame.pc, frame.end)
        frames = (*frames[:-1], _at(frame, stop))
        return ((*stack, value), variables, frames), None
    if char == "'":
        frames = (*frames[:-1], _at(frame, frame.pc + 2))
        return ((*stack, ord(code[frame.pc + 1])), variables, frames), None
    if char == "{":
        stop = code.index("}", frame.pc) + 1
        frames = (*frames[:-1], _at(frame, stop))
        return (stack, variables, frames), None
    if char == '"':
        stop = code.index('"', frame.pc + 1)
        frames = (*frames[:-1], _at(frame, stop + 1))
        return (stack, variables, frames), ("str", code[frame.pc + 1 : stop])
    if char == "[":
        stop = closers[frame.pc]
        frames = (*frames[:-1], _at(frame, stop + 1))
        return ((*stack, _Lambda(frame.pc + 1, stop)), variables, frames), None
    if char in _LETTERS:
        return ((*stack, _LETTERS.index(char)), variables, frames), None
    if char == "$":
        top, _rest = _pop(stack)
        return ((*stack, top), variables, frames), None
    if char == "%":
        _top, rest = _pop(stack)
        return (rest, variables, frames), None
    if char == "\\":
        two, rest = _pop(stack)
        one, rest = _pop(rest)
        return ((*rest, two, one), variables, frames), None
    if char == "@":
        three, rest = _pop(stack)
        two, rest = _pop(rest)
        one, rest = _pop(rest)
        return ((*rest, two, three, one), variables, frames), None
    if char in "øO":
        depth, rest = _pop(stack)
        index = _number(depth, "'ø'")
        if not 0 <= index < len(rest):
            raise HaltError(f"'ø' asks for stack entry {index}, which is not there")
        return ((*rest, rest[len(rest) - 1 - index]), variables, frames), None
    if char == "_":
        top, rest = _pop(stack)
        return ((*rest, _wrap32(-_number(top, "'_'"))), variables, frames), None
    if char == "~":
        top, rest = _pop(stack)
        return ((*rest, _wrap32(~_number(top, "'~'"))), variables, frames), None
    if char in "+-*/&|>=":
        return (_binary(char, stack), variables, frames), None
    if char == ":":
        reference, rest = _pop(stack)
        # Not ``value``: that name holds the integer literal above, and one
        # binding cannot be both an int and a lambda.
        stored, rest = _pop(rest)
        index = _variable(reference)
        return (
            rest,
            (*variables[:index], stored, *variables[index + 1 :]),
            frames,
        ), None
    if char == ";":
        reference, rest = _pop(stack)
        index = _variable(reference)
        fetched = variables[index]
        if fetched is None:
            raise HaltError(
                f"FALSE variable {_LETTERS[index]!r} was read before it was stored"
            )
        return ((*rest, fetched), variables, frames), None
    if char == "!":
        body, rest = _pop(stack)
        if not isinstance(body, _Lambda):
            raise HaltError("'!' runs a lambda, but the top of the stack is a number")
        return (rest, variables, (*frames, _Frame(body.start, body.end))), None
    if char == "?":
        body, rest = _pop(stack)
        flag, rest = _pop(rest)
        if not isinstance(body, _Lambda):
            raise HaltError("'?' runs a lambda, but the top of the stack is a number")
        if _number(flag, "'?'"):
            return (rest, variables, (*frames, _Frame(body.start, body.end))), None
        return (rest, variables, frames), None
    if char == "#":
        body, rest = _pop(stack)
        cond, rest = _pop(rest)
        if not isinstance(body, _Lambda) or not isinstance(cond, _Lambda):
            raise HaltError("'#' drives two lambdas, and one of these is a number")
        loop = _Loop(cond.start, cond.end, cond, body)
        return (rest, variables, (*frames, loop)), None
    if char == ".":
        top, rest = _pop(stack)
        return (rest, variables, frames), ("num", _number(top, "'.'"))
    if char == ",":
        top, rest = _pop(stack)
        return (rest, variables, frames), ("char", _number(top, "','") & 0xFF)
    if char == "^":
        # The read already happened in the shell.  ``None`` is end of input,
        # which the spec answers with -1.
        value = -1 if line is None else ord(line[0]) if line else 0
        return ((*stack, value), variables, frames), None
    # ``ß``/``B`` flush a buffer this package does not have, and every other
    # character is ignored, as the reference's parser ignores whitespace.
    return (stack, variables, frames), None


class _Machine:
    """The run state: the stack, the variables, and the frame stack."""

    #: ``^`` answers -1 at end of input, so an underfed program computes a
    #: different row rather than failing.  Declared because the public API
    #: reports it: a caller has to know its short stdin was not refused.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.closers = _closers(code)
        self.state: _State = ((), (None,) * _VARS, (_Frame(0, len(code)),))

    @property
    def halted(self) -> bool:
        return not _finalize(self.state)[2]

    #: A lambda is a span into the source the caller handed in, so every
    #: frame's position is an offset on that text.
    ip_shape = "offset"

    @property
    def ip(self) -> int | None:
        frames = _finalize(self.state)[2]
        return frames[-1].pc if frames else None

    @property
    def memory(self) -> list[int]:
        """The variables, with an unstored slot reading as zero."""
        return [
            0 if value is None else value
            for value in self.state[1]
            if not isinstance(value, _Lambda)
        ]

    @property
    def stack(self) -> list[object]:
        return list(self.state[0])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.position())

    def step(self) -> None:
        """Execute one command, with the reads and writes the transition asks."""
        if self.halted:
            return
        state = _finalize(self.state)
        frames = state[2]
        char = self.code[frames[-1].pc]
        line: str | None = None
        if char == "^":
            try:
                line = chr(self.io.input_char())
            except EOFError:
                # ``^`` has an EOF value in the spec, so the port's raise is
                # caught and turned into it -- as nine other interpreters here
                # turn it into their own language's.  Letting it escape made
                # the reference's own cat loop (``[^1_=~][,]#``) a crash.
                line = None
        self.state, effect = _advance(state, self.code, self.closers, line)
        if effect is None:
            return
        kind, value = effect
        if kind == "num":
            self.io.print_num(int(str(value)))
        elif kind == "char":
            self.io.print_char(chr(int(str(value))))
        else:
            self.io.print_str(str(value))


def run(code: str, io: IO) -> None:
    """Run a FALSE program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
