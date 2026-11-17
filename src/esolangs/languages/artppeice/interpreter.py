"""Interpreter for artppeice.

A program is an IRC log, one instruction per line, run top to bottom in an
endless loop.  Each line opens with an ``hh:mm:ss`` timestamp and a space.
Memory is a set of named queues of words.  The program stops only by
halting: dequeuing from a missing or empty queue, or enqueuing into a
missing one.

Commands:
    ``-!- N has joined. (W)``   create queue ``N`` holding words ``W``; without
                                the parentheses, read its words from input.
                                Nothing if ``N`` exists.
    ``-!- N has quit. (T)``     delete ``N`` and print ``T``; without the
                                parentheses, print its words.  Nothing if
                                ``N`` is missing.
    ``-!- N has changed nick to M.``  rename ``N`` to ``M``; nothing if
                                ``N`` is missing.
    ``<N> W``                   dequeue a word from ``N`` and enqueue ``W``
                                into the queue that word names.
    ``* N comment``             nothing.

Input/output:
    A join without parentheses reads one input line; its words are the
    whitespace-separated runs.  A quit prints its words joined by single
    spaces, or its parenthesized text as written, with nothing between
    quits.

Errors:
    ProgramError: a line matching no form, or no lines.
    InputExhaustedError: a join that reads at EOF.
    HaltError: a rename onto another existing queue.

Decisions:
    * Quits print with no separator.  The page's Hello and XKCD examples
      print one quit each and show no framing; the screening probe's
      byte-framing ruling chose none.
    * EOF on a reading join raises: the page gives it no value, and its
      cat program re-reads on every pass.
    * Renaming onto another existing queue is unspecified and raises
      HaltError; renaming a queue to itself is nothing.
    * The page's cyclic-tag rules ``-!- <1> bits`` match no instruction
      form and raise ProgramError; ``<1> bits`` is the evident intent.
    * A final newline is allowed; any other blank line is an error.
"""

import re
from collections import deque
from collections.abc import Mapping
from typing import Any

from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.artppeice.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.source_hints import syntax_error

_FORMS = (
    ("join", re.compile(r"-!- (\S+) has joined\.(?: \((.*)\))?")),
    ("quit", re.compile(r"-!- (\S+) has quit\.(?: \((.*)\))?")),
    ("nick", re.compile(r"-!- (\S+) has changed nick to (\S+)\.")),
    ("route", re.compile(r"<([^\s>]+)>(?: (.*))?")),
    ("note", re.compile(r"\* (\S+)(?: .*)?")),
)
_STAMP = re.compile(r"\d\d:\d\d:\d\d (.*)")

#: ``(kind, name, argument)``: a join's words (``None`` reads input), a
#: quit's text (``None`` prints the queue), a nick's new name, a route's words.
type _Op = tuple[str, str, Any]
#: What a step does to memory: create, delete, rename or move.
type _Effect = tuple[Any, ...] | None


def _parse(code: str) -> tuple[_Op, ...]:
    """Parse each line into an instruction."""
    lines = code.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise syntax_error(
            "no instructions", "write one instruction per line", error_type=ProgramError
        )
    ops = []
    for line in lines:
        stamp = _STAMP.fullmatch(line)
        for kind, form in _FORMS:
            if stamp and (m := form.fullmatch(stamp[1])):
                name, arg = m[1], m.group(2) if form.groups > 1 else None
                if kind in ("join", "route") and (arg is not None or kind == "route"):
                    arg = tuple((arg or "").split())
                ops.append((kind, name, arg))
                break
        else:
            raise syntax_error(
                f"cannot parse {line!r}",
                "start with hh:mm:ss, then -!- N has joined./quit./changed "
                "nick to M., <N> words, or * N comment",
                error_type=ProgramError,
            )
    return tuple(ops)


def _reads(pc: int, ops: tuple[_Op, ...], queues: Mapping[str, Any]) -> bool:
    """Return whether the instruction at ``pc`` reads an input line."""
    kind, name, arg = ops[pc]
    return kind == "join" and arg is None and name not in queues


def _advance(
    pc: int,
    ops: tuple[_Op, ...],
    queues: Mapping[str, deque[str]],
    line: str | None = None,
) -> tuple[int, _Effect, str | None, bool]:
    """Run one instruction; return the next line, the effect, the print, halt.

    Pure: a join's input line arrives as ``line``; ``queues`` is only read.
    """
    kind, name, arg = ops[pc]
    nxt = (pc + 1) % len(ops)
    if kind == "join" and name not in queues:
        words = arg if arg is not None else tuple((line or "").split())
        return nxt, ("create", name, words), None, False
    if kind == "quit" and name in queues:
        out = " ".join(queues[name]) if arg is None else arg
        return nxt, ("delete", name), out, False
    if kind == "nick" and name in queues and arg != name:
        if arg in queues:
            raise HaltError(f"{arg} already exists", hint="rename to a free name")
        return nxt, ("rename", name, arg), None, False
    if kind == "route":
        source = queues.get(name)
        if not source or source[0] not in queues:
            return pc, None, None, True
        return nxt, ("move", name, source[0], arg), None, False
    return nxt, None, None, False


_WORKSPACE_MODEL = WorkspaceModel("artppeice-v1", ("line", "queues", "input_cursor"))


class _Machine:
    """An artppeice run: the current line and the named queues."""

    ip_shape = "line"

    def __init__(self, code: str | tuple[_Op, ...], io: IO) -> None:
        self.ops = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.ind = 0
        self.queues: dict[str, deque[str]] = {}
        self.halted = False
        self._writer = _BufferedOutput()

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            line=(
                WorkspaceVariant("pending_output", (self.ind, accepted))
                if accepted
                else self.ind
            ),
            queues=frozenset((k, tuple(v)) for k, v in self.queues.items()),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        accepted = self._writer.accepted
        boundary = (
            self.halted,
            self.ind,
            tuple(sorted((k, tuple(v)) for k, v in self.queues.items())),
            self.io.progress(),
        )
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        """Run one instruction; a reading join reads here."""
        if self.halted:
            return
        line = None
        if _reads(self.ind, self.ops, self.queues):
            line = self.io.input_str().removesuffix("\r")
        self.ind, effect, out, self.halted = _advance(
            self.ind, self.ops, self.queues, line
        )
        if out:
            self._writer.write(self.io, out)
        if effect is None:
            return
        if effect[0] == "create":
            self.queues[effect[1]] = deque(effect[2])
        elif effect[0] == "delete":
            del self.queues[effect[1]]
        elif effect[0] == "rename":
            self.queues[effect[2]] = self.queues.pop(effect[1])
        else:
            _, source, target, words = effect
            self.queues[source].popleft()
            self.queues[target].extend(words)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("artppeice machines require text source")
    if options:
        raise TypeError("artppeice machines accept no runtime options")
    ops = _parse(source)
    return RuntimePlan(lambda io: _Machine(ops, io), lambda io: _execute(ops, io))


def _execute(code: str | tuple[_Op, ...], io: IO) -> CompletionReport:
    """Run an artppeice program until it halts."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run an artppeice program until it halts."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
