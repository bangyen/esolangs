"""Interpreter for Forþ.

Digits 0-9 and A-F push, ``:`` duplicates, ``+``/``-``/``*``/``/``/``%``
do arithmetic (top on the right), ``~`` complements, ``.`` prints the top
as a character, ``,`` reads a line pushing each byte (rightmost on top),
``(``/``[`` branch/loop while the top is nonzero, ``{`` stores a scope
under the number atop the stack, ``;`` calls it, ``o`` reverses, ``c``
rotates three, ``v`` swaps two; anything else is ignored.

Arithmetic wraps to signed 32-bit and ``/``/``%`` truncate toward zero
(C++11).  ``;`` on a key no ``{`` stored calls an empty scope.  The machine
has an explicit call stack (one frame per scope); ``halted`` signals clean
completion and a repeated ``snapshot`` proves a loop.  A top-level abort
sets the machine's ``error`` so ``run`` raises HaltError.

Input/output:
    ``,`` reads a line, excluding its newline, and pushes its Unicode code
    points; it raises at EOF (the cross-check exits 3).  ``.`` prints Unicode
    scalars.  Values outside that range retain the reference's byte fallback.

Errors:
    InputExhaustedError: ``,`` at EOF.
    HaltError: An empty-stack pop; in the top-level scope, the other invalid
    operations (binary op under two values, ``c`` under three, division by
    zero, unterminated bracket).  In a called scope those abort only the
    innermost scope, as the cross-check's discarded status did.

Decisions:
    * The spec says nothing on errors or EOF; a clean-room reading exits on
      the first invalid operation instead.
    * The spec asks for a string without defining its delimiter; comma reads
      one line, excluding its newline, and pushes its Unicode code points.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from operator import add, mul, sub
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.for_thorn._scopes import (
    SNAPSHOT_CODECS as SNAPSHOT_CODECS,
)
from esolangs.languages.for_thorn._scopes import (
    _Frame,
    _Frames,
    _prepare_source,
    _Scopes,
)
from esolangs.languages.for_thorn.lifecycle import CAPABILITIES
from esolangs.runtime._capabilities import _AncestorEntry
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import trunc_div, trunc_mod, wrap_int32

_BINARY: dict[str, Callable[[int, int], int]] = {
    "+": add,
    "-": sub,
    "*": mul,
    "/": trunc_div,
    "%": trunc_mod,
}


# The frames are the reason this is a stack rather than a cursor: ``;``
# and all three bracket forms push one, and a ``[`` body is re-pushed
# whenever it finishes with a nonzero top.  A frame carries its own code,
# because a called scope runs text that is not the program's.
#
# ``error`` is state and not an exception: an abort ends the innermost
# scope the way completing it would, and only at the top level does it
# mean the run failed.  ``run`` reads it after the loop.
class _State(NamedTuple):
    """One instant of a run.

    The shared operand stack, the scope table ``{`` fills and ``;`` calls,
    the frame stack, and whether the *top-level* scope aborted.
    """

    stack: tuple[int, ...]
    table: _Scopes
    frames: _Frames
    error: bool


def _top(stack: tuple[int, ...]) -> int:
    """Return the top of ``stack``, halting when there is none."""
    if not stack:
        raise HaltError(
            "the stack is empty, so there is no top value to read",
            hint="push a value before reading or removing the stack top",
        )
    return stack[-1]


def _at(frame: _Frame, pc: int) -> _Frame:
    """Return ``frame`` with its cursor moved to ``pc``."""
    return _Frame(frame.code, pc, frame.loop, frame.offset, frame.ends)


def _finalize(state: _State) -> _State:
    """Pop completed frames, re-running a ``[`` body while its top holds.

    A fresh pass is finalized by a later step, so an empty body is a no-op
    step whose repeated snapshot proves a hang.
    """
    frames = state.frames
    while frames and frames[-1].pc >= len(frames[-1].code):
        frame = frames[-1]
        if frame.loop and _top(state.stack) != 0:
            return state._replace(frames=(*frames[:-1], _at(frame, 0)))
        frames = frames[:-1]
    return state._replace(frames=frames)


def _abort(state: _State) -> _State:
    """End the innermost scope on an invalid operation (status 3).

    Behaves like the scope completing; a top-level scope halts with
    ``error`` set.
    """
    frames = state.frames
    frame = frames[-1]
    ended = state._replace(frames=(*frames[:-1], _at(frame, len(frame.code))))
    finalized = _finalize(ended)
    return finalized._replace(error=finalized.error or len(frames) == 1)


def _bracket_end(frame: _Frame, at: int) -> int | None:
    """Return the local cursor after the closer, if it is in this frame."""
    end = frame.ends.get(frame.offset + at)
    if end is not None and end <= frame.offset + len(frame.code):
        return end - frame.offset
    return None


class _Step(NamedTuple):
    """One command offered to the dispatch handlers.

    The state after the active frame's cursor moved past ``char``, that
    advanced frame and frame stack (a bracket's scan starts from them),
    and the line a ``,`` command arrived with.
    """

    state: _State
    char: str
    frame: _Frame
    frames: _Frames
    line: str | None

    @property
    def stack(self) -> tuple[int, ...]:
        """The shared operand stack the command works on."""
        return self.state.stack


def _literal_step(step: _Step) -> _State | None:
    """Push a digit (``0``-``9``) or a hex letter (``A``-``F``); else decline."""
    char, stack = step.char, step.stack
    if "0" <= char <= "9":
        return step.state._replace(stack=(*stack, ord(char) - 48))
    if "A" <= char <= "F":
        return step.state._replace(stack=(*stack, ord(char) - 55))
    return None


def _stack_step(step: _Step) -> _State | None:
    """Handle ``:``, ``~``, ``.``, ``o`` and ``c``; else decline."""
    char, state, stack = step.char, step.state, step.stack
    if char == ":":
        return state._replace(stack=(*stack, _top(stack)))
    if char == "~":
        return state._replace(stack=(*stack[:-1], ~_top(stack)))
    if char == ".":
        # The print already happened in the shell; this only pops.
        _top(stack)
        return state._replace(stack=stack[:-1])
    if char == "o":
        return state._replace(stack=tuple(reversed(stack)))
    if char == "c":
        if len(stack) < 3:
            return _abort(state)
        return state._replace(stack=(*stack[:-3], *stack[-2:], stack[-3]))
    return None


def _transfer_step(step: _Step) -> _State | None:
    """Handle ``,`` (push the read line) and ``;`` (call a scope); else decline."""
    char, state, stack = step.char, step.state, step.stack
    if char == ",":
        read = tuple(ord(ch) for ch in (step.line or ""))
        return state._replace(stack=(*stack, *read))
    if char == ";":
        scope = state.table.frame(_top(stack))
        return state._replace(stack=stack[:-1], frames=(*step.frames, scope))
    return None


def _bracket_step(step: _Step) -> _State | None:
    """Handle ``(``/``[``/``{``: scan the body, then branch, loop or store it."""
    char, state, stack = step.char, step.state, step.stack
    if char not in "([{":
        return None
    frame = step.frame
    end = _bracket_end(frame, frame.pc - 1)
    if end is None:
        ended = (*step.frames[:-1], _at(frame, len(frame.code)))
        return _abort(state._replace(frames=ended))
    frames = (*step.frames[:-1], _at(frame, end))
    state = state._replace(frames=frames)
    if char in "([" and not _top(stack):
        return state
    body = _Frame(
        frame.code[frame.pc : end - 1],
        loop=char == "[",
        offset=frame.offset + frame.pc,
        ends=frame.ends,
    )
    if char in "([":
        return state._replace(frames=(*frames, body))
    table = state.table.store(_top(stack), body)
    return state._replace(table=table)


def _operator_step(step: _Step) -> _State | None:
    """Handle ``+``/``-``/``*``/``/``/``%`` and the swap ``v``; else decline."""
    char, state, stack = step.char, step.state, step.stack
    if char not in "+-*/%v":
        return None
    if len(stack) < 2:
        return _abort(state)
    two, one = stack[-1], stack[-2]
    rest = stack[:-2]
    if char == "v":
        return state._replace(stack=(*rest, two, one))
    # Both operands are consumed before the divisor is tested, so a
    # zero-divisor abort leaves the stack without them.
    if char in "/%" and two == 0:
        return _abort(state._replace(stack=rest))
    return state._replace(stack=(*rest, wrap_int32(_BINARY[char](one, two))))


#: The command groups, in the order ``_advance`` offers each character to
#: them; the groups partition the command set, so a character is handled by
#: exactly one of them and every other character is ignored.
_STEP_HANDLERS: tuple[Callable[[_Step], _State | None], ...] = (
    _literal_step,
    _stack_step,
    _transfer_step,
    _bracket_step,
    _operator_step,
)


def _advance(state: _State, line: str | None = None) -> _State:
    """Return the state after executing one command of the active frame.

    Pure; ``.``'s value is read by the caller first, ``,``'s line arrives
    as ``line``.  An abort is a value, not a raise, which is why a called
    scope's invalid operation is swallowed and a top-level one fails.
    """
    state = _finalize(state)
    if not state.frames:
        return state
    frame = state.frames[-1]
    if frame.pc >= len(frame.code):
        return state  # a finished pass (an empty loop body) is a no-op step

    char = frame.code[frame.pc]
    frame = _at(frame, frame.pc + 1)
    frames = (*state.frames[:-1], frame)
    state = state._replace(frames=frames)
    step = _Step(state, char, frame, frames, line)
    for handler in _STEP_HANDLERS:
        result = handler(step)
        if result is not None:
            return result
    return state


_WORKSPACE_MODEL = WorkspaceModel(
    "for-thorn-v1", ("stack", "scopes", "frames", "input_cursor", "input_reads")
)


class _Machine:
    """Per-run Forþ state: the shared stack, scope table, and call stack.

    A ``[`` loop that never exhausts its top is a finite-state cycle the
    hang detector can prove.
    """

    def __init__(
        self, code: str | _Frame, io: IO, *, track_ancestors: bool = True
    ) -> None:
        """Start with the top-level ``code`` as the only frame."""
        self.io = io
        self._writer = _BufferedOutput()
        self._fault: tuple[tuple[object, ...], tuple[str, ...]] | None = None
        self.stack: tuple[int, ...] = ()
        self.table = _Scopes()
        frame = _prepare_source(code) if isinstance(code, str) else code
        self.frames: tuple[_Frame, ...] = (frame,)
        self._input_reads = 0
        self._ancestor_history: tuple[_AncestorEntry, ...] | None = (
            () if track_ancestors else None
        )
        self.error = False  # the top-level scope aborted (status 3)
        # Where the top-level frame ends, kept because ``ip`` still has to
        # report a position after that frame has been popped.
        self._length = len(frame.code)

    @property
    def halted(self) -> bool:
        """Whether every scope has completed without a terminal fault."""
        return not self.frames and self._fault is None

    # The VM's language-shaped view: a stack language with a frame stack and
    # no addressable cells.

    #: ``ip`` is a position, but not one on the source text: each live frame's pc,
    #: outermost first.
    #: Declared rather than left to the default so that a tuple nobody has
    #: classified is a missing answer instead of this one.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """Each live frame's pc, outermost first.

        No frames means the top-level one finished at the end of the
        program, which is what is reported then.
        """
        frames = self.frames
        return tuple(f.pc for f in frames) if frames else (self._length,)

    def _workspace_frames(self) -> tuple[tuple[str, int, bool], ...] | WorkspaceVariant:
        frames = tuple((frame.code, frame.pc, frame.loop) for frame in self.frames)
        if self._fault is not None:
            return WorkspaceVariant("halt_fault", (frames, *self._fault))
        accepted = self._writer.accepted
        return (
            WorkspaceVariant("pending_output", (frames, accepted))
            if accepted
            else frames
        )

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            stack=self.stack,
            scopes=frozenset(self.table.items()),
            frames=self._workspace_frames(),
            input_cursor=self.io.progress(),
            input_reads=self._input_reads,
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = (
            self.stack,
            self.table,
            tuple((f.code, f.pc, f.loop) for f in self.frames),
            self.io.progress(),
            self._input_reads,
        )
        if self._fault is not None:
            return (*boundary, self._fault)
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    @property
    def _ancestor_entries(self) -> tuple[_AncestorEntry, ...] | None:
        """Return the recursive frame activations from outermost to innermost."""
        return self._ancestor_history

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        """Return the state a called scope needs to replay an ancestor.

        Scope text plus the shared stack and scope table; ``loop``
        distinguishes a stored scope from a bracket body with the same text.
        See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        return (
            frame.code,
            frame.loop,
            self.stack,
            self.table,
            self.io.progress(),
            self._input_reads,
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return _State(self.stack, self.table, self.frames, self.error)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.stack, self.table, self.frames, self.error = state

    def step(self) -> None:
        """Execute one command of the active frame.

        Finished frames are finalized first, as the original did, so the
        ports see the frame about to run.
        """
        if self._fault is not None:
            args, notes = self._fault
            error = HaltError(*args)
            for note in notes:
                error.add_note(note)
            raise error
        if not self.frames:
            return
        state = _finalize(self._state)
        frames = state.frames
        char = ""
        # The cursor moves past the command before the command runs, and
        # the original had already written that when anything it did
        # raised -- an empty stack, or the input port at EOF. Preserve
        # those boundaries while a refused output leaves . pending.
        #
        # A bracket walks further than one place: its scan runs before the
        # condition is tested, so a raise afterwards leaves the cursor past
        # the whole body.
        if frames and frames[-1].pc < len(frames[-1].code):
            frame = frames[-1]
            char = frame.code[frame.pc]
            if char in "([{":
                end = _bracket_end(frame, frame.pc)
                cursor = len(frame.code) if end is None else end
            else:
                cursor = frame.pc + 1
            frames = (*frames[:-1], _at(frame, cursor))
        if char == "." and state.stack:
            value = state.stack[-1]
            output = (
                chr(value)
                if 0 <= value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF
                else chr(value & 0xFF)
            )
            self._writer.write(
                self.io, output, first=partial(self.io.print_char, output)
            )
        self._restore(state._replace(frames=frames))
        # Finalizing can pop a completed scope and the next command can
        # immediately replace it. Trim before comparing the command's depths.
        entries = self._ancestor_history
        if entries and len(frames) <= len(entries):
            entries = entries[: max(0, len(frames) - 1)]
            self._ancestor_history = entries

        line = None
        if char == ",":
            line = self.io.input_str()
            self._input_reads += 1

        try:
            self._restore(_advance(state, line))
        except HaltError as fault:
            self._fault = fault.args, tuple(getattr(fault, "__notes__", ()))
            raise
        if entries is not None:
            depth = len(self.frames)
            if depth > len(frames):
                self._ancestor_history = (
                    *entries,
                    _AncestorEntry(self.frame_entry_key(self.frames[-1])),
                )
            elif depth <= len(entries):
                self._ancestor_history = entries[: max(0, depth - 1)]
        # Raised here, not in ``run``, so a stepped VM fails as ``run`` does.
        if self.error:
            error = HaltError(
                "the top-level scope aborted, which Forþ reports as status 3"
            )
            self._fault = error.args, ()
            raise error


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the source and delimiter index across calls and invocations."""
    source = require_text_source(source, options, "for_thorn")

    frame = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(frame, io), lambda io: _execute(frame, io))


def _execute(code: str | _Frame, io: IO) -> CompletionReport:
    """Run a Forþ program."""
    return drive(
        _Machine(code, io, track_ancestors=False), policy=CAPABILITIES.completion
    )


def run(code: str, io: IO) -> None:
    """Run a Forþ program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
