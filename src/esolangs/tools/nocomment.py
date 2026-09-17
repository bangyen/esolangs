"""Boolean-function generator for NoComment."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

#: How each input is set: ``c`` clears the cell for a zero, ``i`` increments
#: it to one.  The template spells each input as a run of
#: :data:`TEMPLATE_CHAR` this wide.
PAIR = ("c", "i")
_NOCOMMENT_INPUT = TEMPLATE_CHAR * len(PAIR[0])

# The largest value a NoComment cell can hold, hence the largest distance a
# single ``s``/``b`` jump can cover: the skip amount is peeked off the stack,
# and everything on that stack came from a byte-sized tape cell.
_NOCOMMENT_SKIP_MAX = 255


# Past this arity the *index* no longer fits one byte, so the single-skip
# decode below stops working.  It is the largest ``n`` with
# ``2**n - 1 <= _NOCOMMENT_SKIP_MAX``; the chain takes over well before it.
_NOCOMMENT_NARROW_MAX = (_NOCOMMENT_SKIP_MAX + 1).bit_length() - 1

# The arity from which :func:`_nocomment_chain` is the smaller program.  The
# narrow decode pays a NOT gate and a guarded weight per input plus one
# preloaded cell per row; the chain pays six commands per row and a stage
# per 32 rows.  Measured over every table: the narrow decode is smaller on
# 218 of the 256 tables at three inputs and the chain is never larger at four.
_NOCOMMENT_CHAIN_MIN = 4


#: A chain group is six commands, ``f s f X X s``: the pop-and-skip a stage
#: lands on, the pop the final skip lands on, the row's two-command delta,
#: and the skip that carries the fall-through to the next group's delta.
_NOCOMMENT_GROUP = 6

#: Groups one full stage advances.  A stage skips ``6 * a + 4`` commands, so
#: ``a`` is at most 41; a power of two keeps every bit's weight a whole
#: number of full stages until the weight itself drops below it.
_NOCOMMENT_STAGE = 32


def _nocomment_chain(truth_table: str, n: int) -> str:
    """Build a NoComment template that needs six tape cells at any arity.

    The one-``s`` narrow decode caps at ``n == 8`` and the wide one's
    ``2**n`` output cells at ``n == 12`` on the 4096-cell tape; here the rows
    live in the *code* and the index on the *stack*.  A table that ignores
    inputs is evaluated over the essential ones.  Bit ``i`` of weight ``W``
    pushes ``W / 32`` stages of ``6 * a + 4`` (one) or ``4`` (zero), reusing
    six cells.  The code is uniform six-command groups ``f s f X X s``: a
    stage's ``f`` pops the amount into ``G`` and ``s`` skips ``a + 1``
    groups; the constant ``6`` lands two commands into a group so the
    fall-through runs every later group's ``X X`` delta (``+2``, ``-2`` or
    ``0`` for ``table[j] - table[j + 1]``) and nothing else.  The deltas
    telescope to ``table[A]``, ``G`` reads ``6 + 2 * table[A]``, and the
    epilogue maps ``{6, 8}`` to ``{48, 49}``.  Size ``6`` per row plus
    ``T / 32`` pushes; execution ``O(T)``; stack depth ``T / 32 + n + 3``.
    """
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    weights = {i: 1 << (width - 1 - slot) for slot, i in enumerate(used)}
    rows = 1 << width
    out: list[str] = []
    ptr = [0]
    bit, comp, stage, scratch, guard, const = range(6)

    def move(dst: int) -> None:
        while ptr[0] < dst:
            out.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            out.append("l")
            ptr[0] -= 1

    def guarded(cell: int, block: list[str]) -> None:
        """Run ``block`` iff ``cell`` is zero, ending on ``cell``.

        Leaves the stack as it found it; below is the index under construction.
        """
        move(scratch)
        out.append("c")
        out.extend(["i"] * len(block))
        out.append("n")
        move(cell)
        out.append("s")
        out.extend(block)
        move(scratch)
        out.append("f")
        move(cell)

    # The two constants under everything: the fall-through's skip of three
    # (deepest, so it is what remains) and the final stage's landing six.
    move(const)
    out.append("c")
    out.extend(["i"] * 3)
    out.append("n")
    out.extend(["i"] * 3)
    out.append("n")

    stages = 0
    for i in range(n):
        move(bit)
        out.append("c")
        out.append(_NOCOMMENT_INPUT)
        if i not in weights:
            continue
        weight = weights[i]
        advance = min(weight, _NOCOMMENT_STAGE)
        count = weight // advance
        move(comp)
        out.append("c")
        # comp = 1 - bit: the increment runs exactly when the bit is zero.
        guarded(bit, ["r", "i", "l"])
        move(stage)
        out.append("c")
        out.extend(["i"] * 4)
        # stage = 4 + 6 * advance exactly when the bit is one.
        guarded(comp, ["r", *(["i"] * (_NOCOMMENT_GROUP * advance)), "l"])
        move(stage)
        out.extend(["n"] * count)
        stages += count

    # The first group pops before it skips, so a nonzero dummy goes on top.
    move(const)
    out.append("c")
    out.extend(["i"] * 4)
    out.append("n")
    move(guard)

    def group(delta: int) -> str:
        return "fsf" + {1: "ii", -1: "dd", 0: "id"}[delta] + "s"

    out.extend(group(0) for _ in range(stages + 1))
    for j in range(rows):
        after = int(table[j + 1]) if j + 1 < rows else 0
        out.append(group(int(table[j]) - after))

    # The last group's skip of three lands past it, on three dead commands.
    out.append("sss")
    # G is 6 or 8: down to {0, 2}, then +1 only when zero -> {1, 2}, then +47.
    out.extend(["d"] * _NOCOMMENT_GROUP)
    out.append("s")
    out.append("iid")
    out.extend(["i"] * (_ASCII_ZERO - 1))
    out.append("o")
    return "".join(out)


def nocomment(truth_table: str) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Each
    run is a constant-length setter; the complement is not embedded, since
    ``s`` (skip iff nonzero) doubles as a NOT gate and a prologue computes
    ``comp_i = 1 - bit_i`` once.  The program computes the numeric index
    (each bit adds ``2**w`` when its complement cell is zero) and uses it as
    a byte-sized ``s`` skip into a staircase of ``l`` moves landing on a
    preloaded cell holding ``48 + truth_table[index]``, then one ``o``.  The
    one-skip form needs the index to fit a byte and is used below
    ``_NOCOMMENT_CHAIN_MIN``; :func:`_nocomment_chain` takes over from four inputs.
    """
    n = _validate_truth_table(truth_table)
    if n >= _NOCOMMENT_CHAIN_MIN:
        return _nocomment_chain(truth_table, n)

    # Everything is sized by the index range (one ``l`` and one output
    # cell per row), so evaluating over the essential inputs shrinks
    # ``2**n`` to ``2**width``.  Every input keeps its setter and prologue;
    # an ignored one's weight run ``["i"] * (2**w)`` is empty, and its
    # guard still leaves the pointer on its complement cell.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    # Slot ``s`` carries original input ``used[s]``, so it takes the weight
    # ``2**(width - 1 - s)``; an ignored input takes none.
    weights = {i: 2 ** (width - 1 - slot) for slot, i in enumerate(used)}

    k = 2**width
    index = 2 * n
    skip_base = index + 1  # one skip cell per input bit
    tbase = skip_base + n  # the output cells
    sentinel = tbase + k  # non-zero cell the final ``s`` gates on
    scratch = sentinel + 1  # reused per bit to push each NOT gate's skip length

    # Emit the index computation and the output staircase.  Each bit's
    # guarded increment ends with the pointer back on its complement cell,
    # so the emitted moves stay consistent.
    commands: list[str] = []
    ptr = [index]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            commands.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            commands.append("l")
            ptr[0] -= 1

    skip_vals: dict[int, int] = {}
    for i in range(n):
        comp = n + i
        d = skip_base + i
        move(d)
        commands.append("n")
        move(comp)
        commands.append("s")
        block = len(commands)
        move(index)
        commands.extend(["i"] * weights.get(i, 0))
        move(comp)
        skip_vals[d] = len(commands) - block
    move(index)
    commands.append("n")  # push the index
    ptr[0] = index
    move(sentinel)
    commands.append("s")  # skip by the index into the staircase
    commands.extend(["l"] * k)
    commands.append("o")

    # Setup: bits, complements, index, skip cells, output cells, sentinel,
    # scratch.  The complement cells (n..2n-1) start at zero and are filled
    # by the NOT-gate prologue below, not by a second embedded run.
    setup: list[str] = []
    setup_ptr = [0]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    for _i in range(n):
        setup.append(_NOCOMMENT_INPUT)
        setup.append("r")
    setup_ptr[0] = n

    # NOT-gate prologue: ``s`` at the bit cell skips the block that
    # increments comp_i, so it runs only when the bit is zero; both paths
    # leave the pointer on the bit cell.
    for i in range(n):
        comp = n + i
        # comp is always to the right of bit i (comp - i == n), so the gate
        # is a straight-line move-set-return with no branching to track.
        dist = comp - i
        gate = ["r"] * dist + ["i"] + ["l"] * dist
        gate_len = len(gate)

        setup_move(scratch)
        setup.append("c")
        setup.extend(["i"] * gate_len)
        setup.append("n")  # push gate_len
        setup_move(i)
        setup.append("s")
        setup.extend(gate)

    setup_move(index)
    setup.append("c")  # index starts at zero
    cells: list[tuple[int, int]] = list(skip_vals.items())
    cells.append((sentinel, _ASCII_ZERO))
    for j in range(k):
        cells.append((tbase + j, _ASCII_ZERO + int(table[j])))
    cells.sort(key=lambda cv: cv[1])
    # The sentinel is appended unconditionally above, so there is always at
    # least one cell to walk here.
    if cells:  # pragma: no branch - the sentinel keeps this non-empty
        first_addr, first_value = cells[0]
        setup_move(first_addr)
        setup.extend(["i"] * first_value)
        prev_value = first_value
        for addr, value in cells[1:]:
            setup.append("n")
            setup_move(addr)
            setup.append("f")
            diff = value - prev_value
            setup.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
            prev_value = value
    setup_move(index)

    return "".join(setup + commands)
