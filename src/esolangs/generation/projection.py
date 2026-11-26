"""Essential inputs and row lookups for Boolean generators."""

from collections.abc import Mapping, Sequence
from itertools import pairwise
from types import MappingProxyType
from typing import NamedTuple

from esolangs.generation.lookup import symmetric_outputs as _symmetric_outputs

_LEAF_BITS = bytes.maketrans(b"01", b"\x00\x01")


class ResidualDiagram(NamedTuple):
    """Ordered node IDs per depth, their children and their constant values."""

    levels: tuple[tuple[int, ...], ...]
    children: Mapping[int, tuple[int, int]]
    constants: Mapping[int, int | None]


def _residual_ids(truth_table: str, n: int) -> ResidualDiagram:
    """Canonical residual IDs, children and constant values in O(T) RAM work."""
    levels: list[tuple[int, ...]] = [()] * (n + 1)
    ids: Sequence[int] = str.encode(truth_table, "ascii").translate(_LEAF_BITS)
    levels[n] = tuple(dict.fromkeys(ids))
    children: dict[int, tuple[int, int]] = {}
    constants: dict[int, int | None] = {0: 0, 1: 1}
    serial = 2
    for k in range(n - 1, -1, -1):
        names: dict[tuple[int, int], int] = {}
        parents = []
        layer = iter(ids)
        for pair in zip(layer, layer, strict=True):
            node = names.get(pair)
            if node is None:
                node = names[pair] = serial
                children[node] = pair
                zero, one = pair
                constants[node] = (
                    constants[zero] if constants[zero] == constants[one] else None
                )
                serial += 1
            parents.append(node)
        levels[k] = tuple(names.values())
        ids = parents
    return ResidualDiagram(
        tuple(levels), MappingProxyType(children), MappingProxyType(constants)
    )


def essential_inputs(truth_table: str, n: int) -> list[int]:
    """Input positions affecting the table, with O(T) worst-case RAM work.

    Shrink equal leading halves as they are proved independent. After four
    table lengths of comparisons, canonical child IDs bound remaining work.
    """
    budget = 4 * len(truth_table)
    result = []
    ignored = 0
    for i in range(n):
        half = 1 << (n - 1 - i)
        block = 2 * half
        for lo in range(0, len(truth_table), block):
            if block > budget:
                if truth_table.count(truth_table[0]) == len(truth_table):
                    return []
                levels, children, _ = _residual_ids(truth_table, n - ignored)
                return [
                    k + ignored
                    for k in range(n - ignored)
                    if any(children[s][0] != children[s][1] for s in levels[k])
                ]
            budget -= block
            left = truth_table[lo : lo + half]
            if not truth_table.startswith(left, lo + half, lo + block):
                result.append(i)
                break
            if not result and block == len(truth_table):
                truth_table = left
                ignored += 1
    return result


def read_at(truth_table: str, inputs: tuple[int, ...] | list[int], n: int) -> str:
    """Return the ``len(inputs)``-input table read at the given input positions.

    Slot ``k`` varies with original input ``inputs[k]``; every input not
    named is held at 0.  :func:`permute_truth_table` passes all ``n`` (a
    renaming); projecting generators pass the
    essential inputs (holding an ignored one at 0 cannot change the answer).
    ``n`` is passed because the projected result is narrower than its input.
    """
    if (
        len(inputs) == n
        and len(truth_table) == 1 << n
        and all(slot == original for slot, original in enumerate(inputs))
    ):
        return truth_table
    if inputs and len(inputs) < n and all(b == a + 1 for a, b in pairwise(inputs)):
        # With the omitted bits held at zero, contiguous slots are a stride.
        stride = 1 << (n - 1 - inputs[-1])
        last = ((1 << len(inputs)) - 1) * stride
        if last < len(truth_table):
            return truth_table[: last + 1 : stride]

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


def input_weights(
    truth_table: str, n: int, *, essential: list[int] | None = None
) -> WeightedLookup:
    """Each input's row weight in the table read at its essential inputs.

    An ignored input weighs 0, so a positional embed spends nothing on it:
    holding it at 0 cannot change the answer (see :func:`read_at`).
    """
    if essential is None:
        essential = essential_inputs(truth_table, n)
    weights = [0] * n
    for rank, i in enumerate(essential):
        weights[i] = 1 << (len(essential) - 1 - rank)
    return WeightedLookup(tuple(weights), read_at(truth_table, essential, n))


def symmetric_lookup(projected: WeightedLookup) -> WeightedLookup | None:
    """Index an already projected binary lookup by popcount if it is symmetric."""
    weights, table = projected
    kept = sum(map(bool, weights))
    if kept < 2 or (outputs := _symmetric_outputs(table, kept)) is None:
        return None
    return WeightedLookup(tuple(int(bool(weight)) for weight in weights), outputs)


def reflected_table(table: str, n: int) -> str:
    """Reorder rows by bit-reversed index, so the last input is tested first."""
    return read_at(table, tuple(range(n - 1, -1, -1)), n)
