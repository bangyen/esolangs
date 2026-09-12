r"""Unit tests for the Minifuck boolean generator."""

import importlib
import re
from unittest.mock import patch

import pytest

from esolangs.tools.boolean.helpers import essential_inputs


def _unreachable(*_args: object, **_kwargs: object) -> None:
    r"""Stand in for a function a test asserts is never called."""
    raise AssertionError("this should not have been called")


def _all_derived_plans(derived_plans, staged_arities, n: int) -> dict:
    r"""Every staging the enumeration places at ``n``, in one pass."""
    if n not in staged_arities:
        return derived_plans(n, ())
    every = tuple(format(v, f"0{2**n}b") for v in range(2 ** (2**n)))
    return derived_plans(n, every)


def _slot_order(gen: object, table: str) -> list[int] | None:
    r"""The ``{Xi}`` indices in the order ``gen`` emits them, or None."""
    import re

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover.
    return [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", template)]


@pytest.mark.slow  # the degenerate tables are the.
def test_minifuck_slots_run_in_name_order() -> None:
    r"""Minifuck emits in name order, including the tables that once did."""
    from esolangs.tools.boolean import parameterized

    for table in ("11001100", "10101010", "01010101", "00001111"):
        slots = _slot_order(parameterized.minifuck, table)
        if slots is None:
            continue
        assert slots == sorted(slots), (table, slots)

    # ``00010001`` and ``11101110``.
    # enumeration derives both at.
    # ``_reconverged`` that dropped.
    # these two off the route and.
    # stayed green -- the four.
    # are pinned here, by the.
    for table in ("00010001", "11101110"):
        slots = _slot_order(parameterized.minifuck, table)
        assert slots is not None, table
        assert slots == sorted(slots), (table, slots)

    # **The whole arity, not a.
    # ``{X0}{X2}{X1}`` -- every one.
    # *middle* -- and they survived.
    # specific tables and none of.
    # cannot fail on the case.
    # assertion that matters and.
    # grew from.
    # residue to ``_mux``, which.
    unsorted_tables = []
    for value in range(256):
        table = format(value, "08b")
        slots = _slot_order(parameterized.minifuck, table)
        if slots is not None and slots != sorted(slots):
            unsorted_tables.append((table, slots))
    assert not unsorted_tables, unsorted_tables


@pytest.mark.slow  # two closed-form builds plus.
def test_minifuck_reconverged_tables_compute_their_function() -> None:
    r"""The reconvergence route computes, not merely emits in order."""
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
        # The ignored setters are.
        # not make the program's length.
        assert len(widths) == 1, (table, widths)


def test_minifuck_reconvergence_declines_outside_one_or_two_essentials() -> None:
    r"""The reconvergence route only handles one or two essential inputs."""

    from esolangs.tools.boolean.minifuck import _reconverged

    assert _reconverged("01", [], 1) is None
    assert _reconverged("01011010", [0, 1, 2], 3) is None


# 2.3s: two three-input.
@pytest.mark.slow
def test_minifuck_single_essential_falls_past_the_degenerate_lookup() -> None:
    r"""One essential input does not guarantee the cell lookup resolves it."""
    import importlib

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import run
    from esolangs.tools.boolean.examples import _fill_minifuck

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    for table in ("01010101", "10101010"):
        assert module.essential_inputs(table, 3) == [2]
        assert module._degenerate(table, 3) is None  # noqa: SLF001

        # Declining is only correct if.
        template = module.minifuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            io_ = ScriptedIO("")
            run(_fill_minifuck(template, bits), io_)
            assert io_.getvalue() == table[combo], f"{table} inputs {bits}"


# 4s: one five-input build,.
# effectively free next to.
@pytest.mark.slow
def test_minifuck_builds_five_input_xor() -> None:
    r"""Five-input XOR builds from a staging and prints all 32 rows."""
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


# 5.8s: builds the five-input.
# This is the guard on a.
# rather than a sample -- a.
# silent coverage regression,.
@pytest.mark.slow
def test_the_fused_column_walk_matches_the_one_at_a_time_derivation() -> None:
    r"""``_column_sweep`` agrees with ``_printed_column``, which is its."""
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

    # Driven through.
    # first.
    # module scope: once any.
    # build derives anything and.
    # enough on its own either,.
    # statements and only this call.
    # which is what the assertion.
    _derived_plans.cache_clear()
    with patch("esolangs.tools.boolean.minifuck._column_sweep", spy):
        _derived_plans(2, ("0110",))

    assert captured, "the build derived no columns, so nothing was compared"
    compared = 0
    for joint, cell7 in captured:
        sweep = real(joint, cell7)
        for acc in range(9, _MAX_ACC + 1):
            # An accumulator the walk.
            # mapping, which is exactly the.
            assert _printed_column(joint, acc, cell7) == sweep.get(acc), (acc, cell7)
            compared += 1
    assert compared >= 100, compared  # the sweep really did cover a.

    # The memo is what makes asking.
    # does, so a second ask for a.
    # the cache rather than.
    # impossible: `_find_pool` is.
    # that touches it is a repeat.
    joint, cell7 = captured[0]
    first = _printed_column(joint, 9, cell7)
    with patch("esolangs.tools.boolean.minifuck._find_pool", _unreachable):
        assert _printed_column(joint, 9, cell7) == first


def test_a_flipped_embed_complements_in_place_and_keeps_slot_order() -> None:
    r"""``flips`` is a live derivation coordinate, not dead weight."""
    import re

    from esolangs.tools.boolean.minifuck import _FLIP, _embed

    for n in (2, 3):
        plain = _embed(n).template()
        slots = [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", plain)]
        assert slots == sorted(slots), slots
        assert _embed(n, flips=0).template() == plain  # the default is no-op.

        for mask in range(1, 2**n):
            flipped = _embed(n, flips=mask).template()
            assert len(flipped) == len(plain) + len(_FLIP) * mask.bit_count(), mask
            order = [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", flipped)]
            assert order == slots, (mask, order)


def test_the_coverage_population_is_its_stated_definition() -> None:
    r"""The 109 the ``_SEPS`` figures are stated over, re-derived each run."""
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


@pytest.mark.slow  # 7.1s: enumerates the stagings.
def test_the_constraint_query_matches_the_index() -> None:
    r"""``_first_staging`` answers exactly what the index spelling answers."""
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

    # The budget arm: a capped.
    # capped fill visits, including.
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


@pytest.mark.slow  # two arity tabulations plus.
def test_the_constraint_query_matches_the_index_where_inserts_live() -> None:
    r"""The same equality at the arities the insert family serves."""
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
    r"""``_planned_bits`` equals ``_planned_bit`` per accumulator, per plan."""
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
    # A sweep that never reaches a.
    # three -- pure, point-flip,.
    assert modes == {0, 1, 2}, modes


# 3.7s standalone: the.
# XOR5 build above has already.
# a -k selection or a shuffled.
# for what it costs on its own.
@pytest.mark.slow
def test_minifuck_five_input_plans_are_derived_per_table() -> None:
    r"""At five inputs the derivation is asked for one table, not the arity."""

    from esolangs.tools.boolean.minifuck import (
        _INSERT_ARITIES,
        _STAGED_ARITIES,
        _derived_plans,
    )

    assert 5 in _STAGED_ARITIES
    assert 5 in _INSERT_ARITIES

    # A target set the enumeration.
    # complement are asked for.
    table = "".join(str(bin(r).count("1") & 1) for r in range(32))
    complement = "".join(str(1 - int(c)) for c in table)
    plans = _derived_plans(5, (table, complement))
    assert set(plans) <= {table, complement}


# 3.2s over 129 tests: runs the.
@pytest.mark.medium
class TestParameterizedMinifuck:
    r"""Input-by-substitution boolean generator for Minifuck."""

    def run_minifuck(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        r"""Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_minifuck

        return _fill_minifuck(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            # ``parameterized.minifuck``.
            # that costs, not the.
            # two-input table takes 2.7s.
            # a one-input table takes.
            # ``slow`` -- as does every.
            # one -- and the one-input.
            pytest.param("0001", 2, marks=pytest.mark.slow),  # AND.
            pytest.param("0110", 2, marks=pytest.mark.slow),  # XOR.
            # XNOR and NAND -- unreachable.
            pytest.param("1001", 2, marks=pytest.mark.slow),
            pytest.param("1110", 2, marks=pytest.mark.slow),
            # OR ("0111") and NOR ("1000").
            # ~47s here, and.
            # sixteen two-input tables.
            # that remain are the two.
            # cover.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minifuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minifuck(self.instantiate(template, bits))
            assert got == table[combo], f"{table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        r"""Every two-input table builds, including the ones the wall named."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.minifuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_two_inputs_never_search(self) -> None:
        r"""No two-input table reaches the searches."""
        import importlib

        from esolangs.tools.boolean import parameterized

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        # The searches these used to.
        # instead of patching them,.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        for table_int in range(16):
            table = format(table_int, "04b")
            # ``minifuck`` is cached, so go.
            # to be sure the build actually.
            template = module.minifuck.__wrapped__(format(table_int, "04b"))
            assert "{X0}" in template, table
            assert "{X1}" in template, table
        # And the public entry point.
        assert parameterized.minifuck("0110").count("{X") == 2

    @pytest.mark.slow  # derives a staging for all.
    def test_the_derivation_reaches_every_two_input_table(self) -> None:
        r"""Every two-input table gets a staging from the enumeration alone."""

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

    @pytest.mark.slow  # builds all 38 degenerate.
    def test_degenerate_three_input_tables_never_search(self) -> None:
        r"""Every table with at most two essential inputs is search-free."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        checked = 0
        # The searches these used to.
        # instead of patching them,.
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

    # 2.4s: the three-input.
    # unstaged arity is free --.
    # does not pay for the staged.
    @pytest.mark.slow
    def test_a_table_with_no_staging_falls_through(self) -> None:
        r"""An unplanned table declines the staging and reaches the next route."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.minifuck import (
            _STAGED_ARITIES,
            _derive_staging,
            _staged,
        )

        unstaged = max(_STAGED_ARITIES) + 1
        assert unstaged not in _STAGED_ARITIES
        assert _derive_staging("1" * 2**unstaged, unstaged) is None
        # A table the derivation does.
        for table_int in range(4):
            key = format(table_int, "08b")
            template = _staged(key, 3)
            assert template is not None, key
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == key[combo], f"{key} inputs {bits}"
        # ...and the public entry point.
        assert parameterized.minifuck("00000001")

    @pytest.mark.slow  # the four-input derivation is.
    def test_four_input_xor_builds_from_a_staging(self) -> None:
        r"""XOR4 builds without searching, and computes its function."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "0110100110010110"  # XOR4, the recorded search.
        # The searches these used to.
        # instead of patching them,.
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

    @pytest.mark.slow  # the four-input separation.
    def test_sculpted_route_computes_and_is_row_addressable(self) -> None:
        r"""``_mux`` builds a fully-essential table and every row is run."""
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
        r"""The named sculpt code is what the replaced scan would have found."""
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

    @pytest.mark.slow  # the six-input build, tens of.
    def test_no_arity_is_gated(self) -> None:
        r"""A fully-essential six-input table builds and prints all 64 rows."""
        import importlib

        from esolangs.tools.boolean.helpers import essential_inputs

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        assert module._MUX_MIN_ARITY == 2  # noqa: SLF001

        n = 6
        # Fixed table rather than a.
        # table cannot fail.
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
        r"""The budget is machine-independent, and it ships disabled."""
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

        # The ranking is a permutation.
        # reorders what is spent first,.
        assert sorted(module._SLICE_YIELD_ORDER) == sorted(plain)  # noqa: SLF001

    @pytest.mark.slow
    def test_the_slice_order_is_its_measured_yield(self) -> None:
        r"""The yield ranking is re-derived, not trusted."""
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
        r"""The five-input override is selected only while budgets are off."""
        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_STAGING_BUDGET", None)
            patch.setattr(module, "_STAGING_BUDGET_N5", 17)
            assert module._budget(5) == 17  # noqa: SLF001
            assert module._budget(6) == 17  # noqa: SLF001
            assert module._budget(4) is None  # noqa: SLF001

            # A finite general budget.
            patch.setattr(module, "_STAGING_BUDGET", 23)
            assert module._budget(5) == 23  # noqa: SLF001

    def test_a_budget_gives_up_length_not_coverage(self) -> None:
        r"""A table the budget skips still builds, through the sculpted route."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "0110100110010110"  # XOR4, which the staged route.
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
        r"""The budget is checked in the insert pass, not only the first one."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        orphan = "1101000011010000"  # no staging in the enumeration.
        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 8000  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derive_staging(orphan, 4) is None  # noqa: SLF001
            # And the oracle, which carries.
            # budget honoured in only one.
            # disagree for a reason.
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(4, (orphan,)) == {}  # noqa: SLF001
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

        # And it still builds, by the.
        template = module.minifuck(orphan)
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == orphan[combo], (orphan, bits)
        assert len(widths) == 1, widths

    def test_a_spent_budget_stops_before_the_first_staging(self) -> None:
        r"""A budget of zero derives nothing at all, in both spellings."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 0  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(2, ("0110",)) == {}  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._staging_index(2) == {}  # noqa: SLF001

            # One staging's worth spends.
            # of before it, which is the.
            # budget is consumed per.
            # gets exactly one look before.
            module._STAGING_BUDGET = 1  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(2, ("0001",)) == {}  # noqa: SLF001
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

    @pytest.mark.slow  # ~3.6s: a five-input index.
    def test_a_table_no_staging_reaches_costs_length_not_coverage(self) -> None:
        r"""A table outside every staging still builds, the other way."""
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
        r"""The separation is constructed, so it is exact and immediate."""
        import importlib
        import time

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for arity in (2, 3, 4, 5):
            start = time.monotonic()
            joint = module._mux_separate(arity)  # noqa: SLF001
            assert joint is not None, arity
            assert len(set(joint.ptrs())) == 2**arity, arity
            assert time.monotonic() - start < 1.0, arity

    @pytest.mark.slow  # 3.1s: a five-input sculpted.
    def test_five_input_tables_build_and_print_every_row(self) -> None:
        r"""A five-input table builds through the sculpted route and runs."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table = "01101001100101101001011001101001"  # five-input XOR.
        template = module._mux(table, 5)  # noqa: SLF001
        assert template is not None

        widths = set()
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    @pytest.mark.slow  # builds and runs all 256.
    def test_every_three_input_table_is_search_free(self) -> None:
        r"""All 256 three-input tables build without searching."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        searched = []
        # The searches these used to.
        # instead of patching them,.
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
        r"""The searching routes scan two separators; the plan names the rest."""

        from esolangs.tools.boolean.minifuck import (
            _SCAN_SEPS,
            _SEPS,
            _stagings,
        )

        assert _SEPS[:2] == _SCAN_SEPS, _SCAN_SEPS
        assert len(_SEPS) > len(_SCAN_SEPS), _SEPS
        # Every separator index the.
        # must offer all of them -- the.
        # past the scanned pair are the.
        offered = {sep_index for sep_index, *_rest in _stagings(3)}
        assert offered == set(range(len(_SEPS))), offered

    def test_the_pool_codes_cover_every_route(self) -> None:
        r"""The fixed codes must serve every route that reaches the endgame."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for table_int in range(16):
            table = format(table_int, "04b")
            assert module.minifuck.__wrapped__(table), table

    def test_the_pool_codes_all_serve_one_orientation(self) -> None:
        r"""Every pool code answers ``cell7 == 0``, and that is enough."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        codes = module._POOL_CODES  # noqa: SLF001
        assert codes, "the pool list should not be empty"
        # Shortest first, so the.
        assert list(codes) == sorted(codes, key=len), codes
        # Every code is built from the.
        # though the alphabet allows it.
        for code in codes:
            assert set(code) <= {"[", "<"}, code
        # No code answers ``cell7 ==.
        # Checked on the states a build.
        # constructed here --.
        # endgame, and a bare embed is.
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

        # And that is a property of the.
        # family reaches the other.
        # mirrors -- nothing is.
        # are ``'[<' * k`` walks with a.
        # ``cell7 == 1`` where no.
        # the "half a list" account.
        # unreachable".
        # .
        # Harvested separately, and.
        # on ``minifuck`` alone is not.
        # and a warm plan cache makes.
        # once instead of the hundreds.
        # sample would make the check.
        wide: list[tuple[object, int, int]] = []

        def record_all(joint: object, cell7: int, walk_out: int) -> object:
            if len(wide) < 400:
                wide.append((joint.fork(), cell7, walk_out))  # type: ignore[attr-defined]
            return real(joint, cell7, walk_out)

        with patch.object(module, "_find_pool", record_all):
            module._derived_plans.cache_clear()  # noqa: SLF001
            module.minifuck.cache_clear()
            # Harvested from the oracle's.
            # build now derives its columns.
            # ``_find_pool`` only twice per.
            # enumeration still visits the.
            # inputs, because the sample.
            # visits 77 sites where this.
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
        r"""A code answers ``cell7 == 0`` or ``cell7 == 1``, never both."""
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
            # The oracle's walk, for the.
            # above -- a build's.
            module._derived_plans(3, ("01101001",))  # noqa: SLF001
        module.minifuck.cache_clear()
        assert len(seen) > 100, f"expected a cold walk's lookups, got {len(seen)}"

        # The two witnesses from the.
        # step law the shipped codes.
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
        r"""The five codes are spelled by the law, not stored as strings."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        # The anchor: the derivation.
        assert module._POOL_CODES == (  # noqa: SLF001
            "[[[<[<<<<",
            "[<[[[<[<[<",
            "[<[<[[[<[<[<",
            "[<<[<[<[[[<[<",
            "[<[<[<<[[[<[[<<<",
        )

        # The step law itself, away.
        # of 2c-1 brackets, and.
        step = module._step  # noqa: SLF001
        assert step() == "[<"  # the default: carry one, trail.
        assert step(carry=2) == "[[[<"
        assert step(carry=1, odd=False) == "[[<"
        assert step(carry=1, backs=4) == "[<<<<"

        # Two of the five plans are.
        # what "one construction.
        plans = module._PLANS  # noqa: SLF001
        assert len(plans) == len(module._POOL_CODES)  # noqa: SLF001
        bare = [(n, core) for n, core, over in plans if not over]
        assert bare == [(4, 1), (5, 2)], bare

        # Every plan has exactly one.
        for n, core, over in plans:
            assert 0 <= core < n, (n, core)
            assert all(0 <= i < n for i in over), (n, over)

    def test_the_pool_codes_are_one_construction(self) -> None:
        r"""Each pool code is a mark, shifted three cells by a shared core."""

        from esolangs.tools.boolean.minifuck import _POOL_CODES, _Sim

        core = "[[[<["

        def run(code: str) -> object:
            machine = _Sim(64)
            for char in code:
                machine.exec(char)
            return machine

        # The law the whole family.
        # mark right by ceil(k / 2).
        # failure here says "the.
        for start in (2, 3, 4, 5):
            for brackets in range(1, 9):
                machine = run("[<" * start + "[" * brackets)
                marks = [i for i in range(32) if machine.cell(i)]  # type: ignore[attr-defined]
                assert marks == [start + (brackets + 1) // 2], (start, brackets, marks)
                assert machine.skip is bool(brackets % 2), (start, brackets)  # type: ignore[attr-defined]

        shifted = 0
        for code in _POOL_CODES:
            # The decomposition itself.
            assert code.count(core) == 1, code
            prefix = code[: code.find(core)]

            # The prefix plants at most one.
            before = run(prefix)
            marks = [i for i in range(32) if before.cell(i)]  # type: ignore[attr-defined]
            assert len(marks) <= 1, (code, marks)

            # Where the prefix leaves the.
            # that mark three cells right.
            after = run(prefix + core)
            moved = [i for i in range(32) if after.cell(i)]  # type: ignore[attr-defined]
            if marks and before.ptr == marks[0] - 1:  # type: ignore[attr-defined]
                assert moved == [marks[0] + 3], (code, marks, moved)
                assert after.ptr == marks[0] + 2, (code, after.ptr)  # type: ignore[attr-defined]
                shifted += 1
        assert shifted == 3, shifted

        # And ``'[<' * n`` is what.
        for n in range(1, 6):
            machine = run("[<" * n)
            marks = [i for i in range(32) if machine.cell(i)]  # type: ignore[attr-defined]
            assert marks == [n], (n, marks)

    @pytest.mark.slow  # one full three-input ablation.
    def test_dropping_a_pool_code_is_measured_not_assumed(self) -> None:
        r"""What each pool code is worth, ablated rather than argued."""
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
            # Zero, and it used to be ten.
            # ignored input is the *middle*.
            # sort; ``_mux`` solves them at.
            # ascending by construction.
            assert baseline == 0, baseline

            stranding = {}
            for dropped in range(len(codes)):
                reset(tuple(c for i, c in enumerate(codes) if i != dropped))
                stranded = []
                # The column and parked.
                # they no longer exist.
                # the same reason they were: it.
                # codes remain, so a live one.
                # dropped code strands and.
                with patch.object(module, "_mux", lambda *_a, **_k: None):
                    for table_int in range(256):
                        table = format(table_int, "08b")
                        # This pair has no staged route.
                        # no bracket run carries its.
                        # so it strands under every.
                        # flat 2 to every count.
                        # pool codes, so it is left out.
                        if table in ("01101101", "10010010"):
                            continue
                        try:
                            module.minifuck.__wrapped__(table)
                        except (AssertionError, ValueError):
                            # ``AssertionError`` is a stub.
                            # ``ValueError`` is ``_solve``.
                            # is what a strand looks like.
                            # column and parked searches.
                            # no route left below to.
                            # Both mean the same thing here.
                            # cost this table.
                            stranded.append(table)
                stranding[codes[dropped]] = len(stranded)

            # Three codes are required.
            assert sum(1 for n in stranding.values() if n) == 3, stranding
            # The other two strand nothing,.
            # dropping both takes the.
            free = [c for c, n in stranding.items() if not n]
            assert len(free) == 2, stranding
            reset(tuple(c for c in codes if c not in free))
            # **The reason these two were.
            # that rather than hiding it.**.
            # justified them was the quiet.
            # take the out-of-name-order.
            # does: ``_mux`` sorts those.
            # so both counts are 0 and the.
            # .
            # They are still shipped,.
            # measurement" is not the same.
            # the ablation above only.
            # answers shifts with arity.
            # has to measure at four, which.
            # question this assertion used.
            assert out_of_order() == baseline == 0, out_of_order()
        finally:
            reset(original)

    def test_the_degenerate_cells_are_where_they_were_written_down(self) -> None:
        r"""Measuring the embed reproduces the six cells that used to be stored."""

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
        # One input leaves no ``b1`` to.
        # is there rather than assuming.
        assert _degenerate_cells(1) == {
            "const1": 1,
            "~b0": 16,
            "b0": 17,
            "const0": 18,
        }

    def test_the_enumeration_and_the_derivation_agree(self) -> None:
        r"""``_stagings`` states the order ``_derived_plans`` actually walks."""

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
        # Every staging the derivation.
        # offers -- so the caps and the.
        offered = set(expected)
        for table, staging in _all_derived_plans(
            _derived_plans, _STAGED_ARITIES, 2
        ).items():
            assert staging in offered, (table, staging)

        # Four inputs adds the insert.
        # pure run: that ordering is.
        # already close assigned.
        # checked rather than assumed.
        # a second time as nested.
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
            ("0001", "scan"),  # AND: the embed's carry chain.
            ("0110", "column search"),  # XOR: found by searching for a.
        ],
    )
    def test_the_search_tiers_still_build_when_the_cheap_routes_miss(
        self, table: str, tier: str
    ) -> None:
        r"""With the derived routes stubbed off, the searches build the table."""
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

    # 4.8s: the enumeration it.
    @pytest.mark.slow
    def test_the_enumeration_skips_a_column_that_is_not_one_digit(self) -> None:
        r"""A probe printing anything but single digits is passed over."""

        from esolangs.tools.boolean.minifuck import (
            _STAGED_ARITIES,
            _derived_plans,
            _Joint,
        )

        real_printed = _Joint.printed

        def two_digits(self: object) -> list[str]:
            # Every row prints two.
            return ["00" for _ in real_printed(self)]

        try:
            _derived_plans.cache_clear()
            with patch.object(_Joint, "printed", two_digits):
                assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2) == {}
        finally:
            _derived_plans.cache_clear()
        # With the real print restored.
        # again, so the empty result.
        assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2)

    def test_reconverged_declines_what_it_cannot_replay(self) -> None:
        r"""``_reconverged`` bails rather than replaying a staging it lacks."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        # Two essential inputs with the.
        # takes its projection branch.
        # staging -- rather than the.
        # known cell.
        # guard firing and not the.
        table, n = "00010001", 3
        pair = essential_inputs(table, n)
        assert pair == [1, 2], pair
        assert module._reconverged(table, pair, n) is not None  # noqa: SLF001

        with patch.object(module, "_derive_staging", lambda *_a, **_k: None):
            assert module._reconverged(table, list(pair), n) is None  # noqa: SLF001

        # The same call, but the.
        # `brackets` is a string rather.
        # replay because it makes no.
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
        r"""A reset leaving the rows in different states is not built on."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        table, n = "0101", 2  # input 1 alone decides it;.
        essential = essential_inputs(table, n)
        # The route builds this table.
        assert module._reconverged(table, essential, n) is not None  # noqa: SLF001

        # ``[`` alone reads a.
        def diverging(_ignored: int) -> str:
            return "["

        with patch.object(module, "_reset_code", diverging):
            assert module._reconverged(table, essential, n) is None  # noqa: SLF001

    def test_the_constructed_reset_converges_every_arity(self) -> None:
        r"""``_reset_code`` drives all ``2**k`` rows to one identical state."""
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
        r"""``_mux`` keeps the shortest build, not the first one that prints."""
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
        r"""The derived accumulator sweeps equal the interpreter's, per suffix."""
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
        r"""The inverted index assigns exactly what the per-table sweep does."""
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

    @pytest.mark.slow  # ~22s: the arity 4 and 5 index.
    def test_the_staging_index_agrees_at_the_wider_arities(self) -> None:
        r"""The same agreement where the insert family and the budget live."""
        import importlib
        import random

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        random.seed(20260902)
        wide = [format(value, "016b") for value in range(65536)]
        wide = [t for t in wide if len(essential_inputs(t, 4)) == 4]
        samples = [(4, t) for t in random.sample(wide, 40)]
        samples.append((4, "0110100110010110"))  # four-input XOR.
        samples.append((5, "01101001100101101001011001101001"))  # five-input.

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
        r"""Outside ``_STAGED_ARITIES`` the derivation offers nothing."""

        from esolangs.tools.boolean.minifuck import (
            _STAGED_ARITIES,
            _derive_staging,
            _derived_plans,
        )

        for n in (1, max(_STAGED_ARITIES) + 1):
            assert n not in _STAGED_ARITIES
            assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, n) == {}
            assert _derive_staging("0" * 2**n, n) is None
        # At a staged arity the.
        # empty results above are the.
        assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2)

    def test_the_pool_rule_matches_the_scan_it_replaced(self) -> None:
        r"""``_find_pool`` answers what trying every code would have answered."""
        import importlib
        import random

        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        codes = module._POOL_CODES  # noqa: SLF001
        width = module._POOL_WIDTH  # noqa: SLF001
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        def scan(joint: object, cell7: int, walk_out: int) -> str | None:
            r"""The replaced search, kept as the oracle."""
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

        # Every single-row key in the.
        for low in range(1 << width):
            for ptr in range(ptr_max + 1):
                for skip in (False, True):
                    for cell7 in (0, 1):
                        joint = joint_of([row(low, ptr, skip=skip)])
                        walk_out = module._PROBE_WALK_OUT  # noqa: SLF001
                        assert module._find_pool(joint, cell7, walk_out) == scan(  # noqa: SLF001
                            joint, cell7, walk_out
                        ), (low, ptr, skip, cell7)

        # Joints, where the cross-row.
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
        r"""Deriving a slice at a time answers what one big table would."""
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
        r"""The bound is a refusal, not a gap in a table."""
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
        # .
        served = [
            code
            for code in module._POOL_CODES  # noqa: SLF001
            if module._pool_reaches(joint, code, 1, 12)  # noqa: SLF001
        ]
        assert served, "expected the scan to still answer outside the domain"

    def test_pool_reaches_refuses_a_code_that_kills_a_row(self) -> None:
        r"""``_pool_reaches`` rejects code that kills or desynchronises a row."""
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
        # ``[[`` leaves a row dead or.
        # the walk out is priced -- a.
        assert not module._pool_reaches(joint, "[[", cell7, walk_out)  # noqa: SLF001
        # ``x`` writes under the.
        assert not module._pool_reaches(joint, "x", cell7, walk_out)  # noqa: SLF001
        # A code that ends past the.
        # walked backwards: the walk.
        # already beyond it can never.
        assert not module._pool_reaches(joint, "[x", cell7, 0)  # noqa: SLF001
        # Bare navigation is refused.
        # the code has to leave the.
        assert not module._pool_reaches(joint, "", cell7, walk_out)  # noqa: SLF001
        # Exactly one of the pool's own.
        # are a filter over the list,.
        served = [
            code
            for code in module._POOL_CODES  # noqa: SLF001
            if module._pool_reaches(joint, code, cell7, walk_out)  # noqa: SLF001
        ]
        assert len(served) == 1, served

    @pytest.mark.slow  # re-simulates a derived.
    def test_stagings_deliver_the_column_the_read_sees(self) -> None:
        r"""Every staging really does deliver its table's column at the read."""

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
        r"""The template has placeholders and every fill has the same length."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minifuck("0110")
        assert "{X0}" in template
        assert "{X1}" in template
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, f"unequal instantiation lengths: {lengths}"

    def test_the_simulator_mirrors_the_interpreter_at_its_edges(self) -> None:
        r"""The search's model of a row has to match what Minifuck does."""
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

        # The print flips the cell it.
        # the byte writes its own 1:.
        printing = _Sim(16)
        printing.exec(".")
        assert printing.out == ["@"]
        assert not printing.dead

        # Past cell 8 the flip lands.
        zero = _Sim(16)
        zero.ptr = 9
        zero.exec(".")
        assert zero.dead, "printing a zero byte ends the row"
        assert zero.out == []

    def test_the_simulator_agrees_with_a_real_run_on_random_streams(self) -> None:
        r"""``_Sim`` and a whole-program run agree, instruction for instruction."""
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
                # The whole-program run fetches.
                # instead marks the row dead;.
                # the emitter's contract.
                assert sim.dead, (stream, "the emitter missed a read")
                deaths += 1
                continue

            assert not sim.dead, (stream, "the emitter killed a live row")
            assert "".join(sim.out) == io_.getvalue(), stream
            printed += len(sim.out)
            skips += sim.skip

        # The comparison is worthless.
        # fire, so assert the sample.
        assert printed, "no stream printed"
        assert deaths, "no stream hit the zero-pool read"
        assert skips, "no stream ended on a pending skip"

    def test_the_closed_form_runs_agree_with_stepping_them(self) -> None:
        r"""A whole run's law matches applying it one instruction at a time."""
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

        # A sweep that never reaches.
        # the pending skip is what.
        # and a walk that never wrote a.
        assert skips, "no state carried a pending skip"
        assert clamped, "no clamp started away from cell 0"
        assert walks_cascaded, "no walk touched the tape"

    def test_the_laws_agree_with_the_interpreters_step(self) -> None:
        r"""Every law matches ``_step``, from arbitrary states, over the."""
        import importlib
        import random

        from esolangs.interpreters.tape_based.minifuck import _step
        from esolangs.tools.boolean.minifuck_sim import _runs, _Sim

        # The package re-exports the.
        # submodule's name, so the.
        m = importlib.import_module("esolangs.tools.boolean.minifuck")

        def reference(row: _Sim, code: str) -> None:
            r"""The retired stepper: one ``_step`` call per character."""
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

        # The comparison is worthless.
        # fire, so assert the sample.
        assert deaths, "no state hit the zero-pool read"
        assert printed, "no state printed"
        assert skips, "no state ended on a pending skip"

    def test_the_parsed_emission_matches_stepping_every_row(self) -> None:
        r"""``_Joint.emit`` parses a code once and advances rows by whole runs."""
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
            # What makes the comparison.
            # an emission's effect is.
            # are the states the.
            if len({m.ptr for m in reference}) > 1:
                checked[0] += 1

        # ``minifuck`` and the pool.
        # an earlier test already built.
        # Counting only the.
        # meaningful without depending.
        minifuck.cache_clear()
        with patch.object(minifuck_sim._Joint, "emit", checking_emit):  # noqa: SLF001
            for table in ("01", "0110", "10010110"):
                minifuck(table)
        minifuck.cache_clear()

        assert checked[0], "no emission met rows whose pointers had diverged"

    def test_the_computed_endgame_choice_matches_trying_all_four(self) -> None:
        r"""``_try_print`` names the pair the retired four-fork trial found."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        def retired(joint: object, truth_table: str, acc: int) -> object:
            r"""The replaced trial loop, verbatim."""
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

        # One table per route: a.
        # including the in-pool cell 1.
        # staged pair, a reconverged.
        # -- the scout replays only the.
        # build is one call site now.
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
        # The comparison has to see.
        assert hits, "no site printed"
        assert misses, "no site declined"

    def test_the_walk_needs_a_converged_pointer_going_right(self) -> None:
        r"""``[x`` walks are only safe rightward from one shared position."""
        from esolangs.tools.boolean.minifuck import _clamp, _embed, _walk_to

        spread = _embed(2)
        with pytest.raises(ValueError, match="converged pointer"):
            _walk_to(spread, 0)

        clamped = _embed(2)
        _clamp(clamped)
        with pytest.raises(ValueError, match="cannot walk left"):
            _walk_to(clamped, -5)

    def test_the_pool_search_needs_the_rows_to_agree_on_the_pointer(self) -> None:
        r"""A pool is only a pool if every row reads it from one place."""
        from esolangs.tools.boolean.minifuck import _clamp, _embed, _find_pool

        spread = _embed(2)
        assert len(set(spread.ptrs())) > 1, "the embed should leave rows apart"
        assert _find_pool(spread, 0, 12) is None

        clamped = _embed(2)
        _clamp(clamped)
        assert len(set(clamped.ptrs())) == 1

    def test_the_endgame_refuses_an_impossible_setup(self) -> None:
        r"""Two ways the endgame cannot run, reported rather than emitted."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
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


@pytest.mark.slow  # one four-input staging.
def test_insert_pass_stops_as_soon_as_its_last_target_is_placed() -> None:
    r"""The second pass has its own early exit, and only it can reach this."""
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    table = "0100110110100101"
    plans = module._derived_plans(4, (table,))  # noqa: SLF001
    assert set(plans) == {table}
    # A str suffix is the insert.
    assert isinstance(plans[table][2], str)


def test_mux_refuses_below_its_minimum_arity() -> None:
    r"""``_mux`` separates rows, which needs at least two of them to."""
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    assert module._MUX_MIN_ARITY == 2  # noqa: SLF001
    assert module._mux("01", 1) is None  # noqa: SLF001


def test_the_scout_distrusts_states_its_summary_cannot_speak_for() -> None:
    r"""A base outside the parity law's key sends ``_mux`` to the sweep."""
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
    r"""Off the canonical state the probe answers by simulation,."""
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
    r"""A code that strands a skip or leaves the pool region has no frame."""
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    byte = module._mux_separate(2).ms[0].tape & module._POOL_MASK  # noqa: SLF001
    assert module._probe_frame("[", byte) is None  # noqa: SLF001
    assert module._probe_frame("[x" * 9, byte) is None  # noqa: SLF001
    assert module._probe_frame(module._SCULPT_POOL_CODE, byte) is not None  # noqa: SLF001


def test_the_weight_law_matches_the_parsed_runs() -> None:
    r"""``run_weight`` is ``apply(_runs(_mux_weight(k)))``, or refuses."""
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

    # The edge arms: a dead row and.
    dead = _Sim(16)
    dead.dead = True
    frozen = dead.key()
    assert dead.run_weight(3)
    assert dead.key() == frozen
    fresh = _Sim(16)
    frozen = fresh.key()
    assert fresh.run_weight(0)
    assert fresh.key() == frozen

    # The joint-level fallback: a.
    # parsed runs and the pair must.
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
    r"""A sculpting round and a fused round sequence match the parsed runs."""
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

    # The edge arms: dead rows and.
    # count is the bare ``x``,.
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


def _rule_arities() -> list[int]:
    r"""The rule's first arity and the top of the sweep."""
    import importlib

    module = importlib.import_module("esolangs.tools.boolean.minifuck")
    first = module._MUX_RULE_ARITY  # noqa: SLF001
    return sorted({first, 10}) if first <= 10 else [first]


@pytest.mark.slow  # the rule build plus the.
@pytest.mark.parametrize("n", _rule_arities())
def test_the_rule_spelling_matches_the_real_sculpt(n: int) -> None:
    r"""From ``_MUX_RULE_ARITY`` the spelled build is the sculpt's bytes."""
    import importlib
    import random

    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    rng = random.Random(20260914)
    table = format(rng.getrandbits(2**n), f"0{2**n}b")
    built = module._mux(table, n)  # noqa: SLF001
    assert built is not None

    base = module._mux_separate(n)  # noqa: SLF001
    top = min(base.ptrs()) - 2
    winner, trusted = module._mux_scout(  # noqa: SLF001
        base.fork(), table, n, range(top, top + 1)
    )
    assert trusted
    assert winner is not None
    acc, direct, predicted = winner
    assert acc == top
    assert len(built) == predicted
    sculpted = module._mux_sculpt(  # noqa: SLF001
        base,
        table,
        n,
        acc,
        0,
        direct=direct,
        hint=module._SCULPT_POOL_CODE,  # noqa: SLF001
    )
    assert built == sculpted


@pytest.mark.slow  # two ten-input builds plus.
def test_ten_input_builds_print_on_the_interpreter() -> None:
    r"""Sampled rows of both ten-input shapes answer on the real."""
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
