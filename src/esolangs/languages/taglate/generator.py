"""Taglate Boolean program generator: fixed queue slots halved by strided reduces.

Rows are fixed queue slots the strided reduces walk, two characters for a 0 or
a 1, so a constant half or repeat has nothing to fold or share.

Size:
    O(T) slots, independent of the table's values; n=10 random 1847: 21,025
    chars, n=10 parity: 21,025 chars, n=9 random 1847: 10,760 chars.  A table
    ignoring inputs is built over its essential inputs only.
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


def _reorder_tt(tt: str, n: int) -> str:
    """Reorder truth table entries into the slot order the reduces expect.

    Each entry sits in a value slot ``[0, s_i, 0, s_j, ...]``; an even
    reduce must be able to drop an entire contiguous run of slots without
    splitting a pair.  Sorting the input index ``i`` by ``(-(i >> 1),
    i & 1)`` puts the 1-group of the current input first, then the 0-group,
    with the two sub-cases of the next input adjacent inside each group.
    Odd-reduce levels (which branch the other way) then re-apply the same
    ordering, so the sort key serves both.  That key is the pairs in
    reverse, each pair in place, written out directly: O(2**n), no sort.
    """
    return "".join(tt[i : i + 2] for i in range(2**n - 2, -1, -2))


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


def _even_reduce(pairs: int, level: int, n: int) -> str:
    """Even-reduction block: select half the value pairs, keep all inputs.

    The queue holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then
    two 48s, then the ``n`` input cells.  The ``rot`` rotation brings the
    next input to the front; ``gy ... gz`` branches on it so the ``e^pairs``
    strides past the half of the value slots the input rejects; ``e^ahead``
    skips the untouched half and ``f^pairs`` drops it.  Every input stays on
    the queue, so the level that follows still sees all ``n`` of them.
    """
    return "e" * (2 * pairs + 2 + level) + _half_select(pairs, n - level, n)


# Final odd-reduce block: the committed n==2 pattern.  Given the 8-cell
# queue [0, v0, 0, v1, 48, 48, prev, curr] (v0/v1 the two candidate values,
# prev/curr the two remaining inputs), it rotates curr and prev to the front,
# drops the candidate the inputs reject, adds the surviving value to one of
# the two 48s (48 + bit), and prints it with ``i``.
_SEL1_N2: str = (
    "e" * 7
    + "gy"
    + "e" * 3
    + "gz"
    + "e" * 3
    + "gy"
    + "e" * 3
    + "gz"
    + "ff"
    + "gy"
    + "e" * 4
    + "gz"
    + "e"
    + "a"
    + "e" * 4
    + "i"
)


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    """Odd-reduction block: retire one input, reduce, keep the rest.

    ``level`` is the 0-based reduce level (odd here: 1, 3, ...).  The queue
    holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then two 48s,
    then the ``n`` input cells.  Unlike the even reduce, the odd level
    branches on a *retired* (previous) input whose bit has already been
    used, so ``e^rot`` brings that input to the front and the block runs
    ``zero`` (``gy j e^(qlen-1) gz``) to fold it away, ``swap`` (``e gy j
    e^(qlen-2) j gz``) to encode the current input as the ghost cell the
    even-reduce branches on, and ``bring`` (``e^(qlen-1)``) to put the
    value slots back at the front before ``er`` runs the even-reduce body.

    The ZS adds an extra ghost cell at the front, so the even-reduce body
    uses ``ahead = n - level + 1`` instead of ``n - level``.  No input is
    popped; the final ``f^pairs`` in ``er`` drops only the rejected value
    slots.
    """
    qlen = 2 * pairs + 2 + n
    rot = 2 * pairs + 1 + level
    zero = "gy" + "j" + "e" * (qlen - 1) + "gz"
    swap = "e" + "gy" + "j" + "e" * (qlen - 2) + "j" + "gz"
    bring = "e" * (qlen - 1)
    er = _half_select(pairs, n - level + 1, n)  # +1: the swap's ghost cell
    return "e" * rot + zero + swap + bring + er


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
    parts.append(reads[-1])
    leading = used[0]
    trailing = n - used[-1] - 1
    return seed + "\n" + discard * leading + "".join(parts) + "h" * trailing


def _affine(truth_table: str) -> str:
    """One input: ``base + bit * coeff`` by ``b``/``c``/``a`` queue arithmetic.

    The general layout needs two inputs, so n == 1 cannot share it.
    """
    base = _ASCII_ZERO + int(truth_table[0])
    coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
    seed = "0" + chr(coeff) + chr(base)
    return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"


def _full_layout(truth_table: str, n: int) -> str:
    """Program for a table that uses every input, ``n >= 2``.

    The seed holds ``n - 1`` literal ``'1'``s around a run of ``'0'``s and
    one trailing ``'1'``.  ``h``/``e``/``b``/``d``/``j`` read the ``n``
    inputs and interleave the reordered table into value slots
    ``[0, s0, 0, s1, ...]``, then two 48s and the inputs.  Alternating
    even/odd reduce blocks halve the slots without popping inputs;
    ``e^6 f^(n - 2) e^2`` reshapes the queue into the 8-cell layout
    ``_SEL1_N2`` selects on.  The strided reduces need an even number ``m``
    of input cells ahead of the value slots, so odd ``n`` carries one extra
    ``'1'`` cell after the last input: a spare cell, not a ghost input, so
    the table stays ``2**n`` entries.
    """
    spare = n % 2
    cells = n + spare

    seed = "1" * (n - 1 + spare) + "0" * (2 ** (n + 2) + 2) + "1"

    ordered = _reorder_tt(truth_table, n)
    selectors = "".join("bd" if c == "1" else "bb" for c in ordered)

    # The spare cell is the seed's last leading '1' (rotated behind the
    # inputs by the extra ``e``); ``b`` pairs skip it, and the last ``e``
    # puts it behind the inputs again after ``j`` has run.
    prefix = (
        "he" * (n - 1)
        + "h"
        + "e" * spare
        + selectors
        + "ee"
        + "b" * n
        + "e" * (2 ** (n + 1) + 2 + spare)
        + "j" * n
        + "e" * spare
    )

    select_parts: list[str] = []
    for level in range(n - 1):
        pairs = 2 ** (n - level)
        reduce = _even_reduce if level % 2 == 0 else _odd_reduce
        select_parts.append(reduce(pairs, level, cells))

    if n > 2:
        select_parts.append("e" * 6 + "f" * (n - 2) + "e" * 2 + "f" * spare)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result


def _taglate_raw(truth_table: str) -> str:
    """Build a Taglate program computing the given truth table.

    A table that ignores some inputs is emitted as the smaller table over
    the inputs it uses, with the ignored ones read and discarded: a constant
    table goes from 451 characters (n=4) to 7, ``11110000`` from 278 to 16.
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
        # The seed adds one row: W=w, H=1+ceil(length/w). Widths on
        # either side of w*w-A*w=A*length (A=CELL_ASPECT) bracket the
        # smallest side.
        crossing = (CELL_ASPECT + isqrt(CELL_ASPECT**2 + 4 * CELL_ASPECT * length)) // 2
        for width in (crossing, crossing + 1):
            candidates.append(
                wrap_program(program, "taglate", min(upper, max(lower, width)))
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
