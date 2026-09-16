"""Boolean-function generator for NoComment."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

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

    The narrow generator lands the pointer on ``table[index]`` with one
    ``s`` whose skip amount *is* the index, which caps it at ``n == 8``, and
    the wide generator it used to hand off to put the ``2**n`` output cells
    on the tape, which the static 4096-cell tape capped at ``n == 12``.
    This puts nothing per row on the tape.  The rows live in the *code*, the
    index lives on the *stack*, and the tape holds six cells for any ``n``.

    As in the narrow decode, a table that ignores some inputs is evaluated
    over the essential ones: every input keeps its ``{Xi}`` setter, and an
    ignored one pushes no stage, so the rows and stages are those of the
    smaller table.

    *The stack is the index.*  The index is a sum of stage amounts, each at
    most a byte, pushed one per stage: bit ``i`` of weight ``W`` pushes
    ``W / 32`` full stages (or one stage of ``W`` when ``W < 32``), each
    holding ``6 * a + 4`` when the bit is one and ``4`` when it is zero.
    The bit's cells are dead once its stages are pushed, so every bit reuses
    the same six -- the tape never grows with ``n``.

    *The code is the table.*  After the prologue the program is a run of
    uniform six-command groups, ``f s f X X s``.  A stage lands on a group's
    first command with the pointer on ``G``: ``f`` pops the spent amount
    into ``G`` (nonzero, so the skip fires) and ``s`` skips the next amount
    -- ``6 * a + 4`` commands from the second position is exactly ``a + 1``
    groups.  The stack's last amount is the constant ``6``, which lands two
    commands *into* a group instead: that ``f`` pops the ``6`` into ``G``,
    the group's ``X X`` runs, and its final ``s`` skips the constant ``3``
    left on the stack -- which from the sixth position is the *next* group's
    ``X X``.  So the fall-through executes every later group's delta and
    nothing else: it pops nothing and lands nowhere a stage could.

    *The delta telescopes.*  Group ``m + 1 + j`` is row ``j`` and its
    ``X X`` is ``+2``, ``-2`` or ``0`` (``ii``, ``dd``, ``id``) for
    ``table[j] - table[j + 1]``, the row past the last counting as zero.
    Landing on row ``A`` therefore runs the deltas of rows ``A`` and after,
    which sum to ``table[A] - 0``: ``G`` reads ``6 + 2 * table[A]`` whatever
    fell through, and the epilogue maps ``{6, 8}`` to ``{48, 49}`` with one
    skip-guarded ``+1`` and prints it.  The first ``m + 1`` groups are pads
    a stage may land on, with zero deltas.

    Size is ``6`` commands per row plus ``T / 32`` stage pushes plus a
    fixed prologue per bit -- linear, and below the narrow decode from
    ``n == 4`` up.  Execution is one skip per stage, then three commands
    per group fallen through: ``O(T)`` commands.  The stack holds
    ``T / 32 + n + 3`` values at its deepest.
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

        The skip amount is pushed from ``scratch`` first and popped back into
        it after, on both paths, so the guard leaves the stack as it found it
        -- the stack below is the index under construction.
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
        out.append("{X" + str(i) + "}")
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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    NoComment has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a constant-length setter for each
    input bit, and the harness instantiates one program per input
    combination.  Unlike an earlier version of this generator, the complement
    is *not* embedded: NoComment's ``s`` (skip the next block iff the tested
    cell is nonzero) doubles as a NOT gate, since the skipped block only runs
    when the cell is zero.  A short runtime prologue pushes a fixed skip
    length, tests each raw bit cell, and increments a fresh complement cell
    in the skipped block -- so ``comp_i = 1 - bit_i`` is computed once per
    input from the embedded bit, with no ``{Ci}`` placeholder and no second
    embed.

    Rather than routing a decision tree, the program **computes the input's
    numeric index** and uses it as a byte-sized ``s`` skip into a staircase of
    ``l`` moves that land the pointer on a pre-loaded output cell holding
    ``48 + truth_table[index]``.  Each bit ``i`` contributes its weight
    (``2**w``) to the index cell only when the bit is one -- the guard tests
    the complement cell so the contribution is skipped when the bit is zero.
    The output is then a single ``o``.

    This is a straight-line program: no leaf chains, no interleaved stations,
    no placement.  A single ``s`` skip is byte-sized, so this narrow form
    needs the whole index to fit a byte -- a property of the *one-skip*
    decode, not of the language.  It is used only below
    ``_NOCOMMENT_CHAIN_MIN``, where it is the smaller program: from four
    inputs :func:`_nocomment_chain` pushes the index as a run of byte-sized
    skips and keeps the rows in the code, on six tape cells at any arity.
    """
    n = _validate_truth_table(truth_table)
    if n >= _NOCOMMENT_CHAIN_MIN:
        return _nocomment_chain(truth_table, n)

    # A table that ignores some of its inputs is a smaller table, and almost
    # everything here is sized by the *index range*: the staircase is one
    # ``l`` per row, and one output cell per row is preloaded and stepped
    # through in the setup's sorted climb.  Evaluating over the essential
    # inputs alone shrinks the dominant term from ``2**n`` to ``2**width``.
    #
    # Every input keeps its ``{Xi}`` setter and its NOT-gate prologue -- the
    # harness has a bit for each one -- and an ignored input costs only its
    # guarded increment's *run length*, which goes to zero: the weight is
    # ``["i"] * (2**w)``, a run this generator chooses, so a dropped input
    # contributes an empty run.  The guard still runs and still leaves the
    # pointer on its complement cell, so the emitted moves stay consistent.
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
    # by the NOT-gate prologue below, not by a {Ci} placeholder.
    setup: list[str] = []
    setup_ptr = [0]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    for i in range(n):
        setup.append("{X" + str(i) + "}")
        setup.append("r")
    setup_ptr[0] = n

    # NOT-gate prologue: for each bit i, comp_i = 1 - bit_i.  ``s`` at the
    # bit cell skips a fixed-length block (move to comp_i, set it, move back)
    # exactly when the bit is nonzero, so the block runs -- and increments
    # the complement cell -- only when the bit is zero.  Both the skip and
    # fall-through paths leave the pointer back on the bit cell, so the
    # next bit's prologue starts from a known position.
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
