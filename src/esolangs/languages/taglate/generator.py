"""Taglate Boolean generator: select a printable nibble, divide, then take parity.

Size:
    O(T) characters; n=10 random 1847: 4,454 chars, n=10 parity: 4,454
    chars, n=9 random 1847: 2,673 chars. Ignored inputs use a smaller table.
"""

from itertools import pairwise
from math import isqrt

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score, wrap_program
from esolangs.languages.taglate.interpreter import _PREFIX, _SUFFIX, percent_encode
from esolangs.languages.taglate.proof_formulas import execution, workspace
from esolangs.languages.taglate.wrapping import _taglate, same_layout
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _half_select(pairs: int, ahead: int, n: int) -> str:
    """Branch on the front input, skip the kept half, drop the rejected one."""
    return (
        "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (n + 2)
        + "gz"
    )


def _even_reduce(pairs: int, retired: int, cells: int) -> str:
    """Reduce block: select half the value slots, keep every input cell.

    The queue holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then
    two nonzero sentinels, then ``cells`` data cells; ``retired`` precede
    the next input.  The rotation brings the next input to the front; ``gy ... gz``
    branches on it so the ``e^pairs`` strides past the half of the value
    slots the input rejects; ``e^ahead`` skips the untouched half and
    ``f^pairs`` drops it.  The stride lands on a 0 slot only if ``ahead``
    is even.
    """
    return "e" * (2 * pairs + 2 + retired) + _half_select(pairs, cells - retired, cells)


def _with_discards(reduced: str, used: list[int], n: int) -> str:
    """Re-expand the program for ``used`` inputs to read all ``n``.

    Each ignored input is read with ``h``, rotated to the front with ``e``
    once per queued cell, and dropped with ``f``, leaving the queue as the
    reduced program expects.  The count is the queue length at that point
    (seed plus the reads so far), computed, not searched.
    """
    seed, commands = reduced.split("\n", 1)
    discard = "h" + "e" * len(seed) + "f"
    reads = commands.split("h")
    parts = [reads[0] + "h"]
    for read, (before, after) in enumerate(pairwise(used), start=1):
        between = "h" + "e" * (len(seed) + read) + "f"
        parts.append(between * (after - before - 1))
        parts.append(reads[read] + "h")
    # Trailing ignored inputs queue behind everything, so they are read just
    # before the closing print, which takes the front.
    parts.append(reads[-1][:-1] + "h" * (n - used[-1] - 1) + reads[-1][-1])
    return seed + "\n" + discard * used[0] + "".join(parts)


def _affine(truth_table: str) -> str:
    """One input: ``base + bit * coeff`` by ``b``/``c``/``a`` queue arithmetic.

    The general layout needs two inputs, so n == 1 cannot share it.
    """
    base = _ASCII_ZERO + int(truth_table[0])
    coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
    seed = "0" + chr(coeff) + chr(base)
    return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"


def _full_layout(truth_table: str, n: int) -> str:
    """Select a printable four-bit leaf, then divide by its two input factors."""
    leaves = 1 << (n - 2)
    packed = [
        sum(int(bit) << offset for offset, bit in enumerate(truth_table[i : i + 4]))
        for i in range(0, len(truth_table), 4)
    ]
    # Powers of two never land on another input in a six-cell group.
    # A two-cell group fails at 00000001, row 6: the stride hits the next 1.
    ghosts = "0" + "\0" * 5
    seed = ghosts * (n - 1) + "0\1\1" + "\0" + "0\0"
    seed += "".join("\0" + chr(32 + value) for value in reversed(packed))
    seed += " 0\1\3"
    # The first n-2 bits keep the trailing/leading half for 0/1, hence
    # reversed leaves; within each nibble the last two bits index low-first.
    prefix = "heeeeee" * n + "e" * (2 * leaves + 4) + "beeeee" * n
    reductions = "".join(
        _even_reduce(leaves >> level, 2 + 6 * level, 6 * n + 2)
        for level in range(n - 2)
    )
    # Keep [x,32,1,3,A,B,1,1,0,48]; discard retired bits and ghosts.
    prune = "feefee" + "f" * (6 * n - 12) + "efffff" + "eeeeef"
    # x-=32; D_A=1+3A; x/=D_A; D_B=1+B; x/=D_B.
    divide = "b" + "ec" + "e" * 6 + "a" + "e" * 5 + "dc" + "e" * 4 + "aeedee"
    # [q,0,48]: decrement q, toggle the accumulator, rotate 48. q<=15.
    parity = "gyjjegzfai"
    return seed + "\n" + prefix + reductions + prune + divide + parity


def _taglate_raw(truth_table: str) -> str:
    """Build a Taglate program computing the given truth table.

    A table that ignores some inputs is emitted as the smaller table over
    the inputs it uses, with the ignored ones read and discarded. Constants
    use one seed character, n reads and a print.
    """
    n = _validate_truth_table(truth_table)

    if len(set(truth_table)) == 1:
        return truth_table[0] + "\n" + "h" * n + "i"
    used = essential_inputs(truth_table, n)
    if 0 < len(used) < n:
        reduced = _taglate_raw(read_at(truth_table, used, n))
        return _with_discards(reduced, used, n)
    if n == 1:
        return _affine(truth_table)
    return _full_layout(truth_table, n)


def _seed_commands(seed: str) -> str:
    """Build a generator seed from the empty queue with bounded ASCII passes."""
    targets = list(map(ord, seed))
    subtract = len(targets) == 3 and targets[1] == 65535
    if subtract:
        targets[1:2] = [0, 1]
    count = len(targets)
    prefixes: list[str] = []
    suffixes: list[str] = []

    prefix, suffix = _PREFIX, _SUFFIX
    enough = 0
    while enough < count:
        prefixes.append(prefix)
        suffixes.append(suffix)
        enough += sum(ord(c) >= 49 for c in prefix + suffix)
        prefix, suffix = percent_encode(prefix), percent_encode(suffix)
    # Encoding distributes over concatenation; nested URLs are these layers.
    values = list(map(ord, "".join(prefixes + suffixes[::-1])))
    parts: list[str] = ["t" * len(prefixes)]
    selected: list[int] = []
    for value in values:
        keep = value >= 49 and len(selected) < count
        parts.append("e" if keep else "f")
        if keep:
            selected.append(value)
    # Each j/e rotates once, so a complete pass restores FIFO order.
    # URL output is ASCII: at most 126 passes reach generator constants.
    for _ in range(
        max(v - target for v, target in zip(selected, targets, strict=True))
    ):
        for index, target in enumerate(targets):
            decrement = selected[index] > target
            parts.append("j" if decrement else "e")
            selected[index] -= decrement
    if subtract:
        parts.append("ebe")  # [48, 0, 1, base] -> [48, 65535, base].
    return "".join(parts)


def _bootstrapped(program: str) -> str:
    """Return ``program`` with its literal seed rebuilt from the empty queue."""
    seed, _, commands = program.partition("\n")
    return "\n" + _seed_commands(seed) + commands


def taglate(truth_table: str, width: int | None = None) -> str:
    """Return Taglate code; narrow seeds bootstrap an empty queue."""
    program = _taglate_raw(truth_table)
    if width is None:
        return program
    if len(program.partition("\n")[0]) > width:
        program = _bootstrapped(program)
    return wrap_program(program, "taglate", width)


def balance_taglate(_table: str, default: str) -> str:
    """Compare literal and bootstrapped folds of one queue construction."""
    seed, _, commands = default.partition("\n")
    candidates = [default]
    bootstrapped = _bootstrapped(default)
    regimes = [
        (default, len(seed), max(len(seed), len(commands))),
        (bootstrapped, 1, len(seed) - 1),
    ]
    for program, lower, upper in regimes:
        length = len(program.partition("\n")[2])
        # The seed adds one row: W=w, H=1+ceil(length/w); the floor of
        # w*w-A*w=A*length (A=CELL_ASPECT).  Its upper neighbour as a second
        # candidate saved under 1% (seed 4242, n=1..10).
        crossing = (CELL_ASPECT + isqrt(CELL_ASPECT**2 + 4 * CELL_ASPECT * length)) // 2
        candidates.append(
            wrap_program(program, "taglate", min(upper, max(lower, crossing)))
        )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Taglate",
    "taglate",
    proof_execution=(execution, True, (3, 4, 5)),
    proof_workspace=(workspace, True, (3, 4, 5)),
    category="queue_based",
    boolean=taglate,
    split=True,
    contract=BooleanContract(input_shape="char_stream"),
    # Both concatenate before tokenizing (Taglate after the queue seed; A
    # Painter Ant drops whitespace), so no break can land inside a command.
    wrap=_taglate,
    wrap_multiline=True,
    same_layout=same_layout,
    balance=balance_taglate,
)
