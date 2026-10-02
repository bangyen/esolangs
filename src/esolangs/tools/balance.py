"""Exact balance rules for generators with distinct width regimes."""

import re
from collections.abc import Callable
from itertools import pairwise
from math import isqrt

from esolangs.raster import Raster
from esolangs.tools._circuit_balance import balance_circuit_diagram
from esolangs.tools._piet_balance import balance as balance_piet
from esolangs.tools.algebraic_programming_language import balance_apl
from esolangs.tools.alight_balance import balance_alight
from esolangs.tools.arrowqueue import arrowqueue
from esolangs.tools.b_tapemark import b_tapemark
from esolangs.tools.back import back
from esolangs.tools.befunge import balance_befunge
from esolangs.tools.brainif import _brainif_tree, brainif
from esolangs.tools.clockwise import clockwise
from esolangs.tools.collatz_multiverse import balance_collatz_multiverse
from esolangs.tools.container import balance_container
from esolangs.tools.crement import crement
from esolangs.tools.dig import _dig_grid, dig
from esolangs.tools.dimensional import dimensional
from esolangs.tools.egl import egl
from esolangs.tools.false import false
from esolangs.tools.fargo import fargo
from esolangs.tools.fish import balance_fish
from esolangs.tools.flowchart import _flowchart_cells, _flowchart_render, flowchart
from esolangs.tools.forbin import forbin
from esolangs.tools.fractran import _PARITY_BINARY, _PARITY_TWO, _PLAIN_MAX, _plain
from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, mark_runs
from esolangs.tools.inject import inject
from esolangs.tools.intercal import balance_intercal
from esolangs.tools.laserfuck import balance_laserfuck
from esolangs.tools.line import balance as balance_line
from esolangs.tools.minifuck import minifuck
from esolangs.tools.minifuck_sim import PAIR
from esolangs.tools.packlang import balance_packlang
from esolangs.tools.parameterized import bitdeque, minsky_swap
from esolangs.tools.qoibl_balance import balance_qoibl
from esolangs.tools.ram0 import ram0
from esolangs.tools.smallfuck import smallfuck, smallfuck_setters
from esolangs.tools.stack import modulous
from esolangs.tools.streetcode import (
    _streetcode_flat,
    _streetcode_hallway_program,
    _streetcode_rotate,
    _streetcode_shared_programs,
    _streetcode_tree,
    streetcode,
)
from esolangs.tools.super_snusp import balance_super_snusp
from esolangs.tools.taglate import balance_taglate
from esolangs.tools.thisthat import thisthat
from esolangs.tools.thue import balance_thue
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.underload import underload
from esolangs.tools.vandevelo import vandevelo
from esolangs.tools.wrap import (
    _BRACKET_LITERAL,
    _DIMENSIONAL_COMMAND,
    _FALSE_COMMAND,
    _MINIFUCK_COMMAND,
    _RUN,
    _bitdeque_tokens,
    _join_tokens,
    balance_score,
)


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


def _back(table: str, default: str) -> str:
    """Compare the reflected tree, descending tree and parity column."""
    descending = back(table, max(1, _width(default) - 1))
    return min(default, descending, back(table, 1), key=balance_score)


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


def _false(table: str, default: str) -> str:
    """Compare ordinary token fits above width one and the alternate zero push."""
    tokens = re.findall(_FALSE_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(
        default, _join_tokens(tokens, width, ""), false(table, 1), key=balance_score
    )


def _forbin(table: str, default: str) -> str:
    """Balance the disjoint-guard spelling below the natural statement span."""
    tokens = forbin(table, 1).split()
    width = balanced_token_width(tokens, " ", maximum=_width(default) - 1)
    return min(default, _join_tokens(tokens, width, " "), key=balance_score)


def _fractran(table: str, default: str) -> str:
    """Balance ordinary fractions, small-root fractions and parity phases."""
    n = _validate_truth_table(table)
    floor = max(map(len, default.split()))
    narrow = _plain(table, n, small_root=True) if n <= _PLAIN_MAX else default
    if max(map(len, narrow.split())) >= floor:
        narrow = default
    regimes: list[tuple[str, int, int | None]] = [(default, floor, None)]
    upper = floor - 1
    lower = 1
    if n == 2 and all(int(bit) == row.bit_count() % 2 for row, bit in enumerate(table)):
        lower = max(map(len, narrow.split()))
        regimes.extend(
            [
                (_PARITY_BINARY, 1, min(3, lower - 1, upper)),
                (_PARITY_TWO, 4, min(lower - 1, upper)),
            ]
        )
    regimes.append((narrow, lower, upper))
    candidates = [default]
    for program, lower, maximum in regimes:
        if maximum is not None and lower > maximum:
            continue
        tokens = program.split()
        width = balanced_token_width(tokens, " ", minimum=lower, maximum=maximum)
        candidates.append(_join_tokens(tokens, width, " "))
    return min(candidates, key=balance_score)


def _ram0(table: str, default: str) -> str:
    """Compare the width-one NAND form and ordinary operand row fits."""
    tokens = default.split()
    width = balanced_token_width(tokens, " ", minimum=2)
    return min(
        default, _join_tokens(tokens, width, " "), ram0(table, 1), key=balance_score
    )


def _bitdeque(table: str, default: str) -> str:
    """Balance the eleven-cell and short endpoint loads in their width regimes."""
    normal = _bitdeque_tokens(default)
    short = _bitdeque_tokens(bitdeque(table, 1))
    normal_width = balanced_token_width(normal, " ", minimum=11)
    short_width = balanced_token_width(short, " ", maximum=10)
    return min(
        default,
        _join_tokens(normal, normal_width, " "),
        _join_tokens(short, short_width, " "),
        key=balance_score,
    )


def _minsky_swap(table: str, default: str) -> str:
    """Compare compact source and the three line-oriented setter regimes."""
    return min(
        default,
        minsky_swap(table, 1),
        minsky_swap(table, 10),
        minsky_swap(table, 15),
        key=balance_score,
    )


def _crement(table: str, default: str) -> str:
    """Compare preserved instructions and the two field-wrapping regimes."""
    candidates = [default]
    upper = _width(default) - 1
    if upper >= 6:
        normal = crement(table, upper)
        candidates.append(normal)
        folded_upper = min(upper, _width(normal) - 1)
        if folded_upper >= 6:
            width = balanced_token_width(
                normal.split(), " ", minimum=6, maximum=folded_upper
            )
            candidates.append(crement(table, width))
    short = crement(table, 1)
    width = balanced_token_width(short.split(), " ", maximum=5)
    candidates.append(crement(table, width))
    return min(candidates, key=balance_score)


def _dimensional(table: str, default: str) -> str:
    """Balance index tokens above width one and compare bare leaf coordinates."""
    tokens = re.findall(_DIMENSIONAL_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(
        default, dimensional(table, width), dimensional(table, 1), key=balance_score
    )


def _egl(table: str, default: str) -> str:
    """Balance character folds above the header and its fixed-width regime."""
    header, _, body = default.partition(":")
    floor = len(header) + 1
    square = max(floor, isqrt(len(default) - 1) + 1)
    crossing = len(body) // (floor - 1)
    widths = {
        square,
        min(max(1, crossing), floor - 1),
        min(max(1, crossing + 1), floor - 1),
    }
    return min(default, *(egl(table, width) for width in widths), key=balance_score)


def _smallfuck(table: str, default: str) -> str:
    """Balance four-character setters and the one-character narrow setters."""
    n = _validate_truth_table(table)
    candidates = [default]
    for source, minimum, maximum in ((default, 4, None), (smallfuck(table, 3), 1, 3)):
        clean = source.replace("\n", "")
        marked = mark_runs(clean, TEMPLATE_CHAR, smallfuck_setters(clean, n))
        tokens = re.findall(f"{_RUN}|[\\s\\S]", marked)
        width = balanced_token_width(tokens, minimum=minimum, maximum=maximum)
        candidates.append(smallfuck(table, width))
    return min(candidates, key=balance_score)


def _underload(table: str, default: str) -> str:
    """Balance five-character selectors, the width-four form and swap bits."""
    normal = re.findall(r"\${5}|\(\)!|\([01]\)|.", default)
    width = balanced_token_width(normal, minimum=5)
    short = underload(table, 3).replace("\n", "")
    tokens = re.findall(r"\$|\(\)!|\([01]\)|.", short)
    short_width = balanced_token_width(tokens, maximum=3)
    return min(
        default,
        underload(table, width),
        underload(table, 4),
        underload(table, short_width),
        key=balance_score,
    )


def _minifuck(table: str, default: str) -> str:
    """Balance ordinary and paired skip tokens, including the parity column."""
    n = _validate_truth_table(table)

    def tokens(program: str) -> list[str]:
        marked = mark_runs(program.replace("\n", ""), TEMPLATE_CHAR, (PAIR,) * n)
        return re.findall(f"{_RUN}|{_MINIFUCK_COMMAND}", marked)

    normal = tokens(default)
    floor = max(map(len, normal))
    width = balanced_token_width(normal, minimum=floor)
    candidates = [default, minifuck(table, width), minifuck(table, 1)]
    parity = all(
        int(bit) == ((row.bit_count() ^ int(table[0])) & 1)
        for row, bit in enumerate(table)
    )
    lower = 4 if parity else 1
    if lower < floor:
        # Below the ordinary token floor, paired tokens win throughout the
        # regime exactly when their own floor is smaller; otherwise the
        # generator retains the ordinary tokens throughout it.
        narrow = tokens(minifuck(table, lower))
        width = balanced_token_width(narrow, minimum=lower, maximum=floor - 1)
        candidates.append(minifuck(table, width))
    return min(candidates, key=balance_score)


def _modulous(table: str, default: str) -> str:
    """Balance bracket atoms and literal chunks at quotient and row fits."""
    atoms = re.findall(_BRACKET_LITERAL, default)
    floor = max(map(len, atoms))
    width = balanced_token_width(atoms, minimum=floor)
    candidates = [default, modulous(table, width)]
    numeric = modulous(table, 1).split()
    width = balanced_token_width(numeric, " ", maximum=3)
    candidates.append(modulous(table, width))
    # Below nine columns the three-word push prefix cannot share a row.
    candidates.extend(modulous(table, width) for width in range(4, 9))
    size = len(table)
    whole = modulous(table, size + 3).split()
    width = balanced_token_width(whole, " ", minimum=size + 3, maximum=floor - 1)
    candidates.append(modulous(table, width))
    suffix = re.findall(r'"[^"]*"\]|[A-Z]+|\d+|[^\s]', default[size + 12 :])
    lengths = list(map(len, suffix))
    fits = set()
    for start in range(len(lengths)):
        span = -1
        for length in lengths[start:]:
            span += length + 1
            fits.add(span - 3)
    fixed = [1, 3, 3, 0, 1, 3, 3]
    partial_fits = {
        sum(fixed[start:stop]) + stop - start - 1
        for start in range(4)
        for stop in range(4, 8)
    }
    quotients = {size}
    for divisor in range(1, isqrt(size - 1) + 1):
        quotients.update((divisor + 1, (size - 1) // divisor + 1))

    def height(parts: list[int], columns: int) -> int:
        rows, used = 1, 0
        for length in parts:
            if used and used + 1 + length > columns:
                rows += 1
                used = length
            else:
                used += length + bool(used)
        return rows

    best: tuple[int, int, int] | None = None
    for count in quotients:
        lower = max(6, (size + count - 1) // count)
        upper = min(size - 1, (size - 1) // (count - 1))
        if lower > upper:
            continue
        events = {lower, upper + 1}
        events.update(fit for fit in fits if lower < fit <= upper)
        events.update(
            point
            for extra in partial_fits
            if lower < (point := (size + extra + count - 1) // count) <= upper
        )
        boundaries = sorted(events)
        for start, stop in pairwise(boundaries):
            partial = size - (count - 1) * start
            rows = (
                height([1, 3, 3, partial + 3, 1, 3, 3], start + 3)
                + 2 * count
                - 3
                + height(lengths, start + 3)
            )
            columns = min(max(rows, start + 3), stop + 2)
            score = (abs(columns - rows), size + 14 * count, columns)
            if best is None or score < best:
                best = score
    if best is not None:
        candidates.append(modulous(table, best[2]))
    return min(candidates, key=balance_score)


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


BALANCERS: dict[str, Callable[[str, str], str] | Callable[[str, Raster], Raster]] = {
    "line": balance_line,
    "piet": balance_piet,
    "algebraic_programming_language": balance_apl,
    "alight": balance_alight,
    "arrowqueue": _arrowqueue,
    "back": _back,
    "b_tapemark": _tapemark,
    "befunge": balance_befunge,
    "bitdeque": _bitdeque,
    "brainif": _brainif,
    "circuit_diagram": balance_circuit_diagram,
    "clockwise": _clockwise,
    "collatz_multiverse": balance_collatz_multiverse,
    "container": balance_container,
    "crement": _crement,
    "dimensional": _dimensional,
    "egl": _egl,
    "smallfuck": _smallfuck,
    "underload": _underload,
    "dig": _dig,
    "fargo": _fargo,
    "false": _false,
    "fish": balance_fish,
    "flowchart": _flowchart,
    "forbin": _forbin,
    "fractran": _fractran,
    "inject": _inject,
    "intercal": balance_intercal,
    "laserfuck": balance_laserfuck,
    "minifuck": _minifuck,
    "minsky_swap": _minsky_swap,
    "modulous": _modulous,
    "packlang": balance_packlang,
    "qoibl": balance_qoibl,
    "ram0": _ram0,
    "streetcode": _streetcode,
    "super_snusp": _super_snusp,
    "taglate": balance_taglate,
    "thisthat": _thisthat,
    "thue": balance_thue,
    "vandevelo": _vandevelo,
}
