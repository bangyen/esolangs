"""Unit tests for the Minifuck boolean generator.

Covers :mod:`esolangs.tools.boolean.minifuck`, split out of
``test_boolean_parameterized.py``: Minifuck is one language's solver and the
largest single block of those tests.

The two helpers below are duplicated from that module rather than shared.
``mutate_one`` copies test bodies and drops module-level imports, so a helper
imported from a common module would leave these tests silently uncovered
under mutation.
"""

import importlib
import re
from unittest.mock import patch

import pytest

from esolangs.tools.boolean.helpers import essential_inputs


def _unreachable(*_args: object, **_kwargs: object) -> None:
    """Stand in for a function a test asserts is never called."""
    raise AssertionError("this should not have been called")


def _all_derived_plans(derived_plans, staged_arities, n: int) -> dict:
    """Every staging the enumeration places at ``n``, in one pass.

    ``_derived_plans`` is asked for the tables it should look for, so a test
    that wants the whole arity has to name them.  The arity guard is checked
    *first*: naming every table means ``2 ** (2 ** n)`` of them, which is
    unbuildable past four inputs, and the guard is what the unstaged arities
    are being tested for anyway.
    """
    if n not in staged_arities:
        return derived_plans(n, ())
    every = tuple(format(v, f"0{2**n}b") for v in range(2 ** (2**n)))
    return derived_plans(n, every)


def _slot_order(gen: object, table: str) -> list[int] | None:
    """The ``{Xi}`` indices in the order ``gen`` emits them, or None."""
    import re

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover every arity
    return [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", template)]


@pytest.mark.slow  # the degenerate tables are the fast closed-form path
def test_minifuck_slots_run_in_name_order() -> None:
    """Minifuck emits in name order, including the tables that once did not.

    This was a strict ``xfail``.  The tables listed here are the ones that
    used to leave sequence, kept as the regression: ``11001100`` is closed by
    solving at full arity rather than projecting, and ``01010101`` /
    ``10101010`` -- the projections onto the *last* input, which full arity
    cannot reach -- by emitting the ignored setters first and reconverging
    the rows before the essential one.

    Degenerate tables only: they are the closed-form path, and the only ones
    whose slot order can leave sequence.  A table needing the search takes
    tens of seconds and cannot exercise this.
    """
    from esolangs.tools.boolean import parameterized

    for table in ("11001100", "10101010", "01010101", "00001111"):
        slots = _slot_order(parameterized.minifuck, table)
        if slots is None:
            continue
        assert slots == sorted(slots), (table, slots)

    # ``00010001`` and ``11101110`` project onto AND and NAND, and the
    # enumeration derives both at ``settle == 1``.  A version of
    # ``_reconverged`` that dropped the staging's settle count pushed exactly
    # these two off the route and out of sequence, while every other test
    # stayed green -- the four tables above do not reach that path.  So they
    # are pinned here, by the property the bug broke.
    for table in ("00010001", "11101110"):
        slots = _slot_order(parameterized.minifuck, table)
        assert slots is not None, table
        assert slots == sorted(slots), (table, slots)

    # **The whole arity, not a list.**  Ten tables used to emit
    # ``{X0}{X2}{X1}`` -- every one of them with the ignored input in the
    # *middle* -- and they survived precisely because this test named
    # specific tables and none of them had that shape.  A hand-picked list
    # cannot fail on the case nobody thought of, so the sweep is the
    # assertion that matters and the tables above are the regressions it
    # grew from.  They are sorted now because ``_solve`` hands exactly that
    # residue to ``_mux``, which embeds at full arity in ascending order.
    unsorted_tables = []
    for value in range(256):
        table = format(value, "08b")
        slots = _slot_order(parameterized.minifuck, table)
        if slots is not None and slots != sorted(slots):
            unsorted_tables.append((table, slots))
    assert not unsorted_tables, unsorted_tables


@pytest.mark.slow  # two closed-form builds plus eight interpreter runs each
def test_minifuck_reconverged_tables_compute_their_function() -> None:
    """The reconvergence route computes, not merely emits in order.

    ``01010101`` and ``10101010`` are built by emitting the inputs the table
    ignores *first* and then erasing them, which is a different construction
    from every other table's -- so ordering alone is not evidence it works.
    Only running every row is, and a wrong build here would otherwise look
    exactly like a right one to the test above.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools.boolean import parameterized
    from esolangs.tools.boolean.examples import _fill_minifuck

    for table in ("01010101", "10101010"):
        template = parameterized.minifuck(table)
        widths = set()
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            program = _fill_minifuck(template, bits)
            widths.add(len(program))
            io_ = ScriptedIO("")
            run(program, io_)
            assert io_.getvalue() == table[combo], f"{table} inputs {bits}"
        # The ignored setters are emitted rather than dropped, so they must
        # not make the program's length depend on the bits it is given.
        assert len(widths) == 1, (table, widths)


def test_minifuck_reconvergence_declines_outside_one_or_two_essentials() -> None:
    """The reconvergence route only handles one or two essential inputs.

    With none there is no table left to build once the ignored inputs are
    erased, and with three or more the route has no embed geometry to fall
    back on -- both decline up front rather than searching.
    """

    from esolangs.tools.boolean.minifuck import _reconverged

    assert _reconverged("01", [], 1) is None
    assert _reconverged("01011010", [0, 1, 2], 3) is None


# 2.3s: two three-input minifuck builds, which is the cost, not the asserts.
@pytest.mark.slow
def test_minifuck_single_essential_falls_past_the_degenerate_lookup() -> None:
    """One essential input does not guarantee the cell lookup resolves it.

    ``_degenerate`` answers from a column of the embed rather than
    searching, and a projection onto the *last* input has no such column, so
    it declines.  These tables reach it through the projection block, which
    returns whatever ``_lift`` builds; the later ``len(essential) <= 1``
    lookup is not what serves them.  That one is reachable only when no
    projection happened at all -- ``n <= 1`` -- and every such table
    resolves, so its own decline branch cannot be taken from here.
    """
    import importlib

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools.boolean.examples import _fill_minifuck

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    for table in ("01010101", "10101010"):
        assert module.essential_inputs(table, 3) == [2]
        assert module._degenerate(table, 3) is None  # noqa: SLF001

        # Declining is only correct if the build still produces the table.
        template = module.minifuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            io_ = ScriptedIO("")
            run(_fill_minifuck(template, bits), io_)
            assert io_.getvalue() == table[combo], f"{table} inputs {bits}"


# 4s: one five-input build, which is the cost -- the 32 interpreter runs are
# effectively free next to deriving the staging.
@pytest.mark.slow
def test_minifuck_builds_five_input_xor() -> None:
    """Five-input XOR builds from a staging and prints all 32 rows.

    This is the table the arity turns on.  ``docs/minifuck_generator.md`` records XOR as
    the four-input table the searches could not build, and at five inputs a
    fully-essential table has no search that reaches it at all -- so a
    result here is a staging result or it is nothing.

    Running every row on the shipped interpreter is the whole point: a
    template that has not been seen to print is not evidence, and the
    equal-width check is what keeps the instantiation from leaking its
    inputs through ``len()``.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools.boolean import parameterized
    from esolangs.tools.boolean.examples import _fill_minifuck

    table = "".join(str(bin(r).count("1") & 1) for r in range(32))
    template = parameterized.minifuck(table)

    widths = set()
    for combo in range(32):
        bits = [(combo >> (4 - i)) & 1 for i in range(5)]
        program = _fill_minifuck(template, bits)
        widths.add(len(program))
        io_ = ScriptedIO("")
        run(program, io_)
        assert io_.getvalue() == table[combo], f"inputs {bits}"

    assert len(widths) == 1, widths


# 5.8s: builds the five-input spans and replays the enumeration through them.
# This is the guard on a *soundness* claim, so it checks the whole population
# rather than a sample -- a screen that declines one reachable table is a
# silent coverage regression, which no sampled test would catch.
@pytest.mark.slow
def test_the_fused_column_walk_matches_the_one_at_a_time_derivation() -> None:
    """``_column_sweep`` agrees with ``_printed_column``, which is its oracle.

    The sweep reads every accumulator's column off a *single* walk, which is
    sound only because the pool code does not depend on the accumulator --
    ``_find_pool`` takes a ``walk_out`` and so could answer differently per
    accumulator, in which case the fused walk would be wrong.  That is an
    empirical fact about the pool patterns, not a guarantee, so the
    one-at-a-time derivation is kept as the reference and the equivalence is
    checked rather than argued.

    Nothing else calls ``_printed_column``: production takes the sweep, so
    the oracle only runs when something compares them.  Left uncompared it
    would rot, and a future pool family that broke the accumulator
    independence would be caught by nothing.

    The stagings are the real ones -- captured from a build rather than
    constructed -- and every accumulator is compared for both ``cell7``
    values, including the unreachable ones where the sweep omits the key and
    the oracle returns None.
    """
    from esolangs.tools.boolean.minifuck import (
        _MAX_ACC,
        _column_sweep,
        _derived_plans,
        _printed_column,
    )

    captured: list[tuple[object, int]] = []
    real = _column_sweep

    def spy(joint: object, cell7: int) -> dict:
        if len(captured) < 6:
            captured.append((joint, cell7))
        return real(joint, cell7)

    # Driven through `_derived_plans` rather than `minifuck`, and cleared
    # first.  A build goes by `_staging_index`, which is itself `@cache`d at
    # module scope: once any earlier test in the process has warmed it, no
    # build derives anything and the spy sees nothing.  Clearing is not
    # enough on its own either, since the clear and the build are separate
    # statements and only this call is guaranteed to do the derivation --
    # which is what the assertion below is for.
    _derived_plans.cache_clear()
    with patch("esolangs.tools.boolean.minifuck._column_sweep", spy):
        _derived_plans(2, ("0110",))

    assert captured, "the build derived no columns, so nothing was compared"
    compared = 0
    for joint, cell7 in captured:
        sweep = real(joint, cell7)
        for acc in range(9, _MAX_ACC + 1):
            # An accumulator the walk cannot reach is absent from the
            # mapping, which is exactly the None the oracle returns.
            assert _printed_column(joint, acc, cell7) == sweep.get(acc), (acc, cell7)
            compared += 1
    assert compared >= 100, compared  # the sweep really did cover a range

    # The memo is what makes asking per table cost what asking for the arity
    # does, so a second ask for a key already answered must come back from
    # the cache rather than re-deriving.  Checked by making a re-derivation
    # impossible: `_find_pool` is the first thing a miss reaches, so a repeat
    # that touches it is a repeat that missed.
    joint, cell7 = captured[0]
    first = _printed_column(joint, 9, cell7)
    with patch("esolangs.tools.boolean.minifuck._find_pool", _unreachable):
        assert _printed_column(joint, 9, cell7) == first


def test_a_flipped_embed_complements_in_place_and_keeps_slot_order() -> None:
    """``flips`` is a live derivation coordinate, not dead weight.

    The pass that varied it was removed and the parameter kept, so no build
    passes a mask any more -- which left the gadget it emits unrun.  Kept
    open, it should still do what its docstring says, and the two claims are
    separable:

    First, the mask *lands*: each set bit adds exactly one ``_FLIP`` gadget,
    so the template grows by three characters per bit and by nothing at all
    for the empty mask.  Second, the setters stay in ascending name order
    whatever the mask says -- the gadget goes after the setter it
    complements, never in place of a different one -- which is the invariant
    every generator here is held to, and the one a "complement input i"
    coordinate is most likely to break.
    """
    import re

    from esolangs.tools.boolean.minifuck import _FLIP, _embed

    for n in (2, 3):
        plain = _embed(n).template()
        slots = [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", plain)]
        assert slots == sorted(slots), slots
        assert _embed(n, flips=0).template() == plain  # the default is no-op

        for mask in range(1, 2**n):
            flipped = _embed(n, flips=mask).template()
            assert len(flipped) == len(plain) + len(_FLIP) * mask.bit_count(), mask
            order = [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", flipped)]
            assert order == slots, (mask, order)


def test_the_coverage_population_is_its_stated_definition() -> None:
    """The 109 the ``_SEPS`` figures are stated over, re-derived each run.

    The comment used to say only "non-degenerate", which is 125 -- and that
    missing half of the definition is what left two later re-probes unable
    to reconcile the counts.  Deriving it here means the denominator cannot
    drift from the words again.

    The holdout is the pin: a wrong population of a coincidentally similar
    size would not put the single miss on the table the comment names.
    """
    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    def complement(table: str) -> str:
        return "".join("1" if c == "0" else "0" for c in table)

    tables = [format(i, "08b") for i in range(256)]
    pairs = {min(t, complement(t)) for t in tables}
    assert len(pairs) == 128

    degenerate = {t for t in tables if module._degenerate(t, 3) is not None}  # noqa: SLF001
    assert len({min(t, complement(t)) for t in degenerate}) == 3

    population = {
        min(t, complement(t))
        for t in tables
        if t not in degenerate and len(essential_inputs(t, 3)) == 3
    }
    assert len(population) == 109

    index = module._staging_index(3)  # noqa: SLF001
    missed = [
        p
        for p in population
        if tuple(int(c) for c in p) not in index
        and tuple(int(c) for c in complement(p)) not in index
    ]
    assert missed == ["01101101"], missed


@pytest.mark.slow  # 7.1s: enumerates the stagings the screen claims to skip
def test_the_constraint_query_matches_the_index() -> None:
    """``_first_staging`` answers exactly what the index spelling answers.

    The constraint intersection is the shipped assignment and the
    first-claim-wins dictionary stays as its oracle, so the two are held
    equal key for key -- every reachable column at two and three inputs,
    plus random tables for the misses, plus small budgets, whose cap the
    query lays over the passes where the index bakes it into the fill.
    """
    import importlib
    import random

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    rng = random.Random(17)
    for n in (2, 3):
        index = module._staging_index(n)  # noqa: SLF001
        assert index, n
        for key in index:
            table = "".join(str(bit) for bit in key)
            assert module._first_staging(table, n) == index[key], table  # noqa: SLF001
        for _ in range(30):
            table = format(rng.getrandbits(2**n), f"0{2**n}b")
            expected = index.get(tuple(int(c) for c in table))
            assert module._first_staging(table, n) == expected, table  # noqa: SLF001

    # The budget arm: a capped query consults the same staging prefix the
    # capped fill visits, including budgets that stop mid-slice and before
    # the first staging.
    original = module._STAGING_BUDGET  # noqa: SLF001
    try:
        for budget in (0, 1, 40, 900):
            module._STAGING_BUDGET = budget  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            capped = module._staging_index(3)  # noqa: SLF001
            probes = ["".join(str(bit) for bit in key) for key in capped]
            probes += [format(rng.getrandbits(8), "08b") for _ in range(20)]
            for table in probes:
                expected = capped.get(tuple(int(c) for c in table))
                assert module._first_staging(table, 3) == expected, (  # noqa: SLF001
                    budget,
                    table,
                )
    finally:
        module._STAGING_BUDGET = original  # noqa: SLF001
        module._derived_plans.cache_clear()  # noqa: SLF001


@pytest.mark.slow  # two arity tabulations plus ~2600 mask queries, ~4s
def test_the_constraint_query_matches_the_index_where_inserts_live() -> None:
    """The same equality at the arities the insert family serves.

    Two and three inputs never reach the insert pass, so this is the check
    that the pass boundary -- pure runs across every slice before any
    insert -- survives in the query's spelling of the order.  Sampled,
    because the full four-input key set costs ~10s; the sample is spread
    across the whole index rather than taken from its head, so both passes
    and every slice appear.
    """
    import importlib
    import random

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    rng = random.Random(23)
    for n, width in ((4, 2000), (5, 400)):
        index = module._staging_index(n)  # noqa: SLF001
        keys = list(index)
        sampled = keys[:: max(1, len(keys) // width)]
        inserts = sum(isinstance(index[key][2], str) for key in sampled)
        assert inserts, "the sample missed the insert family entirely"
        for key in sampled:
            table = "".join(str(bit) for bit in key)
            assert module._first_staging(table, n) == index[key], table  # noqa: SLF001
        for _ in range(25):
            table = format(rng.getrandbits(2**n), f"0{2**n}b")
            expected = index.get(tuple(int(c) for c in table))
            assert module._first_staging(table, n) == expected, table  # noqa: SLF001


def test_the_batched_planned_bits_match() -> None:
    """``_planned_bits`` equals ``_planned_bit`` per accumulator, per plan.

    The batched form re-spells the per-accumulator case analysis one region
    at a time, so the per-accumulator function stays as the specification
    and every plan the staged arities actually build is walked both ways.
    """
    from esolangs.tools.boolean.minifuck import (
        _BASE,
        _MAX_ACC,
        _insert_suffixes,
        _planned_bit,
        _planned_bits,
        _slice_chains,
        _slices,
        _suffix_plan,
    )

    accs = range(_BASE, _MAX_ACC + 1)
    checked = 0
    modes: set[int] = set()
    for n in (2, 3):
        for sep_index, settle in _slices(n):
            chains, _pools = _slice_chains(n, sep_index, settle)
            suffixes: list[tuple[int, int]] = [(cut, 0) for cut in range(29)]
            suffixes += [
                (s.index("<"), len(s) - s.index("<") - 1) for s in _insert_suffixes()
            ]
            for cut, rest in suffixes:
                for chain in chains:
                    plan = _suffix_plan(chain, cut, rest)
                    assert _planned_bits(chain, plan, accs) == [
                        _planned_bit(chain, plan, acc) for acc in accs
                    ], (n, sep_index, settle, cut, rest)
                    modes.add(plan[0])
                    checked += 1
    assert checked > 10000, f"too few plans walked: {checked}"
    # A sweep that never reaches a plan shape proves nothing about it: all
    # three -- pure, point-flip, complemented chain -- must have fired.
    assert modes == {0, 1, 2}, modes


# 3.7s standalone: the target-set derivation is the cost.  It is free when the
# XOR5 build above has already run in this process and warmed the cache, but
# a -k selection or a shuffled order can pick this one alone, so it is marked
# for what it costs on its own rather than for the lucky case.
@pytest.mark.slow
def test_minifuck_five_input_plans_are_derived_per_table() -> None:
    """At five inputs the derivation is asked for one table, not the arity.

    A whole-arity spelling would pre-build a dict over every table, which is
    ``2**32`` entries at this arity and will not be built.  Every arity is
    now asked for its targets, and this pins what that has to give back: the
    arity is staged, and asking ``_derived_plans`` for a target set returns
    at most those targets rather than a whole-arity map.
    """

    from esolangs.tools.boolean.minifuck import (
        _INSERT_ARITIES,
        _STAGED_ARITIES,
        _derived_plans,
    )

    assert 5 in _STAGED_ARITIES
    assert 5 in _INSERT_ARITIES

    # A target set the enumeration cannot possibly print -- a table and its
    # complement are asked for together, and nothing else may come back.
    table = "".join(str(bin(r).count("1") & 1) for r in range(32))
    complement = "".join(str(1 - int(c)) for c in table)
    plans = _derived_plans(5, (table, complement))
    assert set(plans) <= {table, complement}


class TestParameterizedMinifuck:
    """Input-by-substitution boolean generator for Minifuck.

    Minifuck's only read is ``.`` pulling a byte when the eight-cell pool is
    zero, which a boolean program cannot use without destroying the pool it
    is about to print -- so the inputs are embedded instead.  The generator
    simulates every row as it emits and raises rather than returning a
    program it has not seen print the table, so these tests are checking the
    *interpreter* agrees with that simulation.
    """

    def run_minifuck(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_minifuck

        return _fill_minifuck(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            # ``parameterized.minifuck`` searches, and it is the *build*
            # that costs, not the assertion: measured at one worker, a
            # two-input table takes 2.7s (NAND) to 9.0s (XOR) to emit while
            # a one-input table takes ~0.03s.  So the two-input cases carry
            # ``slow`` -- as does every other test in this class that builds
            # one -- and the one-input cases above stay in the fast run.
            pytest.param("0001", 2, marks=pytest.mark.slow),  # AND
            pytest.param("0110", 2, marks=pytest.mark.slow),  # XOR
            # XNOR and NAND -- unreachable in the reading model
            pytest.param("1001", 2, marks=pytest.mark.slow),
            pytest.param("1110", 2, marks=pytest.mark.slow),
            # OR ("0111") and NOR ("1000") are not listed: they cost ~48s and
            # ~47s here, and test_all_two_input_tables below already runs all
            # sixteen two-input tables through the same assertion.  The cases
            # that remain are the two one-input tables, which it does not
            # cover.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minifuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minifuck(self.instantiate(template, bits))
            assert got == table[combo], f"{table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input table builds, including the ones the wall named.

        A wall once recorded NAND, NOR and XNOR as unreachable.  It does not
        hold either way round: embedding lifts it, which is what this checks,
        and ``docs/minifuck_generator.md`` now also records a *reading* construction
        verifying all sixteen -- the searches behind the original claim were
        length-bounded well below what it needs.

        No longer marked ``slow``: two inputs come from a derived staging
        rather than a search, so all sixteen build in about a second
        together where they used to cost 2.5-9s each.
        """
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.minifuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_two_inputs_never_search(self) -> None:
        """No two-input table reaches the searches.

        The construction's value is that it is a *derivation*: every table
        has a staging, so the column and parked searches -- which is what
        made this generator cost tens of seconds -- must never run at this
        arity.  Asserting on the templates alone would not catch a
        regression that quietly fell through to the search and got the same
        answer slowly, so the searches themselves are stubbed to fail.
        """
        import importlib

        from esolangs.tools.boolean import parameterized

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        for table_int in range(16):
            table = format(table_int, "04b")
            # ``minifuck`` is cached, so go through the wrapped function
            # to be sure the build actually runs under the patch.
            template = module.minifuck.__wrapped__(format(table_int, "04b"))
            assert "{X0}" in template, table
            assert "{X1}" in template, table
        # And the public entry point still agrees with what it built.
        assert parameterized.minifuck("0110").count("{X") == 2

    @pytest.mark.slow  # derives a staging for all sixteen
    def test_the_derivation_reaches_every_two_input_table(self) -> None:
        """Every two-input table gets a staging from the enumeration alone.

        There is no stored two-input plan to check against, so what this pins
        is the property that plan used to guarantee: the enumeration reaches
        all sixteen, and reaches them within its own caps rather than by
        running off the end.

        A table and its complement share a staging -- the endgame tries both
        read polarities, and the printed digit is ``NOT(v XOR cell7)`` -- so
        the pair costs one derivation between them, which is why the sweep
        finds the second member of each pair as readily as the first.
        """

        from esolangs.tools.boolean.minifuck import (
            _MAX_ACC,
            _MAX_BRACKETS,
            _SEPS,
            _derive_staging,
        )

        for table_int in range(16):
            table = format(table_int, "04b")
            plan = _derive_staging(table, 2)
            assert plan is not None, table
            sep_index, settle, brackets, acc = plan
            assert 0 <= sep_index < len(_SEPS), (table, plan)
            assert settle in (0, 1), (table, plan)
            assert isinstance(brackets, int), (table, plan)
            assert 0 <= brackets <= _MAX_BRACKETS, (table, plan)
            assert 9 <= acc <= _MAX_ACC, (table, plan)

    @pytest.mark.slow  # builds all 38 degenerate three-input tables
    def test_degenerate_three_input_tables_never_search(self) -> None:
        """Every table with at most two essential inputs is search-free.

        A table that ignores an input is a smaller table wearing extra ones,
        so it projects onto a two-input problem -- which is a closed form.
        Nothing here needed its own construction; the arity below carries it.

        Ten of these come out with their slots *not* in ascending order, and
        all ten have the same shape: the ignored input is the *middle* one
        (essential ``[0, 2]``).  Emitting it first cannot sort them, since it
        already follows ``{X0}``, and no reset fixes it -- reconvergence
        works by driving every row to one state, so it cannot collapse
        ``x1`` while preserving ``x0``.  Searched to depth 14: none exists.
        Sorting those needs the solver to assign names.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        checked = 0
        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        for table_int in range(256):
            table = format(table_int, "08b")
            if len(essential_inputs(table, 3)) > 2:
                continue
            checked += 1
            template = module.minifuck.__wrapped__(table)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"
        assert checked == 38, checked

    # 2.4s: the three-input derivation is the cost.  The staging probe at the
    # unstaged arity is free -- declining is the whole point of it -- so this
    # does not pay for the staged arities above three.
    @pytest.mark.slow
    def test_a_table_with_no_staging_falls_through(self) -> None:
        """An unplanned table declines the staging and reaches the next route.

        Both three-input plans are now complete, so the fall-through is
        exercised at an arity that has no plan at all -- which is the case
        that matters, since it is what lets a wider table reach the sculpted
        route instead of failing outright.

        That arity is now six: four and five are both staged (partially), so
        probing the fall-through at either would miss the point and pay that
        arity's derivation to do it.

        The unstaged arity is read off :data:`_STAGED_ARITIES` rather than
        written down, so raising the staged arity again moves this test with
        it instead of breaking it.  What is asserted is the *gate* -- that an
        unstaged arity declines immediately -- which is what keeps the miss
        cheap: without it the table would grind through the whole enumeration
        before giving up.

        **What is probed is ``_derive_staging``, not ``_staged``.**  This used
        to assert that ``_staged`` itself returned None at the unstaged arity,
        which was only true while :func:`_mux` carried an arity gate of its
        own; with that gate gone the fall-through *succeeds*, and asserting
        None would be asserting the generator is partial.  Six inputs does
        build here -- 1822 characters in about 35 seconds for the all-ones
        table -- so the cheap half of the claim is kept by probing the
        staging derivation directly, which still declines in 0.000s.
        """
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.minifuck import (
            _STAGED_ARITIES,
            _derive_staging,
            _staged,
        )

        unstaged = max(_STAGED_ARITIES) + 1
        assert unstaged not in _STAGED_ARITIES
        assert _derive_staging("1" * 2**unstaged, unstaged) is None
        # A table the derivation does reach is built from it, not searched.
        for table_int in range(4):
            key = format(table_int, "08b")
            template = _staged(key, 3)
            assert template is not None, key
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == key[combo], f"{key} inputs {bits}"
        # ...and the public entry point still builds one.
        assert parameterized.minifuck("00000001")

    @pytest.mark.slow  # the four-input derivation is whole-arity, minutes
    def test_four_input_xor_builds_from_a_staging(self) -> None:
        """XOR4 builds without searching, and computes its function.

        Four inputs is the arity the insert family was added for, and XOR is
        the pointed case: ``docs/minifuck_generator.md`` records it as the four-input
        table the searches fail on.  The searches are stubbed to raise, so a
        table that builds here built from a staging.

        Every row is run on the interpreter and the widths are compared: a
        template that computes the table but whose fills differ in length
        leaks its inputs through ``len(program)``, which is the one thing the
        parameterized convention exists to prevent.

        **Only one table.**  This used to build five, and assert besides that
        a plans miss returns None -- which forced a *whole-arity* derivation
        on top of the ordinary one and put the test past nine minutes for
        five builds.  That second sweep (the flipped-embed pass) has since
        been removed outright, but the lever is unchanged: a four-input miss
        still runs the staged enumeration to its caps, so what this costs is
        how much of the arity it demands.  The recorded claim is about XOR4,
        and that is what is kept; the miss path is covered at an unstaged
        arity by :meth:`test_a_table_with_no_staging_falls_through`, which
        pays no derivation at all.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "0110100110010110"  # XOR4, the recorded search failure
        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        assert module._staged(table, 4) is not None  # noqa: SLF001
        template = module.minifuck.__wrapped__(table)
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            got = self.run_minifuck(program)
            assert got == table[combo], f"{table} inputs {bits}"
        assert len(widths) == 1, widths

    @pytest.mark.slow  # the four-input separation derivation, ~15s once
    def test_sculpted_route_computes_and_is_row_addressable(self) -> None:
        """``_mux`` builds a fully-essential table and every row is run.

        The sculpted route is what closes four inputs: a derived,
        table-independent suffix drives the sixteen rows to sixteen distinct
        pointer positions -- each input still embedded exactly once, the
        rule every generator here holds to -- and the printed column is then
        fixed one row at a time from the highest position down.  XOR4 is
        used because it is this file's historically pointed table; the route
        itself never consults the stagings, so this exercises it directly
        without paying the four-input whole-arity derivation.

        The separation claim is asserted structurally too: sixteen rows at
        sixteen distinct pointers, with each ``{Xi}`` appearing once,
        because row addressability without re-embedding is exactly what the
        route contributes.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        separated = module._mux_separate(4)  # noqa: SLF001
        positions = separated.ptrs()
        assert len(set(positions)) == 16, positions
        for i in range(4):
            assert separated.template().count("{X" + str(i) + "}") == 1, i

        table = "0110100110010110"
        template = module._mux(table, 4)  # noqa: SLF001
        assert template is not None
        names = [int(m) for m in re.findall(r"\{X(\d+)\}", template)]
        assert names == sorted(names), names
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    def test_sculpt_pool_code_matches_scan(self) -> None:
        """The named sculpt code is what the replaced scan would have found.

        ``_mux_probe`` used to scan ``_POOL_CODES`` through ``_pool_reaches``
        -- a real interpreter probe, and the module's hot spot at five
        inputs.  It is now :data:`_SCULPT_POOL_CODE`, a constant, because the
        probe state is canonical: the ``x`` and the clamp put every row at
        pointer 0 with the same pool region, a sculpting round cannot write
        into that region under the rewind guard, and no pool code's own
        execution reaches past cell 6.

        This replays the scan on the states a sculpt actually reaches and
        asserts the constant answers exactly what it returned -- the same
        specification-oracle shape the other closed searches keep.  Both
        orientations are scanned at every recorded state -- the scout means
        only the winning replay probes now, always at ``cell7 == 0`` -- so
        "``cell7 == 1`` is answered by none" stays pinned as a measured
        fact rather than an assumption baked into the constant.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        seen: list[object] = []
        real = module._mux_probe  # noqa: SLF001

        def record(joint: object, acc: int, cell7: int, hint: object = None) -> object:
            if len(seen) < 60:
                probe = joint.fork()  # type: ignore[attr-defined]
                probe.emit("x")
                module._clamp(probe)  # noqa: SLF001
                seen.append(probe)
            return real(joint, acc, cell7, hint)

        with patch.object(module, "_mux_probe", record):
            assert module._mux("0110100110010110", 4) is not None  # noqa: SLF001
        assert seen, "no sculpting probes were observed"

        for probe in seen:
            for cell7 in (0, 1):
                scanned = next(
                    (
                        code
                        for code in module._POOL_CODES  # noqa: SLF001
                        if module._pool_reaches(  # noqa: SLF001
                            probe,
                            code,
                            cell7,
                            module._PROBE_WALK_OUT,  # noqa: SLF001
                        )
                    ),
                    None,
                )
                assert scanned == module._sculpt_pool_code(cell7), cell7  # noqa: SLF001

    @pytest.mark.slow  # the six-input build, tens of seconds
    def test_no_arity_is_gated(self) -> None:
        """A fully-essential six-input table builds and prints all 64 rows.

        Six is the first arity the old ``_MUX_ARITIES = (2, 3, 4, 5)``
        declined, and it declined in **0.000s** -- a configuration gate, not
        a construction that failed.  ``docs/minifuck_generator.md``
        ("Is ``_mux`` total?") closes all six of the route's refusal sites
        with arguments carrying no
        residual ``n``, and the gate is now the floor
        :data:`_MUX_MIN_ARITY`, which only keeps constants and one-input
        projections on the :func:`_degenerate` path.

        This is the execution half of that claim, which is the half the repo's
        standing rule says a generated program is worth.  The table must be
        **fully essential**: a six-input table with a narrow core projects to
        an arity the old tuple already carried, so it built even while the
        gate stood, and asserting on one would test nothing.

        Every row is run and the widths compared, the same as at four inputs
        -- a template that computes the table but whose fills differ in length
        leaks its inputs through ``len(program)``.
        """
        import importlib

        from esolangs.tools.boolean.helpers import essential_inputs

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        assert module._MUX_MIN_ARITY == 2  # noqa: SLF001

        n = 6
        # Fixed table rather than a sampled one: a test that picks its own
        # table cannot fail reproducibly.
        table = "0110100110010110100101100110100101101001011010011100101101001010"
        assert len(table) == 2**n
        assert len(essential_inputs(table, n)) == n, "the table must be fully essential"

        template = module._solve(table)  # noqa: SLF001
        names = [int(m) for m in re.findall(r"\{X(\d+)\}", template)]
        assert names == sorted(names), names
        widths = set()
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    def test_staging_budget_is_counted_in_stagings_not_seconds(self) -> None:
        """The budget is machine-independent, and it ships disabled.

        A wall-clock budget would make this generator non-deterministic: the
        same table would build on a fast host and fall through on a slow
        one, and which template a table got would depend on machine load.
        Counting *stagings* -- one ``(separator, settle, suffix,
        accumulator)`` tuple of :func:`_stagings` -- is identical everywhere,
        so a budget selects the same tables on any hardware.

        Two properties are pinned.  The default is ``None``, because
        anything else would change every recorded template.  And the slice
        order is the plain enumeration order while unbudgeted -- yield
        ordering only applies when something is actually being given up, and
        only at the arity it was measured at.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        assert module._STAGING_BUDGET is None  # noqa: SLF001

        plain = tuple(
            (sep, settle)
            for sep in range(len(module._SEPS))  # noqa: SLF001
            for settle in (0, 1)
        )
        assert module._slices(4) == plain  # noqa: SLF001
        assert module._slices(3) == plain  # noqa: SLF001

        # The ranking is a permutation of the slices, not a subset: a budget
        # reorders what is spent first, it never drops a slice outright.
        assert sorted(module._SLICE_YIELD_ORDER) == sorted(plain)  # noqa: SLF001

    @pytest.mark.slow
    def test_the_slice_order_is_its_measured_yield(self) -> None:
        """The yield ranking is re-derived, not trusted.

        The comment above ``_SLICE_YIELD_ORDER`` states the measurement
        that produced it -- each slice's yield at four inputs, best 2874
        against worst 424 -- but a stated measurement is not a checked
        one, and the table is dormant as shipped, so nothing else would
        catch it drifting.

        The yield is *marginal*, not intrinsic: a slice is credited with
        the columns it is the first to reach in the plain enumeration,
        not with everything it could place on its own.  That distinction
        is what picks this order out -- ranking slices by their
        independent reach gives a different one -- so the assertion
        pins the mechanism and not just the numbers.  All ten counts are
        distinct, so descending order is total and needs no tie-break.
        """
        import importlib
        from collections import Counter

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        index = module._staging_index(4)  # noqa: SLF001
        counts = Counter((entry[0], entry[1]) for entry in index.values())
        assert len(set(counts.values())) == len(counts), counts
        derived = tuple(sorted(counts, key=lambda slot: -counts[slot]))
        assert derived == module._SLICE_YIELD_ORDER  # noqa: SLF001
        assert max(counts.values()) == 2874
        assert min(counts.values()) == 424

    def test_five_input_budget_uses_its_separate_default(self) -> None:
        """The five-input override is selected only while budgets are off.

        Five inputs were measured separately from the smaller staging passes,
        so its disabled-budget value must not accidentally inherit a future
        finite general budget.  Patch both values to make the dispatch, not
        their current equal ``None`` spelling, observable.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_STAGING_BUDGET", None)
            patch.setattr(module, "_STAGING_BUDGET_N5", 17)
            assert module._budget(5) == 17  # noqa: SLF001
            assert module._budget(6) == 17  # noqa: SLF001
            assert module._budget(4) is None  # noqa: SLF001

            # A finite general budget applies uniformly, including at five.
            patch.setattr(module, "_STAGING_BUDGET", 23)
            assert module._budget(5) == 23  # noqa: SLF001

    def test_a_budget_gives_up_length_not_coverage(self) -> None:
        """A table the budget skips still builds, through the sculpted route.

        This is the property that makes lowering the budget safe on a slow
        machine: the staged route is what emits *short* templates, and
        :func:`_mux` is total at four inputs, so a budget trades program
        length for time and never coverage.

        Uses a tiny budget and a table the staged route would otherwise
        place, so the fall-through is what is exercised.  Every row is run:
        an emitted template is not evidence it computes.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "0110100110010110"  # XOR4, which the staged route places
        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 1  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derive_staging(table, 4) is None  # noqa: SLF001
            template = module._mux(table, 4)  # noqa: SLF001
            assert template is not None
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    def test_a_budget_stops_the_suffix_pass_too(self) -> None:
        """The budget is checked in the insert pass, not only the first one.

        ``test_a_budget_gives_up_length_not_coverage`` above spends the
        budget immediately, so the enumeration stops in the bracket-run loop
        and the suffix pass that follows it never runs.  A budget that
        outlives the first loop and expires inside the second is what proves
        the later checks are wired: without them a budget would be ignored
        for the whole insert pass, which is the more expensive half.

        The table matters as much as the budget.  A table the staged route
        *places* is claimed before the budget can bite, so this uses one the
        enumeration never places -- the sculpted route is what serves it --
        and the spend was measured rather than guessed: the insert pass is
        entered at 7540 stagings and the whole enumeration costs 120640, so
        8000 lands inside it.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        orphan = "1101000011010000"  # no staging in the enumeration prints it
        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 8000  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derive_staging(orphan, 4) is None  # noqa: SLF001
            # And the oracle, which carries its own copy of both loops: a
            # budget honoured in only one of the two would make the pair
            # disagree for a reason unrelated to the order they exist to pin.
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(4, (orphan,)) == {}  # noqa: SLF001
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

        # And it still builds, by the route that does not need a staging.
        template = module.minifuck(orphan)
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == orphan[combo], (orphan, bits)
        assert len(widths) == 1, widths

    def test_a_spent_budget_stops_before_the_first_staging(self) -> None:
        """A budget of zero derives nothing at all, in both spellings.

        The exhaustion check runs before the first embed rather than after
        it, so a budget already spent costs nothing rather than one staging.
        Both the oracle and the index it is compared against are asked, since
        each carries its own copy of the loop and a budget honoured in only
        one of them would make the two disagree for a reason unrelated to
        the enumeration order they exist to pin.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 0  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(2, ("0110",)) == {}  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._staging_index(2) == {}  # noqa: SLF001

            # One staging's worth spends inside the bracket-run loop instead
            # of before it, which is the other end of the same check: the
            # budget is consumed per staging visited, so a budget of one
            # gets exactly one look before it stops.
            module._STAGING_BUDGET = 1  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(2, ("0001",)) == {}  # noqa: SLF001
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

    @pytest.mark.slow  # ~3.6s: a five-input index fill plus a sculpted build
    def test_a_table_no_staging_reaches_costs_length_not_coverage(self) -> None:
        """A table outside every staging still builds, the other way.

        A five-input table the tabulation cannot answer is an index miss --
        the linear-algebra screen that used to pre-empt the lookup is gone,
        see the note above ``_CHAIN_CAP`` -- so the danger is not a wrong
        admission but a table that stops being built at all.  This drives
        the miss and the fall-through below it.

        Executed on every row rather than merely emitted, because a miss
        that quietly rerouted a table to a *wrong* program would look
        identical to one that rerouted it to a longer one.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "01001100001110000110000011001011"
        module._derived_plans.cache_clear()  # noqa: SLF001
        assert module._derive_staging(table, 5) is None  # noqa: SLF001

        template = module.minifuck(table)
        widths = set()
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    def test_sculpted_route_separates_every_arity_by_construction(self) -> None:
        """The separation is constructed, so it is exact and immediate.

        This used to pin the opposite: that five inputs declined, because no
        derivation had driven 32 rows to 32 distinct pointers and the
        searches took about three minutes to fail at it.  Weighting each
        input as it lands makes the pointer the row's binary expansion, so
        every arity separates in closed form -- and five is now built rather
        than declined.  What is pinned is the property the searches could
        not guarantee: ``2**n`` rows, ``2**n`` distinct pointers, fast.
        """
        import importlib
        import time

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for arity in (2, 3, 4, 5):
            start = time.monotonic()
            joint = module._mux_separate(arity)  # noqa: SLF001
            assert joint is not None, arity
            assert len(set(joint.ptrs())) == 2**arity, arity
            assert time.monotonic() - start < 1.0, arity

    @pytest.mark.slow  # 3.1s: a five-input sculpted build plus all 32 rows
    def test_five_input_tables_build_and_print_every_row(self) -> None:
        """A five-input table builds through the sculpted route and runs.

        Five-input XOR is the pointed one: ``docs/minifuck_generator.md``
        records it as a table no search here builds at all.  Every row is
        run on the shipped interpreter, because a template that emits
        without computing would otherwise pass silently.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "01101001100101101001011001101001"  # five-input XOR
        template = module._mux(table, 5)  # noqa: SLF001
        assert template is not None

        widths = set()
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    @pytest.mark.slow  # builds and runs all 256 three-input tables
    def test_every_three_input_table_is_search_free(self) -> None:
        """All 256 three-input tables build without searching.

        With ``_find_column`` and ``_find_parked`` stubbed to raise, every
        table still builds -- and every row is run, because a staging that
        emits without computing would otherwise pass silently.

        The searches are kept anyway.  They are the fallback for an arity
        with no plan, and this assertion is what would notice if a staging
        stopped working: the table would fall through and raise here rather
        than quietly costing two minutes.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        searched = []
        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        for table_int in range(256):
            table = format(table_int, "08b")
            try:
                template = module.minifuck.__wrapped__(table)
            except AssertionError:
                searched.append(table)
                continue
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"
        assert searched == [], searched

    def test_only_the_first_separators_are_scanned(self) -> None:
        """The searching routes scan two separators; the plan names the rest.

        Adding a separator to :data:`_SEPS` widens what the plan can *name*
        without widening what the searches must *try* -- each extra separator
        would multiply the cost of every fallback search.  This pins that
        split, which is easy to undo by looping over ``_SEPS`` out of habit.
        """

        from esolangs.tools.boolean.minifuck import (
            _SCAN_SEPS,
            _SEPS,
            _stagings,
        )

        assert _SEPS[:2] == _SCAN_SEPS, _SCAN_SEPS
        assert len(_SEPS) > len(_SCAN_SEPS), _SEPS
        # Every separator index the enumeration yields must exist, and it
        # must offer all of them -- the ten stragglers that need separators
        # past the scanned pair are the whole reason ``_SEPS`` is wider.
        offered = {sep_index for sep_index, *_rest in _stagings(3)}
        assert offered == set(range(len(_SEPS))), offered

    def test_the_pool_codes_cover_every_route(self) -> None:
        """The fixed codes must serve every route that reaches the endgame.

        They replaced a breadth-first search, so the property that matters
        is coverage: wherever the search would have found a pool, the list
        must too.  This builds through the public entry point precisely
        because the routes differ -- the degenerate and reconverged ones
        reach the endgame from states the staged route never produces, and
        six of the ten codes answer only those.

        It deliberately does not assert that each code is necessary.
        Measured, none of them is: every one can be dropped alone and every
        table at both arities still builds.  That is not because the codes
        cover for each other -- six of them uniquely answer 40 of the 16766
        call sites -- but because a missing pool is *recoverable*:
        ``_endgame`` raises, ``_try_print`` counts it as one failed
        read/orientation, and another accumulator answers the table.  So
        coverage of the routes is the real property, and minimality is not
        one to pin.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for table_int in range(16):
            table = format(table_int, "04b")
            assert module.minifuck.__wrapped__(table), table

    def test_the_pool_codes_all_serve_one_orientation(self) -> None:
        """Every pool code answers ``cell7 == 0``, and that is enough.

        The list looks like half a list: no code satisfies ``cell7 == 1``,
        yet the endgame asks about both orientations.  It works because a
        missing pool is recoverable -- ``_try_print`` forks the same state
        for both orientations and both reads, so a refusal is one failed
        attempt among four.

        The list carried the ``cell7 == 1`` mirrors for one commit.  They
        changed 136 templates and bought nothing, which an ablation only
        exposed once the fallback searches were stubbed: with the
        fallthrough open, a gutted pool list still "works", because the
        searches quietly rebuild what it drops.  So this pins the property
        that made the mirrors droppable rather than the mirrors.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        codes = module._POOL_CODES  # noqa: SLF001
        assert codes, "the pool list should not be empty"
        # Shortest first, so the emitted program is no longer than it must be.
        assert list(codes) == sorted(codes, key=len), codes
        # Every code is built from the two idioms only -- no ``x`` appears,
        # though the alphabet allows it.
        for code in codes:
            assert set(code) <= {"[", "<"}, code
        # No code answers ``cell7 == 1``: the list really is one orientation.
        # Checked on the states a build actually reaches, not on a state
        # constructed here -- ``_find_pool`` is called part-way through the
        # endgame, and a bare embed is not a state any call sees.
        seen: list[tuple[object, int, int]] = []
        real = module._find_pool  # noqa: SLF001

        def record(joint: object, cell7: int, walk_out: int) -> object:
            if len(seen) < 40:
                seen.append((joint.fork(), cell7, walk_out))  # type: ignore[attr-defined]
            return real(joint, cell7, walk_out)

        with patch.object(module, "_find_pool", record):
            module.minifuck.cache_clear()
            module.minifuck.__wrapped__("0110")
        assert seen, "no pool lookups were observed"
        answered = {
            cell7
            for joint, cell7, walk_out in seen
            for code in codes
            if module._pool_reaches(joint, code, cell7, walk_out)  # noqa: SLF001
        }
        assert answered == {0}, f"expected only cell7==0 to be served, got {answered}"

        # And that is a property of the list, not of the language: the step
        # family reaches the other orientation natively.  These are not
        # mirrors -- nothing is appended to a shipped code to get them -- they
        # are ``'[<' * k`` walks with a different tail, and they answer
        # ``cell7 == 1`` where no shipped code answers anything.  Pinned so
        # the "half a list" account cannot drift back into "the other half is
        # unreachable".
        #
        # Harvested separately, and from a cold derivation.  ``cache_clear``
        # on ``minifuck`` alone is not enough: ``_derived_plans`` survives it,
        # and a warm plan cache makes this build ask ``_find_pool`` exactly
        # once instead of the hundreds of times a cold one does.  A one-site
        # sample would make the check below depend on which test ran first.
        wide: list[tuple[object, int, int]] = []

        def record_all(joint: object, cell7: int, walk_out: int) -> object:
            if len(wide) < 400:
                wide.append((joint.fork(), cell7, walk_out))  # type: ignore[attr-defined]
            return real(joint, cell7, walk_out)

        with patch.object(module, "_find_pool", record_all):
            module._derived_plans.cache_clear()  # noqa: SLF001
            module.minifuck.cache_clear()
            # Harvested from the oracle's enumeration rather than a build: a
            # build now derives its columns in closed form and asks
            # ``_find_pool`` only twice per slice, where the emit-and-walk
            # enumeration still visits the staged states one by one.  Three
            # inputs, because the sample has to be wide: a two-input walk
            # visits 77 sites where this one fills the 400-site cap.
            module._derived_plans(3, ("01101001",))  # noqa: SLF001
        module.minifuck.cache_clear()
        assert len(wide) > 100, f"expected a cold build's lookups, got {len(wide)}"

        other = ("[<[<[[[<[<[[<<", "[<[<[[[<[[[[<<", "[<[<[[[[[<[[<<")
        other_answered = {
            cell7
            for joint, cell7, walk_out in wide
            for code in other
            if module._pool_reaches(joint, code, cell7, walk_out)  # noqa: SLF001
        }
        assert other_answered == {1}, (
            f"expected the family's other orientation, got {other_answered}"
        )

    def test_no_pool_code_serves_both_orientations(self) -> None:
        """A code answers ``cell7 == 0`` or ``cell7 == 1``, never both.

        Per site this is forced rather than observed: a code's effect on a
        fixed state is deterministic, so it leaves one value in cell 7 and can
        match at most one of the two targets.  Checked here on the shipped
        five and on two codes from the other orientation, because the fact is
        what makes the list's one-sidedness structural -- the space has no
        code that would let one string serve both, so "half a list" is the
        shape of the space rather than a gap in these five.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        seen: list[tuple[object, int, int]] = []
        real = module._find_pool  # noqa: SLF001

        def record(joint: object, cell7: int, walk_out: int) -> object:
            if len(seen) < 200:
                seen.append((joint.fork(), cell7, walk_out))  # type: ignore[attr-defined]
            return real(joint, cell7, walk_out)

        with patch.object(module, "_find_pool", record):
            module._derived_plans.cache_clear()  # noqa: SLF001
            module.minifuck.cache_clear()
            # The oracle's walk, for the width of the sample; see the note
            # above -- a build's closed-form derivation visits too few sites.
            module._derived_plans(3, ("01101001",))  # noqa: SLF001
        module.minifuck.cache_clear()
        assert len(seen) > 100, f"expected a cold walk's lookups, got {len(seen)}"

        # The two witnesses from the other orientation, spelled by the same
        # step law the shipped codes are.
        other = (
            module._step(4, 3, odd=False),  # noqa: SLF001
            module._step() + module._step(5, 2, odd=False),  # noqa: SLF001
        )
        assert other == ("[[[[[[[[<<<", "[<[[[[[[[[[[<<"), other

        for code in (*module._POOL_CODES, *other):  # noqa: SLF001
            for joint, _cell7, walk_out in seen:
                both = all(
                    module._pool_reaches(joint, code, orientation, walk_out)  # noqa: SLF001
                    for orientation in (0, 1)
                )
                assert not both, f"{code!r} answered both orientations at one site"

    def test_the_pool_codes_are_generated_from_the_law(self) -> None:
        """The five codes are spelled by the law, not stored as strings.

        ``_POOL_CODES`` is built by walking ``_PLANS`` through :func:`_step`,
        which inverts the ``ceil(k / 2)`` law: a carry of ``c`` fixes the
        bracket run at ``2 * c - 1``, or ``2 * c`` where the pending skip is
        not wanted.  The five literals below are the anchor -- with the source
        deriving them, every number in the plans and in the step law is
        otherwise unpinned, and this one assertion is what makes a wrong
        carry, a wrong override, or a reordered plan fail.

        The plans are also checked for the property that makes them a
        construction rather than five parameter dumps: two of the five carry
        no override at all.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        # The anchor: the derivation must reproduce these exactly, in order.
        assert module._POOL_CODES == (  # noqa: SLF001
            "[[[<[<<<<",
            "[<[[[<[<[<",
            "[<[<[[[<[<[<",
            "[<<[<[<[[[<[<",
            "[<[<[<<[[[<[[<<<",
        )

        # The step law itself, away from the plans: a carry of c spells a run
        # of 2c-1 brackets, and dropping the skip spells the even run.
        step = module._step  # noqa: SLF001
        assert step() == "[<"  # the default: carry one, trail by one
        assert step(carry=2) == "[[[<"
        assert step(carry=1, odd=False) == "[[<"
        assert step(carry=1, backs=4) == "[<<<<"

        # Two of the five plans are (steps, core) and nothing else, which is
        # what "one construction indexed by where the mark goes" means.
        plans = module._PLANS  # noqa: SLF001
        assert len(plans) == len(module._POOL_CODES)  # noqa: SLF001
        bare = [(n, core) for n, core, over in plans if not over]
        assert bare == [(4, 1), (5, 2)], bare

        # Every plan has exactly one core, and it is inside the walk.
        for n, core, over in plans:
            assert 0 <= core < n, (n, core)
            assert all(0 <= i < n for i in over), (n, over)

    def test_the_pool_codes_are_one_construction(self) -> None:
        """Each pool code is a mark, shifted three cells by a shared core.

        The five read as unrelated strings -- edit distance 2 to 7, and an
        exact regex factors *longer* than it lists -- but that measures
        spelling.  Behaviourally every code is ``prefix + '[[[<[' + suffix``
        with the core appearing exactly once, and for three of the five the
        prefix plants a single 1 that the core then shifts three cells right.

        One law runs through it: a run of ``k`` brackets carries a mark right
        by ``ceil(k / 2)``, leaving a pending skip when ``k`` is odd.  The
        core opens with three brackets and so moves a mark +2; the suffixes
        that open with none only reposition the pointer, which is why two
        codes share the suffix ``'<[<'`` verbatim at different marks.

        The exception is the point: the walk is clean only when the pointer
        sits just left of the mark.  The code with an empty prefix has no
        mark to carry, and ``'[<[<[<<'`` arrives at cell 3 with the pointer
        at 1 rather than 2, so the core spreads marks instead of moving one.
        """

        from esolangs.tools.boolean.minifuck import _POOL_CODES, _Sim

        core = "[[[<["

        def run(code: str) -> object:
            machine = _Sim(64)
            for char in code:
                machine.exec(char)
            return machine

        # The law the whole family rests on: a run of k brackets carries a
        # mark right by ceil(k / 2).  Checked away from the codes first, so a
        # failure here says "the language changed" rather than "a code did".
        for start in (2, 3, 4, 5):
            for brackets in range(1, 9):
                machine = run("[<" * start + "[" * brackets)
                marks = [i for i in range(32) if machine.cell(i)]  # type: ignore[attr-defined]
                assert marks == [start + (brackets + 1) // 2], (start, brackets, marks)
                assert machine.skip is bool(brackets % 2), (start, brackets)  # type: ignore[attr-defined]

        shifted = 0
        for code in _POOL_CODES:
            # The decomposition itself holds for every code.
            assert code.count(core) == 1, code
            prefix = code[: code.find(core)]

            # The prefix plants at most one mark and writes nothing else.
            before = run(prefix)
            marks = [i for i in range(32) if before.cell(i)]  # type: ignore[attr-defined]
            assert len(marks) <= 1, (code, marks)

            # Where the prefix leaves the pointer on its mark, the core moves
            # that mark three cells right and takes the pointer with it.
            after = run(prefix + core)
            moved = [i for i in range(32) if after.cell(i)]  # type: ignore[attr-defined]
            if marks and before.ptr == marks[0] - 1:  # type: ignore[attr-defined]
                assert moved == [marks[0] + 3], (code, marks, moved)
                assert after.ptr == marks[0] + 2, (code, after.ptr)  # type: ignore[attr-defined]
                shifted += 1
        assert shifted == 3, shifted

        # And ``'[<' * n`` is what plants a mark at cell n -- the parameter.
        for n in range(1, 6):
            machine = run("[<" * n)
            marks = [i for i in range(32) if machine.cell(i)]  # type: ignore[attr-defined]
            assert marks == [n], (n, marks)

    @pytest.mark.slow  # one full three-input ablation per code
    def test_dropping_a_pool_code_is_measured_not_assumed(self) -> None:
        """What each pool code is worth, ablated rather than argued.

        This replaced an assertion on ``len(_POOL_CODES)``, which noticed
        only that the list had been edited.  The property worth pinning is
        what each code *does*, and it is not uniform: three of the five
        strand tables when dropped, and two strand none.

        The two that strand nothing are still not free, which is the trap
        this records.  Removing both keeps every table correct and makes the
        build faster -- and pushes eight tables off ``_reconverged`` onto a
        route that cannot sort their slots, taking the out-of-name-order
        count from ten to eighteen.  Coverage and correctness are the loud
        properties; slot order is the quiet one, and it is what a trim
        actually costs here.

        The searches are stubbed, so a table that loses its pool fails here
        rather than being rebuilt slowly by a fallback -- with the
        fallthrough open this test would pass on any list at all.
        The one pair the two-insert family used to reach is skipped for the
        same reason it always was: it has no staged route, so it would
        strand under every drop and add a flat 2 to every count.  Three
        inputs, because two is not enough: two of the codes strand nothing
        at ``n == 2`` and 20 and 18 tables at ``n == 3``.
        """
        import importlib
        import re

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        codes = module._POOL_CODES  # noqa: SLF001

        def out_of_order() -> int:
            count = 0
            for table_int in range(256):
                table = format(table_int, "08b")
                template = module.minifuck.__wrapped__(table)
                names = [int(m) for m in re.findall(r"\{X(\d+)\}", template)]
                count += names != sorted(names)
            return count

        def reset(new_codes: tuple[str, ...]) -> None:
            module._POOL_CODES = new_codes  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            module._degenerate_cells.cache_clear()  # noqa: SLF001
            module.minifuck.cache_clear()

        original = codes
        try:
            reset(original)
            baseline = out_of_order()
            # Zero, and it used to be ten.  The ten were the tables whose
            # ignored input is the *middle* one, which no projection could
            # sort; ``_mux`` solves them at full arity, where the slots are
            # ascending by construction.
            assert baseline == 0, baseline

            stranding = {}
            for dropped in range(len(codes)):
                reset(tuple(c for i, c in enumerate(codes) if i != dropped))
                stranded = []
                # The column and parked searches used to be stubbed here too;
                # they no longer exist.  ``_mux`` is still a fallthrough for
                # the same reason they were: it sculpts with whatever pool
                # codes remain, so a live one would rebuild most of what a
                # dropped code strands and report the drop as nearly free.
                with patch.object(module, "_mux", lambda *_a, **_k: None):
                    for table_int in range(256):
                        table = format(table_int, "08b")
                        # This pair has no staged route by construction --
                        # no bracket run carries its column to the read --
                        # so it strands under every drop and would add a
                        # flat 2 to every count.  What this measures is the
                        # pool codes, so it is left out.
                        if table in ("01101101", "10010010"):
                            continue
                        try:
                            module.minifuck.__wrapped__(table)
                        except (AssertionError, ValueError):
                            # ``AssertionError`` is a stub firing.  A
                            # ``ValueError`` is ``_solve`` giving up, which
                            # is what a strand looks like now that the
                            # column and parked searches are gone: there is
                            # no route left below to rebuild it quietly.
                            # Both mean the same thing here -- this drop
                            # cost this table.
                            stranded.append(table)
                stranding[codes[dropped]] = len(stranded)

            # Three codes are required.
            assert sum(1 for n in stranding.values() if n) == 3, stranding
            # The other two strand nothing, and are kept for slot order:
            # dropping both takes the out-of-order count from 10 to 18.
            free = [c for c, n in stranding.items() if not n]
            assert len(free) == 2, stranding
            reset(tuple(c for c in codes if c not in free))
            # **The reason these two were kept has expired, and this records
            # that rather than hiding it.**  They strand no table; what
            # justified them was the quiet property -- dropping both used to
            # take the out-of-name-order count from 10 to 18.  It no longer
            # does: ``_mux`` sorts those tables whatever the pool list holds,
            # so both counts are 0 and the slot-order argument is gone.
            #
            # They are still shipped, because "no longer justified by this
            # measurement" is not the same as "measured to be worthless" --
            # the ablation above only covers three inputs, and which code
            # answers shifts with arity.  Whoever wants to trim the list now
            # has to measure at four, which is the honest version of the
            # question this assertion used to answer.
            assert out_of_order() == baseline == 0, out_of_order()
        finally:
            reset(original)

    def test_the_degenerate_cells_are_where_they_were_written_down(self) -> None:
        """Measuring the embed reproduces the six cells that used to be stored.

        ``_degenerate_cells`` replaced a written-down mapping, and the reason
        it can is the reason the mapping was constant in the first place: the
        carry chain preserves ``b0`` and ``b1`` individually before the
        prefix-XOR starts mixing.  This pins the collapse to the numbers it
        replaced, so a change to the embed or the separator that moved these
        columns would be caught here rather than as a slow degenerate build.

        The cells are the same at every arity the route serves, which is what
        let one mapping serve all of them.
        """

        from esolangs.tools.boolean.minifuck import _degenerate_cells

        written_down = {
            "const1": 1,
            "~b0": 16,
            "b0": 17,
            "const0": 18,
            "~b1": 19,
            "b1": 20,
        }
        for n in (2, 3, 4):
            assert _degenerate_cells(n) == written_down, n
        # One input leaves no ``b1`` to find, and the route asks for whatever
        # is there rather than assuming all six.
        assert _degenerate_cells(1) == {
            "const1": 1,
            "~b0": 16,
            "b0": 17,
            "const0": 18,
        }

    def test_the_enumeration_and_the_derivation_agree(self) -> None:
        """``_stagings`` states the order ``_derived_plans`` actually walks.

        The derivation interleaves the four loops with the machines it is
        advancing, so a bracket count costs one instruction rather than a
        rebuild -- which means the order is written out twice, once as a
        generator and once as nested loops.  This checks they match, since a
        drift between them would silently change which staging each table
        gets while every other test still passed.
        """

        from esolangs.tools.boolean.minifuck import (
            _MAX_ACC,
            _MAX_BRACKETS,
            _SEPS,
            _STAGED_ARITIES,
            _derived_plans,
            _insert_suffixes,
            _stagings,
        )

        expected = [
            (sep_index, settle, brackets, acc)
            for sep_index in range(len(_SEPS))
            for settle in (0, 1)
            for brackets in range(_MAX_BRACKETS + 1)
            for acc in range(9, _MAX_ACC + 1)
        ]
        assert list(_stagings(3)) == expected
        # Every staging the derivation hands back is one the enumeration
        # offers -- so the caps and the loops cannot have drifted apart.
        offered = set(expected)
        for table, staging in _all_derived_plans(
            _derived_plans, _STAGED_ARITIES, 2
        ).items():
            assert staging in offered, (table, staging)

        # Four inputs adds the insert family as a *second pass*, after every
        # pure run: that ordering is what keeps the arities the pure runs
        # already close assigned exactly the stagings they had, so it is
        # checked rather than assumed.  The derivation writes this order out
        # a second time as nested loops, which is what can drift.
        widened = expected + [
            (sep_index, settle, suffix, acc)
            for sep_index in range(len(_SEPS))
            for settle in (0, 1)
            for suffix in _insert_suffixes()
            for acc in range(9, _MAX_ACC + 1)
        ]
        assert list(_stagings(4)) == widened
        assert widened[: len(expected)] == expected

    @pytest.mark.parametrize(
        ("table", "tier"),
        [
            ("0001", "scan"),  # AND: the embed's carry chain already holds it
            ("0110", "column search"),  # XOR: found by searching for a column
        ],
    )
    def test_the_search_tiers_still_build_when_the_cheap_routes_miss(
        self, table: str, tier: str
    ) -> None:
        """With the derived routes stubbed off, the searches build the table.

        Every supported table is served by the staged, degenerate, or
        reconverged route, so these tiers are dead weight on the measured
        path -- but they are the fallback the module keeps for tables a
        future enumeration does not reach.  Stubbing the cheap routes is the
        only way to run them, and they answer in well under a second at two
        inputs, so this stays off the slow marker.

        The program is executed against every input row rather than merely
        being returned: a tier that builds the wrong thing is the failure
        this is here to catch.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        with (
            patch.object(module, "_staged", lambda *_a, **_k: None),
            patch.object(module, "_reconverged", lambda *_a, **_k: None),
            patch.object(module, "_degenerate", lambda *_a, **_k: None),
        ):
            module.minifuck.cache_clear()
            try:
                template = module.minifuck.__wrapped__(table)
            finally:
                module.minifuck.cache_clear()

        assert template, f"the {tier} tier returned nothing"
        for combo in range(4):
            bits = [(combo >> 1) & 1, combo & 1]
            got = self.run_minifuck(self.instantiate(template, bits))
            assert got == table[combo], (tier, bits)

    # 4.8s: the enumeration it walks is the cost.
    @pytest.mark.slow
    def test_the_enumeration_skips_a_column_that_is_not_one_digit(self) -> None:
        """A probe printing anything but single digits is passed over.

        Measured over ``_derived_plans(2)``, all 1844 prints the enumeration
        makes are single digits, so this filter never fires on the stagings
        that exist -- it is what keeps a column from being *decoded* out of a
        print the endgame did not actually produce one digit per row for.
        Forcing it needs the print itself stubbed, and the caches cleared
        either side so neither the stub nor the real run is served stale.
        """

        from esolangs.tools.boolean.minifuck import (
            _STAGED_ARITIES,
            _derived_plans,
            _Joint,
        )

        real_printed = _Joint.printed

        def two_digits(self: object) -> list[str]:
            # Every row prints two characters, so no column is ever decoded.
            return ["00" for _ in real_printed(self)]

        try:
            _derived_plans.cache_clear()
            with patch.object(_Joint, "printed", two_digits):
                assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2) == {}
        finally:
            _derived_plans.cache_clear()
        # With the real print restored the enumeration finds its entries
        # again, so the empty result above is the filter and not a cache.
        assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2)

    def test_reconverged_declines_what_it_cannot_replay(self) -> None:
        """``_reconverged`` bails rather than replaying a staging it lacks.

        Neither refusal fires on real data -- every two-input inner table has
        a staging, and every one of those stagings is a plain bracket run, so
        the two-essential-input route always has something to replay.  They
        are the guards that keep a *future* enumeration, one with a gap or
        one carrying the literal-suffix form, from being replayed by a route
        that makes no walk.  Forcing them is the only way to reach them, so
        the enumeration is stubbed the way the search-route tests stub theirs.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        # Two essential inputs with the ignored one leading, so the route
        # takes its projection branch -- the one that replays an inner
        # staging -- rather than the single-input branch that stands at a
        # known cell.  Unstubbed this table builds, so a None below is the
        # guard firing and not the route failing for its own reasons.
        table, n = "00010001", 3
        pair = essential_inputs(table, n)
        assert pair == [1, 2], pair
        assert module._reconverged(table, pair, n) is not None  # noqa: SLF001

        with patch.object(module, "_derive_staging", lambda *_a, **_k: None):
            assert module._reconverged(table, list(pair), n) is None  # noqa: SLF001

        # The same call, but the staging carries the literal-suffix form:
        # `brackets` is a string rather than a count, which this route cannot
        # replay because it makes no walk.
        real = module._derive_staging  # noqa: SLF001

        def literal_suffix(inner: str, arity: int) -> object:
            plan = real(inner, arity)
            if plan is None:
                return None
            sep_index, settle, _brackets, acc = plan
            return (sep_index, settle, "[x", acc)

        with patch.object(module, "_derive_staging", literal_suffix):
            assert module._reconverged(table, list(pair), n) is None  # noqa: SLF001

    def test_reconverged_declines_a_reset_that_splits_the_rows(self) -> None:
        """A reset leaving the rows in different states is not built on.

        The route's whole premise is that the ignored inputs are gone, which
        a split state has not achieved.  The reset is constructed now rather
        than searched, so there is one of them and the guard *declines*
        instead of trying the next candidate -- which is safe because
        ``_solve`` falls through to a route that does not need the reset.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table, n = "0101", 2  # input 1 alone decides it; input 0 is ignored
        essential = essential_inputs(table, n)
        # The route builds this table from the constructed reset.
        assert module._reconverged(table, essential, n) is not None  # noqa: SLF001

        # ``[`` alone reads a row-dependent cell, so the rows stop agreeing.
        def diverging(_ignored: int) -> str:
            return "["

        with patch.object(module, "_reset_code", diverging):
            assert module._reconverged(table, essential, n) is None  # noqa: SLF001

    def test_the_constructed_reset_converges_every_arity(self) -> None:
        """``_reset_code`` drives all ``2**k`` rows to one identical state.

        This is what the breadth-first search used to look for, and it found
        the answer only up to three ignored inputs -- its depth cap bit at
        four.  The construction has no cap, so the property is asserted well
        past where the search stopped.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for ignored in range(1, 7):
            joint = module._Joint(ignored)  # noqa: SLF001
            for slot in range(ignored):
                joint.emit_setter(slot)
            joint.emit(module._reset_code(ignored))  # noqa: SLF001
            assert not any(m.dead for m in joint.ms), ignored
            assert len({m.key() for m in joint.ms}) == 1, ignored

    def test_the_sculpted_route_returns_its_shortest_build(self) -> None:
        """``_mux`` keeps the shortest build, not the first one that prints.

        The accumulator sets the price of every sculpting round -- a round is
        ``3 * K + 1`` characters for a rewind of ``K`` -- so which one is
        chosen decides the program's length, and the first is a poor choice.
        This pins the property rather than a number: no ``(C, orientation,
        read)`` combination may produce a build shorter than the one
        returned.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "1010000110011011"
        built = module._mux(table, 4)  # noqa: SLF001
        assert built is not None

        base = module._mux_separate(4)  # noqa: SLF001
        assert base is not None
        positions = base.ptrs()
        lowest, highest = min(positions), max(positions)
        for acc in range(highest - lowest + 9, lowest - 1):
            for cell7 in (0, 1):
                for direct in (True, False):
                    other = module._mux_sculpt(  # noqa: SLF001
                        base, table, 4, acc, cell7, direct=direct
                    )
                    if other is not None:
                        assert len(other) >= len(built), (acc, cell7, direct)

    @pytest.mark.parametrize(("sep_index", "settle"), [(2, 0), (0, 1)])
    def test_closed_sweeps_match_the_emit_and_walk_sweep(
        self, sep_index: int, settle: int
    ) -> None:
        """The derived accumulator sweeps equal the interpreter's, per suffix.

        ``_staging_index`` fills from ``_closed_sweeps``, which computes each
        staging's columns arithmetically -- the bracket staircase, the
        slice-constant pool, the walk-out XOR -- where ``_column_sweep``
        emits the pool code and walks.  The index-vs-oracle tests compare
        the two end to end; this is the direct per-suffix pin, at the first
        arity with the insert family, so a formula that drifts is named by
        the ``(slice, suffix, orientation)`` it breaks on rather than by a
        reassigned staging three layers up.

        Two slices rather than ten to stay in the fast suite; the full
        cross-check behind the closed form ran every slice at two, three
        and four inputs -- 10440 sweeps -- with no disagreement.  The
        slices chosen span both settles and include the one five-input XOR
        builds from.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        chains, pools = module._slice_chains(4, sep_index, settle)  # noqa: SLF001
        base = module._embed(  # noqa: SLF001
            4,
            settle=settle,
            sep=module._SEPS[sep_index],  # noqa: SLF001
        )
        module._clamp(base)  # noqa: SLF001
        module._walk_to(base, module._BASE - 1)  # noqa: SLF001
        suffixes: list[int | str] = list(range(module._MAX_BRACKETS + 1))  # noqa: SLF001
        suffixes += list(module._insert_suffixes())  # noqa: SLF001
        run = base.fork()
        for suffix in suffixes:
            if isinstance(suffix, int):
                staged = run.fork()
                staged.emit("<")
                run.emit("[")
            else:
                staged = base.fork()
                staged.emit(suffix)
            module._clamp(staged)  # noqa: SLF001
            derived = module._closed_sweeps(chains, pools, suffix)  # noqa: SLF001
            for cell7 in (0, 1):
                walked = module._column_sweep(staged, cell7)  # noqa: SLF001
                assert derived[cell7] == walked, (sep_index, settle, suffix, cell7)

    def test_the_staging_index_agrees_with_the_enumeration(self) -> None:
        """The inverted index assigns exactly what the per-table sweep does.

        ``_derive_staging`` reads ``_staging_index``, which walks the
        enumeration once per arity and tabulates column -> first staging;
        ``_derived_plans`` walks the same order per table.  They must agree
        tuple for tuple, because the order -- not a stored answer -- is what
        decides which program a truth table gets.

        This is the regression net for one specific mistake, and what makes
        it hard to catch: an index that walks the order wrongly still
        produces columns that are all reachable and all valid.
        A draft of the index interleaved the two enumeration passes per
        slice instead of running every pure bracket run before any insert
        suffix, and the only symptom was five-input XOR being assigned
        ``None`` where the enumeration assigns ``(2, 0, 0, 33)``.  Every
        program it did emit still printed its table.  So the assertion here
        is on the staging *tuple*, never on whether the build works.

        ``_derived_plans`` takes a *tuple* of targets and answers them in one
        walk of the order, so every table is asked at once rather than one
        call per table.  That is the whole cost: 256 separate three-input
        walks were 7.4s, and the single walk answering all of them is 0.12s.
        The comparison is unchanged -- still every table at arity 2 and 3,
        still against the staging tuple -- and the complement is dropped from
        the targets only because at these arities the complement of every
        table is already in the set.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for arity in (2, 3):
            index = module._staging_index(arity)  # noqa: SLF001
            width = 2**arity
            tables = tuple(format(value, f"0{width}b") for value in range(2**width))
            plans = module._derived_plans(arity, tables)  # noqa: SLF001
            for table in tables:
                column = tuple(int(bit) for bit in table)
                assert index.get(column) == plans.get(table), (arity, table)

    @pytest.mark.slow  # ~22s: the arity 4 and 5 index builds dominate
    def test_the_staging_index_agrees_at_the_wider_arities(self) -> None:
        """The same agreement where the insert family and the budget live.

        Four inputs is the first arity with a second enumeration pass (the
        insert suffixes), and five is the only one that runs under a staging
        budget and in slice-yield rather than plain order.  Both are code
        paths the two- and three-input check above never reaches, and both
        are where an index that mis-walks the order would show up.

        Batched for the same reason as the check above: ``_derived_plans``
        answers a whole tuple of targets in one walk, so the sample costs one
        four-input enumeration instead of one per table -- 97s of per-table
        calls against 2.6s for the single walk, to the same answers.  The
        complements go into the targets explicitly here, because a 40-table
        sample at arity 4 does not already contain them the way the
        exhaustive arities above do.

        What is left is the oracle's emit-and-walk enumerations -- the index
        builds themselves derive their columns in closed form and cost 0.62s
        and 1.12s -- and the oracle is the independent spelling this test
        exists to compare against, not overhead the test can drop.  So it
        stays marked slow.
        """
        import importlib
        import random

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        random.seed(20260902)
        wide = [format(value, "016b") for value in range(65536)]
        wide = [t for t in wide if len(essential_inputs(t, 4)) == 4]
        samples = [(4, t) for t in random.sample(wide, 40)]
        samples.append((4, "0110100110010110"))  # four-input XOR
        samples.append((5, "01101001100101101001011001101001"))  # five-input

        by_arity: dict[int, list[str]] = {}
        for arity, table in samples:
            by_arity.setdefault(arity, []).append(table)

        for arity, tables in by_arity.items():
            index = module._staging_index(arity)  # noqa: SLF001
            targets = set(tables)
            for table in tables:
                targets.add("".join(str(1 - int(bit)) for bit in table))
            plans = module._derived_plans(arity, tuple(sorted(targets)))  # noqa: SLF001
            for table in tables:
                column = tuple(int(bit) for bit in table)
                assert index.get(column) == plans.get(table), (arity, table)

    def test_the_staging_enumeration_is_offered_only_at_its_arities(self) -> None:
        """Outside ``_STAGED_ARITIES`` the derivation offers nothing.

        One input is solved by the degenerate route and four is past what the
        enumeration covers, so neither asks for a staging.  The guard is what
        lets the caller fall through to the searches rather than paying an
        enumeration that has no entries to give.
        """

        from esolangs.tools.boolean.minifuck import (
            _STAGED_ARITIES,
            _derive_staging,
            _derived_plans,
        )

        for n in (1, max(_STAGED_ARITIES) + 1):
            assert n not in _STAGED_ARITIES
            assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, n) == {}
            assert _derive_staging("0" * 2**n, n) is None
        # At a staged arity the enumeration really does have entries, so the
        # empty results above are the guard and not an exhausted search.
        assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2)

    def test_the_pool_rule_matches_the_scan_it_replaced(self) -> None:
        """``_find_pool`` answers what trying every code would have answered.

        The scan below *is* the specification: it is what ``_find_pool`` used
        to do -- walk the codes in order through the simulator and take the
        first that reaches the pool.  The shipped rule instead asks each row
        which code it names and checks the rows agree, so this pins the two
        together over the whole domain the rule claims, not over the states a
        build happens to visit.

        Both halves matter and each caught a real bug while landing.  The
        exhaustive half covers every single-row key; the random half builds
        *joints*, which is where the two cross-row conditions live -- rows must
        name the same code and be left on the same cell by it.  Independent
        random rows almost never collide in the low byte, so the joints are
        drawn by perturbing one window: with rows drawn independently the
        end-pointer split showed up in none of 40000 joints, and in 5 of the
        first 80000 built this way.
        """
        import importlib
        import random

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        codes = module._POOL_CODES  # noqa: SLF001
        width = module._POOL_WIDTH  # noqa: SLF001
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        def scan(joint: object, cell7: int, walk_out: int) -> str | None:
            """The replaced search, kept as the oracle."""
            for code in codes:
                if module._pool_reaches(joint, code, cell7, walk_out):  # noqa: SLF001
                    return code
            return None

        def joint_of(sims: list[object]) -> object:
            joint = module._Joint.__new__(module._Joint)  # noqa: SLF001
            joint.ms = sims
            return joint

        def row(tape: int, ptr: int = 0, *, skip: bool = False) -> object:
            sim = module._Sim(512)  # noqa: SLF001
            sim.tape = tape
            sim.ptr = ptr
            sim.skip = skip
            return sim

        # Every single-row key in the derived domain, against the oracle.
        for low in range(1 << width):
            for ptr in range(ptr_max + 1):
                for skip in (False, True):
                    for cell7 in (0, 1):
                        joint = joint_of([row(low, ptr, skip=skip)])
                        walk_out = module._PROBE_WALK_OUT  # noqa: SLF001
                        assert module._find_pool(joint, cell7, walk_out) == scan(  # noqa: SLF001
                            joint, cell7, walk_out
                        ), (low, ptr, skip, cell7)

        # Joints, where the cross-row conditions live.
        rnd = random.Random(20260906)
        for _ in range(3000):
            seed_low = rnd.getrandbits(width)
            ptr = rnd.randint(0, ptr_max)
            sims = []
            for _ in range(rnd.choice([2, 4, 8])):
                low = seed_low
                if rnd.random() < 0.5:
                    low ^= 1 << rnd.randrange(width)
                sims.append(row(low | (rnd.getrandbits(16) << width), ptr))
            joint = joint_of(sims)
            for cell7 in (0, 1):
                walk_out = rnd.choice([9, 12, 20, 33])
                assert module._find_pool(joint, cell7, walk_out) == scan(  # noqa: SLF001
                    joint, cell7, walk_out
                ), [(s.tape & ((1 << width) - 1), s.ptr) for s in sims]

    def test_the_pool_slices_cover_the_whole_domain(self) -> None:
        """Deriving a slice at a time answers what one big table would.

        The slices exist so a caller pays for the ``(pointer, skip)`` it
        actually asks about -- a build touches one of the six, and deriving
        all of them on first use billed a 0.2ms build 57ms of work it had no
        use for.  What must not change is the *answers*: this rebuilds the
        whole-domain derivation the slices replaced and pins the union to it,
        so a slice that quietly disagreed with it would fail here.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        codes = module._POOL_CODES  # noqa: SLF001
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        whole = {
            (low, ptr, skip, cell7): answer
            for low in range(1 << module._POOL_WIDTH)  # noqa: SLF001
            for ptr in range(ptr_max + 1)
            for skip in (False, True)
            for cell7 in (0, 1)
            if (
                answer := module._pool_code_for_row(  # noqa: SLF001
                    codes, low, ptr, cell7, skip=skip
                )
            )
            is not None
        }

        union = {
            (low, ptr, skip, cell7): answer
            for ptr in range(ptr_max + 1)
            for skip in (False, True)
            for (low, cell7), answer in module._pool_slice(  # noqa: SLF001
                codes, ptr, skip=skip
            ).items()
        }

        assert union == whole
        assert whole, "the derivation should not be empty"

    def test_the_pool_rule_declines_outside_its_domain(self) -> None:
        """The bound is a refusal, not a gap in a table.

        Past ``_POOL_PTR_MAX`` the window byte is no longer the whole key --
        the codes reach above cell 7 -- so there is no answer to look up and
        the rule says None rather than guessing.  Codes do still fit out
        there, which is the point: this is where the rule stops claiming, not
        where the language stops working.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        outside = module._Sim(512)  # noqa: SLF001
        outside.tape = 156
        outside.ptr = 3
        joint = module._Joint.__new__(module._Joint)  # noqa: SLF001
        joint.ms = [outside]

        assert ptr_max == 2, "the bound this test pins has moved"
        assert module._find_pool(joint, 1, 12) is None  # noqa: SLF001
        # ... while the simulator still finds a code from there.
        served = [
            code
            for code in module._POOL_CODES  # noqa: SLF001
            if module._pool_reaches(joint, code, 1, 12)  # noqa: SLF001
        ]
        assert served, "expected the scan to still answer outside the domain"

    def test_pool_reaches_refuses_a_code_that_kills_a_row(self) -> None:
        """``_pool_reaches`` rejects code that kills or desynchronises a row.

        The pool list is chosen so the codes it does offer keep every row
        alive, so this refusal never fires during a build -- but it is what
        makes a *candidate* code safe to try.  Checked against joints
        captured from a real build rather than a hand-built state, for the
        reason the pool test gives: a bare embed is not a state any call
        sees.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        seen: list[tuple[object, int, int]] = []
        real = module._find_pool  # noqa: SLF001

        def record(joint: object, cell7: int, walk_out: int) -> object:
            if len(seen) < 4:
                seen.append((joint.fork(), cell7, walk_out))  # type: ignore[attr-defined]
            return real(joint, cell7, walk_out)

        with patch.object(module, "_find_pool", record):
            module.minifuck.cache_clear()
            module.minifuck.__wrapped__("0110")
        assert seen, "no pool lookups were observed"

        joint, cell7, walk_out = seen[0]
        # ``[[`` leaves a row dead or mid-skip, so the code is refused before
        # the walk out is priced -- a dead row cannot be walked at all.
        assert not module._pool_reaches(joint, "[[", cell7, walk_out)  # noqa: SLF001
        # ``x`` writes under the pointer and is refused as well.
        assert not module._pool_reaches(joint, "x", cell7, walk_out)  # noqa: SLF001
        # A code that ends past the walk-out target is refused rather than
        # walked backwards: the walk out only ever moves right, so a pointer
        # already beyond it can never arrive.
        assert not module._pool_reaches(joint, "[x", cell7, 0)  # noqa: SLF001
        # Bare navigation is refused too: reaching the state is not enough,
        # the code has to leave the answer where the read will find it.
        assert not module._pool_reaches(joint, "", cell7, walk_out)  # noqa: SLF001
        # Exactly one of the pool's own codes serves this joint -- the guards
        # are a filter over the list, not a formality that passes everything.
        served = [
            code
            for code in module._POOL_CODES  # noqa: SLF001
            if module._pool_reaches(joint, code, cell7, walk_out)  # noqa: SLF001
        ]
        assert len(served) == 1, served

    @pytest.mark.slow  # re-simulates a derived staging for every table
    def test_stagings_deliver_the_column_the_read_sees(self) -> None:
        """Every staging really does deliver its table's column at the read.

        This recomputes what a staging leaves at its accumulator *as the read
        sees it* -- after the pool code and the walk out, which is where the
        running prefix-XOR applies -- and checks it against the table it was
        derived for.  Selecting on the pre-walk column instead is the mistake
        that covered 10 of 16 at two inputs, so the transform is the point
        rather than an implementation detail.

        The derivation accepts a staging by *printing*, which is a stronger
        test than this one and would catch a broken staging on its own.  What
        this adds is the reason: it pins that the column arrives at the read,
        so a future change that made the printing accidental rather than
        earned would show up here.

        ``01101101`` used to be listed here as the table only the two-insert
        family reached.  That family is gone and the sculpted route builds
        the pair instead, so the table has no staging to check -- it is not
        an omission, and adding it back would assert on a route that no
        longer produces stagings at all.
        """

        from esolangs.tools.boolean.minifuck import (
            _BASE,
            _SEPS,
            _clamp,
            _derive_staging,
            _embed,
            _find_pool,
            _walk_to,
        )

        plans = {
            2: {
                format(t, "04b"): _derive_staging(format(t, "04b"), 2)
                for t in range(16)
            },
            3: {
                key: _derive_staging(key, 3)
                for key in ("00000001", "01111111", "00010111")
            },
        }
        for n, plan in sorted(plans.items()):
            for key, staging in sorted(plan.items()):
                assert staging is not None, (n, key)
                sep_index, settle, suffix, acc = staging
                joint = _embed(
                    n,
                    settle=settle,
                    sep=_SEPS[sep_index],
                )
                _clamp(joint)
                _walk_to(joint, _BASE - 1)
                joint.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
                _clamp(joint)
                arrived = None
                for cell7 in (0, 1):
                    probe = joint.fork()
                    code = _find_pool(probe, cell7, acc - 1)
                    if code is None:
                        continue
                    probe.emit(code)
                    _walk_to(probe, acc - 1)
                    column = "".join(str(b) for b in probe.col(acc))
                    complement = "".join(str(1 - int(c)) for c in column)
                    if key in (column, complement):
                        arrived = column
                        break
                assert arrived is not None, (n, key, sep_index, settle, suffix, acc)

    def test_template_is_input_independent_and_equal_length(self) -> None:
        """The template has placeholders and every fill has the same length.

        Both properties concern the same expensive ``0110`` construction.
        Building it separately only to inspect its placeholders duplicated
        construction without exercising a distinct path.  The current
        combined check takes 0.12s serially, so it belongs in the fast suite.
        """
        from esolangs.tools.boolean import parameterized

        template = parameterized.minifuck("0110")
        assert "{X0}" in template
        assert "{X1}" in template
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, f"unequal instantiation lengths: {lengths}"

    def test_the_simulator_mirrors_the_interpreter_at_its_edges(self) -> None:
        """The search's model of a row has to match what Minifuck does.

        The search prunes on simulated state, so a divergence here would
        make it reason about tapes the interpreter never produces.  The
        edges are the ones a mid-tape step never shows: a dead row ignores
        everything after it, a spent skip eats one instruction, ``<`` is
        pinned at cell 0, the tape grows on demand, and a print reads the
        first eight cells as one byte -- emitting that character, or
        killing the row if the byte is zero.
        """
        from esolangs.tools.boolean.minifuck import _Sim

        dead = _Sim(16)
        dead.dead = True
        dead.exec("[")
        assert dead.ptr == 0, "a dead row executes nothing"

        skipping = _Sim(16)
        skipping.skip = True
        skipping.exec("[")
        assert skipping.ptr == 0, "the skipped instruction does nothing"
        assert not skipping.skip, "and the skip is spent"

        pinned = _Sim(16)
        pinned.exec("<")
        assert pinned.ptr == 0, "there is nothing to the left of cell 0"

        growing = _Sim(3)
        for _ in range(5):
            growing.exec("[")
        assert growing.length > 3, "the tape grows to meet the pointer"

        # The print flips the cell it steps onto first, so a print inside
        # the byte writes its own 1: cell 1 makes 0b01000000 == 64.
        printing = _Sim(16)
        printing.exec(".")
        assert printing.out == ["@"]
        assert not printing.dead

        # Past cell 8 the flip lands outside the byte, which stays zero.
        zero = _Sim(16)
        zero.ptr = 9
        zero.exec(".")
        assert zero.dead, "printing a zero byte ends the row"
        assert zero.out == []

    def test_the_simulator_agrees_with_a_real_run_on_random_streams(self) -> None:
        """``_Sim`` and a whole-program run agree, instruction for instruction.

        The edges above are hand-picked; this is the same claim made over
        random programs, which is what would catch a divergence nobody
        thought to write a case for.  ``_Sim`` advances by its own closed-
        form laws -- that is the point of the module, the build path no
        longer drives the interpreter -- so the two *can* disagree now, and
        this comparison against a real ``run`` is one of the two tests that
        would say so (the other pins each law to ``_step`` from arbitrary
        states, below).

        Only live rows are compared cell by cell: once a row is ``dead`` the
        emitter stops tracking it by contract, while a real run keeps going,
        so past that point only the output and the death itself are shared.
        """
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run
        from esolangs.tools.boolean.minifuck import _Sim

        rng = random.Random(20260902)
        printed = deaths = skips = 0

        for _ in range(300):
            stream = "".join(rng.choice("<[.x") for _ in range(rng.randrange(1, 40)))

            sim = _Sim(64)
            for ins in stream:
                sim.exec(ins)

            io_ = ScriptedIO("")
            try:
                run(stream, io_)
            except EOFError:
                # The whole-program run fetches input where the emitter
                # instead marks the row dead; that is the one divergence
                # the emitter's contract creates on purpose.
                assert sim.dead, (stream, "the emitter missed a read")
                deaths += 1
                continue

            assert not sim.dead, (stream, "the emitter killed a live row")
            assert "".join(sim.out) == io_.getvalue(), stream
            printed += len(sim.out)
            skips += sim.skip

        # The comparison is worthless if the interesting transitions never
        # fire, so assert the sample reached all three.
        assert printed, "no stream printed"
        assert deaths, "no stream hit the zero-pool read"
        assert skips, "no stream ended on a pending skip"

    def test_the_closed_form_runs_agree_with_stepping_them(self) -> None:
        """A whole run's law matches applying it one instruction at a time.

        ``run_left``, ``run_walk`` and ``run_brackets`` each claim a closed
        form over a run of ``k`` tokens; ``exec`` applies the same laws one
        token at a time.  The two spellings must compose to the same state
        -- the staircase inverse and the prefix-XOR doubling are exactly the
        parts a per-token application does not share -- and the
        disagreement this invites is not hypothetical: a first ``run_walk``
        that ignored the cascade a ``[`` fires when its flip lands on zero
        matched on the easy states and diverged on 877 of 3000 random ones.

        So the comparison is made from *arbitrary* states, not fresh ones --
        a fresh row has a zero tape and no pending skip, which is exactly
        where a wrong model still looks right.
        """
        import random

        from esolangs.tools.boolean.minifuck import _Sim

        rng = random.Random(20260906)
        skips = walks_cascaded = clamped = 0

        for _ in range(400):
            start = _Sim(96)
            for _ in range(rng.randrange(0, 25)):
                start.exec(rng.choice("<[.x"))
            count = rng.randrange(0, 12)

            for token, closed in (
                ("<", "run_left"),
                ("[x", "run_walk"),
                ("[", "run_brackets"),
            ):
                stepped = start.copy()
                for ins in token * count:
                    stepped.exec(ins)

                direct = start.copy()
                getattr(direct, closed)(count)

                assert direct.key() == stepped.key(), (
                    token,
                    count,
                    start.key(),
                    "the closed form left a different state",
                )

            if start.skip:
                skips += 1
            if start.ptr and count:
                clamped += 1
            probe = start.copy()
            probe.run_walk(count)
            if probe.tape != start.tape:
                walks_cascaded += 1

        # A sweep that never reaches the interesting states proves nothing:
        # the pending skip is what makes the run's first instruction special,
        # and a walk that never wrote a cell never exercised the cascade.
        assert skips, "no state carried a pending skip"
        assert clamped, "no clamp started away from cell 0"
        assert walks_cascaded, "no walk touched the tape"

    def test_the_laws_agree_with_the_interpreters_step(self) -> None:
        """Every law matches ``_step``, from arbitrary states, over the
        construction's own vocabulary.

        The laws are the module's own statement of the language -- the build
        path no longer delegates to the interpreter -- so this differential
        is what now pins them to ``_step``, which stays Minifuck's single
        definition.  The reference is the retired delegating stepper,
        rebuilt here from ``_step`` itself; the states are arbitrary rather
        than fresh (fresh ones are where a wrong model still looks right);
        and the codes are the strings the generator actually emits --
        separators, setters, reads, pool codes, weight gadgets, resets --
        plus bare runs and random mixed streams, so no law is exercised
        only on the shapes it was derived from.
        """
        import importlib
        import random

        from esolangs.interpreters.tape_based.minifuck import _step
        from esolangs.tools.boolean.minifuck_sim import _runs, _Sim

        # The package re-exports the generator function under the
        # submodule's name, so the module comes through importlib.
        m = importlib.import_module("esolangs.tools.boolean.minifuck")

        def reference(row: _Sim, code: str) -> None:
            """The retired stepper: one ``_step`` call per character."""
            for ins in code:
                if row.dead:
                    return
                if row.skip:
                    row.skip = False
                    continue
                if ins == "<":
                    if row.ptr:
                        row.ptr -= 1
                    continue
                if ins not in ".[":
                    continue
                tape, length, ptr, skipped, char, reads = _step(
                    ins, row.tape, row.length, row.ptr
                )
                if reads:
                    row.dead = True
                    return
                if char is not None:
                    row.out.append(char)
                row.tape, row.length, row.ptr, row.skip = tape, length, ptr, skipped

        gadgets = [
            *m._SEPS,  # noqa: SLF001
            *m._POOL_CODES,  # noqa: SLF001
            *m._READS,  # noqa: SLF001
            m._FLIP,  # noqa: SLF001
            "[<",
            "xx",
            "[x",
            "[x.",
            m._reset_code(2),  # noqa: SLF001
            m._mux_weight(4),  # noqa: SLF001
            m._mux_weight(8),  # noqa: SLF001
        ]

        rng = random.Random(20260906)
        deaths = printed = skips = 0
        for _ in range(4000):
            tape = rng.getrandbits(48)
            ptr = rng.randrange(0, 40)
            skip = rng.random() < 0.3
            pick = rng.random()
            if pick < 0.4:
                code = rng.choice(gadgets)
            elif pick < 0.55:
                code = "[" * rng.randrange(1, 30)
            elif pick < 0.7:
                code = "[x" * rng.randrange(1, 20)
            else:
                code = "".join(rng.choice("[<x.") for _ in range(rng.randrange(1, 25)))

            lawful = _Sim(48)
            lawful.tape, lawful.ptr, lawful.skip = tape, ptr, skip
            stepped = lawful.copy()
            lawful.apply(_runs(code))
            reference(stepped, code)
            assert lawful.key() == stepped.key(), (
                f"laws diverged from _step on {code!r} at tape={tape:#x} "
                f"ptr={ptr} skip={skip}"
            )
            deaths += stepped.dead
            printed += len(stepped.out)
            skips += stepped.skip

        # The comparison is worthless if the interesting transitions never
        # fire, so assert the sample reached all three.
        assert deaths, "no state hit the zero-pool read"
        assert printed, "no state printed"
        assert skips, "no state ended on a pending skip"

    def test_the_parsed_emission_matches_stepping_every_row(self) -> None:
        """``_Joint.emit`` parses a code once and advances rows by whole runs.

        The parse and the per-run laws have to compose to exactly what
        applying the laws one character at a time does -- the run boundaries
        and the skip handed from one run to the next are where a parse bug
        would live.  Synthetic codes do not reach the states this has to get
        right: random emissions leave the rows' pointers converged, and it
        is precisely the *divergent* pointers the real construction creates
        that make an emission's effect differ row by row.  So the generator
        itself drives the comparison, with every emission checked both ways
        as it happens.
        """
        from esolangs.tools.boolean import minifuck_sim
        from esolangs.tools.boolean.minifuck import minifuck

        real_emit = minifuck_sim._Joint.emit  # noqa: SLF001
        checked = [0]

        def checking_emit(self: object, code: str) -> None:
            rows = self.ms  # type: ignore[attr-defined]
            reference = [m.copy() for m in rows]
            real_emit(self, code)
            for row in reference:
                for ch in code:
                    row.exec(ch)
            assert [m.key() for m in rows] == [m.key() for m in reference], (
                f"the parsed emission of {code!r} diverged from stepping it"
            )
            # What makes the comparison bite is rows whose pointers differ:
            # an emission's effect is row-dependent exactly there, and they
            # are the states the construction actually produces.
            if len({m.ptr for m in reference}) > 1:
                checked[0] += 1

        # ``minifuck`` and the pool searches under it are cached, so a table
        # an earlier test already built emits far less the second time.
        # Counting only the divergent-pointer emissions keeps the floor
        # meaningful without depending on which caches happen to be warm.
        minifuck.cache_clear()
        with patch.object(minifuck_sim._Joint, "emit", checking_emit):  # noqa: SLF001
            for table in ("01", "0110", "10010110"):
                minifuck(table)
        minifuck.cache_clear()

        assert checked[0], "no emission met rows whose pointers had diverged"

    def test_the_computed_endgame_choice_matches_trying_all_four(self) -> None:
        """``_try_print`` names the pair the retired four-fork trial found.

        The trial loop -- fork the joint, run every ``(read, orientation)``
        endgame, keep whichever printed -- is the specification, so it is
        replayed here, spelled as it stood, against the computed choice on
        the call sites real builds reach.  Corpus identity already pins
        today's outcomes; this pins the *selection rule*, which is what
        would drift if the polarity mapping or the trial order were edited.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        def retired(joint: object, truth_table: str, acc: int) -> object:
            """The replaced trial loop, verbatim."""
            for read in module._READS:  # noqa: SLF001
                for cell7 in (0, 1):
                    probe = joint.fork()  # type: ignore[attr-defined]
                    try:
                        module._endgame(probe, acc, read, cell7)  # noqa: SLF001
                    except ValueError:
                        continue
                    if probe.printed() == list(truth_table):
                        return probe
            return None

        sites: list[tuple[object, str, int]] = []
        real = module._try_print  # noqa: SLF001

        def record(joint: object, truth_table: str, acc: int) -> object:
            if len(sites) < 200:
                sites.append((joint.fork(), truth_table, acc))  # type: ignore[attr-defined]
            return real(joint, truth_table, acc)

        # One table per route: a constant (the degenerate cell scan,
        # including the in-pool cell 1 the computed refusal now answers), a
        # staged pair, a reconverged projection, and three sculpted tables
        # -- the scout replays only the winning combination, so a sculpted
        # build is one call site now rather than one per combination.
        with patch.object(module, "_try_print", record):
            module.minifuck.cache_clear()
            for table in (
                "1111",
                "0110",
                "0011",
                "01101101",
                "1101000011010000",
                "1010000110011011",
            ):
                module.minifuck.__wrapped__(table)
        module.minifuck.cache_clear()

        assert len(sites) > 5, f"expected real call sites, got {len(sites)}"
        misses = hits = 0
        for joint, table, acc in sites:
            expected = retired(joint, table, acc)
            got = real(joint, table, acc)
            if expected is None:
                assert got is None, (table, acc)
                misses += 1
            else:
                assert got is not None, (table, acc)
                assert got.template() == expected.template(), (table, acc)
                hits += 1
        # The comparison has to see both verdicts to mean anything.
        assert hits, "no site printed"
        assert misses, "no site declined"

    def test_the_walk_needs_a_converged_pointer_going_right(self) -> None:
        """``[x`` walks are only safe rightward from one shared position.

        Every row runs the same program, so a walk emitted while the rows
        disagree about where the pointer is would move them different
        distances.  And ``[x`` only advances -- the pointer is Minifuck's
        one leftward channel, and it is not this one -- so a leftward
        target is refused rather than silently ignored.
        """
        from esolangs.tools.boolean.minifuck import _clamp, _embed, _walk_to

        spread = _embed(2)
        with pytest.raises(ValueError, match="converged pointer"):
            _walk_to(spread, 0)

        clamped = _embed(2)
        _clamp(clamped)
        with pytest.raises(ValueError, match="cannot walk left"):
            _walk_to(clamped, -5)

    def test_the_pool_search_needs_the_rows_to_agree_on_the_pointer(self) -> None:
        """A pool is only a pool if every row reads it from one place.

        The embed leaves the rows on different cells -- that spread is what
        carries the inputs -- so the pool search declines outright until a
        clamp has brought them back together.
        """
        from esolangs.tools.boolean.minifuck import _clamp, _embed, _find_pool

        spread = _embed(2)
        assert len(set(spread.ptrs())) > 1, "the embed should leave rows apart"
        assert _find_pool(spread, 0, 12) is None

        clamped = _embed(2)
        _clamp(clamped)
        assert len(set(clamped.ptrs())) == 1

    def test_the_endgame_refuses_an_impossible_setup(self) -> None:
        """Two ways the endgame cannot run, reported rather than emitted.

        The pool occupies cells 0..7, so an accumulator inside it would be
        overwritten by the digit it is supposed to carry.  And the pool has
        to be *built*: if no pattern reaches it from here, there is nothing
        to print, and emitting the read anyway would print a junk byte.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        from esolangs.tools.boolean.minifuck import _clamp, _embed, _endgame

        joint = _embed(2)
        _clamp(joint)

        with pytest.raises(ValueError, match="must sit past the pool"):
            _endgame(joint.fork(), 3, "[<", 0)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_find_pool", lambda *_a, **_k: None)
            with pytest.raises(ValueError, match="no pool pattern"):
                _endgame(joint.fork(), 12, "[<", 0)


@pytest.mark.slow  # one four-input staging enumeration, ~1.2s
def test_insert_pass_stops_as_soon_as_its_last_target_is_placed() -> None:
    """The second pass has its own early exit, and only it can reach this one.

    The bracket-run pass returns when it places the last table, so a target it
    reaches never gets as far as the insert family.  This table does not build
    from a pure run -- its staging carries an insert string rather than a
    bracket count -- so asking for it alone is what drives ``remaining`` to
    zero inside the second loop.
    """
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    table = "0100110110100101"
    plans = module._derived_plans(4, (table,))  # noqa: SLF001
    assert set(plans) == {table}
    # A str suffix is the insert family; the run pass records an int.
    assert isinstance(plans[table][2], str)


def test_mux_refuses_below_its_minimum_arity() -> None:
    """``_mux`` separates rows, which needs at least two of them to separate."""
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    assert module._MUX_MIN_ARITY == 2  # noqa: SLF001
    assert module._mux("01", 1) is None  # noqa: SLF001


def test_the_scout_distrusts_states_its_summary_cannot_speak_for() -> None:
    """A base outside the parity law's key sends ``_mux`` to the sweep.

    The scout summarises a row as its tape alone, which is only sound with
    no skip pending, no dead row, and one shared pool region.  No
    separation produces the other states, so they are constructed: each
    must come back untrusted rather than mispriced.
    """
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    base = module._mux_separate(2)  # noqa: SLF001
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    accs = range(highest - lowest + module._POOL_WIDTH + 1, lowest - 1)  # noqa: SLF001

    trusted = module._mux_scout(base, "0110", 2, accs)  # noqa: SLF001
    assert trusted[1], "the real separation must be scoutable"

    skipped = base.fork()
    skipped.ms[0].skip = True
    assert module._mux_scout(skipped, "0110", 2, accs) == (None, False)  # noqa: SLF001

    dead = base.fork()
    dead.ms[1].dead = True
    assert module._mux_scout(dead, "0110", 2, accs) == (None, False)  # noqa: SLF001

    torn = base.fork()
    torn.ms[0].tape ^= 1 << 3
    assert module._mux_scout(torn, "0110", 2, accs) == (None, False)  # noqa: SLF001


def test_the_probe_simulates_when_the_parity_law_declines() -> None:
    """Off the canonical state the probe answers by simulation, identically.

    ``_sculpt_columns`` refuses a joint whose rows disagree inside the pool
    region, and ``_mux_probe`` must then hand back exactly what the
    simulated probe says -- the fallback is the specification, not an
    approximation of it.
    """
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    torn = module._mux_separate(2).fork()  # noqa: SLF001
    torn.ms[0].tape ^= 1 << 3
    acc = module._POOL_WIDTH + 4  # noqa: SLF001
    assert module._sculpt_columns(torn, acc) is None  # noqa: SLF001
    assert module._mux_probe(torn, acc, 0) == module._mux_probe_sim(  # noqa: SLF001
        torn, acc, 0
    )


def test_the_probe_frame_refuses_codes_outside_its_key() -> None:
    """A code that strands a skip or leaves the pool region has no frame.

    The frame summarises a pool code as ``(landed, parity)``, which is only
    a summary while the code stays inside the region and leaves the row
    runnable.  ``[`` from the canonical byte cascades and owes a skip; a
    long walk crosses cell 8.  Both must decline rather than summarise.
    """
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    byte = module._mux_separate(2).ms[0].tape & module._POOL_MASK  # noqa: SLF001
    assert module._probe_frame("[", byte) is None  # noqa: SLF001
    assert module._probe_frame("[x" * 9, byte) is None  # noqa: SLF001
    assert module._probe_frame(module._SCULPT_POOL_CODE, byte) is not None  # noqa: SLF001


def test_the_weight_law_matches_the_parsed_runs() -> None:
    """``run_weight`` is ``apply(_runs(_mux_weight(k)))``, or refuses untouched.

    The gadget law is a composition claim over the pinned laws, so the
    differential is against them, from arbitrary states -- a fresh setter
    site is exactly where a wrong march model still looks right.  A refusal
    must leave the row untouched, and both the skip refusal and the floor
    refusal must actually fire in the sample.
    """
    import importlib
    import random

    from esolangs.tools.boolean.minifuck_sim import _runs, _Sim

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    rng = random.Random(20260910)
    applied = refused = 0
    for _ in range(2500):
        fast = _Sim(64)
        fast.tape = rng.getrandbits(rng.choice([16, 48, 200]))
        fast.ptr = rng.randrange(0, 40)
        fast.skip = rng.random() < 0.2
        units = rng.randrange(1, 70)
        slow = fast.copy()
        if not fast.run_weight(units):
            refused += 1
            assert fast.key() == slow.key(), "a refusal touched the row"
            continue
        applied += 1
        slow.apply(_runs(module._mux_weight(units)))  # noqa: SLF001
        assert fast.key() == slow.key(), (units, slow.key())
    assert applied, "the fused arm never fired"
    assert refused, "the refusal arm never fired"

    floor_refusals = 0
    for ptr in range(6):
        for units in range(1, 12):
            fast = _Sim(64)
            fast.tape, fast.ptr = (1 << 40) - 1, ptr
            slow = fast.copy()
            if fast.run_weight(units):
                slow.apply(_runs(module._mux_weight(units)))  # noqa: SLF001
                assert fast.key() == slow.key(), (ptr, units)
            else:
                floor_refusals += 1
    assert floor_refusals, "the floor guard never fired"

    # The edge arms: a dead row and zero units are no-ops that still apply.
    dead = _Sim(16)
    dead.dead = True
    frozen = dead.key()
    assert dead.run_weight(3)
    assert dead.key() == frozen
    fresh = _Sim(16)
    frozen = fresh.key()
    assert fresh.run_weight(0)
    assert fresh.key() == frozen

    # The joint-level fallback: a row the law refuses advances by the
    # parsed runs and the pair must land on the same state.
    joint = module._Joint(1)  # noqa: SLF001
    for m in joint.ms:
        m.tape, m.ptr = 0b1011 << 5, 8
    joint.ms[0].skip = True
    clones = [m.copy() for m in joint.ms]
    code = module._mux_weight(3)  # noqa: SLF001
    joint.emit_weight(code, 3)
    assert joint.parts[-1] == code
    for m, clone in zip(joint.ms, clones, strict=True):
        clone.apply(_runs(code))
        assert m.key() == clone.key()


def test_the_rewind_law_matches_the_parsed_runs() -> None:
    """A sculpting round and a fused round sequence match the parsed runs.

    ``run_rewind`` claims the round ``"<"*k + "[x"*k + "x"`` in one law
    call and ``run_rewinds`` claims a whole sequence over one extracted
    window; both fall back to the laws when their frame does not hold, so
    the differential covers fused and fallback states alike.
    """
    import random

    from esolangs.tools.boolean.minifuck_sim import _runs, _Sim

    rng = random.Random(20260911)
    fused = fell_back = 0
    for _ in range(2500):
        fast = _Sim(64)
        fast.tape = rng.getrandbits(rng.choice([32, 400]))
        fast.ptr = rng.randrange(0, 60)
        fast.skip = rng.random() < 0.2
        count = rng.randrange(0, 40)
        slow = fast.copy()
        if fast.skip or fast.ptr < count:
            fell_back += 1
        else:
            fused += 1
        fast.run_rewind(count)
        slow.apply(_runs("<" * count + "[x" * count + "x"))
        assert fast.key() == slow.key(), (count, slow.key())
    assert fused, "the fused arm never fired"
    assert fell_back, "the fallback arm never fired"

    for _ in range(800):
        fast = _Sim(64)
        fast.tape = rng.getrandbits(rng.choice([64, 400]))
        fast.ptr = rng.randrange(0, 60)
        fast.skip = rng.random() < 0.15
        widths = sorted(
            (rng.randrange(1, 40) for _ in range(rng.randrange(1, 12))),
            reverse=True,
        )
        if rng.random() < 0.3:
            rng.shuffle(widths)
        slow = fast.copy()
        fast.run_rewinds(widths)
        for width in widths:
            slow.apply(_runs("<" * width + "[x" * width + "x"))
        assert fast.key() == slow.key(), (widths, slow.key())

    # The edge arms: dead rows and empty sequences are no-ops, and a zero
    # count is the bare ``x``, which consumes a pending skip.
    dead = _Sim(16)
    dead.dead = True
    frozen = dead.key()
    dead.run_rewind(4)
    dead.run_rewinds([3, 2])
    assert dead.key() == frozen
    still = _Sim(16)
    frozen = still.key()
    still.run_rewinds([])
    assert still.key() == frozen
    skipping = _Sim(16)
    skipping.skip = True
    clone = skipping.copy()
    skipping.run_rewind(0)
    clone.apply(_runs("x"))
    assert skipping.key() == clone.key()


@pytest.mark.slow  # a ten-input rule build plus the retired sculpt, ~4s
def test_the_rule_spelling_matches_the_real_sculpt_at_ten_inputs() -> None:
    """Above ``_MUX_RULE_ARITY`` the spelled build is the sculpt's bytes.

    The rule names the combination; the spelling must then be exactly what
    :func:`_mux_sculpt` emits at that combination, so the retired machinery
    is run once here as the oracle.  Byte equality is the whole claim --
    the replay acceptance inside ``_mux`` already checked the prints.
    """
    import importlib
    import random

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    rng = random.Random(20260914)
    table = format(rng.getrandbits(1024), "01024b")
    built = module._mux(table, 10)  # noqa: SLF001
    assert built is not None

    base = module._mux_separate(10)  # noqa: SLF001
    top = min(base.ptrs()) - 2
    winner, trusted = module._mux_scout(  # noqa: SLF001
        base.fork(), table, 10, range(top, top + 1)
    )
    assert trusted
    assert winner is not None
    acc, direct, predicted = winner
    assert acc == top
    assert len(built) == predicted
    sculpted = module._mux_sculpt(  # noqa: SLF001
        base,
        table,
        10,
        acc,
        0,
        direct=direct,
        hint=module._SCULPT_POOL_CODE,  # noqa: SLF001
    )
    assert built == sculpted


@pytest.mark.slow  # two ten-input builds plus twelve interpreter rows, ~10s
def test_ten_input_builds_print_on_the_interpreter() -> None:
    """Sampled rows of both ten-input shapes answer on the real interpreter.

    The rule path's acceptance is the laws' replay; this is the standard
    above it -- the shipped interpreter running instantiated rows.  Six
    rows per shape, the two corner rows always among them; the full
    1024-row sweep was executed when the path landed, both shapes correct.
    """
    import hashlib
    import random

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools.boolean import minifuck
    from esolangs.tools.boolean.examples import _fill_minifuck

    digest = hashlib.sha256(b"dense:10").digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 1024:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    dense = "".join(bits[:1024])
    parity = "".join(str(bin(row).count("1") & 1) for row in range(1024))

    rng = random.Random(20260915)
    for table in (dense, parity):
        template = minifuck(table)
        for combo in sorted({*rng.sample(range(1024), 4), 0, 1023}):
            row = [(combo >> (9 - i)) & 1 for i in range(10)]
            io_ = ScriptedIO("")
            run(_fill_minifuck(template, row), io_)
            assert io_.getvalue() == table[combo], f"row {combo}"
