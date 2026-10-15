"""Thirteen-input tier: the twelve-input core with input thirteen read by the stub."""

from __future__ import annotations

from functools import cache
from typing import NamedTuple

from .cascade import (
    _C_INITS,
    _NEXT,
    _build_constants,
    _decoder_entry,
    _emit_fold,
    _ops,
)
from .core import (
    _T_FLOOR,
    _T_HELPERS,
    _T_HUB_CELLS,
    _T_LABELS,
    _T_LOW,
    _T_SEEDS,
    _main_planner,
    _merge_code,
    _n_hub_pass,
    _options_of,
    _Planner,
    _pointers,
    _prime,
    _seed_label_chains,
    _t_hubs,
    _t_jump,
    _turn_hubs,
    _walker,
)
from .isa import (
    _apply,
    _g,
    _rot,
)
from .wide import (
    _W_PATHS,
    _W_SELECT,
    _W_SELECT_OPS,
    _wide,
)

# ---------------------------------------------------------------------------
# Thirteen inputs: the twelve-input core, with input thirteen read by the stub.
#
# The core's table cells are kept, one per twelve-bit prefix, and each cell's
# label now names one of four answers as a function of the last input -- 0,
# 1, ``x`` or ``not x`` -- or ``N``.  Five labels need five characters of the
# eight at every residue, which the ``[P0, P1]`` pairs and NEXT runs cannot
# afford; so every label is a single pointer cell, and the decoder takes one
# more hop: ``j`` to the table cell, ``j`` to its pointer cell ``T + 1``, ``j``
# to the *hub* ``V + 1`` the pointer names, ``i`` through the hub.  ``d`` is
# then ``V + 2`` whatever the row, so a stub may read the source characters
# after its hub.  The pointer region holds nothing but labels and the mixer:
# helpers, selectors and seeds move to the walked cells 128..419, reached by
# walking up from a ``j``; navigation is a shortest path over ``o`` and ``j``
# through every cell whose value is known.
#
# A class's pointer cells are filled by one chained ``p`` over all-1 cells
# from a seed ``s`` (a walked cell rotated ``k`` times), so they hold ``s`` and
# ``f(s)`` alternately, ``f`` swapping 0/1 trits; each value owns a hub.  A hub
# holds a source character rotated until it names a free stub; the N hubs hold
# all-1 twice and reach the decoder at ``_T_DECODER`` (29525) as before.
_THIRTEEN_N = 13
#: The decoder address the twelve/thirteen-input builds jump to; the N hubs
#: hold one less.  Hub placement keeps a guard band around it clear.
_T_DECODER = 29525
_T_DECODER_AVOID = range(_T_DECODER - 5, _T_DECODER + 275)


class _Layout(NamedTuple):
    """Thirteen inputs' build: code, data, the core's ``level``/``tables``, labels."""

    code: dict[int, str]
    data: dict[int, int]
    level: tuple[tuple[int, ...], ...]
    tables: tuple[tuple[tuple[int, ...], ...], ...]
    labels: dict[int, str]


def _t_place(
    values: dict[int, int],
    label: dict[int, str],
    avoid: set[int],
    hub_cells: dict[str, int | tuple[int, ...]] = _T_HUB_CELLS,
) -> tuple[dict[int, int], dict[int, str], dict[int, int]]:
    """Place the hubs of thirteen and fourteen inputs (see :func:`_t_hubs`)."""
    return _t_hubs(
        values,
        label,
        avoid,
        hub_cells=hub_cells,
        options_of=_options_of(values),
        floor=_T_FLOOR,
    )


@cache
def _thirteen() -> _Layout:
    """Return ``(code, data, level, tables, labels)`` for thirteen inputs.

    ``level`` and ``tables`` are the twelve-input core's, indexed by the
    twelfth input and the eleven-bit prefix.  Raises if any code, stub, hub
    or data cell collides with another or with a table cell.
    """
    _, level, tables, _ = _wide()
    cells_of_tables = set(tables[0][0] + tables[0][1])
    for x in (0, 1):
        cells_of_tables.update(h for row, h in enumerate(tables[1][x]) if level[x][row])

    used = set(_T_LOW)
    helper = {"all1": _T_LOW[0], "all2": _T_LOW[1]}

    walked = _walker(used)
    for name, value in _T_HELPERS.items():
        helper[name] = walked(value)
    select = [walked(_g(a)) for a in _W_SELECT]
    seeds = {lab: walked(value) for lab, (value, _) in _T_SEEDS.items()}
    label = {t + 34: lab for t, lab in enumerate(_T_LABELS) if lab != "-"}
    mix = [
        next(a for a in range(34, 128) if _g(a) == v and a not in label)
        for v in _C_INITS
    ]
    values, pointer = _pointers(label, _seed_values(seeds, _T_SEEDS))
    data, stubs, hub_turns = _t_place(
        values, label, cells_of_tables | set(_T_DECODER_AVOID)
    )

    cell = [*mix, helper["z0"], helper["all1"], helper["all2"]]
    main, mem = _main_planner(data)
    # all-2 is one more ``p`` with ``A = all-2`` (``crazy(all-2, all-1)``).
    _build_constants(main, helper)
    _prime(main, helper, (helper["all1"], helper["all2"], *sorted(label)))
    _seed_label_chains(
        main,
        helper,
        {lab: " ".join(["rot"] * turns) for lab, (_, turns) in _T_SEEDS.items()},
        seeds,
        label,
    )
    main.op("*", helper["z1"])
    for v in sorted(pointer):
        if label[pointer[v]] == "N":
            _n_hub_pass(main, pointer[v], v)
    _turn_hubs(main, pointer, hub_turns)
    _emit_fold(main, cell)
    main.raw("/")
    _ops(main, select, _W_SELECT_OPS)
    main.goto(select[0])
    main.raw("i")
    code_end = main.c

    targets = []
    for x in (0, 1):
        state = [_g(a) for a in _W_SELECT]
        _apply(state, 48 + x, _W_SELECT_OPS)
        targets.append(state[:2])
    parts = [main.code]
    for x in (0, 1):
        parts.append(_thirteen_path(0, x, targets, select, cell, helper, mem, data))
    dec = _Planner(_NEXT + 1, 0, mem, data)
    _decoder_entry(dec, _NEXT + 1)
    dec.goto(select[1])
    dec.raw("i")
    parts.append(dec.code)
    for x in (0, 1):
        parts.append(_thirteen_path(1, x, targets, select, cell, helper, mem, data))

    code = _merge_code(
        (*parts, stubs), data, cells_of_tables, code_end, ceiling=_T_FLOOR
    )
    labels = {p - 1: lab for p, lab in label.items()}
    return _Layout(code, data, level, tables, labels)


def _seed_values(
    seeds: dict[str, int], rotations: dict[str, tuple[int, int]]
) -> list[tuple[str, int]]:
    """Return each label's first pointer value: its seed cell rotated ``k`` times."""
    out = []
    for lab, (_, turns) in rotations.items():
        a = _g(seeds[lab])
        for _ in range(turns):
            a = _rot(a)
        out.append((lab, a))
    return out


def _thirteen_path(
    lvl: int,
    x: int,
    targets: list[list[int]],
    select: list[int],
    cell: list[int],
    helper: dict[str, int],
    mem: dict[int, int | None],
    data: dict[int, int],
) -> dict[int, str]:
    """Emit one twelve/thirteen-input level path, never walked, only jumped to.

    Level 1 left ``a1`` at 48: two rounds give 69 and then 48 again.
    """
    path = _Planner(targets[x][lvl] + 1, select[lvl] + 1, mem, data)
    spec = _W_PATHS[lvl][x]
    _ops(path, cell, spec.ops)
    for _ in range(1 if lvl == 0 else 2):
        path.op("*", helper["all2"])
        path.op("p", helper["a1"])
    _t_jump(path, cell[spec.readout], spec.offset)
    return path.code
