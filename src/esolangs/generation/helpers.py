"""Shared helpers for the boolean-function program generators.

A valid table has ``2**n`` entries, so ``n`` is recovered from the length
and the generators take no ``n`` parameter.
"""

from array import array
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from types import MappingProxyType

from esolangs.exceptions import TruthTableError
from esolangs.generation.lookup import prefix_counts as _prefix_counts
from esolangs.generation.lookup import prefix_totals as _prefix_totals
from esolangs.generation.projection import _LEAF_BITS, essential_inputs, read_at
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import with_hint

# ``ord("0")``.  Input digits arrive as 48/49 from a byte-oriented read, and a
# result prints as ``_ASCII_ZERO + bit``, so this offset appears in every
# generator that reads or writes a digit.  Named because a bare ``48`` in a run
# of ``+`` or ``-`` reads as a magic number.
_ASCII_ZERO = 48
_ASCII_ONE = _ASCII_ZERO + 1  # ``ord("1")``, the digit the other branch prints


def short_name(index: int, alphabet: str) -> str:
    """Return the zero-based bijective-base name over a nonempty alphabet."""
    if index < 0 or not alphabet:
        raise ValueError("short_name needs a nonnegative index and nonempty alphabet")
    value = index + 1
    chars = []
    while value:
        value, digit = divmod(value - 1, len(alphabet))
        chars.append(alphabet[digit])
    return "".join(reversed(chars))


def constant_span_test(truth_table: str) -> Callable[[int, int], bool]:
    """Return an O(1) test for whether a half-open table span is constant."""
    ones: Sequence[int]
    if len(truth_table) >= 4096:
        # Large indexes otherwise retain a Python int and a list slot per row.
        width = "I" if len(truth_table).bit_length() <= 8 * array("I").itemsize else "Q"
        ones = array(width, _prefix_totals(truth_table, "1"))
    else:
        ones = _prefix_counts(truth_table, "1")

    def constant(start: int, stop: int) -> bool:
        count = ones[stop] - ones[start]
        return count in (0, stop - start)

    return constant


def subtree_ids(truth_table: str) -> tuple[tuple[int, ...], ...]:
    """Return immutable subtable ids, equal ones at a level sharing one.

    ``ids[d][k]`` names the ``k``-th subtable of ``2**(n - d)`` rows:
    ``ids[0]`` is the whole table, ``ids[n]`` its rows.  A constant subtable
    is ``0`` or ``1`` at every level; any other id is fresh the first time
    its pair of halves turns up, so ids ascend with first occurrence along a
    level.  Built bottom-up from the child ids, one dict lookup a node (the
    quasi-reduced decision diagram, interned rather than searched), in O(T).
    """
    n = _validate_truth_table(truth_table)
    level = tuple(str.encode(truth_table, "ascii").translate(_LEAF_BITS))
    ids = [level]
    fresh = 2
    for _ in range(n):
        seen: dict[tuple[int, int], int] = {}
        above: list[int] = []
        children = iter(level)
        for pair in zip(children, children, strict=True):
            zero, one = pair
            if zero == one and zero < 2:  # two equal constants stay one
                above.append(zero)
                continue
            node = seen.get(pair)
            if node is None:
                node = seen[pair] = fresh
                fresh += 1
            above.append(node)
        level = tuple(above)
        ids.append(level)
    ids.reverse()
    return tuple(ids)


def subtree_slot(
    ids: Sequence[Sequence[int]], level: int, block: int, *, skip: bool
) -> tuple[int, int, tuple[int, int]]:
    """Name the subtree at ``block`` of ``level`` for a shared tree's lookup.

    With ``skip``, a test whose halves agree is passed over for its zero
    half.  The name is ``(level, id)`` for a node and ``(-1, bit)`` for a
    leaf, which is the same code at every level.
    """
    while skip and level + 1 < len(ids) and ids[level][block] >= 2:
        if ids[level + 1][2 * block] != ids[level + 1][2 * block + 1]:
            break
        level, block = level + 1, 2 * block
    key = ids[level][block]
    return level, block, (level, key) if key >= 2 else (-1, key)


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class SubtreeDiagram:
    """The reduced diagram by subtree id, for a tree that hands a share down.

    ``halves[key]`` are a node's zero and one halves and ``level[key]`` its
    depth; ids are unique across levels, so an id alone names a node.  A
    generator that pushes or binds a repeated subtree once, where its copies
    all lie below, asks :meth:`reaches` whether a half still needs it and
    :meth:`repeated_near` which subtrees are worth offering.  Both memoize
    per id, so each is O(1) a node amortized for a fixed ``depth``.
    """

    root: int
    halves: Mapping[int, tuple[int, int]]
    level: Mapping[int, int]
    _reach: dict[tuple[int, int], bool] = field(init=False)
    _counts: dict[tuple[int, int], dict[int, int]] = field(init=False)

    def __init__(self, truth_table: str) -> None:
        """Intern subtrees and retain the read-only node index."""
        ids = subtree_ids(truth_table)
        halves: dict[int, tuple[int, int]] = {}
        level: dict[int, int] = {}
        for depth, (row, under) in enumerate(pairwise(ids)):
            for block, key in enumerate(row):
                if key >= 2 and key not in halves:
                    halves[key] = (under[2 * block], under[2 * block + 1])
                    level[key] = depth
        object.__setattr__(self, "root", ids[0][0])
        object.__setattr__(self, "halves", MappingProxyType(halves))
        object.__setattr__(self, "level", MappingProxyType(level))
        object.__setattr__(self, "_reach", {})
        object.__setattr__(self, "_counts", {})

    def reaches(self, key: int, target: int) -> bool:
        """Whether node ``target`` is ``key`` or lies below it."""
        if key == target:
            return True
        if key < 2 or self.level[key] >= self.level[target]:
            return False
        if (key, target) not in self._reach:
            halves = set(self.halves[key])
            found = any(self.reaches(half, target) for half in halves)
            self._reach[key, target] = found
        return self._reach[key, target]

    def _count(self, key: int, depth: int) -> dict[int, int]:
        """Count each node within ``depth`` levels below, equal halves once."""
        if key < 2 or not depth:
            return {}
        if (key, depth) not in self._counts:
            found: dict[int, int] = {}
            for half in set(self.halves[key]):
                below = self._count(half, depth - 1).items()
                for name, count in [(half, 1), *below]:
                    if name >= 2:
                        found[name] = found.get(name, 0) + count
            self._counts[key, depth] = found
        return self._counts[key, depth]

    def repeated_near(self, key: int, depth: int) -> list[int]:
        """Return the nodes met twice or more within ``depth`` levels below."""
        return [name for name, count in self._count(key, depth).items() if count > 1]


def check_table_text(truth_table: object) -> str:
    """Return the truth table's text, independent of subclass behavior."""
    if not _has_backing_type(truth_table, str):
        raise with_hint(
            TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            ),
            ("pass truth-table text, for example '0110' for two-input XOR"),
        )
    return str.__str__(truth_table)


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``.

    A one-entry table (``2**0``) is refused: it is a constant, not a
    function of any input, and 44 generators used to build one, 24 then
    crashing with ``IndexError`` and 16 with ``negative shift count``.
    """
    n = _validate_shape(truth_table)
    if n == 0:
        raise with_hint(
            TruthTableError(
                "truth table needs at least one input (n >= 1); "
                "a one-entry table is a constant, not a boolean function"
            ),
            ("use '00' or '11' to represent a constant with one input"),
        )
    return n


def _validate_shape(truth_table: str) -> int:
    """Validate a table's *shape* only, allowing a nullary one.

    A generator's ``_solve`` can reduce to essential inputs and reach a
    one-entry table on the way down; its public entry still validates in full.
    """
    # Check the alphabet first so ``01a`` names the ``a``. Count in C on
    # candidate builds and scan for the offending character only on error.
    if str.count(truth_table, "0") + str.count(truth_table, "1") != len(truth_table):
        # The *argument*, plus which character is wrong and where.  This
        # printed ``sorted(set(...))``, so someone who typed ``nonsense``
        # was told "got 'enos'" -- a string they had never seen, which
        # reads like a shell-quoting bug rather than a typo.  The sibling
        # validator in ``encode-inputs`` echoed the argument all along.
        bad = next((i, c) for i, c in enumerate(truth_table) if c not in {"0", "1"})
        raise with_hint(
            TruthTableError(
                f"truth table must contain only '0' and '1', got {truth_table!r} "
                f"-- {bad[1]!r} at position {bad[0]} is not one of them"
            ),
            ("write adjacent 0/1 results in row order, without spaces or separators"),
        )
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        # The likeliest first error anyone gets, and the rule alone leaves
        # them to do the arithmetic.  The brackets are cheap here because
        # this is the cold path and only ever raises once.
        between = (
            f"; {len(truth_table)} is between {2**n} "
            f"({n} input{'' if n == 1 else 's'}) and "
            f"{2 ** (n + 1)} ({n + 1} input{'' if n + 1 == 1 else 's'})"
            if truth_table
            else ""
        )
        raise with_hint(
            TruthTableError(
                "truth table must have a power-of-two number of entries "
                f"(2**n), got {len(truth_table)}{between}",
            ),
            (
                "choose n inputs and provide 2**n results; two "
                "inputs need four, for example '0110'"
            ),
        )
    return n


def permute_truth_table(truth_table: str, perm: tuple[int, ...]) -> str:
    """Rewrite ``truth_table`` so level ``k`` splits on original input ``perm[k]``.

    The same function with its inputs renamed.  A subtree folds only when
    its rows agree, and the split order decides which rows a subtree
    covers: ``11110000`` folds after one split, ``10101010`` only at the
    bottom, and reordering lets the second be emitted as the first.
    """
    _validate_truth_table(truth_table)
    return read_at(truth_table, perm, len(perm))


def stored_inputs(truth_table: str, perm: tuple[int, ...]) -> set[int]:
    """Return the *stream* inputs a decision tree over ``perm`` has to keep.

    Analyze the permuted table in O(T), then map essential levels through
    ``perm`` to their positions in the original input stream.
    """
    n = _validate_truth_table(truth_table)
    return {perm[k] for k in essential_inputs(truth_table, n)}


def in_input_order[T](
    truth_table: str,
    build: Callable[[str, tuple[int, ...]], T],
) -> T:
    """Build a validated table in input order."""
    n = _validate_truth_table(truth_table)
    return build(truth_table, tuple(range(n)))


def move_text(start: int, target: int, right: str, left: str) -> str:
    """Return the moves taking a one-dimensional pointer to ``target``.

    One run, not one token per cell, so a caller measuring maximal runs
    sees the same count either way.
    """
    delta = target - start
    return right * delta if delta >= 0 else left * -delta


def same_tokens(template: str, program: object) -> bool:
    """Whether the two hold the same whitespace-separated tokens."""
    return isinstance(program, str) and template.split() == program.split()


def same_token_layout(template: str, plain: str, _layout: object) -> bool:
    """Compare whitespace-separated tokens: ``same_layout`` for token languages."""
    return same_tokens(template, plain)
