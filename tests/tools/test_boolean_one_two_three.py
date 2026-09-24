"""Covers :mod:`esolangs.tools.one_two_three_construct`."""

import random
from collections.abc import Iterable

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs, runs
from esolangs.tools.one_two_three import ONE, ZERO
from esolangs.tools.one_two_three_construct import _RING
from tests.tools.boolean_runners import one_two_three_result


def _mask(cells: Iterable[int]) -> int:
    """Build a tape mask from cell numbers (bit ``c + _RING`` per cell)."""
    m = 0
    for c in cells:
        m |= 1 << (c + _RING)
    return m


#: One input's run, as the template spells it.
_X = TEMPLATE_CHAR * len(ZERO)


# 2.3s over 132 tests: runs the generated program.
@pytest.mark.medium
class TestParameterizedOneTwoThree:
    """Input-by-substitution boolean generator for the no-input language 123.

    123's ``2`` reads real stdin, so a decision tree cannot read its inputs;
    the generator embeds them, ``1`` for a one and ``2`` for a zero.  Like
    ArrowQueue the answer is the termination convention -- halt for a ``0``
    entry, loop for a ``1`` -- decided by state-cycle detection.

    The recorded monotone ceiling was the displacement-neutral ``12``/``21``
    setter's, not the language's: the +-1 fill breaks position lockstep, so
    XOR and NAND come out too and all sixteen two-input tables are covered.

    Every arity is *constructed*; the stored plan tables are retired.  Small
    arities build in ``one_two_three``, wider ones in
    ``one_two_three_construct``.  Neither replays what it emitted, so the
    sweeps here are the execution gate: every ``n <= 3`` row run per command.
    """

    def run(self, program: str) -> str:
        return one_two_three_result(program)

    def instantiate(self, template: str, bits: list[int]) -> str:
        return fill_runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * len(bits), bits)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every one-, two- and three-input table halts or loops per its entry."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.one_two_three(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run(self.instantiate(template, bits))
                assert got == table[combo], (table, bits)

    def test_the_tables_walls_md_called_unreachable(self) -> None:
        """XOR and NAND build, against the recorded monotone ceiling.

        The monotonicity argument forbids these: a set bit can only add a
        pass under the neutral setter, so the looping set is upward-closed.
        """
        from esolangs.tools import parameterized

        for table in ("0110", "1110", "1001", "1000"):
            template = parameterized.one_two_three(table)
            got = "".join(
                self.run(self.instantiate(template, [(c >> 1) & 1, c & 1]))
                for c in range(4)
            )
            assert got == table

    def test_no_row_diverges(self) -> None:
        """No emitted row marches the pointer right forever.

        ``run_until_halt_or_cycle`` never returns on unbounded growth, so a
        template with such a row hangs the suite rather than report a 1.
        Every looping row must revisit a state: a run that neither halts nor
        cycles within the budget is exactly the shape that must not ship.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools import parameterized

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    code = self.instantiate(template, bits)
                    machine = _Machine(code, ScriptedIO(""))
                    seen = set()
                    for _ in range(10_000):
                        if machine.halted:
                            break
                        state = machine.snapshot()
                        if state in seen:
                            break
                        seen.add(state)
                        machine.step()
                    else:  # pragma: no cover - a diverging row would reach here
                        pytest.fail(f"{code!r} neither halts nor revisits a state")

    def test_batched_gate_agrees_with_the_interpreter(self) -> None:
        """The construction's replay gate matches a per-command run.

        ``_replay_verdict`` executes a maximal ``1``/``2`` run at a time in
        closed form, which makes the gate affordable (95s to 0.28s at five
        inputs) -- but a batched cycle detector sampling the wrong events
        could call a loop a halt, so every row through three inputs is
        checked both ways.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools import parameterized
        from tests.tools.one_two_three_support import _replay_verdict

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    code = self.instantiate(template, bits)
                    machine = _Machine(code, ScriptedIO(""))
                    seen = set()
                    stepwise = "1"
                    for _ in range(10_000):
                        if machine.halted:
                            stepwise = "0"
                            break
                        state = machine.snapshot()
                        if state in seen:
                            break
                        seen.add(state)
                        machine.step()
                    assert _replay_verdict(code) == stepwise == table[combo], (
                        table,
                        bits,
                    )

    @pytest.mark.slow
    def test_the_replay_gate_agrees_on_programs_it_did_not_build(self) -> None:
        """The batched executor is checked against arbitrary 123 code.

        Every other test drives ``_replay_verdict`` on programs the
        construction *built*, where the pointer stays in range and the
        reads never fire; an executor wrong outside that shape passes all
        of them.  So random programs over the three commands are compared
        against :class:`_Machine`, which shares no code with the batching.
        Reads-stdin and budget-exceeding programs are skipped both sides.
        Fixed seed: 177 comparable, zero disagree.
        """

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from tests.tools.one_two_three_support import _replay_verdict

        def stepwise(code: str) -> str | None:
            """The interpreter's own verdict, or None if it is not comparable."""
            machine = _Machine(code, ScriptedIO(""))
            seen = set()
            for _ in range(20_000):
                if machine.halted:
                    return "0"
                state = machine.snapshot()
                if state in seen:
                    return "1"
                seen.add(state)
                try:
                    machine.step()
                except EOFError:
                    return None
            return None

        rng = random.Random(7)
        compared = 0
        for _ in range(300):
            code = "".join(rng.choice("123") for _ in range(rng.randint(1, 12)))
            expected = stepwise(code)
            if expected is None:
                continue
            try:
                got = _replay_verdict(code)
            except ValueError:
                continue  # the executor's own guards; not a verdict to compare
            compared += 1
            assert got == expected, code
        assert compared == 177

    def test_the_construction_emits_an_exact_template(self) -> None:
        """``construct`` itself, pinned -- not the small route.

        The exact-template tests above go through
        ``parameterized.one_two_three``, so the wider construction had no
        golden of its own: a plan emitting three bytes more per table, or
        two fewer, changed nothing any test compared.
        """
        from esolangs.tools.one_two_three_construct import construct

        assert construct("01") == (
            f"2222{_X}1111121211222222111111233222332233222211211211213311111111"
            "122222222212331111111111"
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        The paint flag and the separation law move a handful of bytes
        per table without changing a verdict, so no single table is a
        reliable witness -- ``00111000`` moves by two and ``11111111`` by
        two the other way.  The sum over the sweep is, and it is the same
        shape of assertion the small route already carries.
        """
        from esolangs.tools.one_two_three_construct import construct

        total = sum(len(construct(format(value, "08b"))) for value in range(256))
        assert total == 189055

    def test_slots_run_in_name_order(self) -> None:
        """Every emitted template embeds exactly two runs, one per input."""
        from esolangs.tools import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.one_two_three(table)
            assert "{X" not in template
            assert len(runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * 2)) == 2, table

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero and a one embed at equal width, so length leaks nothing."""
        from esolangs.tools import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.one_two_three(table)
            sizes = {
                len(self.instantiate(template, [(c >> 1) & 1, c & 1])) for c in range(4)
            }
            assert len(sizes) == 1, (table, sizes)

    def test_a_wider_table_is_constructed(self) -> None:
        """A four-input table builds through the constructed route.

        This used to assert a :class:`ValueError`, on the recorded reason
        that an inert embed shifts the pointer phase the plan decodes --
        one decode shape's bound, not the language's.  Every row is
        replayed here on the real interpreter.
        """
        from esolangs.tools import parameterized

        table = "0000000000000000"
        template = parameterized.one_two_three(table)
        assert len(runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * 4)) == 4, table
        sizes = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            sizes.add(len(program))
            assert self.run(program) == table[combo], (table, bits)
        assert len(sizes) == 1, (table, sizes)

    @pytest.mark.parametrize(
        ("table", "length", "route"),
        [
            ("00000000", 63, "small"),
            ("10000000", 155, "wide"),
            ("00010111", 201, "small"),
            ("01101001", 151, "small"),
        ],
    )
    def test_three_inputs_take_the_shorter_route(
        self, table: str, length: int, route: str
    ) -> None:
        """``n == 3`` builds both routes and keeps the shorter program.

        Both are correct, so only size sees the choice.  The small route
        still wins the mean, 201.6 bytes against 214.9 -- that is what pins
        the crossover at ``n > 3`` -- but it stopped winning every table
        once the wide chain gave up pre-painting, so gating the chain out
        by arity would cost size on 98 of the 256.  These four straddle it.
        """
        from esolangs.tools import parameterized
        from esolangs.tools.one_two_three import _construct_small, _in_name_order
        from esolangs.tools.one_two_three_construct import _construct_linear

        small = len(_in_name_order(_construct_small(table, 3), 3))
        wide = len(_in_name_order(_construct_linear(table, 3), 3))
        assert (wide < small) == (route == "wide"), (small, wide)
        assert len(parameterized.one_two_three(table)) == length == min(small, wide)

    @pytest.mark.slow
    def test_the_separation_law_is_the_least_mean(self) -> None:
        """The law's constants are re-derived, not trusted.

        ``_LAWS`` claims one selection rule at every arity: over constant
        walk seeds and alternating pure-test displacement vectors, the law
        with the least mean template length.  Re-running that sweep at
        ``n <= 2`` fails a hand-edited constant rather than shipping it;
        ``n == 3`` is 13 laws over 256 tables, minutes rather than seconds.
        """
        from itertools import product

        from esolangs.tools.one_two_three import (
            _LAWS,
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _endgame,
            _on_mark,
            _verdict_junky,
            _work,
        )

        def prototype(n: int, walk: int, disps: tuple[int, ...]) -> object:
            """Replay one candidate law, or ``None`` if it does not fit.

            A candidate that walks a row off the ring raises exactly as a
            build would; here that only means "not this law", so the
            raise is caught rather than propagated.
            """
            # pylint: disable=duplicate-code
            # The overlap with ``_separated``'s replay is the point, not
            # an oversight: this test re-derives the shipped constants,
            # so it has to replay the law independently.  Sharing a
            # helper would check the generator against itself and a bug
            # in the replay would pass here, so the copy stays and the
            # similarity check is told so rather than left to fail in CI.
            _work[0] = _WORK_BUDGET
            try:
                b = _Builder(n)
                for i in range(n):
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
                else:
                    return None
                for i, step in enumerate(disps):
                    b.run(("1" if i % 2 == 0 else "2") * step)
                    b.test()
            except ConstructError:
                return None
            poss = [r.pos for r in b.live()]
            if len(set(poss)) != len(poss) or any(p % 2 == 0 for p in poss):
                return None
            return b

        def mean_length(n: int, proto: object) -> float | None:
            total = 0
            tables = ["".join(t) for t in product("01", repeat=2**n)]
            for table in tables:
                _work[0] = _WORK_BUDGET
                b = proto.clone()  # type: ignore[attr-defined]
                try:
                    _verdict_junky(b, table)
                    _endgame(b)
                except ConstructError:
                    return None
                total += len(b.template())
            return total / len(tables)

        for n in (1, 2):
            ranked = []
            for walk in range(9):
                for depth in range(5):
                    for disps in product(range(1, 11), repeat=depth):
                        proto = prototype(n, walk, disps)
                        if proto is None:
                            continue
                        mean = mean_length(n, proto)
                        if mean is not None:
                            ranked.append((mean, walk, disps))
            assert ranked, n
            ranked.sort()
            _best_mean, best_walk, best_disps = ranked[0]
            assert (best_walk, best_disps) == _LAWS[n], (n, ranked[:3])

    @pytest.mark.medium  # 2120 rows of the real interpreter, 0.9s
    def test_the_wide_route_is_exhaustive_and_loses_on_the_mean(self) -> None:
        """The chain four inputs and up really emit, gated and compared.

        ``construct`` sends ``n <= 3`` to the modelled pipeline, so the wide
        chain needs its own exhaustive gate and its own honest comparison:
        every row of every table through three inputs on the real
        interpreter, and a *mean* rather than witnesses -- the chain is the
        smaller on 98 of the 256.
        """
        from esolangs.tools.one_two_three import one_two_three
        from esolangs.tools.one_two_three_construct import _construct_linear

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                template = _construct_linear(table, n)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    program = self.instantiate(template, bits)
                    assert self.run(program) == table[combo], (n, table, bits)
        from esolangs.tools.one_two_three import _construct_small, _in_name_order

        tables = [format(value, "08b") for value in range(256)]
        wide = [len(_construct_linear(table, 3)) for table in tables]
        small = [len(_in_name_order(_construct_small(table, 3), 3)) for table in tables]
        assert [sum(wide), sum(small)] == [55004, 51609]
        assert sum(a < b for a, b in zip(wide, small, strict=True)) == 98
        # ``one_two_three`` is the pointwise minimum of the two, so naming
        # it as one side would compare a route with the contest holding it.
        built = [len(one_two_three(table)) for table in tables]
        assert built == [min(a, b) for a, b in zip(wide, small, strict=True)]
        assert sum(built) == 46703

    @pytest.mark.parametrize(
        ("table", "template"),
        [
            ("01", f"{_X}223311122212331111"),
            ("0001", f"22{_X}22{_X}22331113322331111332133121233111111121121"),
        ],
    )
    def test_the_emitted_template_is_exact(self, table: str, template: str) -> None:
        """The construction is deterministic down to the byte.

        ``_construct_small`` builds one prototype per arity, so the
        emission is a function of the law and the table alone.  A change to
        the law's constants, or to the order its tests fire in, moves these
        bytes even where every truth-table assertion still passes.
        """
        from esolangs.tools import parameterized

        assert parameterized.one_two_three(table) == template

    def test_the_paint_pass_is_only_run_when_something_was_painted(
        self,
    ) -> None:
        """``b.test()`` after the paints is conditional, and the flag varies.

        Of the 276 tables through three inputs, 10 need no paint at all, so
        the flag is genuinely two-valued; forcing it either way leaves every
        template correct, so only size sees it, and the total is asserted
        because the effect is spread across the sweep.  It also pins the two
        routes' joint cost: 47902 characters, against 52826 when the
        separation law served every three-input table alone and the wide
        route's 56902.  (A template is as long as the programs it fills to.)
        """
        from esolangs.tools import parameterized

        total = 0
        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                total += len(parameterized.one_two_three(table))
        assert total == 47902

    def test_a_seed_with_even_positions_is_refused(self) -> None:
        """The junky verdict rejects a seed whose rows are not distinct odd.

        The paint offsets are collision-free only because every live row
        sits at a distinct *odd* position: two rows sharing an offset would
        sit one cell apart, which odd-and-distinct forbids.  The shipped law
        separates to odd at every arity, so the state is built by hand here.
        """
        from esolangs.tools.one_two_three import (
            _WORK_BUDGET,
            ConstructError,
            _separated,
            _verdict_junky,
            _work,
        )

        _work[0] = _WORK_BUDGET
        builder = _separated(1).clone()
        # Nudge one row onto an even cell; the law itself never does.
        builder.live()[0].pos += 1
        assert any(r.pos % 2 == 0 for r in builder.live())
        with pytest.raises(ConstructError) as caught:
            _verdict_junky(builder, "01")
        assert str(caught.value) == "verdict precondition: positions not distinct odd"

    def test_every_pipeline_stage_fires_on_one_table(self) -> None:
        """A single table exercises each stage the docstring describes.

        ``00111000`` has 1-rows above 0-rows, so its build takes the shield
        paints as well as the embed, separation, kill, and endgame -- every
        stage on a real trajectory, not inferred from ``construct()``'s
        success.  The paints go through ``_paint_all``; ``_paint`` itself is
        the small-arity route's, covered by the test two below.
        """
        from esolangs.tools import one_two_three_construct as construct_mod

        called: set[str] = set()
        originals = {
            name: getattr(construct_mod, name)
            for name in ("_phase_a", "_separate", "_paint_all", "_verdict", "_endgame")
        }

        def watch(name: str, fn: object) -> object:
            def wrapper(*args: object, **kwargs: object) -> object:
                called.add(name)
                return fn(*args, **kwargs)  # type: ignore[operator]

            return wrapper

        for name, fn in originals.items():
            setattr(construct_mod, name, watch(name, fn))
        try:
            # construct() emits without replaying; every row is run on
            # the real interpreter below, which is the execution gate.
            template = construct_mod.construct("00111000")
        finally:
            for name, fn in originals.items():
                setattr(construct_mod, name, fn)

        assert called == set(originals), called
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            program = self.instantiate(template, bits)
            assert self.run(program) == "00111000"[combo], bits

    def test_a_set_bit_replays_three_times_and_leaves_what_leftover_says(
        self,
    ) -> None:
        """The splitter's contract, re-simulated: 3 passes, and the leftovers.

        ``_leftover`` is a closed form for the tape a level leaves above a
        row's landing cell and the shields are planted off it, so a wrong
        cell is a wrong verdict, not a bigger template.  Re-derived on an
        exact row model: a clear bit escapes on pass one, a set bit on pass
        three (the split is ``3*d - (d + 2)``, which halves the walk), every
        row lands on ``start + 2*bit_reverse(r)``, and every cell above
        matches the closed form.
        """
        from esolangs.tools.one_two_three_construct import (
            _exec_run,
            _leftover,
            _on_mark,
            _Row,
            _run_parts,
            _segment,
            _walk,
            _work,
        )

        for n in (1, 2, 3, 4, 5):
            _work[0] = 10**9
            bits = [tuple(map(int, format(r, f"0{n}b"))) for r in range(2**n)]
            rows = [_Row(b) for b in bits]
            for i in range(n):
                segment = _segment(i)[: -len("33")]
                for row in rows:
                    code = segment.replace(_X, ONE if row.bits[i] else ZERO)
                    passes = 0
                    while passes == 0 or _on_mark(row):
                        passes += 1
                        for part in _run_parts(code):
                            _exec_run(row, part[0], len(part))
                    assert passes == (3 if row.bits[i] else 1), (n, i, row.bits)
            start = sum(_walk(i) + 2 for i in range(n))
            for r, row in enumerate(rows):
                spread = int(format(r, f"0{n}b")[::-1], 2)
                assert row.pos == start + 2 * spread, (n, r, row.pos)
                for off in range(1, 2 * _walk(n - 1) + 3):
                    marked = bool(row.tape >> (row.pos + off + _RING) & 1)
                    assert marked == _leftover(n, row.bits[-1], off), (n, r, off)

    def test_the_searched_routes_worst_tables_build_at_once(self) -> None:
        """The tables that starved the searched verdict are ordinary now.

        ``1000110011010101`` and ``0100000011001001`` each burned a whole
        four-input budget under a searched verdict.  The wide route plans
        instead of searching; each is checked row by row on the interpreter.
        """
        from esolangs.tools.one_two_three_construct import construct

        for table in ("1000110011010101", "0100000011001001"):
            # construct() emits without replaying; the rows below are the gate.
            template = construct(table)
            for combo in range(16):
                bits = [(combo >> (3 - i)) & 1 for i in range(4)]
                program = self.instantiate(template, bits)
                assert self.run(program) == table[combo], (table, bits)

    @pytest.mark.slow  # one four-input template, all rows on the interpreter
    def test_a_dense_four_input_sweep_witness_stays_exact(self) -> None:
        """Pin one mixed table from the exhaustive constructor sweep.

        The exhaustive four-input sweep is a one-shot script rather than a
        suite entry -- 65536 tables, 1048576 rows through the replay oracle.
        This witness keeps a gate local to the suite: all sixteen rows halt
        or revisit an exact state, never through a fuel limit.
        """
        from esolangs.tools.one_two_three_construct import construct

        table = "1100010001000111"
        template = construct(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            assert self.run(program) == table[combo], (table, bits)

    def test_paint_marks_one_cell_and_restores_every_position(self) -> None:
        """``_paint(k)`` flips exactly cell ``pos + k`` per row, in place.

        The shield algebra rests on this: two walk-descend blocks whose
        stripes cancel everywhere but the top cell.  Checked across rows at
        distinct positions with junk tapes, ``k == 1`` and wider offsets.
        """
        from esolangs.tools.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint,
            _work,
        )

        _work[0] = _WORK_BUDGET
        for k in (1, 2, 3, 17, 100):
            b = _Builder(2)
            tapes = (0, 0b1011 << _RING, 1 << (40 + _RING), 0b110 << _RING)
            for row, pos, tape in zip(b.rows, (1, 5, 29, 41), tapes, strict=True):
                row.pos, row.tape = pos, tape
            before = [(r.pos, r.tape) for r in b.rows]
            _paint(b, k)
            after = [(r.pos, r.tape) for r in b.rows]
            for (p0, t0), (p1, t1) in zip(before, after, strict=True):
                assert p1 == p0, k
                assert t1 == t0 ^ (1 << (p0 + k + _RING)), k

    def test_paint_all_sweeps_the_span_once(self) -> None:
        """The fused painter flips an arbitrary mask in one linear sweep."""
        from esolangs.tools.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint_all,
            _work,
        )

        _work[0] = _WORK_BUDGET
        b = _Builder(2)
        for row, pos in zip(b.rows, (1, 5, 29, 41), strict=True):
            row.pos = pos
        before = [(r.pos, r.tape) for r in b.rows]
        _paint_all(b, [1, 3, 6])
        assert b.template() == "222222112112111211"
        delta = sum(1 << k for k in (1, 3, 6))
        for (p0, t0), row in zip(before, b.rows, strict=True):
            assert row.pos == p0
            assert row.tape == t0 ^ (delta << (p0 + _RING))

    def test_paint_all_replays_mixed_runs_exactly(self) -> None:
        """A conditional sweep replays ``21`` as two different commands."""
        from esolangs.tools.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint_all,
            _work,
        )

        _work[0] = _WORK_BUDGET
        b = _Builder(1)
        b.rows[1].tape = 1 << (2 + _RING)
        b.run("2221")
        _paint_all(b, [7])
        b.test()
        assert [row.pos for row in b.rows] == [2, 4]
        assert all((row.tape >> (9 + _RING)) & 1 for row in b.rows)
        assert not (b.rows[0].tape >> (11 + _RING)) & 1
        assert (b.rows[1].tape >> (11 + _RING)) & 1

    def test_the_verdict_checks_its_position_preconditions(self) -> None:
        """A state violating the parity law raises instead of emitting.

        The shield algebra needs every live position distinct and odd, and
        separation delivers that at every probed arity -- but the verdict
        re-checks rather than assumes, so an arity that broke the parity
        would raise instead of handing out an unvouched template.
        """
        from esolangs.tools.one_two_three_construct import (
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _verdict,
            _work,
        )

        _work[0] = _WORK_BUDGET
        even = _Builder(1)
        even.rows[0].pos, even.rows[1].pos = 2, 5
        with pytest.raises(ConstructError, match="precondition"):
            _verdict(even, "01")

        shared = _Builder(1)
        shared.rows[0].pos = shared.rows[1].pos = 5
        with pytest.raises(ConstructError, match="precondition"):
            _verdict(shared, "01")

        all_zero = _Builder(1)
        all_zero.rows[0].pos, all_zero.rows[1].pos = 2, 5
        _verdict(all_zero, "00")  # no 1-rows: nothing to prove, no check

    def test_an_exhausted_work_budget_is_declined(self) -> None:
        """A table that would build still raises once the work runs out.

        ``_work`` is deterministic (simulated commands, not wall clock), so
        shrinking :data:`_WORK_BUDGET` reproduces the exhausted-budget branch
        exactly -- the path an unconvergent search takes, without paying one.
        """
        from esolangs.tools import one_two_three_construct as construct_mod

        original_budget = construct_mod._WORK_BUDGET  # noqa: SLF001
        construct_mod._WORK_BUDGET = 50  # noqa: SLF001
        try:
            with pytest.raises(ValueError, match="work budget ran out"):
                construct_mod.construct("00000000")
        finally:
            construct_mod._WORK_BUDGET = original_budget  # noqa: SLF001

    def test_normalize_reports_a_live_locked_ring(self) -> None:
        """Four distinct rows pinned to all four ring cells cannot escape.

        ``_normalize`` steps every live row together, so four *different*
        rows one each on -1, -2, -3 and 0 never converge: the round freeing
        the -3 row re-occupies -4 -> 0 while another stays put.  Contrived --
        real builds keep rows in lockstep -- but it must terminate, not spin.
        """
        from esolangs.tools.one_two_three_construct import (
            ConstructError,
            _Builder,
            _normalize,
            _Row,
            _work,
        )

        rows = []
        for i, pos in enumerate((-1, -2, -3, 0)):
            row = _Row((i,))
            row.pos = pos
            rows.append(row)
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = rows
        _work[0] = 100_000  # _normalize is called outside construct() here
        with pytest.raises(ConstructError, match="live-locked"):
            _normalize(b)

    def test_close_reports_no_clean_cell_in_range(self) -> None:
        """A row TRUE on every cell in the search window has no exit.

        ``_close`` walks right for a position where every live row is
        simultaneously on a FALSE cell; a row whose tape covers the whole
        search window supplies none, so the search must give up.
        """
        from esolangs.tools.one_two_three_construct import (
            ConstructError,
            _Builder,
            _close,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask(range(100002))
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = [row]
        _work[0] = 10_000_000  # _close is called outside construct() here
        with pytest.raises(ConstructError, match="no clean closing cell"):
            _close(b)

    def test_fixpoint_reports_a_non_converging_rerun(self) -> None:
        """A segment that never revisits a state within the cap gives up.

        A dense tape lets a single ``2`` keep the row TRUE at every position
        while it marches right forever, so the rerun neither escapes nor
        repeats within the cap -- a diverging candidate segment's shape.
        """
        from esolangs.tools.one_two_three_construct import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask(range(200))
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]
        b.rows = [row]
        _work[0] = 10_000  # fixpoint is called outside construct() here
        with pytest.raises(ConstructError, match="fixpoint cap"):
            b.fixpoint(row)

    def test_test_reports_a_kill_that_escapes(self) -> None:
        """``test(kills=...)`` requires every named victim to provably loop."""
        from esolangs.tools.one_two_three_construct import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask({0})
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]  # pos 0 -> 1, leaves the tape: escapes, not a kill
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside construct() here
        with pytest.raises(ConstructError, match="kill escaped"):
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_a_kill_that_never_fires(self) -> None:
        """``test(kills=...)`` refuses a close where a victim tested FALSE.

        A kill whose victim never lands on a TRUE cell leaves the row alive;
        the close must report it, because every adopted kill claims one
        specific row is now provably looping.
        """
        from esolangs.tools.one_two_three_construct import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = 0  # nothing marked: the victim tests FALSE everywhere
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside construct() here
        with pytest.raises(ConstructError, match="kill missed"):
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_an_unintended_loop(self) -> None:
        """A plain ``test()`` requires every TRUE row to escape, not loop."""
        from esolangs.tools.one_two_three_construct import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask({0})
        # eight '1's flip cells 0,-1,-2,-3 twice each: pos and tape both
        # return to the start, a proven revisit where a plain test wants
        # an escape instead
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["1"] * 8
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside construct() here
        with pytest.raises(ConstructError, match="unintended loop"):
            b.test()

    def test_an_empty_table_is_declined(self) -> None:
        """A table implying zero inputs raises rather than building nothing.

        ``"1"`` is a well-formed truth table of length ``2**0``, so it clears
        the power-of-two check and is refused on arity instead.  The rule is
        the shared validator's, so this asserts the shared wording.
        """
        from esolangs.tools import parameterized

        # ``match`` is a substring search, so the equality below is what
        # actually pins the message.
        with pytest.raises(ValueError, match="at least one input") as caught:
            parameterized.one_two_three("1")
        assert str(caught.value) == (
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function"
        )

    def test_each_input_is_embedded_once(self) -> None:
        """Each input's run appears exactly once, and nothing else is a run."""

        from esolangs.tools import parameterized

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                spans = runs(template, TEMPLATE_CHAR, ((ZERO, ONE),) * n)
                assert len(spans) == n, (table, spans)
                assert template.count(TEMPLATE_CHAR) == n * len(ZERO), table

    def test_every_batched_run_charges_the_work_budget(self) -> None:
        """Each closed form in ``_exec_run`` has to stop on a drained budget.

        The batched paths exist so a long run costs O(1) instead of ``w``
        trips through ``_exec_char``, but the budget counts *simulated
        commands* and must not depend on which path ran them.  Each case
        selects one path, with the budget just under its charge.
        """
        from esolangs.tools.one_two_three_construct import (
            _exec_char,
            _exec_run,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        def drained(budget: int, ch: str, pos: int, w: int) -> None:
            row = _Row((0,))
            row.pos = pos
            _work[0] = budget
            _exec_run(row, ch, w)

        # The per-character fallback, reached directly.
        _work[0] = 0
        with pytest.raises(_WorkExhaustedError):
            _exec_char(_Row((0,)), "1")
        # `2` from pos >= 0: a plain right-walk.
        with pytest.raises(_WorkExhaustedError):
            drained(3, "2", 0, 10)
        # `1` from pos >= 0 stopping at -1 or above: one contiguous XOR.
        with pytest.raises(_WorkExhaustedError):
            drained(3, "1", 8, 5)
        # `1` descending past -1: the head above the ring boundary.
        with pytest.raises(_WorkExhaustedError):
            drained(2, "1", 5, 20)
        # `1` inside the ring: whole laps reduced to a parity.
        with pytest.raises(_WorkExhaustedError):
            drained(3, "1", -1, 12)

    def test_the_endgame_parks_survivors_and_reports_a_state_it_cannot(
        self,
    ) -> None:
        """Parking is what makes a template halt, so failing it must raise.

        A state with no survivors is already parked.  Four occupied residues
        mod 4 take the ring round -- rows of equal residue fuse, so a class
        has to be freed first.  The allowance is ``64 * 2**n + 64`` passes,
        which a small ``n`` beside far wider rows outlasts: a real exit.
        """
        from esolangs.tools.one_two_three_construct import (
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _endgame,
            _Row,
            _work,
        )

        _work[0] = _WORK_BUDGET

        no_survivors = _Builder(1)
        for row in no_survivors.rows:
            row.dead = True
        _endgame(no_survivors)  # returns rather than dividing by no rows

        crowded = _Builder(2)
        for i, row in enumerate(crowded.rows):
            row.pos, row.tape = i, 0
        assert len({row.pos % 4 for row in crowded.live()}) == 4
        _endgame(crowded)
        assert {row.pos for row in crowded.live()} == {-1}

        stranded = _Builder.__new__(_Builder)
        stranded.n = 1  # an allowance of 192 passes
        stranded.chunks, stranded.seg = [], []
        stranded.rows = []
        for i in range(12):
            row = _Row((i,))
            row.pos, row.tape = i * 977, 0
            stranded.rows.append(row)
        with pytest.raises(ConstructError, match="endgame did not converge"):
            _endgame(stranded)

    def test_a_stage_refusal_surfaces_as_a_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stage that cannot prove its move is reported, never worked
        around -- the alternative is emitting a template no stage proved.
        """
        from esolangs.tools import one_two_three_construct as module

        def refuse(*_: object, **__: object) -> None:
            raise module.ConstructError("verdict precondition: constructed refusal")

        monkeypatch.setattr(module, "_verdict", refuse)
        with pytest.raises(ValueError, match="123 construction failed"):
            module.construct("0110")

    def test_a_looping_row_reads_as_a_one(self) -> None:
        """A 1-row is decided by cycle detection, not by halting.

        A 1-row does not halt -- it is the loop the kill built -- so the
        verdict comes from Brent's cycle detection.  Both readings are
        pinned: the real interpreter's, which is the shipped contract, and
        :func:`_replay_verdict`'s, which the suite uses elsewhere.
        """
        from esolangs.tools.one_two_three_construct import construct
        from tests.tools.one_two_three_support import _replay_verdict

        template = construct("01")
        for bit in (0, 1):
            program = self.instantiate(template, [bit])
            assert self.run(program) == "01"[bit], bit
            assert _replay_verdict(program) == "01"[bit], bit

    def test_a_spread_of_three_input_tables_builds(self) -> None:
        """A stride-17 sample of the 256 three-input tables all build.

        The planned verdict claims totality by argument; this spread is
        the fast in-suite witness (the slow suite sweeps every table).
        """
        from esolangs.tools.one_two_three_construct import construct

        built = 0
        for value in range(0, 256, 17):
            try:
                construct(format(value, "08b"))
            except ValueError:
                continue
            built += 1
        assert built == 16

    def test_the_remaining_batched_run_and_token_paths(self) -> None:
        """``2`` from inside the ring batches too, and a plain token is a char.

        The ring case is decided by its first step -- -1 and -2 land on 0 --
        after which the rest is a plain right-walk charging the budget like
        every other closed form.  ``apply_token`` resolves an input fill
        against the row's own bits; a plain token passes straight through.
        """
        from esolangs.tools.one_two_three_construct import (
            _WORK_BUDGET,
            _Builder,
            _exec_run,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        inside_the_ring = _Row((0,))
        inside_the_ring.pos = -1
        _work[0] = 2
        with pytest.raises(_WorkExhaustedError):
            _exec_run(inside_the_ring, "2", 10)

        _work[0] = _WORK_BUDGET
        b = _Builder(1)
        b.apply_token(b.rows[0], "1")
        assert b.rows[0].pos == -1

    def test_a_two_at_minus_three_is_refused_rather_than_reading_stdin(self) -> None:
        """``2`` at -3 would read real input, so the move is rejected.

        The harness runs on an empty script, so a read is fatal rather than
        merely wrong: the builder declines the candidate that reached this
        cell.  The neighbours are the contrast -- -2 lands on 0 (printing a
        junk byte no snapshot sees), anything else is a plain step right.
        """
        from esolangs.tools.one_two_three_construct import (
            _WORK_BUDGET,
            ConstructError,
            _exec_char,
            _Row,
            _work,
        )

        _work[0] = _WORK_BUDGET
        reads_stdin = _Row((0,))
        reads_stdin.pos = -3
        with pytest.raises(ConstructError, match="reads stdin"):
            _exec_char(reads_stdin, "2")

        wraps = _Row((0,))
        wraps.pos = -2
        _exec_char(wraps, "2")
        assert wraps.pos == 0

        steps = _Row((0,))
        steps.pos = 4
        _exec_char(steps, "2")
        assert steps.pos == 5

    def test_closing_walks_only_when_a_row_sits_on_a_true_cell(self) -> None:
        """``_close`` emits the walk it needs and nothing when already clean.

        A fresh builder starts every row on cell 0 with a blank tape, already
        a FALSE cell, so the close is free.  Flipping cell 0 forces the walk,
        and the emitted ``2``s carry every row to a clean cell -- none there
        would leave the next segment starting on a TRUE cell.
        """
        from esolangs.tools.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _close,
            _work,
        )

        _work[0] = _WORK_BUDGET
        already_clean = _Builder(1)
        _close(already_clean)
        assert "2" not in "".join(already_clean.chunks)

        _work[0] = _WORK_BUDGET
        needs_a_walk = _Builder(1)
        needs_a_walk.run("1")  # flips cell 0 TRUE and steps into the ring
        _close(needs_a_walk)
        emitted = "".join(needs_a_walk.chunks)
        assert "2" in emitted
        # Every row ends on a cell that is FALSE, which is what "closed" means.
        assert all(
            row.pos >= 0 and not row.tape >> (row.pos + _RING) & 1
            for row in needs_a_walk.live()
        )

    def test_replaying_twos_handles_the_empty_walk_and_the_stdin_cell(self) -> None:
        """A zero-width run is a no-op; a run starting at -3 is refused.

        ``_replay_twos`` re-derives the interpreter's rule for ``2`` without
        the builder's model, so it owns the same stdin refusal ``_exec_char``
        does -- reached here by starting a real run on the cell rather than
        by walking onto it.
        """
        from esolangs.tools.one_two_three_construct import ConstructError
        from tests.tools.one_two_three_support import _replay_twos

        # Nothing to walk: the state is handed straight back.
        assert _replay_twos(5, 0b1011, 0) == (5, 0b1011)
        assert _replay_twos(-3, 0, -2) == (-3, 0)  # a negative width is empty too

        with pytest.raises(ConstructError, match="reads stdin"):
            _replay_twos(-3, 0, 1)

    def test_replaying_a_verdict_skips_commandless_and_unknown_characters(
        self,
    ) -> None:
        """Only ``1`` and ``2`` are commands; everything else is a NOP.

        A program with no command at all never starts the walk and halts
        with no output, which is the ``"0"`` verdict.  A program that mixes
        commands with other characters has to step over them rather than
        treating them as a run -- so the two spellings agree.
        """
        from tests.tools.one_two_three_support import _replay_verdict

        assert _replay_verdict("") == "0"
        assert _replay_verdict("xyz") == "0"  # no command: nothing to run
        # The NOPs are skipped, so padding a program cannot change its verdict.
        assert _replay_verdict("1x1") == _replay_verdict("11")
        assert _replay_verdict("x1y1z") == _replay_verdict("11")


def test_a_malformed_template_is_refused() -> None:
    """The one-run-per-input invariant is asserted, not assumed.

    Every table the generator builds satisfies it, so the guard is
    reachable only by handing the helper a body that violates it -- a run
    short, or a fill character loose in the program text -- which is what
    a mistyped plan would look like.  Fast: nothing runs.
    """
    from esolangs.tools.one_two_three import _in_name_order

    assert _in_name_order(_X * 2, 2) == _X * 2

    with pytest.raises(ValueError, match="does not embed 2 inputs"):
        _in_name_order(_X, 2)
    with pytest.raises(ValueError, match="does not embed 1 inputs"):
        _in_name_order(_X + "1" + _X, 1)
