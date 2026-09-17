"""Covers :mod:`esolangs.tools.pct_squared_minus_one` end to end.

The routes with modules of their own have files to match:
test_boolean_pct_fold and test_boolean_pct_helpers.
"""

import importlib
import itertools

import pytest

#: The one pair every input is spelled by, at every arity.
_PAIR = ("s", "i")


def _module():
    # The package re-exports the generator under the submodule's own name,
    # so the module is imported explicitly rather than by attribute.
    return importlib.import_module("esolangs.tools.pct_squared_minus_one")


def _run_pct(prog: str) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.pct_squared_minus_one import run

    io = ScriptedIO()
    run(prog, io)
    return io.getvalue()


def _instantiate(tpl: str, bits: list[int]) -> str:
    from tests.tools.fills import _fill_pct_squared_minus_one

    return _fill_pct_squared_minus_one(tpl, bits)


def _executes(template: str, table: str, n: int) -> None:
    """Every row prints its answer, and every fill has one length."""
    lengths = set()
    for row in range(2**n):
        bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
        program = _instantiate(template, bits)
        lengths.add(len(program))
        assert _run_pct(program) == table[row], (table, bits)
    assert len(lengths) == 1, sorted(lengths)


class TestParameterizedPctSquaredMinusOne:
    """Input-by-substitution boolean generator for %^2^-1.

    The wall proved for %^2^-1 (``the relevant tests``) shows no program
    that *reads* its inputs computes XOR or AND at any length.  That bounds
    the reading model, not the language: these programs embed their bits
    instead, so the read that erases the accumulator never happens, and
    every two-input table builds.

    Every input is the one pair ``s``/``i``, so the template is what
    carries the table: the weight of each run is the doublings after it,
    and the fold's relocations do the rest.
    """

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR -- the function the wall forbids a reader
            ("1001", 2),  # XNOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools import parameterized

        _executes(parameterized.pct_squared_minus_one(table), table, n)

    # 272 templates, each executed on every row: about four seconds.
    @pytest.mark.slow
    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            _executes(parameterized.pct_squared_minus_one(table), table, n)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_input_is_the_one_pair(self, n: int) -> None:
        """Uniform: the setters are ``s``/``i`` repeated, for every table.

        This is the conventions audit's cell, read off the generator rather
        than the programs: no route spells an input any other way, whatever
        the table, so the pair carries the bit and the template the rest.
        """
        from esolangs.tools import parameterized

        module = _module()
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.pct_squared_minus_one(table)
            assert module.setters(template) == (_PAIR,) * n, table

    def test_instantiations_share_a_length(self) -> None:
        """All four programs are the same length, so none leaks its inputs."""
        from esolangs.tools import parameterized

        template = parameterized.pct_squared_minus_one("0110")
        lengths = {len(_instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)}
        assert len(lengths) == 1, lengths

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.tools import parameterized
        from esolangs.tools.helpers import TEMPLATE_CHAR, runs
        from esolangs.tools.pct_squared_minus_one import body, setters

        template = parameterized.pct_squared_minus_one("0110")
        assert "{X" not in template
        pairs = setters(template)
        assert len(pairs) == 2
        assert template.count(TEMPLATE_CHAR) == sum(len(zero) for zero, _ in pairs)
        assert len(runs(body(template), TEMPLATE_CHAR, pairs)) == 2

    def test_programs_never_read_input(self) -> None:
        """No emitted program contains ``n``, the input command.

        This is what separates the generator from the model the wall
        bounds: the bits arrive by substitution, so the read that overwrites
        the accumulator never runs.
        """
        from esolangs.tools import parameterized

        for table_int in range(16):
            template = parameterized.pct_squared_minus_one(format(table_int, "04b"))
            for a in (0, 1):
                for b in (0, 1):
                    assert "n" not in _instantiate(template, [a, b])

    @pytest.mark.parametrize(
        ("table", "expected"),
        [
            ("00", "l$"),
            ("11", "ipsl$"),
            ("01", "$psl"),
            ("10", "$pipl"),
            ("00110011", "$'$psl$"),  # input 1 of three, runs on both sides
            ("11110000", "$pipl$$"),  # NOT input 0 of three
        ],
    )
    def test_a_one_input_table_prints_off_its_run(
        self, table: str, expected: str
    ) -> None:
        """A table depending on one input needs no fold.

        Every run is a translation, so a template without the reset is
        affine in the bits, and an affine function into ``{0, 1}`` depends
        on at most one input.  The deciding run is followed by ``ps`` (the
        bit) or ``pip`` (its complement) and ``l``; earlier runs are erased
        by one ``'``, later ones execute after the print.  Spelled and
        executed, since the whole point is that the text is tiny.
        """
        module = _module()
        n = (len(table) - 1).bit_length()
        template = module.pct_squared_minus_one(table)
        assert module.body(template) == expected
        assert module.setters(template) == (_PAIR,) * n
        _executes(template, table, n)

    def test_a_two_input_table_is_not_one_input(self) -> None:
        """The affine read declines every table that needs the reset."""
        module = _module()
        assert module._one_input("0110", 2) is None  # noqa: SLF001
        assert module._one_input("0001", 2) is None  # noqa: SLF001
        assert module._one_input("0011", 2) is not None  # noqa: SLF001

    def test_fold_doubling_is_what_reorders(self) -> None:
        """The fold computes a table whose runs alternate four times.

        ``00000101`` has four runs, and under the wipe-only algebra the
        groups' cyclic order is invariant -- each wipe caps the spread at
        3003, one short of the 3004 a relocation jumps, so a landing can
        never split two survivors and an alternating word of four or more
        runs can never contract to two points.  The doubling is what breaks
        that: it regrows a gap past 3004, the landing splits it, and the
        order changes.  This table is the smallest that *needs* the escape,
        so it pins the mechanism rather than merely exercising the path.
        """
        from esolangs.tools.pct_squared_minus_one import _fold

        table = "00000101"
        template = _fold(table, 3)
        assert template is not None
        # The plan, not the ladder: the runs' own doublings weight the
        # inputs, so the ``m`` looked for is one past the last run.
        after_last_run = _module().body(template).rsplit("$", 1)[1]
        assert after_last_run.startswith("psp")
        plan = after_last_run[3:].lstrip("m")
        assert "m" in plan, "the doubling never fired"
        _executes(template, table, 3)

    @pytest.mark.slow  # a 19-run plan plus 32 interpreter runs
    def test_fold_closes_five_inputs(self) -> None:
        """A five-input table with no symmetry computes on the distinct ladder.

        Pinned as a random table: no mask collapses it onto the popcount
        ladder, so it is laid a row per position and folded from there.
        The template is executed on all 32 rows at equal fill length.
        """
        from esolangs.tools.pct_squared_minus_one import _fold

        table = "11011111100100101001101110111000"
        template = _fold(table, 5)
        assert template is not None
        _executes(template, table, 5)

    @pytest.mark.slow  # a 21-point plan plus 32 interpreter runs
    def test_a_wide_state_plans_and_executes(self) -> None:
        """A 21-point table plans in milliseconds and computes every row.

        Pinned when this table was a planner regression: an earlier
        search-based configuration explored it for fifty seconds and then
        *refused a table it can build*.  The rule construction plans it
        outright, and the rows are executed rather than merely planned,
        because a plan that does not compute is not a fix.
        """
        from esolangs.tools.pct_squared_minus_one import _fold

        table = "01010101000101111111010101011110"
        template = _fold(table, 5)
        assert template is not None
        _executes(template, table, 5)

    @pytest.mark.parametrize("bit", ["0", "1"])
    def test_fold_finishes_a_single_class(self, bit: str) -> None:
        """A constant table leaves one class, which ``finish`` zeroes and shifts.

        The dispatcher prints constants off a zero accumulator without a
        fold; called directly, the fold opens on one run and the endgame's
        one-class arm erases every row with ``'`` and shifts to the digit.
        """
        from esolangs.tools.pct_squared_minus_one import _fold

        table = bit * 8
        template = _fold(table, 3)
        assert template is not None
        assert "'p" in _module().body(template)
        _executes(template, table, 3)

    @pytest.mark.parametrize(
        ("table", "reaches"),
        [
            # A minterm: symmetric only under the complementation of its
            # own row, so the popcount ladder is laid with one ``p$pi``.
            ("0010", "the popcount ladder under a mask"),
            # Majority: symmetric as it stands, and a threshold, so the plan
            # is empty and the endgame prints straight off the ladder.
            ("00010111", "an empty plan on the popcount ladder"),
            # XOR at three inputs: symmetric, but alternating, so the plan
            # has work to do on a four-point state.
            ("01101001", "a folded popcount ladder"),
            # No mask keeps this one's collisions inside a class -- every
            # two-input table is a masked-symmetric one, so it takes three
            # -- and the distinct ladder is laid, the rows one apart.
            ("00000101", "the distinct ladder after every mask is refused"),
        ],
    )
    def test_tables_that_reach_each_ladder(self, table: str, reaches: str) -> None:
        """Witnesses for each ladder the dispatch can settle on.

        Executed rather than merely built: a program that reaches a new arm
        and computes the wrong function is the failure this is here to
        catch, so every row runs and the fills stay one width.
        """
        from esolangs.tools import parameterized

        n = (len(table) - 1).bit_length()
        template = parameterized.pct_squared_minus_one(table)
        body = _module().body(template)
        if "under a mask" in reaches:
            assert "p$pi" in body
        if "empty plan" in reaches:
            assert "m" * 12 in body, reaches
            assert len(body) < 80, reaches
        if "distinct" in reaches:
            assert "$pspm$pspm$pspmm" in body
        _executes(template, table, n)

    def test_dispatch_falls_through_to_the_fold(self) -> None:
        """The public entry returns what the fold returns past the affine read.

        The fold tests above call ``_fold`` themselves to keep their cost
        to the plan they are pinning; this pins that the dispatch hands a
        table the affine read declines to the fold unchanged.
        """
        from esolangs.tools.pct_squared_minus_one import (
            _fold,
            _one_input,
            pct_squared_minus_one,
        )

        table = "11011111100100101001101110111000"
        assert _one_input(table, 5) is None
        assert pct_squared_minus_one(table) == _fold(table, 5)

    def test_the_refusal_names_what_builds(self) -> None:
        """With both fold routes failed the generator refuses, not guesses."""
        module = _module()
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_fold", lambda *_a, **_k: None)
            patch.setattr(module, "_interleaved_fold", lambda *_a, **_k: None)
            with pytest.raises(ValueError, match="symmetric under a complementation"):
                module.pct_squared_minus_one("0110")

    def test_the_model_mirrors_every_command_the_language_has(self) -> None:
        """``_apply`` stands in for the interpreter, so it owes it every op.

        The endgame doubles and resets on purpose, so ``m`` and the
        over-3003 reset are on the path every built program takes; a model
        that quietly disagreed with the interpreter would let a tail be
        validated against a machine that does not exist.
        """
        from esolangs.tools.pct_squared_minus_one import _LIMIT, _apply

        assert _apply(10, "s") == 8  # s subtracts 2
        assert _apply(10, "i") == 7  # i subtracts 3
        assert _apply(10, "m") == 20  # m doubles
        assert _apply(10, "p") == -10  # p negates
        assert _apply(10, "'") == 0  # ' erases

        # The reset fires *before* a command, not after: one past the limit
        # is zeroed and the command then applies to that zero.
        assert _apply(_LIMIT + 1, "s") == -2
        assert _apply(_LIMIT, "s") == _LIMIT - 2, "at the limit nothing resets"

        # The model covers the five commands the generator emits; the
        # language's others (``l``/``e``/``n`` do I/O, ``t`` jumps) leave the
        # accumulator alone here, exactly as a character the interpreter
        # does not recognize does.  Skipping rather than raising is what
        # lets a tail be scored without first filtering its spelling.
        assert _apply(10, "l") == 10
        assert _apply(10, "x") == 10
        assert _apply(10, "sxs") == 6, "an unmodelled command interrupts nothing"


class TestPctLadders:
    """The uniform pair's ladders: the prefix, its legality, and the order."""

    @pytest.mark.parametrize(
        ("weights", "mask"),
        [
            ((1, 1, 1), 0),
            ((1, 1, 1), 5),
            ((4, 2, 1), 0),
            ((8, 4, 2), 0),
            ((2, 2, 1), 3),
        ],
    )
    def test_the_prefix_lays_every_row_where_the_ladder_says(
        self, weights: tuple[int, ...], mask: int
    ) -> None:
        """Replaying the filled prefix lands each row on its ladder value.

        The prefix is the runs with their ``psp`` fix-ups and the doublings
        between them; ``_ladder_values`` is the arithmetic the plan is
        built on.  The two are held to each other on every row, through
        the same model the emitter replays.
        """
        from esolangs.tools.helpers import fill_runs

        module = _module()
        n = len(weights)
        prefix = module._ladder_prefix(n, weights, mask)  # noqa: SLF001
        values = module._ladder_values(n, weights, mask)  # noqa: SLF001
        for row in range(2**n):
            bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
            program = fill_runs(prefix, "$", [_PAIR] * n, bits)
            assert module._apply(0, program) == values[row], (row, program)  # noqa: SLF001

    def test_a_weight_that_is_not_a_doubling_is_refused(self) -> None:
        """Only non-increasing powers of two are spellable as doublings."""
        module = _module()
        with pytest.raises(AssertionError):
            module._ladder_prefix(2, (3, 1), 0)  # noqa: SLF001
        with pytest.raises(AssertionError):
            module._ladder_prefix(2, (1, 2), 0)  # noqa: SLF001

    def test_legality_is_class_purity_of_the_collisions(self) -> None:
        """The popcount ladder is legal exactly for masked-symmetric tables."""
        module = _module()
        legal = module._ladder_legal  # noqa: SLF001
        ones = (1, 1)
        assert legal("0110", 2, ones, 0)  # XOR: symmetric
        assert legal("0001", 2, ones, 0)  # AND: symmetric
        assert not legal("0100", 2, ones, 0)  # a minterm: not under mask 0
        assert legal("0100", 2, ones, 1)  # ... but under its own row's mask
        assert all(legal("0110", 2, ones, mask) for mask in range(4))
        assert legal("0010", 2, (2, 1), 0)  # the distinct ladder always is

    def test_ladders_come_symmetric_first_then_distinct(self) -> None:
        """Every legal mask of the popcount ladder precedes the distinct ones."""
        module = _module()
        ladders = module._fold_ladders("0100", 2)  # noqa: SLF001
        assert ladders[0] == ((1, 1), 1)
        assert ladders[-3:] == [((8, 4), 0), ((4, 2), 0), ((2, 1), 0)]
        assert all(mask == 0 for _, mask in ladders[-3:])
        # XOR is symmetric under every mask, so all four come first.
        assert [m for w, m in module._fold_ladders("0110", 2) if w == (1, 1)] == [  # noqa: SLF001
            0,
            1,
            2,
            3,
        ]

    def test_masks_above_the_sweep_are_read_off_the_table(self) -> None:
        """Past eight inputs only four masks are tested, and they suffice.

        A minterm at nine inputs is symmetric under its own row and under
        that row's complement; a sweep of all 512 would find the same two.
        """
        module = _module()
        n = module._MASK_SWEEP + 1  # noqa: SLF001
        row = 37
        minterm = "".join("1" if r == row else "0" for r in range(2**n))
        masks = [m for w, m in module._fold_ladders(minterm, n) if w == (1,) * n]  # noqa: SLF001
        assert masks == [row, row ^ (2**n - 1)]
        maxterm = "".join("0" if r == row else "1" for r in range(2**n))
        assert [m for w, m in module._fold_ladders(maxterm, n) if w == (1,) * n] == [  # noqa: SLF001
            row,
            row ^ (2**n - 1),
        ]


class TestPctEndgame:
    """``finish``: the doubling endgame that prints a threshold state."""

    @staticmethod
    def emitter(groups: dict[int, tuple[int, str]]):
        module = _module()
        em = module._FoldEmitter.__new__(module._FoldEmitter)  # noqa: SLF001
        em.table = "".join(cls for _, cls in groups.values())
        em.rows = len(groups)
        em.body = []
        em.load(groups)  # type: ignore[arg-type]
        return em

    def test_the_chains_reach_their_values(self) -> None:
        """Each chain walks 0 to one under (or over) a residue system."""
        module = _module()
        chain0, digit0 = module._ENDGAME["0"]  # noqa: SLF001
        chain1, digit1 = module._ENDGAME["1"]  # noqa: SLF001
        assert module._apply(0, chain0) == -255  # noqa: SLF001
        assert module._apply(0, chain1) == -257  # noqa: SLF001
        assert (digit0, digit1) == (48, 49)
        assert set(chain0 + chain1) <= {"s", "i", "m"}, "a p would lift the deep class"

    @pytest.mark.parametrize(
        ("lower", "upper"),
        [
            # Straddling zero already: no shift at all.
            ({-2: "0"}, {5: "1"}),
            # Both below zero: the upper class rises to zero.
            ({-30: "1", -20: "1"}, {-7: "0", -3: "0"}),
            # Both above zero: the lower class drops to minus one.
            ({4: "0"}, {9: "1", 11: "1"}),
            # At the edge of the workspace.
            ({-3003: "1"}, {3003: "0"}),
            # A wide upper class, every point wiped onto the same zero.
            ({-1: "0"}, {0: "1", 1: "1", 1500: "1", 3003: "1"}),
        ],
    )
    def test_a_threshold_state_prints_from_any_position(
        self, lower: dict[int, str], upper: dict[int, str]
    ) -> None:
        """Every point of the lower class deep, every upper point on one value.

        The state is replayed by ``_apply`` on each row through the emitted
        tail, the same model the emitter's own assertion uses, so this is
        the endgame checked from outside: whatever the extents, the lower
        class prints its digit and the upper class the other.
        """
        module = _module()
        groups = {}
        table = ""
        for value, cls in list(lower.items()) + list(upper.items()):
            groups[len(table)] = (value, cls)
            table += cls
        em = self.emitter(groups)
        em.finish()
        tail = "".join(em.body)
        assert tail.endswith("e")
        assert "m" * module._DEEP_DOUBLINGS in tail  # noqa: SLF001
        for row, (value, cls) in groups.items():
            out = module._apply(value, tail[:-1])  # noqa: SLF001
            if out > module._LIMIT:  # noqa: SLF001
                out = 0
            assert out & 0xFF == ord(cls), (row, value, cls, out)
        # The mirror holds one value per class, on the digits.
        assert {em.cls[key]: value % 256 for value, key in em.at.items()} == {
            "0": 48,
            "1": 49,
        }

    def test_a_single_class_is_erased_and_shifted(self) -> None:
        """One class: ``'`` zeroes every row, one shift lands the digit."""
        module = _module()
        em = self.emitter({0: (-40, "1"), 1: (17, "1"), 2: (2900, "1")})
        em.finish()
        tail = "".join(em.body)
        assert tail.startswith("'p")
        assert tail.endswith("pe")
        for value in (-40, 17, 2900):
            assert module._apply(value, tail[:-1]) == 49  # noqa: SLF001
        assert list(em.at) == [49]

    def test_a_state_that_is_not_a_threshold_is_refused(self) -> None:
        """Three runs cannot be printed by the endgame; the plan owes two."""
        em = self.emitter({0: (-4, "0"), 1: (-2, "1"), 2: (0, "0")})
        with pytest.raises(AssertionError, match="threshold"):
            em.finish()

    def test_two_runs_plan_as_nothing(self) -> None:
        """A threshold state is done before the first move, whatever its extents."""
        module = _module()
        state = module._fold_norm(  # noqa: SLF001
            [(0, 5, "0", frozenset(range(6))), (-6, 1, "1", frozenset({6, 7}))]
        )
        assert module._fold_plan(state) == []  # noqa: SLF001
        three = module._fold_norm(  # noqa: SLF001
            [
                (0, 0, "0", frozenset({0})),
                (-4, 0, "1", frozenset({1})),
                (-8, 0, "0", frozenset({2})),
            ]
        )
        assert module._fold_plan(three)  # noqa: SLF001

    @pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 8, 11])
    def test_symmetric_tables_are_dozens_of_characters_at_any_arity(
        self, n: int
    ) -> None:
        """``AND``, ``OR`` and majority open as two runs on the popcount ladder.

        So their programs are the ladder, the endgame and nothing else,
        and the size grows by the runs alone -- one character and a
        ``psp`` per input.  Executed on a sample of rows at each arity.
        """
        from esolangs.tools import parameterized

        module = _module()
        size = 2**n
        for table in (
            "0" * (size - 1) + "1",
            "0" + "1" * (size - 1),
            "".join("1" if bin(r).count("1") * 2 > n else "0" for r in range(size)),
        ):
            template = parameterized.pct_squared_minus_one(table)
            assert len(template) < 70 + 12 * n, (n, len(template))
            assert module.setters(template) == (_PAIR,) * n
            for row in itertools.islice(
                itertools.chain([0, size - 1], range(1, size, max(1, size // 5))), 8
            ):
                bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
                assert _run_pct(_instantiate(template, bits)) == table[row], (
                    table,
                    bits,
                )


class TestPctThresholdPlans:
    """Plans stop at a threshold state, and the ledger counts its runs."""

    #: Four points, alternating classes: two runs short of a threshold.
    STATE = (
        (0, 0, "0", frozenset({0})),
        (-4, 0, "1", frozenset({1})),
        (-8, 0, "0", frozenset({2})),
        (-12, 0, "1", frozenset({3})),
    )

    def test_the_ledger_counts_class_boundaries_incrementally(self) -> None:
        """``bounds`` is the run count less one, under inserts and removes."""
        from esolangs.tools.pct_fold_plan import _FoldLedger

        ledger = _FoldLedger.from_state(self.STATE)
        assert ledger.bounds == 3
        assert not ledger.is_threshold()
        ledger._remove(-4)  # noqa: SLF001
        assert ledger.bounds == 1  # 0, 0, 1 from the top: two boundaries gone
        assert ledger.is_threshold()
        ledger._insert(-6, 0, "1", [frozenset({9})])  # noqa: SLF001
        assert ledger.bounds == 3  # 0, 1, 0, 1 again
        ledger._insert(-2, 0, "0", [frozenset({8})])  # noqa: SLF001
        assert ledger.bounds == 3  # between a zero and a one: one boundary moved
        ledger._remove(-8)  # noqa: SLF001
        assert ledger.bounds == 1  # 0, 0, 1, 1: one boundary
        assert ledger.is_threshold()
        ledger._insert(-20, 3, "0", [frozenset({7})])  # noqa: SLF001
        assert ledger.bounds == 2
        assert not ledger.is_threshold()  # a spanned point is never done
        assert _FoldLedger.from_state(self.STATE[:1]).bounds == 0

    def test_a_skeleton_plan_is_cut_at_its_first_threshold(self) -> None:
        """The skeleton plans to two points; the plan stops two runs early."""
        module = _module()
        state = module._fold_norm(list(self.STATE))  # noqa: SLF001
        skeleton = module._fold_construct(state)  # noqa: SLF001
        plan = module._fold_plan(state)  # noqa: SLF001
        assert skeleton is not None
        assert plan is not None
        assert plan == skeleton[: len(plan)]
        assert len(plan) < len(skeleton)
        for op in plan:
            state = module._fold_step(state, op)  # noqa: SLF001
            assert state is not None
        classes = [cls for _, _, cls, _ in state]
        assert sum(a != b for a, b in itertools.pairwise(classes)) == 1
