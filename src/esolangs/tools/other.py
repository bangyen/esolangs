"""Boolean-function generators for languages in the ``other`` category."""

# Every language whose construction is large enough to read on its own owns
# a file; what is left here is three_x and bit_tilde, which are not.  The
# rest are re-exported so this module stays the import site the package and
# tests already use.

from collections.abc import Callable
from itertools import pairwise

from esolangs.tools.clockwise import clockwise as clockwise

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.container import (
    _container_packed as _container_packed,
)
from esolangs.tools.container import container as container
from esolangs.tools.flowchart import (
    _flowchart_cells as _flowchart_cells,
)
from esolangs.tools.flowchart import (
    _flowchart_render as _flowchart_render,
)
from esolangs.tools.flowchart import (
    _flowchart_stacked as _flowchart_stacked,
)
from esolangs.tools.flowchart import flowchart as flowchart
from esolangs.tools.forbin import (
    _FORBIN_RESERVED as _FORBIN_RESERVED,
)
from esolangs.tools.forbin import (
    _forbin_name as _forbin_name,
)
from esolangs.tools.forbin import (
    _forbin_ordered as _forbin_ordered,
)
from esolangs.tools.forbin import forbin as forbin
from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    essential_inputs,
    read_at,
)
from esolangs.tools.laserfuck import laserfuck as laserfuck
from esolangs.tools.streetcode import streetcode as streetcode
from esolangs.tools.taglate import taglate as taglate

__all__ = [
    "bit_tilde",
    "clockwise",
    "container",
    "forbin",
    "laserfuck",
    "streetcode",
    "taglate",
    "three_x",
]


# Closed-form 3x constant encodings.  Every integer is built from the literal
# 3 with the ``x`` op (which replaces the top three items ``a, b, c``, c on
# top, with ``(c-b)//a``).  The three base-3 digits are:
_ZERO = "333x"  # (3-3)//3 = 0


_ONE = "3333x3x"  # (3-0)//3 = 1


_TWO = _ONE + _ONE + "3x"  # (3-1)//1 = 2


# From [v], ``push X # push Y x`` leaves [(Y-v)//X], so with X=-1/3 and
# Y=-d/3 it maps v -> (-d/3 - v)/(-1/3) = 3v + d.  These are the two fixed
# rationals (and the d=0 case, which is just 0):
_NEG_THIRD = "3" + _ONE + _ZERO + "x"  # (0-1)//3 = -1/3


_NEG_TWO_THIRDS = "33" + _ONE + "x"  # (1-3)//3 = -2/3


_DIGIT = (_ZERO, _ONE, _TWO)


_NEG_DIGIT = (_ZERO, _NEG_THIRD, _NEG_TWO_THIRDS)


def _const(n: int) -> str:
    """3x code pushing ``n`` on a clean stack, for any integer ``n``.

    Base-3 digits, most significant first, each applying ``v -> 3v + d``
    via one ``x`` (see ``_NEG_THIRD``): ``O(log_3 n)`` length.
    """
    if n <= 2:
        return _DIGIT[n]
    digits = []
    while n:
        digits.append(n % 3)
        n //= 3
    prog = _DIGIT[digits[-1]]
    for d in reversed(digits[:-1]):
        prog += _NEG_THIRD + "#" + _NEG_DIGIT[d] + "x"
    return prog


def three_x(truth_table: str) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).

    Each ``?`` stores one bit in a variable; a ``( ... )`` guard pops into
    a trash variable (0), the body stores the entry into the result
    variable (3), a sentinel zero exits.  The result defaults to the
    majority value, so only differing rows get an override block.

    **The tree splits in whichever order emits the shortest program**
    (:func:`~esolangs.tools.helpers.best_input_order`), spelled in the
    store targets: stream input ``i`` is stored into the name tested at
    depth ``perm.index(i)``.  The read block's length never changes, so
    the screen figure is exact: 4.5% at n=3 (146 of 256 tables), 5.4%
    at n=4 -- unlike Circlefuck (over-estimate) or S*bleq/BrainIf
    (under-estimate).
    """
    return best_input_order(truth_table, _three_x_ordered)


def _three_x_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's 3x program; see :func:`three_x`."""
    n = _validate_truth_table(truth_table)

    # Variable allocation: var 0 is the loop-trash (its constant, 333x, is
    # short and emitted twice per guard), var 3 is the result (its constant
    # is the single char `3`, emitted once per table entry), and the inputs
    # live in the cheapest remaining names by actual constant length (the
    # base-3 encodings are non-monotonic: 15 is cheaper than 13).  Deep tree
    # levels occur exponentially more often in the emitted program, so the
    # cheapest name goes deepest.  Reversing the length order makes the name
    # cost a geometric sum rather than repeating the longest name at half the
    # nodes.  Which input lands at which depth is what ``best_input_order``
    # searches over.
    trash = _const(0) + "#v"  # pop the stack top into variable 0
    result = 3
    used = {0, 3}
    input_vars = sorted(
        (v for v in range(3 + n) if v not in used),
        key=lambda v: len(_const(v)),
    )[:n][::-1]

    def store(var: int) -> str:
        return _const(var) + "#v"  # var = stack top, stack ends empty

    def read(var: int) -> str:
        return _const(var) + "^"

    def not_bit() -> str:
        return _ONE + "#" + _ONE + "x"  # from [b] leave [1-b]

    # A guard's body is laid down between its two halves, into one flat
    # piece list rather than a string rebuilt per level.
    pieces: list[str] = []

    def guard(i: int, body: Callable[[], None]) -> None:
        """If bit i is 1, run ``body``; leaves the stack balanced."""
        pieces.append(read(i) + "(" + trash)
        body()
        pieces.append(_ZERO + ")" + trash)

    def guard_not(i: int, body: Callable[[], None]) -> None:
        """If bit i is 0, run ``body``; leaves the stack balanced."""
        pieces.append(read(i) + not_bit() + "(" + trash)
        body()
        pieces.append(_ZERO + ")" + trash)

    # A table that ignores some of its inputs is a smaller table, and this
    # tree does not fold it away on its own: it prunes only the rows that
    # *differ from the default*, which for a one-dependency table is still
    # half of them, each carrying a full-depth guard chain.  Reducing to the
    # essential inputs collapses those to one guard.  The reads stay in
    # stream order -- every input is still ``?``-read and stored, which is
    # the interface -- and an ignored one lands in a variable the tree never
    # reads.
    essential = essential_inputs(truth_table, n) or [0]
    if len(essential) < n:
        table = read_at(truth_table, essential, n)
        width = len(essential)
    else:
        table, width = truth_table, n

    # Reads run in stream order; only the store target moves.  Stream input
    # ``i`` goes into the name the tree tests at depth ``perm.index(i)``.
    # A reduced tree tests only ``width`` names, so the ignored inputs take
    # the leftover ones; ``perm`` is a permutation of all ``n`` either way.
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    pieces.append("".join("?" + store(input_vars[depth_of[i]]) for i in range(n)))

    # Default the result to the majority value so only the minority rows
    # need an override block (combos matching the default are skipped).
    default = "1" if table.count("1") >= table.count("0") else "0"
    pieces.append((_ONE if default == "1" else _ZERO) + store(result))

    # One decision tree instead of an independent guard chain per differing
    # combo: rows that share a bit prefix share the guards for that prefix,
    # amortizing the ~19-char guard scaffolding across them.  Each guard
    # leaves the stack balanced, so both branches concatenate safely inside
    # their parent's body, and whole subtrees that match the default are
    # pruned.
    def override(combo: int) -> str:
        return (_ONE if table[combo] == "1" else _ZERO) + store(result)

    # ``truth_table`` is already the *permuted* table when the reorder
    # wrapper calls this, so ``essential`` is in the tree's own coordinates:
    # entry ``s`` names the depth the unreduced tree would have tested, and
    # the bit for that depth sits in ``input_vars[essential[s]]``.  Going
    # back through ``depth_of`` would mix stream and tree coordinates, which
    # agrees only when the essential set is contiguous from 0 -- gapped sets
    # like ``[0, 2]`` are exactly where that mismatch shows up.
    slot_var = [input_vars[s] for s in essential]

    # Rows split most-significant-first, so a subtree is a row span, and a
    # prefix count of the differing rows says in O(1) whether it is pruned:
    # O(2**n) over the tree.
    differing = [0]
    for entry in table:
        differing.append(differing[-1] + (entry != default))

    def build(lo: int, hi: int, depth: int) -> None:
        if differing[lo] == differing[hi]:
            return
        if depth == width:
            pieces.append(override(lo))  # rows are pruned, so it differs from default
            return
        mid = (lo + hi) // 2
        if differing[mid] != differing[hi]:
            guard(slot_var[depth], lambda: build(mid, hi, depth + 1))
        if differing[lo] != differing[mid]:
            guard_not(slot_var[depth], lambda: build(lo, mid, depth + 1))

    build(0, 2**width, 0)

    pieces.append(read(result) + "!")
    return "".join(pieces)


def bit_tilde(truth_table: str) -> str:
    """Build a bit~ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Each node copies its input into two
    indicators, complements one, and uses both as one-shot ``{``/``}``
    branch loops that clear themselves; deep levels sit nearest the input
    area so the pointer walks sum geometrically and the source is O(T).
    """
    n = _validate_truth_table(truth_table)

    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)

    prog: list[str] = []
    pos = 0

    def move(dst: int) -> None:
        nonlocal pos
        while pos < dst:
            prog.append(">")
            pos += 1
        while pos > dst:
            prog.append("<")
            pos -= 1

    def copy2(src: int, d1: int, d2: int) -> None:
        """Copy ``src`` to ``d1`` and ``d2``, zeroing ``src``."""
        nonlocal pos
        move(src)
        prog.append("{")
        move(d1)
        prog.append("~")
        move(d2)
        prog.append("~")
        move(src)
        prog.append("~")
        prog.append("}")

    for i in range(n):
        if i:
            move(8 * i)
        prog.append(")")
        pos = 8 * i

    base = 8 * n
    result = base

    def set_result() -> None:
        nonlocal pos
        move(result)
        prog.append("{ ~ } ~")
        pos = result

    def clear(cell: int) -> None:
        nonlocal pos
        move(cell)
        prog.append("{~}")
        pos = cell

    changes = [0]
    for previous, current in pairwise(table):
        changes.append(changes[-1] + (previous != current))

    def node(start: int, end: int, depth: int) -> None:
        nonlocal pos
        if changes[start] == changes[end - 1]:
            if table[start] == "1":
                set_result()
            return
        half = (start + end) // 2
        slot = width - 1 - depth
        zero = base + 1 + 3 * slot
        one = zero + 1
        temp = zero + 2
        for cell in (zero, one, temp):
            clear(cell)
        source = 8 * used[depth] + 7
        copy2(source, one, temp)
        copy2(temp, source, zero)
        move(zero)
        prog.append("~{")
        pos = zero
        node(start, half, depth + 1)
        move(zero)
        prog.append("~}")
        pos = zero
        move(one)
        prog.append("{")
        pos = one
        node(half, end, depth + 1)
        move(one)
        prog.append("~}")
        pos = one

    node(0, 1 << width, 0)

    # Cell 7 still holds input 0 because tree copies preserve every source.
    clear(7)
    move(result)
    prog.append("{")
    move(7)
    prog.append("~")
    move(result)
    prog.append("~")
    prog.append("}")
    pos = result
    move(0)
    prog.append("(")
    return "".join(prog)
