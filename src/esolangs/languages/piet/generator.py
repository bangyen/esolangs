"""Piet Boolean generator: triple entries from four essential inputs.

Pushes three bits per entry, reads inputs into a row number, and ``roll``
selects its chunk; integer division extracts the bit. Small lookups stay packed.
One-hot and one-cold tables use literal products; majority and its complement
sum and compare the essential inputs. See :mod:`esolangs.generation.raster_lookup`.

Size:
    O(T) codels; n=10 parity: 6,477 codels, n=10 and: 66 codels.
    n=8 majority: 87 codels (scale 1), counting its essential inputs.
    Triple strips trade area for commands ([ablations.chunked_entry_push]).
    Constant strips use 6n+12-3b codels (scale 1), 2n+3-b steps and
    4+bl(2n+3-b)+bl(2n-1)+bl(n) written bits; packing can reduce the area.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, essential_inputs, read_at
from esolangs.generation.raster_lookup import (
    _ADD,
    _DUPLICATE,
    _INITIAL,
    _MULTIPLY,
    _NOT,
    _OUT_NUMBER,
    _ROLL,
    _SUBTRACT,
    _literal_product,
    _majority_count,
    _next_colour,
    _Operation,
    _operations,
    _push,
    _row_number,
    _select,
    strip,
)
from esolangs.generation.raster_lookup.balance import (
    _bounded_operations,
    balance,
    folded,
)
from esolangs.generation.raster_lookup.packing import _raster_score, smallest
from esolangs.raster import Raster
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec, SourceKind


@cache
def _generate(truth_table: str) -> Raster:
    """Return a Piet raster computing ``truth_table``."""
    inputs = _validate_truth_table(truth_table)
    return strip(_operations(truth_table, inputs), _INITIAL, _next_colour)


def _area(image: Raster) -> int:
    return len(image.rows) * len(image.rows[0])


@cache
def _packed(truth_table: str) -> Raster:
    """Return the least-area packed layout, bounded by the strip."""
    return smallest(_bounded_operations(truth_table), _generate(truth_table))


@cache
def _smallest(truth_table: str) -> Raster:
    """Return the strip, or the least-area packed layout.

    The strip wins a tie; see [ablations.area_default].
    """
    flat, packed = _generate(truth_table), _packed(truth_table)
    return packed if _area(packed) < _area(flat) else flat


def _chunks(
    table: str, essential: list[int], inputs: int, *, flip: bool
) -> list[_Operation]:
    """Store three bits per entry; retain the row to decode the selected bit."""
    op, push = _Operation, _push
    values = [
        sum(int(bit) << j for j, bit in enumerate(table[i : i + 3]))
        for i in range(0, len(table), 3)
    ]
    count = len(values)
    operations = []
    for value in values:
        operations.extend([push(value)] if value else [push(1), op(_NOT)])
    operations += _row_number(essential, inputs, 0)
    operations += [
        op(_DUPLICATE),
        push(count + 2),
        push(1),
        op(_ROLL),
        push(3),
        op((2, 0)),
    ]
    operations += _select(count)
    operations += [
        push(count + 1),
        push(1),
        push(2),
        op(_SUBTRACT),
        op(_ROLL),
        push(3),
        op((2, 1)),
    ]
    # q(q+1)/2+1 is 1, 2, 4 for q=0,1,2.
    operations += [
        op(_DUPLICATE),
        push(1),
        op(_ADD),
        op(_MULTIPLY),
        push(2),
        op((2, 0)),
        push(1),
        op(_ADD),
        op((2, 0)),
        push(2),
        op((2, 1)),
    ]
    if flip:
        operations.append(op(_NOT))
    return [*operations, op(_OUT_NUMBER)]


@cache
def _default(table: str) -> Raster:
    """Use triple strips past the proved command crossover; retain linear families."""
    inputs = _validate_truth_table(table)
    essential = essential_inputs(table, inputs)
    reduced = read_at(table, essential, inputs)
    # The worst-command bound crosses at m=4: 96 -> 68.
    # At m=3, 00011111 actually loses39 ->56.
    # This command-admitted rule can enlarge individual tables.
    if (
        len(essential) < 4
        or any(
            _literal_product(reduced, essential, inputs, summed=summed)
            for summed in (False, True)
        )
        or _majority_count(reduced, essential, inputs) is not None
    ):
        return _smallest(table)
    complement = reduced.translate(str.maketrans("01", "10"))
    operations = min(
        (
            _chunks(reduced, essential, inputs, flip=False),
            _chunks(complement, essential, inputs, flip=True),
        ),
        key=lambda operations: (
            sum(operation.size for operation in operations),
            len(operations),
        ),
    )
    return strip(operations, _INITIAL, _next_colour)


def _balance(truth_table: str, default: Raster) -> Raster:
    """Balance the legacy strip, keeping the default when it is squarer.

    Before triple strips, seeding with the packed default left it
    unchanged on random tables; the strip gives -24.4% balanced area at
    n=7 and parity / majority -14% to -26% at n=7..9
    ([ablations.balance_strip_seed]).
    """
    return min(balance(truth_table, _generate(truth_table)), default, key=_raster_score)


def piet(truth_table: str, width: int | None = None, *, scale: int = 1) -> Raster:
    """Return a Piet raster computing the table."""
    if width is not None:
        return folded(truth_table, width).upscaled(scale)
    return _default(truth_table).upscaled(scale)


LANGUAGE = Language(
    "Piet",
    RuntimeSpec(
        "piet",
        category="stack_based",
        source_kind=SourceKind.RASTER,
        eof="an exhausted input command is ignored, as the spec requires",
    ),
    boolean=piet,
    contract=BooleanContract(
        note="the committed example is drawn at 80 pixels per codel; "
        "generate draws 1 unless --scale says otherwise"
    ),
    balance=_balance,
    example=Example(scale=80),
)
