"""Boolean-function generators for register-based languages."""

from itertools import pairwise

# Polynomial, Dig and AddSubJump each own a file: their constructions dwarf
# the rest of the category, and this module stays the import site the package
# and tests already use.
from esolangs.tools.addsubjump import addsubjump as addsubjump

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach it
# by this name, so the pieces are re-exported in the ``x as x`` form.
from esolangs.tools.dig import (
    _DIG_BAND as _DIG_BAND,
)
from esolangs.tools.dig import (
    _DIG_BRANCH as _DIG_BRANCH,
)
from esolangs.tools.dig import (
    _DIG_RETURN as _DIG_RETURN,
)
from esolangs.tools.dig import (
    _DIG_STRIDE as _DIG_STRIDE,
)
from esolangs.tools.dig import (
    _dig_grid as _dig_grid,
)
from esolangs.tools.dig import dig as dig
from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _cm_constants,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.tools.polynomial import (
    _POLYNOMIAL_MAX_INSTRS as _POLYNOMIAL_MAX_INSTRS,
)
from esolangs.tools.polynomial import (
    _POLYNOMIAL_SCREEN_SLACK as _POLYNOMIAL_SCREEN_SLACK,
)
from esolangs.tools.polynomial import (
    _polynomial_assemble as _polynomial_assemble,
)
from esolangs.tools.polynomial import (
    _polynomial_dag as _polynomial_dag,
)
from esolangs.tools.polynomial import (
    _polynomial_drained_dag as _polynomial_drained_dag,
)
from esolangs.tools.polynomial import (
    _polynomial_drained_dag_cost as _polynomial_drained_dag_cost,
)
from esolangs.tools.polynomial import (
    _polynomial_hybrid as _polynomial_hybrid,
)
from esolangs.tools.polynomial import (
    _polynomial_hybrid_cost as _polynomial_hybrid_cost,
)
from esolangs.tools.polynomial import _polynomial_states
from esolangs.tools.polynomial import polynomial as polynomial


def decleq(truth_table: str) -> str:
    """Build a Decleq program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Decleq's only arithmetic is ``b = a - 1`` with a ``<= 0`` jump, so each
    input byte (48/49) is normalized to 1/2 by a 47-step decrement chain,
    which makes ``cell cell c`` a branch: a ``0`` bit (1) decrements to 0 and
    jumps to ``c``, a ``1`` bit (2) falls through.

    A pure decision tree is ``Theta(T log T)`` here whatever it folds: its
    ``T - 1`` branches name ``T - 1`` distinct absolute targets, whose digits
    sum to that.  So the tree stops ``k`` levels short, ``2**k >= 2 n``, and
    each of its leaves is a ``2**k``-cell table of ``48``/``49`` indexed by
    the last ``k`` inputs.  The index is computed once, before the tree: a
    counter starts at ``2**k`` and each low input that is one takes its
    weight off it in an unrolled run of decrements, ``2**k - 1`` cells in
    all.  A leaf then decrements the address operand of its own output
    instruction that many times short of the table's top, lands on row
    ``index``, prints it and halts.  Size is O(T): the tables are ``T``
    three-character cells, and the ``T / 2**k <= T / (2 n)`` leaves and
    branches carry O(n) digits each.  Execution is ``O(2**k) = O(n)``.

    A subtree whose rows all agree becomes a one-instruction leaf that jumps
    to a shared print-and-halt gadget at a fixed low address rather than
    branching on bits that cannot change the answer.  Rows split
    most-significant-first, so a subtree is a contiguous run and
    ``11110000`` folds to a single branch -- unlike the generators that
    split the other way, where that table folds nothing.

    Every input is still read, so the program consumes exactly ``n`` input
    bytes.  But an ignored input never controls a non-folded branch and
    never moves the index, so it needs no 47-step normalization chain: the
    fixed cost is ``47 * len(essential_inputs)`` rather than ``47 * n``.

    Layout: cell 0 jumps over two print-and-halt gadgets (``-2 K 0`` then
    ``0 0 END``), the constants 48 and 49, the counter and the ``n`` read
    cells; the code follows on the next multiple of three.  Cell 0 is the
    decrement source of every unconditional jump -- it only ever goes
    further negative -- and ``END`` is one past the last cell, the smallest
    address that halts.
    """
    n = _validate_truth_table(truth_table)
    # The table depth: the fewest low inputs whose lookup pays for the
    # tree above it, ``2**k >= 2 n``, and never more inputs than there are.
    k = min(n, (2 * n - 1).bit_length())
    span = 2**k

    # ``changes[r]`` counts the value changes before row ``r``, so a run is
    # constant iff its two ends agree; a slice-and-set per node would cost
    # ``Theta(n T)`` over the tree.
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))

    def constant(row: int, width: int) -> bool:
        """Whether the ``width`` rows starting at ``row`` all agree."""
        return changes[row] == changes[row + width - 1]

    # Only the inputs the table depends on need the normalization chain;
    # see the docstring for why an ignored one still reads but never routes.
    essential = set(essential_inputs(truth_table, n))

    # Fixed low addresses; a leaf reaches a gadget by ``0 0 gadget``.
    out_zero, halt, out_one = 3, 6, 9
    k48, k49, counter = 15, 16, 17
    read_cells = [18 + i for i in range(n)]
    # The code starts on a multiple of three so wrap_grid's columns are the
    # operand columns; at most two pad cells.
    code = -(-(18 + n) // 3) * 3

    mem: list[int] = [0, 0, code, -2, k48, 0, 0, 0, 0, -2, k49, 0, 0, 0, 0]
    mem += [_ASCII_ZERO, _ASCII_ONE, span] + [0] * (code - 18)
    ends = [halt + 2, halt + 8]  # the two END operands, patched last

    def emit(a: int, b: int, c: int) -> None:
        mem.extend([a, b, c])

    def pc() -> int:
        return len(mem)

    def patch(addr: int, c: int) -> None:
        mem[addr + 2] = c

    # A read falls through and these decrements never reach 0: target 0.
    for rc in read_cells:
        emit(-1, rc, 0)
    for i, rc in enumerate(read_cells):
        if i not in essential:
            continue
        for _ in range(47):
            emit(rc, rc, 0)

    # Index: the low ``k`` inputs, each one taking its weight off the
    # counter.  A zero (1) decrements to 0 and jumps the run; a one (2)
    # falls into it.
    for i in range(n - k, n):
        if i not in essential:
            continue
        rc = read_cells[i]
        weight = 2 ** (n - 1 - i)
        emit(rc, rc, pc() + 3 * (weight + 1))
        for _ in range(weight):
            emit(counter, counter, 0)

    def leaf(row: int) -> None:
        """Print row ``counter`` of the table at ``row``, then halt.

        ``counter`` holds ``2**k - index``; the loop runs it down and takes
        one off the output's address operand per pass but the last, so the
        operand ends ``index`` above the table's base.
        """
        loop = pc()
        out = loop + 9
        emit(counter, counter, out)
        emit(out + 1, out + 1, 0)
        emit(0, 0, loop)
        emit(-2, out + 6 + span - 1, 0)
        emit(0, 0, halt)
        mem.extend(_ASCII_ZERO + int(c) for c in truth_table[row : row + span])

    def node(level: int, row: int) -> None:
        width = 2 ** (n - level)
        if constant(row, width):
            emit(0, 0, out_one if truth_table[row] == "1" else out_zero)
            return
        if level == n - k:
            leaf(row)
            return
        rc = read_cells[level]
        emit(rc, rc, 0)
        branch = pc() - 3
        node(level + 1, row + width // 2)
        target = pc()
        node(level + 1, row)
        patch(branch, target)

    node(0, 0)

    # Deriving END from the cell count keeps it out of wrap_grid's way: a
    # leaf's table-top operand is within ``2**k + 8`` of it, so the two
    # differ by at most one digit, and _cell_width drops an outlier only at
    # twice the next width.
    for addr in ends:
        mem[addr] = len(mem)
    return " ".join(map(str, mem))


#: Table rows a Collatz Multiverse cell carries, and so its decoder's stride.
#: A cell costs one line whatever its width and the decoder ``c`` lines per
#: distinct cell: at most 64 for four, but up to 2048 for eight, more than
#: the ``T / 8`` lines eight saves below fourteen inputs.
_CM_CHUNK = 4

#: Cell-constant names: one character, and none a register spelled elsewhere.
#: Fifteen, one per nonzero code a four-row cell can take.
_CM_ALIAS = "abcefghijlmnpqr"

#: The shortest line that does nothing -- ``z`` is the zero register.
_CM_PAD = "z=zx+z,NOT PRINT."


def _cm_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Append a block placing ``values`` at consecutive cells of ``array``.

    ``capture`` takes the address one below the first cell -- a line rather
    than a built constant, padded odd so the reader can sum even weights into
    it.  A ``None`` value is left at its default, free in a trailing run.
    """
    if (len(lines) + 1) % 2 == 0:
        lines.append(_CM_PAD)
    lines.append(f"{capture}=zx+lineNumber,NOT PRINT.")
    block = [
        f"{array}[lineNumber]=zx+{value},NOT PRINT." if value else _CM_PAD
        for value in values
    ]
    while block and block[-1] == _CM_PAD:
        block.pop()
    lines += block


def _cm_codes(chunks: list[int], *, zero_top: bool) -> dict[int, int] | None:
    """Return codes ``0, 1, ...`` for the distinct cells: the decoder spans them.

    A cell's code, not its bits, is what the table stores and the decoder is
    indexed by, so a table with ``m`` distinct cells needs ``4 m`` decoder
    lines whatever their values -- ``1000`` is value 1 but ``0001`` is 8,
    and a decoder spanning the values paid 32 lines to reach it.  Code 0 is
    the cell nothing writes, so it goes to the empty cell when there is one
    (its cells cost a pad) and else to the most frequent.  The top code's
    decoder entries past its highest set bit are trailing pads and drop, so
    it goes to the cell whose highest set bit is lowest.

    ``zero_top`` instead puts the empty cell on top, where its four decoder
    entries all drop, and pays for its cells with an alias; ``None`` when
    there is no empty cell to move.
    """
    counts: dict[int, int] = {}
    for value in chunks:
        counts[value] = counts.get(value, 0) + 1
    if zero_top and 0 not in counts:
        return None
    ranked = sorted(counts, key=lambda v: (-counts[v], v))
    head = []
    if 0 in counts and not zero_top:
        ranked.remove(0)
        head = [0]
    top = 0 if zero_top else min(ranked, key=lambda v: (v.bit_length(), -counts[v]))
    ranked.remove(top)
    return {value: code for code, value in enumerate([*head, *ranked, top])}


def _cm_build(
    truth_table: str,
    n: int,
    order: list[int],
    *,
    zero_top: bool | None,
    negate: bool = False,
    flip: bool = False,
) -> str | None:
    """Emit the cell-and-decoder program over ``order``'s inputs.

    ``order`` names the inputs the address is built from, most significant
    first; its last two select a row within a cell and the rest index the
    cells.  An input it leaves out is still read, and never added.
    ``zero_top`` picks :func:`_cm_codes`'s numbering; ``None`` stores each
    cell's own value as its code, the build before cells were numbered.
    ``negate`` stores the complement and prints ``49 - bit``; ``flip``
    stores the table with the last selector's arms swapped.
    """
    table = read_at(truth_table, order, n)
    if negate:
        table = table.translate(str.maketrans("01", "10"))
    if flip:
        table = "".join(table[r ^ 1] for r in range(len(table)))
    padded = table + "0" * (-len(table) % _CM_CHUNK)
    chunks = [
        sum(int(bit) << j for j, bit in enumerate(padded[base : base + _CM_CHUNK]))
        for base in range(0, len(padded), _CM_CHUNK)
    ]
    if zero_top is None:
        codes: dict[int, int] | None = {value: value for value in chunks}
    else:
        codes = _cm_codes(chunks, zero_top=zero_top)
    if codes is None:
        return None
    uses: dict[int, int] = {}
    for value in chunks:
        uses[value] = uses.get(value, 0) + 1

    high = max(len(order) - 2, 0)
    weights = {2 ** (high - 1 - k) for k in range(high)}
    stored = sorted((code, value) for value, code in codes.items() if code)
    lines = _cm_constants(
        {_ASCII_ZERO + negate, *weights, *(_CM_CHUNK * code for code, _ in stored)},
        zero="z",
    )
    # A cell names its code's constant, or a one-letter alias of it when the
    # alias line is cheaper than the characters the alias saves.
    names: dict[int, str] = {}
    for code, value in stored:
        constant = f"k{_CM_CHUNK * code}"
        alias = _CM_ALIAS[sum(len(name) == 1 for name in names.values())]
        line = f"{alias}=zx+{constant},NOT PRINT."
        if uses[value] * (len(constant) - 1) > len(line) + 1:
            lines.append(line)
            names[value] = alias
        else:
            names[value] = constant
    decoder: list[str | None] = [None] * (_CM_CHUNK * (max(codes.values()) + 1))
    for value, code in codes.items():
        for j in range(_CM_CHUNK):
            if (value >> j) & 1:
                decoder[_CM_CHUNK * code + j] = "k1"
    _cm_cells(lines, "D", decoder, "t")
    _cm_cells(lines, "A", [names.get(value) for value in chunks], "s")

    for i in range(n):
        lines.append(f"w{i}=zx+input,NOT PRINT.")
    # ``s`` sits one below the first cell, so the address wants the missing
    # one -- folded into the only odd weight, which has to be added last.
    cells, select = order[:high], order[high:]
    for k, i in enumerate(cells[:-1]):
        lines.append(f"w{i}=k{2 ** (high - 1 - k)}x+z,NOT PRINT.")
        lines.append(f"s=k1x+w{i},NOT PRINT.")
    if cells:
        lines.append(f"w{cells[-1]}=k1x+k1,NOT PRINT.")
        lines.append(f"s=k1x+w{cells[-1]},NOT PRINT.")
    else:
        lines.append("s=k1x+k1,NOT PRINT.")
    lines.append("t=k1x+A[s],NOT PRINT.")
    if len(select) == 2:
        lines.append(f"w{select[0]}=k2x+z,NOT PRINT.")
        lines.append(f"t=k1x+w{select[0]},NOT PRINT.")
    # ``1 + bit``, or ``2 - bit`` when the build swapped that input's arms.
    last = "negativeOnex+k2" if flip else "k1x+k1"
    lines.append(f"w{select[-1]}={last},NOT PRINT.")
    lines.append(f"t=k1x+w{select[-1]},NOT PRINT.")
    lines.append("o=zx+D[t],NOT PRINT.")
    # ``o`` holds the bit: ``0 * a + b`` for a zero, ``1 * a + b`` for a one.
    scale = "negativeOne" if negate else "k1"
    lines.append(f"o={scale}x+k{_ASCII_ZERO + negate},DO PRINT.")
    return "\n".join(lines)


def collatz_multiverse(truth_table: str) -> str:
    """Build a Collatz Multiverse program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The table is placed in cells and indexed, not walked.  An array subscript
    may name ``lineNumber``, so ``A[lineNumber] = z x + v`` drops ``v`` into
    the cell the writing line's own number addresses: such a block lays the
    table out at consecutive addresses for one line a cell, no pointer to
    advance.  Four rows ride in each cell, stored as a *code* ``c`` whose
    constant is ``4 c``, and the last two inputs select within it through a
    decoder holding the cell's bit ``j`` at ``4 c + j``.  ``d = A x + B`` is
    ``d := B + d*A`` for a destination holding zero and ``d := d // 2`` for an
    even one, so an address takes its odd weight last: nothing halves it.

    The candidates are all O(T) and the shortest is kept, the plain build
    first so ties keep it: the plain build stores each cell's value as its
    code; the numbered builds store codes ``0 .. m`` (:func:`_cm_codes`),
    which halves the three-input total, over the essential inputs only (an
    ignored input is read and never added) and under three named choices of
    the two selecting inputs -- the last two, the first two, and the first
    and last, which at three inputs is every pair.  Only which input a
    level tests moves; the reads stay in name order.  Each is also built
    for the complement, printed as ``49 - bit``, and with the last selector
    added as ``2 - bit``: arithmetic swaps those arms, not the fill.
    """
    n = _validate_truth_table(truth_table)
    if all(c == truth_table[0] for c in truth_table):
        # A constant table needs no evaluation, but the reads are the
        # interface: skipping them strands the caller's bits and the prompts.
        const = _ASCII_ZERO + int(truth_table[0])
        lines = _cm_constants({const})
        lines += [f"b{i} = negativeOne x + input, NOT PRINT." for i in range(n)]
        lines.append(f"out = negativeOne x + k{const}, DO PRINT.")
        return "\n".join(lines)

    essential = essential_inputs(truth_table, n)
    orders = [essential]
    if len(essential) >= 3:
        orders += [
            essential[2:] + essential[:2],
            [*essential[1:-1], essential[0], essential[-1]],
        ]
    candidates = [_cm_build(truth_table, n, list(range(n)), zero_top=None)]
    candidates += [
        _cm_build(truth_table, n, order, zero_top=zero_top, negate=negate, flip=flip)
        for order in orders
        for zero_top in (False, True)
        for negate in (False, True)
        for flip in (False, True)
    ]
    return min((c for c in candidates if c is not None), key=len)


def sophie(truth_table: str) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` has ``2**n`` entries, most significant input first.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@$48{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. A leaf loads ``#$48``
    or ``#$49`` for one final ``,`` to print; a last-level ``01`` is its read
    and ``10`` tests it in the character form, ``;@0{#1}{#0}``.

    :func:`_sophie_hybrid` nests unshared residual states like a tree and
    labels only states reached from multiple parents, merging equal ones.

    **Reordering the inputs is not available here**, unlike most tree
    generators: ``;`` and ``:`` *assign* to the accumulator, ``#`` loads only
    a literal, and nothing else writes it, so a bit can only be branched on
    before the next read and the test order is the stream order.  The merge
    collects the saving a reorder would have found.
    """
    _validate_truth_table(truth_table)
    return _sophie_hybrid(truth_table)


#: Accumulator values a Sophie label may not take.
#: A read leaves the accumulator holding the character read, and the tests
#: are against ``48``/``49`` -- ASCII ``0`` and ``1`` -- so a block labelled
#: with either would fire on an ordinary bit rather than on a jump.  Nothing
#: else is reserved: the interpreter reads a label as a plain digit run, so
#: they can climb as high as the program needs.
_SOPHIE_RESERVED = frozenset({_ASCII_ZERO, _ASCII_ONE})


def sophie_labels(retained: list[list[str]]) -> list[dict[str, int]]:
    """Return one label per retained state, unique across all levels.

    This used to draw from two bands by level parity -- ``((1, 20), (21,
    40))`` -- on the reasoning that a fired block leaves the accumulator
    holding a *next*-level label, which no remaining test in the chain can
    match.  The reasoning holds for consecutive levels and that is not the
    relation that matters.  Unshared states are *inlined*, so one top-level
    block contains jumps originating at many different depths, and two
    levels of the same parity are both jump targets from inside it.  Level 2
    and level 4 then both got label ``1``, and since level 2 is emitted
    first, a jump meant for level 4 fired level 2 on the way past -- reading
    inputs the caller never supplied.

    The smallest table that does it is the five-input
    ``00000000000000010000000100000100``, whose program carries two ``@$1``
    blocks.  It is shape-dependent rather than size-dependent, so it hides
    from parity and dense tables and shows up on one-hot: over 500 random
    tables per arity, 1.6% collide at n=5, 11.2% at n=6, 35.0% at n=7 and
    87.6% at n=8, while all 65536 tables at n <= 4 are clean.
    """
    labels: list[dict[str, int]] = []
    number = 1
    for states in retained:
        level: dict[str, int] = {}
        for state in states:
            while number in _SOPHIE_RESERVED:
                number += 1
            level[state] = number
            number += 1
        labels.append(level)
    return labels


def _sophie_hybrid(truth_table: str) -> str:
    """Emit a Sophie tree that labels only shared residual states.

    The states are the residual subtables as strings, ``n * 2**n``
    characters over all levels, and every test here is one C-level pass
    over a state: Theta(T log T), intrinsic to naming the shared states.
    """
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    references: list[dict[str, int]] = [{} for _ in levels]
    for k in range(n - 1):
        width = 2 ** (n - k - 1)
        for state in levels[k]:
            if state.count(state[0]) == len(state):
                continue
            for child in {state[:width], state[width:]}:
                references[k + 1][child] = references[k + 1].get(child, 0) + 1

    retained = [
        [
            state
            for state in states
            if k == 0
            or (
                state.count(state[0]) < len(state)
                and references[k].get(state, 0) > 1
                and state != "01"
            )
        ]
        for k, states in enumerate(levels)
    ]
    labels = sophie_labels(retained)

    # A leaf runs on to the final ``,``: 48/49 fire no ``@$L`` on the way.
    def body(k: int, state: str) -> str:
        if state.count(state[0]) == len(state):
            return ";" * (n - k) + f"#${_ASCII_ZERO + int(state[0])}"
        width = 2 ** (n - k - 1)
        zero, one = state[:width], state[width:]
        if k + 1 == n:
            return ";" if one == "1" else ";@0{#1}{#0}"

        def next_body(child: str) -> str:
            if child in labels[k + 1]:
                return f"#${labels[k + 1][child]}"
            return body(k + 1, child)

        if zero == one:
            return ";" + next_body(zero)
        return f";@$48{{{next_body(zero)}}}{{{next_body(one)}}}"

    out = []
    for k, states in enumerate(retained):
        for state in states:
            block = body(k, state)
            out.append(block if k == 0 else f"@${labels[k][state]}{{{block}}}")
    return "".join(out) + ","


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


_QOIBL_POWER, _QOIBL_ROW = 0, 1


def qoibl(truth_table: str) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` has length ``2**n``, most significant input first.  The
    whole table rides in one binary literal, bit ``k`` holding row ``k``, so
    ``table // 2**index`` then ``r - 2 * (r // 2)`` reads that row off.
    """
    n = _validate_truth_table(truth_table)
    power = _qoibl_enc(_QOIBL_POWER)
    row = _qoibl_enc(_QOIBL_ROW)
    zero = _qoibl_enc(_ASCII_ZERO)
    packed = sum(int(bit) << index for index, bit in enumerate(truth_table))

    # ``p = p * (p * (et - 47))``: the digit is 48 or 49, so that factor is
    # the bit plus one and squaring makes the reads Horner's rule.
    bit = f"et ry ey ry {_qoibl_enc(_ASCII_ZERO - 1)}"
    lines = [f"we {power} we {bit} we"]
    lines += (n - 1) * [
        f"we {power} we qe {power} qe ry ye ry qe {power} qe ry ye ry {bit} we"
    ]
    lines.append(f"we {row} we {_qoibl_enc(packed)} ry yy ry qe {power} qe we")
    lines.append(
        f"tt qe {row} qe ry ee ry {zero} ry ey ry ye ry ye ry "
        f"qe {row} qe ry yy ry ye tt"
    )
    return "\n".join(lines)
