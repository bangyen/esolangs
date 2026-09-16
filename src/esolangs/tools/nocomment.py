"""Boolean-function generator for NoComment."""

from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.tape_based.nocomment import _TAPE
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
# decode below stops working and :func:`_nocomment_wide` takes over.  It is
# the largest ``n`` with ``2**n - 1 <= _NOCOMMENT_SKIP_MAX``.
_NOCOMMENT_NARROW_MAX = (_NOCOMMENT_SKIP_MAX + 1).bit_length() - 1


def _nocomment_summand_plan(n: int, room: int) -> list[list[tuple[int, int]]]:
    """Split the index's bit weights into cells that cannot overflow a byte.

    The index is ``sum(2**(n-1-i) for i where bit i is one)``, which exceeds
    a byte past ``n == 8``.  Splitting it into *summands* rather than digits
    keeps every part byte-sized and keeps each part a plain sum of per-bit
    contributions, so each contribution stays a guarded increment.

    Returns one list of ``(bit, amount)`` pairs per summand cell.  A cell's
    amounts total at most ``_NOCOMMENT_SKIP_MAX``, so no input can push it
    past a byte, and each single contribution is at most ``room`` so the
    guarded block that adds it stays within one skip.
    """
    parts: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    total = 0
    for i in range(n):
        remaining = 2 ** (n - 1 - i)
        while remaining:
            if total == _NOCOMMENT_SKIP_MAX:
                parts.append(current)
                current, total = [], 0
            take = min(remaining, _NOCOMMENT_SKIP_MAX - total, room)
            current.append((i, take))
            total += take
            remaining -= take
    # Each pass appends to ``current`` before it can be flushed, so the only
    # way to arrive here empty is a table with no inputs -- which
    # ``_validate_truth_table`` rejects before any caller gets this far.
    if current:  # pragma: no branch - n == 0 never reaches the planner
        parts.append(current)
    return parts


def _nocomment_wide(truth_table: str, n: int, tape: int) -> str:
    """Build a NoComment template for a table too wide for one byte-sized skip.

    The narrow generator lands the pointer on ``table[index]`` with a single
    ``s`` whose skip amount *is* the index, which caps it at ``n == 8``.
    Nothing about the language caps it there, because **skips compose**.  Two
    compositions do the work:

    *Chained guards.*  ``s`` peeks the stack rather than popping it and does
    not move the pointer, so after a skip fires the guard cell is still under
    the pointer and still nonzero.  A guarded region of any length is then a
    run of chunks, each at most ``_NOCOMMENT_SKIP_MAX`` commands and each
    preceded by glue that rebuilds the chunk's length and re-tests the same
    guard.  Every chunk ends with the pointer back on the guard, so the glue
    -- which runs on both paths -- is emitted from one known position.

    *Additive staircases.*  Entering a staircase of ``L`` copies of ``l`` by
    skipping ``c`` runs ``L - c`` of them, so pre-walking ``L`` right and
    then skipping ``c`` is a net move of ``+c``.  Displacements add across
    consecutive staircases, so a displacement far past 255 is reached by
    ``q`` stages whose skip amounts sum to it, each stage's amount held in
    its own byte-sized summand cell.

    Between stages the stack top must advance, and ``f`` is the only way to
    pop -- it writes the popped value into the cell under the pointer.  That
    clobber is harmless because it always lands mid-corridor: a **constant**
    trailing summand of ``1`` is appended so the final landing is strictly
    right of every clobbered cell, which is what makes the all-zero input
    (every input-driven summand zero) come out right.

    What binds instead is the tape.  The layout needs the ``2**n`` output
    cells plus an apron of nonzero cells for the stages' guards to test, and
    the wiki requires the memory space to be static, so the generator refuses
    when the top cell it needs does not fit in ``tape``.  The wiki does not
    specify a *size*, though, so that bound is the interpreter's configuration
    rather than a property of the language: pass a larger ``tape`` here and run
    the program on an interpreter given the same size.
    """
    cap = _NOCOMMENT_SKIP_MAX
    k = 2**n
    comp_base = n  # comp_i = 1 - bit_i
    sbase = 2 * n  # the summand cells

    # The furthest summand cell sets how long a guarded contribution's
    # move-add-return block is, which sets how much of one contribution fits
    # in a single skip.  Planning with the worst-case distance keeps every
    # emitted skip within a byte without a second pass.
    plan = _nocomment_summand_plan(n, 1)
    span = len(plan) + 1
    room = cap - 2 * (sbase + span - 1 - comp_base)
    if room > 0:
        plan = _nocomment_summand_plan(n, room)
    q = len(plan) + 1  # the input-driven summands plus the constant one
    scratch = sbase + q
    base = scratch + 1
    apron = base + k
    # Each stage pre-walks a full staircase right of its landing cell before
    # testing, so the guard apron must cover one staircase past the table,
    # and the walk itself reaches one staircase past that.
    top = apron + 2 * cap + 1
    if top >= tape:
        raise GeneratorCapError(
            f"the NoComment boolean generator needs cell {top} for n == {n}, "
            f"past the interpreter's {tape}-cell tape"
        )

    out: list[str] = []
    ptr = [0]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            out.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            out.append("l")
            ptr[0] -= 1

    def guarded(guard: int, chunks: list[list[str]]) -> None:
        """Emit a region that runs iff ``guard`` is zero, chunked to fit skips.

        Each chunk must start and end with the pointer on ``guard``.  The
        glue rebuilds the chunk's length in ``scratch``, pushes it, returns
        to the guard, and skips -- so the skip path never leaves the guard
        and the fall-through path is returned there by the chunk itself.
        """
        for chunk in chunks:
            move(scratch)
            out.append("c")
            out.extend(["i"] * len(chunk))
            out.append("n")
            move(guard)
            out.append("s")
            out.extend(chunk)
            ptr[0] = guard

    for i in range(n):
        out.append("{X" + str(i) + "}")
        out.append("r")
    ptr[0] = n

    # comp_i = 1 - bit_i: the block runs exactly when bit i is zero.
    for i in range(n):
        dist = comp_base + i - i
        guarded(i, [["r"] * dist + ["i"] + ["l"] * dist])

    for j in range(q):
        move(sbase + j)
        out.append("c")

    # The output table, then an apron of nonzero cells so every stage's
    # pre-walk lands on a truthy guard.  Both are constants, so they go
    # through one sorted diff chain: sorting by value makes each step a
    # single push/pop plus the difference from the previous value.
    cells: list[tuple[int, int]] = [
        (base + j, _ASCII_ZERO + int(truth_table[j])) for j in range(k)
    ]
    cells += [(apron + t, _ASCII_ZERO) for t in range(2 * cap + 1)]
    cells.sort(key=lambda cv: cv[1])
    first_addr, first_value = cells[0]
    move(first_addr)
    out.extend(["i"] * first_value)
    prev_value = first_value
    for addr, value in cells[1:]:
        out.append("n")
        move(addr)
        out.append("f")
        diff = value - prev_value
        out.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
        prev_value = value

    # Bit i adds its share to each summand cell it feeds.  The guard is the
    # complement, so the block runs exactly when the bit is one.
    for j, part in enumerate(plan):
        cell = sbase + j
        for i, amount in part:
            guard = comp_base + i
            dist = cell - guard
            chunks = []
            remaining = amount
            while remaining:
                take = min(remaining, cap - 2 * dist)
                chunks.append(["r"] * dist + ["i"] * take + ["l"] * dist)
                remaining -= take
            guarded(guard, chunks)

    move(sbase + q - 1)
    out.append("c")
    out.append("i")  # the constant trailing summand

    # Push the summands so the first stage sees the first one on top.
    for j in reversed(range(q)):
        move(sbase + j)
        out.append("n")

    # The trailing summand contributes the final ``+1``, so the walk starts
    # one cell left of the table and ends on ``base + index``.
    move(base - 1)
    for j in range(q):
        if j:
            # Advance the stack top.  ``f`` writes the popped summand into
            # the cell under the pointer, which is always a corridor cell at
            # least one staircase left of any cell a later stage tests.
            out.append("f")
        out.extend(["r"] * cap)
        out.append("s")
        out.extend(["l"] * cap)
    out.append("o")
    return "".join(out)


def nocomment(truth_table: str, tape: int = _TAPE) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ``tape`` is the cell count the emitted program is allowed to use; it
    defaults to the interpreter's own default, so a program built here runs
    on a default interpreter.  Raising it lifts the arity bound (``n == 12``
    needs 4650 cells), but the runner must then be given the same size.

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
    needs the whole index to fit a byte and works through ``n == 8`` -- a
    property of the *one-skip* decode, not of the language: past eight inputs
    :func:`_nocomment_wide` composes several byte-sized skips instead, and
    the binding constraint becomes the tape size.
    """
    n = _validate_truth_table(truth_table)
    if n > _NOCOMMENT_NARROW_MAX:
        return _nocomment_wide(truth_table, n, tape)

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
