"""Boolean-function generator for Polynomial.

:mod:`esolangs.tools._polynomial` is the algebra; this decides the
instructions.  Every instruction is priced by opcode: ``[a, b]`` is the
factor ``(x - a)**2 + p**(2*b)`` and ``[v]`` is ``x - p**v``, with
``+=`` at ``b == 1``, ``-=`` 2, ``*=`` 3, ``//=`` 4 and ``if > 0`` at
``v == 1``, ``endif`` 2, ``if < 0`` 3, ``if == 0`` 4.  So subtraction is
``+=`` with a negative operand, tests are ``if > 0`` only, and ``*=``/
``//=`` are kept for the two places nothing cheaper reaches: dense n == 6
renders 1.9x shorter than the ``-= 1; if == 0`` builder, n == 7 2.1x.
"""

from typing import Any

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

# Instruction cap.  Analytic n=10 worst case is 1659
# (``test_polynomial_cap_admits_every_n10_table``); kept at the old 1934,
# which the interpreter affords (n=10: 1638 instructions, 44s for 1024
# rows).  Dense n=11 (2910) ran 2048 rows in 267s, 264.5s of it factoring.
_POLYNOMIAL_MAX_INSTRS = 1934


# Instruction-count slack the dispatch still renders; selection is on
# characters, and the two disagree (later instructions take larger primes,
# ``*=`` costs 3x the digits of ``+=``).  n <= 3 needs 1, 2000 sampled n=4
# tables reach 6; held at the old builder's 10 so more is a real finding.
# ``test_polynomial_screen_slack`` re-derives the n <= 3 figure.
_POLYNOMIAL_SCREEN_SLACK = 10


def polynomial(truth_table: str) -> str:
    """Build a Polynomial program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    Programs are polynomials whose roots are instructions.  Every
    construction is :func:`_polynomial_hybrid` at some ``k``: ``k == n`` a
    folded tree, ``k == 0`` one state machine (an ordered BDD merging equal
    residuals: parity needs two states per level, 11 instructions per
    input), the interior a machine per residual; reduced variants drain a
    leading run of ignored inputs.  Reordering is unreachable (a read
    assigns the single register).  Selection is on rendered characters.
    More than ``_POLYNOMIAL_MAX_INSTRS`` raises :class:`ValueError`.
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

    # An ignored input still costs a level of branching, so drain a
    # *leading* ignored run before building (a later one drained out of
    # turn branched on the wrong bit: 92 wrong rows over 26 tables).
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

    # Select on rendered characters; the instruction count only screens
    # (a candidate past ``_POLYNOMIAL_SCREEN_SLACK`` is not built -- a
    # measured bound, not a proof).  ``k`` descends and the comparison is
    # strict, so a table nothing shortens emits what it always did.
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

    Primes upward; within one, real roots by exponent then complex by
    ``(b, a)``.
    """
    if len(instr) == 1:
        return (0, instr[0])
    return (instr[1], instr[0])


def _polynomial_assemble(instrs: list[list[int]]) -> str:
    """Expand an instruction list into its ``f(x) = ...`` polynomial.

    Consecutive instructions share a prime when their decode order is their
    program order (keys never decrease), and each shared prime shrinks every
    later constant: dense n=5..8 machines fall 14%, 12%, 11%, 10%.  A block's
    ``if > 0; input; *= span`` and ``endif; += 1`` are such runs, so a block
    spends three primes, not six.
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

    Two prefixes leaving the same subtable are one state -- the merge a
    tree cannot make.
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

    A span of 1 needs no ``*= span``, the dearest opcode a block carries
    (``p**6`` vs ``p**2``), so labels are chosen greedily to make
    ``zero == one + 1`` where no slot is taken and no cycle closes: dense
    n=6..8 keep 8, 13 and 30 spans against 31, 50 and 82 blocks.
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

    Counted by building; a separate mirror would drift on the labelling.
    """
    return len(_polynomial_dag(truth_table))


def _polynomial_dag(truth_table: str, park: int | None = None) -> list[list[int]]:
    """Emit the state-machine instructions; see :func:`polynomial`.

    State is *which branch is running*: a level is a chain of blocks, one
    per state, entered at ``-i``; each does ``+= 1; if > 0``, so block ``i``
    fires and parks at ``-(child + remaining)`` so none later fires.  The
    read is mapped by ``*= span; += park - 48*span`` (multiply dropped at
    ``span == 1``); merged children are divided away with ``//= 50``, since
    ``[0, b]`` spells I/O.  A leaf steps to the digit, prints, and parks at
    or below ``-park`` so enclosing arms never see a positive register.
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

    The whole family: ``k == n`` is the plain tree, ``k == 0`` one machine,
    the interior serves tables whose residuals merge within a top split but
    not across it.  A tree node reads, subtracts 48, branches ``if > 0``
    into the one-arm; every arm leaves the register at or below
    ``-(n + 2)``, so ``+= 1; if > 0`` fires for the zero bit (``p`` and
    ``p**2`` vs ``if == 0``'s ``p**4``).  The machine's root opens with a
    read, so no splice is needed.
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

    One bare read per ignored input.  ``None`` when nothing is ignored or the
    reduction leaves one row.
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

    Counted by building; ``test_polynomial_hybrid_cost_mirrors_build``.
    """
    return len(_polynomial_hybrid(truth_table, k))
