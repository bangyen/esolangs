"""Unsquare Boolean program generator: a stack lookup popped by input weight.

Entries are pushed reversed as ``O``/``I`` so row ``r`` sits at depth ``r``;
each input read pops its bit's weight, leaving the addressed entry on top.
Runs of equal cells use a counted loop when shorter, and two identical
aligned halves share one counted push body before lookup overwrites the
accumulator, when shorter within the command bound.

Size:
    Two bytes per row, O(T), against 32.5 for a decision tree; n=10 and:
    1,176 chars, n=10 random 1847: 2,173 chars.

Decisions:
    Run loops: no saving on seeded random tables at n=6/7 (runs fall short
    of the ~9-entry break-even); the saving lives on run-rich tables
    ([ablations.run_loops]).
"""

from itertools import groupby

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
    subtree_ids,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _run(entry: str, count: int) -> tuple[str, int]:
    """Push ``count`` copies of ``entry`` (``O``/``I``), by a loop when shorter.

    Returns the code and its executed command count.  The accumulator is set
    to ``2 * (count // 2)`` by Horner's rule (``x`` doubles, ``+`` adds two);
    each trip runs ``>``, pushes two, subtracts two and runs ``<``.
    """
    bits = bin(count // 2)[2:]
    setup = "OA+" + "".join("x" + "+" * (bit == "1") for bit in bits[1:])
    loop = setup + ">" + entry * 2 + "-<" + entry * (count % 2)
    if count <= len(loop):
        return entry * count, count
    return loop, len(setup) + 5 * (count // 2) + count % 2


def _runs(bits: str) -> tuple[str, int]:
    """Return run-counted pushes and their executed command count."""
    parts: list[str] = []
    commands = 0
    for entry, run in groupby(bits):
        count = len(list(run))
        code, executed = _run("I" if entry == "1" else "O", count)
        parts.append(code)
        commands += executed
    return "".join(parts), commands


def _twin_halves(bits: str) -> tuple[int, int] | None:
    """Return ``(start, span)`` of the first aligned block of two identical halves.

    Blocks need halves over 7 entries long; shallowest, then leftmost, first.
    """
    ids = subtree_ids(bits)
    for depth, layer in enumerate(ids[:-1]):
        span = 1 << (len(ids) - 1 - depth)
        if span // 2 <= 7:
            continue
        for index, state in enumerate(layer):
            if (
                state >= 2
                and ids[depth + 1][2 * index] == ids[depth + 1][2 * index + 1]
            ):
                return index * span, span
    return None


def _command_bound(n: int) -> int:
    """Commands the shared form may execute: one pass of the plain lookup cost."""
    return 4 * (1 << n) + 79 * n + 22


def _lookup_cost(n: int, kept: int, size: int) -> int:
    """Commands of the lookup, over a ``size``-entry table, outside the pushes."""
    return 79 * kept + 2 * (n - kept) + size + 26


def _shared_pushes(bits: str, n: int, kept: int) -> str | None:
    """Count two identical aligned halves before lookup overwrites the counter."""
    chosen = _twin_halves(bits)
    if chosen is None:
        return None
    start, span = chosen
    before, first_cost = _runs(bits[:start])
    after, last_cost = _runs(bits[start + span :])
    block = bits[start : start + span // 2].translate(str.maketrans("01", "OI"))
    # O/I preserve the accumulator; only the later addressing pops overwrite it.
    cells = before + "OA++>" + block + "-<" + after
    commands = first_cost + last_cost + span + 10 + _lookup_cost(n, kept, len(bits))
    return cells if commands <= _command_bound(n) else None


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program for a binary ``2**n``-entry table, MSB first.

    Index ``2**m - 1`` against ``2**m`` cells prevents underflow.  A constant
    half costs about log of its length (:func:`_run`).
    """
    n = _validate_truth_table(truth_table)
    weights, reduced = input_weights(truth_table, n)
    bits = reduced[::-1]
    cells, _ = _runs(bits)
    kept = n - weights.count(0)
    shared = _shared_pushes(bits, n, kept) if len(bits) > 1 else None
    if shared is not None and len(shared) < len(cells):
        cells = shared
    blocks: list[str] = []
    for weight in weights:
        if weight:
            # ``>-<`` subtracts 2 to reach the input character's parity; ``x``
            # doubles it, ``>`` pops only for 1, ``OA`` zeroes it for the ``<``.
            blocks.append("iA>-<x>" + "A" * weight + "OA<")
        else:
            blocks.append("iA")  # consume the line, leave the stack alone
    return cells + "".join(blocks) + "A" + "+" * (_ASCII_ZERO // 2) + "Po"


LANGUAGE = Language(
    "Unsquare",
    "unsquare",
    category="stack_based",
    boolean=unsquare,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
