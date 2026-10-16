"""Interpreter for Grapheme.

Each uppercase letter is a command; the stack holds unbounded integers,
strings and functions, with an untyped variable map.  ``E``/``F``/``H``
toggle string/int/function mode, accumulating characters into a value
pushed when the mode ends.

Each uppercase letter is a command; the stack holds unbounded integers,
strings and functions, with an untyped variable map.  ``E``/``F``/``H``
toggle string/int/function mode, accumulating characters into a value
pushed when the mode ends.  A literal still open at the end of the code is
pushed.  ``G``/``I``/``Q``/``Z`` run a function in a fresh normal-mode
context sharing stack and variables.  "each one representing a command":
``U``/``V``/``X`` skip letters, not whole literals, and funcmode ends at the
next ``H`` even inside ``E...E``.  ``Z`` on a non-function does nothing;
``V``'s count converts as ``J`` does; ``N`` on a function returns its body.
Unbounded pushes are what ``esolangs.run``'s ``timeout`` catches, and
ancestor replay is decided by :func:`esolangs.vm.run_until_halt_or_ancestor`.

Input/output:
    ``W`` reads one line, excluding its newline, and raises at EOF.

Errors:
    ProgramError: a character outside ``A``-``Z`` (after LF removal);
    ``integer_conversion`` other than ``between_letters`` or
    ``after_each_letter``; an unhandled letter reached through a string
    read from input and run by ``G``/``I``.
    InputExhaustedError: ``W`` at EOF.
    HaltError: underflow, math or ``Y`` on a function, a negative ``N``
    integer (alphabet ``A``-``J``), division by zero, and ``G`` on a value
    that is neither string nor function.

Decisions:
    * Loading removes LF before validation, modes and indexing so line-wrapped
      generated programs run.  Spaces, tabs and CR remain malformed.
    * ``integer_conversion="between_letters"`` keeps existing programs and
      generators: ``FAFY`` prints 1.  ``"after_each_letter"`` follows the
      prose and prints 10; int mode and string-to-integer conversion share
      this rule.  Numeric and function conversions are unchanged.
    * Reading an unset variable pushes its name: the spec leaves initial
      values unspecified, and its "Using variables" example
      (``EVARIABLEEMYVAREKCDY`` prints ``VARIABL``) reads a name it never set.
    * The page's truth machine ``HFAFYHWJUZFZFY`` works for input 0 only: on
      1, ``U`` pops the 1, ``Z`` pops the function off an otherwise empty
      stack, its loop never runs, and ``FZFY`` prints 0.  Only a ``Z`` that
      keeps its function on the stack would loop, against the table's "Pop
      A"; not adopted.
    * The spec asks for strings without defining their delimiter; ``W`` reads
      one line, excluding its newline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import takewhile
from operator import add, mul, sub
from types import MappingProxyType
from typing import Final, Literal

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

INTEGER_CONVERSIONS = ("between_letters", "after_each_letter")


@dataclass(frozen=True)
class GraphemeDialect:
    """Choose when integer conversion multiplies by ten."""

    integer_conversion: str = "between_letters"

    def __post_init__(self) -> None:
        """Reject an unknown conversion rule."""
        if self.integer_conversion not in INTEGER_CONVERSIONS:
            raise ValueError(
                "integer_conversion must be between_letters or after_each_letter"
            )

    def finish_integer(self, value: int) -> int:
        """Apply the selected final multiplication."""
        return value * 10 if self.integer_conversion == "after_each_letter" else value


DEFAULT_GRAPHEME = GraphemeDialect()


_FUNC: Final = "func"

# A Grapheme value is a number, a string, or a function -- and a function
# is always the pair ``(_FUNC, body)``, built in the two places a frame's
# buffer is closed.  Naming the three lets the checker see that the
# conversions below handle every one, so none needs a trailing assertion
# for a fourth kind that cannot exist, and the function body no longer has
# to be cast to str at each use.
_Function = tuple[Literal["func"], str]
_Value = int | str | _Function


def _letter_number(chars: Iterable[str]) -> int:
    """Fold letters into a number, one decimal place each: A..Y add 1..25, Z 0."""
    res = 0
    for c in chars:
        res = res * 10 + (ord(c) - 64 if c != "Z" else 0)
    return res


def _int_from(buf: Iterable[str], dialect: GraphemeDialect = DEFAULT_GRAPHEME) -> int:
    """Parse an intmode buffer under the selected multiplication rule."""
    return dialect.finish_integer(_letter_number(buf))


def _to_int(value: _Value, dialect: GraphemeDialect = DEFAULT_GRAPHEME) -> int:
    """Convert a value to an integer (the ``J`` command)."""
    if isinstance(value, int):
        return value
    if isinstance(value, tuple):  # function -> number of commands
        return len(value[1])
    letters = takewhile(lambda c: c != "F", value)
    return dialect.finish_integer(_letter_number(letters))


def _to_str(value: _Value) -> str:
    """Convert a value to a string (the ``N`` command)."""
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):  # function -> its body
        return value[1]
    if value < 0:
        raise HaltError("N cannot encode a negative integer")
    digits = "JABCDEFGHI"  # J = 0, A = 1, ..., I = 9
    if value == 0:
        return "J"
    res: list[str] = []
    while value:
        res.append(digits[value % 10])
        value //= 10
    return "".join(reversed(res))


def _as_num(value: _Value) -> int:
    """Math operand: an integer, or the ord of a string's first character."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return ord((value or "\0")[0])
    raise HaltError(
        "math on a function is undefined", hint="use numeric operands for arithmetic"
    )


def _truthy(value: _Value) -> bool:
    """Falsy values are zero, the empty string, and the empty function."""
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return value[1] != ""


#: One call context: ``(code, pc, mode, buf, pending_at, repeat)``.
#:
#: A tuple rather than a record, so the whole call stack is a value that
#: :meth:`_Machine.snapshot` can hash -- the shared frames are tuples for the
#: same reason.  ``repeat`` marks a ``Z`` body: a frame holding one is
#: rewound instead of popped while the stack is non-empty.
type _Frame = tuple[str, int, str, tuple[str, ...], int, bool]

#: The part of a run the pure layer owns: the variables and the call stack.
#: The value stack is deliberately absent; see the module docstring.
type _Vars = Mapping[_Value, _Value]
type _State = tuple[_Vars, tuple[_Frame, ...]]

#: A read-only view of the live value stack, which the pure layer indexes
#: but never writes.
type _StackView = Sequence[_Value]

#: What a step wants done to the value stack: how many to remove from the
#: top, what to add after that, and whether ``P`` reversed what was left.
#: Applied in exactly that order.
type _StackFx = tuple[int, tuple[_Value, ...], bool]


#: The command that opens each mode, and the one that closes it.  The two
#: are the same letter: ``E`` opens string mode and ``E`` ends it.  Naming
#: them once keeps the open and close arms from drifting apart.
_OPENS: Final = {"E": "string", "F": "int", "H": "func"}
_CLOSES: Final = {mode: char for char, mode in _OPENS.items()}


def _frame(code: str, *, repeat: bool = False) -> _Frame:
    """Build a fresh frame for ``code``, at the start and in no mode."""
    return (code, 0, "", (), -1, repeat)


@dataclass
class _Step:
    """Everything one command may read or change, held in one place.

    A handler takes this and records its effects on it explicitly.  It
    never escapes :func:`_advance`, so the transition
    stays pure over the immutable :type:`_State`.
    """

    variables: _Vars
    pc: int
    mode: str
    buf: tuple[str, ...]
    pending_at: int
    line_in: str | None
    pops: int = 0
    pushes: tuple[_Value, ...] = ()
    reverse: bool = False
    body: str | None = None
    call_repeat: bool = False
    output: _Value | None = None

    def pop(self, view: _StackView) -> _Value:
        """Read the next value down the stack, and count the pop.

        Sound only because every command pops before it pushes.
        """
        if self.pops >= len(view):
            raise HaltError(
                "popped an empty stack",
                hint="push a value before reading or removing the stack top",
            )
        value = view[-1 - self.pops]
        self.pops += 1
        return value


#: A command handler: takes the step scratch, the read-only stack view, and
#: the dialect, and records its effects on the scratch.
type _Handler = Callable[[_Step, _StackView, GraphemeDialect], None]


def _flush_of(
    frame: _Frame, dialect: GraphemeDialect = DEFAULT_GRAPHEME
) -> tuple[_Value, ...]:
    """Return what an unterminated mode leaves behind, as at end of program."""
    _, _, mode, buf, _, _ = frame
    if mode == "string":
        return ("".join(buf),)
    if mode == "int":
        return (_int_from(buf, dialect),)
    if mode == "func":
        return ((_FUNC, "".join(buf)),)
    return ()


def _finished(
    state: _State,
    view: _StackView,
    fx: _StackFx,
    dialect: GraphemeDialect = DEFAULT_GRAPHEME,
) -> tuple[_State, _StackFx]:
    """Flush the top frame's mode and pop it -- or rewind it, for ``Z``.

    ``Z``'s emptiness test reads the *virtual* depth.
    """
    variables, frames = state
    frame = frames[-1]
    pops, pushes, reverse = fx
    pushes = (*pushes, *_flush_of(frame, dialect))
    fx = (pops, pushes, reverse)

    code, _, _, _, _, repeat = frame
    if repeat and len(view) - pops + len(pushes) > 0:
        rewound = _frame(code, repeat=repeat)
        return (variables, (*frames[:-1], rewound)), fx
    return (variables, frames[:-1]), fx


def _arith(op: Callable[[int, int], int]) -> _Handler:
    """Build a handler for a binary arithmetic command (``A``, ``B``, ``S``)."""

    def run(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
        """Apply the operation to the top two numbers."""
        a = step.pop(view)
        b = step.pop(view)
        step.pushes = (op(_as_num(a), _as_num(b)),)

    return run


def _open_mode(mode: str) -> _Handler:
    """Build a handler that opens the given literal mode (``E``/``F``/``H``)."""

    def run(step: _Step, _view: _StackView, _dialect: GraphemeDialect) -> None:
        """Open the mode, discarding any characters accumulated so far."""
        step.mode = mode
        step.buf = ()

    return run


def _cmd_divide(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Divide the top two numbers, halting on a zero divisor."""
    a = step.pop(view)
    b = step.pop(view)
    divisor = _as_num(b)
    if divisor == 0:
        raise HaltError(
            "division by zero", hint="ensure the divisor is nonzero before dividing"
        )
    step.pushes = (_as_num(a) // divisor,)


def _cmd_store(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Bind a name to a value in the variable map."""
    name = step.pop(view)
    value = step.pop(view)
    # The map takes "integers/strings/functions to" the same, so a
    # function names a variable too (by its body, a hashable pair).
    step.variables = MappingProxyType({**step.variables, name: value})


def _cmd_load(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Push a variable's value, or its name if it was never set."""
    name = step.pop(view)
    # An unset name reads as itself: the wiki's "Using variables"
    # example prints ``VARIABL`` by reading a name it never set.
    step.pushes = (step.variables.get(name, name),)


def _cmd_call(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Call the body of a string or function value."""
    value = step.pop(view)
    raw = value[1] if isinstance(value, tuple) else value
    if not isinstance(raw, str):
        raise HaltError(
            "G needs a string or a function",
            hint="pass G a string or a function value",
        )
    step.body = raw


def _cmd_exec(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Call a function value, or push a non-function back unchanged."""
    value = step.pop(view)
    if isinstance(value, tuple):
        step.body = value[1]
    else:
        step.pushes = (value,)


def _cmd_to_int(step: _Step, view: _StackView, dialect: GraphemeDialect) -> None:
    """Convert the top value to an integer (``J``'s rule)."""
    step.pushes = (_to_int(step.pop(view), dialect),)


def _cmd_dup(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Duplicate the top of the stack."""
    value = step.pop(view)
    step.pushes = (value, value)


def _cmd_swap(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Swap the top two stack values."""
    a = step.pop(view)
    b = step.pop(view)
    step.pushes = (a, b)


def _cmd_drop(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Discard the top of the stack."""
    step.pop(view)


def _cmd_to_str(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Convert the top value to a string (``N``'s rule)."""
    step.pushes = (_to_str(step.pop(view)),)


def _cmd_length(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Push a string's length; other values pass through."""
    value = step.pop(view)
    step.pushes = (len(value) if isinstance(value, str) else value,)


def _cmd_reverse(step: _Step, _view: _StackView, _dialect: GraphemeDialect) -> None:
    """Reverse the stack below this command's effects."""
    step.reverse = True


def _cmd_cond_call(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Call a function value when the value beneath it is truthy."""
    a = step.pop(view)
    b = step.pop(view)
    if isinstance(a, tuple) and _truthy(b):
        step.body = a[1]


def _cmd_not(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Push 1 for a falsy value, 0 for a truthy one."""
    step.pushes = (int(not _truthy(step.pop(view))),)


def _cmd_skip_if_falsy(
    step: _Step, view: _StackView, _dialect: GraphemeDialect
) -> None:
    """Skip the next letter when the top value is falsy."""
    if not _truthy(step.pop(view)):
        step.pc += 1


def _cmd_skip_many(step: _Step, view: _StackView, dialect: GraphemeDialect) -> None:
    """Skip the next B letters when A is falsy; a negative B skips none."""
    a = step.pop(view)
    b = step.pop(view)
    if not _truthy(a):
        # "skip the next B commands": a negative B skips none.
        step.pc += max(0, _to_int(b, dialect))


def _cmd_read_line(step: _Step, _view: _StackView, _dialect: GraphemeDialect) -> None:
    """Push the input line, or the empty string when there is none."""
    step.pushes = (step.line_in if step.line_in is not None else "",)


def _cmd_exec_next(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Run the next letter when truthy (then skip one), else skip it."""
    if _truthy(step.pop(view)):
        # execute the next command, then skip the one after it
        step.pending_at = step.pc
    else:
        # skip the next command entirely
        step.pc += 1


def _cmd_output(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Report the top value as output; functions cannot be output."""
    value = step.pop(view)
    if isinstance(value, tuple):
        raise HaltError(
            "Y cannot output a function",
            hint="use a whole-number character code between 0 and 1114111",
        )
    step.output = value


def _cmd_repeat(step: _Step, view: _StackView, _dialect: GraphemeDialect) -> None:
    """Repeat a function while the stack is non-empty, keeping its body."""
    value = step.pop(view)
    if isinstance(value, tuple) and len(view) - step.pops + len(step.pushes) > 0:
        step.body = value[1]
        step.call_repeat = True


#: Every command letter and the handler that runs it.
_COMMANDS: Final[dict[str, _Handler]] = {
    "A": _arith(add),
    "B": _arith(sub),
    "C": _cmd_store,
    "D": _cmd_load,
    **{char: _open_mode(mode) for char, mode in _OPENS.items()},
    "G": _cmd_call,
    "I": _cmd_exec,
    "J": _cmd_to_int,
    "K": _cmd_dup,
    "L": _cmd_swap,
    "M": _cmd_drop,
    "N": _cmd_to_str,
    "O": _cmd_length,
    "P": _cmd_reverse,
    "Q": _cmd_cond_call,
    "R": _cmd_divide,
    "S": _arith(mul),
    "T": _cmd_not,
    "U": _cmd_skip_if_falsy,
    "V": _cmd_skip_many,
    "W": _cmd_read_line,
    "X": _cmd_exec_next,
    "Y": _cmd_output,
    "Z": _cmd_repeat,
}


# :class:`_Machine` has an explicit call stack (one frame per active call),
# so ``halted`` is true once no frame remains and a repeated
# :meth:`_Machine.snapshot` proves a loop; unbounded growth (``HKHKZ``)
# needs the wall-clock bound.  :func:`_advance` is pure over an immutable
# ``_State`` (variables, tuple call stack) and returns *collected effects*
# ``(pops, pushes, reverse)`` on the value stack, which stays a list in the
# shell: 200,000 commands of ``HKHKZ`` take 0.21s against a list and 445s
# against a rebuilt tuple.  The invariant that makes reporting sound:
# **every command pops before it pushes**, so operands are read at
# ``stack[-1 - pops]``.  Finishing a frame (flush the mode buffer, pop, or
# rewind for ``Z``) is part of the transition, reading the *virtual* depth.
def _advance(
    state: _State,
    view: _StackView,
    line_in: str | None = None,
    dialect: GraphemeDialect = DEFAULT_GRAPHEME,
) -> tuple[_State, _StackFx, _Value | None]:
    """Execute one command: the new state, the stack effects, any output.

    Pure.  ``Y`` reports its value (the shell picks ``print_str`` or
    ``print_value`` by type); ``W``'s line arrives as ``line_in``.
    """
    variables, frames = state
    frame = frames[-1]
    code, pc, mode, buf, pending_at, repeat = frame

    # A frame whose code has run out never reaches here: the shell flushes
    # and pops it without spending a step, so ``pc`` indexes a command.
    c = code[pc]

    # In a mode, every character but the closing one is data.
    if mode in _CLOSES:
        grown: _Frame
        pushes: tuple[_Value, ...] = ()
        if c == _CLOSES[mode]:
            pushes = _flush_of(frame, dialect)
            grown = (code, pc + 1, "", (), pending_at, repeat)
        else:
            grown = (code, pc + 1, mode, (*buf, c), pending_at, repeat)
        return (variables, (*frames[:-1], grown)), (0, pushes, False), None

    step = _Step(
        variables=variables,
        pc=pc,
        mode=mode,
        buf=buf,
        pending_at=pending_at,
        line_in=line_in,
    )
    handler = _COMMANDS.get(c)
    if handler is None:
        # a string read from input and executed via G/I may carry any
        # character; reject it like the top-level program validation would
        raise syntax_error(
            f"unhandled command {c!r}",
            "use uppercase Latin command letters A through Z",
        )
    handler(step, view, dialect)

    pc = step.pc + 1
    pending_at = step.pending_at
    if pending_at >= 0 and pc == pending_at + 2:
        pc += 1
        pending_at = -1

    frames = (*frames[:-1], (code, pc, step.mode, step.buf, pending_at, repeat))

    if step.body is not None:
        frames = (*frames, _frame(step.body, repeat=step.call_repeat))

    # a command that left the current frame finished (the program ended or
    # a call returned) is completed now, so a caller sees ``halted`` as
    # soon as the last command runs instead of one step later.
    state = (step.variables, frames)
    fx = (step.pops, step.pushes, step.reverse)
    while frames and frames[-1][1] >= len(frames[-1][0]):
        state, fx = _finished(state, view, fx, dialect)
        frames = state[1]
        if frames and frames[-1][5] and not frames[-1][0]:
            break  # an empty Z body repeats as one observable step

    return state, fx, step.output


class _Machine:
    """Shared stack, variables, and call stack for a run."""

    def __init__(
        self,
        code: str,
        io: IO,
        *,
        integer_conversion: str = "between_letters",
    ) -> None:
        """Build a machine running ``code`` as its top-level frame."""
        self.dialect = GraphemeDialect(integer_conversion)
        code = code.replace("\n", "")
        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
            raise syntax_error(
                "Grapheme programs may only contain uppercase Latin letters",
                "use uppercase Latin command letters A through Z",
            )
        self.stack: list[_Value] = []
        self.vars: _Vars = MappingProxyType({})
        self.io = io
        self._input_reads = 0
        self.frames: tuple[_Frame, ...] = (_frame(code),)
        # Where the top-level frame ends, so ``ip`` can still report a
        # position once every frame has been popped.
        self._top_length = len(code)

    @property
    def halted(self) -> bool:
        return not self.frames

    # The VM's language-shaped view: a stack language whose call frames each
    # carry their own cursor, and with no addressable cells.

    #: ``ip`` is a position, but not one on the source text: each active frame's pc,
    #: root-to-leaf.
    #: Declared rather than left to the default so that a tuple nobody has
    #: classified is a missing answer instead of this one.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """Each active frame's pc, root-to-leaf.

        Depth-sensitive: ``(5,)`` matches only a top-level frame at pc 5,
        not ``(2, 5)``.  No frames means the program finished at its end.
        """
        if self.frames:
            return tuple(f[1] for f in self.frames)
        return (self._top_length,)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # A frame is already a tuple of its six fields, so the call stack
        # goes in as it stands rather than being unpacked field by field --
        # which is what a frame being a value rather than a record buys.
        return (
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.frames,
            self.io.progress(),
            self._input_reads,
        )

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        """Return the state a called function needs to replay an ancestor.

        Function text, ``Z``'s repeat mode, and immutable copies of the
        stack and variables.  See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        code, _, _, _, _, repeat = frame
        return (
            code,
            repeat,
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.io.progress(),
            self._input_reads,
        )

    def _apply(self, fx: _StackFx) -> None:
        """Apply a step's stack effects, in order: pops, reverse, pushes.

        No command currently reverses *and* pushes; fixing the order here
        keeps that from becoming a question.
        """
        pops, pushes, reverse = fx
        if pops:
            del self.stack[len(self.stack) - pops :]
        if reverse:
            self.stack.reverse()
        self.stack.extend(pushes)

    def step(self) -> None:
        """Execute one command, finishing any frames that are now complete."""
        if self.halted:
            return

        code, pc, mode, _, _, _ = self.frames[-1]

        # A frame whose code has run out does no work and costs no step: it
        # only flushes and pops, which the transition does.
        if pc >= len(code):
            (self.vars, self.frames), fx = _finished(
                (self.vars, self.frames), self.stack, (0, (), False), self.dialect
            )
            self._apply(fx)
            return

        # ``W`` reads only when it is a *command*.  Inside a mode every
        # character is data, so a ``W`` accumulating into a string must not
        # touch the port -- reading there turns a program that prints into
        # one that raises at EOF.
        line_in = None
        if mode == "" and code[pc] == "W":
            line_in = self.io.input_str()
            self._input_reads += 1

        (self.vars, self.frames), fx, output = _advance(
            (self.vars, self.frames), self.stack, line_in, self.dialect
        )
        self._apply(fx)

        if output is not None:
            if isinstance(output, str):
                self.io.print_str(output)
            else:
                self.io.print_value(output)


def run(
    code: str,
    io: IO,
    *,
    integer_conversion: str = "between_letters",
) -> None:
    """Run a Grapheme program to completion."""
    machine = _Machine(code, io, integer_conversion=integer_conversion)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
