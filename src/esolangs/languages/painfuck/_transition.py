"""Apply one Painfuck command to state and supplied port values."""

from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, cast

from esolangs.exceptions import HaltError
from esolangs.runtime.memory import parse_integer

# "Past the end" (or before the start) of a program reads as NUL: the
# cross-check's program string is NUL-terminated, so an out-of-range read
# yields a command that matches no case.
_NUL = "\0"


#: ``(cells, loop, pos, ind, rep, span)``: the nonzero cells as sorted
#: positions and their values, loop-entry stack, pointer, cursor, repeat
#: counter, and the ``(low, high)`` positions visited.  Positions count from
#: the starting cell (``d``'s target).  Sparse because ``ctt`` moves 7**13
#: cells in one step: a dense tuple built them all and a trace-corpus program
#: was killed at 8 GB (2026-11-17).  ``span`` keeps the dense tape the debugger
#: shows, and makes snapshots equal exactly when those tapes are.
#: ``c`` multiplies ``rep`` by 7 and ``t`` by 3 and the whole command runs
#: that many times, so effects are a list.
type _Cells = tuple[tuple[int, ...], tuple[int, ...]]
type _State = tuple[_Cells, tuple[int, ...], int, int, int, tuple[int, int]]


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


#: No cell stored.  Positions apart from values, so ``bisect`` compares
#: plain ints: a key function cost 10% of the step rate.
_EMPTY: _Cells = ((), ())


def _get(cells: _Cells, pos: int) -> int:
    """Return the cell at ``pos``; unstored cells are zero."""
    positions, values = cells
    at = bisect_left(positions, pos)
    return values[at] if at < len(positions) and positions[at] == pos else 0


def _put(cells: _Cells, pos: int, value: int) -> _Cells:
    """Return ``cells`` with ``pos`` set to ``value``, storing no zero."""
    positions, values = cells
    at = bisect_left(positions, pos)
    after = at + (at < len(positions) and positions[at] == pos)
    if value:
        return (
            (*positions[:at], pos, *positions[after:]),
            (*values[:at], value, *values[after:]),
        )
    return (*positions[:at], *positions[after:]), (*values[:at], *values[after:])


def _visit(span: tuple[int, int], pos: int) -> tuple[int, int]:
    """Return ``span`` widened to include ``pos``."""
    low, high = span
    return (pos, high) if pos < low else (low, pos) if pos > high else span


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


def _collapse_print(cells: _Cells, pos: int, c: str, rep: int) -> _Print:
    """Return one effect carrying a repeated print's ``rep``.

    A repeated print emits the same cell every time -- nothing in the loop
    writes the tape -- so one effect carries the count rather than
    appending ``rep`` identical ones.
    """
    value = _get(cells, pos) if c == "o" else _get(cells, pos) & 0xFF
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
    if c == "t":
        adds = 1
        while ind < n and prog[ind] == "t":
            ind += 1
            adds += 1
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
    while ind > 0:
        ind -= 1
        if prog[ind] != "t":
            return prog[ind], rep
        rep *= 3
    return _NUL, rep


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
        self.cells, self.loop, self.pos, self.ind, self.rep, self.span = state
        self.prog = prog
        self.n = n
        self.reads = _Cursor(reads, _NeedRead)
        self.coins = _Cursor(coins, _NeedCoin)
        self.effects: list[_Effect] = []
        self.cmd = self.prog[self.ind]
        self.ind += 1

    @property
    def cell(self) -> int:
        """The cell under the pointer."""
        # ``_get`` inlined: the extra call cost 1% of the step rate.
        positions, values = self.cells
        pos = self.pos
        at = bisect_left(positions, pos)
        return values[at] if at < len(positions) and positions[at] == pos else 0

    @cell.setter
    def cell(self, value: int) -> None:
        self.cells = _put(self.cells, self.pos, value)

    def move(self, pos: int) -> None:
        """Point at ``pos``, widening the visited span."""
        self.pos = pos
        self.span = _visit(self.span, pos)

    def snapshot(self) -> _State:
        """Return the working fields as the value the transition works on."""
        return (self.cells, self.loop, self.pos, self.ind, self.rep, self.span)

    def finish(self) -> tuple[_State, tuple[_Effect, ...]]:
        """Return the step's result once the repeat counter runs out."""
        cells, loop, pos, ind, rep, span = self.snapshot()
        return (cells, loop, pos, ind, rep + 1, span), tuple(self.effects)

    def finish_at_end(self) -> tuple[_State, tuple[_Effect, ...]]:
        """Return the step's result for ``e``: the cursor past the program."""
        state = (self.cells, self.loop, self.pos, self.n, 0, self.span)
        return state, tuple(self.effects)


def _do_p(step: _Step) -> None:
    """Add two to the cell."""
    step.cell += 2


def _do_s(step: _Step) -> None:
    """Subtract one from the cell."""
    step.cell -= 1


def _do_r(step: _Step) -> None:
    """Move the pointer two cells right."""
    step.move(step.pos + 2)


def _do_l(step: _Step) -> None:
    """Move the pointer one cell left."""
    step.move(step.pos - 1)


def _do_i(step: _Step) -> None:
    """Read a decimal integer into the cell."""
    try:
        line = step.reads.take(line=True)
    except _NeedRead as want:
        raise _NeedRead(line=True, state=step.snapshot()) from want
    try:
        step.cell = parse_integer(cast(str, line))
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
    step.cell = int(byte)


def _do_o(step: _Step) -> None:
    """Queue the cell as a decimal number for printing."""
    step.effects.append(_Print(step.cell, as_char=False))


def _do_u(step: _Step) -> None:
    """Queue the cell's low byte as a character for printing."""
    step.effects.append(_Print(step.cell & 0xFF, as_char=True))


def _do_a(step: _Step) -> None:
    """Enter the loop on nonzero; skip to its end on zero."""
    if step.cell != 0:
        step.loop = (*step.loop, step.ind - 1)
    else:
        step.ind = _skip_loop(step.prog, step.ind, step.n)


def _do_b(step: _Step) -> None:
    """Pop the loop entry; jump back only while the cell is nonzero."""
    if not step.loop:
        raise _Halted(
            step.snapshot(),
            step.effects,
            HaltError(
                "unmatched 'b': the loop stack is empty",
                hint="execute a matching loop opener before b",
            ),
        )
    if step.cell != 0:
        step.ind = step.loop[-1]
    step.loop = step.loop[:-1]


def _do_k(step: _Step) -> None:
    """Square the cell."""
    step.cell **= 2


def _do_z(step: _Step) -> None:
    """Zero the cell."""
    step.cell = 0


def _do_h(step: _Step) -> None:
    """Halve the cell, rounding down per the author clarification."""
    step.cell //= 2


def _do_w(step: _Step) -> None:
    """Copy the right neighbour into the cell (zero past the end)."""
    step.cell = _get(step.cells, step.pos + 1)


def _do_q(step: _Step) -> None:
    """Copy the left neighbour into the cell (zero past the start)."""
    step.cell = _get(step.cells, step.pos - 1)


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
    if step.ind == step.n:
        step.rep = 0
        return _After.BREAK
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
        step.rep = int(step.cell == 0)
        step.ind += 1


def _do_d(step: _Step) -> None:
    """Return the pointer to the starting cell."""
    step.pos = 0


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
        step.cell += 2 * rep
    elif cmd == "s":
        step.cell -= rep
    elif cmd == "r":
        step.move(step.pos + 2 * rep)
    elif cmd == "l":
        step.move(step.pos - rep)
    elif cmd == "h":
        # Repeated floor division by two is an arithmetic shift; the author
        # rounds negative odd values down.
        step.cell >>= rep
    elif cmd == "k" and -1 <= step.cell <= 1:
        # Squaring has a closed form, ``x ** (2 ** rep)``, but for ``|x| > 1``
        # the *result* has 2**rep times the bits, so no rewrite makes it
        # affordable (measured at 1.0x); the loop is not the cost there.  At
        # the fixed points (``|x| <= 1``) it collapses to one squaring.
        step.cell **= 2
    elif cmd in "ou":
        step.effects.append(_collapse_print(step.cells, step.pos, cmd, rep))
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
