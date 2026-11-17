"""Interpreter for moar cheese :3.

A program is a space-separated list of instructions run left to right
over a queue of bytes, initially empty.  At halt the queue prints as a
string.  There is no input.

Commands:
    ``c(code)``  (re)define the instruction ``c``, one ASCII character, to
                 run ``code``.
    ``(c)``      enqueue the character ``c``.
    ``()``       dequeue a byte and run it as an instruction; on an empty
                 queue, halt.
    ``c``        run ``c``'s code; an undefined ``c`` does nothing.

Errors:
    ProgramError: a malformed instruction, a missing separator, or a
        character outside printable ASCII.

Decisions:
    * A call runs the body as it stood when the call began, then returns
      to the caller: a body that redefines its own name finishes its old
      code.  The cyclic-tag encoding ``l(... l) l`` needs no other reading.
      A call in tail position replaces its frame, so that loop runs in
      constant space.
    * Instructions are separated by runs of spaces, as in every example.
      ``(0)(1)`` is an error, not two enqueues.  A final newline is
      allowed.
    * ``(()`` and ``())`` are errors.  Neither appears on the page, and
      either would unbalance a body's parentheses.
    * Names are printable ASCII other than space and parentheses.  ``(c)``
      takes any printable ASCII character, since Hello world enqueues
      ``( )``.
    * Halting on an empty dequeue still prints the queue, which is empty.
"""

from collections import deque
from collections.abc import Mapping
from typing import Any

from esolangs.exceptions import ProgramError
from esolangs.languages.moar_cheese_3.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.source_hints import syntax_error

#: ``("enq", c)``, ``("deq", "")``, ``("call", c)`` or ``("def", c, body)``,
#: where ``body`` indexes the parsed bodies; body 0 is the program.
type _Op = tuple[Any, ...]


def _error(message: str) -> ValueError:
    return syntax_error(
        message,
        "write c(code), (c), () or c, separated by spaces",
        error_type=ProgramError,
    )


def _parse(code: str) -> tuple[tuple[_Op, ...], ...]:
    """Return every body's instructions; body 0 is the program."""
    code = code.removesuffix("\n")
    if bad := next((c for c in code if not " " <= c <= "~"), None):
        raise _error(f"{bad!r} is not printable ASCII")
    bodies: list[tuple[_Op, ...]] = [()]

    def body(start: int, stop: int) -> tuple[_Op, ...]:
        ops: list[_Op] = []
        i = start
        while i < stop:
            if code[i] == " ":
                i += 1
                continue
            if ops and code[i - 1] != " ":
                raise _error(f"no space before column {i + 1}")
            if code.startswith("()", i):
                ops.append(("deq", ""))
                i += 2
            elif code[i] == "(":
                if i + 2 >= stop or code[i + 2] != ")" or code[i + 1] in "()":
                    raise _error(f"bad enqueue at column {i + 1}")
                ops.append(("enq", code[i + 1]))
                i += 3
            elif code[i] == ")":
                raise _error(f"unmatched ) at column {i + 1}")
            elif i + 1 < stop and code[i + 1] == "(":
                depth, j = 1, i + 2
                while depth:
                    if j >= stop:
                        raise _error(f"unclosed body at column {i + 2}")
                    depth += {"(": 1, ")": -1}.get(code[j], 0)
                    j += 1
                bodies.append(())
                index = len(bodies) - 1
                bodies[index] = body(i + 2, j - 1)
                ops.append(("def", code[i], index))
                i = j
            else:
                ops.append(("call", code[i]))
                i += 1
        return tuple(ops)

    bodies[0] = body(0, len(code))
    return tuple(bodies)


def _advance(
    top: tuple[int, int],
    bodies: tuple[tuple[_Op, ...], ...],
    defs: Mapping[str, int],
    head: str | None,
) -> tuple[tuple[int, int] | None, int | None, _Op | None, bool]:
    """Run the top frame's next instruction.

    Return the frame's successor (None once finished), a body to push, the
    effect and whether the run halts.  Pure: ``head`` is the queue's first
    byte, or None when it is empty.  The effect is ``("enq", c)``,
    ``("deq", "")`` or ``("def", c, body)``.
    """
    body, index = top
    op = bodies[body][index]
    # A finished frame is dropped before a call pushes, so tail calls loop
    # in constant space.
    nxt = (body, index + 1) if index + 1 < len(bodies[body]) else None
    kind, name = op[0], op[1]
    if kind == "deq":
        if head is None:
            return nxt, None, None, True
        name = head
    if kind in ("deq", "call"):
        target = defs.get(name)
        push = target if target is not None and bodies[target] else None
        return nxt, push, op if kind == "deq" else None, False
    return nxt, None, op, False


_WORKSPACE_MODEL = WorkspaceModel(
    "moar-cheese-3-v1", ("frames", "definitions", "queue")
)


class _Machine:
    """A moar cheese :3 run: call frames, definitions and the byte queue."""

    def __init__(self, code: str | tuple[tuple[_Op, ...], ...], io: IO) -> None:
        self.bodies = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.frames: list[tuple[int, int]] = [(0, 0)] if self.bodies[0] else []
        self.defs: dict[str, int] = {}
        self.queue: deque[str] = deque()
        self.halted = False
        self._writer = _BufferedOutput()

    @property
    def ind(self) -> int:
        """The next instruction's index in its body."""
        return self.frames[-1][1] if self.frames else 0

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            frames=(
                WorkspaceVariant("pending_output", (tuple(self.frames), accepted))
                if accepted
                else tuple(self.frames)
            ),
            definitions=frozenset(self.defs.items()),
            queue="".join(self.queue),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = (
            self.halted,
            tuple(self.frames),
            tuple(sorted(self.defs.items())),
            "".join(self.queue),
        )
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        """Run one instruction; print the queue on halting."""
        if self.halted:
            return
        if not self.frames:
            halted, effect = True, None
        else:
            head = self.queue[0] if self.queue else None
            nxt, push, effect, halted = _advance(
                self.frames[-1], self.bodies, self.defs, head
            )
        if halted:
            if self.queue:
                self._writer.write(self.io, "".join(self.queue))
            self.halted = True
            return
        if nxt is None:
            self.frames.pop()
        else:
            self.frames[-1] = nxt
        if push is not None:
            self.frames.append((push, 0))
        if effect is None:
            return
        if effect[0] == "enq":
            self.queue.append(effect[1])
        elif effect[0] == "deq":
            self.queue.popleft()
        else:
            self.defs[effect[1]] = effect[2]


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("moar cheese :3 machines require text source")
    if options:
        raise TypeError("moar cheese :3 machines accept no runtime options")
    bodies = _parse(source)
    return RuntimePlan(lambda io: _Machine(bodies, io), lambda io: _execute(bodies, io))


def _execute(code: str | tuple[tuple[_Op, ...], ...], io: IO) -> CompletionReport:
    """Run a moar cheese :3 program until it halts."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a moar cheese :3 program and print its final queue."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
