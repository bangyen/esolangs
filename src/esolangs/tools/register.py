"""Boolean-function generators for register-based languages."""

from itertools import pairwise

# Polynomial, Dig and AddSubJump each own a file: their constructions dwarf
# the rest of the category, and this module stays the import site the package
# and tests already use.
from esolangs.tools.addsubjump import addsubjump as addsubjump

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
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
    jumps to ``c``, a ``1`` bit (2) falls through.  The decision tree routes
    those branches to leaves that output 48 or 49 (placed in data cells of
    the self-modifying memory) and then halt.

    A subtree whose rows all agree becomes a leaf rather than branching on
    bits that cannot change the answer.  Rows split most-significant-first,
    so a subtree is a contiguous run and ``11110000`` folds to a single
    branch -- unlike the generators that split the other way, where that
    table folds nothing.

    The fold has to be counted *before* it is emitted.  ``data_base`` sits
    above the code, so the output cells' addresses depend on how long the
    tree came out; :func:`tree_instrs` walks it first and must stop in
    exactly the places :func:`node` will.  When it does, the code ends
    exactly at ``data_base`` and the ``extend`` below allocates only the
    ``n`` read cells and the two output cells -- every cell in the program
    holds either an instruction or live data.

    Getting the count wrong does not produce a *broken* program: the
    ``extend`` fills out to whatever address was reserved, so the leaves
    still resolve and the output is still correct.  It silently inserts a
    run of dead zero cells instead (63 of them at ``n == 3`` if the tree is
    sized as though nothing folded), which is why the test pins the cell
    count rather than the output -- an output-based test cannot see it.

    Every input is still read, so the program consumes exactly ``n`` input
    bytes.  But an ignored input never controls a non-folded branch, so it
    needs no 47-step normalization chain: the fixed cost is
    ``47 * len(essential_inputs)`` rather than ``47 * n``.
    """
    n = _validate_truth_table(truth_table)

    def constant(level: int, row: int) -> bool:
        """Whether every row this subtree covers agrees.

        Rows split most-significant-first, so a subtree covers the
        contiguous run of ``2 ** (n - level)`` rows starting at ``row``.
        """
        span = 2 ** (n - level)
        return len(set(truth_table[row : row + span])) == 1

    def tree_instrs(level: int, row: int) -> int:
        """Instructions the subtree at ``(level, row)`` emits.

        The data cells sit above the code, so their addresses depend on the
        tree's length -- which folding changes.  The count has to come from
        the same walk that emits, or every leaf would name the wrong output
        cell.
        """
        if level == n or constant(level, row):
            return 2  # output, then halt
        return (
            1
            + tree_instrs(level + 1, row + 2 ** (n - 1 - level))
            + tree_instrs(
                level + 1,
                row,
            )
        )

    # Every input is read to preserve the interface, but only inputs on
    # which the table depends need normalizing: folding makes both outcomes
    # of every other branch equivalent.
    essential = set(essential_inputs(truth_table, n))
    # instructions: n reads, one normalization chain per essential input,
    # and the tree, whose size depends on how much of it folds away.
    n_instr = n + 47 * len(essential) + tree_instrs(0, 0)
    data_base = 3 * n_instr
    read_cells = [data_base + i for i in range(n)]
    out48 = data_base + n
    out49 = out48 + 1

    mem: list[int] = []

    def emit(a: int, b: int, c: int) -> None:
        mem.extend([a, b, c])

    def pc() -> int:
        return len(mem)

    def patch(addr: int, c: int) -> None:
        mem[addr + 2] = c

    for rc in read_cells:
        emit(-1, rc, pc() + 3)
    for i, rc in enumerate(read_cells):
        if i not in essential:
            continue
        for _ in range(47):
            emit(rc, rc, pc() + 3)

    # The halt jump has to name an address past the end of memory, unknown
    # until the data cells below have been appended.  Each leaf emits this
    # placeholder and the real address is substituted once the program is
    # complete, so the sentinel is exactly one past the last cell however the
    # tree came out.
    halts: list[int] = []

    def node(level: int, row: int) -> None:
        # The fold has to stop in exactly the places tree_instrs stopped:
        # it sized the data cells from that walk, so a check applied here
        # and not there would leave every leaf naming the wrong address.
        if level == n or constant(level, row):
            emit(-2, out49 if truth_table[row] == "1" else out48, 0)
            emit(0, 0, 0)
            halts.append(pc() - 1)
            return
        rc = read_cells[level]
        emit(rc, rc, 0)
        branch = pc() - 3
        node(level + 1, row + 2 ** (n - 1 - level))
        target = pc()
        node(level + 1, row)
        patch(branch, target)

    node(0, 0)

    mem.extend([0] * (out49 - len(mem) + 1))
    mem[out48] = _ASCII_ZERO
    mem[out49] = _ASCII_ONE
    # One past the last cell: the interpreter halts as soon as the pointer
    # leaves memory, so this is the smallest address that stops the program.
    #
    # Deriving it from the cell count also keeps it out of wrap_grid's way,
    # however big the program gets.  Every leaf names out48 or out49 --
    # len(mem) - 2 and len(mem) - 1 -- so a token within two of the sentinel
    # always exists, and the two can differ by at most one digit (only across
    # a power of ten).  _cell_width drops an outlier only while it is at
    # least *twice* the next width, which one digit never is above 9 cells,
    # so the sentinel widens the cell at worst and never spans two of them
    # the way the old constant 10**9 did.
    for addr in halts:
        mem[addr] = len(mem)
    return " ".join(map(str, mem))


def collatz_multiverse(truth_table: str) -> str:
    """Build a Collatz Multiverse program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    A postorder Shannon tree combines child bits as
    ``(!x & zero) | (x & one)``. Registers are reused by recursion depth;
    every write first clears its destination because Collatz assignment
    otherwise depends on the destination's old parity. Short names belong to
    the deepest, most repeated levels, keeping the emitted source O(T).
    """
    n = _validate_truth_table(truth_table)
    if all(c == truth_table[0] for c in truth_table):
        # A constant table needs no evaluation, but the reads are the language's
        # interface: skipping them would leave the caller's bits unread on the
        # input stream and drop the prompts a prompting interpreter emits.  So
        # read every input, discard it, and print the constant.
        const = _ASCII_ZERO + int(truth_table[0])
        lines = _cm_constants({const})
        lines += [f"b{i} = negativeOne x + input, NOT PRINT." for i in range(n)]
        lines.append(f"out = negativeOne x + k{const}, DO PRINT.")
        return "\n".join(lines)

    lines = _cm_constants({_ASCII_ZERO})
    inputs = [f"b{n - 1 - depth}" for depth in range(n)]
    for name in inputs:
        lines.append(f"{name} = negativeOne x + input, NOT PRINT.")

    def clear(dst: str) -> None:
        lines.append(f"{dst} = zero x + zero, NOT PRINT.")

    def assign(dst: str, src: str) -> None:
        clear(dst)
        lines.append(f"{dst} = negativeOne x + {src}, NOT PRINT.")

    def negate(dst: str, src: str) -> None:
        assign(dst, src)
        lines.append(f"{dst} = negativeOne x + k1, NOT PRINT.")

    def conjunction(dst: str, x: str, y: str) -> None:
        assign(dst, x)
        lines.append(f"{dst} = {y} x + zero, NOT PRINT.")

    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))

    def tree(start: int, end: int, depth: int) -> str:
        if changes[start] == changes[end - 1]:
            return "k1" if truth_table[start] == "1" else "zero"
        half = (start + end) // 2
        zero = tree(start, half, depth + 1)
        index = n - 1 - depth
        saved = f"l{index}"
        if zero not in {"zero", "k1"}:
            assign(saved, zero)
            zero = saved
        one = tree(half, end, depth + 1)
        inverted = f"i{index}"
        left = f"a{index}"
        right = f"c{index}"
        result = f"r{index}"
        negate(inverted, inputs[depth])
        conjunction(left, inverted, zero)
        conjunction(right, inputs[depth], one)
        assign(result, left)
        lines.append(f"{result} = k1 x + {right}, NOT PRINT.")
        return result

    result = tree(0, 1 << n, 0)
    out = "out"
    assign(out, result)
    lines.append(f"{out} = k1 x + k48, DO PRINT.")
    return "\n".join(lines)


def sophie(truth_table: str) -> str:
    """Build a Sophie program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Sophie reads a character with ``;`` and branches on the accumulator with
    ``@$48{then}{else}`` -- the else block runs flat after a failed check, so
    consecutive conditionals must use the block form. Each leaf sets the
    result with ``#$48``/``#$49`` and prints it before halting.

    :func:`_sophie_hybrid` nests unshared residual states like a tree and
    labels only states reached from multiple parents. It therefore keeps
    constant-subtree folding while merging equal residual subfunctions.

    The hybrid only pays a label where sharing needs it, so it cannot lose
    the tree's compact unshared regions.

    **Reordering the inputs is not available here**, unlike most tree
    generators: ``;`` and ``:`` *assign* to the accumulator, ``#`` loads only
    a literal, and nothing else writes it, so a bit can only be branched on
    before the next read and the test order is the stream order.  The merge
    collects the saving a reorder would have found.
    """
    _validate_truth_table(truth_table)
    return _sophie_hybrid(truth_table)


#: Accumulator values a Sophie label may not take.
#:
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

    Numbering across the whole program rather than per level also retires a
    second latent collision: the bands' upper bounds were never read, so a
    level with more than twenty retained states ran straight into the next
    band.
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
    """Emit a Sophie tree that labels only shared residual states."""
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    references: list[dict[str, int]] = [{} for _ in levels]
    for k in range(n - 1):
        width = 2 ** (n - k - 1)
        for state in levels[k]:
            if len(set(state)) == 1:
                continue
            for child in {state[:width], state[width:]}:
                references[k + 1][child] = references[k + 1].get(child, 0) + 1

    retained = [
        [
            state
            for state in states
            if k == 0 or (len(set(state)) > 1 and references[k].get(state, 0) > 1)
        ]
        for k, states in enumerate(levels)
    ]
    labels = sophie_labels(retained)

    def body(k: int, state: str) -> str:
        if len(set(state)) == 1:
            return ";" * (n - k) + f"#${_ASCII_ZERO + int(state[0])},&"
        width = 2 ** (n - k - 1)
        zero, one = state[:width], state[width:]
        if k + 1 == n:
            return (
                f";@$48{{#${_ASCII_ZERO + int(zero)},&}}"
                f"{{#${_ASCII_ZERO + int(one)},&}}"
            )

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
    return "".join(out)


def _qoibl_enc(n: int) -> str:
    """Qoibl binary literal for ``n`` (e is 0, y is 1)."""
    return f"{n:b}".replace("0", "e").replace("1", "y")


def qoibl(truth_table: str) -> str:
    """Build a Qoibl program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Each input is read with ``et`` and normalized to 0/1.  A folded Shannon
    tree then combines children as ``(1 - x) * lo + x * hi``.  Four registers
    are reserved per level; the deepest, most frequently repeated levels get
    the shortest binary names, so widening register IDs still sum to O(T).
    """
    n = _validate_truth_table(truth_table)

    def registers(level: int) -> tuple[int, int, int, int]:
        base = 4 * (n - 1 - level)
        return base, base + 1, base + 2, base + 3

    lines: list[str] = []
    for level in range(n):
        raw, complement, _lo, _hi = registers(level)
        lines.append(
            f"we {_qoibl_enc(raw)} we et ry ey ry {_qoibl_enc(_ASCII_ZERO)} we"
        )
        lines.append(
            f"we {_qoibl_enc(complement)} we {_qoibl_enc(1)} "
            f"ry ey ry qe {_qoibl_enc(raw)} qe we"
        )

    root = 4 * n

    def assign(destination: int, expression: str) -> None:
        lines.append(f"we {_qoibl_enc(destination)} we {expression} we")

    def node(level: int, lo: int, hi: int, destination: int) -> None:
        if len(set(truth_table[lo:hi])) == 1:
            assign(destination, _qoibl_enc(int(truth_table[lo])))
            return
        mid = (lo + hi) // 2
        if truth_table[lo:mid] == truth_table[mid:hi]:
            node(level + 1, lo, mid, destination)
            return
        raw, complement, low, high = registers(level)
        node(level + 1, lo, mid, low)
        node(level + 1, mid, hi, high)
        assign(
            low,
            f"qe {_qoibl_enc(complement)} qe ry ye ry qe {_qoibl_enc(low)} qe",
        )
        assign(high, f"qe {_qoibl_enc(raw)} qe ry ye ry qe {_qoibl_enc(high)} qe")
        assign(
            destination,
            f"qe {_qoibl_enc(low)} qe ry ee ry qe {_qoibl_enc(high)} qe",
        )

    node(0, 0, 2**n, root)
    lines.append(f"tt qe {_qoibl_enc(root)} qe ry ee ry {_qoibl_enc(_ASCII_ZERO)} tt")
    return "\n".join(lines)
