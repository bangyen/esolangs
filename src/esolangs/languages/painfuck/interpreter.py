"""Interpreter for Painfuck.

Source is first translated through the ``trans`` table: each character in
the cycles ``pevkjzwr`` and ``yuctsobqihald`` is replaced by the one ``k``
steps along its cycle, ``k`` the count translated so far; others are
dropped.  This inverts the generator's rotation, so generated programs
round-trip.

Tape of unbounded integers from one 0 cell.  Step-capable.  ``y`` is random,
so the cycle detector is unsound on it, but the machine enumerates every coin
outcome for the bounded all-branches detector in :mod:`esolangs.vm`.

Commands:
    ``p``: add 2.
    ``s``: subtract 1.
    ``r``: move two right.
    ``l``: move one left.
    ``i``: read a number.
    ``j``: read a byte.
    ``o``: print the number.
    ``u``: print the byte.
    ``a``: loop while nonzero.
    ``b``: loop end.
    ``k``: square.
    ``z``: zero.
    ``h``: halve, rounded down.
    ``w``: copy from the right neighbour.
    ``q``: copy from the left neighbour.
    ``c``: repeat the next command ``7**run``.
    ``y``: skip the next command (with probability 1/2, per the wiki).
    ``v``: execute the next command only when the cell is zero.
    ``d``: reset the pointer.
    ``t``: repeat the previous command ``3**run``.
    ``e``: halt.

Input/output:
    ``u`` prints ``chr(cell & 0xFF)``.  Reads at exhausted input raise.
    ``i`` on a non-integer token halts.

Errors:
    InputExhaustedError: ``i`` or ``j`` reads at EOF.
    HaltError: ``i`` on a non-integer token; ``b`` with no open loop.

Decisions:
    * ``i`` reads one whitespace-delimited decimal token, leaving its
      delimiter; the spec leaves input framing open.
    * A trailing ``y`` consumes its owed coins and ends the step: there is
      no next command to execute.
    * The tape is unbounded both ways: ``l`` at the leftmost cell grows it a
      zero cell on the left.  The wiki says nothing about the left edge, and
      cells left of the start are allowed.
    * ``d`` ("go back to the start of tape") returns to the cell the run
      started on, wherever the tape has grown since, and ``q`` at the leftmost
      cell copies the zero to its left, as ``w`` at the rightmost copies the
      zero to its right.
    * A ``c`` run is one count: ``ccc`` is ``7**3``. ``cp`` runs ``p`` seven
      times; ``pt`` four, and ``ptt`` thirteen (the author's ``ptto`` prints
      26). Each successive ``t`` contributes the next power of three.  ``ct``
      is four ``c``s, ``7**4``; ``ctt`` thirteen, ``7**13``.
    * "The last command" is the previous character of the program, so ``vpt``
      repeats ``p`` (not ``vp``) and a ``t`` after a jump repeats the text
      before it.
    * A repeated ``y`` is each its own flip, so ``cyp`` spans
      ``{0, 2, ..., 14}`` weighted ``Binomial(7, 1/2)``.
    * Divergences from the retired cross-check (written alongside this
      interpreter, so never independent evidence): repeated ``y`` rebound and
      executed there; reads at exhausted input raise (it exited 3); ``i`` on a
      non-integer line halts (it exited 3); a ``t`` run walking before the
      program repeats NUL in both; out-of-program reads are NUL, so an
      unmatched ``a`` on zero halts.
"""

from collections.abc import Mapping
from functools import partial
from typing import Any, NamedTuple, cast

from esolangs.exceptions import HaltError, InterpreterLimitError
from esolangs.languages.painfuck._transition import (
    _EMPTY,
    _advance,
    _Cells,
    _Effect,
    _get,
    _Halted,
    _NeedCoin,
    _NeedRead,
    _State,
)
from esolangs.languages.painfuck.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RandomRuntimePlan, RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._proof import BranchFailure, branch_outcomes
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import _MAX_CELLS
from esolangs.runtime.io import IO, ScriptedIO, _BufferedOutput
from esolangs.runtime.memory import format_integer
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import with_hint

# The two substitution cycles, in the order the cross-check scans them.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def _translate(code: str) -> str:
    """Translate the source text into an executable program."""
    prog: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            p = cycle.find(char)
            if p != -1:
                prog.append(cycle[(p + k) % len(cycle)])
                k += 1
                break
    return "".join(prog)


class _Image(NamedTuple):
    program: str


type _PendingOutput = tuple[_State, tuple[_Effect, ...]]
type _PortValues = tuple[tuple[str | int, ...], tuple[int, ...]]
type _BranchState = _State | tuple[_State] | tuple[_State, _PortValues]


def _dense(cells: _Cells, span: tuple[int, int]) -> tuple[int, ...]:
    """Return the visited tape, leftmost cell first, as the debugger shows it."""
    low, high = span
    size = high - low + 1
    if size > _MAX_CELLS:
        raise InterpreterLimitError(
            f"Painfuck visited tape exceeds the {_MAX_CELLS}-cell dense view limit",
            hint="inspect individual cells with debugger watches or breakpoints",
        )
    tape = [0] * size
    for pos, value in zip(*cells, strict=True):
        tape[pos - low] = value
    return tuple(tape)


_WORKSPACE_MODEL = WorkspaceModel(
    "painfuck-v1",
    (
        "tape",
        "loops",
        "pointer",
        "instruction",
        "repeat",
        "origin",
        "input_cursor",
        "input_reads",
        "draws",
    ),
)


class _Machine:
    """Per-run Painfuck state: the tape, loop stack, pointer, and cursor.

    ``y`` makes the machine non-deterministic, so the hang detector must
    exclude it.
    """

    def __init__(
        self, code: str | _Image, io: IO, rng: Randomness | None = None
    ) -> None:
        """Start at the first command of the translated program.

        ``rng`` overrides ``y``'s coin flip; ``None`` draws for real.
        """
        self.io = io
        self._input_reads = 0
        self._random_draws = 0
        self._rng = rng
        self._pending_output: _PendingOutput | None = None
        self._pending_ports: _PortValues | None = None
        self._fault: tuple[tuple[object, ...], tuple[str, ...]] | None = None
        self._writer = _BufferedOutput()
        self.prog = _translate(code) if isinstance(code, str) else code.program
        self.n = len(self.prog)
        self.cells = _EMPTY
        self.loop: tuple[int, ...] = ()
        self.pos = 0
        self.ind = 0
        self.rep = 1
        self.span = (0, 0)

    @property
    def halted(self) -> bool:
        """Whether execution finished without a terminal fault."""
        return self._fault is None and self.ind >= self.n

    # The VM's language-shaped view: Translated tape + cursor; ip the cursor, memory
    # the tape.

    @property
    def memory(self) -> list[int]:
        """The visited cells, leftmost first."""
        return list(self.tape)

    def memory_at(self, index: int) -> int | None:
        """Read one cell by its index from the left edge of the visited tape."""
        low, high = self.span
        pos = low + index
        return _get(self.cells, pos) if low <= pos <= high else None

    @property
    def tape(self) -> tuple[int, ...]:
        """The visited cells, leftmost first; ``ptr`` and ``origin`` index it."""
        return _dense(self.cells, self.span)

    @property
    def ptr(self) -> int:
        """The pointer's index into ``tape``."""
        return self.pos - self.span[0]

    @property
    def origin(self) -> int:
        """The starting cell's index into ``tape``."""
        return -self.span[0]

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.loop)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        pending = self._output_boundary()
        instruction: int | WorkspaceVariant = self.ind
        if pending is not None:
            instruction = WorkspaceVariant("pending_output", (self.ind, *pending))
        elif self._fault is not None:
            instruction = WorkspaceVariant("halt_fault", (self.ind, *self._fault))
        elif self._pending_ports is not None:
            instruction = self._port_boundary()
        return _WORKSPACE_MODEL.capture(
            # The visited tape, as before the sparse store: the ledger prices
            # the cells a run reaches, and its pins were measured on these.
            tape=self.tape,
            loops=self.loop,
            pointer=self.ptr,
            instruction=instruction,
            repeat=self.rep,
            origin=self.origin,
            input_cursor=self.io.progress(),
            input_reads=self._input_reads,
            draws=self._random_draws,
        )

    def _output_boundary(self) -> tuple[object, ...] | None:
        pending = self._pending_output
        if pending is None:
            return None
        state, effects = pending
        return (
            state,
            tuple((effect.value, effect.as_char, effect.count) for effect in effects),
            self._writer.accepted or 0,
        )

    def _port_boundary(self) -> WorkspaceVariant:
        assert self._pending_ports is not None
        return WorkspaceVariant("pending_ports", (self.ind, *self._pending_ports))

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = (
            self.cells,
            self.loop,
            self.pos,
            self.ind,
            self.rep,
            self.span,
            self.io.progress(),
            self.prog,
            self._input_reads,
            self._random_draws,
        )
        if self._fault is not None:
            return (*boundary, self._fault)
        pending = self._output_boundary()
        if pending is not None:
            return (*boundary, pending)
        if self._pending_ports is not None:
            return (*boundary, self._port_boundary())
        return boundary

    def branching_snapshot(self) -> _BranchState:
        """Return control state with any effects already accepted by this command."""
        if self._fault is not None:
            raise self._fresh_fault(*self._fault)
        if self._pending_output is not None:
            return (self._pending_output[0],)
        if self._pending_ports is not None:
            return self._state, self._pending_ports
        return self._state

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has run past the translated program."""
        current = cast(_BranchState, state)
        return len(current) == 6 and current[3] >= self.n

    def branching_successors(
        self, state: object, limit: int
    ) -> tuple[_State | BranchFailure, ...] | None:
        """Enumerate all coin outcomes for one command without mutating us.

        Forks again on every coin the core asks for, since one ``step()`` can
        run several ``y``. A read needs an external cursor and stays
        undecided while the search explores the other coin outcomes.
        """
        if limit < 1:
            return None
        current = cast(_BranchState, state)
        if len(current) == 1:
            return current
        if len(current) == 2:
            current, (reads, accepted_coins) = current
        else:
            reads, accepted_coins = (), ()
        pending = [accepted_coins]
        successors: list[_State | BranchFailure] = []
        while pending:
            coins = pending.pop()
            try:
                next_state, _effects = _advance(
                    current, self.prog, self.n, reads, coins
                )
            except _NeedCoin as need_coin:
                if len(pending) + len(successors) + 2 > limit:
                    raise with_hint(
                        TimeoutError(
                            f"undecided after {limit} coin outcomes "
                            "in one Painfuck step"
                        ),
                        (
                            "increase the branching state/outcome limit if "
                            "feasible or reduce coin-repeated instructions"
                        ),
                    ) from need_coin
                pending.extend(((*coins, 0), (*coins, 1)))
            except _NeedRead:
                successors.append(BranchFailure())
            except _Halted as halt:
                successors.append(BranchFailure(halt.error))
            else:
                successors.append(next_state)
        return branch_outcomes(successors)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.cells, self.loop, self.pos, self.ind, self.rep, self.span)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.cells, self.loop, self.pos, self.ind, self.rep, self.span = state

    @staticmethod
    def _fresh_fault(args: tuple[object, ...], notes: tuple[str, ...]) -> HaltError:
        error = HaltError(*args)
        for note in notes:
            error.add_note(note)
        return error

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        A step can print or read more than once; the core collects writes and
        asks for each input, and this re-runs it with the inputs so far.
        """
        if self._fault is not None:
            raise self._fresh_fault(*self._fault)
        if self.ind >= self.n:
            return
        if self._pending_output is not None:
            self._finish_output(*self._pending_output)
            return
        start = self._state
        pending = self._pending_ports
        reads, coins = pending if pending is not None else ((), ())
        try:
            while True:
                try:
                    state, effects = _advance(start, self.prog, self.n, reads, coins)
                except _NeedRead as want:
                    try:
                        value = (
                            self.io.input_token() if want.line else self.io.input_char()
                        )
                    except EOFError:
                        # Physical EOF commits the completed reads and the cursor.
                        if want.state is None:
                            raise AssertionError(
                                "read suspension has no state"
                            ) from None
                        self._restore(want.state)
                        reads, coins = (), ()
                        raise
                    self._input_reads += 1
                    reads = (*reads, value)
                    continue
                except _NeedCoin:
                    coins = (*coins, draw(self._rng, 2))
                    self._random_draws += 1
                    continue
                except _Halted as halt:
                    self._restore(halt.state)
                    self._fault = (
                        halt.error.args,
                        tuple(getattr(halt.error, "__notes__", ())),
                    )
                    reads, coins = (), ()
                    raise halt.error from None
                break
        except BaseException:
            # Only replay accepted effects when the core has not committed.
            self._pending_ports = (reads, coins) if reads or coins else None
            raise
        if pending is not None:
            self._pending_ports = None
        if effects:
            self._finish_output(state, effects)
        else:
            self._restore(state)

    def _finish_output(self, state: _State, effects: tuple[_Effect, ...]) -> None:
        """Finish this command without replaying accepted reads, draws or writes."""
        for index, effect in enumerate(effects):
            try:
                self._write(effect)
            except BaseException:
                if isinstance(self.io, ScriptedIO):
                    self._pending_output = state, effects[index:]
                raise
        self._pending_output = None
        self._restore(state)

    def _write(self, effect: _Effect) -> None:
        """Perform one collected write, ``count`` times over, as one string."""
        io = self.io
        if effect.count == 1:
            if effect.as_char:
                char = chr(effect.value)
                if isinstance(io, ScriptedIO):
                    self._writer.write(io, char, first=partial(io.print_char, char))
                else:
                    io.print_char(char)
            elif isinstance(io, ScriptedIO):
                self._writer.write(
                    io,
                    format_integer(effect.value),
                    first=partial(io.print_num, effect.value),
                )
            else:
                io.print_num(effect.value)
            return
        piece = chr(effect.value) if effect.as_char else format_integer(effect.value)
        if isinstance(io, ScriptedIO):
            self._writer.write(io, piece * effect.count)
        else:
            io.print_str(piece * effect.count)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Translate source once and bind randomness for each invocation."""
    if not isinstance(source, str):
        raise TypeError("painfuck machines require text source")
    if options.keys() - {"rng"}:
        raise TypeError("painfuck machines accept only the rng runtime option")
    image = _Image(_translate(source))
    return RandomRuntimePlan.driven(
        partial(_Machine, image), policy=CAPABILITIES.completion
    ).bind(options.get("rng"))


def _execute(
    code: str | _Image, io: IO, rng: Randomness | None = None
) -> CompletionReport:
    """Run a Painfuck program, flipping ``y``'s coin with ``rng``.

    ``None`` draws for real.  Same signature as the other random-drawing runs.
    """
    machine = _Machine(code, io, rng)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Run a Painfuck program, flipping ``y``'s coin with ``rng``.

    ``None`` draws for real.  Same signature as the other random-drawing runs.
    """
    _execute(code, io, rng)


if __name__ == "__main__":
    script_main(run)
