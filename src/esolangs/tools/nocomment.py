"""Boolean-function generator for NoComment.

Every row owns a landing site for the index skip, so a constant half or repeat
has no subtree to fold or share.
"""

from collections.abc import Callable

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape
from esolangs.tools.constant_projection import balanced_projection, projected_inputs
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    TEMPLATE_CHAR,
    _validate_truth_table,
    move_text,
    read_at,
)
from esolangs.tools.wrap import wrap_chars

#: How each input is set: ``c`` clears the cell for a zero, ``i`` increments
#: it to one.  The template spells each input as a run of
#: :data:`TEMPLATE_CHAR` this wide.
PAIR = ("c", "i")
_NOCOMMENT_INPUT = TEMPLATE_CHAR * len(PAIR[0])


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


def _projected(
    truth_table: str, n: int, *, keep_constant_input: bool = False
) -> tuple[str, int, dict[int, int]]:
    """Return the essential-input table, its width, and weight by input."""
    used = projected_inputs(truth_table, n, keep_constant_input=keep_constant_input)
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    return table, width, {i: 1 << (width - 1 - s) for s, i in enumerate(used)}


def _mover(buf: list[str], pos: int) -> Callable[[int], None]:
    """Return a ``move(dst)`` appending ``r``/``l`` runs to ``buf`` from ``pos``."""

    def move(dst: int) -> None:
        nonlocal pos
        buf.append(move_text(pos, dst, "r", "l"))
        pos = dst

    return move


def _push(k: int) -> str:
    """Return the commands pushing ``k`` from a cleared current cell."""
    return "c" + "i" * k + "n"


def _group(delta: int) -> str:
    return "fsf" + {1: "ii", -1: "dd", 0: "id"}[delta] + "s"


def _nocomment_chain(
    truth_table: str, n: int, *, keep_constant_input: bool = False
) -> str:
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
    table, width, weights = _projected(
        truth_table, n, keep_constant_input=keep_constant_input
    )
    rows = 1 << width
    out: list[str] = []
    move = _mover(out, 0)
    bit, comp, stage, scratch, guard, const = range(6)

    def guarded(cell: int, block: list[str]) -> None:
        """Run ``block`` iff ``cell`` is zero, ending on ``cell``.

        Leaves the stack as it found it; below is the index under construction.
        """
        move(scratch)
        out.append(_push(len(block)))
        move(cell)
        out.append("s")
        out.extend(block)
        move(scratch)
        out.append("f")
        move(cell)

    # The two constants under everything: the fall-through's skip of three
    # (deepest, so it is what remains) and the final stage's landing six.
    move(const)
    out.append(_push(3) + "iiin")

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
        out.append(_push(4)[:-1])
        # stage = 4 + 6 * advance exactly when the bit is one.
        guarded(comp, ["r", *(["i"] * (_NOCOMMENT_GROUP * advance)), "l"])
        move(stage)
        out.extend(["n"] * count)
        stages += count

    # The first group pops before it skips, so a nonzero dummy goes on top.
    move(const)
    out.append(_push(4))
    move(guard)

    out.extend(_group(0) for _ in range(stages + 1))
    for j in range(rows):
        after = int(table[j + 1]) if j + 1 < rows else 0
        out.append(_group(int(table[j]) - after))

    # The last group's skip of three lands past it, on three dead commands.
    out.append("sss")
    # G is 6 or 8: down to {0, 2}, then +1 only when zero -> {1, 2}, then +47.
    out.extend(["d"] * 6)
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
    return _program(truth_table)


def _program(truth_table: str, *, keep_constant_input: bool = False) -> str:
    """Build the indexed template, including a one-entry constant table."""
    n = _validate_truth_table(truth_table)
    if n >= _NOCOMMENT_CHAIN_MIN:
        return _nocomment_chain(truth_table, n, keep_constant_input=keep_constant_input)

    # Sized by the essential inputs (one ``l`` and one output cell per row).
    # An ignored input keeps its setter and prologue but takes no weight.
    table, width, weights = _projected(
        truth_table, n, keep_constant_input=keep_constant_input
    )

    k = 2**width
    index = 2 * n
    skip_base = index + 1  # one skip cell per input bit
    tbase = skip_base + n  # the output cells
    sentinel = tbase + k  # non-zero cell the final ``s`` gates on
    scratch = sentinel + 1  # reused per bit to push each NOT gate's skip length

    commands: list[str] = []
    move = _mover(commands, index)

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
        skip_vals[d] = len("".join(commands[block:]))
    move(index)
    commands.append("n")  # push the index
    move(sentinel)
    commands.append("s")  # skip by the index into the staircase
    commands.extend(["l"] * k)
    commands.append("o")

    # Setup: bits, complements, index, skip cells, output cells, sentinel,
    # scratch.  The complement cells (n..2n-1) start at zero and are filled
    # by the NOT-gate prologue below, not by a second embedded run.
    setup: list[str] = []
    setup_move = _mover(setup, n)
    setup.append((_NOCOMMENT_INPUT + "r") * n)

    # NOT-gate prologue: ``s`` at the bit cell skips the block that
    # increments comp_i, so it runs only when the bit is zero.
    for i in range(n):
        gate = "r" * n + "i" + "l" * n  # comp is always n right of bit i
        setup_move(scratch)
        setup.append(_push(len(gate)))
        setup_move(i)
        setup.append("s" + gate)

    setup_move(index)
    setup.append("c")  # index starts at zero
    cells: list[tuple[int, int]] = list(skip_vals.items())
    cells.append((sentinel, _ASCII_ZERO))
    for j in range(k):
        cells.append((tbase + j, _ASCII_ZERO + int(table[j])))
    cells.sort(key=lambda cv: cv[1])
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


def balance_nocomment(truth_table: str, default: str) -> str:
    """Retain the legacy constant layout when it balances better."""
    return balanced_projection(
        default, _program(truth_table, keep_constant_input=True), "nocomment"
    )


LANGUAGE = Language(
    "NoComment",
    "tape_based.nocomment",
    weekly_mutation=("generator",),
    boolean=nocomment,
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(),
    wrap=wrap_chars,
    balance=balance_nocomment,
    example=Example(pair=PAIR),
)
