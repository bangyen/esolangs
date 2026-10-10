"""Boolean-function generator for ROTfuck, at the default ``rotation="backward"``.

ROTfuck turns every command one step around its cycle after each executed
command, so what a character *means* depends on how many commands have run.
The generator writes a brainfuck program and :class:`_Builder` spells each
command backwards by the rotation it will execute at.

Loops are where that bites.  A bracket seeks its partner before rotating, so
a loop is sound when its ``[`` and ``]`` execute at the same rotation modulo
eight -- the *phase* -- and nothing between them reads as a bracket there.
Then every trip leaves the rotation where it found it, and a skip, an exit
and a jump back all resume one past the phase.  So a body is padded to
seven modulo eight with runs that change nothing (:data:`_PADS`), and every
command in it is placed at a rotation that hides it from each open seek.
"""

import heapq
from collections.abc import Callable
from itertools import product

from esolangs.interpreters.tape_based.rotfuck._dialect import (
    ROTATIONS,
    ROTFUCK_CYCLES,
)
from esolangs.interpreters.tape_based.rotfuck._dialect import (
    rotation as validate_rotation,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.constant_projection import balanced_projection, projected_inputs
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    read_at,
)
from esolangs.tools.wrap import wrap_chars

__all__ = ["rotfuck"]

#: The default direction's cycle: ``+ -> ] -> [ -> . -> , -> < -> > -> - -> +``.
_ROTFUCK_CHAIN = ROTFUCK_CYCLES["backward"]

# Pads are even-length; an 8-run is a full-cycle rotation no-op, so 6 is the cap.
_MAX_PAD = 6

#: Bits per digit of the index.  A digit's walk takes ``count**2 / 2`` moves,
#: so wider digits trade shorter walk text for quadratic run time.
_RADIX_BITS = 6

#: A tree of brainfuck: commands, and nested lists for loop bodies.
type _Tree = list[str | _Tree]


def _rotfuck_rot(char: str, steps: int) -> str:
    """Advance ``char`` ``steps`` steps along the ROTfuck rotation cycle."""
    index = _ROTFUCK_CHAIN.index(char)
    return _ROTFUCK_CHAIN[(index + steps) % 8]


def _shows(cmd: str, seek: int, rot: int) -> bool:
    """Whether ``cmd``, executing at ``rot``, reads as a bracket at ``seek``.

    A seek reads the whole program at one rotation, so a command that
    executes ``d`` steps after it shows there as ``rot^-d`` of itself.
    """
    return _rotfuck_rot(cmd, seek - rot) in "[]"


def _pads() -> tuple[str, ...]:
    """Command runs that change neither the tape nor the pointer.

    Shortest first, since padding is pure cost.  A run may step left of
    cell zero: the tape grows a zero cell there, and the program is relative.
    """
    out = []
    for length in range(2, _MAX_PAD + 1, 2):
        for run in product("+-><", repeat=length):
            cells: dict[int, int] = {}
            at = 0
            for char in run:
                at += (char == ">") - (char == "<")
                cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
            if at == 0 and not any(cells.values()):
                out.append("".join(run))
    return tuple(out)


_PADS = _pads()


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

    def __init__(self) -> None:
        """Start empty, at rotation zero, inside no loop."""
        self.src: list[str] = []
        self.rot = 0
        self._seeks: list[int] = []

    def _hidden(self, cmd: str, rot: int) -> bool:
        """Whether ``cmd``, executing at ``rot``, shows as no bracket."""
        return not any(_shows(cmd, seek, rot) for seek in self._seeks)

    def _put(self, cmd: str) -> None:
        """Append the character that reads as ``cmd`` at the current rotation."""
        self.src.append(_rotfuck_rot(cmd, -self.rot))
        self.rot = (self.rot + 1) % 8

    def _pad_until(self, done: Callable[[int], bool]) -> None:
        """Emit the shortest hidden padding after which ``done(rot)`` holds.

        Eight residues and a fixed pad list: Dijkstra on pad length.
        """
        queue = [(0, self.rot, "")]
        seen: set[int] = set()
        while queue:
            cost, rot, path = heapq.heappop(queue)
            if done(rot):
                for char in path:
                    self._put(char)
                return
            if rot in seen:
                continue
            seen.add(rot)
            for run in _PADS:
                if all(self._hidden(c, rot + i) for i, c in enumerate(run)):
                    heapq.heappush(
                        queue, (cost + len(run), (rot + len(run)) % 8, path + run)
                    )
        raise _UnplaceableError(  # pragma: no cover - a pad always fits
            "no neutral pad is hidden from every open seek"
        )

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
        crosses.  The body pads to seven modulo eight, so its parity has to
        be odd: a body with an even item count opens with a ``[`` that
        cannot fire, because the cell that entered the loop is nonzero and
        the pads before it preserve that cell.
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
    """Brainfuck moving ``distance`` cells right across zeros, shortest of two.

    Plain ``>`` steps, or a count carried ``stride`` cells a step.  The count
    sits on the current cell when it is ``fresh`` (zero), else one cell on, and
    must land on a zero cell before the destination.
    """
    best = ">" * distance
    start = "" if fresh else ">"
    room = distance - 1 if fresh else distance - 2
    for stride in range(2, room + 1):
        count = room // stride
        if count < 2:
            break
        walk = f"[[-{'>' * stride}+{'<' * stride}]{'>' * stride}-]"
        left = distance - len(start) - stride * count
        candidate = start + "+" * count + walk + ">" * left
        if len(candidate) < len(best):
            best = candidate
    return best


def _strip(table: str, *, skips: bool) -> str:
    """Brainfuck writing the table's ones two cells apart, ending past the last slot."""
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
    the pointer has passed for good.
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
    """Build a ROTfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  Only
    the default ``rotation`` is targeted.

    A tape lookup: entry ``e`` sits at cell ``2 * (size - 1 - e)``, each
    with a zero carrier above it, and the pointer starts on entry 0's
    carrier.  The digits' walks step ``2 * index`` cells down in total, and
    one ``<`` reads the entry.  The table costs two ``>`` and half a ``+``
    per entry; the rest is O(n) plus the walks' strides.  A run of zero entries
    is crossed by a carried count instead (:func:`_skip`; zero upper half
    -3%/-7.5%/-14% at n=7/8/9, 12 seeded tables).  A repeated block is not
    shared: a brainfuck copy is at least 19 commands a cell against 2.5 for
    an entry.
    """
    return _program(truth_table, rotation=rotation)


def _program(
    truth_table: str, *, rotation: str = "backward", keep_constant_input: bool = False
) -> str:
    """Build the rotated lookup, including a one-entry constant table."""
    if validate_rotation(rotation) != "backward":
        raise ValueError("the ROTfuck generator targets rotation='backward' only")
    n = _validate_truth_table(truth_table)

    # Ignored inputs are still read but do not enter the index.
    used = projected_inputs(truth_table, n, keep_constant_input=keep_constant_input)
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    strips = [_strip(table, skips=False)]
    if (skipped := _strip(table, skips=True)) != strips[0]:
        strips.append(skipped)
    texts = []
    for strip in strips:
        bf = (
            strip + _select(n, used, _groups(len(used))) + "<" + "+" * _ASCII_ZERO + "."
        )
        out = _Builder()
        out.emit(_parse(bf))
        texts.append(out.text())
    return min(texts, key=len)


def balance_rotfuck(
    truth_table: str, default: str, *, rotation: str = "backward"
) -> str:
    """Retain the legacy constant layout when it balances better."""
    return balanced_projection(
        default,
        _program(truth_table, rotation=rotation, keep_constant_input=True),
        "rotfuck",
    )


def _dialect(rotation: str = "backward") -> None:
    """Validate which way ROTfuck's command cycle turns."""
    validate_rotation(rotation)


LANGUAGE = Language(
    "ROTfuck",
    "tape_based.rotfuck",
    boolean=rotfuck,
    dialect=_dialect,
    dialect_values={"rotation": ROTATIONS},
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    balance=balance_rotfuck,
)
