r"""INTERCAL-72 with the C-INTERCAL extensions: a language built to be unlike any.

A program is a list of statements, run top to bottom.  Each opens with ``DO``
or ``PLEASE`` (one fifth to one third must say ``PLEASE``, else E079 or
E099), optionally after a ``(label)``, and may add ``NOT`` (start abstained)
and ``%n`` (run with n% chance), and end ``ONCE`` or ``AGAIN``.

- Values are 16-bit onespot ``.1`` and 32-bit twospot ``:1`` scalars, and
  tail ``,1`` and hybrid ``;1`` arrays, dimensioned ``,1 <- #3 BY #4`` and
  indexed ``,1 SUB #2 #1``.  Constants are ``#n``, 0-65535.
- The operators are mingle ``$`` (interleave two 16-bit values' bits),
  select ``~`` (keep the left's bits where the right has ones, packed
  right), and unary ``&`` ``V`` ``?`` (and, or, xor of each bit with its
  neighbour, rotating).  Sparks ``'`` and rabbit-ears ``"`` group.
- ``.1 <- expr`` assigns.  ``(n) NEXT`` calls label n, pushing a return;
  ``RESUME #k`` returns k levels up, ``FORGET #k`` drops k returns without
  going anywhere.  ``COME FROM (n)``
  takes control whenever label n finishes.  ``ABSTAIN FROM`` and
  ``REINSTATE`` switch statements off and on by label or by gerund
  (``CALCULATING``); ``STASH``/``RETRIEVE`` save and restore variables,
  ``IGNORE``/``REMEMBER`` make them read-only.  ``GIVE UP`` halts.
- ``WRITE IN`` reads numbers spelt as digit words (``ONE TWO``); ``READ
  OUT`` prints them in Roman numerals.  An array reads and writes the
  Turing Tape: characters as differences, bits reversed.

Also here: computed ``ABSTAIN``, ``COME FROM`` by expression and gerund,
``NEXT FROM`` and ``TRY AGAIN``.  Not implemented: the system library,
threads, backtracking, ``CREATE``, operand overloading, ``PIN``, CLC-INTERCAL
I/O and wimpmode.

A ``%n`` draws at random; ``esolangs.run(..., seed=s)`` fixes the draw.

Input/output:
    Numeric ``WRITE IN`` at EOF raises; Turing Tape input stores 256 at EOF.

Errors:
    HaltError: every INTERCAL error, naming its E-number.  Unparsable
    statements are E000 syntax errors raised only when executed;
    program-wide checks (labels, politeness E079/E099, NEXT/ABSTAIN/COME
    FROM targets) raise at load.  No ProgramError arises.
    InputExhaustedError: numeric ``WRITE IN`` at EOF.

Decisions:
    * A statement starts at ``DO``/``PLEASE`` even inside a word
      (``DOUBLE``), as C-INTERCAL lexes; a label starts one only before an
      identifier.  A line with no identifier that is a complete core command
      stays its own statement.
    * Politeness keeps the stricter one-fifth to one-third rule for any
      length; running off the end halts quietly instead of E633.
    * Zero prints a lone overbar over an empty line, as the manual says; a
      value below 4000 prints one line, where C-INTERCAL prints an empty
      overbar line first.
    * Whitespace may split a number from its sigil and its own digits, as
      C-INTERCAL's lexer allows, though the manual says it cannot.
    * Digit words read in any case, split at any whitespace; C-INTERCAL wants
      upper case split at spaces.  Of two errors in one statement, the
      right-hand side's is raised before the target subscript's.
    * ``READ OUT`` takes any expression; a subscript list holds bare operands,
      and a subscripted element may be the left operand of a binary operator.
    * Array elements start at 0, where C-INTERCAL leaves them uninitialised;
      ``RETRIEVE`` restores an array even if it is undimensioned.
    * Turing Tape characters are code points; the tape differences are taken
      modulo 256 and output bytes are written as code points 0-255.
    * ``ONCE``/``AGAIN`` take effect when the statement is reached (for
      ``COME FROM`` when it fires); a computed ``COME FROM`` is checked at
      every labelled statement, a gerund one after every statement of that
      kind.
"""

from __future__ import annotations

import gc
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.intercal.interpreter._parse import (
    _fail,
    _Key,
    _load,
    _Node,
    _parse_expression,
    _SelfAbstain,
    _Statement,
    _statements,
    _unary,
)
from esolangs.languages.intercal.interpreter._pmap import _PMap
from esolangs.languages.intercal.interpreter._semantics import (
    _advance,
    _link,
    _NeedDraw,
    _NeedInput,
    _Program,
    _snapshot,
    _State,
    _thaw,
)
from esolangs.languages.intercal.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._fault import _Fault
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RandomRuntimePlan, RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw

_WORKSPACE_MODEL = WorkspaceModel(
    "intercal-v1",
    (
        "instruction",
        "scalars",
        "arrays",
        "ignored",
        "stashes",
        "abstentions",
        "returns",
        "last_input",
        "last_output",
        "input_cursor",
    ),
)


class _Image(NamedTuple):
    lines: tuple[str, ...]
    program: _Program
    abstained: tuple[int, ...]


def _prepare_source(code: str) -> _Image:
    lines = tuple(_statements(code))
    # The parse trees are acyclic, but the collector rescans the growing
    # heap again and again: a 33,062-statement load took 3.3 s, 1.7 s without it.
    collecting = gc.isenabled()
    gc.disable()
    try:
        statements = tuple(_load(line) for line in lines)
    finally:
        if collecting:
            gc.enable()
    polite = sum(statement.polite for statement in statements)
    if not lines or polite * 5 < len(lines) or polite * 3 > len(lines):
        raise _fail(
            "E079" if polite * 5 < len(lines) else "E099",
            "INTERCAL program is insufficiently or excessively polite",
            hint="use PLEASE on one fifth to one third of the statements",
        )
    program = _link(statements)
    abstained = tuple(int(statement.abstained) for statement in statements)
    return _Image(lines, program, abstained)


class _Machine:
    """Parsed INTERCAL statements and the immutable run state.

    ``step`` is the shell: it draws and reads only when the pure transition
    asks and writes what it returns.
    """

    def __init__(
        self, code: str | _Image, io: IO, rng: Randomness | None = None
    ) -> None:
        self.io = io
        self._rng = rng
        image = _prepare_source(code) if isinstance(code, str) else code
        self.lines, self._program, abstained = image
        self.state = _State(
            0,
            _PMap(),
            _PMap(),
            frozenset(),
            _PMap(),
            abstained,
            (),
            0,
            0,
        )

    @property
    def halted(self) -> bool:
        return self.state.ind >= len(self._program.statements)

    @property
    def ip(self) -> int:
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        return [value for _key, value in sorted(self.state.scalars.items())]

    @property
    def stack(self) -> list[object]:
        return [resume for resume, _origin in self.state.nexts]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        s = self.state

        def array(value: int | tuple[tuple[int, ...], _PMap[int, int]]) -> Hashable:
            if isinstance(value, int):
                return value
            dimensions, data = value
            return dimensions, frozenset(data.items())

        return _WORKSPACE_MODEL.capture(
            instruction=s.ind,
            scalars=frozenset(s.scalars.items()),
            arrays=frozenset(
                (key, dimensions, frozenset(data.items()))
                for key, (dimensions, data) in s.arrays.items()
            ),
            ignored=s.ignored,
            stashes=frozenset(
                (key, tuple(array(value) for value in values))
                for key, values in s.stashes.items()
            ),
            abstentions=s.abstained,
            returns=s.nexts,
            last_input=s.last_in,
            last_output=s.last_out,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[Any, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*_snapshot(self.state), self.io.progress())

    def branching_snapshot(self) -> tuple[Any, ...]:
        """Return immutable state for exhaustive ``%`` branch search."""
        return self.snapshot()

    def branching_halted(self, state: Any) -> bool:
        """Report whether an immutable state has run past its last statement."""
        return bool(state[0] >= len(self._program.statements))

    def _restore(self, state: tuple[Any, ...]) -> _State:
        """Rebuild a run state from a snapshot tuple."""
        (
            ind,
            scalars,
            arrays,
            ignored,
            stashes,
            abstained,
            nexts,
            last_in,
            last_out,
        ) = state[:9]
        return _State(
            ind=ind,
            scalars=_PMap(dict(scalars)),
            arrays=_PMap(
                {
                    key: (dimensions, _PMap(dict(data)))
                    for key, dimensions, data in arrays
                }
            ),
            ignored=frozenset(ignored),
            stashes=_PMap(
                {
                    key: tuple(_thaw(value) for value in values)
                    for key, values in stashes
                }
            ),
            abstained=tuple(abstained),
            nexts=tuple(nexts),
            last_in=last_in,
            last_out=last_out,
        )

    def branching_successors(
        self, state: Any, limit: int
    ) -> tuple[tuple[Any, ...], ...] | None:
        """Return all outcomes, or ``None`` at input or above the outcome budget.

        Replays the pure transition over explicit draw prefixes: a missing
        draw is filled with ``0`` (the scripted default) and every position
        the run drew at is also tried with ``99``, which forces the other
        outcome of a ``%chance`` qualifier.
        """
        current: tuple[Any, ...] = state
        if limit < 1:
            return None
        if self.branching_halted(current):
            return (current,)
        ind: int = current[0]
        if self._program.statements[ind].command.tag == "write" and not current[5][ind]:
            return None
        successors: list[tuple[Any, ...]] = []
        pending: list[tuple[int, ...]] = [()]
        while pending:
            prefix = pending.pop()
            base = len(prefix)
            draws = list(prefix)
            branch = self._restore(current)
            while True:
                try:
                    new_state, _effects, _used = _advance(
                        branch, self._program, tuple(draws), ()
                    )
                except _NeedDraw:
                    # Each new draw needs the current path and one flipped prefix.
                    if len(successors) + len(pending) + len(draws) - base + 2 > limit:
                        return None
                    draws.append(0)
                    continue
                except _NeedInput:
                    return None
                except _Fault as fault:
                    raise fault.error from None
                break
            filled = tuple(draws)
            pending.extend((*filled[:at], 99) for at in range(base, len(filled)))
            successors.append((*_snapshot(new_state), current[-1]))
        return tuple(successors)

    def step(self) -> None:
        """Execute one statement, drawing and reading only as asked.

        The shell performs the draws and reads the pure transition asks for
        and writes what it returns.  Each request flushes the output computed
        before it, and a fault flushes the same prefix before it is re-raised,
        so output written before a later draw, read, or halt is not lost.
        """
        if self.halted:
            return
        draws: list[int] = []
        inputs: list[int | str | None] = []
        flushed = 0
        while True:
            try:
                self.state, effects, _used = _advance(
                    self.state, self._program, tuple(draws), tuple(inputs)
                )
            except _NeedDraw as need:
                flushed = self._flush(need.effects, flushed)
                draws.append(draw(self._rng, 100))
                continue
            except _NeedInput as need:
                flushed = self._flush(need.effects, flushed)
                if need.kind == "char":
                    try:
                        inputs.append(self.io.input_char())
                    except EOFError:
                        inputs.append(None)
                else:
                    inputs.append(self.io.input_str())
                continue
            except _Fault as fault:
                self._flush(fault.effects, flushed)
                raise fault.error from None
            break
        self._flush(effects, flushed)

    def _flush(self, effects: Sequence[str], flushed: int) -> int:
        """Print ``effects`` past ``flushed``; return the new flush count."""
        for text in effects[flushed:]:
            self.io.print_str(text)
        return len(effects)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain linked statements and bind independent invocation state."""
    if not isinstance(source, str):
        raise TypeError("intercal machines require text source")
    if options.keys() - {"rng"}:
        raise TypeError("intercal machines accept only the rng runtime option")
    image = _prepare_source(source)

    def build(io: IO, rng: Randomness | None) -> _Machine:
        return _Machine(image, io, rng)

    def execute(io: IO, rng: Randomness | None) -> CompletionReport:
        return _execute(image, io, rng)

    return RandomRuntimePlan(build, execute).bind(options.get("rng"))


def _execute(
    code: str | _Image, io: IO, rng: Randomness | None = None
) -> CompletionReport:
    """Execute an INTERCAL program."""
    machine = _Machine(code, io, rng)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Execute an INTERCAL program."""
    _execute(code, io, rng)
