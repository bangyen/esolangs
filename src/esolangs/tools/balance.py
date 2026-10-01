"""Exact balance rules for generators with distinct width regimes."""

from collections.abc import Callable

from esolangs.tools.arrowqueue import arrowqueue
from esolangs.tools.b_tapemark import b_tapemark
from esolangs.tools.befunge import balance_befunge
from esolangs.tools.brainif import _brainif_tree, brainif
from esolangs.tools.clockwise import clockwise
from esolangs.tools.dig import _dig_grid, dig
from esolangs.tools.fargo import fargo
from esolangs.tools.fish import balance_fish
from esolangs.tools.flowchart import _flowchart_cells, _flowchart_render, flowchart
from esolangs.tools.helpers import _validate_truth_table
from esolangs.tools.inject import inject
from esolangs.tools.streetcode import (
    _streetcode_flat,
    _streetcode_hallway_program,
    _streetcode_rotate,
    _streetcode_shared_programs,
    _streetcode_tree,
    streetcode,
)
from esolangs.tools.super_snusp import balance_super_snusp
from esolangs.tools.thisthat import thisthat
from esolangs.tools.thue import balance_thue
from esolangs.tools.vandevelo import vandevelo
from esolangs.tools.wrap import balance_score


def _width(program: str) -> int:
    """Return the largest rendered row."""
    return max(map(len, program.split("\n")))


def _arrowqueue(table: str, default: str) -> str:
    """Compare the tree and cascades with four, five and six columns."""
    return min(
        default,
        arrowqueue(table, 1),
        arrowqueue(table, 5),
        arrowqueue(table, 6),
        key=balance_score,
    )


def _tapemark(table: str, default: str) -> str:
    """Compare the original grid, its reflection and the narrow staircase."""
    return min(
        default,
        b_tapemark(table, _width(default)),
        b_tapemark(table, 1),
        key=balance_score,
    )


def _brainif(table: str, default: str) -> str:
    """Compare the DAG, full tree, short spellings and small zero-jump tree."""
    wide = _brainif_tree(table, None)
    short = brainif(table, max(1, _width(wide) - 1))
    return min(default, wide, short, brainif(table, 1), key=balance_score)


def _clockwise(table: str, default: str) -> str:
    """Compare the lookup, legacy rotation, lean rotation and two-column route."""
    rotated = clockwise(table, max(1, _width(default) - 1))
    lean = clockwise(table, max(1, _width(rotated) - 1))
    return min(default, rotated, lean, clockwise(table, 1), key=balance_score)


def _dig(table: str, default: str) -> str:
    """Compare alternating, flat, banded and reachable narrow/affine routes."""
    n = _validate_truth_table(table)
    flat = _dig_grid(table, n, None)
    candidates = [default, flat, dig(table, 1), dig(table, 8)]
    if n >= 2:
        banded = _dig_grid(table, n, (n + 3) // 2)
        if _width(banded) < _width(flat):
            candidates.append(banded)
    return min(candidates, key=balance_score)


def _fargo(table: str, default: str) -> str:
    """Compare both order sets and the single definition/factored fallback."""
    # Width requests add orders; their shortest expression cannot grow.
    wide = fargo(table, len(default))
    return min(default, wide, fargo(table, 1), key=balance_score)


def _flowchart(table: str, default: str) -> str:
    """Compare deque lookup, flat tree and the supported stacked fallback."""
    flat = _flowchart_render(_flowchart_cells(table))
    return min(default, flat, flowchart(table, 1), key=balance_score)


def _inject(table: str, default: str) -> str:
    """Compare the normal program and its width-selected banded lookup."""
    return min(default, inject(table, 1), key=balance_score)


def _thisthat(table: str, default: str) -> str:
    """Compare tree, rotation, strip, stream and the one-column XOR route."""
    rotated = thisthat(table, max(1, _width(default) - 1))
    strip = thisthat(table, max(1, _width(rotated) - 1))
    stream = thisthat(table, max(1, _width(strip) - 1))
    return min(default, rotated, strip, stream, thisthat(table, 1), key=balance_score)


def _streetcode(table: str, default: str) -> str:
    """Compare each fit threshold and the seven/nine-column fallback regimes."""
    n = _validate_truth_table(table)
    if n >= 6:
        flat = _streetcode_flat(table, n)
        shapes = [flat, _streetcode_rotate(flat)]
    else:
        tree = _streetcode_tree(table)
        shapes = [
            _streetcode_hallway_program(n, tree),
            *_streetcode_shared_programs(table, n, tree),
        ]
        if n == 5:
            shapes.append(_streetcode_flat(table, n))
    # A requested width changes the shortest fitting shape only when another
    # shape starts fitting; asking at that shape's span also excludes losers.
    candidates = [default, streetcode(table, 1), streetcode(table, 9)]
    candidates.extend(streetcode(table, _width(shape)) for shape in shapes)
    return min(candidates, key=balance_score)


def _vandevelo(table: str, default: str) -> str:
    """Compare the two spellings; any requested width selects the compact one."""
    return min(default, vandevelo(table, 1), key=balance_score)


def _super_snusp(_table: str, default: str) -> str:
    """Balance the already-generated straight line."""
    return balance_super_snusp(default)


BALANCERS: dict[str, Callable[[str, str], str]] = {
    "arrowqueue": _arrowqueue,
    "b_tapemark": _tapemark,
    "befunge": balance_befunge,
    "brainif": _brainif,
    "clockwise": _clockwise,
    "dig": _dig,
    "fargo": _fargo,
    "fish": balance_fish,
    "flowchart": _flowchart,
    "inject": _inject,
    "streetcode": _streetcode,
    "super_snusp": _super_snusp,
    "thisthat": _thisthat,
    "thue": balance_thue,
    "vandevelo": _vandevelo,
}
