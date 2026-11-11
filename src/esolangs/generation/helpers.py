"""Shared helpers for the boolean-function program generators.

A valid table has ``2**n`` entries, so ``n`` is recovered from the length
and the generators take no ``n`` parameter.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from types import MappingProxyType
from typing import NamedTuple

from esolangs._bindings import MARK as MARK
from esolangs._bindings import MOST_INPUTS as MOST_INPUTS
from esolangs._bindings import TEMPLATE_CHAR as TEMPLATE_CHAR
from esolangs._bindings import Setters as Setters
from esolangs._bindings import check_setters as check_setters
from esolangs._bindings import fill_runs as fill_runs
from esolangs._bindings import mark as mark
from esolangs._bindings import mark_runs as mark_runs
from esolangs._bindings import runs as runs
from esolangs._bindings import unmark as unmark
from esolangs.exceptions import TruthTableError
from esolangs.generation.lookup import prefix_counts as _prefix_counts
from esolangs.generation.lookup import symmetric_outputs as _symmetric_outputs
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


def grid_width(program: str) -> int:
    """Return the widest rendered row, including its padding."""
    return max(map(len, program.split("\n")))


def grid_area(program: str) -> int:
    """Return the cells of the program's bounding rectangle."""
    return grid_width(program) * (program.count("\n") + 1)


def grid_rank(program: str) -> tuple[int, int]:
    """Rank a 2D grid by area, then characters: grids are judged by area."""
    return grid_area(program), len(program)


def narrowest_grid(*candidates: str) -> str:
    """Return the narrowest layout, keeping the earlier one on a tie."""
    return min(candidates, key=grid_width)


def constant_span_test(truth_table: str) -> Callable[[int, int], bool]:
    """Return an O(1) test for whether a half-open table span is constant."""
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
    # The list comprehension avoids resuming a generator for each leaf.
    level = tuple([1 if bit == "1" else 0 for bit in truth_table])
    ids = [level]
    fresh = 2
    for _ in range(n):
        seen: dict[tuple[int, int], int] = {}
        above: list[int] = []
        children = iter(level)
        for zero, one in zip(children, children, strict=True):
            if zero == one and zero < 2:  # two equal constants stay one
                above.append(zero)
                continue
            if (zero, one) not in seen:
                seen[zero, one] = fresh
                fresh += 1
            above.append(seen[zero, one])
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


def check_table_text(truth_table: object) -> None:
    """Refuse a truth table that is not text."""
    if not isinstance(truth_table, str):
        raise with_hint(
            TruthTableError(
                f"truth table must be a string of '0' and '1', got "
                f"{type(truth_table).__name__}"
            ),
            ("pass truth-table text, for example '0110' for two-input XOR"),
        )


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
    # Alphabet first: length-first answered ``01a`` with "got 3 entries"
    # and never named the ``a``.  A set difference, since this runs per
    # character on every candidate build.
    if set(truth_table) - {"0", "1"}:
        # The *argument*, plus which character is wrong and where.  This
        # printed ``sorted(set(...))``, so someone who typed ``nonsense``
        # was told "got 'enos'" -- a string they had never seen, which
        # reads like a shell-quoting bug rather than a typo.  The sibling
        # validator in ``encode`` echoed the argument all along.
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


class ResidualDiagram(NamedTuple):
    """Ordered node IDs per depth, their children and their constant values."""

    levels: tuple[tuple[int, ...], ...]
    children: Mapping[int, tuple[int, int]]
    constants: Mapping[int, int | None]


def _residual_ids(truth_table: str, n: int) -> ResidualDiagram:
    """Canonical residual IDs, children and constant values in O(T) RAM work."""
    levels: list[tuple[int, ...]] = [()] * (n + 1)
    ids = [1 if bit == "1" else 0 for bit in truth_table]
    levels[n] = tuple(dict.fromkeys(ids))
    children: dict[int, tuple[int, int]] = {}
    constants: dict[int, int | None] = {0: 0, 1: 1}
    serial = 2
    for k in range(n - 1, -1, -1):
        names: dict[tuple[int, int], int] = {}
        parents = []
        for zero, one in zip(ids[::2], ids[1::2], strict=True):
            pair = (zero, one)
            if pair not in names:
                names[pair] = serial
                children[serial] = pair
                constants[serial] = (
                    constants[zero] if constants[zero] == constants[one] else None
                )
                serial += 1
            parents.append(names[pair])
        levels[k] = tuple(names.values())
        ids = parents
    return ResidualDiagram(
        tuple(levels), MappingProxyType(children), MappingProxyType(constants)
    )


def essential_inputs(truth_table: str, n: int) -> list[int]:
    """Input positions affecting the table, with O(T) worst-case RAM work.

    Slice comparisons stop early on dense tables. After four table lengths
    of comparisons, canonical child IDs bound the remaining work instead.
    """
    budget = 4 * len(truth_table)
    result = []
    for i in range(n):
        half = 1 << (n - 1 - i)
        block = 2 * half
        for lo in range(0, len(truth_table), block):
            if block > budget:
                if truth_table.count(truth_table[0]) == len(truth_table):
                    return []
                levels, children, _ = _residual_ids(truth_table, n)
                return [
                    k
                    for k in range(n)
                    if any(children[s][0] != children[s][1] for s in levels[k])
                ]
            budget -= block
            if truth_table[lo : lo + half] != truth_table[lo + half : lo + block]:
                result.append(i)
                break
    return result


def _depends_on(truth_table: str, half: int) -> bool:
    """Whether some block of ``2 * half`` rows has unequal halves."""
    block = 2 * half
    return any(
        truth_table[lo : lo + half] != truth_table[lo + half : lo + block]
        for lo in range(0, len(truth_table), block)
    )


def read_at(truth_table: str, inputs: tuple[int, ...] | list[int], n: int) -> str:
    """Return the ``len(inputs)``-input table read at the given input positions.

    Slot ``k`` varies with original input ``inputs[k]``; every input not
    named is held at 0.  :func:`permute_truth_table` passes all ``n`` (a
    renaming); projecting generators pass the
    essential inputs (holding an ignored one at 0 cannot change the answer).
    ``n`` is passed because the projected result is narrower than its input.
    """
    # The row indices are built by doubling rather than by re-scattering
    # each row's bits: slot ``k`` is the next-most-significant bit, so
    # appending ``o | mask`` after ``o`` extends the list in row order.
    # That is O(2**k) list work against O(2**k * k) bit tests -- worth the
    # doubling because order selection calls this once per candidate.
    #
    # Materialising that list costs 2**k int objects -- at k = 26 some
    # 1.9 GB, the packed build's whole peak -- so distinct slots take an
    # equivalent blocked path: their masks are distinct powers of two, the
    # doubling never collides, and a row's index is the XOR of the masks
    # of its set index bits (slot k's bit sits at index position
    # len(inputs) - 1 - k).  Only a low block of index bits gets an offset
    # table, built by the same doubling; each block of rows above it
    # shares one XOR base and is gathered and joined block by block.
    # Repeated slots (no caller passes any) keep the doubling verbatim.
    masks = [1 << (n - 1 - i) for i in inputs]
    # Dropping one input needs block slices, not a gather per output row.
    # Malbolge's 17-input projection otherwise lost over 10% generation speed.
    if len(masks) == n - 1 and masks == sorted(set(masks), reverse=True):
        missing = ((1 << n) - 1) ^ sum(masks)
        if 0 < missing < 1 << n and missing.bit_count() == 1:
            return "".join(
                truth_table[i : i + missing]
                for i in range(0, len(truth_table), 2 * missing)
            )
    if len(set(masks)) != len(masks):
        originals = [0]
        for mask in masks:
            originals = [x for o in originals for x in (o, o | mask)]
        return "".join([truth_table[o] for o in originals])
    by_bit = masks[::-1]
    low_bits = min(len(masks), 16)
    low = [0]
    for bit in range(low_bits):
        low += [offset ^ by_bit[bit] for offset in low]
    bases = [0]
    for bit in range(low_bits, len(masks)):
        bases += [base ^ by_bit[bit] for base in bases]
    return "".join(
        "".join([truth_table[base ^ offset] for offset in low]) for base in bases
    )


class WeightedLookup(NamedTuple):
    """Index ``table`` by the sum of weights for set inputs, first input first.

    Zero-weight inputs still belong to the reader; projection never licenses
    skipping their reads.
    """

    weights: tuple[int, ...]
    table: str


def input_weights(truth_table: str, n: int) -> WeightedLookup:
    """Each input's row weight in the table read at its essential inputs.

    An ignored input weighs 0, so a positional embed spends nothing on it:
    holding it at 0 cannot change the answer (see :func:`read_at`).
    """
    essential = essential_inputs(truth_table, n)
    weights = [0] * n
    for rank, i in enumerate(essential):
        weights[i] = 1 << (len(essential) - 1 - rank)
    return WeightedLookup(tuple(weights), read_at(truth_table, essential, n))


def symmetric_weights(truth_table: str, n: int) -> WeightedLookup | None:
    """Weight 1 per essential input and the table by popcount, if it is symmetric.

    A table that depends only on how many essential inputs are 1 (parity,
    majority, thresholds, and/or) is indexed by their sum: ``m + 1`` entries
    against ``2**m``.  None for asymmetric tables and fewer than two inputs.
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) < 2:
        return None
    outputs = _symmetric_outputs(read_at(truth_table, essential, n), len(essential))
    if outputs is None:
        return None
    weights = tuple(int(i in essential) for i in range(n))
    return WeightedLookup(weights, outputs)


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


def same_up_to_wrapping(template: str, plain: str) -> bool:
    """Whether ``template`` is ``plain``, or ``plain`` broken by newlines.

    The default ``same_layout`` of a ``Language``.
    """
    return template == plain or (
        "\n" not in plain and template.replace("\n", "") == plain
    )


def same_tokens(template: str, program: object) -> bool:
    """Whether the two hold the same whitespace-separated tokens."""
    return isinstance(program, str) and template.split() == program.split()


def same_token_layout(template: str, plain: str, _layout: object) -> bool:
    """Compare whitespace-separated tokens: ``same_layout`` for token languages."""
    return same_tokens(template, plain)


def same_ignoring_whitespace(template: str, plain: str, _layout: object) -> bool:
    """Compare with whitespace removed: ``same_layout`` for languages ignoring it."""
    return "".join(template.split()) == "".join(plain.split())


def layout_width(template: str) -> int:
    """Return the widest line of ``template``: the width it was laid out to."""
    return max(1, max(map(len, template.splitlines()), default=0))


def reflected_table(table: str, n: int) -> str:
    """Reorder rows by bit-reversed index, so the last input is tested first."""
    return "".join(table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(1 << n))
