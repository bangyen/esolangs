"""Interpreter for Painfuck.

The program file is *not* executed directly: its source text is first
translated through a fixed substitution, the ``trans`` table.  Each source
character that appears in one of the two cycles ``pevkjzwr`` and
``yuctsobqihald`` is replaced by the character ``k`` steps further along
that cycle, where ``k`` is the number of characters translated so far (so
the substitution is a position-dependent Caesar shift per cycle); characters
in no cycle are dropped.  This is the inverse of the generator's own cycle
rotation, so a generated program round-trips.

The translated program runs over a tape of unbounded integers starting as a
single 0 cell.  ``p``/``s`` add 2/subtract 1 from the current cell,
``r``/``l`` move the pointer two right/one left (``l`` clamps at cell 0,
``r`` grows the tape), ``i``/``j`` read a number/byte from input,
``o``/``u`` print the cell as a decimal number/byte, ``a``/``b`` open/close
a while-nonzero loop, ``k`` squares the cell, ``z`` zeroes it, ``h``
halves it (truncating toward zero), ``w``/``q`` copy from the right/left
neighbor, ``c`` repeats the next command ``7``^run-length times, ``y``
skips the next command, ``v`` skips the next command when the cell is
nonzero, ``d`` resets the pointer to cell 0, ``t`` repeats the previous
command ``3``^run-length times, and ``e`` halts.  A ``c``/``t`` run also
re-fetches the command it repeats: ``c`` consumes the whole ``c`` run and
repeats the following command, ``t`` consumes the whole ``t`` run and
repeats the preceding command.

Each run is *one* count, not one per character: ``ccc`` is ``7**3`` and
``ttt`` is ``3**3``.  The two differ in what they can consume.  ``c`` sits
before its command and runs it outright, so ``cp`` runs ``p`` seven times;
``t`` sits after one that has already executed and can only add, so ``pt``
runs ``p`` four times -- once itself, three more from the ``t``.  A ``t``
cannot retroactively cancel the application that already happened.

The command before a ``t`` run may itself be a ``c`` run, and then the
``t`` adds applications of *that*: ``ct`` is four ``c``s, ``7 ** 4``.  Both
runs are read at dispatch rather than letting the ``t`` execute on its own,
which would have to hand a count backward to a command already gone -- and
no such handoff leaves ``pt`` and ``ct`` both right.

The wiki specifies neither the composition nor the run lengths, so the
arithmetic above is this implementation's reading of "do the last command
3 times" rather than a quoted rule.  No generated program pairs the two:
every ``t`` run one emits follows a ``p`` or an ``s``.

A repeated ``y`` is the same kind of gap.  Each repeat is its own flip, so a
run of ``rep`` drops ``heads`` applications of the bound command and ``cyp``
spans ``{0, 2, ..., 14}``, weighted by ``Binomial(7, 1/2)``.  All the
candidate readings agree at ``rep`` 1, the only case the wiki describes;
``docs/painfuck.md`` argues the choice and records the two rejected.

Documented divergences from the cross-check:

- ``y`` is nondeterministic (a random skip) in the wiki and in the retired
  cross-check alike, so it skips the next command with probability 1/2 here
  too; the generator and the differential corpus never use it.  A *repeated*
  ``y`` diverges: the cross-check rebound the repeated command and executed
  it, where each repeat here is its own flip.  The cross-check was written
  alongside this interpreter rather than from an independent source, so its
  agreement was never evidence about the composition.
- Reads at exhausted input raise :class:`EOFError` (the repo-wide
  convention), where the cross-check exits with status 3.
- ``i`` parses the whole input line as an integer with ``int()``; a line
  that is not a single integer raises :class:`HaltError` (the cross-check
  exits with status 3 on the same input).
- A ``t`` run that reaches the start of the program repeats a NUL in place
  of the command it walks before the program, in both implementations (the
  cross-check used to read out of bounds there; it now bounds the walk).
- The cross-check's reads before/after the program are modeled as NUL, so an
  unmatched ``a`` on a zero cell skips to the end and the program halts.
- ``u`` prints ``chr(cell & 0xFF)``, matching the cross-check's ``(char)``
  cast for cell values outside the byte range.

Invalid runtime operations halt with :class:`~esolangs.exceptions.HaltError`.

The interpreter runs on a :class:`_Machine` (the tape, the loop stack, the
pointer, and the code cursor), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once the cursor reaches the end of the code.
``y`` draws a random skip.  The ordinary cycle detector remains unsound on
it, but the machine can enumerate every coin outcome for the bounded
all-branches detector in :mod:`esolangs.vm`.
"""

import sys
from dataclasses import dataclass
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

# The two substitution cycles,.
_CYCLES = ("pevkjzwr", "yuctsobqihald")

# "Past the end" (or before the.
# cross-check's program string.
# yields a command that matches.
_NUL = "\0"


def _translate(code: str) -> str:
    """Translate the source text into an executable program.

    Mirrors the cross-check ``trans`` table: each source character found in
    one of the two cycles is replaced by the character ``k`` steps further
    along that cycle, where ``k`` counts the characters translated so far.
    Characters in no cycle are dropped.
    """
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


def _trunc2(n: int) -> int:
    """Half of ``n``, truncating toward zero (C++ ``/= 2`` semantics)."""
    return n // 2 if n >= 0 else -((-n) // 2)


# : One instant of a run:.
# : stack of loop-entry.
#: repeat counter.
# :.
# : ``rep`` is what makes a.
# : by seven and ``t`` by.
# : times, so a single step can.
# : effects are collected in a.
# : time, the shape Eval.
type _State = tuple[tuple[int, ...], tuple[int, ...], int, int, int]


@dataclass(frozen=True)
class _Print:
    """Write a value, as a number (``o``) or a character (``u``).

    ``count`` is how many times in a row -- a repeated ``o``/``u`` prints
    the *same* cell every iteration, since nothing between them changes it,
    so one effect carries the repeat instead of ``rep`` copies of itself.
    """

    value: int
    as_char: bool
    count: int = 1


type _Effect = _Print


class _NeedRead(Exception):  # noqa: N818 - a control signal, not an error
    """Raised by the core when it wants an input it was not given.

    The shell answers by reading one and running the step again.  The core
    is pure, so re-running is safe; the reads it already had are handed
    back in order, which keeps a repeated ``i`` reading the same number of
    times as the original did.
    """

    def __init__(self, *, line: bool) -> None:
        """Record whether a whole line is wanted, or one character."""
        super().__init__()
        self.line = line


class _NeedCoin(Exception):  # noqa: N818 - a control signal, not an error
    """Raised by the core when ``y`` wants a coin flip it was not given."""


class _Halted(Exception):  # noqa: N818 - carries a state, not a message
    """A HaltError raised partway through a step, with the state reached.

    ``c`` spends cursor and multiplies the repeat counter before the
    command it repeats runs, so how much of a step happened before a fault
    is not something the caller can reconstruct.  The core hands it over.
    """

    def __init__(self, state: _State, effects: list[_Effect], error: HaltError) -> None:
        """Record the partial state, the writes already made, and the cause."""
        super().__init__()
        self.state = state
        self.effects = effects
        self.error = error


class _Reader:
    """Hands out the inputs already supplied, then asks for one more.

    Both input forms draw from this one sequence, in the order the program
    asks for them; the request carries which kind the shell should fetch.
    """

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


# : Commands whose second.
# : length is one application.
# : does not itself write (a.
#: pointer to a fixed place.
# :.
# : ``h`` is absent because it.
# : writes* -- but it is still.
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

    Pure: it reads its arguments and returns a description.  The two output
    forms are collected rather than performed, because the repeat counter
    can make one step print many times; the inputs arrive in ``reads`` and
    the ``y`` coin flips in ``coins``.

    The command being run is a local, not state: ``c``, ``y``, ``v`` and
    ``t`` each fetch a *different* command partway through the repeat loop,
    and ``j`` rewrites itself to a newline so a repeated read only reads
    once.  All of that lives inside one step.
    """
    tape, loop, ptr, ind, rep = state
    reader = _Reader(reads)
    coin = _Coins(coins)
    effects: list[_Effect] = []
    c = prog[ind]
    ind += 1

    while rep > 0:
        # ``c`` and ``t`` make ``rep``.
        # per ``t`` -- so a step can.
        # The commands below are.
        # ``rep`` times has a closed.
        # the loop mutates, so the.
        # An optimization, not a.
        # produces the same state one.
        # .
        # This sits *inside* the loop.
        # ``c`` partway through a step:.
        # count and only then names the.
        # that ran once before the loop.
        # made ``rep`` large.
        # .
        # The rest need their.
        # separate effects, ``a``/``b``.
        # rebinding commands re-fetch.
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
                ptr, rep = max(0, ptr - rep), 0
                continue
            if c == "h":
                # Halving ``rep`` times is one.
                # truncates toward zero rather.
                # ``//`` is wrong for every.
                cell = tape[ptr]
                shifted = cell // (1 << rep) if cell >= 0 else -((-cell) // (1 << rep))
                tape, rep = _set(tape, ptr, shifted), 0
                continue
            if c == "k" and -1 <= tape[ptr] <= 1:
                # Squaring has a closed form --.
                # for ``|x| > 1`` the *result*.
                # no rewrite makes it.
                # is not the cost there.
                tape, rep = _set(tape, ptr, tape[ptr] * tape[ptr]), 0
                continue
            if c in "ou":
                # A repeated print emits the.
                # in the loop writes the tape.
                # count rather than appending.
                value = tape[ptr] if c == "o" else tape[ptr] & 0xFF
                effects.append(_Print(value, as_char=c == "u", count=rep))
                rep = 0
                continue
            if c in _IDEMPOTENT:
                # Repeating these is doing them.
                # fixed by the state this.
                rep = 1
            elif c in "ab":
                # The wiki defines these as.
                # if the value is zero", "go.
                # not" -- so each is a.
                # iterations changes the cell.
                # repeat therefore decides the.
                # .
                # The loop stack is this.
                # matching bracket, not part of.
                # a repeated ``a`` pushed.
                # a loop needing ``rep``.
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
        elif c == "i":
            line = reader.take(line=True)
            try:
                tape = _set(tape, ptr, int(str(line)))
            except ValueError:
                raise _Halted(
                    (tape, loop, ptr, ind, rep), effects, HaltError()
                ) from None
        elif c == "j":
            # ``j`` is answered with a.
            tape = _set(tape, ptr, int(str(reader.take(line=False))))
            # The cross-check's.
            # command variable holding.
            # only reads once and then.
            c = "\n"
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
                    (tape, loop, ptr, ind, rep),
                    effects,
                    HaltError("unmatched 'b': the loop stack is empty"),
                )
            ind = loop[-1]
            loop = loop[:-1]
        elif c == "k":
            tape = _set(tape, ptr, tape[ptr] * tape[ptr])
        elif c == "z":
            tape = _set(tape, ptr, 0)
        elif c == "h":
            tape = _set(tape, ptr, _trunc2(tape[ptr]))
        elif c == "w":
            tape = _set(tape, ptr, tape[ptr + 1] if ptr + 1 < len(tape) else 0)
        elif c == "q":
            if ptr:
                tape = _set(tape, ptr, tape[ptr - 1])
        elif c == "c":
            rep = 1
            while c == "c":
                c = prog[ind] if ind < n else _NUL
                ind += 1
                rep *= 7
            # A ``t`` run directly after.
            # which has already applied.
            # applications of it: ``ct`` is.
            # here rather than letting the.
            # would have to hand a count.
            # dispatched -- the shape that.
            # be right at the same time.
            # The run loop above already.
            # ``c``s into ``c``, so that.
            adds = 0
            if c == "t":
                adds = 1
                while ind < n and prog[ind] == "t":
                    ind += 1
                    adds += 1
            if adds:
                rep **= 1 + 3**adds
                c = prog[ind] if ind < n else _NUL
                ind += 1
        elif c == "y":
            # ``y`` binds forward to the.
            # do, and then each repeat.
            # flip per repeat, heads.
            # flips are drawn here rather.
            # affine collapses above run.
            # closed form, which cannot.
            # surviving count is what they.
            # .
            # ``rep`` flips leave ``rep -.
            # number that run is binomial.
            # spans 0 to 14 in steps of two.
            # single decision for the whole.
            # agree at ``rep`` 1, which is.
            # ``rep`` was decremented at.
            # applications still owed are.
            owed = rep + 1
            rep = owed - sum(coin.take() for _ in range(owed))
            if ind < n:
                c = prog[ind]
                ind += 1
            if rep <= 0:
                break
        elif c == "e":
            return ((tape, loop, ptr, n, 0), effects)
        elif c == "v" and tape[ptr] != 0 and ind < n:
            c = prog[ind]
            ind += 1
        elif c == "d":
            ptr = 0
        elif c == "t":
            # The whole run is one count of.
            # to clear all of it: stopping.
            # each later one a step of its.
            # predecessors, so ``ptt``.
            # times instead of nine.
            while ind < n and prog[ind] == "t":
                ind += 1
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

    return ((tape, loop, ptr, ind, rep + 1), effects)


class _Machine:
    """Per-run Painfuck state: the tape, loop stack, pointer, and cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object (``y`` makes the machine non-deterministic, so the
    hang detector must exclude it).
    """

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        """Translate ``code`` and start at the first command.

        ``rng`` overrides the ``y`` command's coin flip, which is what
        makes a stepped run reproducible; ``None`` draws for real.
        """
        self.io = io
        self._rng = rng
        self.prog = _translate(code)
        self.n = len(self.prog)
        self.tape: tuple[int, ...] = (0,)
        self.loop: tuple[int, ...] = ()
        self.ptr = 0
        self.ind = 0
        self.rep = 1

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= self.n

    # The VM's language-shaped.
    # the tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

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
            self.io.position(),
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

        A repeated ``c``/``t`` command can execute several ``y`` operations
        in one public ``step()``, so this forks again every time the pure
        core asks for a coin, rather than assuming a one-step/one-draw
        correspondence.  Input would require an independent cursor and
        future-line store for every sibling branch; declining it is sound,
        and lets the caller report an undecided result rather than sharing
        one branch's input with another.
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
                    raise TimeoutError(
                        f"undecided after {limit} coin outcomes in one Painfuck step"
                    ) from need_coin
                pending.extend(((*coins, 0), (*coins, 1)))
            except _NeedRead:
                return None
            except _Halted as halt:
                # A malformed loop is a.
                # is to ``run``.
                # its cursor past the program;.
                # recognizes it without.
                tape, loop, ptr, _ind, rep = halt.state
                successors.append((tape, loop, ptr, self.n, rep))
            else:
                successors.append(next_state)
        return tuple(successors)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.tape, self.loop, self.ptr, self.ind, self.rep)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- ``snapshot`` reads
        all five -- so they stay; the one assignment a step makes is here
        rather than in the rules above.
        """
        self.tape, self.loop, self.ptr, self.ind, self.rep = state

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The ports live here rather than in the transition: this is the
        shell.  A step can print or read more than once, because the repeat
        counter runs the same command many times -- so the core collects
        what it wants written and asks for each input as it needs it, and
        this reads one and runs it again.  Re-running is safe because the
        core is pure, and the inputs it already had are handed back in
        order.
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
                    value = self.io.input_str() if want.line else self.io.input_char()
                except EOFError:
                    # The port raises in the shell,.
                    # a thing -- but the original.
                    # cursor and spent a repeat, so.
                    tape, loop, ptr, ind, rep = start
                    self._restore((tape, loop, ptr, ind + 1, max(rep - 1, 0)))
                    raise
                reads = (*reads, value)
                continue
            except _NeedCoin:
                coins = (*coins, draw(self._rng, 2))
                continue
            except _Halted as halt:
                # A fault partway through a.
                # spent repeats, and may.
                # original wrote all of that.
                # .
                # No current command reaches.
                # to only by `o` and `u`,.
                # and `b`, and one step runs.
                # repeats that same command.
                # step that prints cannot fault.
                # cannot have printed.
                # every program to length 5.
                # faulting command,.
                # effects list was empty at all.
                # firing on each fault as its.
                # .
                # It stays because the.
                # across a fault, and a command.
                # would need it -- deleting it.
                # `effects` written at both.
                for effect in halt.effects:  # pragma: no cover - see above
                    self._write(effect)
                self._restore(halt.state)
                raise halt.error from None
            break
        for effect in effects:
            self._write(effect)
        self._restore(state)

    def _write(self, effect: _Effect) -> None:
        """Perform one collected write, ``count`` times over.

        A repeat is written as one string rather than a loop of calls: the
        value is the same every time, and ``print_str`` derives its
        end-of-line state from the text, so the repeated form and the
        looped one leave the port identical.
        """
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

    ``rng`` is the source ``y`` draws from; ``None`` draws for real, which
    is the spec's behaviour and what a plain run gets.  The machine has
    always taken one -- it is how the VM makes a stepped run reproducible
    -- but ``run`` did not forward it, so a caller holding only ``run``
    could not pin the coin without patching ``secrets`` globally.  This is
    the signature COD, WII2D and LaserFuck take.
    """
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
