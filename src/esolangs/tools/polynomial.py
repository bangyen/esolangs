"""Boolean-function generator for Polynomial.

The algebra that turns a program into a polynomial is
:mod:`esolangs.tools._polynomial`; this is the construction that decides
which instructions to encode.

**Every instruction is priced by its opcode.**  A complex instruction
``[a, b]`` is the factor ``(x - a)**2 + p**(2*b)`` and a real one ``[v]`` is
``x - p**v``, so the digits a program spends on an instruction grow with
``2*b`` or ``v`` times ``log p``.  The opcodes are not equally priced:
``+=`` is ``b == 1``, ``-=`` is 2, ``*=`` 3, ``//=`` 4; ``if > 0`` is
``v == 1``, ``endif`` 2, ``if < 0`` 3, ``if == 0`` 4.  Every construction
here therefore spells subtraction as ``+=`` with a negative operand, tests
with ``if > 0`` only, and keeps ``*=`` and ``//=`` for the two places
nothing cheaper reaches.  Against the previous builder (``-= 1; if == 0``
chains, ``-= 48`` reads) the dense fixtures render 1.9x shorter at n == 6
and 2.1x at n == 7, every row executed; the count of instructions also
falls, since the chain's ``-= offset`` and the read's ``-= 48`` are gone.
"""

from typing import Any

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

# Largest instruction count :func:`polynomial` will emit.  Each instruction
# contributes a factor, so the polynomial's degree -- and the cost of
# recovering the instructions from it -- tracks this count and nothing else.
#
# The analytic worst case over n == 10 tables is now 1659: level ``k`` of
# the machine holds at most ``min(2**k, 2**2**(10 - k))`` states at 6
# instructions each (3 of chain, a read, one map, one park), the root level
# 3, and the two leaves 6 each -- ``3 + 6*274 + 12``.
# ``test_polynomial_cap_admits_every_n10_table`` re-derives it.  The bound
# stays at the 1934 the previous builder's worst case set, because that is
# a price the interpreter was measured to afford (n=8, 541 instructions,
# 3.5s for all 256 rows; n=10, 1638, 44s for all 1024) and a cheaper
# per-state spelling is no reason to refuse a table that fit before.
#
# The count, not the arity, is what this measures: a table that collapses
# to few states is cheap at any width, and parity renders far past n == 10
# inside the bound.  Past it, dense n=11 (2910 instructions under the old
# builder) built and ran all 2048 rows in 267s, 264.5s of it the one
# factorization, for a 123609143-character program.
_POLYNOMIAL_MAX_INSTRS = 1934


# How far above the cheapest candidate the dispatch still renders.  Selection
# is on characters, so the instruction count only screens -- and a strict
# screen picks wrong, because the two disagree: a longer program's later
# instructions consume larger primes, and here a ``*=`` costs three times
# the digits of a ``+=``.
#
# The slack has to be measured per arity, not guessed: every table at
# n <= 3 needs at most 1, but 2000 sampled tables at n == 4 reach 6.  Held
# at 10, the margin the previous builder's n == 4 worst case (9) set, so a
# table needing more is a real finding rather than a quiet regression;
# ``test_polynomial_screen_slack`` re-derives the n <= 3 figure.
_POLYNOMIAL_SCREEN_SLACK = 10


def polynomial(truth_table: str) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Polynomial programs are polynomials whose roots encode instructions, so
    both constructions below emit complex ``[a, b]`` (arithmetic, input,
    output) and real ``[v]`` (if/endif) roots that expand into
    ``f(x) = ...``.  The program's size and the interpreter's factorization
    cost both track the *instruction count* -- which is what the two
    constructions compete on -- and the digits per instruction track the
    opcode, which is why every construction spells itself on the cheapest
    ones (see the module docstring).

    Every construction here is :func:`_polynomial_hybrid` at some ``k``:
    ``k == n`` branches every bit and never reaches a machine (a plain
    decision tree, collapsing a constant subtable to its output), ``k == 0``
    hands the whole table to one machine, and the interior branches ``k``
    bits and gives each surviving residual its own machine.  The reduced
    variants prepend a drain for a leading run of ignored inputs and rebuild
    on the smaller table.

    The machine merges any two prefixes with the *same residual
    subfunction* rather than only constant ones -- an ordered BDD where the
    tree is a plain tree.  That merge is strictly stronger than the fold and
    the gap grows with ``n``: parity is the tree's worst case at every width
    (``2**n - 1`` internal nodes) and needs just two states per level, so
    ``k == 0`` is *linear* there -- 11 instructions per input.  Small or
    near-constant tables still favour the tree end.

    The interior is where neither endpoint serves: a table whose residuals
    merge *within* a top-level split but not *across* it defeats both, since
    the tree cannot merge them at all and the machine pays a full state level
    for the split.

    **The order the tree tests its inputs in is not free here**, unlike
    every other decision-tree generator: a read *assigns* to the single
    register, so nothing survives it and the tested bit is always the one
    just read.  Every construction consumes input in stream order, so
    reordering is unreachable rather than merely unhelpful.  What the machine
    recovers is the *saving* a reorder would have bought -- the residual
    merge subsumes the folds a better order would have exposed.

    Selection is on *rendered characters* rather than instruction count,
    because the two disagree; the count screens which candidates are worth
    rendering.  See the dispatch below.

    A table needing more than ``_POLYNOMIAL_MAX_INSTRS`` instructions under
    both constructions raises :class:`ValueError`: the interpreter recovers
    instructions by factoring the polynomial, and that is what becomes
    impractical.  The bound is on instructions rather than on ``n``, but it
    is sized so every n == 10 table fits; a table that collapses to few
    states renders at any width beyond that.
    """
    n = _validate_truth_table(truth_table)

    # Every construction here is :func:`_polynomial_hybrid` at some ``k``.
    # ``k == n`` is the plain decision tree, ``k == 0`` the plain state
    # machine, and the interior splits the difference; the reduced variants
    # below prepend a drain and rebuild on a smaller table.
    builders: list[tuple[int, Any]] = [
        (
            _polynomial_hybrid_cost(truth_table, level),
            lambda level=level: _polynomial_hybrid(truth_table, level),
        )
        for level in range(n, -1, -1)
    ]

    # A table that ignores some of its inputs is a smaller table, and this
    # generator cannot get there on its own: a read *assigns* to the single
    # register, so the construction consumes inputs in stream order and an
    # ignored one still costs a full level of branching before reaching the
    # input that matters.  Folding collapses subtrees, not the levels above
    # them.
    #
    # Reduction sidesteps that because it is *order-blind*: it rewrites the
    # table before anything is built.  The ignored inputs are drained first,
    # so every path still consumes exactly ``n`` inputs.  Only a *leading*
    # run can be handled this way -- an ignored input sitting after an
    # essential one would be drained out of turn and the build would branch
    # on the wrong bit (measured: 92 wrong rows over 26 tables).
    #
    # A drain is one bare read: the next instruction on every path is
    # itself a read, which overwrites the register, so nothing needs to be
    # subtracted away.
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if lead:
        prefix: list[list[int]] = [[0, 2]] * lead
        reduced = read_at(truth_table, list(range(lead, n)), n)
        reduced_n = n - lead
        builders += [
            (
                len(prefix) + _polynomial_hybrid_cost(reduced, level),
                lambda level=level, r=reduced, pre=prefix: (
                    pre + _polynomial_hybrid(r, level)
                ),
            )
            for level in range(reduced_n, 0, -1)
        ]
        drained = _polynomial_drained_dag_cost(truth_table)
        # Only reached inside ``if lead:``, and the cost is None only when
        # there is no lead to drain, so it always answers here.
        if drained is not None:  # pragma: no branch
            builders.append((drained, lambda: _polynomial_drained_dag(truth_table)))

    fits = [(cost, build) for cost, build in builders if cost <= _POLYNOMIAL_MAX_INSTRS]
    if not fits:
        raise GeneratorCapError(
            "the Polynomial boolean generator emits one instruction per "
            f"prime and caps at {_POLYNOMIAL_MAX_INSTRS}, but this table "
            f"needs {min(cost for cost, _ in builders)} under its cheapest "
            "construction, which costs more per row than checking a table "
            "of this width can afford",
        )

    # Selection is on *rendered characters*, because instructions and
    # characters disagree: a longer program's later instructions consume
    # larger primes, and the opcodes are not equally priced.
    #
    # So the instruction count only screens: a candidate more than
    # ``_POLYNOMIAL_SCREEN_SLACK`` above the cheapest cannot win and is not
    # built.  The screen is a measured bound, not a proof: a candidate
    # rendering shorter from a further-out instruction count would be
    # skipped.
    #
    # ``k`` descends so the tree is tried first, and the comparison is
    # strict, so a table nothing shortens emits what it always emitted.
    cheapest = min(cost for cost, _ in fits)
    program: str | None = None
    for cost, build in fits:
        if cost > cheapest + _POLYNOMIAL_SCREEN_SLACK:
            continue
        candidate = _polynomial_assemble(build())
        if program is None or len(candidate) < len(program):
            program = candidate
    if program is None:  # pragma: no cover - the cheapest member always fits
        raise AssertionError(
            "the Polynomial screen dropped every candidate, which the "
            "cheapest member cannot do",
        )
    return program


def _polynomial_decode_key(instr: list[int]) -> tuple[int, int]:
    """Return where ``convert`` places ``instr`` among the roots of one prime.

    The interpreter walks the primes upward and, within a prime, takes its
    roots sorted by ``(imag, real)``: real roots ``p**v`` first in exponent
    order, then complex ``a + p**b i`` by ``b`` and then by ``a``.
    """
    if len(instr) == 1:
        return (0, instr[0])
    return (instr[1], instr[0])


def _polynomial_assemble(instrs: list[list[int]]) -> str:
    """Expand an instruction list into its ``f(x) = ...`` polynomial.

    A complex instruction ``[a, b]`` contributes ``(x - a)**2 + p**(2*b)``
    and a real one ``[v]`` contributes ``x - p**v``, so the roots the
    interpreter factors back out are exactly the instructions.

    **Consecutive instructions share a prime when their decode order is
    their program order.**  The interpreter orders instructions by prime and,
    within one prime, by :func:`_polynomial_decode_key`; a run whose keys
    never decrease therefore reads back in the order it was written whether
    it sits on one prime or on several.  Each shared prime is one fewer
    prime consumed, so every later instruction's constant shrinks: measured
    on dense n=5..8 machines the text falls 14%, 12%, 11%, 10% (the gain
    thins as ``log p`` grows past the ``log 2`` a halved prime saves).
    A machine block's ``if > 0; input; *= span`` is one such run and its
    ``endif; += 1`` another, so a block spends three primes, not six.
    """
    from esolangs.tools._polynomial import primes, render_product

    groups: list[list[list[int]]] = []
    for instr in instrs:
        if groups and _polynomial_decode_key(groups[-1][-1]) <= _polynomial_decode_key(
            instr
        ):
            groups[-1].append(instr)
        else:
            groups.append([instr])
    factors: list[list[int]] = []
    for group, p in zip(groups, primes(len(groups)), strict=True):
        for instr in group:
            if len(instr) == 2:
                a, b = instr
                factors.append([1, -2 * a, a * a + p ** (2 * b)])
            else:
                factors.append([1, -(p ** instr[0])])
    # The expansion is the whole cost past n == 7 -- the factor count is the
    # degree, and multiplying them in one incremental sweep rescans a
    # polynomial whose coefficients keep growing.  ``render_product`` cuts
    # the list into groups and merges them packed; see there.
    return str(render_product(factors))


def _polynomial_states(truth_table: str, n: int) -> list[list[str]]:
    """Return the distinct residual subfunctions at each level.

    Level ``k``'s states are the distinct subtables of width ``2**(n-k)``
    reachable after reading ``k`` bits.  Two prefixes that leave the same
    subtable are the *same* state and share one continuation -- the merge a
    decision tree cannot make, since it can only collapse a constant
    subtable.
    """
    levels = [[truth_table]]
    for k in range(n):
        width = 2 ** (n - k - 1)
        nxt: list[str] = []
        for state in levels[k]:
            for half in (state[:width], state[width:]):
                if half not in nxt:
                    nxt.append(half)
        levels.append(nxt)
    return levels


def _polynomial_labels(levels: list[list[str]], n: int) -> list[dict[str, int]]:
    """Label each level's states so a parent's children sit one apart.

    A block maps its read bit to a child index with ``*= span`` where
    ``span`` is the zero child's index less the one child's; a span of 1
    needs no multiply at all, and ``*=`` is the dearest opcode a block
    carries (``p**6`` against ``p**2`` for the ``+=`` that follows).  So the
    labels are chosen, greedily, to make ``zero == one + 1`` for as many
    parents as the level allows: each parent asks for its one child to be
    followed by its zero child, the request is granted when neither slot is
    taken and it closes no cycle, and the chains are then numbered in level
    order.  Measured on dense n=6..8 machines, 8, 13 and 30 spans survive
    against 31, 50 and 82 blocks.
    """
    index = [{state: i for i, state in enumerate(level)} for level in levels]
    for k in range(n):
        width = 2 ** (n - k - 1)
        follows: dict[str, str] = {}  # one child -> the zero child after it
        precedes: dict[str, str] = {}
        for state in levels[k]:
            zero, one = state[:width], state[width:]
            if zero == one or one in follows or zero in precedes:
                continue
            cursor, closes = zero, False
            while cursor in follows:
                cursor = follows[cursor]
                if cursor == one:
                    closes = True
                    break
            if closes:
                continue
            follows[one] = zero
            precedes[zero] = one
        labels: dict[str, int] = {}
        for state in levels[k + 1]:
            if state in precedes:
                continue
            cursor = state
            while True:
                labels[cursor] = len(labels)
                if cursor not in follows:
                    break
                cursor = follows[cursor]
        index[k + 1] = labels
    return index


def _polynomial_dag_cost(truth_table: str) -> int:
    """Return :func:`_polynomial_dag`'s instruction count.

    Counted by building: the build is linear in the states and the render
    is what costs, so nothing is saved by pricing it separately -- and a
    separate mirror would drift on the labelling.
    """
    return len(_polynomial_dag(truth_table))


def _polynomial_dag(truth_table: str, park: int | None = None) -> list[list[int]]:
    """Emit the state-machine instructions; see :func:`polynomial`.

    The register is the only storage and a read *assigns* to it, so nothing
    survives a read except the instruction cursor.  The state is therefore
    carried as *which branch is running*: a level is a chain of blocks, one
    per live state, and the block that fires reads its bit and moves to the
    child state's index.

    **The chain counts up from a negative index and tests ``if > 0``.**  A
    level is entered with the register at ``-i`` for state ``i``; every
    block does ``+= 1`` and tests ``> 0``, so block ``i`` is the first to
    see a positive register.  Its body parks the register at
    ``-(child + remaining)``, where ``remaining`` is the number of blocks
    still to come: their increments bring it to exactly ``-child`` and never
    above zero, so no later block fires and the next level is entered in
    the same convention.  ``if > 0`` is the cheapest test there is
    (``x - p``, where ``if == 0`` is ``x - p**4``) and ``+= 1`` the
    cheapest arithmetic; the previous chain's ``-= 1; if == 0`` cost
    ``p**4`` twice per block.  The root level has one state and no chain.

    **The read is mapped in one or two instructions.**  The register holds
    ``48 + bit`` after a read; when the children differ by ``span =
    zero - one`` the block does ``*= span`` then ``+= park - 48*span``,
    and when ``span == 1`` (which :func:`_polynomial_labels` arranges as
    often as it can) the multiply goes.  Children that merge, so the bit
    cannot change the answer, are read and divided away (``//= 50``); a
    ``*= 0`` is not an option, because ``[0, b]`` is how the interpreter
    spells I/O -- the same trap makes a zero park a *skip* rather than an
    instruction, since ``[0, 1]`` would print.

    The leaf states are one-wide subtables, so each *is* its answer: its
    block steps the register (at 1 inside the test) to the digit, prints,
    and parks at or below ``-park`` so that any tree arms enclosing the
    machine, each adding at most one on its way out, never see a positive
    register.  ``park`` defaults to two past the table's width.

    Exactly one branch fires per level, and every branch reads once, so each
    path consumes ``n`` inputs by construction rather than by draining.
    """
    n = _validate_truth_table(truth_table)
    if park is None:
        park = n + 2
    levels = _polynomial_states(truth_table, n)
    index = _polynomial_labels(levels, n)
    instrs: list[list[int]] = []

    for k in range(n):
        width = 2 ** (n - k - 1)
        states = sorted(levels[k], key=index[k].__getitem__)
        chained = len(states) > 1
        for j, state in enumerate(states):
            if chained:
                instrs.append([1, 1])  # += 1
                instrs.append([1])  # if reg > 0
            remaining = len(states) - 1 - j
            zero = index[k + 1][state[:width]]
            one = index[k + 1][state[width:]]
            target = -(zero + remaining)
            instrs.append([0, 2])  # input -> 48 + bit
            if zero == one:
                instrs.append([_ASCII_ZERO + 2, 4])  # //= 50 -> 0
                if target:
                    instrs.append([target, 1])
            else:
                span = zero - one
                if span != 1:
                    instrs.append([span, 3])  # *= span, never zero here
                if delta := target - _ASCII_ZERO * span:
                    instrs.append([delta, 1])
            if chained:
                instrs.append([2])  # endif

    leaves = sorted(levels[n], key=index[n].__getitem__)
    for state in leaves:
        value = _ASCII_ZERO + int(state)
        if len(leaves) > 1:
            instrs.append([1, 1])  # += 1
            instrs.append([1])  # if reg > 0, entered holding 1
            instrs.append([value - 1, 1])
        else:
            # A constant table: every level merged, so the register is 0.
            instrs.append([value, 1])
        instrs.append([0, 1])  # output
        instrs.append([-(value + park), 1])  # park below every enclosing test
        if len(leaves) > 1:
            instrs.append([2])  # endif

    for instr in instrs:
        # ``a == 0`` is how the interpreter spells I/O, so an arithmetic
        # instruction computing a zero operand would silently become a read
        # -- a wrong program rather than a failure.  The builder never emits
        # one; this raises rather than asserting so the guard survives
        # ``-O``, where the trap it catches would be silent.
        if len(instr) == 2 and instr[0] == 0 and instr not in ([0, 1], [0, 2]):
            raise AssertionError(
                f"{instr} has a zero operand, which the interpreter reads as "
                "I/O rather than arithmetic",
            )
    return instrs


def _polynomial_hybrid(truth_table: str, k: int) -> list[list[int]]:
    """Emit ``k`` tree levels above a state machine per surviving residual.

    This is the whole construction family, not a third option beside two
    others.  ``k == n`` never reaches the machine and emits exactly what a
    plain decision tree emits; ``k == 0`` hands the whole table to one
    machine.  Between them the tree branches the top ``k`` bits and each
    surviving residual gets its own machine.

    The endpoints are worth having as one function because the interior is
    where the wins are.  The tree cannot merge two prefixes leaving the same
    residual; the machine pays for a level of states even where the table's
    top split is the only structure there is.  A table whose residuals merge
    *within* a top-level split but not *across* it is served by neither.

    **The tree tests ``if > 0`` twice.**  A node reads, subtracts 48 and
    branches ``if > 0`` into the one-bit arm; every arm leaves the register
    at or below ``-(n + 2)`` on its way out (a leaf parks there, a machine's
    leaves park there), so ``+= 1; if > 0`` afterwards fires exactly for the
    zero bit -- at ``p`` and ``p**2`` where ``if == 0`` costs ``p**4``.
    Each level out adds one, so the deepest arm's park still clears the
    top.  Both arms are entered holding 1.

    The machine needs no splice: its root level has no chain and opens with
    a read, so whatever the arm holds is overwritten.
    """
    n = _validate_truth_table(truth_table)
    instrs: list[list[int]] = []
    park = n + 2

    def build(rows: list[int], bit: int, last: int) -> None:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            # ``last`` is 0 or 1 and the digit is 48 or 49, so neither
            # operand here can be the zero that would spell I/O.
            instrs.append([_ASCII_ZERO + v - last, 1])
            instrs.append([0, 1])  # output
            # Drain the reads the untaken siblings would have made, after
            # printing so they cannot disturb the value; a bare read is
            # enough, since the park below overwrites what it left.
            for _ in range(bit, n):
                instrs.append([0, 2])
            instrs.append([-(_ASCII_ZERO + 1 + park), 1])
            return
        if bit == k:
            instrs.extend(_polynomial_dag("".join(truth_table[r] for r in rows), park))
            return
        instrs.extend([[0, 2], [-_ASCII_ZERO, 1]])  # input; += -48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([1, 1])  # += 1: a zero bit is now 1, a taken arm <= -1
        instrs.append([1])  # if reg > 0
        build(g0, bit + 1, 1)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs


def _polynomial_drained_dag(truth_table: str) -> list[list[int]] | None:
    """Drain a leading run of ignored inputs, then run the machine.

    The reduction the tree gets above is available to the machine too.  A
    drain is one bare read per ignored input: the machine's root level
    opens with a read of its own, so the drained byte is never looked at.

    Returns ``None`` when no input is ignored, or when the reduction leaves
    a single row (a constant, which the tree already spells cheaply).
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if not lead:
        return None
    reduced = read_at(truth_table, list(range(lead, n)), n)
    # Exhausted over every table to four inputs: a nonzero lead leaves an
    # essential input behind, so the reduction always holds two rows.
    if len(reduced) < 2:  # pragma: no cover - see above
        return None
    return [[0, 2]] * lead + _polynomial_dag(reduced, n + 2)


def _polynomial_drained_dag_cost(truth_table: str) -> int | None:
    """Return :func:`_polynomial_drained_dag`'s instruction count."""
    built = _polynomial_drained_dag(truth_table)
    return None if built is None else len(built)


def _polynomial_hybrid_cost(truth_table: str, k: int) -> int:
    """Return :func:`_polynomial_hybrid`'s instruction count.

    Counted by building, for the reason :func:`_polynomial_dag_cost` gives;
    ``test_polynomial_hybrid_cost_mirrors_build`` keeps the two equal.
    """
    return len(_polynomial_hybrid(truth_table, k))
