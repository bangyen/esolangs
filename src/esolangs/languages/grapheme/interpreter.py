"""Interpreter for Grapheme.

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

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, NamedTuple

from esolangs.languages.grapheme._transition import (
    _advance,
    _finished,
    _Frame,
    _frame,
    _StackFx,
    _Value,
    _Vars,
)
from esolangs.languages.grapheme.dialect import GraphemeDialect
from esolangs.languages.grapheme.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer
from esolangs.runtime.source_hints import syntax_error

_WORKSPACE_MODEL = WorkspaceModel(
    "grapheme-v1", ("stack", "variables", "frames", "input_cursor", "input_reads")
)


class _Image(NamedTuple):
    frames: tuple[_Frame, ...]
    dialect: GraphemeDialect
    length: int


def _prepare_source(code: str, *, integer_conversion: str) -> _Image:
    dialect = GraphemeDialect(integer_conversion)
    code = code.replace("\n", "")
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
        raise syntax_error(
            "Grapheme programs may only contain uppercase Latin letters",
            "use uppercase Latin command letters A through Z",
        )
    return _Image((_frame(code),), dialect, len(code))


class _Machine:
    """Shared stack, variables, and call stack for a run."""

    def __init__(
        self,
        code: str | _Image,
        io: IO,
        *,
        integer_conversion: str = "between_letters",
    ) -> None:
        """Start a machine at its top-level frame."""
        image = (
            _prepare_source(code, integer_conversion=integer_conversion)
            if isinstance(code, str)
            else code
        )
        # The initial frame is immutable; transitions replace it by value.
        self.frames, self.dialect, self._top_length = image
        self.stack: list[_Value] = []
        self.vars: _Vars = MappingProxyType({})
        self.io = io
        self._input_reads = 0
        self._writer = _BufferedOutput()

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

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        frames = tuple(
            (code, pc, mode, buf, pending, repeat)
            for code, pc, mode, buf, pending, repeat in self.frames
        )
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            stack=tuple(self.stack),
            variables=frozenset(self.vars.items()),
            frames=WorkspaceVariant("pending_output", (frames, accepted))
            if accepted
            else frames,
            input_cursor=self.io.progress(),
            input_reads=self._input_reads,
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # A frame is already a tuple of its six fields, so the call stack
        # goes in as it stands rather than being unpacked field by field --
        # which is what a frame being a value rather than a record buys.
        boundary = (
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.frames,
            self.io.progress(),
            self._input_reads,
        )
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

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

        state, fx, output = _advance(
            (self.vars, self.frames), self.stack, line_in, self.dialect
        )
        if isinstance(output, str):
            self._writer.write(self.io, output)
        elif output is not None:
            self._writer.write(
                self.io,
                format_integer(output),
                first=lambda: self.io.print_value(output),
            )
        self.vars, self.frames = state
        self._apply(fx)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the validated initial frame and dialect for each invocation."""
    if not isinstance(source, str):
        raise TypeError("grapheme machines require text source")
    if options.keys() - {"integer_conversion"}:
        raise TypeError("grapheme machines accept only integer_conversion")
    integer_conversion = options.get("integer_conversion", "between_letters")

    image = _prepare_source(source, integer_conversion=integer_conversion)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(
    code: str | _Image,
    io: IO,
    *,
    integer_conversion: str = "between_letters",
) -> CompletionReport:
    """Run a Grapheme program to completion."""
    machine = _Machine(code, io, integer_conversion=integer_conversion)
    return drive(machine, policy=CAPABILITIES.completion)


def run(
    code: str,
    io: IO,
    *,
    integer_conversion: str = "between_letters",
) -> None:
    """Run a Grapheme program to completion."""
    _execute(code, io, integer_conversion=integer_conversion)


if __name__ == "__main__":
    script_main(run)
