r"""Boolean-function generator for 123, under the termination convention.

123's input command reads real stdin, so this is a *parameterized*
generator: input runs become ``1`` for a one and ``2`` for a zero (both
one character, so ``len()`` leaks nothing).  **The answer is the halting
behaviour**: halt is 0, a proven loop is 1, decided by
:func:`esolangs.vm.run_until_halt_or_cycle`.

Printing cannot work: flipping is XOR, so straight-line programs are
affine and reach only the eight affine tables at ``n == 2``.  The
limitations ledger's *monotone* cap (nine of sixteen) belonged to the
displacement-neutral ``12``/``21`` setter, not the language: the ±1
setter here displaces the fills oppositely, so the looping set need not
be upward-closed.

Construction (``n <= 3``; wider tables go to
:mod:`esolangs.tools.one_two_three.construction`):

1. **Seed** ``"2"*w0 $ "2"*w1 $ ... "33"`` -- the fills are the
   embedding; ``33`` closes at the first offset where no row sits on a
   mark (bounded first-fit).
2. **Separation** -- a frozen per-arity schedule of even-displacement
   walk/descend segments each closed by ``33``, ending with every row at
   a distinct odd position.  Frozen constants, replayed on the exact
   model, never searched at build time; up to four laws per arity are
   candidates, and the shortest template wins.
3. **Verdict** -- a planned kill on a junky tape: one paint per row whose
   tested cell disagrees with the table's demand; distinct odd positions
   keep paint offsets collision-free.
4. **Endgame** -- ``_endgame`` parks the survivors below zero.

Every row walks the same segments in parallel on one tape, so no jump
reaches a subtree twice; rows past the last one need no verdict paint.

The suite's exhaustive ``n <= 3`` sweep on the real interpreter is what
pins the schedules.  Every template loops by a proven state revisit, never
unbounded growth, or the harness would hang instead of reporting a 1; the
suite checks it.
"""

from __future__ import annotations

from functools import cache

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    read_at,
    runs,
)
from esolangs.tools.one_two_three.construction import (
    _INPUT,
    _ONE,
    _RING,
    _WORK_BUDGET,
    _ZERO,
    ConstructError,
    _Builder,
    _endgame,
    _on_mark,
    _paint,
    _table_val,
    _tested,
    _work,
    _WorkExhaustedError,
    construct,
)
from esolangs.tools.wrap import wrap_chars

__all__ = ["one_two_three"]

#: The input fills, re-exported from the construction.
ONE, ZERO = _ONE, _ZERO
#: Each input's embed: the generator's own ``ZERO``/``ONE`` command.
PAIR = (ZERO, ONE)

#: One separation law: the walk before each fill, then the alternating
#: ``1``/``2`` test displacements, each closed by its own ``33``.  Rows whose
#: tested cell is marked re-run the segment and escape, rows whose cell is
#: clear skip: rows differ in their *marks* after a bare fill, not their
#: positions, so a walk alone can never split them.
type _Law = tuple[tuple[int, ...], tuple[int, ...]]

#: The separation laws per small arity, each a named candidate.
#:
#: Derived, not a frozen search log.  The first law has the least mean
#: template length over constant seeds and alternating displacement vectors;
#: the rest are a greedy cover (seeds 0..6 per fill, up to four displacements
#: of 1..10): each most shrinks the total over every table given the laws
#: before it and the wide chain, at most four in all.  Both rules are
#: re-derived in ``tests/tools/test_boolean_one_two_three_laws.py``.  A
#: failing law could only raise, never mis-emit.
_LAWS: dict[int, tuple[_Law, ...]] = {
    1: (((0,), ()), ((1,), (1, 2, 2)), ((0,), (2,))),
    2: (
        ((2, 2), (3, 2, 4)),
        ((2, 0), (2,)),
        ((2, 0), (2, 4, 4)),
        ((0, 6), (3, 2, 4)),
    ),
    3: (
        ((3, 3, 3), (1, 3, 9, 4)),
        ((6, 0, 1), (4, 8, 6)),
        ((2, 6, 1), (7, 4, 2)),
        ((4, 2, 3), (6, 9, 2)),
    ),
}


@cache
def _separated(n: int, law: int = 0) -> _Builder:
    """Execute arity ``n``'s ``law``-th separation law up to full separation.

    A prototype the per-table build clones, so the law is modelled once per
    process.  Raises if the law no longer separates, which the exhaustive
    sweep turns into a test failure.
    """
    walks, disps = _LAWS[n][law]
    _work[0] = _WORK_BUDGET
    b = _Builder(n)
    for i, walk in enumerate(walks):
        if walk:
            b.run("2" * walk)
        b.fill(i)
    for d in range(4 * 2**n + 9):
        probe = b.clone()
        if d:
            probe.run("2" * d)
        if any(r.pos < 0 for r in probe.live()):
            continue
        if not any(_on_mark(r) for r in probe.live()):
            if d:
                b.run("2" * d)
            b.test()
            break
    else:  # pragma: no cover - the derived seeds all close within range
        raise ConstructError("no clean close for the seed")
    # Pure tests, alternating ``1``-runs and ``2``-runs by position.
    for i, d in enumerate(disps):
        b.run(("1" if i % 2 == 0 else "2") * d)
        b.test()
    poss = [r.pos for r in b.live()]
    if len(set(poss)) != len(poss):  # pragma: no cover - invariant
        raise ConstructError("the law left shared positions")
    return b


def _verdict_junky(b: _Builder, table: str) -> None:
    """Settle the verdict with the planned kill, on a junky tape.

    Paints aim at *disagreement*: below the kill a 0-row's tested cell must
    end marked (the kill clears it) and a 1-row's clear (the kill's trailing
    mark loops it).  Rows at or above the kill height test their own cell,
    which must be clean; a dirty survivor rejects the schedule (none does at
    these arities).
    """
    ones = [r for r in b.live() if _table_val(table, r.bits) == "1"]
    if not ones:
        return
    live = b.live()
    positions = [r.pos for r in live]
    if len(set(positions)) != len(positions) or any(p % 2 == 0 for p in positions):
        raise ConstructError("verdict precondition: positions not distinct odd")
    a = max(r.pos for r in ones) + 2
    if any(r.pos >= a and _on_mark(r) for r in live):  # pragma: no cover
        raise ConstructError("a survivor sits on a marked cell")
    painted = False
    for r in sorted(live, key=lambda row: row.pos):
        if r.pos >= a:
            continue
        tested = _tested(a, r.pos)
        have = bool(r.tape >> (tested + _RING) & 1)
        want = _table_val(table, r.bits) == "0"
        if have != want:
            _paint(b, tested - r.pos)
            painted = True
    if painted:
        b.test()
    b.run("1" * a + "2" + "2" * (a - 1) + "12")
    b.test(kills=frozenset(r.bits for r in ones))


def _construct_small(truth_table: str, n: int, law: int = 0) -> str:
    """Build the small-arity template arity ``n``'s ``law``-th law gives.

    No closing replay: ``test_all_small_tables`` sweeps every ``n <= 3``
    table through the real interpreter, the same contract as
    :func:`~esolangs.tools.one_two_three.construction.construct`.
    """
    _work[0] = _WORK_BUDGET
    try:
        b = _separated(n, law).clone()
        _verdict_junky(b, truth_table)
        _endgame(b)
    except (
        ConstructError,
        _WorkExhaustedError,
    ) as exc:  # pragma: no cover - the sweep proves coverage
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
    return b.template()


#: An ignored input's run past the end, between fixed ``1``/``2`` halves.  No
#: ``3``, so it moves the pointer alone: from any of -1, -2, -3, either fill
#: ends below 0 again without a ``2`` at -3 (a read).  Every jump in front
#: lands where it did, killed rows never leave their loops, and the rows
#: that reach the end are below 0, so they still halt.
_IDLE = "1112" + _INPUT + "12111"


def _in_name_order(body: str, n: int) -> str:
    """Return ``body`` once it is known to carry exactly ``n`` input runs."""
    try:
        runs(body, TEMPLATE_CHAR, (PAIR,) * n)
    except ValueError as exc:
        raise ValueError(f"template {body!r} does not embed {n} inputs: {exc}") from exc
    return body


def one_two_three(truth_table: str) -> str:
    """Build a 123 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Input runs take ``1`` for a one and
    ``2`` for a zero; the program halts for 0 and loops for 1, decided by
    :func:`esolangs.vm.run_until_halt_or_cycle`.  Raises
    :class:`ValueError` when a stage invariant breaks; the execution gate
    lives in the test suite.
    """
    n = _validate_truth_table(truth_table)
    if n > 3:
        # Inputs past the last essential one become idle runs on the end.
        essential = essential_inputs(truth_table, n)
        if essential and essential[-1] + 1 == len(essential) < n:
            inner = one_two_three(read_at(truth_table, essential, n))
            return _in_name_order(inner + _IDLE * (n - len(essential)), n)
        return _in_name_order(construct(truth_table), n)
    candidates = [_construct_small(truth_table, n, law) for law in range(len(_LAWS[n]))]
    return _in_name_order(min(candidates, key=len), n)


LANGUAGE = Language(
    "123",
    "tape_based.one_two_three",
    boolean=one_two_three,
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="123 answers by terminating: it halts for a 0 result and loops "
        "forever for a 1, so only the halting branch is committed. Its "
        "output is not the answer and is not compared -- the merge pops "
        "through location -2 and prints whatever that cell holds, which "
        "for this program is the two bytes 'VO with a diaeresis'",
        parameterized=True,
    ),
    # The trailing ``1`` is a terminator, not a structural line.
    wrap=wrap_chars,
    empty_program="an empty 123 program never halts",
    # 123 answers with the termination convention, as ArrowQueue does, so
    # only the halting (0) branch is committed.  The constructed template
    # pops through location -2 while merging, which prints junk bytes on
    # every row; ``test_boolean_example`` asserts the halt and ignores
    # them, so ``expected`` is vestigial here.
    example=Example(pair=PAIR, expected="", expected_compared=False),
)
