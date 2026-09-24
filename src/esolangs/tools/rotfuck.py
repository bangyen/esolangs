"""Boolean-function generator for ROTfuck.

ROTfuck advances every command one step along ``+-><,.[]`` after each
executed command, so what a character *means* depends on how many commands
have run.  The generator writes the program it wants and rotates each
character backwards by the rotation it will execute at (:class:`_Builder`).

The hard part is the loop.  A ``]`` that jumps back rotates before it seeks,
so the character it lands beside has to read as ``[`` one rotation *after*
the code it introduces -- a rotation at which that character would execute as
``.`` and print.  The way out is never to execute it: the loop is entered by
a ``[`` that fires over it, and the character is a phantom, read as ``]`` by
that forward seek and as ``[`` by every backward one.
:meth:`_Builder.loop` lays out the five parts and their rotations.
"""

from collections.abc import Callable
from itertools import product

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["rotfuck"]

# The eight-step rotation cycle: + -> - -> > -> < -> , -> . -> [ -> ] -> +.
_ROTFUCK_CHAIN = "+-><,.[]"

# Longest pad the search will build.  Not eight: a pad of eight advances the
# rotation by nothing, so it would pad forever without moving anything on.
_MAX_PAD = 6

#: Lengths, modulo eight, that a loop's ``B`` half may take.  Six and seven
#: are out because at those the loop's own phantoms read as brackets to its
#: own seeks.  One and five put the loop's two seeks two rotations apart,
#: which is exactly the spacing at which they ban all four of ``+-><`` at one
#: rotation: nothing can be written there, so no body could be padded past.
_SPANS = (0, 2, 4, 3)

#: Bits per digit of the index.  A cell is a byte, and the widest thing a
#: digit drives is a loop that marks its entry cell twice a turn, so a digit
#: of ``d`` bits needs ``2 * (2**d)`` to stay under 256.  Six is the answer;
#: seven was wrong by exactly one table, at ``n == 8``.
_RADIX_BITS = 6


def _rotfuck_rot(char: str, steps: int) -> str:
    """Advance ``char`` ``steps`` steps along the ROTfuck rotation cycle."""
    index = _ROTFUCK_CHAIN.index(char)
    return _ROTFUCK_CHAIN[(index + steps) % 8]


def _shows(cmd: str, seek: int, rot: int) -> bool:
    """Whether ``cmd``, executing at ``rot``, reads as a bracket at ``seek``.

    A seek reads the whole program at one fixed rotation, so a command that
    executes ``d`` steps after it shows there as ``rot^-d`` of itself.  A
    bracket moves the seek's depth count and pairs the loop with the wrong
    character -- a program that still runs and computes something else.
    """
    return _rotfuck_rot(cmd, seek - rot) in "[]"


def _pads() -> tuple[str, ...]:
    """Command runs that change neither the tape nor the pointer.

    Shortest first, since padding is pure cost.  A run may step right, which
    the tape always allows, but never left of where it started: ``<`` clamps
    at cell zero.
    """
    out = []
    for length in range(2, _MAX_PAD + 1, 2):
        for run in product("+-><", repeat=length):
            cells: dict[int, int] = {}
            at = low = 0
            for char in run:
                at += (char == ">") - (char == "<")
                low = min(low, at)
                cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
            if at == 0 and low == 0 and not any(cells.values()):
                out.append("".join(run))
    return tuple(out)


_PADS = _pads()


class _Builder:
    """Emitted source, plus the rotation each character will execute at.

    In straight-line code the rotation is the position, but a loop runs its
    body many times and the two part company, so the rotation is what has to
    be tracked.  ``_seeks`` holds the rotations at which some open seek is
    reading the text being written.
    """

    def __init__(self) -> None:
        """Start empty, at rotation zero, inside no seek."""
        self.src: list[str] = []
        self.rot = 0
        self.ptr = 0
        self._seeks: list[int] = []

    def _hidden(self, cmd: str, rot: int) -> bool:
        """Whether ``cmd``, executing at ``rot``, shows as no bracket."""
        return not any(_shows(cmd, seek, rot) for seek in self._seeks)

    def _put(self, cmd: str, rot: int) -> None:
        """Append the character that reads as ``cmd`` at rotation ``rot``."""
        self.src.append(_rotfuck_rot(cmd, -rot))

    def _pad(self, most: int = _MAX_PAD) -> None:
        """Advance the rotation by up to ``most``, changing nothing else."""
        for run in _PADS:
            if len(run) <= most and all(
                self._hidden(c, self.rot + i) for i, c in enumerate(run)
            ):
                self.emit(run)
                return
        raise AssertionError("no neutral pad is hidden from every open seek")

    def _fill(self, need: int) -> None:
        """Pad by exactly ``need`` rotations.

        Capping each pad at what is left stops it overshooting, so the
        remainder falls every time and an odd ``need`` runs out of pads
        rather than looping forever.
        """
        while need:
            before = self.rot
            self._pad(need)
            need -= (self.rot - before) % 8

    def _state(self) -> tuple[list[str], int, int, list[int]]:
        """Everything a failed attempt has to put back."""
        return (list(self.src), self.rot, self.ptr, list(self._seeks))

    def _restore(self, state: tuple[list[str], int, int, list[int]]) -> None:
        """Undo an attempt."""
        self.src, self.rot, self.ptr, self._seeks = state

    def emit(self, text: str) -> None:
        """Emit ``text`` in line, padding past rotations that would betray it."""
        for char in text:
            while not self._hidden(char, self.rot):
                self._pad()
            self._put(char, self.rot)
            self.rot = (self.rot + 1) % 8
            self.ptr += (char == ">") - (char == "<")

    def travel(self, goal: int) -> None:
        """Walk the pointer to cell ``goal``."""
        self.emit((">" if goal > self.ptr else "<") * abs(goal - self.ptr))

    def drain(self, work: str) -> None:
        """Loop on the cell two to the left, running ``work`` on it.

        The shape every loop here but the walk wants: the pointer sits on a
        zero cell, the cell two below it is the one being counted down, and
        ``work`` -- which runs from that cell and has to come back up two --
        is what empties it.  Afterwards the pointer is on the emptied cell.
        """
        home = self.ptr
        self.loop(lambda: self.emit("<<"), lambda: self.emit(work))
        self.ptr = home - 2

    def loop(self, every: Callable[[], None], again: Callable[[], None]) -> None:
        """Emit a loop out of two halves, run in the order ``again``, ``every``.

        Six parts, in text order, with the rotation each executes at::

            f  [        phi            fires over the phantom: its cell is 0
            p  phantom  (back)         never executed; reads '[' to a back seek
            A  again    back ...       skipped on the first pass
            x  phantom  entry - 1      reads ']' to f's seek, executes as '['
            B  every    entry ...      run on every pass, ends on the test cell
            q  ]        entry + |B|    jumps back to A while that cell is nonzero

        ``f`` fires because its cell is zero, which skips ``p`` -- the only
        way to have a back-seek target that is never executed, and so the
        only way to have a loop at all.  Its seek stops at ``x``, so the first
        pass starts at ``B``, and ``A`` is padded until the whole cycle is 0
        modulo 8: that is what makes every pass read the same commands and
        the exit rotation independent of the trip count.

        Why two halves.  ``f``'s cell is the cell ``B`` starts from on the
        first pass, and ``q``'s is the cell ``B`` ends on; a loop whose
        pointer came back to where it started would need those to be the same
        cell, which cannot be both zero and the nonzero thing being tested.
        So the pointer has to move by ``B``'s displacement each pass, and
        ``A`` is what moves it back.  Only ``f``'s seek stops before ``B``,
        so ``B`` is read by one seek and ``A`` by two -- nested loops belong
        in ``B``.

        The caller owes: a zero under the pointer, an ``A`` that leaves the
        pointer on a nonzero cell (a zero there fires ``x``), and halves whose
        lengths agree in parity, since a pad is a pair.
        """
        for _ in range(8):
            state = self._state()
            try:
                self._loop_once(every, again)
            except AssertionError:
                self._restore(state)
                self._pad()
            else:
                return
        raise AssertionError("no rotation admits this loop")

    def _every(self, every: Callable[[], None], span: int) -> list[str] | None:
        """Emit ``B`` once to measure it; keep it only if it fits ``span``.

        Its length decides the rotation of the seek that reads it, and that
        seek decides how much padding its own commands need -- so the length
        is a fixed point, found by trying each residue.
        """
        state = self._state()
        self._seeks.append((self.rot + span + 2) % 8)
        self.rot = (self.rot + 1) % 8
        mark = len(self.src)
        body = None
        try:
            entry = self.rot
            every()
            self._fill((span - self.rot + entry) % 8)
            body = self.src[mark:]
        except AssertionError:
            body = None
        self._restore(state)
        return body

    def _loop_once(self, every: Callable[[], None], again: Callable[[], None]) -> None:
        """Emit the loop at the current rotation, or fail leaving a mess."""
        for span in _SPANS:
            state = self._state()
            try:
                self._span_once(every, again, span)
            except AssertionError:
                self._restore(state)
            else:
                return
        raise AssertionError("no body length fits this rotation")

    def _span_once(
        self, every: Callable[[], None], again: Callable[[], None], span: int
    ) -> None:
        """Emit the loop with its ``B`` half of length ``span`` modulo eight."""
        phi = self.rot
        entry = (phi + 1) % 8
        back = (entry + span + 1) % 8
        fixed = (("[", phi), ("[", back), ("]", entry), ("]", entry + span))
        if not all(self._hidden(cmd, at) for cmd, at in fixed):
            raise AssertionError("a loop's own brackets would show in a seek")
        body = self._every(every, span)
        if body is None:
            raise AssertionError("this body length does not fit")

        self._put("[", phi)
        self._put("[", back)
        self._seeks += [entry, back]
        self.rot = back
        again()
        self._fill((entry - 1 - self.rot) % 8)
        self._seeks = self._seeks[:-2]
        self._put("]", entry)
        self.src += body
        self._put("]", entry + span)
        self.rot = back

    def text(self) -> str:
        """Return the finished, rotated source."""
        return "".join(self.src)


def _read_digit(out: _Builder, cell: int) -> None:
    """Read one input bit into ``cell`` as 1 or 2, never as zero.

    A walk is a do-while -- its test sits after its body -- so the count it
    carries has to start nonzero.  The digits therefore carry a bias of one,
    and Horner's rule carries it through: with ``d`` in ``{1, 2}``,
    ``a -> 2a + d - 2`` leaves the accumulator at the digit plus one.
    """
    out.travel(cell)
    out.emit(",")
    out.emit("-" * (_ASCII_ZERO - 1))


def _groups(width: int) -> list[int]:
    """Bit counts of the index's base-128 digits, lowest digit first.

    See :data:`_RADIX_BITS` for why six.  A digit is just a run of input
    bits, so splitting the index costs no division at all: each digit is
    read, folded and spent before the next one is read.
    """
    out = []
    while width > 0:
        out.append(min(_RADIX_BITS, width))
        width -= out[-1]
    return out


def _walk(out: _Builder, stride: int) -> None:
    """Carry the count under the pointer leftwards, ``stride`` cells a step.

    Entered on the carrier holding the count, it leaves the pointer on the
    carrier ``stride * count`` cells below.  The inner loop is entered on the
    carrier being filled rather than one past the one being emptied, which
    keeps its skipped half to ``-<...<+``: it has to be short, because three
    seeks read it at once and no three rotations leave all eight writable.
    """
    out.travel(2)

    def carry() -> None:
        """One step: empty this carrier into the next, then drop one."""
        out.emit("<" * (stride + 2))
        out.loop(
            lambda: out.emit(">" * stride),
            lambda: out.emit("-" + "<" * stride + "+"),
        )
        out.emit("<" * stride + "-")

    # ``>>+`` parks on the carrier just above, which the walk has left for
    # good, and leaves it nonzero so the phantom in front of the carry is
    # stepped over rather than fired.
    out.loop(carry, lambda: out.emit(">>+"))
    out.ptr = 0


def _select(out: _Builder, n: int, used: list[int], groups: list[int]) -> None:
    """Read the inputs and walk the pointer to the entry they select.

    One digit at a time, highest first, and each digit's walk runs before the
    next digit is read -- which is what makes the reads free of any pointer
    arithmetic.  After a walk the pointer sits on a carrier whose address
    nobody knows, so everything here is relative to it: offset 0 is that
    carrier, the even offsets above it are clean carriers to work in, and
    offset 1 is a passed entry's cell, which nothing reads again.
    """
    chosen = set(used)
    cursor = 0
    for width, stride in zip(reversed(groups), reversed(_strides(groups)), strict=True):
        taken = 0
        slot = 0
        while taken < width:
            here = cursor
            cursor += 1
            if here not in chosen:
                out.travel(1)
                out.emit(",")
                continue
            if taken == 0:
                _read_digit(out, 2)
            else:
                twice = 2 * slot + 4
                out.travel(twice)
                out.drain("->+>++")
                _read_digit(out, twice + 2)
                out.travel(twice + 4)
                out.drain("-<<+>>>>++")
                out.travel(twice)
                out.emit("--")
                slot += 1
            taken += 1
        acc = 2 * slot + 2
        out.travel(acc + 2)
        out.drain("-" + "<" * acc + "+" + ">" * (acc + 2) + "++")
        _walk(out, stride)
    while cursor < n:
        out.travel(1)
        out.emit(",")
        cursor += 1


def _strides(groups: list[int]) -> list[int]:
    """How far each digit's walk steps, in cells, lowest digit first."""
    out = []
    shift = 0
    for width in groups:
        out.append(2 << shift)
        shift += width
    return out


def rotfuck(truth_table: str) -> str:
    """Build a ROTfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program is a tape lookup rather than a decision tree.  The table is
    written out once, one entry per even cell, which leaves the odd cells as
    the zero carriers a variable-distance pointer walk needs; it is written
    backwards so the walk can run leftwards from the far end.  The inputs are
    then read six bits at a time, and each digit's walk carries its count
    leftwards until the count runs out.  The walks together step
    ``2 * index`` cells, plus one stride each that the start allows for, so
    the pointer lands on the carrier beside the entry the inputs select, and
    one ``<`` reads it.

    The cost is two ``>`` and half a ``+`` per table entry, and O(n) plus a
    fixed stride allowance for everything else: the walks' *length* is data,
    not code, which is what a per-row layout has to spend characters on.
    """
    n = _validate_truth_table(truth_table)

    # Ignored inputs are still read but do not enter the index.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    size = 2 ** len(used)

    # Entry ``e`` sits at cell ``2 * (size - 1 - e)`` with its carrier just
    # above it.  Each walk overshoots by one stride, because its test comes
    # after its body, so the strip starts that much further up.
    groups = _groups(len(used))
    start = 2 * size - 1 + sum(_strides(groups))

    out = _Builder()
    for slot in range(size):
        if table[size - 1 - slot] == "1":
            out.emit("+")
        out.emit(">>")
    out.travel(start)
    out.ptr = 0

    _select(out, n, used, groups)
    out.travel(-1)
    out.emit("+" * _ASCII_ZERO)
    out.emit(".")
    return out.text()
