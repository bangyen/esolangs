"""Polynomial Boolean program generator: instructions as polynomial roots.

:mod:`esolangs.languages.polynomial.generator.algebra` is the algebra; this decides the
instructions.  Every instruction is priced by opcode: ``[a, b]`` is the
factor ``(x - a)**2 + p**(2*b)`` and ``[v]`` is ``x - p**v``, with
``+=`` at ``b == 1``, ``-=`` 2, ``*=`` 3, ``//=`` 4 and ``if > 0`` at
``v == 1``, ``endif`` 2, ``if < 0`` 3, ``if == 0`` 4.  So subtraction is
``+=`` with a negative operand, tests are ``if > 0`` only, and ``*=``/
``//=`` are kept for the two places nothing cheaper reaches.  Every program
is a hybrid: ``k`` tree levels above one state machine per surviving
residual, ``k`` the one with the fewest instructions.  An expansion bounded
past 1,000,000,000 characters also raises.

Size:
    Grows with the instruction count and the prime sizes; n=8 parity: 40,385
    chars, n=8 random 1847: 1,454,887 chars, n=16 and: 206,042 chars.

Raises:
    GeneratorCapError: the cheapest construction needs more than 1934
    instructions (dense n=11 needs 2447).

Decisions:
    Dense n == 6 renders 1.9x shorter on ``+=`` and ``if > 0`` than on the
    old ``-= 1; if == 0`` builder, n == 7 1.9x.
"""

from collections.abc import Iterator

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
    same_ignoring_whitespace,
)
from esolangs.generation.wrap import balance_program
from esolangs.languages.polynomial.generator.algebra import primes, render_product
from esolangs.languages.polynomial.generator.resources import estimate_generation
from esolangs.languages.polynomial.proof_formulas import workspace
from esolangs.languages.polynomial.wrapping import (
    _balance_polynomial,
    _polynomial,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime.source_hints import with_hint

# Instruction cap.  Analytic n=10 worst case is 1659
# (``test_polynomial_cap_admits_every_n10_table``); kept at the old 1934,
# which the interpreter affords (n=10: 1382 instructions, 44s for 1024
# rows).  Dense n=11 (2447) ran 2048 rows in 267s, 264.5s of it factoring.
_POLYNOMIAL_MAX_INSTRS = 1934

# Pre-expansion ceiling on a proof-sized upper bound, not the rendered length.
# Every admitted n <= 10 construction stays below it; it prevents a short
# instruction list with enormous operands from entering Decimal multiplication.
_POLYNOMIAL_MAX_ESTIMATED_CHARS = 1_000_000_000


def polynomial(truth_table: str) -> str:
    """Return a Polynomial program for ``truth_table`` (``2**n`` bits, MSB first).

    The fewest-instruction :func:`_polynomial_hybrid` of each reduction, the
    shortest rendering of those.
    """
    n = _validate_truth_table(truth_table)

    candidates = list(_polynomial_candidates(truth_table, n))
    fits = [ins for ins, cost in candidates if cost <= _POLYNOMIAL_MAX_INSTRS]
    costs = [cost for _, cost in candidates]

    if not fits:
        raise with_hint(
            GeneratorCapError(
                "the Polynomial boolean generator groups instructions onto "
                f"primes and caps at {_POLYNOMIAL_MAX_INSTRS}, but this table "
                f"needs {min(costs)} under its cheapest "
                "construction, which costs more per row than checking a table "
                "of this width can afford",
            ),
            (
                "check another generator's limits; layout "
                "cannot raise the prime instruction budget"
            ),
        )

    # Rendered characters choose among the reductions only (ignored runs).
    return min((_polynomial_assemble(instructions) for instructions in fits), key=len)


_READ = [0, 2]

#: ``[0, 1]``: output -- with ``_READ``, one of the two ``a == 0`` I/O spells.
_OUTPUT = [0, 1]


def _read() -> list[int]:
    """Return a fresh read instruction (``[0, 2]``; see ``_READ``)."""
    return list(_READ)


def _output() -> list[int]:
    """Return a fresh output instruction (``[0, 1]``; see ``_OUTPUT``)."""
    return list(_OUTPUT)


def _add(operand: int) -> list[int]:
    """Return the ``+= operand`` instruction, ``[operand, 1]``."""
    return [operand, 1]


def _multiply(span: int) -> list[int]:
    """Return the ``*= span`` instruction, ``[span, 3]``."""
    return [span, 3]


def _divide_by_50() -> list[int]:
    """Return ``//= 50``, ``[50, 4]``: undo a read's ``48 + bit``."""
    return [_ASCII_ZERO + 2, 4]


def _if_positive() -> list[int]:
    """Return the ``if reg > 0`` instruction, ``[1]``."""
    return [1]


def _endif() -> list[int]:
    """Return the ``endif`` instruction, ``[2]``."""
    return [2]


def _polynomial_candidates(
    truth_table: str, n: int
) -> Iterator[tuple[list[list[int]], int]]:
    """Yield ``(instructions, cost)`` for the cheapest hybrid ``k`` of each reduction.

    Rejected plans cost more than ``_POLYNOMIAL_MAX_INSTRS`` instructions,
    ignored-input reads included; the caller drops them.
    """

    def hybrid(
        table: str, arity: int, before: int = 0, after: int = 0
    ) -> tuple[list[list[int]], int]:
        # The fewest instructions, ties to the larger ``k``.  Choosing among
        # the near-cheapest by rendered length saved 0.0% (random n=4..8).
        cheapest = min(
            (_polynomial_hybrid(table, level) for level in range(arity, -1, -1)),
            key=len,
        )
        return (
            [_READ] * before + cheapest + [_READ] * after,
            len(cheapest) + before + after,
        )

    yield hybrid(truth_table, n)

    # An ignored input still costs a level of branching, so drain a
    # *leading* ignored run before building (a later one drained out of
    # turn branched on the wrong bit: 92 wrong rows over 26 tables).
    # Reordering inputs is unreachable: a read assigns the single register.
    essential = essential_inputs(truth_table, n) or [0]
    # A *trailing* ignored run is cut from the table and its reads appended
    # at the very end, which every path reaches parked below zero, so they
    # change nothing; the selection keeps it only where it is shorter.
    tail = n - 1 - essential[-1]
    if tail:
        cut = read_at(truth_table, list(range(n - tail)), n)
        yield hybrid(cut, n - tail, after=tail)
    lead = next((i for i in range(n) if i in essential), n)
    if lead:
        reduced = read_at(truth_table, list(range(lead, n)), n)
        yield hybrid(reduced, n - lead, before=lead)


def _polynomial_assemble(instrs: list[list[int]]) -> str:
    """Expand an instruction list into its ``f(x) = ...`` polynomial.

    Consecutive instructions share a prime when their decode order is their
    program order (keys never decrease); each shared prime shrinks every
    later constant; figures in [ablations.prime_sharing].
    """
    factors = _polynomial_factors(instrs)
    estimate = estimate_generation(factors)
    if estimate.rendered_chars > _POLYNOMIAL_MAX_ESTIMATED_CHARS:
        raise with_hint(
            GeneratorCapError(
                "the Polynomial expansion is conservatively bounded at "
                f"{estimate.rendered_chars} characters and "
                f"{estimate.peak_decimal_digits} live decimal digits, past the "
                f"{_POLYNOMIAL_MAX_ESTIMATED_CHARS}-character construction ceiling"
            ),
            (
                "check another generator's limits; output "
                "width cannot reduce the polynomial expansion"
            ),
        )
    # The expansion is the whole cost past n == 7 -- the factor count is the
    # degree, and multiplying them in one incremental sweep rescans a
    # polynomial whose coefficients keep growing.  ``render_product`` cuts
    # the list into groups and merges them packed; see there.
    return str(render_product(factors))


def _polynomial_decode_key(instr: list[int]) -> tuple[int, int]:
    """Return where ``convert`` places ``instr`` among the roots of one prime.

    Primes upward; within one, real roots by exponent then complex by
    ``(b, a)``.
    """
    if len(instr) == 1:
        return (0, instr[0])
    return (instr[1], instr[0])


def _polynomial_factors(instrs: list[list[int]]) -> list[list[int]]:
    """Encode instructions as factors without expanding their product."""
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
    return factors


def _polynomial_states(truth_table: str, n: int) -> list[list[str]]:
    """Return the distinct residual subfunctions at each level.

    Two prefixes leaving the same subtable are one state -- the merge a
    tree cannot make.  A level's states are deduplicated through a set, so
    a level costs its own text (the states' total length), not a list scan
    per child; the levels together hold ``n * 2**n`` characters.
    """
    levels = [[truth_table]]
    for k in range(n):
        width = 2 ** (n - k - 1)
        nxt: dict[str, None] = {}
        for state in levels[k]:
            nxt.setdefault(state[:width])
            nxt.setdefault(state[width:])
        levels.append(list(nxt))
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


def _polynomial_dag(truth_table: str, park: int | None = None) -> list[list[int]]:
    """Emit the state-machine instructions; see :func:`_polynomial_hybrid`.

    State is *which branch is running*: a level is a chain of blocks, one
    per state, entered at ``-i``; each does ``+= 1; if > 0``, so block ``i``
    fires and parks at ``-(child + remaining)`` so none later fires.  The
    read is mapped by ``*= span; += park - 48*span`` (multiply dropped at
    ``span == 1``); merged children are divided away with ``//= 50``, since
    ``[0, b]`` spells I/O.  A leaf steps to the digit, prints, and parks at
    or below ``-park`` so enclosing arms never see a positive register.
    """
    if park is None:
        park = _validate_truth_table(truth_table) + 2
    return _DagEmitter(truth_table, park).run()


class _DagEmitter:
    """The state machine of :func:`_polynomial_dag`, as state plus phases.

    ``levels``/``index`` come from :func:`_polynomial_states` and
    :func:`_polynomial_labels`; ``instrs`` accumulates the instructions
    as each level's blocks and then the leaves are emitted.
    """

    def __init__(self, truth_table: str, park: int) -> None:
        self.n = _validate_truth_table(truth_table)
        self.park = park
        self.levels = _polynomial_states(truth_table, self.n)
        self.index = _polynomial_labels(self.levels, self.n)
        self.instrs: list[list[int]] = []

    def run(self) -> list[list[int]]:
        """Emit every level's blocks, then the leaves, then check the result."""
        for k in range(self.n):
            self.emit_level(k)
        self.emit_leaves()
        self.check_no_zero_operands()
        return self.instrs

    def emit_level(self, k: int) -> None:
        """Emit one block per state at level ``k``, in label order."""
        states = sorted(self.levels[k], key=self.index[k].__getitem__)
        chained = len(states) > 1
        for j, state in enumerate(states):
            self.emit_block(k, state, remaining=len(states) - 1 - j, chained=chained)

    def emit_block(self, k: int, state: str, *, remaining: int, chained: bool) -> None:
        """Emit one state's block: fire only at ``-j``, read, map to the child.

        The read is mapped by ``*= span; += park - 48*span`` (multiply
        dropped at ``span == 1``); merged children are divided away with
        ``//= 50``, since ``[0, b]`` spells I/O.
        """
        instrs = self.instrs
        width = 2 ** (self.n - k - 1)
        if chained:
            instrs.append(_add(1))  # += 1
            instrs.append(_if_positive())  # if reg > 0
        zero = self.index[k + 1][state[:width]]
        one = self.index[k + 1][state[width:]]
        target = -(zero + remaining)
        instrs.append(_read())  # input -> 48 + bit
        if zero == one:
            instrs.append(_divide_by_50())  # //= 50 -> 0
            if target:
                instrs.append(_add(target))
        else:
            span = zero - one
            if span != 1:
                instrs.append(_multiply(span))  # *= span, never zero here
            if delta := target - _ASCII_ZERO * span:
                instrs.append(_add(delta))
        if chained:
            instrs.append(_endif())

    def emit_leaves(self) -> None:
        """Emit one leaf per final state: step to the digit, print, park."""
        leaves = sorted(self.levels[self.n], key=self.index[self.n].__getitem__)
        for state in leaves:
            value = _ASCII_ZERO + int(state)
            if len(leaves) > 1:
                self.instrs.append(_add(1))  # += 1
                self.instrs.append(_if_positive())  # if reg > 0, entered holding 1
                self.instrs.append(_add(value - 1))
            else:
                # A constant table: every level merged, so the register is 0.
                self.instrs.append(_add(value))
            self.instrs.append(_output())  # output
            # Park below every enclosing test.
            self.instrs.append(_add(-(value + self.park)))
            if len(leaves) > 1:
                self.instrs.append(_endif())

    def check_no_zero_operands(self) -> None:
        """Reject any arithmetic instruction whose zero operand spells I/O."""
        for instr in self.instrs:
            # ``a == 0`` is how the interpreter spells I/O, so an arithmetic
            # instruction computing a zero operand would silently become a read
            # -- a wrong program rather than a failure.  The builder never emits
            # one; this raises rather than asserting so the guard survives
            # ``-O``, where the trap it catches would be silent.
            if len(instr) == 2 and instr[0] == 0 and instr not in (_OUTPUT, _READ):
                raise AssertionError(
                    f"{instr} has a zero operand, which the interpreter reads as "
                    "I/O rather than arithmetic",
                )


def _polynomial_hybrid(truth_table: str, k: int) -> list[list[int]]:
    """Emit ``k`` tree levels above a state machine per surviving residual.

    The whole family: ``k == n`` is the plain tree, ``k == 0`` one machine
    (an ordered BDD merging equal residuals; parity needs two states per
    level, 11 instructions per input), the interior serves tables whose
    residuals merge within a top split but not across it.  A tree node reads,
    subtracts 48, branches ``if > 0`` into the one-arm; every arm leaves the
    register at or below ``-(n + 2)``, so ``+= 1; if > 0`` fires for the zero
    bit (``p`` and ``p**2`` vs ``if == 0``'s ``p**4``).  The machine's root
    opens with a read, so no splice is needed.
    """
    return _HybridBuilder(truth_table, k).run()


class _HybridBuilder:
    """The recursive tree-above-machine emission of :func:`_polynomial_hybrid`.

    ``instrs`` accumulates the instructions; ``park`` is the value every
    arm leaves the register at or below, so an ancestor's ``+= 1; if > 0``
    test can tell a taken arm from an untaken zero bit.
    """

    def __init__(self, truth_table: str, k: int) -> None:
        self.truth_table = truth_table
        self.n = _validate_truth_table(truth_table)
        self.k = k
        self.park = self.n + 2
        self.instrs: list[list[int]] = []

    def run(self) -> list[list[int]]:
        """Build the whole table, starting from every row at the root."""
        self.build(list(range(2**self.n)), 0, 0)
        return self.instrs

    def build(self, rows: list[int], bit: int, last: int) -> None:
        """Emit the subtree over ``rows`` at depth ``bit``."""
        vals = {self.truth_table[r] for r in rows}
        if len(vals) == 1:
            self.emit_leaf(int(vals.pop()), bit, last)
            return
        if bit == self.k:
            residual = "".join(self.truth_table[r] for r in rows)
            self.instrs.extend(_polynomial_dag(residual, self.park))
            return
        self.emit_node(rows, bit)

    def emit_leaf(self, v: int, bit: int, last: int) -> None:
        """Emit a constant subtree: step to the digit, print, drain, park."""
        instrs = self.instrs
        # ``last`` is 0 or 1 and the digit is 48 or 49, so neither
        # operand here can be the zero that would spell I/O.
        instrs.append(_add(_ASCII_ZERO + v - last))
        instrs.append(_output())  # output
        # Drain the reads the untaken siblings would have made, after
        # printing so they cannot disturb the value; a bare read is
        # enough, since the park below overwrites what it left.
        for _ in range(bit, self.n):
            instrs.append(_read())
        # Only an ancestor tests the parked value.
        instrs.append(_add(-(_ASCII_ZERO + 1 + self.park)))

    def emit_node(self, rows: list[int], bit: int) -> None:
        """Emit one tree node: read, branch into the one-arm, then the zero-arm."""
        instrs = self.instrs
        n = self.n
        instrs.extend([_read(), _add(-_ASCII_ZERO)])  # input; += -48
        g1 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 1]
        g0 = [r for r in rows if ((r >> (n - 1 - bit)) & 1) == 0]
        instrs.append(_if_positive())  # if reg > 0
        self.build(g1, bit + 1, 1)
        instrs.append(_endif())
        instrs.append(_add(1))  # += 1: a zero bit is now 1, a taken arm <= -1
        instrs.append(_if_positive())  # if reg > 0
        self.build(g0, bit + 1, 1)
        instrs.append(_endif())


LANGUAGE = Language(
    "Polynomial",
    "polynomial",
    category="register_based",
    extra="math",
    generator_restrictions=f"at most {_POLYNOMIAL_MAX_INSTRS} instructions and "
    f"{_POLYNOMIAL_MAX_ESTIMATED_CHARS} estimated characters; "
    "table dependent",
    boolean=polynomial,
    documented_sizes=(1_589_968, 5_016_851, 3.1),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    # Space wrap stranded every sign alone; keep sign with term, one per line.
    wrap=_polynomial,
    wrap_balance=_balance_polynomial,
    same_layout=same_ignoring_whitespace,
    slow_width_sweep=True,
    eof="an exhausted input instruction stores -1",
    empty_program="Polynomial program must start with 'f(x) = '",
    proof_workspace=(workspace, False, (3,)),
)
