"""Ascenic Boolean program generator: a threshold scan over the row number.

Arguments must rise line by line, so a constant is never reused: ``-2`` is
built fresh each time as ``PUSH a``, ``PUSH a+2``, ``SUBS``.  Horner's rule
with ``MULS`` by ``-2`` and alternating ``ADDS``/``SUBS`` of each read bit
leaves ``2r`` for row ``r``, and ``ADD`` shifts it to ``x = base + 2r``,
``base`` above every argument so far and of the last row's parity.  Each
row ``k`` whose answer differs from row ``k+1``'s gets ``LT base+2k+1``,
``ADDS``: it adds 1 to every ``x`` below it, and the codes' spacing of 2
keeps those increments below the next threshold.  So ``x``'s parity is the
last row's answer flipped once per change after the row, its answer;
``MUL a``, ``MOD 2a``, ``ADD 2a+1``, ``DIV 2a+2`` turn it into 0 or 1 for
``PRINT``.  The program never jumps: every line runs once.

Size:
    Two lines per change point, whose arguments climb to about 2T; a
    straight line's arguments sum to at least half its line count squared,
    so O(T^2) characters; at most 6n+2R+6 steps for R change points; n=10
    parity: 1,545,756 chars, n=10 random 1847: 1,176,242 chars.

Decisions:
    An input the table ignores is read and popped, outside the Horner code
    ([ablations.ignored_input_drop]).

    The shorter of the table and its reversal is built (the reversal's rows
    read ``T - 1 - r`` by flipped Horner signs and a first-line ``SUB 2``):
    the scale lines' arguments follow the last change point, so and at n=8
    8,399 -> 2,965 chars ([ablations.mirror_scan]).

    A decision tree with ``JMPF`` cannot share: a jump's target is its line
    plus its argument, both rising, so no two jumps land on one line.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.languages.ascenic.proof_formulas import workspace
from esolangs.registry._language import Language

_PRINT, _INPUT, _PUSH, _ADD, _SUB, _MUL, _DIV, _MOD = 1, 2, 3, 4, 5, 6, 7, 8
_POP = 10
_LT, _ADDS, _SUBS, _MULS = 13, 16, 17, 18


class _Lines:
    """Lines under construction, each argument above the last."""

    def __init__(self) -> None:
        self.lines: list[tuple[int, int]] = []

    @property
    def free(self) -> int:
        """The smallest argument the next line may take."""
        return self.lines[-1][1] + 1 if self.lines else 1

    def add(self, opcode: int, arg: int | None = None, *, odd: bool = False) -> None:
        """Append a line; ``arg`` defaults to the next free value."""
        if arg is None:
            arg = self.free + (odd and self.free % 2 == 0)
        assert arg >= self.free, (opcode, arg)
        self.lines.append((opcode, arg))

    def negative_two(self) -> None:
        """Push -2: the second-pushed constant minus itself plus 2."""
        start = self.free
        self.add(_PUSH, start)
        self.add(_PUSH, start + 2)
        self.add(_SUBS)

    def text(self) -> str:
        return "\n".join("A" * op + "s" * arg for op, arg in self.lines)


def _scan(table: str, n: int, used: list[int], *, mirror: bool) -> str:
    """Return the scan program for ``table``, its rows read forwards or mirrored.

    Mirrored, the Horner signs flip so ``x_n = r + e`` and a first-line
    ``+-2`` (weight ``(-2)**n`` after the last ``MULS``) adds ``2T``: the
    rows come out as ``T - 1 - r``, so ``table`` must be the reversed one.
    ``table`` is over the inputs ``used``; the rest are read and popped.
    """
    out = _Lines()
    m = len(used)
    # x_i = -2 x_(i-1) +- b_i, signed so that x_m is -r and -2 x_m is 2r.
    i = 0
    for pos in range(n):
        if pos not in used:
            out.add(_INPUT, odd=True)
            out.add(_POP)
            continue
        i += 1
        if i > 1:
            out.negative_two()
            out.add(_MULS)
        out.add(_INPUT, odd=True)
        if mirror:
            if i == 1:
                out.add(_SUB, 2)
            if (m - i) % 2 == 1:
                out.add(_SUBS)  # a first bit subtracts from the empty stack's 0
            elif i > 1:
                out.add(_ADDS)
        elif (m - i) % 2 == 0:
            out.add(_SUBS)  # the first bit subtracts from the empty stack's 0
        elif i > 1:
            out.add(_ADDS)
    out.negative_two()
    out.add(_MULS)
    # Mirrored, the first-line 2T stands in for all but ``base - 2`` of the shift.
    base = out.free + (out.free % 2 != int(table[-1])) + 2 * mirror
    out.add(_ADD, base - 2 * mirror)
    for k in range(len(table) - 1):
        if table[k] != table[k + 1]:
            out.add(_LT, base + 2 * k + 1)
            out.add(_ADDS)
    scale = out.free
    out.add(_MUL, scale)
    out.add(_MOD, 2 * scale)
    out.add(_ADD, 2 * scale + 1)
    out.add(_DIV, 2 * scale + 2)
    out.add(_PRINT, odd=True)
    return out.text()


def ascenic(truth_table: str) -> str:
    """Build an Ascenic program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n)
    table = read_at(truth_table, used, n)
    forward = _scan(table, n, used, mirror=False)
    # The mirror's ``SUB 2`` needs the first line's argument budget.
    if not used or used[0] != 0:
        return forward
    # Threshold arguments climb with the last change point: a table whose
    # changes sit at the end is cheaper read from the other end.
    mirrored = _scan(table[::-1], n, used, mirror=True)
    return min(forward, mirrored, key=len)


LANGUAGE = Language(
    "Ascenic",
    "ascenic",
    category="stack_based",
    boolean=ascenic,
    random=True,
    no_wrap="a line's length is its opcode and argument",
    proof_workspace=(workspace, True, (3, 4, 5, 6, 7)),
)
