"""ROTfuck Boolean program generator: a tape lookup spelled against the rotation.

ROTfuck turns every command one step around its cycle after each executed
command, so a character's meaning depends on how many commands have run.
The generator writes brainfuck and :class:`_Builder` spells each command
against the cycle in force, backward by default or forward by ``rotation``.
The two cycles read the eight commands in opposite directions, each keeping
``[`` and ``]`` adjacent, so the phase arithmetic is the same for both.

A bracket seeks its partner before rotating, so a loop is sound when its ``[``
and ``]`` execute at the same rotation modulo eight (the *phase*) and nothing
between them reads as a bracket there (:func:`_shows`).  Then every trip
leaves the rotation where it found it, and a skip, an exit and a jump back all
resume one past the phase.  A body is padded to seven modulo eight with
no-op runs (:meth:`_Builder._pad`), each command placed to hide from every open
seek.

Size:
    O(T): two ``>`` and half a ``+`` per entry, the rest O(n) plus walk
    strides; n=10 random 1847: 4,061 chars, n=10 and: 1,769 chars.

Decisions:
    A repeated block is not shared: a brainfuck copy is at least 19 commands
    a cell against 2.5 for an entry.
"""

import math
from collections.abc import Callable

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.rotfuck.interpreter import (
    ROTATIONS,
    ROTFUCK_CYCLES,
    validate_rotation,
)
from esolangs.languages.rotfuck.proof_formulas import execution
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["rotfuck"]

#: The default (backward) cycle: ``+ -> ] -> [ -> . -> , -> < -> > -> - -> +``.
_ROTFUCK_CHAIN = ROTFUCK_CYCLES["backward"]

#: Net-zero pairs, tried in this order.  Every pad is a chain of these, a pair
#: wrapped in its own inverse move or cell step, so a pad is net zero by
#: construction.
_UNITS = ("+-", "-+", "<>", "><")

#: What undoes a pad command.
_INVERSE = {"+": "-", "-": "+", "<": ">", ">": "<"}

#: Bits per digit of the index.  A digit's walk takes ``count**2 / 2`` moves,
#: so wider digits trade shorter walk text for quadratic run time.
_RADIX_BITS = 6

#: A tree of brainfuck: commands, and nested lists for loop bodies.
type _Tree = list[str | _Tree]


def _rotfuck_rot(char: str, steps: int, cycle: str = _ROTFUCK_CHAIN) -> str:
    """Advance ``char`` ``steps`` steps along the ROTfuck rotation cycle."""
    index = cycle.index(char)
    return cycle[(index + steps) % 8]


def _shows(cmd: str, seek: int, rot: int, cycle: str = _ROTFUCK_CHAIN) -> bool:
    """Whether ``cmd``, executing at ``rot``, reads as a bracket at ``seek``.

    A seek reads the whole program at one rotation, so a command that
    executes ``d`` steps after it shows there as ``rot^-d`` of itself.
    """
    return _rotfuck_rot(cmd, seek - rot, cycle) in "[]"


class _UnplaceableError(Exception):
    """Open seeks leave no admissible padding."""


def _parse(text: str) -> _Tree:
    """Return balanced brainfuck ``text`` as a tree of loops."""
    stack: list[_Tree] = [[]]
    for char in text:
        if char == "[":
            stack.append([])
        elif char == "]":
            body = stack.pop()
            stack[-1].append(body)
        else:
            stack[-1].append(char)
    return stack[0]


class _Builder:
    """Emitted source, the rotation it has reached, and the open seeks' phases."""

    def __init__(self, cycle: str = _ROTFUCK_CHAIN) -> None:
        """Start empty, at rotation zero, inside no loop, against ``cycle``."""
        self.src: list[str] = []
        self.rot = 0
        self._seeks: list[int] = []
        self.cycle = cycle

    def _hidden(self, cmd: str, rot: int) -> bool:
        """Whether ``cmd``, executing at ``rot``, shows as no bracket."""
        return not any(_shows(cmd, seek, rot, self.cycle) for seek in self._seeks)

    def _put(self, cmd: str) -> None:
        """Append the character that reads as ``cmd`` at the current rotation."""
        self.src.append(_rotfuck_rot(cmd, -self.rot, self.cycle))
        self.rot = (self.rot + 1) % 8

    def _unit(self, rot: int) -> str | None:
        """The first net-zero pair hidden at ``rot`` and ``rot + 1``, if any."""
        return next(
            (
                unit
                for unit in _UNITS
                if self._hidden(unit[0], rot) and self._hidden(unit[1], rot + 1)
            ),
            None,
        )

    def _wrapped(self, rot: int) -> str | None:
        """A pair at ``rot + 1`` inside a step and its inverse, hidden, if any."""
        inner = self._unit(rot + 1)
        return next(
            (
                step + inner + _INVERSE[step]
                for step in "+-<>"
                if inner
                and self._hidden(step, rot)
                and self._hidden(_INVERSE[step], rot + 3)
            ),
            None,
        )

    def _pad(self, length: int) -> str:
        """Return a hidden net-zero run of ``length`` commands from here.

        A chain of pairs.  A pair no unit fits (a start of one residue per
        two-seek set, see :meth:`_pad_until`) is wrapped: its four commands
        are a step, a pair at the odd alignment, which has no such start, and
        the inverse step; ``length - 4`` when the dead pair is the last one.
        """
        wraps = {
            min(at, length - 4)
            for at in range(0, length, 2)
            if self._unit(self.rot + at) is None
        }
        out = ""
        while len(out) < length:
            at = self.rot + len(out)
            wrap = len(out) in wraps
            piece = self._wrapped(at) if wrap else self._unit(at)
            if piece is None:
                raise _UnplaceableError("no neutral pad is hidden from every open seek")
            out += piece
        return out

    def _pad_until(self, done: Callable[[int], bool]) -> None:
        """Emit the shortest hidden padding after which ``done(rot)`` holds.

        Pads are even, and of every even length except one case: a pair start
        where no unit is hidden (two seeks an odd distance apart, one residue
        of eight) cannot take two, and takes ten for what two would reach.
        """
        lengths = (0, 2, 4, 6) if self._unit(self.rot) else (0, 4, 6, 10)
        length = next((n for n in lengths if done((self.rot + n) % 8)), None)
        if length is None:
            raise _UnplaceableError("no neutral pad reaches the target rotation")
        for char in self._pad(length):
            self._put(char)

    def _command(self, cmd: str) -> None:
        """Emit ``cmd``, padded past rotations at which it shows as a bracket."""
        self._pad_until(lambda rot: self._hidden(cmd, rot))
        self._put(cmd)

    def _loop(self, body: _Tree) -> None:
        """Emit ``[body]`` with both brackets at one phase.

        The new loop's brackets must show to each open seek as a matched pair
        (the same phase) or as nothing (two to six apart); one apart, one of
        them reads as the other bracket.  Two apart is out too: two seeks
        that far apart ban all of ``+-><`` at one rotation, which no pad
        crosses.  Both cycles keep ``[`` and ``]`` adjacent, so this set of
        phases does not depend on the direction.  The body pads to seven
        modulo eight, so its parity has to be odd: a body with an even item
        count opens with a ``[`` that cannot fire, because the cell that
        entered the loop is nonzero and the pads before it preserve that cell.
        """
        self._pad_until(
            lambda rot: all((seek - rot) % 8 in (0, 3, 4, 5) for seek in self._seeks)
        )
        phase = self.rot
        self._put("[")
        self._seeks.append(phase)
        if len(body) % 2 == 0:
            self._command("[")
        self.emit(body)
        self._pad_until(lambda rot: rot == phase)
        self._seeks.pop()
        self._put("]")

    def emit(self, tree: _Tree) -> None:
        """Emit a brainfuck tree: an item is a command or a loop body.

        Each item, pads aside (all even), advances the rotation by one
        modulo two -- a loop by one modulo eight -- which is the parity
        :meth:`_loop` counts.
        """
        for item in tree:
            if isinstance(item, list):
                self._loop(item)
            else:
                self._command(item)

    def text(self) -> str:
        """Return the finished, rotated source."""
        return "".join(self.src)


def _groups(width: int) -> list[int]:
    """Bit counts of the index's base-64 digits, lowest digit first."""
    out = []
    while width > 0:
        out.append(min(_RADIX_BITS, width))
        width -= out[-1]
    return out


def _strides(groups: list[int]) -> list[int]:
    """How far each digit's walk steps, in cells, lowest digit first."""
    out = []
    shift = 0
    for width in groups:
        out.append(2 << shift)
        shift += width
    return out


def _walk(stride: int) -> str:
    """Brainfuck carrying the count under the pointer ``stride`` cells left per unit.

    Each step moves the count to the next carrier down and drops one, so it
    leaves the pointer ``stride * count`` cells lower on a zero carrier.
    """
    left, right = "<" * stride, ">" * stride
    return f"[[-{left}+{right}]{left}-]"


def _skip(distance: int, *, fresh: bool) -> str:
    """Brainfuck moving ``distance`` cells right across zeros, shorter of two.

    Plain ``>`` steps, or a count carried ``isqrt(room / 3)`` cells a step.  The count
    sits on the current cell when it is ``fresh`` (zero), else one cell on, and
    must land on a zero cell before the destination.  A zero upper half
    shrinks the program ([ablations.skip_race]).
    """
    best = ">" * distance
    start = "" if fresh else ">"
    room = distance - 1 if fresh else distance - 2
    # A walk costs 3 * stride + room // stride - room, nearly: minimal near
    # sqrt(room / 3).  The exact scan over strides gained 0.08% (94,060 vs
    # 94,134 chars, 40 random n=7..10 tables), under the 10% bar.
    stride = math.isqrt(max(room, 0) // 3)
    if stride < 2 or room // stride < 2:
        return best
    count = room // stride
    walk = f"[[-{'>' * stride}+{'<' * stride}]{'>' * stride}-]"
    left = distance - len(start) - stride * count
    candidate = start + "+" * count + walk + ">" * left
    return min(best, candidate, key=len)


def _strip(table: str, *, skips: bool) -> str:
    """Brainfuck writing the table's ones two cells apart, ending past the last slot.

    Entry ``e`` sits at cell ``2 * (size - 1 - e)`` with a zero carrier above
    it; the pointer starts on entry 0's carrier.  A run of zero entries is
    crossed by a carried count instead (:func:`_skip`).
    """
    size = len(table)
    out = []
    at = 0  # the cell the pointer stands on
    written = False
    for slot in range(size):
        if table[size - 1 - slot] == "1":
            distance = 2 * slot - at
            out.append(_skip(distance, fresh=not written) if skips else ">" * distance)
            out.append("+")
            at, written = 2 * slot, True
    distance = 2 * size - 1 - at
    out.append(_skip(distance, fresh=not written) if skips else ">" * distance)
    return "".join(out)


def _select(n: int, used: list[int], groups: list[int]) -> str:
    """Brainfuck reading the inputs and walking to the entry they select.

    One digit at a time, highest first, accumulated by Horner's rule on the
    carrier under the pointer with the carrier above as scratch; each
    digit's walk runs before the next is read, so the reads need no pointer
    arithmetic.  An ignored input lands on the entry cell just above, which
    the pointer has passed for good.  The walks step ``2 * index`` cells down
    in total; the caller's one ``<`` reads the entry.
    """
    chosen = set(used)
    digit = "-" * _ASCII_ZERO
    out = []
    cursor = 0
    for width, stride in zip(reversed(groups), reversed(_strides(groups)), strict=True):
        taken = 0
        while taken < width:
            if cursor not in chosen:
                out.append(">,<")
            elif taken == 0:
                out.append("," + digit)
                taken += 1
            else:
                out.append(f"[->>++<<],{digit}>>[-<<+>>]<<")
                taken += 1
            cursor += 1
        out.append(_walk(stride))
    out.append(">,<" * (n - cursor))
    return "".join(out)


def rotfuck(truth_table: str, *, rotation: str = "backward") -> str:
    """Return a ROTfuck program for ``truth_table`` (MSB first) in ``rotation``."""
    return _program(truth_table, rotation=rotation)


def _program(truth_table: str, *, rotation: str = "backward") -> str:
    """Build the rotated lookup, including a one-entry constant table."""
    cycle = ROTFUCK_CYCLES[validate_rotation(rotation)]
    n = _validate_truth_table(truth_table)

    # Ignored inputs are still read but do not enter the index.
    used = essential_inputs(truth_table, n)
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    strips = [_strip(table, skips=False)]
    if (skipped := _strip(table, skips=True)) != strips[0]:
        strips.append(skipped)
    texts = []
    for strip in strips:
        bf = (
            strip + _select(n, used, _groups(len(used))) + "<" + "+" * _ASCII_ZERO + "."
        )
        out = _Builder(cycle)
        out.emit(_parse(bf))
        texts.append(out.text())
    return min(texts, key=len)


def _dialect(rotation: str = "backward") -> None:
    """Validate which way ROTfuck's command cycle turns."""
    validate_rotation(rotation)


LANGUAGE = Language(
    "ROTfuck",
    "rotfuck",
    category="tape_based",
    boolean=rotfuck,
    dialect=_dialect,
    dialect_values={"rotation": ROTATIONS},
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    proof_execution=(execution, True, (3, 5)),
)
