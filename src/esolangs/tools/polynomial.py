"""Boolean-function generator for Polynomial.

The algebra that turns a program into a polynomial is
:mod:`esolangs.tools._polynomial`; this is the construction that decides
which instructions to encode.
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
# consumes a fresh prime and contributes a factor, so the polynomial's degree
# -- and the cost of recovering the instructions from it -- tracks this count
# and nothing else.
#
# The bound is the analytic worst case over n == 10 tables: level ``k`` of
# the state machine holds at most ``min(2**k, 2**2**(10 - k))`` states at 7
# instructions each (5 fixed plus at most 2 transitions), and the leaf level
# 5 each less the final endif -- ``7*275 + 5*2 - 1 = 1934``, so every n=10
# table builds.  ``test_polynomial_cap_admits_every_n10_table`` re-derives
# it.  The dense n=10 fixture needs 1638; dense n=11 needs 2910 and is
# refused.
#
# The policy is still "admit what a suite can afford to check", against a
# cost curve that moved twice.  At 138 recovery was a bare ``factor_list``
# (~10s at the bound); the exact peels bought 328 (n=7 dense, 21.1s a row).
# Two interpreter changes moved it again: recovery is cached per program --
# rows of one table share a single factorization and parse -- and past
# ``_NTT_MIN_DEGREE`` peel candidates come from NTT root sets rather than
# enumeration and GF factoring.  Measured on the dense fixtures, whole
# table verified against every row: n=8 (541 instructions) 3.5s for all
# 256 rows where the old path took 115s for the *first*, n=10 (1638) 44s
# for all 1024 rows, 43.7s of it the one factorization.
#
# The count, not the arity, is still what this measures: a table that
# collapses to few states is cheap at any width, and parity renders far
# past n == 10 inside the bound.
#
# What the bound declines is measured, not assumed: past it, dense n=11
# (2910 instructions) builds and runs all 2048 rows correctly in 267s --
# 264.5s of that the single factorization, then 0.001s a row -- for a
# 123609143-character program.  Against n=10 on the same machine (1638,
# 56s), 1.78x the instructions costs 4.7x the time.  Left at 1934 on that
# price -- and 2910 is only the dense fixture: the formula above at
# n == 11 gives 3726, so even a cap sized to that price leaves the arity
# partial.
_POLYNOMIAL_MAX_INSTRS = 1934


# How far above the cheapest candidate the dispatch still renders.  Selection
# is on characters, so the instruction count only screens -- and a strict
# screen picks wrong, because the two disagree.  ``01100110`` is the case:
# the drained
# machine is 30 instructions and renders 5267 characters, while a drained
# ``k == 2`` build is 32 and renders 4814, since a longer program's later
# instructions consume larger primes.
#
# The slack has to be measured per arity, not guessed: every table at
# n <= 3 needs at most 6 (242 of 256 need 0), but 1000 sampled tables at
# n == 4 reach 9, and 32 of them need more than 6 -- a slack fitted to the
# smaller corpus silently emits the worse program on those.  Held at the
# n == 4 worst case with a margin of one, so a table needing more is a real
# finding rather than a quiet regression; ``test_polynomial_screen_slack``
# re-derives it.
_POLYNOMIAL_SCREEN_SLACK = 10


def polynomial(truth_table: str) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Polynomial programs are polynomials whose roots encode instructions, so
    both constructions below emit complex ``[a, b]`` (arithmetic, input,
    output) and real ``[val]`` (if/endif) roots that expand into
    ``f(x) = ...``.  Each instruction consumes a fresh prime, so the
    program's size and the interpreter's factorization cost both track the
    *instruction count* -- which is what the two constructions compete on.

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
    (``2**n - 1`` internal nodes, 2298 instructions at n == 8) and needs just
    two states per level, so ``k == 0`` is *linear* there -- 13 instructions
    per input, 106 at n == 8.  Small or near-constant tables still favour the
    tree end.

    The interior is where neither endpoint serves: a table whose residuals
    merge *within* a top-level split but not *across* it defeats both, since
    the tree cannot merge them at all and the machine pays a full state level
    for the split.  ``00000101`` is 43 instructions at ``k == n`` and 39 at
    ``k == 0``, but 36 at ``k == 1``.  Against the two-construction dispatch
    this family shortens 36 of 256 tables at n == 3 (median 3.6%, best
    30.3%) and 3846 of 65536 at n == 4 (median 6.5%, best 39.8%), and grows
    none.

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
    # them -- ``10101010`` costs 66 instructions where the one-input table
    # it really is costs 12.
    #
    # Reduction sidesteps that because it is *order-blind*: it rewrites the
    # table before anything is built.  The ignored inputs are drained first,
    # so every path still consumes exactly ``n`` inputs.  Only a *leading*
    # run can be handled this way -- an ignored input sitting after an
    # essential one would be drained out of turn and the build would branch
    # on the wrong bit (measured: 92 wrong rows over 26 tables).
    essential = essential_inputs(truth_table, n) or [0]
    lead = next((i for i in range(n) if i in essential), n)
    if lead:
        prefix: list[list[int]] = []
        for _ in range(lead):
            prefix.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
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
        # The machine cannot take the ``-= 48`` drain above: its entry chain
        # tests for zero, so a drained 1 fell past every state test.  Its
        # own drain divides the bit away instead; see
        # :func:`_polynomial_drained_dag`.
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
    # characters disagree: `01100000` and three relatives are 42
    # instructions against the tree's 43 and still render 11008 characters
    # against 9507, since a longer program's later instructions consume
    # larger primes.
    #
    # So the instruction count only screens: a candidate more than
    # ``_POLYNOMIAL_SCREEN_SLACK`` above the cheapest cannot win and is not
    # built.  That renders 604 of 1064 candidates over the n == 3 corpus,
    # which costs 2.54x there (0.3s across 256 programs) and 1.09x on an
    # n == 4 sample -- the arity where generation time actually lives.
    # The screen is a measured bound, not a proof: a candidate rendering
    # shorter from a further-out instruction count would be skipped.
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


def _polynomial_assemble(instrs: list[list[int]]) -> str:
    """Expand an instruction list into its ``f(x) = ...`` polynomial.

    The k-th instruction takes the k-th prime ``p``: a complex instruction
    ``[a, b]`` contributes ``(x - a)**2 + p**(2*b)`` and a real one ``[v]``
    contributes ``x - p**v``, so the roots the interpreter factors back out
    are exactly the instructions.
    """
    from esolangs.tools._polynomial import primes, render_product

    factors: list[list[int]] = []
    for instr, p in zip(instrs, primes(len(instrs)), strict=True):
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


def _polynomial_dag_cost(truth_table: str) -> int:
    """Return :func:`_polynomial_dag`'s instruction count without emitting it."""
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    index = [{state: i for i, state in enumerate(level)} for level in levels]
    total = 0
    for k in range(n):
        width = 2 ** (n - k - 1)
        states = levels[k]
        transitions = 0
        for state in states:
            zero = index[k + 1][state[:width]]
            one = index[k + 1][state[width:]]
            transitions += 1 if zero == one or one - zero == 1 else 2
        total += 5 * len(states) + transitions
    return total + 5 * len(levels[n]) - 1


def _polynomial_dag(truth_table: str) -> list[list[int]]:
    """Emit the state-machine instructions; see :func:`polynomial`.

    The register is the only storage and a read *assigns* to it, so nothing
    survives a read except the instruction cursor.  The state is therefore
    carried as *which branch is running*: each level is a chain of
    ``-= 1`` / ``if == 0`` tests over the live states, and the branch that
    fires reads its bit and moves to the child state's index.

    Two details are required.

    **``[0, b]`` is I/O, not arithmetic.**  The interpreter tests ``a == 0``
    before the opcode, so ``[0, 3]`` reads a character rather than
    multiplying by zero -- exactly the instruction a naive builder wants when
    both children merge.  That case instead reads and divides the bit away
    (``//= 50``), and an assertion below keeps any other ``a == 0`` from
    being emitted.

    **A chain of equality tests re-fires.**  A taken branch leaves the
    register holding its child state, and the chain's remaining ``-= 1``
    steps keep running, so a later test can zero it and fire too.  Every
    branch therefore parks the register at ``offset + child + remaining``,
    so the trailing decrements bring each to the same ``offset + child`` and
    the value is never zero mid-chain; the next level's chain subtracts
    ``offset`` to recover the index.

    Exactly one branch fires per level, and every branch reads once, so each
    path consumes ``n`` inputs by construction rather than by draining.
    """
    n = _validate_truth_table(truth_table)
    levels = _polynomial_states(truth_table, n)
    index = [{s: i for i, s in enumerate(level)} for level in levels]
    # Keeps a taken branch's register clear of every later test in its own
    # chain.  Only widens literals, never the instruction count that costs.
    offset = max(len(level) for level in levels) + 1
    instrs: list[list[int]] = []

    for k in range(n):
        width = 2 ** (n - k - 1)
        states = levels[k]
        for i, state in enumerate(states):
            if i:
                instrs.append([1, 2])  # -= 1
            instrs.append([4])  # if reg == 0
            remaining = len(states) - 1 - i
            zero_index = index[k + 1][state[:width]]
            one_index = index[k + 1][state[width:]]
            zero_target = offset + zero_index + remaining
            instrs.append([0, 2])  # input
            if zero_index == one_index:
                # Both children merge, so this bit cannot change the answer.
                # Divide it away rather than multiplying by zero, which the
                # interpreter would read as an input instruction.
                instrs.append([_ASCII_ZERO + 2, 4])  # //= 50 -> 0
            else:
                instrs.append([_ASCII_ZERO, 2])  # -= 48, leaving 0 or 1
                span = one_index - zero_index
                if span != 1:
                    instrs.append([span, 3])  # *= span, never zero here
            instrs.append([zero_target, 1])  # += the child's parked value
            instrs.append([2])  # endif
        instrs.append([offset, 2])  # -= offset, recovering the child index

    # The leaf states are one-wide subtables, so each *is* its answer.  No
    # guard is needed after printing: the register holds 48 or 49 and the
    # one decrement a two-state chain can still apply leaves 47 or 48.
    for i, state in enumerate(levels[n]):
        if i:
            instrs.append([1, 2])  # -= 1
        instrs.append([4])  # if reg == 0
        instrs.append([_ASCII_ZERO + int(state), 1])
        instrs.append([0, 1])  # output
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
    *within* a top-level split but not *across* it is served by neither --
    ``00000101`` costs 43 instructions at ``k == n`` and 39 at ``k == 0``,
    but 36 at ``k == 1``.

    The splice has one requirement.  The machine's entry chain opens with
    ``if reg == 0`` on its first state, while a tree arm arrives holding the
    bit it branched on, so each arm normalizes to 0 first (``last`` is what
    it carries).  Inside a tree arm the register is then parked nonzero,
    exactly as a collapsed leaf parks it, so the enclosing ``else`` skips;
    at the top level there is no enclosing ``else``, so the park is dropped
    and ``k == 0`` is the machine itself.
    """
    n = _validate_truth_table(truth_table)
    instrs: list[list[int]] = []

    def emit_delta(delta: int) -> None:
        if delta > 0:
            instrs.append([delta, 1])
        elif delta < 0:
            instrs.append([-delta, 2])

    def build(rows: list[int], bit: int, last: int) -> None:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            emit_delta(_ASCII_ZERO + v - last)
            instrs.append([0, 1])  # output
            for _ in range(bit, n):
                instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
            emit_delta(1)
            return
        if bit == k:
            emit_delta(-last)  # the machine's chain tests for zero
            instrs.extend(_polynomial_dag("".join(truth_table[r] for r in rows)))
            if bit:  # inside a tree arm; the top level has no else to skip
                instrs.append([1, 1])
            return
        instrs.extend([[0, 2], [_ASCII_ZERO, 2]])  # input; -= 48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append([1])  # if reg > 0
        build(g1, bit + 1, 1)
        instrs.append([2])
        instrs.append([4])  # if reg == 0
        build(g0, bit + 1, 0)
        instrs.append([2])

    build(list(range(2**n)), 0, 0)
    return instrs


def _polynomial_drained_dag(truth_table: str) -> list[list[int]] | None:
    """Drain a leading run of ignored inputs, then run the machine.

    The reduction the tree gets above is available to the machine too, but
    only once the drain stops leaving a bit behind.  ``input; -= 48`` leaves
    0 or 1, and the machine's entry chain opens by testing for zero, so a
    drained ``1`` fell past every state test -- the combination answered
    correctly only while the drained bit was 0.  Draining with the
    ``//= 50`` pair the machine already uses for a merged child lands on 0
    either way, for the same two instructions per level.

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
    instrs: list[list[int]] = []
    for _ in range(lead):
        instrs.extend([[0, 2], [_ASCII_ZERO + 2, 4]])  # input; //= 50 -> 0
    instrs.extend(_polynomial_dag(reduced))
    return instrs


def _polynomial_drained_dag_cost(truth_table: str) -> int | None:
    """Return :func:`_polynomial_drained_dag`'s instruction count."""
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
    return 2 * lead + _polynomial_dag_cost(reduced)


def _polynomial_hybrid_cost(truth_table: str, k: int) -> int:
    """Return :func:`_polynomial_hybrid`'s instruction count without emitting it.

    A deliberate mirror of the emitter above: the dispatch screens on this
    before rendering, so a drift between the two would screen out a table
    the emitter would have won.  ``test_polynomial_hybrid_cost_mirrors_build``
    asserts they agree over the whole ``n <= 3`` corpus.
    """
    n = _validate_truth_table(truth_table)

    def delta(value: int) -> int:
        return 1 if value else 0

    def cost(rows: list[int], bit: int, last: int) -> int:
        vals = {truth_table[r] for r in rows}
        if len(vals) == 1:
            v = int(vals.pop())
            return delta(_ASCII_ZERO + v - last) + 1 + 2 * (n - bit) + delta(1)
        if bit == k:
            residual = "".join(truth_table[r] for r in rows)
            # The park is emitted only inside a tree arm; see the emitter.
            return delta(-last) + _polynomial_dag_cost(residual) + (1 if bit else 0)
        split = n - 1 - bit
        g1 = [r for r in rows if ((r >> split) & 1) == 1]
        g0 = [r for r in rows if ((r >> split) & 1) == 0]
        return 6 + cost(g1, bit + 1, 1) + cost(g0, bit + 1, 0)

    return cost(list(range(2**n)), 0, 0)
