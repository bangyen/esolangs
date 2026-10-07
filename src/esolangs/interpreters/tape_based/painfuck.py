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
brainfuck's page allows cells left of the start.  ``d`` ("go back to the
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

from dataclasses import dataclass
from typing import cast

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw
from esolangs.interpreters.source_hints import with_hint

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


def _half(n: int) -> int:
    """Half of ``n``, rounded down per the author clarification."""
    return n // 2


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


class _Reader:
    """Hands out the inputs already supplied, then asks for one more."""

    def __init__(self, values: tuple[str | int, ...]) -> None:
        """Start at the beginning of ``values``."""
        self._values = values
        self._pos = 0

    def take(self, *, line: bool) -> str | int:
        """Return the next input, or signal that another is needed."""
        if self._pos >= len(self._values):
            raise _NeedRead(line=line)
        value = self._values[self._pos]
        self._pos += 1
        return value


class _Coins:
    """Hands out the coin flips already drawn, then asks for one more."""

    def __init__(self, values: tuple[int, ...]) -> None:
        """Start at the beginning of ``values``."""
        self._values = values
        self._pos = 0

    def take(self) -> int:
        """Return the next flip, or signal that another is needed."""
        if self._pos >= len(self._values):
            raise _NeedCoin
        value = self._values[self._pos]
        self._pos += 1
        return value


def _grow(tape: tuple[int, ...], ptr: int) -> tuple[int, ...]:
    """Return ``tape`` extended with zeros so ``ptr`` is addressable."""
    if ptr < len(tape):
        return tape
    return (*tape, *([0] * (ptr + 1 - len(tape))))


#: Idempotent commands: a repeat of any length is one application.  ``h``
#: halves the cell it writes, so it is collapsed by the shift in
#: :func:`_advance` instead.
_IDEMPOTENT = frozenset("zwqd")


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


def _advance(
    state: _State,
    prog: str,
    n: int,
    reads: tuple[str | int, ...],
    coins: tuple[int, ...],
) -> tuple[_State, list[_Effect]]:
    """Return the state after one step, and what it wants written.

    Pure.  Writes are collected, not performed, because the repeat counter
    can print many times per step; inputs arrive in ``reads`` and ``y``
    coins in ``coins``.  The command is a local, not state: ``c``, ``y``,
    ``v``, ``t`` refetch mid-repeat, and a repeated ``j`` reads each time.
    """
    tape, loop, ptr, ind, rep, origin = state
    reader = _Reader(reads)
    coin = _Coins(coins)
    effects: list[_Effect] = []
    c = prog[ind]
    ind += 1

    while rep > 0:
        # ``rep`` is exponential (7 per ``c``, 3 per ``t``; up to 3**15),
        # and these commands are affine in it, so the remaining iterations
        # are one closed form; the slow path below gives the same state.
        # Inside the loop because ``c``/``t``/``y``/``v`` rebind ``c``
        # mid-step -- a ``t`` run names its command only after multiplying.
        # Prints, reads, ``a``/``b`` and the rebinding commands keep their iterations.
        if rep > 1:
            if c == "p":
                tape, rep = _set(tape, ptr, tape[ptr] + 2 * rep), 0
                continue
            if c == "s":
                tape, rep = _set(tape, ptr, tape[ptr] - rep), 0
                continue
            if c == "r":
                ptr += 2 * rep
                tape, rep = _grow(tape, ptr), 0
                continue
            if c == "l":
                # Past the left edge the tape grows by the overshoot.
                grown = max(0, rep - ptr)
                tape, origin = (0,) * grown + tape, origin + grown
                ptr, rep = ptr + grown - rep, 0
                continue
            if c == "h":
                # Repeated floor division by two is an arithmetic shift.
                # The author specifies rounding negative odd values down.
                tape, rep = _set(tape, ptr, tape[ptr] >> rep), 0
                continue
            if c == "k" and -1 <= tape[ptr] <= 1:
                # Squaring has a closed form -- ``x ** (2 ** rep)`` -- but
                # for ``|x| > 1`` the *result* has 2**rep times the bits, so
                # no rewrite makes it affordable (measured at 1.0x); the loop
                # is not the cost there.  At the fixed points it collapses.
                tape, rep = _set(tape, ptr, tape[ptr] * tape[ptr]), 0
                continue
            if c in "ou":
                # A repeated print emits the same cell every time -- nothing
                # in the loop writes the tape -- so one effect carries the
                # count rather than appending ``rep`` identical ones.
                value = tape[ptr] if c == "o" else tape[ptr] & 0xFF
                effects.append(_Print(value, as_char=c == "u", count=rep))
                rep = 0
                continue
            if c in _IDEMPOTENT:
                # Repeating these is doing them once: each writes a value
                # fixed by the state this iteration began in.
                rep = 1
            elif c in "ab":
                # The wiki defines these as jumps, so a repeat decides the
                # same way every time.  Without this a repeated ``a`` pushed
                # ``rep`` identical stack entries, needing ``rep`` ``b``s.
                rep = 1

        rep -= 1

        if c == "p":
            tape = _set(tape, ptr, tape[ptr] + 2)
        elif c == "s":
            tape = _set(tape, ptr, tape[ptr] - 1)
        elif c == "r":
            ptr += 2
            tape = _grow(tape, ptr)
        elif c == "l":
            if ptr:
                ptr -= 1
            else:
                tape, origin = (0, *tape), origin + 1
        elif c == "i":
            try:
                line = reader.take(line=True)
            except _NeedRead as want:
                raise _NeedRead(
                    line=True, state=(tape, loop, ptr, ind, rep, origin)
                ) from want
            try:
                tape = _set(tape, ptr, int(str(line)))
            except ValueError:
                raise _Halted(
                    (tape, loop, ptr, ind, rep, origin),
                    effects,
                    HaltError(hint="supply a decimal integer for i input"),
                ) from None
        elif c == "j":
            # ``j`` is answered with a character code, so this is already an int.
            try:
                byte = reader.take(line=False)
            except _NeedRead as want:
                raise _NeedRead(
                    line=False, state=(tape, loop, ptr, ind, rep, origin)
                ) from want
            tape = _set(tape, ptr, int(str(byte)))
        elif c == "o":
            effects.append(_Print(tape[ptr], as_char=False))
        elif c == "u":
            effects.append(_Print(tape[ptr] & 0xFF, as_char=True))
        elif c == "a":
            if tape[ptr] != 0:
                loop = (*loop, ind - 1)
            else:
                ind = _skip_loop(prog, ind, n)
        elif c == "b":
            if not loop:
                raise _Halted(
                    (tape, loop, ptr, ind, rep, origin),
                    effects,
                    HaltError(
                        "unmatched 'b': the loop stack is empty",
                        hint="execute a matching loop opener before b",
                    ),
                )
            ind = loop[-1]
            loop = loop[:-1]
        elif c == "k":
            tape = _set(tape, ptr, tape[ptr] * tape[ptr])
        elif c == "z":
            tape = _set(tape, ptr, 0)
        elif c == "h":
            tape = _set(tape, ptr, _half(tape[ptr]))
        elif c == "w":
            tape = _set(tape, ptr, tape[ptr + 1] if ptr + 1 < len(tape) else 0)
        elif c == "q":
            tape = _set(tape, ptr, tape[ptr - 1] if ptr else 0)
        elif c == "c":
            rep = 1
            while c == "c":
                c = prog[ind] if ind < n else _NUL
                ind += 1
                rep *= 7
            # A ``t`` run after the ``c`` run repeats the ``c`` itself:
            # ``ct`` is four ``c``s, ``7 ** 4``.  Read here, not by the
            # ``t`` executing (that made ``pt`` and ``ct`` unable to both be
            # right).  The run loop already pulled the next char into ``c``.
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
        elif c == "y":
            # ``y`` binds forward and each repeat flips separately, so the
            # count that runs is binomial (``cyp`` spans 0..14 by twos, not
            # ``{0, 2}``); the wiki states only ``rep`` 1, where both agree.
            # Drawn here because the affine collapses cannot flip per
            # iteration.  ``rep`` was decremented above: owed is this + ``rep``.
            owed = rep + 1
            rep = owed - sum(coin.take() for _ in range(owed))
            if ind < n:
                c = prog[ind]
                ind += 1
            if rep <= 0:
                break
        elif c == "e":
            return ((tape, loop, ptr, n, 0, origin), effects)
        elif c == "v" and ind < n:
            # "Do next command if value on tape is zero": else skip it.
            # Either way the next command is consumed once.
            c, rep = prog[ind], int(tape[ptr] == 0)
            ind += 1
        elif c == "d":
            ptr = origin
        elif c == "t":
            # Each t contributes another power of three. The author's
            # ptto example is 2 * (1 + 3 + 9) = 26.
            val = ind
            rep = 1
            found = False
            while ind > 0:
                ind -= 1
                if prog[ind] != "t":
                    found = True
                    break
                rep *= 3
            c = prog[ind] if found else _NUL
            ind = val

    return ((tape, loop, ptr, ind, rep + 1, origin), effects)


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
            self.io.position(),
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
                # Preserve partial output across a fault.  Unreachable
                # today: only ``o``/``u`` print, only ``i``/``b`` raise, and
                # a step runs one command (exhaustive to length 5 with a
                # repeat and a fault: effects always empty, probe as
                # control).  Kept so ``_Halted.effects`` has a reader.
                for effect in halt.effects:  # pragma: no cover - see above
                    self._write(effect)
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

    ``None`` draws for real.  Same signature as LaserFuck.
    """
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
