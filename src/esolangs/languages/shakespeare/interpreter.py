"""Interpreter for the Shakespeare Programming Language.

Karl Hasselstrom and Jon Aslund's 2001 play-shaped language.  A play is a
title, a cast (``Name, description.``), then acts and scenes; each cast member
is a variable holding an integer and a stack.  At most two characters stand on
stage; a speaker's "you" is the other one, and the speaker's sentences act on
that listener.  A scene is a goto label.  The run ends when the last
operation has run; each operation is one step.

Commands (``I``/``you`` are the speaker and the listener):
    ``[Enter A and B]``, ``[Exit A]``, ``[Exeunt]``, ``[Exeunt A and B]``.
    ``You are as ADJ as VALUE.`` / ``You are VALUE!`` / ``You NOUN-PHRASE!``
    set the listener.  A value is a noun phrase (``+-1`` doubled per
    adjective), ``nothing``/``zero``, ``I``/``me``/``myself``,
    ``you``/``thyself``, a cast name, or the sum, difference, product,
    quotient, remainder, square, cube, square root, factorial or ``twice`` of
    values.  ``Am I better than you?`` (or ``worse``, ``as ADJ as``) sets the
    flag; ``If so,`` / ``If not,`` guards any sentence.  ``Let us proceed to
    scene III.`` jumps within the act.  ``Open your heart`` / ``Speak your
    mind`` print the listener as a number / character; ``Listen to your
    heart`` / ``Open your mind`` read one into the listener.  ``Remember V``
    pushes onto the listener's stack, ``Recall ...`` pops into the listener.

Input/output:
    A number read takes a whitespace-delimited signed decimal token; a
    character read takes one Unicode character.  Output is not newline
    terminated.

Errors:
    ProgramError: bad syntax, a word outside ``words.toml``, a name not in the
        cast, acts not numbered from I, a goto to a missing scene.
    InputExhaustedError: a number or character read at EOF.
    ArgumentError: a number read given a non-integer token.
    HaltError: a speaker, entering or exiting character in the wrong place
        (including a third on stage), a second person with not exactly two on
        stage, a division by zero, a factorial or square root of a negative,
        a pop from an empty stack, an unprintable character code.
    InterpreterLimitError: an expression nested past the host recursion limit.

Decisions:
    * Word lists: ``words.toml`` (SPL 1.2.1 lists via shakespearelang 1.0.0).
      Any listed adjective of the right sign may follow a noun's article; the
      be-verb after ``You`` is optional (Hello World's ``You lying stupid ...
      coward!``); the simile ``as ADJ as`` takes any adjective.
    * A third character entering is an error (the wiki: at most two); the
      shakespearelang package allows it and fails only on a second person.
    * Integers are unbounded; quotient and remainder truncate toward zero, as C.
    * A read at EOF raises, like every interpreter here.  The Cat program
      ends that way, after echoing its input; the reference package stores -1
      and then fails printing it.  The wiki's copy spells ``Open`` as
      ``Ooen``; that raises, and the repaired spelling is the pinned program.
    * A goto names a scene of its own act; a missing one is a load error.
      Acts number from I; scene numbers need only be unique per act.
    * Title and descriptions end at the first ``.``; a title stays on one line.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import factorial, isqrt

from esolangs.exceptions import HaltError
from esolangs.languages.shakespeare._syntax import Expr, Op, parse
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

#: A persistent stack: ``(top, rest)`` cells, ``None`` for empty.
type _Stack = tuple[int, _Stack] | None


@dataclass(frozen=True, slots=True)
class _State:
    """The whole run state, immutable so ``_advance`` can return a new one."""

    pc: int
    values: tuple[int, ...]
    stacks: tuple[_Stack, ...]
    stage: tuple[int, ...]
    flag: bool


_READS = {"num_in", "chr_in"}


def _listener(state: _State, speaker: int) -> int:
    if len(state.stage) != 2:
        raise HaltError(
            f"Shakespeare second person with {len(state.stage)} on stage",
            hint="have exactly two characters on stage to speak to each other",
        )
    first, second = state.stage
    return second if first == speaker else first


def _quotient(a: int, b: int) -> int:
    if b == 0:
        raise HaltError(
            "Shakespeare division by zero", hint="divide by a nonzero value"
        )
    magnitude = abs(a) // abs(b)
    return -magnitude if (a < 0) != (b < 0) else magnitude


def _isqrt(n: int) -> int:
    if n < 0:
        raise HaltError(
            "Shakespeare square root of a negative number",
            hint="take the square root of a non-negative value",
        )
    return isqrt(n)


def _factorial(n: int) -> int:
    if n < 0:
        raise HaltError(
            "Shakespeare factorial of a negative number",
            hint="take the factorial of a non-negative value",
        )
    return factorial(n)


_UNARY: dict[str, Callable[[int], int]] = {
    "cube": lambda x: x**3,
    "square": lambda x: x * x,
    "twice": lambda x: 2 * x,
    "sqrt": _isqrt,
    "factorial": _factorial,
}
_BINARY: dict[str, Callable[[int, int], int]] = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": _quotient,
    "mod": lambda a, b: a - b * _quotient(a, b),
}


def _eval(expr: Expr, state: _State, speaker: int) -> int:
    kind = expr[0]
    if kind == "const":
        return int(expr[1])
    if kind == "me":
        return state.values[speaker]
    if kind == "you":
        return state.values[_listener(state, speaker)]
    if kind == "name":
        return state.values[expr[1]]
    if kind == "un":
        return _UNARY[expr[1]](_eval(expr[2], state, speaker))
    left = _eval(expr[2], state, speaker)
    return _BINARY[expr[1]](left, _eval(expr[3], state, speaker))


def _active(state: _State, op: Op) -> bool:
    """Whether ``op`` runs: its speaker is on stage and its guard holds."""
    if op.speaker >= 0 and op.speaker not in state.stage:
        raise HaltError(
            "Shakespeare speaker is not on stage",
            hint="[Enter ...] the speaker before the line",
        )
    return op.cond is None or op.cond == state.flag


def _put[T](items: tuple[T, ...], index: int, item: T) -> tuple[T, ...]:
    return (*items[:index], item, *items[index + 1 :])


def _show(code: int) -> str:
    if not 0 <= code <= 0x10FFFF or 0xD800 <= code <= 0xDFFF:
        raise HaltError(
            f"Shakespeare cannot print the character code {code}",
            hint="print a code point in 0..0x10FFFF outside the surrogates",
        )
    return chr(code)


def _stage(state: _State, op: Op) -> _State:
    stage = state.stage
    if op.kind == "enter":
        for who in op.a:
            if who in stage:
                raise HaltError("Shakespeare character is already on stage")
            stage += (who,)
            if len(stage) > 2:
                raise HaltError(
                    "Shakespeare allows two characters on stage",
                    hint="[Exit ...] one before another enters",
                )
    elif op.kind == "exit":
        if op.a not in stage:
            raise HaltError("Shakespeare exit of a character not on stage")
        stage = tuple(who for who in stage if who != op.a)
    else:
        leaving = stage if op.a is None else op.a
        if any(who not in stage for who in leaving):
            raise HaltError("Shakespeare exeunt of a character not on stage")
        stage = tuple(who for who in stage if who not in leaving)
    return replace(state, stage=stage)


def _advance(
    state: _State, op: Op, value: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after ``op`` and the text it prints.

    Pure: a read arrives as ``value``, a write leaves as the return value.
    """
    state = replace(state, pc=state.pc + 1)
    if op.speaker < 0:
        return _stage(state, op), None
    if not _active(state, op):
        return state, None
    kind, speaker = op.kind, op.speaker
    if kind == "goto":
        return replace(state, pc=op.a), None
    if kind == "ask":
        left = _eval(op.a, state, speaker)
        right = _eval(op.b, state, speaker)
        result = {"gt": left > right, "lt": left < right, "eq": left == right}[op.c]
        return replace(state, flag=result), None
    target = _listener(state, speaker)
    if kind == "set" or kind in _READS:
        if kind == "set":
            new = _eval(op.a, state, speaker)
        else:
            assert value is not None  # the shell reads before a read command
            new = value
        return replace(state, values=_put(state.values, target, new)), None
    if kind == "num_out":
        return state, str(state.values[target])
    if kind == "chr_out":
        return state, _show(state.values[target])
    if kind == "push":
        top = _eval(op.a, state, speaker)
        pushed: _Stack = (top, state.stacks[target])
        return replace(state, stacks=_put(state.stacks, target, pushed)), None
    cell = state.stacks[target]
    if cell is None:
        raise HaltError(
            "Shakespeare recall from an empty stack",
            hint="Remember a value before recalling",
        )
    values = _put(state.values, target, cell[0])
    return replace(
        state, values=values, stacks=_put(state.stacks, target, cell[1])
    ), None


class _Machine:
    """The operation list and the state."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        size, self.ops = parse(code)
        self.io = io
        self.state = _State(0, (0,) * size, (None,) * size, (), flag=False)

    @property
    def halted(self) -> bool:
        return self.state.pc >= len(self.ops)

    @property
    def ip(self) -> int:
        return self.state.pc

    def snapshot(self) -> tuple[object, ...]:
        s = self.state
        return (s.pc, s.values, s.stacks, s.stage, s.flag, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        op = self.ops[self.state.pc]
        value = None
        if op.kind in _READS and _active(self.state, op):
            _listener(self.state, op.speaker)
            read = self.io.input_num if op.kind == "num_in" else self.io.input_char
            value = read()
        self.state, out = _advance(self.state, op, value)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a Shakespeare play to its last operation."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
