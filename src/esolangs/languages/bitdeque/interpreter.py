"""Interpreter for Bitdeque.

PUSH/INJECT append the register to the deque, POP/EJECT pop it (0 when
empty), INVERT flips the register, GOTO N jumps to the Nth command,
counting from 1 as "the Nth operation" reads, when it is nonzero.

Input/output:
    No input.  The deque is printed space-separated when the program ends.

Errors:
    ProgramError: a word that is not one of the six upper-case commands.
    HaltError: a taken ``GOTO 0``.

Decisions:
    * A target past the last command ends the run and a taken GOTO 0 raises
      HaltError (the wiki leaves both open).
    * The wiki has no I/O, so the deque is printed at the end -- the repo's
      convention.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.bitdeque.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import keyword_hint, syntax_error


class _State(NamedTuple):
    """One instant of a run; a value, so each transition returns a new one.

    The deque is a ``tuple`` for the same reason.  ``rendered`` is state
    because the dump happens once, *after* the cursor passes the last token,
    so position alone cannot tell "about to print" from "already printed";
    it stays out of ``snapshot``.  The tokens are not in the transition's
    view but are in ``snapshot``; removing them would change every hash the
    cycle detector has stored.
    """

    ind: int  # token cursor
    reg: int
    deq: tuple[int, ...]
    rendered: bool  # the end-of-run dump has been printed


_COMMANDS = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", "GOTO")
_TOKEN = re.compile(r"(?<!\S)(INJECT|PUSH|EJECT|POP|INVERT|GOTO\s+\d+)(?!\S)")


# :func:`_advance` is pure over an immutable ``_State``; the dump is the shell's
# post-halt step.
def _advance(state: _State, sym: str) -> _State:
    """Return the state after executing one token.

    PUSH/POP work the back, INJECT/EJECT the front -- a deque.  GOTO N
    lands on index ``N - 2`` so the shared increment carries it to the Nth
    command; a taken ``GOTO 0`` names no command and raises.
    """
    ind, reg, deq = state.ind, state.reg, state.deq
    if sym == "PUSH":
        deq = (*deq, reg)
    elif sym == "INJECT":
        deq = (reg, *deq)
    elif sym == "POP":
        reg, deq = (deq[-1], deq[:-1]) if deq else (0, deq)
    elif sym == "EJECT":
        reg, deq = (deq[0], deq[1:]) if deq else (0, deq)
    elif sym == "INVERT":
        reg ^= 1
    elif reg:
        if not (target := int(sym[4:])):
            raise HaltError(
                "GOTO 0 names no command; commands count from 1",
                hint="GOTO 1 jumps to the first command",
            )
        ind = target - 2
    return _State(ind + 1, reg, deq, state.rendered)


def _reject_stray_text(code: str) -> None:
    """Refuse a word that is not one of the six commands.

    A seventh word is never deliberate, and ``findall`` would skip it.
    """
    if stray := _TOKEN.sub(" ", code).split():
        raise syntax_error(
            f"{stray[0]!r} is not a Bitdeque command; the commands are "
            f"INJECT, PUSH, EJECT, POP, INVERT and GOTO n, in upper case",
            keyword_hint(
                stray[0],
                _COMMANDS,
                "write uppercase commands; GOTO takes a nonnegative target",
            ),
        )


_WORKSPACE_MODEL = WorkspaceModel(
    "bitdeque-v2", ("instruction", "register", "deque", "rendered", "input_cursor")
)


type _Image = tuple[str, ...]


def _prepare_source(code: str) -> _Image:
    _reject_stray_text(code)
    return tuple(_TOKEN.findall(code))


class _Machine:
    """Per-run Bitdeque state: the token cursor, register, and deque."""

    #: Whether the deque is printed on the step *after* the halt.
    #: It belongs to the language, not to whoever is stepping it: ``run``
    #: ends its loop with one more ``step()``, so a caller who stops at
    #: ``halted`` has driven the program correctly and still holds none of
    #: its output.
    completion = CAPABILITIES.completion

    def __init__(self, code: str | _Image, io: IO) -> None:
        """Tokenize ``code`` and reset the register, deque, and cursor."""
        self.io = io
        self.tokens = _prepare_source(code) if isinstance(code, str) else code
        # ``halted`` is read twice per token -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.tokens)
        self.state = _State(0, 0, (), rendered=False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state.ind

    @property
    def reg(self) -> int:
        return self.state.reg

    @property
    def deq(self) -> tuple[int, ...]:
        return self.state.deq

    @property
    def rendered(self) -> bool:
        """Whether the end-of-run deque dump has already been printed."""
        return self.state.rendered

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last token."""
        return self.state.ind >= self.size

    # The VM's language-shaped view: the deque is the store, and the one
    # register reads as a stack of one.

    @property
    def memory(self) -> list[int]:
        """The deque, front first."""
        return list(self.state.deq)

    @property
    def stack(self) -> list[object]:
        """The single register, as a one-element stack."""
        return [self.state.reg]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state.ind,
            register=self.state.reg,
            deque=self.state.deq,
            rendered=self.state.rendered,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The fields this returned before ``rendered`` joined the state, in
        # the same order.  ``rendered`` stays out: the detector compares
        # states of a running machine.
        ind, reg, deq, _rendered = self.state
        return (self.tokens, ind, reg, deq, self.io.progress())

    def step(self) -> None:
        """Execute one token, printing the deque once the cursor ends.

        The print is the post-halt step, as other dumps spell it.
        """
        ind, _reg, _deq, rendered = self.state
        if ind >= self.size:
            if not rendered:
                self.render()
                self.state = self.state._replace(rendered=True)
            return
        self.state = _advance(self.state, self.tokens[ind])

    def render(self) -> None:
        """Print the deque contents, one value per space, no trailing newline."""
        self.io.print_str(" ".join(map(str, self.state.deq)))


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain parsed source and give each invocation fresh state."""
    if not isinstance(source, str):
        raise TypeError("bitdeque machines require text source")
    if options:
        raise TypeError("bitdeque machines accept no runtime options")
    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Run a Bitdeque program and print the deque at the end."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Bitdeque program and print the deque at the end."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
