"""Boolean program generator for Unsquare."""

from itertools import groupby

from esolangs.generation.constant_projection import (
    balanced_projection,
    projected_inputs,
)
from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    read_at,
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

    Reversed ``O``/``I`` entries put row ``r`` at depth ``r``; each read pops
    its bit's weight: two bytes per row, against 32.5 for a decision tree.
    ``>-<`` subtracts 2 to reach the input character's parity; ``x`` doubles
    it, ``>`` pops only for 1, ``OA`` zeroes it for the returning ``<``.
    Index ``2**m - 1`` against ``2**m`` cells prevents underflow.  A run of
    equal cells is pushed by a loop when shorter, so a constant half costs
    about log of its length (:func:`_run`; -15% at n=7, -10% at n=6, 12 seeded
    tables). Two identical aligned halves share one counted push body before
    lookup overwrites the accumulator, when shorter within the command bound.
    """
    return _program(truth_table, share=True)


def _program(
    truth_table: str, *, share: bool, keep_constant_input: bool = False
) -> str:
    """Return the lookup, optionally sharing its push initializer."""
    n = _validate_truth_table(truth_table)
    used = projected_inputs(truth_table, n, keep_constant_input=keep_constant_input)
    reduced = read_at(truth_table, used, n)
    bits = reduced[::-1]
    cells, _ = _runs(bits)
    shared = _shared_pushes(bits, n, len(used)) if share and len(bits) > 1 else None
    if shared is not None and len(shared) < len(cells):
        cells = shared
    blocks: list[str] = []
    for index in range(n):
        if index in used:
            weight = 1 << (len(used) - 1 - used.index(index))
            blocks.append("iA>-<x>" + "A" * weight + "OA<")
        else:
            blocks.append("iA")  # consume the line, leave the stack alone
    return cells + "".join(blocks) + "A" + "+" * (_ASCII_ZERO // 2) + "Po"


def balance_unsquare(truth_table: str, default: str) -> str:
    """Retain the unshared initializer when its wrapped shape is better."""
    return balanced_projection(
        default,
        _program(truth_table, share=False, keep_constant_input=True),
        "unsquare",
    )


LANGUAGE = Language(
    "Unsquare",
    "unsquare",
    category="stack_based",
    boolean=unsquare,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    balance=balance_unsquare,
)
