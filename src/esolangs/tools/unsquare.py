"""Boolean program generator for Unsquare."""

from itertools import groupby

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.constant_projection import balanced_projection, projected_inputs
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    read_at,
    subtree_ids,
)
from esolangs.tools.wrap import wrap_chars


def _run(entry: str, count: int) -> str:
    """Push ``count`` copies of ``entry`` (``O``/``I``), by a loop when shorter.

    The accumulator is set to ``2 * (count // 2)`` by Horner's rule (``x``
    doubles, ``+`` adds two); each trip pushes two and subtracts two.
    """
    bits = bin(count // 2)[2:]
    setup = "OA+" + "".join("x" + "+" * (bit == "1") for bit in bits[1:])
    loop = setup + ">" + entry * 2 + "-<" + entry * (count % 2)
    return min(entry * count, loop, key=len)


def _runs(bits: str) -> tuple[str, int]:
    """Return run-counted pushes and their executed command count."""
    parts: list[str] = []
    commands = 0
    for entry, run in groupby(bits):
        count = len(list(run))
        char = "I" if entry == "1" else "O"
        code = _run(char, count)
        parts.append(code)
        commands += (
            count
            if code == char * count
            else code.index(">") + 5 * (count // 2) + count % 2
        )
    return "".join(parts), commands


def _shared_pushes(bits: str, n: int, kept: int) -> str | None:
    """Count two identical aligned halves before lookup overwrites the counter."""
    ids = subtree_ids(bits)
    chosen: tuple[int, int] | None = None
    for depth, layer in enumerate(ids[:-1]):
        span = 1 << (len(ids) - 1 - depth)
        for index, state in enumerate(layer):
            if (
                state >= 2
                and span // 2 > 7
                and ids[depth + 1][2 * index] == ids[depth + 1][2 * index + 1]
            ):
                chosen = index * span, span
                break
        if chosen is not None:
            break
    if chosen is None:
        return None
    start, span = chosen
    before, first_cost = _runs(bits[:start])
    after, last_cost = _runs(bits[start + span :])
    block = bits[start : start + span // 2].translate(str.maketrans("01", "OI"))
    # O/I preserve the accumulator; only the later addressing pops overwrite it.
    cells = before + "OA++>" + block + "-<" + after
    commands = (
        first_cost + last_cost + span + 10 + 79 * kept + 2 * (n - kept) + len(bits) + 26
    )
    return cells if commands <= 4 * (1 << n) + 79 * n + 22 else None


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
    "stack_based.unsquare",
    boolean=unsquare,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    balance=balance_unsquare,
)
