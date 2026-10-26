"""Malbolge at seventeen for Hamming-weight classes: a popcount fold.

The positional build folds three bits per digit, so sixteen folded
bits fill the readout and the seventeenth is the stub's.  A table
constant on Hamming-weight classes needs less: the readout has to
name the first sixteen inputs' *weight*, not their positions.  The
first group here reads four inputs with a longer gadget whose trit
0 leaves the inputs' popcount as its digit (five values, one per
weight 0..4, the same for every init triple the cells can hold);
the other four groups keep the positional gadget, so the readout
still determines the last four groups' bits outright and the first
group's weight, hence the sixteen's whole weight.  One cell per
readout -- 20,480 of them, in 6565..59040 -- holds the label for
its weight's class pair, and the stub reads the last input as
before.  The fold contract is the positional build's: choices at
trits 1..3 complete the abstract fold, cell values are searched
over the gadgets' preimages so all fifteen are distinct, and the
readouts are computed state by state, never per row.
"""

from __future__ import annotations

from functools import cache
from itertools import product
from typing import NamedTuple

from esolangs.languages.malbolge.interpreter import _crazy

from .core import (
    _ANSWER,
    _K_CELL,
    _T_LOW,
    _Build,
    _hub_layout,
    _main_planner,
    _merge_code,
    _operand_cells,
    _pointers,
    _stub_builds,
    _table_char,
    _walker,
)
from .digits import (
    _D_FLOOR,
    _D_LABEL,
    _D_SEEDS,
    _D_SWAP_U,
    _D_SWAP_V,
    _GADGET,
    _READ_TRITS,
    _DCells,
    _emit_digit_jump,
    _emit_digit_setup,
    _emit_swap12,
    _helper_cells,
    _hubs,
    _preimages,
    _seed_values,
    _swap12,
)
from .emitter import _Planner
from .isa import _CONSTS, _program, _render, _rot

#: The four-read gadget: the positional gadget's first two read
#: blocks, a suffix folding in the fourth input, and a closing block
#: restoring the digit constants (1, 2) at the trits above 0.  Trit 0
#: maps each weight to a distinct digit: 0:(1, 2), 1:(2, 1),
#: 2:(1, 0), 3:(2, 2), 4:(1, 1).
_S_GADGET = (
    "/",
    "0",
    "K2",
    "0",
    "/",
    "2",
    "0",
    "2",
    "0",
    "K2",
    "0",
    "/",
    "1",
    "2",
    "1",
    "0",
    "2",
    "1",
    "0",
    "0",
    "K2",
    "1",
    "/",
    "0",
    "K2",
    "0",
    "1",
    "1",
    "0",
    "2",
    "K2",
    "1",
    "K0",
    "1",
    "K2",
    "2",
)
#: Gadget per group: the four-read one first, then the positional.
_S_GADGETS = (_S_GADGET, _GADGET, _GADGET, _GADGET, _GADGET)
#: Inputs read per group.
_S_READS = (4, 3, 3, 3, 3)
#: Each group's ``(u, v)`` at trits 1..3, completing the abstract
#: fold (found by search over the gadgets' attainable outputs; the
#: positional trajectory's choices do not complete with a four-read
#: first group, and a four-read last group completes for none).
_S_OUTPUTS = (
    ((2, 2), (2, 2), (2, 2)),
    ((1, 2), (0, 1), (0, 1)),
    ((0, 1), (0, 1), (0, 1)),
    ((1, 2), (2, 1), (1, 2)),
    ((1, 2), (1, 2), (1, 2)),
)


def _s_trit_gadget(cells: tuple[int, ...], read: int) -> tuple[int, int]:
    """Return the four-read gadget's ``(u, v)`` at one trit."""
    c, a = list(cells), 0
    for op in _S_GADGET:
        if op == "/":
            a = read
        elif op[0] == "K":
            a = int(op[1])
        else:
            a = c[int(op)] = _crazy(a, c[int(op)]) % 3
    return c[1], c[2]


@cache
def _s_preimages(read: int) -> dict[tuple[int, int], list[tuple[int, ...]]]:
    """Return the four-read gadget's output preimages at ``read``."""
    preimages: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for cells in reversed(list(product(range(3), repeat=3))):
        preimages.setdefault(_s_trit_gadget(cells, read), []).append(cells)
    return preimages


@cache
def _s_inits() -> tuple[tuple[int, ...], ...]:
    """Return per group the ``g`` values of its three gadget cells.

    Mirrors the positional search over preimages and value options
    (``low``, ``low + 1``, ``low + 81``, ``low + 82`` in 33..126),
    backtracking over the preimages of :data:`_S_OUTPUTS` until all
    fifteen values are distinct -- the cycling assignment the
    positional build uses leaves some of these choices unplaceable.
    """
    per_group = []
    for group, outputs in enumerate(_S_OUTPUTS):
        gadget_pre = _s_preimages if group == 0 else _preimages
        lists = []
        for read, uv in zip(_READ_TRITS, outputs, strict=True):
            if uv not in gadget_pre(read):
                raise AssertionError(f"group {group}: no preimage of {uv}")
            lists.append(gadget_pre(read)[uv])
        per_group.append(lists)

    def assign(
        group: int, used: set[int], acc: tuple[tuple[int, ...], ...]
    ) -> tuple[tuple[int, ...], ...] | None:
        if group == len(_S_OUTPUTS):
            return acc
        for combo in product(*per_group[group]):
            cells = []
            taken = set(used)
            for cell in range(3):
                low = sum(t[cell] * 3**k for k, t in enumerate(combo, 1))
                options = [
                    v
                    for v in (low, low + 1, low + 81, low + 82)
                    if 33 <= v <= 126 and v not in taken
                ]
                if not options:
                    break
                cells.append(options[0])
                taken.add(options[0])
            else:
                got = assign(group + 1, taken, (*acc, tuple(cells)))
                if got is not None:
                    return got
        return None

    inits = assign(0, set(), ())
    if inits is None:
        raise AssertionError("no distinct init values for the popcount fold")
    return inits


@cache
def _s_readouts() -> dict[int, int]:
    """Return each readout cell's weight: cell -> first sixteen's weight.

    Built group by group over the distinct states, as the positional
    build's readouts are; a state reached with two weights would put
    two class pairs in one cell, so that is an error.
    """
    states = {29524: 0}
    for group, init in enumerate(_s_inits()):
        gadget = _S_GADGETS[group]
        following: dict[int, int] = {}
        for s, total in states.items():
            for bits in range(1 << _S_READS[group]):
                reads = iter(
                    48 + ((bits >> k) & 1) for k in reversed(range(_S_READS[group]))
                )
                cells, a = list(init), 0
                for op in gadget:
                    if op == "/":
                        a = next(reads)
                    elif op[0] == "K":
                        a = _CONSTS[int(op[1])]
                    else:
                        a = cells[int(op)] = _crazy(a, cells[int(op)])
                u, v = cells[1], cells[2]
                if group == _D_SWAP_V:
                    v = _swap12(v)
                if group == _D_SWAP_U:
                    u = _swap12(u)
                s2 = _rot(_crazy(_rot(_crazy(v, s)), u))
                weight = total + bits.bit_count()
                if s2 in following and following[s2] != weight:
                    raise AssertionError("one readout, two weights")
                following[s2] = weight
        states = following
    return {_crazy(s, 29524) + 1: total for s, total in states.items()}


class _Symmetric(NamedTuple):
    """The popcount build: code, data, weight per readout, labels."""

    code: dict[int, str]
    data: dict[int, int]
    weights: dict[int, int]
    labels: dict[int, str]


def _s_allocate_cells() -> _DCells:
    """Allocate the working cells, as the positional build does."""
    operands = _operand_cells()
    used = {*_T_LOW, *(cell for cells in operands.values() for cell in cells)}
    helper = _helper_cells(used)
    low, walked = _walker(used, 34), _walker(used)
    gadget = [[low(v) for v in init] for init in _s_inits()]
    s_cell, z_cell = low(), walked()
    # ``p`` under ``A = all-1`` takes 38 to 2 and keeps 2.
    two = low(38)
    # ``p`` under ``A = all-2`` swaps 69 and 48.
    to_48 = walked(69)
    seeds = {lab: walked(g) for lab, g in _D_SEEDS.items()}
    builds: list[_Build] = _stub_builds(_hubs())
    builders = [walked(g) for g, _, _ in builds]
    # Every operand stub shares the middle cell.
    operand = operands["1"][1]
    return _DCells(
        helper,
        gadget,
        s_cell,
        z_cell,
        two,
        to_48,
        seeds,
        builds,
        builders,
        operand,
    )


def _s_emit_groups(main: _Planner, cells: _DCells) -> None:
    """Emit the five groups: the popcount group, then positional ones."""
    helper = cells.helper
    s = cells.s_cell
    for group, cell in enumerate(cells.gadget):
        for op in _S_GADGETS[group]:
            if op == "/":
                main.raw("/")
            elif op[0] == "K":
                main.op("*", helper[_K_CELL[op]])
            else:
                main.op("p", cell[int(op)])
        if group == _D_SWAP_V:
            _emit_swap12(main, cell[2], cells.two, helper)
        main.op("p", s)
        if group == _D_SWAP_U:
            _emit_swap12(main, cell[1], cells.two, helper)
        main.op("*", s)
        main.op("p", cell[1])
        main.op("*", cell[1])
        s = cell[1]


@cache
def _symmetric() -> _Symmetric:
    """Return the popcount build: code, data, weights and labels.

    Raises if any code, stub, hub or data cell collides with a
    readout cell (the positional build's checks, over the 20,480
    readout cells instead of its 32,768).
    """
    weights = _s_readouts()
    cells_of_tables = set(weights)
    cells = _s_allocate_cells()
    _, pointer = _pointers(_D_LABEL, _seed_values().items())
    data, stubs = _hub_layout(_hubs(), cells_of_tables, _D_FLOOR)

    main, _ = _main_planner(data)
    _emit_digit_setup(main, cells)
    _s_emit_groups(main, cells)
    _emit_digit_jump(main, cells, pointer)
    code_end = main.c

    code = _merge_code(
        (main.code, stubs), data, cells_of_tables, code_end, ceiling=_D_FLOOR
    )
    labels = {p - 1: lab for p, lab in _D_LABEL.items()}
    return _Symmetric(code, data, weights, labels)


def _weight_classes(truth_table: str) -> tuple[str, ...] | None:
    """Return the table's class values ``g[0..17]``, or ``None``.

    ``None`` unless every row's answer is determined by the row's
    Hamming weight (the count of its seventeen inputs that are set).
    """
    classes: list[str | None] = [None] * 18
    for row, answer in enumerate(truth_table):
        weight = row.bit_count()
        if classes[weight] is None:
            classes[weight] = answer
        elif classes[weight] != answer:
            return None
    return tuple(classes)  # type: ignore[return-value]


def _symmetric_program(truth_table: str) -> str | None:
    """Return a program for a seventeen-input weight-class table.

    ``None`` when the table is not constant on Hamming-weight
    classes.  Each readout cell takes the label of its weight's
    class pair: the answers for weights ``w`` and ``w + 1``, as the
    stub's input takes the total to one or the other.
    """
    classes = _weight_classes(truth_table)
    if classes is None:
        return None
    code, data, weights, labels = _symmetric()
    program = _program(code)
    program.update(data)
    for cell, weight in weights.items():
        label = _ANSWER[classes[weight] + classes[weight + 1]]
        program[cell] = _table_char(cell, label, labels)
    return _render(program)
