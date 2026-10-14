"""Interpreter for Painfuck.

Source is first translated through the ``trans`` table: each character in
the cycles ``pevkjzwr`` and ``yuctsobqihald`` is replaced by the one ``k``
steps along its cycle, ``k`` the count translated so far; others are
dropped.  This inverts the generator's rotation, so generated programs
round-trip.

Tape of unbounded integers from one 0 cell.  ``p``/``s`` add 2/subtract
1; ``r``/``l`` move two right/one left; ``i``/``j``
read a number/byte; ``o``/``u`` print number/byte; ``a``/``b`` loop while
nonzero; ``k`` squares, ``z`` zeroes, ``h`` halves rounded down; ``w``/``q``
copy from right/left neighbour; ``c`` repeats the next command
``7**run``; ``y`` skips the next command (with probability 1/2, per the
wiki); ``v`` executes it only when the cell is zero; ``d`` resets the pointer;
``t`` repeats the previous command ``3**run``; ``e`` halts.

The tape is unbounded both ways: ``l`` at the leftmost cell grows it a
zero cell on the left.  The wiki says nothing about the left edge, and
cells left of the start are allowed.  ``d`` ("go back to the
start of tape") returns to the cell the run started on, wherever the
tape has grown since, and ``q`` at the leftmost cell copies the zero to
its left, as ``w`` at the rightmost copies the zero to its right.

A ``c`` run is one count: ``ccc`` is ``7**3``. ``cp`` runs ``p``
seven times; ``pt`` four, and ``ptt`` thirteen (the author's ``ptto``
prints 26). Each successive ``t`` contributes the next power of three.
``ct`` is four ``c``s, ``7**4``; ``ctt`` thirteen, ``7**13``.  "The last
command" is the previous character of the program, so ``vpt`` repeats ``p``
(not ``vp``) and a ``t`` after a jump repeats the text before it. A repeated
``y`` is each its own flip, so ``cyp`` spans ``{0, 2, ..., 14}`` weighted
``Binomial(7, 1/2)``.

Divergences from the retired cross-check (written alongside this
interpreter, so never independent evidence): repeated ``y`` rebound and
executed there; reads at exhausted input raise :class:`EOFError` (it
exited 3); ``i`` on a non-integer line raises :class:`HaltError` (it
exited 3); a ``t`` run walking before the program repeats NUL in both;
out-of-program reads are NUL, so an unmatched ``a`` on zero halts; ``u``
prints ``chr(cell & 0xFF)``.  Invalid runtime operations halt with
:class:`~esolangs.exceptions.HaltError`.

Step-capable via :class:`_Machine`.  ``y`` is random, so the cycle
detector is unsound on it, but the machine enumerates every coin outcome
for the bounded all-branches detector in :mod:`esolangs.vm`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw
from esolangs.runtime.source_hints import with_hint

# The two substitution cycles, in the order the cross-check scans them.
_CYCLES = ("pevkjzwr", "yuctsobqihald")

# "Past the end" (or before the start) of a program reads as NUL: the
# cross-check's program string is NUL-terminated, so an out-of-range read
# yields a command that matches no case.
_NUL = "\0"


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


#: ``(tape, loop, ptr, ind, rep, origin)``: cells, loop-entry stack,
#: pointer, cursor, repeat counter, and the index of the starting cell
#: (``d``'s target, which moves right as ``l`` grows the tape left).
#: ``c`` multiplies ``rep`` by 7 and ``t`` by 3 and the whole command runs
#: that many times, so effects are a list.
type _State = tuple[tuple[int, ...], tuple[int, ...], int, int, int, int]


@dataclass(frozen=True)
class _Print:
    """Write a value ``count`` times, as a number (``o``) or character (``u``)."""

    value: int
    as_char: bool
    count: int = 1


type _Effect = _Print


class _NeedRead(Exception):  # noqa: N818 - a control signal, not an error
    """Raised by the core when it wants an input it was not given.

    The shell reads one and re-runs the pure step with the reads so far.
    """

    def __init__(
        self,
        *,
        line: bool,
        state: _State | None = None,
    ) -> None:
        """Record whether a whole line is wanted, or one character."""
        super().__init__()
        self.line = line
        self.state = state


class _NeedCoin(Exception):  # noqa: N818 - a control signal, not an error
    """Raised by the core when ``y`` wants a coin flip it was not given."""


class _Halted(Exception):  # noqa: N818 - carries a state, not a message
    """A HaltError raised partway through a step, with the state reached."""

    def __init__(self, state: _State, effects: list[_Effect], error: HaltError) -> None:
        """Record the partial state, the writes already made, and the cause."""
        super().__init__()
        self.state = state
        self.effects = effects
        self.error = error


class _Cursor[T]:
    """Hands out the values already supplied, then asks for one more.

    ``signal`` is raised, with the caller's keywords, when the values run
    out: ``_NeedRead`` for inputs, ``_NeedCoin`` for coin flips.
    """

    def __init__(
        self, values: tuple[T, ...], signal: Callable[..., BaseException]
    ) -> None:
        """Start at the beginning of ``values``."""
        self._values = values
        self._pos = 0
        self._signal = signal

    def take(self, **kwargs: Any) -> T:
        """Return the next value, or raise the signal for another."""
        if self._pos >= len(self._values):
            raise self._signal(**kwargs)
        value = self._values[self._pos]
        self._pos += 1
        return value


def _grow(tape: tuple[int, ...], ptr: int) -> tuple[int, ...]:
    """Return ``tape`` extended with zeros so ``ptr`` is addressable."""
    if ptr < len(tape):
        return tape
    return (*tape, *([0] * (ptr + 1 - len(tape))))


def _set(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with the cell at ``ptr`` set to ``value``."""
    return (*tape[:ptr], value, *tape[ptr + 1 :])


def _skip_loop(prog: str, ind: int, n: int) -> int:
    """Return the cursor past the ``b`` matching an ``a`` that did not run."""
    val = 1
    while val != 0 and ind < n:
        ch = prog[ind]
        ind += 1
        if ch == "a":
            val += 1
        elif ch == "b":
            val -= 1
    return ind


def _collapse_right(
    tape: tuple[int, ...], ptr: int, rep: int
) -> tuple[tuple[int, ...], int]:
    """Return the tape and pointer after ``rep`` ``r``s: ``+2`` each."""
    ptr += 2 * rep
    return _grow(tape, ptr), ptr


def _collapse_left(
    tape: tuple[int, ...], ptr: int, origin: int, rep: int
) -> tuple[tuple[int, ...], int, int]:
    """Return tape, pointer and origin after ``rep`` ``l``s, as one closed form.

    Past the left edge the tape grows by the overshoot.
    """
    grown = max(0, rep - ptr)
    return (0,) * grown + tape, ptr + grown - rep, origin + grown


def _collapse_print(tape: tuple[int, ...], ptr: int, c: str, rep: int) -> _Print:
    """Return one effect carrying a repeated print's ``rep``.

    A repeated print emits the same cell every time -- nothing in the loop
    writes the tape -- so one effect carries the count rather than
    appending ``rep`` identical ones.
    """
    value = tape[ptr] if c == "o" else tape[ptr] & 0xFF
    return _Print(value, as_char=c == "u", count=rep)


def _scan_c_run(prog: str, ind: int, n: int) -> tuple[str, int, int]:
    """Consume a ``c`` run and any trailing ``t`` run.

    Return ``(command, ind, rep)``.  A ``c`` run is one count: ``ccc`` is
    ``7**3``.  A ``t`` run after the ``c`` run repeats the ``c`` itself:
    ``ct`` is four ``c``s, ``7 ** 4``; ``ctt`` thirteen, ``7 ** 13``.  Read
    here, not by the ``t`` executing (that made ``pt`` and ``ct`` unable to
    both be right).
    """
    rep = 1
    while True:
        c = prog[ind] if ind < n else _NUL
        ind += 1
        rep *= 7
        if c != "c":
            break
    adds = 0
    if c == "t":
        adds = 1
        while ind < n and prog[ind] == "t":
            ind += 1
            adds += 1
    if adds:
        rep **= (3 ** (adds + 1) - 1) // 2
        c = prog[ind] if ind < n else _NUL
        ind += 1
    return c, ind, rep


def _scan_t_run(prog: str, ind: int) -> tuple[str, int]:
    """Walk left over a ``t`` run and name its command.

    Return ``(command, rep)``.  Each ``t`` contributes another power of
    three: the author's ``ptto`` example is ``2 * (1 + 3 + 9) = 26``.  "The
    last command" is the previous character of the program, so a ``t``
    after a jump repeats the text before it.
    """
    rep = 1
    found = False
    while ind > 0:
        ind -= 1
        if prog[ind] != "t":
            found = True
            break
        rep *= 3
    return (prog[ind] if found else _NUL, rep)


class _After(Enum):
    """How a slow-path iteration can end the step: ``y`` out of repeats, or ``e``."""

    BREAK = auto()
    DONE = auto()


class _Step:
    """The pure core's mutable working state for one step."""

    def __init__(
        self,
        state: _State,
        prog: str,
        n: int,
        reads: tuple[str | int, ...],
        coins: tuple[int, ...],
    ) -> None:
        """Unpack ``state`` and read the first command."""
        self.tape, self.loop, self.ptr, self.ind, self.rep, self.origin = state
        self.prog = prog
        self.n = n
        self.reads = _Cursor(reads, _NeedRead)
        self.coins = _Cursor(coins, _NeedCoin)
        self.effects: list[_Effect] = []
        self.cmd = self.prog[self.ind]
        self.ind += 1

    def snapshot(self) -> _State:
        """Return the working fields as the value the transition works on."""
        return (self.tape, self.loop, self.ptr, self.ind, self.rep, self.origin)

    def finish(self) -> tuple[_State, tuple[_Effect, ...]]:
        """Return the step's result once the repeat counter runs out."""
        tape, loop, ptr, ind, rep, origin = self.snapshot()
        return (tape, loop, ptr, ind, rep + 1, origin), tuple(self.effects)

    def finish_at_end(self) -> tuple[_State, tuple[_Effect, ...]]:
        """Return the step's result for ``e``: the cursor past the program."""
        state = (self.tape, self.loop, self.ptr, self.n, 0, self.origin)
        return state, tuple(self.effects)


def _do_p(step: _Step) -> None:
    """Add two to the cell."""
    step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] + 2)


def _do_s(step: _Step) -> None:
    """Subtract one from the cell."""
    step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] - 1)


def _do_r(step: _Step) -> None:
    """Move the pointer two cells right, growing the tape."""
    step.ptr += 2
    step.tape = _grow(step.tape, step.ptr)


def _do_l(step: _Step) -> None:
    """Move the pointer one cell left, growing the tape past the edge."""
    if step.ptr:
        step.ptr -= 1
    else:
        step.tape, step.origin = (0, *step.tape), step.origin + 1


def _do_i(step: _Step) -> None:
    """Read a decimal integer into the cell."""
    try:
        line = step.reads.take(line=True)
    except _NeedRead as want:
        raise _NeedRead(line=True, state=step.snapshot()) from want
    try:
        step.tape = _set(step.tape, step.ptr, int(line))
    except ValueError:
        raise _Halted(
            step.snapshot(),
            step.effects,
            HaltError(hint="supply a decimal integer for i input"),
        ) from None


def _do_j(step: _Step) -> None:
    """Read one character code into the cell."""
    try:
        byte = step.reads.take(line=False)
    except _NeedRead as want:
        raise _NeedRead(line=False, state=step.snapshot()) from want
    step.tape = _set(step.tape, step.ptr, int(byte))


def _do_o(step: _Step) -> None:
    """Queue the cell as a decimal number for printing."""
    step.effects.append(_Print(step.tape[step.ptr], as_char=False))


def _do_u(step: _Step) -> None:
    """Queue the cell's low byte as a character for printing."""
    step.effects.append(_Print(step.tape[step.ptr] & 0xFF, as_char=True))


def _do_a(step: _Step) -> None:
    """Enter the loop on nonzero; skip to its end on zero."""
    if step.tape[step.ptr] != 0:
        step.loop = (*step.loop, step.ind - 1)
    else:
        step.ind = _skip_loop(step.prog, step.ind, step.n)


def _do_b(step: _Step) -> None:
    """Jump back to the matching loop entry, or fault."""
    if not step.loop:
        raise _Halted(
            step.snapshot(),
            step.effects,
            HaltError(
                "unmatched 'b': the loop stack is empty",
                hint="execute a matching loop opener before b",
            ),
        )
    step.ind = step.loop[-1]
    step.loop = step.loop[:-1]


def _do_k(step: _Step) -> None:
    """Square the cell."""
    step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] * step.tape[step.ptr])


def _do_z(step: _Step) -> None:
    """Zero the cell."""
    step.tape = _set(step.tape, step.ptr, 0)


def _do_h(step: _Step) -> None:
    """Halve the cell, rounding down per the author clarification."""
    step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] // 2)


def _do_w(step: _Step) -> None:
    """Copy the right neighbour into the cell (zero past the end)."""
    right = step.tape[step.ptr + 1] if step.ptr + 1 < len(step.tape) else 0
    step.tape = _set(step.tape, step.ptr, right)


def _do_q(step: _Step) -> None:
    """Copy the left neighbour into the cell (zero past the start)."""
    step.tape = _set(step.tape, step.ptr, step.tape[step.ptr - 1] if step.ptr else 0)


def _do_c(step: _Step) -> None:
    """Rebind to the command a ``c`` run names, with its repeat count."""
    step.cmd, step.ind, step.rep = _scan_c_run(step.prog, step.ind, step.n)


def _do_y(step: _Step) -> _After | None:
    """Flip a coin per remaining repeat, then bind the next command forward.

    Each repeat flips separately, so the count that runs is binomial
    (``cyp`` spans 0..14 by twos, not ``{0, 2}``); the wiki states only
    ``rep`` 1, where both agree.  Drawn per iteration because the repeat
    collapse cannot flip.  ``rep`` was already decremented, so the flips
    owed are this iteration plus ``rep``.
    """
    owed = step.rep + 1
    step.rep = owed - sum(step.coins.take() for _ in range(owed))
    if step.ind < step.n:
        step.cmd = step.prog[step.ind]
        step.ind += 1
    return _After.BREAK if step.rep <= 0 else None


def _do_e(_step: _Step) -> _After:
    """Halt: end the step with the cursor past the program."""
    return _After.DONE


def _do_v(step: _Step) -> None:
    """Run the next command only when the cell is zero; consume it either way."""
    if step.ind < step.n:
        step.cmd = step.prog[step.ind]
        step.rep = int(step.tape[step.ptr] == 0)
        step.ind += 1


def _do_d(step: _Step) -> None:
    """Return the pointer to the starting cell."""
    step.ptr = step.origin


def _do_t(step: _Step) -> None:
    """Rebind to the command before the ``t`` run, with its repeat count."""
    step.cmd, step.rep = _scan_t_run(step.prog, step.ind)


def _do_nothing(_step: _Step) -> None:
    """Ignore any other character."""


#: One slow-path iteration per command.  The rebinding commands (``c``,
#: ``y``, ``v``, ``t``) write the step's command directly, so the loop
#: needs no re-sync at the iteration boundary.
_DISPATCH: dict[str, Callable[[_Step], _After | None]] = {
    "p": _do_p,
    "s": _do_s,
    "r": _do_r,
    "l": _do_l,
    "i": _do_i,
    "j": _do_j,
    "o": _do_o,
    "u": _do_u,
    "a": _do_a,
    "b": _do_b,
    "k": _do_k,
    "z": _do_z,
    "h": _do_h,
    "w": _do_w,
    "q": _do_q,
    "c": _do_c,
    "y": _do_y,
    "e": _do_e,
    "v": _do_v,
    "d": _do_d,
    "t": _do_t,
}


#: Idempotent commands: a repeat of any length is one application.  ``h``
#: is not one: its repeat is a shift.
_IDEMPOTENT = frozenset("zwqd")


def _collapse_repeat(step: _Step) -> bool:
    """Collapse a repeated command into one closed form when affordable.

    ``rep`` is exponential (7 per ``c``, 3 per ``t``; up to 3**15), so the
    remaining iterations are computed directly; the slow path gives the
    same state.  This runs inside the loop because ``c``/``t``/``y``/``v``
    rebind the command mid-step.  Idempotents and ``a``/``b`` only shorten
    to a single iteration.

    Return True when the whole repeat collapsed (``rep`` is now 0).
    """
    if step.rep <= 1:
        return False
    cmd, rep = step.cmd, step.rep
    if cmd == "p":
        step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] + 2 * rep)
    elif cmd == "s":
        step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] - rep)
    elif cmd == "r":
        step.tape, step.ptr = _collapse_right(step.tape, step.ptr, rep)
    elif cmd == "l":
        step.tape, step.ptr, step.origin = _collapse_left(
            step.tape, step.ptr, step.origin, rep
        )
    elif cmd == "h":
        # Repeated floor division by two is an arithmetic shift; the author
        # rounds negative odd values down.
        step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] >> rep)
    elif cmd == "k" and -1 <= step.tape[step.ptr] <= 1:
        # Squaring has a closed form, ``x ** (2 ** rep)``, but for ``|x| > 1``
        # the *result* has 2**rep times the bits, so no rewrite makes it
        # affordable (measured at 1.0x); the loop is not the cost there.  At
        # the fixed points (``|x| <= 1``) it collapses to one squaring.
        step.tape = _set(step.tape, step.ptr, step.tape[step.ptr] ** 2)
    elif cmd in "ou":
        step.effects.append(_collapse_print(step.tape, step.ptr, cmd, rep))
    elif cmd in _IDEMPOTENT or cmd in "ab":
        # Repeating these is doing them once: an idempotent writes a value
        # fixed by the state this iteration began in, and the wiki defines
        # ``a``/``b`` as jumps, so a repeat decides the same way every
        # time.  Without this a repeated ``a`` pushed ``rep`` identical
        # stack entries, needing ``rep`` ``b``s to unwind.
        step.rep = 1
        return False
    else:
        return False
    step.rep = 0
    return True


def _advance(
    state: _State,
    prog: str,
    n: int,
    reads: tuple[str | int, ...],
    coins: tuple[int, ...],
) -> tuple[_State, tuple[_Effect, ...]]:
    """Return the state after one step, and what it wants written.

    Pure: writes are collected, not performed, because the repeat counter
    can print many times per step; inputs arrive in ``reads`` and ``y``
    coins in ``coins``.  The rebinding commands (``c``, ``y``, ``v``,
    ``t``) write the step's command directly, and a repeated ``j`` reads
    each time.
    """
    step = _Step(state, prog, n, reads, coins)

    while step.rep > 0:
        if _collapse_repeat(step):
            continue
        step.rep -= 1
        after = _DISPATCH.get(step.cmd, _do_nothing)(step)
        if after is _After.DONE:
            return step.finish_at_end()
        if after is _After.BREAK:
            break
    return step.finish()


class _Machine:
    """Per-run Painfuck state: the tape, loop stack, pointer, and cursor.

    ``y`` makes the machine non-deterministic, so the hang detector must
    exclude it.
    """

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        """Translate ``code`` and start at the first command.

        ``rng`` overrides ``y``'s coin flip; ``None`` draws for real.
        """
        self.io = io
        self._input_reads = 0
        self._random_draws = 0
        self._rng = rng
        self.prog = _translate(code)
        self.n = len(self.prog)
        self.tape: tuple[int, ...] = (0,)
        self.loop: tuple[int, ...] = ()
        self.ptr = 0
        self.ind = 0
        self.rep = 1
        self.origin = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= self.n

    # The VM's language-shaped view: Translated tape + cursor; ip the cursor, memory
    # the tape.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.loop)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.tape,
            self.loop,
            self.ptr,
            self.ind,
            self.rep,
            self.origin,
            self.io.progress(),
            self.prog,
            self._input_reads,
            self._random_draws,
        )

    def branching_snapshot(self) -> _State:
        """Return the initial no-future-input state for branch exploration."""
        return self._state

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has run past the translated program."""
        return cast(_State, state)[3] >= self.n

    def branching_successors(
        self, state: object, limit: int
    ) -> tuple[_State, ...] | None:
        """Enumerate all coin outcomes for one command without mutating us.

        Forks again on every coin the core asks for, since one ``step()`` can
        run several ``y``.  Input is declined (each branch would need its own
        cursor), so the caller reports undecided.
        """
        pending: list[tuple[int, ...]] = [()]
        successors: list[_State] = []
        while pending:
            coins = pending.pop()
            try:
                next_state, _effects = _advance(
                    cast(_State, state), self.prog, self.n, (), coins
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
                return None
            except _Halted as halt:
                # A malformed loop is a terminal (error) outcome, just as it
                # is to ``run``.  The branch graph has no error flag, so move
                # its cursor past the program; ``branching_halted`` then
                # recognizes it without pretending the failed command ran.
                tape, loop, ptr, _ind, rep, origin = halt.state
                successors.append((tape, loop, ptr, self.n, rep, origin))
            else:
                successors.append(next_state)
        return tuple(successors)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.tape, self.loop, self.ptr, self.ind, self.rep, self.origin)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.tape, self.loop, self.ptr, self.ind, self.rep, self.origin = state

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        A step can print or read more than once; the core collects writes and
        asks for each input, and this re-runs it with the inputs so far.
        """
        if self.halted:
            return
        start = self._state
        reads: tuple[str | int, ...] = ()
        coins: tuple[int, ...] = ()
        while True:
            try:
                state, effects = _advance(start, self.prog, self.n, reads, coins)
            except _NeedRead as want:
                try:
                    value = self.io.input_token() if want.line else self.io.input_char()
                except EOFError:
                    # Keep completed repeated reads and the core's cursor.
                    if want.state is None:
                        raise AssertionError("read suspension has no state") from None
                    self._restore(want.state)
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
                raise halt.error from None
            break
        for effect in effects:
            self._write(effect)
        self._restore(state)

    def _write(self, effect: _Effect) -> None:
        """Perform one collected write, ``count`` times over, as one string."""
        if effect.count == 1:
            if effect.as_char:
                self.io.print_char(chr(effect.value))
            else:
                self.io.print_num(effect.value)
            return
        piece = chr(effect.value) if effect.as_char else str(effect.value)
        self.io.print_str(piece * effect.count)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Run a Painfuck program, flipping ``y``'s coin with ``rng``.

    ``None`` draws for real.  Same signature as the other random-drawing runs.
    """
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
