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
trits 1..3 complete the abstract fold, a trit assignment gives
fifteen distinct cell values, and readouts are computed state by state.
"""

from __future__ import annotations

from functools import cache
from typing import NamedTuple

from esolangs.generation.lookup import symmetric_outputs
from esolangs.languages.malbolge.interpreter import _crazy

from .core import (
    _ANSWER,
    _K_CELL,
    _hub_layout,
    _main_planner,
    _merge_code,
    _pointers,
    _table_char,
)
from .digits import (
    _D_FLOOR,
    _D_LABEL,
    _D_SWAP_U,
    _D_SWAP_V,
    _DIGIT,
    _GADGET,
    _allocate_cells,
    _Choice,
    _continuation_cells,
    _d_choice,
    _DCells,
    _emit_digit_jump,
    _emit_digit_setup,
    _emit_swap12,
    _fold,
    _fold_state,
    _full_layout,
    _hubs,
    _seed_values,
)
from .emitter import _Planner
from .isa import _printable_slot, _program, _render


def _weight_gadget() -> tuple[str, ...]:
    """Factor four-bit popcount into crazy operations on three cells."""
    a, b, c = "0", "1", "2"
    # Write C for crazy mod 3 and Kk(t) for C(k, t).
    # From a binary cell, C(x, a) = 1-x and K2 makes it X = 2(1-x).
    first = ("/", a, "K2", a)

    # Start with Y = 1-y in c. Alternating a,c,a computes
    # P = C(Y,X), Q = C(P,Y), R = C(Q,P). Store K2(R) in a.
    # For xy = 00, 01, 10, 11, the pair (K2(R), Q) is respectively
    # (2,2), (1,0), (0,1), (2,0).
    second = ("/", c, a, c, a, "K2", a)

    # Start with Z = 1-z. C(Z,Q) and C(C(Z,Q),Z) fold z into the
    # two-read encoding. Combine the latter with a, then feed that
    # result back through c and b. Substitution of the four pairs
    # above gives (K2(b),c) = (2,2), (0,1), (2,0), (0,2) for
    # weights 0..3. Self-mixing a via C(a,a) makes it binary again.
    mix_third = ("/", b, c, b, a, c, b)
    finish_third = (a, a, "K2", b)

    # Encode D = 2(1-w) as in the first read. B = C(D,b) gives
    # C(B,B) = parity of the total, since b is 2 for even prior
    # weight and 0 for odd. Feed parity through D and c to get
    # V = K2(C(C(parity,D),c)). U = K0(K2(parity)) = 1 + parity.
    fourth = ("/", a, "K2", a)
    parity_and_carry = (b, b, a, c)
    encode_digit = ("K2", b, "K0", b, "K2", c)
    return (
        *first,
        *second,
        *mix_third,
        *finish_third,
        *fourth,
        *parity_and_carry,
        *encode_digit,
    )


_S_GADGET = _weight_gadget()
#: Gadget per group: the four-read one first, then the positional.
_S_GADGETS = (_S_GADGET, _GADGET, _GADGET, _GADGET, _GADGET)
#: Inputs read per group.
_S_READS = (4, 3, 3, 3, 3)


def _s_outputs() -> list[_Choice]:
    """Propagate the fold trits from the four-read group's seed."""
    # On read trit 1 or 2, the four-read circuit sends (2, 1, 2)
    # to (0, 2, 2), giving (u, v) = (2, 2) at all three trits.
    outputs: list[_Choice] = [((2, 2),) * 3]
    state = _fold((1,) * 10, outputs[0], 0)
    for group in range(1, len(_S_GADGETS)):
        assert state is not None, group
        first, middle, last = _d_choice(state, group)
        # Use v3 = 1 where it leaves the fold unchanged and gives
        # enough printable slots. When S3 is 0, crazy(1, 0)
        # equals crazy(2, 0). When S3 is 2, changing v3 to 1 makes
        # the intermediate trit 2, so effective u2 = 1 keeps it 2.
        if state[3] == 2:
            assert group == _D_SWAP_U
            middle = (0, middle[1])  # The swap maps the raw 0 to 1.
        if state[3] in (0, 2):
            # u3 = 0 is attainable with v3 = 1. It folds like u3 = 1:
            # the swap merges them in the first case, and crazy(0, .)
            # merges them under the following zero trit in the second.
            last = (0, 1)
        choice = first, middle, last
        outputs.append(choice)
        state = _fold(state, choice, group)
    assert state == (_DIGIT,) * 10, state
    return outputs


@cache
def _s_inits() -> tuple[tuple[int, ...], ...]:
    """Assign distinct printable words to the five triples of gadget cells."""
    # (2, 1, 2) yields (2, 2) under either read trit of the four-read
    # gadget. The two outer cells share their middle trits and use slots 0, 1.
    trits = [((2, 1, 2),) * 3]
    for first, middle, last in _s_outputs()[1:]:
        u, v = first
        low = (2 - u, 2, v)
        u, _ = middle
        center = (1 - u if u < 2 else u, 1, int(u == 1))
        # When the outside outputs agree, lower the first two high
        # trits to 1 to spread the cells over distinct printable prefixes.
        high = (1, 1, last[1]) if first == last else (2, 2, last[1])
        trits.append((low, center, high))

    slots: dict[int, int] = {}
    inits = []
    for group in trits:
        cells = []
        for t1, t2, t3 in zip(*group, strict=True):
            cells.append(_printable_slot(3 * t1 + 9 * t2 + 27 * t3, slots))
        inits.append(tuple(cells))
    return tuple(inits)


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
                s2 = _fold_state(gadget, init, reads, group, s)
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
    # The five-valued popcount digit becomes the most significant digit.
    # Its three empty low blocks leave room for a contiguous main line.
    weights = {
        (cell - 1) // 9 + (cell - 1) % 9 * 9**4 + 1: weight
        for cell, weight in _s_readouts().items()
    }
    cells_of_tables = set(weights)
    layout = _full_layout(weight_fold=True)
    cells = _allocate_cells(layout, inits=_s_inits())
    _, pointer = _pointers(_D_LABEL, _seed_values(layout).items(), single=True)
    claimed: set[int] = set()
    data, stubs = _hub_layout(
        _hubs(layout),
        cells_of_tables,
        _D_FLOOR,
        cells.builds,
        packed=True,
        claimed=claimed,
    )

    main, _ = _main_planner(data)
    _emit_digit_setup(main, cells)
    _s_emit_groups(main, cells)
    _emit_digit_jump(
        main,
        cells,
        pointer,
        layout,
        swap_cell=_continuation_cells(cells)(),
        rotate_readout=True,
    )
    code = _merge_code(main.code, stubs, data, cells_of_tables, claimed)
    return _Symmetric(code, data, weights)


def _symmetric_program(truth_table: str) -> str | None:
    """Return a program for a seventeen-input weight-class table.

    ``None`` when the table is not constant on Hamming-weight
    classes.  Each readout cell takes the label of its weight's
    class pair: the answers for weights ``w`` and ``w + 1``, as the
    stub's input takes the total to one or the other.
    """
    if len(truth_table) != 1 << 17:
        return None
    classes = symmetric_outputs(truth_table, 17)
    if classes is None:
        return None
    code, data, weights = _symmetric()
    program = _program(code)
    program.update(data)
    for cell, weight in weights.items():
        label = _ANSWER[classes[weight] + classes[weight + 1]]
        program[cell] = _table_char(cell, label)
    return _render(program)
