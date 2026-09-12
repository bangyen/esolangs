r"""Boolean-function generator for SLOW ACV MAMMALIAN."""

from collections.abc import Sequence

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["slow_acv_mammalian"]

# The byte a stash chunk.
# what puts a distant token.
# the most reach per token by.
_STASH_BYTE = 255

# The read node's second seed.
# and XORing bits 4-5 from.
# lands the accumulator on the.
_J2 = 16

# The least a trampoline can.
# ``LEAPFROG`` to fire, and the.
# ``landing + 15`` exactly, so.
# the landing even when the.
# dead code, reached by nothing.
_MIN_HOP = 16

# ``DIGEST PRONOUNCE EXCRETE.
# with, on top of at most 255.
_LEAF_TAIL = 4

# Slack :func:`_widths` adds.
# and ``b`` solves are exact.
# for ``u``) are hard, so this.
# tokens somewhere -- the.
# out.
# 22 tokens spare.
_SLOT_MARGIN = 8

# What a read node can cost.
# worst ``j1`` of 49 (the aim.
# even with bits 4-5 ``01``),.
_NODE_MAX = 255 + 49 + _J2 + 7

# How far past its threshold a.
# landing by at most 510 (a.
# threshold moves by at most.
# rebound of 255, a ``j1``.
# step never opens more than.
_PAD_MAX = 1072

# : A machine state as the.
type _State = tuple[list[int], int]


def _seeded(array: Sequence[int], count: int) -> list[int]:
    r"""``array`` after ``count`` ``SEED``s, which only move the head."""
    out = list(array)
    out[0] = (out[0] + count) % 256
    return out


def _stash_chunk(array: list[int], acc: int) -> tuple[list[str], list[int], int]:
    r"""``SEED*k DIGEST EXCRETE``, appending exactly ``_STASH_BYTE``."""
    count = (((acc % 256) ^ _STASH_BYTE) - sum(array)) % 256
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
        0,
    )


def _aim(start: int) -> int:
    r"""Return the seed count putting ``start + j1`` on the aim class."""
    offset = (start - _J2) % 64
    if offset <= 14:
        # Inside a class block; an odd.
        return start % 2
    return 64 - offset


def _node(array: list[int], acc: int) -> tuple[list[str], _State, _State, int]:
    r"""One read node: tokens, the 0-exit, the 1-exit, and the landing."""
    wrap = (256 - array[0]) % 256
    opened = [*_seeded(array, wrap), acc % 256]
    start = sum(opened)
    j1 = _aim(start)
    first = start + j1
    tokens = [
        *["SEED"] * wrap,
        "EXCRETE",
        *["SEED"] * j1,
        "DIGEST",
        *["SEED"] * _J2,
        "DIGEST",
        "ACCEPT",
        "DIGEST",
        "LEAPFROG",
    ]
    loaded = _seeded(opened, j1 + _J2)
    return tokens, ([*loaded, 0], first), ([*loaded, 1], first + 1), start - 15


def _trampoline(
    array: list[int], acc: int, target: int
) -> tuple[list[str], list[int], int]:
    r"""Build an unconditional jump to token ``target``, plus its exit."""
    cur, val, tokens = list(array), acc, []
    while sum(cur) - cur[0] < target - 255:
        chunk, cur, val = _stash_chunk(cur, val)
        tokens += chunk
    hop = target - (sum(cur) - cur[0])
    if not 1 <= hop <= 255:  # pragma: no cover - the window solve is exact
        raise AssertionError(f"trampoline byte {hop} escaped 1..255")
    count = (((val % 256) ^ hop) - sum(cur)) % 256
    tokens += [*["SEED"] * count, "DIGEST", "EXCRETE", "DIGEST", "LEAPFROG"]
    out = [(cur[0] + count) % 256, *cur[1:], hop]
    return tokens, out, sum(out)


def _chunk_run(chunks: int) -> int:
    r"""Bound from above what ``chunks`` stash chunks cost in tokens."""
    return 257 * min(chunks, 2) + 3 * max(0, chunks - 2)


def _widths(n: int) -> list[int]:
    r"""Per-level trampoline slot widths, from a cap recurrence."""
    caps = [255 + _LEAF_TAIL]
    widths = [0]
    for d in range(1, n + 1):
        child = caps[d - 1]
        # The trampoline's shortfall is.
        # past an entering non-head sum.
        # exactly 255 each and ``b``.
        span = max(child, _MIN_HOP) - 15
        hops = max(0, -(-(span - 255) // 255))
        slot = _chunk_run(hops) + 255 + _LEAF_TAIL + _SLOT_MARGIN
        widths.append(slot)
        # The node's own chunks: gains.
        # gain 0, hence the ``m - 3``).
        # chunk once the counts settle.
        chunks = -(-(255 + 15 + 514 + _NODE_MAX + slot + 768) // 253)
        caps.append(
            _chunk_run(chunks)
            + _NODE_MAX
            + slot
            + _PAD_MAX
            + max(child, _MIN_HOP)
            + child
        )
    return widths


def _leaf_seeds(array: list[int], acc: int, bit: int) -> int:
    r"""``SEED``s bringing the accumulator onto the digit's residue class."""
    return (((acc % 256) ^ (_ASCII_ZERO + bit)) - sum(array)) % 256


def _leaf(array: list[int], acc: int, bit: int) -> list[str]:
    r"""Print the table entry, then halt."""
    count = _leaf_seeds(array, acc, bit)
    return [*["SEED"] * count, "DIGEST", "PRONOUNCE", "EXCRETE", "LEAPFROG"]


def _entry(table: str, row: str) -> int:
    r"""Read the table's value on the path ``row``."""
    return int(table[int(row, 2) if row else 0])


def _subtree(
    table: str,
    n: int,
    depth: int,
    row: str,
    array: list[int],
    acc: int,
    base: int,
    widths: list[int],
) -> list[str]:
    r"""Build the subtree rooted here, knowing it starts at token ``base``."""
    if depth == n:
        return _leaf(array, acc, _entry(table, row))

    slot = widths[n - depth]
    prefix: list[str] = []
    cur, val = list(array), acc
    while True:
        tokens, fell, taken, landing = _node(cur, val)
        if landing >= base + len(prefix) + len(tokens) + slot:
            break
        # Not enough sum to clear the.
        # ends -- a chunk moves the.
        # by 0) while the threshold.
        # and every entering sum is at.
        # stays a handful rather than.
        chunk, cur, val = _stash_chunk(cur, val)
        prefix.extend(chunk)

    node_end = base + len(prefix) + len(tokens)
    one = _subtree(table, n, depth + 1, f"{row}1", *taken, landing, widths)
    target = landing + max(len(one), _MIN_HOP)
    hop, out_array, out_acc = _trampoline(*fell, target)
    if len(hop) > slot:
        raise AssertionError(
            f"trampoline of {len(hop)} tokens overflowed its {slot}-token slot"
        )
    dead = landing - node_end - len(hop)
    if dead < 0:
        raise AssertionError(f"the 1-subtree landed {-dead} tokens into the slot")
    zero = _subtree(table, n, depth + 1, f"{row}0", out_array, out_acc, target, widths)
    return [
        *prefix,
        *tokens,
        *hop,
        *["SEED"] * dead,
        *one,
        *["SEED"] * (target - landing - len(one)),
        *zero,
    ]


def slow_acv_mammalian(truth_table: str) -> str:
    r"""Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``."""
    # ``_validate_truth_table``.
    # always has at least one level.
    n = _validate_truth_table(truth_table)
    return " ".join(_subtree(truth_table, n, 0, "", [0], 0, 0, _widths(n)))
