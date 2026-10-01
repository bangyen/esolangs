"""Boolean-function generators for register-based languages."""

import re
from itertools import chain, count, pairwise

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
    _residual_ids,
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
from esolangs.tools.polynomial import (
    _polynomial_states as _polynomial_states,
)
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


def _cm_narrow_constants(needed: set[int]) -> list[str]:
    """Capture constants at their numbered lines; intervening pads are inert."""
    needed |= {1, 2, 3, 4}
    return [
        f"k{value}=zx+lineNumber,NOT PRINT." if value in needed else _CM_PAD
        for value in range(1, max(needed) + 1)
    ]


def _cm_narrow_cells(
    lines: list[str], array: str, values: list[str | None], capture: str
) -> None:
    """Write at odd indices 3+2i; an odd cursor advances without halving."""
    lines += [f"{capture}=zx+k1,NOT PRINT.", "r=zx+k3,NOT PRINT."]
    last = max((i for i, value in enumerate(values) if value), default=-1)
    for value in values[: last + 1]:
        if value:
            lines.append(f"{array}[r]=zx+{value},NOT PRINT.")
        lines.append("r=k1x+k2,NOT PRINT.")


def _cm_build(
    truth_table: str,
    n: int,
    order: list[int],
    *,
    zero_top: bool | None,
    narrow: bool = False,
) -> str | None:
    """Emit the cell-and-decoder program over ``order``'s inputs.

    ``order`` names the inputs the address is built from, most significant
    first; its last two select a row within a cell and the rest index the
    cells.  An input it leaves out is still read, and never added.
    ``zero_top`` picks :func:`_cm_codes`'s numbering; ``None`` stores each
    cell's own value as its code, the build before cells were numbered.
    ``narrow`` uses odd indices ``3 + 2 i`` and doubles address offsets.
    """
    address_scale = 2 if narrow else 1
    table = read_at(truth_table, order, n)
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
    weights = {address_scale * 2 ** (high - 1 - k) for k in range(high)}
    stored = sorted((code, value) for value, code in codes.items() if code)
    needed = {
        _ASCII_ZERO,
        *weights,
        *(address_scale * _CM_CHUNK * code for code, _ in stored),
    }
    lines = _cm_narrow_constants(needed) if narrow else _cm_constants(needed, zero="z")
    # A cell names its code's constant, or a one-letter alias of it when the
    # alias line is cheaper than the characters the alias saves.
    names: dict[int, str] = {}
    for code, value in stored:
        constant = f"k{address_scale * _CM_CHUNK * code}"
        # The narrow cursor owns r throughout both array blocks.
        alias_pool = _CM_ALIAS.replace("r", "u") if narrow else _CM_ALIAS
        alias = alias_pool[sum(len(name) == 1 for name in names.values())]
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
    cells_builder = _cm_narrow_cells if narrow else _cm_cells
    cells_builder(lines, "D", decoder, "t")
    cells_builder(lines, "A", [names.get(value) for value in chunks], "s")

    for i in range(n):
        lines.append(f"w{i}=zx+input,NOT PRINT.")
    # ``s`` sits one below the first cell, so the address wants the missing
    # one -- folded into the only odd weight, which has to be added last.
    cells, select = order[:high], order[high:]
    for k, i in enumerate(cells[:-1]):
        lines.append(f"w{i}=k{address_scale * 2 ** (high - 1 - k)}x+z,NOT PRINT.")
        lines.append(f"s=k1x+w{i},NOT PRINT.")
    if cells:
        lines.append(f"w{cells[-1]}=k{address_scale}x+k{address_scale},NOT PRINT.")
        lines.append(f"s=k1x+w{cells[-1]},NOT PRINT.")
    else:
        lines.append(f"s=k1x+k{address_scale},NOT PRINT.")
    lines.append("t=k1x+A[s],NOT PRINT.")
    if len(select) == 2:
        lines.append(f"w{select[0]}=k{2 * address_scale}x+z,NOT PRINT.")
        lines.append(f"t=k1x+w{select[0]},NOT PRINT.")
    last = f"k{address_scale}x+k{address_scale}"
    lines.append(f"w{select[-1]}={last},NOT PRINT.")
    lines.append(f"t=k1x+w{select[-1]},NOT PRINT.")
    lines.append("o=zx+D[t],NOT PRINT.")
    # ``o`` holds the bit: ``0 * a + b`` for a zero, ``1 * a + b`` for a one.
    lines.append(f"o=k1x+k{_ASCII_ZERO},DO PRINT.")
    return "\n".join(lines)


def _cm_layout(program: str, width: int) -> str:
    """Narrow complete assignments; an even prefix preserves address parity."""
    if max(map(len, program.splitlines()), default=0) <= width:
        return program
    compact = program.replace(" ", "").replace("NOTPRINT", "NOT PRINT")
    compact = compact.replace("DOPRINT", "DO PRINT")
    if max(map(len, compact.splitlines()), default=0) <= width:
        return compact
    # Generated names exclude '_'.  Captured lineNumber addresses shift
    # together; two prefix lines keep the odd capture used by weighted sums.
    if "negativeOne" in compact:
        aliased = "_=zx+negativeOne,NOT PRINT.\n" + "z=zx+z,NOT PRINT.\n"
        aliased += compact.replace("negativeOne", "_")
        if max(map(len, aliased.splitlines())) < max(map(len, compact.splitlines())):
            compact = aliased
    if max(map(len, compact.splitlines())) <= width:
        return compact
    # A bijective rename changes no lines, so captured addresses and parity stay.
    # Uppercase names other than A/D are absent from the generated cell decoder.
    registers = list(
        dict.fromkeys(re.findall(r"k\d+|w\d+|b\d+|\bout\b|\bzero\b", compact))
    )
    alphabet = "BCEFGHIJKLMNOPQRSTUVWXYZ"
    aliases = {
        name: alphabet[i] if i < len(alphabet) else f"B{i - len(alphabet)}"
        for i, name in enumerate(registers)
    }
    return re.sub(
        r"k\d+|w\d+|b\d+|\bout\b|\bzero\b",
        lambda match: aliases[match.group()],
        compact,
    )


def collatz_multiverse(truth_table: str, width: int | None = None) -> str:
    """Build a Collatz Multiverse program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    ``width`` selects complete statements with fixed odd-index cells when needed.

    The table is placed in cells and indexed, not walked.  An array subscript
    may name ``lineNumber``, so ``A[lineNumber] = z x + v`` drops ``v`` into
    the cell the writing line's own number addresses: such a block lays the
    table out at consecutive addresses for one line a cell, no pointer to
    advance.  Four rows ride in each cell, stored as a *code* ``c`` whose
    constant is ``4 c``, and the last two inputs select within it through a
    decoder holding the cell's bit ``j`` at ``4 c + j``.  ``d = A x + B`` is
    ``d := B + d*A`` for a destination holding zero and ``d := d // 2`` for an
    even one, so an address takes its odd weight last: nothing halves it.

    Numbered builds store codes ``0 .. m`` (:func:`_cm_codes`),
    which halves the three-input total, over the essential inputs only (an
    ignored input is read and never added). The last two or the first and
    last inputs select; width requests also try the first two.  Only which input a
    level tests moves; the reads stay in name order. Both code numberings
    are tried: the empty chunk stays at code zero or moves to the top,
    where its decoder pads drop.
    """
    n = _validate_truth_table(truth_table)
    if all(c == truth_table[0] for c in truth_table):
        # A constant table needs no evaluation, but the reads are the
        # interface: skipping them strands the caller's bits and the prompts.
        const = _ASCII_ZERO + int(truth_table[0])
        lines = _cm_constants({const})
        lines += [f"b{i} = negativeOne x + input, NOT PRINT." for i in range(n)]
        lines.append(f"out = negativeOne x + k{const}, DO PRINT.")
        program = "\n".join(lines)
        if width is None or width <= 0:
            return program
        fitted = _cm_layout(program, width)
        if max(map(len, fitted.splitlines())) <= width:
            return fitted
        lines = _cm_narrow_constants({const})
        lines += [f"b{i}=zx+input,NOT PRINT." for i in range(n)]
        lines.append(f"out=zx+k{const},DO PRINT.")
        narrow = _cm_layout("\n".join(lines), width)
        return min(
            (fitted, narrow), key=lambda c: (max(map(len, c.splitlines())), len(c))
        )

    essential = essential_inputs(truth_table, n)
    orders = [essential]
    if len(essential) >= 3:
        if width is not None:
            orders.append(essential[2:] + essential[:2])
        orders.append([*essential[1:-1], essential[0], essential[-1]])
    candidates = [
        _cm_build(truth_table, n, order, zero_top=zero_top)
        for order in orders
        for zero_top in (False, True)
    ]
    program = min((c for c in candidates if c is not None), key=len)
    if width is None or width <= 0:
        return program
    fitted = _cm_layout(program, width)
    if max(map(len, fitted.splitlines())) <= width:
        return fitted
    narrow_candidates = [
        _cm_build(truth_table, n, order, zero_top=zero_top, narrow=True)
        for order in orders
        for zero_top in (False, True)
    ]
    layouts = [fitted] + [
        _cm_layout(c, width) for c in narrow_candidates if c is not None
    ]
    return min(layouts, key=lambda c: (max(map(len, c.splitlines())), len(c)))


def sophie(truth_table: str) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` has ``2**n`` entries, most significant input first.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@0{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. A leaf loads ``#0`` or
    ``#1`` for one final ``,`` to print; a last-level ``01`` is its read.

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


#: Accumulator values a Sophie label may not take: a read leaves ``0`` or
#: ``1`` (48/49), so a block labelled either would fire on an ordinary bit.
_SOPHIE_RESERVED = frozenset({_ASCII_ZERO, _ASCII_ONE})

#: Values spelled as one character, ``#c``/``@c{``: not ``$``, brackets
#: (``_partners`` ignores loads), ``#`` (``matches`` misreads ``@#{``) or space.
_SOPHIE_CHARACTERS = frozenset(range(33, 127)) - {ord(c) for c in "#$[]{}"}


def _sophie_literal(value: int) -> str:
    """Spell ``value`` after ``#`` or ``@``: its character, else ``$`` digits."""
    return chr(value) if value in _SOPHIE_CHARACTERS else f"${value}"


def sophie_labels(retained: list[list[int]]) -> list[dict[int, int]]:
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

    Single-character values come first, then numbers from 1 that are not.
    """
    single = sorted(_SOPHIE_CHARACTERS - _SOPHIE_RESERVED)
    rest = (v for v in count(1) if v not in _SOPHIE_CHARACTERS)
    values = chain(single, rest)
    return [{state: next(values) for state in states} for states in retained]


def _sophie_hybrid(truth_table: str) -> str:
    """Emit a Sophie tree that labels only shared residual states.

    Canonical child pairs name states in O(T) RAM work without copying
    the subtables at every depth. First-occurrence order preserves labels.
    """
    n = _validate_truth_table(truth_table)
    levels, children, constants = _residual_ids(truth_table, n)
    references: list[dict[int, int]] = [{} for _ in levels]
    for k in range(n - 1):
        for state in levels[k]:
            if constants[state] is not None:
                continue
            for child in set(children[state]):
                references[k + 1][child] = references[k + 1].get(child, 0) + 1

    retained = [
        [
            state
            for state in states
            if k == 0
            or (
                constants[state] is None
                and references[k].get(state, 0) > 1
                and not (k == n - 1 and children[state] == (0, 1))
            )
        ]
        for k, states in enumerate(levels)
    ]
    labels = sophie_labels(retained)

    out: list[str] = []

    # A leaf runs on to the final ``,``: 48/49 fire no ``@L`` on the way.
    def body(k: int, state: int) -> None:
        if constants[state] is not None:
            out.append(";" * (n - k) + f"#{constants[state]}")
            return
        zero, one = children[state]
        if k + 1 == n:
            out.append(";" if one == 1 else ";@0{#1}{#0}")
            return

        def next_body(child: int) -> None:
            if child in labels[k + 1]:
                out.append("#" + _sophie_literal(labels[k + 1][child]))
            else:
                body(k + 1, child)

        if zero == one:
            out.append(";")
            next_body(zero)
        else:
            out.append(";@0{")
            next_body(zero)
            out.append("}{")
            next_body(one)
            out.append("}")

    for k, states in enumerate(retained):
        for state in states:
            if k:
                out.append("@" + _sophie_literal(labels[k][state]) + "{")
            body(k, state)
            if k:
                out.append("}")
    out.append(",")
    return "".join(out)


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


_QOIBL_POWER, _QOIBL_ROW = 0, 1


def qoibl(truth_table: str, width: int | None = None) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` has length ``2**n``, most significant input first.  The
    Whole-table literals expand into O(T) binary Horner steps when narrow.
    The whole table rides in one binary literal, bit ``k`` holding row ``k``, so
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
    program = "\n".join(lines)
    if width is None or width <= 0:
        return program
    from esolangs.tools.wrap import _qoibl, wrap_space_delimited

    previous = _qoibl(program, width)
    if max(map(len, previous.splitlines())) <= width:
        return previous
    limit = max(2, width)
    output: list[str] = []
    scratch = _qoibl_enc(2)
    for line in lines:
        tokens = line.split()
        for at, token in enumerate(tokens):
            if len(token) <= limit:
                continue
            # Each statement has one long literal. Binary Horner steps use
            # spare variable 2; separate multiply/add respect right association.
            chunks = [token[i : i + limit - 1] for i in range(0, len(token), limit - 1)]
            output.append(f"we {scratch} we {chunks[0]} we")
            for chunk in chunks[1:]:
                factor = _qoibl_enc(1 << len(chunk))
                output.append(f"we {scratch} we qe {scratch} qe ry ye ry {factor} we")
                output.append(f"we {scratch} we qe {scratch} qe ry ee ry {chunk} we")
            tokens[at] = f"qe {scratch} qe"
        output.append(" ".join(tokens))
    return "\n".join(wrap_space_delimited(line, limit) for line in output)
