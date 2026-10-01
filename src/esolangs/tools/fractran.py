"""FRACTRAN boolean templates with linear text and generation work.

High inputs route through alternating small-prime state thresholds. Blocks
use a shared threshold dictionary or a fixed exponent decoder, by text size.
The factored interpreter preserves first-match semantics without expanding
state powers. At most six inputs retain the smaller legacy construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice

from esolangs.factor_primes import prime_segments
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
)

#: How each input is set: the exponent of its prime in the starting value.
#: One digit wide, so the run is one :data:`TEMPLATE_CHAR`.
PAIR = ("0", "1")
_FRACTRAN_INPUT = TEMPLATE_CHAR * len(PAIR[0])

#: The widest table also built as a plain tree.  Below four inputs the
#: decoder's fractions and its ten reserved primes outweigh what blocks save,
#: on every table; at four the two split, and from five the tree all but
#: never wins while it grows as ``T log T``, so it is not built past here.
_PLAIN_MAX = 4

#: Preserve small-table text while changing the asymptotic execution path.
_INDEXED_MIN = 7

#: Segment width for the sieve; the primes wanted are a prefix of it.
_PRIME_CHUNK = 1 << 12

#: Primes the decoder reserves, ahead of the inputs and the tree's states:
#: the answer's 2, the two the block shuttles between, the offset counter,
#: and six to hold a loop's phase.
_CONTROL = 10


@dataclass(frozen=True)
class _Leaf:
    """A folded subtable: the answer, and the level it stops reading at."""

    answer: str
    depth: int


@dataclass(frozen=True)
class _Block:
    """An unfolded leaf: the ``w`` entries it loads, as one integer."""

    chunk: int


@dataclass(frozen=True)
class _Node:
    """An internal node: the input it reads, and its children's indices."""

    depth: int
    zero: int
    one: int


def _plan(n: int) -> tuple[int, int]:
    """Return ``v`` and how many blocks take the wider width ``2**(v + 1)``.

    Linearity needs only ``w = Omega(n)`` and a block costs ``O(2**w)`` steps
    to read, so the narrowest qualifying width wins: ``w`` near ``n / 3``.
    A power of two is too coarse a knob -- characters an entry would saw
    where ``w`` doubled -- so both widths are mixed to average the target,
    and covering a fraction ``x`` with the wider ones leaves
    ``(T / w)(1 - x / 2)`` blocks, which fixes ``x``.
    """
    triple = max(9, n)
    v = max(1, min(n, (triple // 3).bit_length() - 1))
    if v >= n:
        return v, 0
    # ``x = 1 - 2**v / target`` with ``target = triple / 3``, in integers.
    wide = (1 << n) * (triple - 3 * (1 << v)) // (triple << v)
    return v, min(wide, 1 << (n - v - 1))


def _primes(count: int) -> list[int]:
    """Return the first ``count`` primes, 2 first."""
    stream = (
        prime
        for _start, _stop, segment in prime_segments(_PRIME_CHUNK)
        for prime in segment
    )
    return list(islice(stream, count))


def _tree(truth_table: str, n: int, v: int, wide: int) -> list[_Leaf | _Block | _Node]:
    """Return the block tree, post-order, root last.

    ``wide`` blocks stop a level above the rest, holding twice as many
    entries; which ones is arbitrary, only how many.
    """
    constant = constant_span_test(truth_table)
    nodes: list[_Leaf | _Block | _Node] = []
    budget = [wide]

    def block(lo: int, hi: int) -> int:
        # Low entry first, so the offset is the exponent's own shift.
        nodes.append(_Block(sum(int(truth_table[lo + i]) << i for i in range(hi - lo))))
        return len(nodes) - 1

    def walk(depth: int, lo: int, hi: int) -> int:
        if constant(lo, hi):
            nodes.append(_Leaf(truth_table[lo], depth))
        elif depth == n - v:
            return block(lo, hi)
        elif depth == n - v - 1 and budget[0] > 0:
            budget[0] -= 1
            return block(lo, hi)
        else:
            mid = (lo + hi) // 2
            zero = walk(depth + 1, lo, mid)
            one = walk(depth + 1, mid, hi)
            nodes.append(_Node(depth, zero, one))
        return len(nodes) - 1

    walk(0, 0, len(truth_table))
    return nodes


def _decoder(control: list[int]) -> list[str]:
    """Return the twelve fractions that read one bit out of a block.

    Each loop alternates between two phase primes, because a fraction holding
    its own phase prime in numerator and denominator alike would cancel it
    out of the guard the interpreter tests, and fire everywhere.  The last
    two need no phase: every earlier state holds a tree state or a phase
    prime whose unguarded fraction comes first.
    """
    carry, work, count = control[1:4]
    ready, halve, shift, back, move, cycle = control[4:]
    return [
        # A shift still to make?  Spend one unit of the offset counter.
        f"{shift}/{ready * count}",
        # Halve, by moving two of the carry prime into one of the work prime.
        f"{halve}*{work}/{shift}*{carry}^2",
        f"{shift}/{halve}",
        f"{back}/{shift}",
        # Whatever the halving shifted out is not the answer.
        f"{move}/{back}*{carry}",
        f"{move}/{back}",
        # Move the halved block back, for the next shift to read.
        f"{cycle}*{carry}/{move}*{work}",
        f"{move}/{cycle}",
        f"{ready}/{move}",
        # The counter is spent: the answer is the low bit of what is left,
        # found by casting out pairs.
        f"1/{ready}",
        f"1/{carry}^2",
        f"2/{carry}",
    ]


def _power(prime: int, exponent: int) -> str:
    """Return ``prime^exponent``, or the bare prime for an exponent of 1."""
    return f"{prime}^{exponent}" if exponent > 1 else str(prime)


def _nodes(
    nodes: list[_Leaf | _Block | _Node],
    states: list[int],
    inputs: list[int],
    load: tuple[int, int],
) -> list[str]:
    """Return the tree's fractions: a leaf's answer, a block's load, a node's two.

    ``load`` is the decoder's ``(ready, carry)`` pair a block multiplies in;
    a tree without blocks never reads it.
    """
    ready, carry = load
    fractions: list[str] = []
    for index, entry in enumerate(nodes):
        if isinstance(entry, _Leaf):
            fractions.append(f"{2 if entry.answer == '1' else 1}/{states[index]}")
        elif isinstance(entry, _Block):
            chunk = f"{_power(carry, entry.chunk)}*" if entry.chunk else ""
            fractions.append(f"{chunk}{ready}/{states[index]}")
        else:
            # The one-child first: the zero-child is the else, by priority.
            one, zero = entry.one, entry.zero
            fractions.append(f"{states[one]}/{states[index] * inputs[entry.depth]}")
            fractions.append(f"{states[zero]}/{states[index]}")
    return fractions


def _start(states: list[int], inputs: list[int]) -> str:
    """Return the starting value: the root's state, and each input's run."""
    return "*".join(
        [str(states[-1])] + [f"{prime}^{_FRACTRAN_INPUT}" for prime in inputs]
    )


def _shallowest(nodes: list[_Leaf | _Block | _Node], n: int) -> int:
    """Return the depth of the shallowest folded leaf, or ``n`` for none."""
    return min((e.depth for e in nodes if isinstance(e, _Leaf)), default=n)


def _plain(truth_table: str, n: int, *, small_root: bool = False) -> str:
    """Return the table as a plain tree: every level read, no decoder.

    Only ``2`` is reserved, so the inputs and states take the smallest primes
    there are, and a run is a step a level, one for the leaf, and a clear for
    each input a folded leaf left unread.
    """
    nodes = _tree(truth_table, n, 0, 0)
    primes = _primes(1 + n + len(nodes))
    inputs, states = primes[1 : 1 + n], primes[1 + n :]
    if small_root:
        states[0], states[-1] = states[-1], states[0]
    fractions = _nodes(nodes, states, inputs, (1, 1))
    fractions += [f"1/{prime}" for prime in inputs[_shallowest(nodes, n) :]]
    return " ".join([_start(states, inputs), *fractions])


def _packed(truth_table: str, n: int) -> str:
    """Return the table as blocks under a tree, read out by the decoder."""
    v, wide = _plan(n)
    nodes = _tree(truth_table, n, v, wide)
    primes = _primes(_CONTROL + n + len(nodes))
    control = primes[:_CONTROL]
    carry, count, ready = control[1], control[3], control[4]
    inputs = primes[_CONTROL : _CONTROL + n]
    states = primes[_CONTROL + n :]

    fractions = _nodes(nodes, states, inputs, (ready, carry))
    # The offset, in unary: one fraction per input the tree did not read.
    # They sit *after* the tree and before the decoder, which is what makes
    # them safe -- a descending tree always has a fraction of its own to
    # fire, so these get their turn only once a block is loaded.  The widest
    # weight belongs to the level a wide block skipped; under a narrow one
    # that prime is already gone, so the two widths need no marker.
    first = n - v - 1 if wide and v < n else n - v
    fractions += [
        f"{_power(count, 1 << (n - 1 - level))}/{inputs[level]}"
        for level in range(first, n)
    ]
    fractions += _decoder(control)
    # A folded answer leaves the tree's inputs from its level down unread,
    # and an offset that no block asked for; a block's path spends both.
    shallowest = _shallowest(nodes, n)
    if shallowest < n:
        fractions += [f"1/{prime}" for prime in (*inputs[shallowest:first], count)]

    return " ".join([_start(states, inputs), *fractions])


def _threshold(table: str, n: int) -> str:
    """Return small-prime state thresholds with shared block dictionaries."""
    v, wide = _plan(n)
    budget = [wide]
    nodes: list[_Leaf | _Block | _Node] = []
    depths: list[int] = []
    constant = constant_span_test(table)

    def walk(depth: int, lo: int, hi: int) -> int:
        if constant(lo, hi):
            nodes.append(_Leaf(table[lo], depth))
        elif depth == n - v or (depth == n - v - 1 and budget[0] > 0):
            if depth == n - v - 1:
                budget[0] -= 1
            nodes.append(_Block(int(table[lo:hi][::-1], 2)))
        else:
            mid = (lo + hi) // 2
            zero = walk(depth + 1, lo, mid)
            one = walk(depth + 1, mid, hi)
            nodes.append(_Node(depth, zero, one))
        depths.append(depth)
        return len(nodes) - 1

    walk(0, 0, len(table))
    chunks = list(dict.fromkeys(e.chunk for e in nodes if isinstance(e, _Block)))
    patterns = {chunk: i + 1 for i, chunk in enumerate(chunks)}
    inputs = _primes(n + 5)[5:]

    def state(i: int) -> str:
        # Unshifted labels crossed decimal widths: n=9,11,13 read 4.690.
        # T+i keeps the state fields at table-width magnitude (4.262).
        depth = depths[i]
        return _power(3 if depth % 2 == 0 else 5, len(table) + i + 1)

    rules: list[str] = []
    for i in reversed(range(len(nodes))):
        e = nodes[i]
        guard = state(i)
        if isinstance(e, _Node):
            rules += [
                f"{state(e.one)}/{guard}*{inputs[e.depth]}",
                f"{state(e.zero)}/{guard}",
            ]
        elif isinstance(e, _Leaf):
            rules.append(f"{2 if e.answer == '1' else 1}/{guard}")
        else:
            rules.append(f"{_power(7, patterns[e.chunk])}/{guard}")
    rules += [
        f"{_power(11, 1 << (n - 1 - level))}/{inputs[level]}"
        for level in range(n - v - 1 if wide and v < n else n - v, n)
    ]
    for chunk, ident in reversed(list(patterns.items())):
        for offset in reversed(range(1 << (v + 1 if wide and v < n else v))):
            bit = (chunk >> offset) & 1
            if offset and bit == ((chunk >> (offset - 1)) & 1):
                continue
            guard = _power(7, ident)
            if offset:
                guard += "*" + _power(11, offset)
            rules.append(f"{2 if bit else 1}/{guard}")
    rules += [f"1/{p}" for p in [*inputs, 11]]
    start = "*".join([state(len(nodes) - 1)] + [f"{p}^{TEMPLATE_CHAR}" for p in inputs])
    return " ".join([start, *rules])


def _indexed_blocks(table: str, n: int) -> str:
    """Return indexed states with packed blocks and a fixed exponent decoder."""
    v, wide = _plan(n)
    nodes = _tree(table, n, v, wide)
    depths: dict[int, int] = {}

    def visit(index: int, depth: int) -> None:
        depths[index] = depth
        entry = nodes[index]
        if isinstance(entry, _Node):
            visit(entry.zero, depth + 1)
            visit(entry.one, depth + 1)

    visit(len(nodes) - 1, 0)
    inputs = _primes(n + 12)[12:]
    control = [2, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    carry, count, ready = 7, 13, 17

    def state(index: int) -> str:
        return _power(3 if depths[index] % 2 == 0 else 5, len(table) + index + 1)

    rules: list[str] = []
    for index in reversed(range(len(nodes))):
        entry, guard = nodes[index], state(index)
        if isinstance(entry, _Node):
            rules.extend(
                [
                    f"{state(entry.one)}/{guard}*{inputs[entry.depth]}",
                    f"{state(entry.zero)}/{guard}",
                ]
            )
        elif isinstance(entry, _Leaf):
            rules.append(f"{2 if entry.answer == '1' else 1}/{guard}")
        else:
            chunk = f"{_power(carry, entry.chunk)}*" if entry.chunk else ""
            rules.append(f"{chunk}{ready}/{guard}")
    first = n - v - 1 if wide and v < n else n - v
    rules += [
        f"{_power(count, 1 << (n - 1 - level))}/{inputs[level]}"
        for level in range(first, n)
    ]
    rules += _decoder(control)
    shallowest = _shallowest(nodes, n)
    if shallowest < n:
        rules += [f"1/{p}" for p in (*inputs[shallowest:first], count)]
    start = "*".join(
        [state(len(nodes) - 1)] + [f"{p}^{_FRACTRAN_INPUT}" for p in inputs]
    )
    return " ".join([start, *rules])


def _indexed(table: str, n: int) -> str:
    """Return the smaller indexed threshold or packed-block construction."""
    packed = _indexed_blocks(table, n)
    threshold = _threshold(table, n)
    return threshold if len(threshold) <= len(packed) else packed


def _fractran_raw(truth_table: str) -> str:
    """Return a template, with input-prime exponents filled by ``PAIR``.

    Halts at 1 or 2 for zero or one. Seven inputs use indexed blocks;
    small tables use trees and intermediate tables use packed blocks.
    """
    n = _validate_truth_table(truth_table)
    if n >= _INDEXED_MIN:
        return _indexed(truth_table, n)
    if n <= _PLAIN_MAX:
        return _plain(truth_table, n)
    return _packed(truth_table, n)


def fractran(truth_table: str, width: int | None = None) -> str:
    """Return a template; narrow small tables give the root the smallest state prime."""
    from esolangs.tools.wrap import wrap_program

    program = _fractran_raw(truth_table)
    if width is None:
        return program
    n = _validate_truth_table(truth_table)
    floor = max(map(len, program.split()))
    if floor > width and n <= _PLAIN_MAX:
        narrow = _plain(truth_table, n, small_root=True)
        if max(map(len, narrow.split())) < floor:
            program = narrow
    # Consume unique phase primes3/7 once, depositing5 for each one.
    # Cancel paired ones, then move the remaining5 onto answer2.
    if (
        n == 2
        and max(map(len, program.split())) > width
        and all(int(bit) == row.bit_count() % 2 for row, bit in enumerate(truth_table))
    ):
        program = _PARITY_BINARY if width < 4 else _PARITY_TWO
    return wrap_program(program, "fractran", width)


_PARITY_TWO = "21 $/3 $/7 1/25 2/5"
_PARITY_PAIR = ("1", "5")
_PARITY_BINARY = "21 $/3 $/7 1/4"


def fractran_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return parity numerator setters only for the exact two-phase program."""
    pair = PAIR
    if n == 2:
        if template.split() == _PARITY_TWO.split():
            pair = _PARITY_PAIR
        elif template.split() == _PARITY_BINARY.split():
            pair = ("1", "2")
    return (pair,) * n
