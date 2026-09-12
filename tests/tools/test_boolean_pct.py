r"""Unit tests for the %^2^-1 boolean generator."""

import importlib
import itertools
import time

import pytest

from esolangs.tools import boolean


class TestParameterizedPctSquaredMinusOne:
    r"""Input-by-substitution boolean generator for %^2^-1."""

    def run_pct(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean.examples import _fill_pct_squared_minus_one

        return _fill_pct_squared_minus_one(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            # The two constant tables are.
            # and 1.0s against 0.04s for.
            # the fast run's one-second.
            pytest.param("00", 1, marks=pytest.mark.slow),  # constant zero.
            pytest.param("11", 1, marks=pytest.mark.slow),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR -- the function the wall.
            ("1001", 2),  # XNOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_pct(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    # Derives every table at that.
    # over the fast run's.
    # the cost is the count -- so.
    @pytest.mark.slow
    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to two inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.pct_squared_minus_one(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_pct(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_instantiations_share_a_length(self) -> None:
        r"""All four programs are the same length, so none leaks its inputs."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one("0110")
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, lengths

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    @pytest.mark.slow  # 5.3s: derives all sixteen.
    def test_programs_never_read_input(self) -> None:
        r"""No emitted program contains ``n``, the input command."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            template = parameterized.pct_squared_minus_one(format(table_int, "04b"))
            for a in (0, 1):
                for b in (0, 1):
                    assert "n" not in self.instantiate(template, [a, b])

    @pytest.mark.parametrize("n", [3, 4, 5, 6])
    def test_minterm_cascade_lifts_the_two_input_cap(self, n: int) -> None:
        r"""Single-minterm tables build at any arity, past the derived path's."""
        from esolangs.tools.boolean import parameterized

        for index in range(2**n):
            table = "".join("1" if i == index else "0" for i in range(2**n))
            template = parameterized.pct_squared_minus_one(table)
            for row in range(2**n):
                bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
                assert self.run_pct(self.instantiate(template, bits)) == table[row]

    def test_cascade_branches_are_equal_width(self) -> None:
        r"""No instantiation leaks its inputs through ``len()``."""
        from esolangs.tools.boolean import parameterized

        n = 4
        template = parameterized.pct_squared_minus_one("1" + "0" * (2**n - 1))
        widths = {
            len(
                self.instantiate(template, [(row >> (n - 1 - k)) & 1 for k in range(n)])
            )
            for row in range(2**n)
        }
        assert len(widths) == 1

    @pytest.mark.parametrize("n", [3, 4, 5])
    def test_cascade_builds_or_and_nand_by_complement(self, n: int) -> None:
        r"""``ips`` maps a 0/1 accumulator to ``1 - r``, so complements are."""
        from esolangs.tools.boolean import parameterized

        tables = {
            "and": "0" * (2**n - 1) + "1",
            "nand": "1" * (2**n - 1) + "0",
            "or": "0" + "1" * (2**n - 1),
            "nor": "1" + "0" * (2**n - 1),
        }
        for table in tables.values():
            template = parameterized.pct_squared_minus_one(table)
            for row in range(2**n):
                bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
                assert self.run_pct(self.instantiate(template, bits)) == table[row]

    def test_cascade_covers_every_subcube_at_three_inputs(self) -> None:
        r"""Every conjunction of literals builds, free inputs included."""
        from esolangs.tools.boolean.pct_squared_minus_one import _cascade

        # The cascade is asked directly.
        # which now falls back to the.
        # serves -- counting the.
        # constructions and no longer.
        built = 0
        for value in range(256):
            table = format(value, "08b")
            template = _cascade(table, 3)
            if template is None:
                continue
            built += 1
            for row in range(8):
                bits = [(row >> (2 - k)) & 1 for k in range(3)]
                assert self.run_pct(self.instantiate(template, bits)) == table[row]
        # The count is exactly ``2 *.
        # subcubes (each input is.
        # many complements; the overlap.
        # tables, the only subcubes.
        # constant tables do not.
        # rejects an empty ON-set.
        # caught rather than passing.
        assert built == 2 * 3**3 - 2 * 3 == 48

    # The cost is the three-input.
    # whole arity and cached --.
    # so it is the arity that is.
    @pytest.mark.slow
    def test_affine_path_builds_three_input_parity(self) -> None:
        r"""XOR3 builds, which no subcube is and the cascade refuses."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.pct_squared_minus_one import _cascade

        table = "01101001"
        assert _cascade(table, 3) is None, "parity is not a subcube"
        template = parameterized.pct_squared_minus_one(table)
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            assert self.run_pct(self.instantiate(template, bits)) == table[row]

    @pytest.mark.slow
    def test_affine_path_instantiations_share_a_length(self) -> None:
        r"""A composed-affine program leaks nothing through ``len()``."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one("01101001")
        lengths = {
            len(self.instantiate(template, [(row >> (2 - k)) & 1 for k in range(3)]))
            for row in range(8)
        }
        assert len(lengths) == 1, lengths

    @pytest.mark.slow
    def test_three_inputs_are_total(self) -> None:
        r"""All 256 three-input tables build, and every one of them runs."""
        from esolangs.tools.boolean import parameterized

        for value in range(256):
            table = format(value, "08b")
            # No ``except`` here: a refusal.
            template = parameterized.pct_squared_minus_one(table)
            lengths = set()
            for row in range(8):
                bits = [(row >> (2 - k)) & 1 for k in range(3)]
                program = self.instantiate(template, bits)
                lengths.add(len(program))
                assert self.run_pct(program) == table[row], (table, bits)
            # Both branches of every setter.
            # its inputs through ``len()``.
            assert len(lengths) == 1, (table, sorted(lengths))

    def test_deep_band_builds_four_input_parity(self) -> None:
        r"""Parity-4 builds and runs, which no earlier path reached."""
        from esolangs.tools.boolean import parameterized

        table = "0110100110010110"
        template = parameterized.pct_squared_minus_one(table)
        lengths = set()
        for row in range(16):
            bits = [(row >> (3 - k)) & 1 for k in range(4)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row], (table, bits)
        assert len(lengths) == 1, sorted(lengths)

    def test_deep_band_refuses_a_class_splitting_collision(self) -> None:
        r"""A weighting whose collision splits a class is refused, not served."""
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _deep_plan,
            _deep_values,
        )

        # Weights (1, 1) collide rows.
        # the same class, so the.
        collided = _deep_values(2, (1, 1), 0)
        assert collided[1] == collided[2]
        assert _deep_plan("0110", 2, collided) is not None
        # A table that disagrees on.
        # schedule can separate rows.
        # is 1 on row 10 and 0 on row.
        assert _deep_plan("0010", 2, collided) is None

    def test_deep_band_builds_symmetric_tables_at_five_inputs(self) -> None:
        r"""Symmetric tables build past four inputs on the deep band."""
        from esolangs.tools.boolean import parameterized

        majority = "".join("1" if bin(r).count("1") >= 3 else "0" for r in range(32))
        template = parameterized.pct_squared_minus_one(majority)
        lengths = set()
        for row in range(32):
            bits = [(row >> (4 - k)) & 1 for k in range(5)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == majority[row], (majority, bits)
        assert len(lengths) == 1, sorted(lengths)

    def test_fold_doubling_is_what_reorders(self) -> None:
        r"""The fold computes a table whose runs alternate four times."""
        from esolangs.tools.boolean.pct_squared_minus_one import _HEADER_END, _fold

        table = "00000101"
        template = _fold(table, 3)
        assert template is not None
        # The body, not the header: the.
        body = template.partition(_HEADER_END)[2]
        assert "m" in body, "the doubling never fired"
        lengths = set()
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row], (table, bits)
        assert len(lengths) == 1, sorted(lengths)

    @pytest.mark.slow  # a 19-run plan plus 32.
    def test_fold_closes_five_inputs(self) -> None:
        r"""A five-input table the deep band refuses computes on the fold."""
        from esolangs.tools.boolean.pct_squared_minus_one import _fold

        table = "11011111100100101001101110111000"
        template = _fold(table, 5)
        assert template is not None
        lengths = set()
        for row in range(32):
            bits = [(row >> (4 - k)) & 1 for k in range(5)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row], (table, bits)
        assert len(lengths) == 1, sorted(lengths)

    @pytest.mark.slow  # a 21-point plan plus 32.
    def test_a_wide_state_plans_and_executes(self) -> None:
        r"""A 21-point table plans in milliseconds and computes every row."""
        from esolangs.tools.boolean.pct_squared_minus_one import _fold

        table = "01010101000101111111010101011110"
        template = _fold(table, 5)
        assert template is not None
        lengths = set()
        for row in range(32):
            bits = [(row >> (4 - k)) & 1 for k in range(5)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row], (table, bits)
        assert len(lengths) == 1, sorted(lengths)

    @pytest.mark.parametrize("bit", ["0", "1"])
    def test_fold_finishes_a_single_class(self, bit: str) -> None:
        r"""A constant table leaves one point, which ``finish`` aligns alone."""
        from esolangs.tools.boolean.pct_squared_minus_one import _fold

        table = bit * 8
        template = _fold(table, 3)
        assert template is not None
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            assert self.run_pct(self.instantiate(template, bits)) == bit

    @pytest.mark.slow  # three arities' worth of.
    @pytest.mark.parametrize(
        ("table", "reaches"),
        [
            # A weighting whose setter.
            # the pair `_deep_setters`.
            # nothing, which every other.
            ("1100110001110111", "an empty setter pair"),
            # The deep band's own refusal,.
            # this table exhausts the.
            # picks it up.
            ("1101000011010101", "the deep band's refusal"),
            # The fold's narrow-gap.
            # within 258 of each other, so.
            # congruence directly and parks.
            # to reopen the gap first.
            ("00001111101010010010001011101101", "finish's narrow-gap reopen"),
        ],
    )
    def test_tables_that_reach_the_rarer_arms(self, table: str, reaches: str) -> None:
        r"""Witnesses for arms no other table in the suite takes."""
        from esolangs.tools.boolean import parameterized

        n = (len(table) - 1).bit_length()
        template = parameterized.pct_squared_minus_one(table)
        lengths = set()
        for row in range(2**n):
            bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row], (reaches, table, bits)
        assert len(lengths) == 1, sorted(lengths)

    def test_dispatch_falls_through_to_the_fold(self) -> None:
        r"""The public entry reaches the fold, not just ``_fold`` called."""
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _deep_band,
            _fold,
            pct_squared_minus_one,
        )

        table = "11011111100100101001101110111000"
        assert _deep_band(table, 5) is None  # the arm above must still.
        assert pct_squared_minus_one(table) == _fold(table, 5)

    def test_deep_band_refuses_past_its_span_budget_without_enumerating(
        self,
    ) -> None:
        r"""Past eleven inputs no weighting fits, and the refusal is instant."""
        from esolangs.tools.boolean.pct_squared_minus_one import _deep_band

        parity = "".join(str(bin(r).count("1") & 1) for r in range(2**12))
        assert _deep_band(parity, 12) is None

    @pytest.mark.slow  # derives the whole three-input.
    def test_affine_reach_is_exactly_characterized(self) -> None:
        r"""The composed-affine path's 86/256 is a predicate, not a measurement."""
        from esolangs.tools.boolean.pct_squared_minus_one import _affine

        def complement(bits: str) -> str:
            return "".join("1" if c == "0" else "0" for c in bits)

        def cofactor(table: str, index: int, value: int) -> str:
            return "".join(
                table[row] for row in range(8) if (row >> (2 - index)) & 1 == value
            )

        def predicted(table: str) -> bool:
            if len(set(table)) == 1:
                return False
            low, high = cofactor(table, 2, 0), cofactor(table, 2, 1)
            return (
                low == high
                or complement(low) == high
                or len(set(low)) == 1
                or len(set(high)) == 1
            )

        reached = {
            table
            for table in (format(v, "08b") for v in range(256))
            if _affine(table, 3) is not None
        }
        assert reached == {
            format(v, "08b") for v in range(256) if predicted(format(v, "08b"))
        }
        assert len(reached) == 86

    def test_affine_builds_the_table_the_enumeration_missed(self) -> None:
        r"""``x0 ^ x2`` builds, and short, which the old enumeration refused."""
        from esolangs.tools.boolean.pct_squared_minus_one import _affine

        for table in ("01011010", "10100101"):
            template = _affine(table, 3)
            assert template is not None, table
            lengths = set()
            for row in range(8):
                bits = [(row >> (2 - k)) & 1 for k in range(3)]
                program = self.instantiate(template, bits)
                lengths.add(len(program))
                assert self.run_pct(program) == table[row], (table, bits)
            assert len(lengths) == 1, sorted(lengths)
            assert len(template) < 100, len(template)

    def test_affine_declines_outside_three_inputs(self) -> None:
        r"""The construction serves the arity the dispatch calls it for."""
        from esolangs.tools.boolean.pct_squared_minus_one import _affine

        assert _affine("0110", 2) is None
        assert _affine("0110100110010110", 4) is None

    def test_cascade_reach_is_exactly_the_subcubes(self) -> None:
        r"""The cascade builds exactly the tables that are a subcube or one's."""
        from esolangs.tools.boolean.pct_squared_minus_one import _cascade

        def is_subcube(table: str) -> bool:
            ones = [row for row in range(8) if table[row] == "1"]
            if not ones:
                return True
            fixed = [
                k for k in range(3) if len({(r >> (2 - k)) & 1 for r in ones}) == 1
            ]
            return len(ones) == 2 ** (3 - len(fixed))

        def predicted(table: str) -> bool:
            flipped = "".join("1" if c == "0" else "0" for c in table)
            return is_subcube(table) or is_subcube(flipped)

        reached = {t for t in (format(v, "08b") for v in range(256)) if _cascade(t, 3)}
        assert reached == {
            format(v, "08b") for v in range(256) if predicted(format(v, "08b"))
        }
        assert len(reached) == 48

    @pytest.mark.slow  # every weighting inside the.
    def test_a_legal_weighting_always_schedules(self) -> None:
        r"""Legality decides the deep band; the schedule then follows."""
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _cross_class_diffs,
            _deep_plan,
            _deep_values,
            _deep_weightings,
            _weighting_is_legal,
        )

        checked = 0
        for value in range(0, 256, 17):
            table = format(value, "08b")
            diffs = _cross_class_diffs(table, 3)
            for units in _deep_weightings(3):
                for mask in range(8):
                    if not _weighting_is_legal(units, mask, diffs):
                        continue
                    checked += 1
                    values = _deep_values(3, units, mask)
                    assert _deep_plan(table, 3, values) is not None, (
                        table,
                        units,
                        mask,
                    )
        assert checked > 3000, checked

    def test_span_budget_is_what_rejects_a_legal_weighting(self) -> None:
        r"""The dropped weightings are dropped for a stated reason."""
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _BAND_UNIT,
            _LIMIT,
            _deep_weightings,
        )

        for units in _deep_weightings(4):
            assert sum(units) * _BAND_UNIT <= _LIMIT, units
        assert max(sum(u) for u in _deep_weightings(4)) == _LIMIT // _BAND_UNIT

    def test_deep_band_is_screened_above_four_inputs(self) -> None:
        r"""Asymmetric five-input tables are screened, symmetric ones built."""
        from esolangs.tools.boolean.pct_squared_minus_one import _deep_band

        parity = "".join(str(bin(r).count("1") % 2) for r in range(32))
        majority = "".join("1" if bin(r).count("1") >= 3 else "0" for r in range(32))
        assert _deep_band(parity, 5) is not None
        assert _deep_band(majority, 5) is not None
        # One flipped row breaks the.
        asymmetric = list(parity)
        asymmetric[7] = "0" if asymmetric[7] == "1" else "1"
        assert _deep_band("".join(asymmetric), 5) is None

    @pytest.mark.slow  # 8.3s: the ladder build plus.
    def test_ladder_builds_majority_three(self) -> None:
        r"""Majority-3 builds, which no affine composition of setters reaches."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.pct_squared_minus_one import _affine, _cascade

        table = "00010111"
        # The other two paths really do.
        assert _cascade(table, 3) is None
        assert _affine(table, 3) is None
        template = parameterized.pct_squared_minus_one(table)
        lengths = set()
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row]
        # Both branches of every setter.
        # inputs through ``len()``.
        assert len(lengths) == 1, lengths

    @pytest.mark.slow  # the whole setter grid,.
    def test_every_branch_pair_shares_a_spelling_width(self) -> None:
        r"""No setter in the grid needs the "no shared width" fallback."""
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _WIDE_A_VALS,
            _WIDE_B_VALS,
            _spellings_by_width,
        )

        grid = [(a, b) for a in _WIDE_A_VALS for b in _WIDE_B_VALS]
        for zero in grid:
            zero_widths = _spellings_by_width(*zero)
            for one in grid:
                shared = set(zero_widths) & set(_spellings_by_width(*one))
                assert shared, (zero, one)

    def test_the_wide_multipliers_are_the_command_closure(self) -> None:
        r"""``_WIDE_A_VALS`` is generated, and the generator is the language."""
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _WIDE_A_LIMIT,
            _WIDE_A_VALS,
            _wide_a_vals,
        )

        assert _WIDE_A_VALS == (0, 1, -1, 2, -2, 4, -4)
        assert _wide_a_vals(_WIDE_A_LIMIT) == _WIDE_A_VALS

        # The closure itself: reachable.
        reach = {0, 1}
        for _ in range(_WIDE_A_LIMIT.bit_length()):
            reach |= {2 * v for v in reach} | {-v for v in reach}
        assert set(_WIDE_A_VALS) == {v for v in reach if abs(v) <= _WIDE_A_LIMIT}

        # Widening is a knob, not a.
        assert _wide_a_vals(8) == (0, 1, -1, 2, -2, 4, -4, 8, -8)

    def test_built_spell_bases_match_the_frozen_witnesses(self) -> None:
        r"""The fold reproduces the enumeration's witnesses exactly."""
        frozen: dict[tuple[int, int], tuple[str | None, str | None]] = {
            (-4, -12): ("pimm", "mpiim"),
            (-4, -11): ("mpssmi", "psmmi"),
            (-4, -10): ("spimim", "mpsim"),
            (-4, -9): ("mmpiii", "mpimi"),
            (-4, -8): ("psmm", "mpssm"),
            (-4, -7): ("spimmi", "mpsmi"),
            (-4, -6): ("mpim", "mmpii"),
            (-4, -5): ("mspimi", "mmpsi"),
            (-4, -4): ("mpsm", "spimm"),
            (-4, -3): ("mmpi", "smpssmi"),
            (-4, -2): ("mmps", "mspim"),
            (-4, -1): ("smpimi", "mmspi"),
            (-4, 0): ("smpssm", "mmp"),
            (-4, 1): ("smpsmi", "msmpi"),
            (-4, 2): ("mmsp", "smpim"),
            (-4, 3): ("mmip", "mimpi"),
            (-4, 4): ("msmp", "smpsm"),
            (-4, 5): ("impsmi", "smmpi"),
            (-4, 6): ("mimp", "smmps"),
            (-4, 7): ("smmspi", "msmip"),
            (-4, 8): ("smmp", "impsm"),
            (-4, 9): ("smsmpi", "immpi"),
            (-4, 10): ("ssmpim", "smmsp"),
            (-4, 11): ("smimpi", "smmip"),
            (-4, 12): ("immp", "smsmp"),
            (-2, -12): ("piim", "psssm"),
            (-2, -11): ("spiimi", "pssmi"),
            (-2, -10): ("psim", "pssms"),
            (-2, -9): ("pimi", "mpiii"),
            (-2, -8): ("pssm", "spiim"),
            (-2, -7): ("psmi", "mpssi"),
            (-2, -6): ("mpii", "pim"),
            (-2, -5): ("mpsi", "spimi"),
            (-2, -4): ("mpss", "psm"),
            (-2, -3): ("smpssi", "mpi"),
            (-2, -2): ("spim", "mps"),
            (-2, -1): ("mspi", "smpsi"),
            (-2, 0): ("mp", "smpss"),
            (-2, 1): ("smpi", "impsi"),
            (-2, 2): ("smps", "msp"),
            (-2, 3): ("impi", "mip"),
            (-2, 4): ("imps", "smp"),
            (-2, 5): ("msip", "ssmpi"),
            (-2, 6): ("smsp", "imp"),
            (-2, 7): ("smip", "simpi"),
            (-2, 8): ("ssmp", "simps"),
            (-2, 9): ("imip", "smsip"),
            (-2, 10): ("simp", "ssmsp"),
            (-2, 11): ("ssimpi", "ssmip"),
            (-2, 12): ("iimp", "sssmp"),
            (-1, -12): ("psssii", "piiii"),
            (-1, -11): ("pssssi", "psiii"),
            (-1, -10): ("spiiii", "pssii"),
            (-1, -9): ("piii", "psssi"),
            (-1, -8): ("psii", "pssss"),
            (-1, -7): ("pssi", "spiii"),
            (-1, -6): ("psss", "pii"),
            (-1, -5): ("sspiii", "psi"),
            (-1, -4): ("spii", "pss"),
            (-1, -3): ("pi", "ipsss"),
            (-1, -2): ("ps", "sspii"),
            (-1, -1): ("ipss", "spi"),
            (-1, 0): ("ssspii", "p"),
            (-1, 1): ("sspi", "ips"),
            (-1, 2): ("sp", "iipss"),
            (-1, 3): ("ip", "ssspi"),
            (-1, 4): ("iips", "ssp"),
            (-1, 5): ("sssspi", "sip"),
            (-1, 6): ("sssp", "iip"),
            (-1, 7): ("ssip", "iiips"),
            (-1, 8): ("siip", "ssssp"),
            (-1, 9): ("iiip", "sssip"),
            (-1, 10): ("sssssp", "ssiip"),
            (-1, 11): ("ssssip", "siiip"),
            (-1, 12): ("sssiip", "iiiip"),
            (0, -12): ("'iim", None),
            (0, -11): ("'ssmi", None),
            (0, -10): ("'sim", None),
            (0, -9): ("'iii", None),
            (0, -8): ("'ssm", None),
            (0, -7): ("'ssi", None),
            (0, -6): ("'ii", None),
            (0, -5): ("'si", None),
            (0, -4): ("'ss", None),
            (0, -3): ("'i", None),
            (0, -2): ("'s", None),
            (0, -1): ("'spi", None),
            (0, 0): ("'", None),
            (0, 1): ("'ips", None),
            (0, 2): ("'sp", None),
            (0, 3): ("'ip", None),
            (0, 4): ("'ssp", None),
            (0, 5): ("'sip", None),
            (0, 6): ("'iip", None),
            (0, 7): ("'ssip", None),
            (0, 8): ("'ssmp", None),
            (0, 9): ("'iiip", None),
            (0, 10): ("'simp", None),
            (0, 11): ("'ssmip", None),
            (0, 12): ("'iimp", None),
            (1, -12): ("iiii", "sssii"),
            (1, -11): ("siii", "ssssi"),
            (1, -10): ("ssii", "sssss"),
            (1, -9): ("sssi", "iii"),
            (1, -8): ("ssss", "sii"),
            (1, -7): ("iiipsp", "ssi"),
            (1, -6): ("ii", "sss"),
            (1, -5): ("si", "sssspip"),
            (1, -4): ("ss", "iipsp"),
            (1, -3): ("ssspip", "i"),
            (1, -2): ("iipssp", "s"),
            (1, -1): ("ipsp", "sspip"),
            (1, 0): ("", "ssspiip"),
            (1, 1): ("spip", "ipssp"),
            (1, 2): ("sspiip", "psp"),
            (1, 3): ("ipsssp", "pip"),
            (1, 4): ("pssp", "spiip"),
            (1, 5): ("psip", "sspiiip"),
            (1, 6): ("piip", "psssp"),
            (1, 7): ("spiiip", "pssip"),
            (1, 8): ("pssssp", "psiip"),
            (1, 9): ("psssip", "piiip"),
            (1, 10): ("pssiip", "spiiiip"),
            (1, 11): ("psiiip", "pssssip"),
            (1, 12): ("piiiip", "psssiip"),
            (2, -12): ("sssm", "iim"),
            (2, -11): ("ssmi", "smssi"),
            (2, -10): ("ssms", "sim"),
            (2, -9): ("smsi", "imi"),
            (2, -8): ("smss", "ssm"),
            (2, -7): ("mssi", "smi"),
            (2, -6): ("im", "sms"),
            (2, -5): ("ssmpip", "msi"),
            (2, -4): ("sm", "mss"),
            (2, -3): ("mi", "impip"),
            (2, -2): ("ms", "smpsp"),
            (2, -1): ("spimpi", "smpip"),
            (2, 0): ("smpssp", "m"),
            (2, 1): ("smpsip", "mspip"),
            (2, 2): ("mpsp", "spimp"),
            (2, 3): ("mpip", "pimpi"),
            (2, 4): ("psmp", "mpssp"),
            (2, 5): ("spimip", "mpsip"),
            (2, 6): ("pimp", "mpiip"),
            (2, 7): ("mpssip", "psmip"),
            (2, 8): ("spiimp", "pssmp"),
            (2, 9): ("mpiiip", "pimip"),
            (2, 10): ("pssmsp", "psimp"),
            (2, 11): ("pssmip", "spiimip"),
            (2, 12): ("psssmp", "piimp"),
            (4, -12): ("smsm", "imm"),
            (4, -11): ("smmi", "mssmi"),
            (4, -10): ("smms", "mssms"),
            (4, -9): ("mimi", "msmsi"),
            (4, -8): ("mssm", "smm"),
            (4, -7): ("msmi", "mmssi"),
            (4, -6): ("msms", "mim"),
            (4, -5): ("mmsi", "smpimpi"),
            (4, -4): ("mmss", "msm"),
            (4, -3): ("mimpip", "mmi"),
            (4, -2): ("smpimp", "mms"),
            (4, -1): ("msmpip", "smpsmip"),
            (4, 0): ("mm", "smpssmp"),
            (4, 1): ("mmspip", "smpimip"),
            (4, 2): ("mspimp", "mmpsp"),
            (4, 3): ("mpimpi", "mmpip"),
            (4, 4): ("spimmp", "mpsmp"),
            (4, 5): ("mmpsip", "mspimip"),
            (4, 6): ("mmpiip", "mpimp"),
            (4, 7): ("mpsmip", "spimmip"),
            (4, 8): ("mpssmp", "psmmp"),
            (4, 9): ("mpimip", "mmpiiip"),
            (4, 10): ("mpsimp", "spimimp"),
            (4, 11): ("psmmip", "mpssmip"),
            (4, 12): ("mpiimp", "pimmp"),
        }
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        assert module._spell_bases() == frozen  # noqa: SLF001

    def test_every_derived_spelling_behaves_at_every_width(self) -> None:
        r"""Each width's string realises its map, padding included."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        for a in module._WIDE_A_VALS:  # noqa: SLF001
            for b in module._WIDE_B_VALS:  # noqa: SLF001
                for width, code in module._spellings_by_width(  # noqa: SLF001
                    a, b
                ).items():
                    assert len(code) == width, (a, b, width, code)
                    assert all(
                        module._apply(value, code) == a * value + b  # noqa: SLF001
                        for value in module._SPELL_WINDOW  # noqa: SLF001
                    ), (a, b, width, code)

    def test_slope_zero_forgets_the_accumulator(self) -> None:
        r"""``'`` is the constant map: it discards whatever it was given."""
        from esolangs.tools.boolean.pct_squared_minus_one import _affine_code, _apply

        code = _affine_code(0, 5)
        assert code is not None
        assert "'" in code, "a constant map has to reset the accumulator"
        assert _apply(7, code) == 5
        assert _apply(0, code) == 5

        # Only four multipliers have a.
        assert _affine_code(3, 0) is None
        # The offset needs one too: 1.
        assert _affine_code(1, -1) is None

    def test_the_model_mirrors_every_command_the_language_has(self) -> None:
        r"""``_apply`` stands in for the interpreter, so it owes it every op."""
        from esolangs.tools.boolean.pct_squared_minus_one import _LIMIT, _apply

        assert _apply(10, "s") == 8  # s subtracts 2.
        assert _apply(10, "i") == 7  # i subtracts 3.
        assert _apply(10, "m") == 20  # m doubles.
        assert _apply(10, "p") == -10  # p negates.
        assert _apply(10, "'") == 0  # ' erases.

        # The reset fires *before* a.
        # is zeroed and the command.
        assert _apply(_LIMIT + 1, "s") == -2
        assert _apply(_LIMIT, "s") == _LIMIT - 2, "at the limit nothing resets"

        # The model covers the five.
        # language's others.
        # accumulator alone here,.
        # does not recognize does.
        # lets a tail be scored without.
        assert _apply(10, "l") == 10
        assert _apply(10, "x") == 10
        assert _apply(10, "sxs") == 6, "an unmodelled command interrupts nothing"

    def test_a_tail_is_not_always_available(self) -> None:
        r"""Not every pair of class values can be printed apart."""
        from esolangs.tools.boolean.pct_squared_minus_one import _tail_for

        assert _tail_for(-5, -5) is None
        assert _tail_for(1, 0) is not None, "the trivial pair still works"
        # Two classes further apart.
        # translation moves both.
        assert _tail_for(5, 0) is None

    def test_a_table_no_candidate_realizes_is_reported(self) -> None:
        r"""With every parameter set rejected the derivation reports nothing."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        from esolangs.tools.boolean.pct_squared_minus_one import _derive

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_solution", lambda *_a, **_k: None)
            assert _derive("0110") is None


class TestPctSquaredHelpers:
    r"""The %^2^-1 spelling helpers, at the inputs their guards exist for."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_sub_of_width_rejects_an_unreachable_split(self) -> None:
        r"""A width too narrow to spell ``k`` has no ``i``/``s`` split."""
        assert self.module()._sub_of_width(1, 1) is None  # noqa: SLF001

    @pytest.mark.parametrize("name", ["_even_width_for"])
    def test_zero_needs_no_width(self, name: str) -> None:
        r"""Subtracting nothing is width zero, not a search."""
        assert getattr(self.module(), name)(0) == 0

    @pytest.mark.parametrize("name", ["_even_width_for"])
    @pytest.mark.parametrize("k", [1, 2, 3, 7])
    def test_unspellable_weights_return_none(self, name: str, k: int) -> None:
        r"""Some weights have no even-width spelling at all."""
        assert getattr(self.module(), name)(k) is None

    @pytest.mark.parametrize("name", ["_even_width_for"])
    def test_odd_starting_width_is_bumped_even(self, name: str) -> None:
        r"""``k == 8`` starts the scan at an odd width, so it is bumped."""
        width = getattr(self.module(), name)(8)
        assert width is not None
        assert width % 2 == 0

    def test_a_ladder_refuses_an_unspellable_base(self) -> None:
        r"""The lead is spelled first, so its width decides before any weight."""
        assert self.module()._ladder_setters((12,), 7) is None  # noqa: SLF001

    def test_a_ladder_refuses_an_unspellable_weight(self) -> None:
        r"""One bad weight refuses the ladder even under a legal lead."""
        assert self.module()._ladder_setters((7,), 12) is None  # noqa: SLF001

    def test_a_ladder_spells_both_branches_at_one_width(self) -> None:
        r"""A legal ladder holds and subtracts at the same length."""
        got = self.module()._ladder_setters((12,), 12)  # noqa: SLF001
        assert got is not None
        setters, lead = got
        hold, code = setters[0]
        assert len(hold) == len(code)
        assert lead == code

    def test_every_tabulated_ladder_entry_computes_its_split(self) -> None:
        r"""Each built ladder entry is checked by arithmetic, not trust."""
        module = self.module()
        for table, (index, suffix) in module._ladder_built().items():  # noqa: SLF001
            weights, base = module._LADDERS[index]  # noqa: SLF001
            spelled = module._ladder_setters(weights, base)  # noqa: SLF001
            assert spelled is not None
            setters, lead = spelled
            vec = module._ladder_vector(setters, lead, 3)  # noqa: SLF001
            for row, want in enumerate(table):
                got = module._apply(vec[row], suffix)  # noqa: SLF001
                assert got == int(want), (table, row)

    def test_ladder_gadgets_match_frozen_spellings(self) -> None:
        r"""The gadget rule reproduces the five searched spellings, byte for."""
        module = self.module()
        assert module._LADDER_GADGETS == (  # noqa: SLF001
            "pspmsmipsp",
            "mpspmipsp",
            "smpspmipsp",
            "mmpspmipsp",
            "pspmimmipsp",
        )

    def test_the_move_algebra_refuses_what_it_cannot_place(self) -> None:
        r"""Each refusal in ``_fold_step`` is a placement the window forbids."""
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001
        double = ("m", 0, 0, frozenset())

        # A doubling has to leave the.
        too_wide = (
            (limit, 0, "a", frozenset({0})),
            (-limit, 0, "a", frozenset({1})),
        )
        assert fold_step(too_wide, double) is None

        # A single point at the origin.
        # the same guard's lower bound.
        flat = ((0, 0, "a", frozenset({0})),)
        assert fold_step(flat, double) is None

        # A state that does fit.
        # top at 0, so what the scaling.
        fits = ((10, 0, "a", frozenset({0})), (0, 0, "a", frozenset({1})))
        doubled = fold_step(fits, double)
        assert doubled is not None
        positions = sorted(p for p, _, _, _ in doubled)
        assert positions[-1] - positions[0] == 20

        # The everything-wipe merges.
        # only once a single class is.
        all_wipe = ("d", 2, limit + 1, frozenset())
        two_classes = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "b", frozenset({1})),
        )
        assert fold_step(two_classes, all_wipe) is None

        one_class = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "a", frozenset({1})),
        )
        assert fold_step(one_class, all_wipe) == ((0, 0, "a", frozenset({0, 1})),)

    def test_a_rise_relocates_survivors_above_the_victims(self) -> None:
        r"""``u`` mirrors ``d``: the survivors move relative to the victim."""
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001
        clean_amount = module._fold_clean_amount  # noqa: SLF001

        state = (
            (0, 0, "a", frozenset({0})),
            (100, 0, "a", frozenset({1})),
            (300, 0, "a", frozenset({2})),
        )
        for kind in ("u", "d"):
            amount = clean_amount(state, kind, 1)
            assert amount is not None, kind
            moved = fold_step(state, (kind, 1, amount, frozenset()))
            assert moved is not None, kind
            # One group is wiped onto the.
            assert len(moved) == 3, kind
            assert any(p == 0 for p, _, _, _ in moved), kind
            # Every id is still accounted.
            assert {x for _, _, _, ids in moved for x in ids} == {0, 1, 2}, kind

    def test_a_wipe_whose_survivors_will_not_fit_is_refused(self) -> None:
        r"""The span is re-checked *after* the relocation, not only before it."""
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001

        positions = ((0, 10, 20), ("a", "a", "a"))
        wide = (
            (0, 6000, "a", frozenset({0})),
            (10, 0, "a", frozenset({1})),
            (20, 0, "a", frozenset({2})),
        )
        assert fold_step(wide, ("u", 1, 3004, frozenset())) is None

        # Same geometry, ordinary.
        narrow = tuple(
            (p, 0, c, frozenset({i}))
            for i, (p, c) in enumerate(zip(*positions, strict=True))
        )
        assert fold_step(narrow, ("u", 1, 3004, frozenset())) is not None

    def test_a_clean_amount_needs_a_frame_to_land_in(self) -> None:
        r"""With no room to relocate into, there is no amount to return."""
        module = self.module()
        clean_amount = module._fold_clean_amount  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001

        assert clean_amount(((0, 0, "a", frozenset({0})),), "d", 1) is None

        spread = ((10, 0, "a", frozenset({0})), (0, 0, "b", frozenset({1})))
        for kind in ("d", "u"):
            assert clean_amount(spread, kind, 1) == limit + 1

    def test_a_reduction_gives_up_when_its_own_move_is_refused(self) -> None:
        r"""The rules can name a move the algebra then rejects, and that ends."""
        module = self.module()
        fold_reduce = module._fold_reduce  # noqa: SLF001
        fold_rule_move = module._fold_rule_move  # noqa: SLF001
        fold_step = module._fold_step  # noqa: SLF001
        fold_done = module._fold_done  # noqa: SLF001

        state = (
            (-40, 6000, "a", frozenset({0})),
            (-33, 2000, "b", frozenset({1})),
            (-26, 0, "a", frozenset({2})),
        )
        # The state is unfinished and.
        assert fold_done(state) is False
        move = fold_rule_move(state)
        assert move is not None
        # .
        assert fold_step(state, move) is None
        assert fold_reduce(state, fold_done, budget=5) is None

    def test_a_reduction_gives_up_when_no_move_applies(self) -> None:
        r"""``_fold_reduce`` returns ``None`` rather than an unfinished plan."""
        module = self.module()
        fold_reduce = module._fold_reduce  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001

        never_done = ((10, 0, "a", frozenset({0})), (0, 0, "b", frozenset({1})))
        assert fold_reduce(never_done, lambda _state: False, budget=3) is None

        too_wide = (
            (limit, 0, "a", frozenset({0})),
            (-limit, 0, "a", frozenset({1})),
        )
        assert fold_reduce(too_wide, lambda _state: False, budget=3) is None

    def test_the_all_wipe_candidate_needs_one_class_and_something_to_move(
        self,
    ) -> None:
        r"""``_fold_moves`` offers the everything-wipe only where it is legal."""
        module = self.module()
        fold_moves = module._fold_moves  # noqa: SLF001

        def kinds(state: object) -> list[tuple[str, int]]:
            return [(m[0], m[1]) for m in fold_moves(state)]

        one_class = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "a", frozenset({1})),
        )
        # k == len(state) is the.
        assert ("d", 2) in kinds(one_class)

        two_classes = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "b", frozenset({1})),
        )
        assert ("d", 2) not in kinds(two_classes)

        # Already collapsed: nothing to.
        assert kinds(((0, 0, "a", frozenset({0})),)) == []

    def test_sub_units_borrows_an_i_back_to_pay_a_remainder_of_one(self) -> None:
        r"""A remainder of 1 cannot be spelled directly, so a whole ``i`` is."""
        module = self.module()
        sub_units = module._sub_units  # noqa: SLF001

        # Exact multiples of 3: all i,.
        assert sub_units(3) == "i"
        assert sub_units(9) == "iii"
        # Remainder 2: one trailing s.
        assert sub_units(2) == "s"
        assert sub_units(5) == "is"
        # Remainder 1: borrow an i.
        assert sub_units(4) == "ss"
        assert sub_units(7) == "iss"
        assert sub_units(10) == "iiss"

        # Whatever the arm, the.
        # and no other spelling of the.
        for units in range(2, 40):
            spelled = sub_units(units)
            assert spelled.count("i") * 3 + spelled.count("s") * 2 == units, units
            best = min(
                (
                    threes + twos
                    for threes in range(units // 3 + 1)
                    for twos in range(units // 2 + 1)
                    if threes * 3 + twos * 2 == units
                ),
                default=None,
            )
            assert len(spelled) == best, units

    def test_a_ladder_cut_that_overshoots_backs_the_doubling_off(self) -> None:
        r"""When the largest power overshoots the cut, ``j`` steps down one."""
        module = self.module()
        ladder_gadget = module._ladder_gadget  # noqa: SLF001

        def chosen_j(cut: int) -> tuple[int, bool]:
            r"""Return the j the gadget settles on, and whether it backed off."""
            j = (3004 // cut).bit_length() - 1
            remainder = -(-3004 // (1 << j)) - cut
            if remainder < 0 or remainder % 2 != 0:
                return j - 1, True
            return j, False

        # The back-off is the common.
        assert sum(chosen_j(cut)[1] for cut in range(1, 3005)) > 1000

        # A slope has to be a whole.
        # so it is picked from that j.
        backed_off = ladder_gadget(1, 2 << chosen_j(1)[0])
        assert chosen_j(1)[1] is True
        assert "psp" in backed_off
        assert backed_off.endswith("ipsp")

        # A cut that does not overshoot.
        clean_cut = next(cut for cut in range(1, 3005) if not chosen_j(cut)[1])
        clean = ladder_gadget(clean_cut, 2 << chosen_j(clean_cut)[0])
        assert "psp" in clean
        assert clean.endswith("ipsp")

    def test_built_ladder_matches_the_frozen_witnesses(self) -> None:
        r"""The fold reproduces the table it replaced, entry for entry."""
        frozen = {
            "00010011": (0, "mpspmipspsl"),
            "11101100": (0, "mpspmipspipl"),
            "00110111": (0, "smpspmipspsl"),
            "11001000": (0, "smpspmipspipl"),
            "00000111": (1, "mpspmipspsl"),
            "11111000": (1, "mpspmipspipl"),
            "00011111": (1, "smpspmipspsl"),
            "11100000": (1, "smpspmipspipl"),
            "00000001": (2, "mpspmipspsl"),
            "11111110": (2, "mpspmipspipl"),
            "00010111": (2, "smpspmipspsl"),
            "11101000": (2, "smpspmipspipl"),
            "11111011": (3, "mmpspmipspsl"),
            "00000100": (3, "mmpspmipspipl"),
            "01111011": (3, "pspmimmipspsl"),
            "10000100": (3, "pspmimmipspipl"),
            "01011011": (4, "pspmimmipspsl"),
            "10100100": (4, "pspmimmipspipl"),
            "00001011": (5, "pspmimmipspsl"),
            "11110100": (5, "pspmimmipspipl"),
            "00011011": (6, "pspmsmipspsl"),
            "11100100": (6, "pspmsmipspipl"),
            "00111011": (7, "pspmimmipspsl"),
            "11000100": (7, "pspmimmipspipl"),
        }
        module = self.module()
        built = module._ladder_built()  # noqa: SLF001
        assert frozen.keys() <= built.keys()
        assert set(built) - set(frozen) == {"00000000", "11111111"}
        for table, witness in frozen.items():
            index, suffix = built[table]
            weights, base = module._LADDERS[index]  # noqa: SLF001
            spelled = module._ladder_setters(weights, base)  # noqa: SLF001
            assert spelled is not None
            setters, lead = spelled
            vector = module._ladder_vector(setters, lead, 3)  # noqa: SLF001
            for row, want in enumerate(table):
                got = module._apply(vector[row], suffix)  # noqa: SLF001
                assert got == int(want), (table, row)
            if (index, suffix) != witness:
                # Two tables are reached by a.
                # harvest picked.
                # emitted: every earlier path.
                # characters, so the ladder is.
                assert module.pct_squared_minus_one(table) != module._ladder(  # noqa: SLF001
                    table, 3
                )

    def test_built_fold_skeletons_match_the_mined_plans(self) -> None:
        r"""The peel/park/close rule reproduces the mined plans exactly."""
        mined = {
            (2, 0, 0): (("u", 1, "cmax"),),
            (2, 0, 1): (("d", 1, "cmax"),),
            (2, 1, 1): (("d", 1, "cmax"), ("d", 1, "cmax")),
            (3, 0, 0): (("d", 1, "cmax"), ("u", 2, "cmax")),
            (3, 1, 1): (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax")),
            (4, 0, 0): (
                ("d", 1, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "cmax"),
                ("u", 1, "land2"),
                ("u", 2, "cmax"),
            ),
            (4, 0, 1): (
                ("u", 1, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "land1"),
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
            ),
            (4, 1, 1): (
                ("d", 1, "cmax"),
                ("d", 1, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "cmax"),
                ("d", 1, "land2"),
                ("d", 2, "cmax"),
            ),
            (5, 0, 0): (
                ("d", 1, "cmax"),
                ("u", 2, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "land1"),
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
            ),
            (5, 0, 1): (
                ("d", 1, "cmax"),
                ("u", 2, "cmin"),
                ("m", 0, "m"),
                ("d", 1, "land1"),
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
            ),
            (5, 1, 0): (
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
                ("u", 1, "cmin"),
                ("m", 0, "m"),
                ("u", 1, "cmax"),
                ("u", 1, "land2"),
                ("u", 2, "cmax"),
            ),
            (5, 1, 1): (
                ("d", 1, "cmax"),
                ("u", 2, "cmax"),
                ("u", 1, "cmin"),
                ("m", 0, "m"),
                ("u", 1, "cmax"),
                ("u", 1, "land2"),
                ("u", 2, "cmax"),
            ),
        }
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        assert {k for k in mined if module._fold_served(*k)} == set(mined)  # noqa: SLF001
        for key, plan in mined.items():
            assert module._fold_skeleton(*key) == plan, key  # noqa: SLF001

    def test_fold_served_is_reachability(self) -> None:
        r"""``_fold_served`` accepts exactly the buildable low-run keys."""
        module = self.module()
        reachable = set()
        for r in range(1, 13):
            for pat in itertools.product((0, 1), repeat=r):
                mids = {(r - 1) // 2, r // 2}
                delta = 1 if all(pat[i] for i in mids) else 0
                reachable.add((r, delta, pat[1] if r > 1 else 0))

        accepted = {
            k
            for k in itertools.product(range(9), (0, 1), (0, 1))
            if module._fold_served(*k)  # noqa: SLF001
        }
        assert accepted == {k for k in reachable if 2 <= k[0] <= 5}
        assert not accepted - reachable

    def test_the_ladder_declines_other_arities(self) -> None:
        r"""Every shipped ladder has three weights, so only ``n == 3`` serves."""
        module = self.module()
        assert module._ladder("0110", 2) is None  # noqa: SLF001
        assert module._ladder("01" * 8, 4) is None  # noqa: SLF001


class TestPctInterleavedFold:
    r"""The staged replacement emits real code between its placeholders."""

    def test_interleaved_template_replays_every_three_input_row(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        table = "00001111"  # X1 creates equal suffix.
        template = module._interleaved_fold(table, 3)  # noqa: SLF001
        assert template is not None
        slots = [template.index("{X" + str(i) + "}") for i in range(3)]
        assert slots == sorted(slots)
        # Slots remain in stream order.
        # through equal branches.
        assert template.count("{X") == 3
        for row, want in enumerate(table):
            bits = [(row >> 2) & 1, (row >> 1) & 1, row & 1]
            io = ScriptedIO()
            run(module.fill(template, bits), io)
            assert io.getvalue() == want

    # Split by cost, measured: the.
    # interpreter replays are 5.15s.
    # mutant can break -- the.
    # so it stays in the fast run,.
    # slow-marked sibling below.
    # whole 256-table space on the.
    def test_every_three_input_table_builds_or_declines_exactly(self) -> None:
        r"""Sweep all 256 three-input tables through the staged build."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        built = 0
        for value in range(256):
            table = format(value, "08b")
            template = module._interleaved_fold(table, 3)  # noqa: SLF001
            if template is None:
                continue
            built += 1
            assert template.count("{X") == 3, table
            slots = [template.index("{X" + str(i) + "}") for i in range(3)]
            assert slots == sorted(slots), table  # slots stay in stream order.
        # The route is selective by.
        # fallback -- so pin that it.
        assert built == 136

    @pytest.mark.slow  # ~5s: 1088 interpreter replays.
    def test_every_three_input_build_computes_its_table(self) -> None:
        r"""Every table the route builds is replayed row by row."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        for value in range(256):
            table = format(value, "08b")
            template = module._interleaved_fold(table, 3)  # noqa: SLF001
            if template is None:
                continue
            for row, want in enumerate(table):
                bits = [(row >> 2) & 1, (row >> 1) & 1, row & 1]
                io = ScriptedIO()
                run(module.fill(template, bits), io)
                assert io.getvalue() == want, (table, row)

    @pytest.mark.slow  # ~10s: 4096 four-input builds.
    def test_four_input_tables_build_or_decline_without_raising(self) -> None:
        r"""At four inputs the merge has room to act, so its arms are reached."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        built = 0
        for value in range(0, 2**16, 16):
            table = format(value, "016b")
            template = module._interleaved_fold(table, 4)  # noqa: SLF001
            if template is None:
                continue
            built += 1
            assert template.count("{X") == 4, table
            slots = [template.index("{X" + str(i) + "}") for i in range(4)]
            assert slots == sorted(slots), table
        assert built == 1444

    def test_interleaved_fallback_builds_past_the_all_row_ladder(self) -> None:
        r"""A late-ignored suffix stays compact instead of spending 4096 rungs."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        n = 12
        # XOR of the first two bits: it.
        # threshold, and the all-row.
        table = "".join("0110"[row >> (n - 2)] for row in range(2**n))
        assert module._fold(table, n) is None  # noqa: SLF001
        template = module.pct_squared_minus_one(table)
        seen = set()
        for row in range(0, 2**n, 97):
            bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
            io = ScriptedIO()
            run(module.fill(template, bits), io)
            assert io.getvalue() == table[row], f"row {row}"
            seen.add(row >> (n - 2))
        assert seen == {0, 1, 2, 3}, seen


class TestPctFoldEmitter:
    r"""The emitter's mirror, driven at the steps the planner rarely asks."""

    @staticmethod
    def emitter(table: str = "01", n: int = 1):
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        return module._FoldEmitter(table, n)  # noqa: SLF001

    def test_a_zero_step_emits_nothing(self) -> None:
        r"""Moving by zero is not spelled at all, in either direction."""
        for move in ("descend", "plain_rise"):
            em = self.emitter()
            getattr(em, move)(0)
            assert em.body == []

    def test_a_single_step_is_spelled_as_three_against_two(self) -> None:
        r"""One has no spelling of its own: ``s`` is 2 and ``i`` is 3."""
        em = self.emitter()
        before = dict(em.pos)
        em.descend(1)
        assert em.body == ["i", "psp"]
        assert all(em.pos[r] - before[r] == -1 for r in before)

        em = self.emitter()
        before = dict(em.pos)
        em.plain_rise(1)
        assert em.body == ["pip", "s"]
        assert all(em.pos[r] - before[r] == 1 for r in before)

    def test_the_final_alignment_wraps_when_it_would_overshoot(self) -> None:
        r"""The last shift is a residue, and only one lift of it fits."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

        for start, expected in ((0, 48), (2900, 2864)):
            em = self.emitter("0", 0)
            key = next(iter(em.pos))
            em.pos = {key: start}
            em.cls = {key: "0"}
            em.finish()
            assert em.pos[key] == expected
            assert em.pos[key] % 256 == em.byte(key) % 256
            assert abs(em.pos[key]) <= module._LIMIT  # noqa: SLF001

    def test_a_rise_with_no_headroom_preshifts_first(self) -> None:
        r"""``p`` needs two to work with, so a shorter rise makes room."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        limit = module._LIMIT  # noqa: SLF001

        def rise_from(victim_top: int) -> list[str]:
            em = self.emitter()
            keys = list(em.pos)
            em.pos = {keys[0]: victim_top, keys[1]: -10}
            em.cls = {keys[0]: "0", keys[1]: "1"}
            em.rise(limit + 1, frozenset({keys[0]}))
            return em.body

        # u == 1: below the floor, so a.
        assert rise_from(limit) == ["i", "psp", "psp", "s"]
        # u == 2: exactly the floor, so.
        assert rise_from(limit - 1) == ["psp", "s"]


class TestPctFoldMoves:
    r"""The fold's move generator, at the guards that refuse a relocation."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_a_collision_across_classes_is_not_a_merge(self) -> None:
        r"""Two points at one value are indistinguishable forever after."""
        module = self.module()
        merge = module._fold_merge  # noqa: SLF001

        cross = [(0, 0, "0", frozenset({0})), (0, 0, "1", frozenset({1}))]
        assert merge(cross) is None

        extent = [(0, 0, "0", frozenset({0})), (0, 3, "0", frozenset({1}))]
        assert merge(extent) is None

        legal = [(0, 0, "0", frozenset({0})), (0, 0, "0", frozenset({1}))]
        assert merge(legal) == ((0, 0, "0", frozenset({0, 1})),)

    def test_a_survivor_reaching_below_the_victims_offers_no_window(self) -> None:
        r"""The relocation window is the gap to the nearest survivor's bottom."""
        state = (
            (0, 400, "0", frozenset({0})),
            (-100, 0, "0", frozenset({1})),
            (-200, 0, "1", frozenset({2})),
        )
        assert len(list(self.module()._fold_moves(state, kcap=3))) == 1  # noqa: SLF001

    def test_a_relocation_that_would_overflow_the_span_is_skipped(self) -> None:
        r"""Every wipe caps the spread, so a move that widens it is refused."""
        module = self.module()
        state = (
            (0, 0, "0", frozenset({0})),
            (-10, 0, "1", frozenset({1})),
            (-12000, 0, "0", frozenset({2})),
        )
        moves = list(module._fold_moves(state, kcap=3))  # noqa: SLF001
        assert moves, "the positive control must offer some move"
        for *_rest, nxt in moves:
            hi = max(p for p, _, _, _ in nxt)
            lo = min(p - span for p, span, _, _ in nxt)
            assert hi - lo <= 2 * module._LIMIT  # noqa: SLF001


class TestPctFoldPlanners:
    r"""The rule construction's refusals, driven through their own guards."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    # : Four points, alternating.
    # : enough that the rules.
    STATE = (
        (0, 0, "0", frozenset({0})),
        (-4, 0, "1", frozenset({1})),
        (-8, 0, "0", frozenset({2})),
        (-12, 0, "1", frozenset({3})),
    )

    def test_the_reduction_gives_up_on_its_budget(self) -> None:
        r"""A budget of zero takes no step and answers ``None``."""
        module = self.module()

        done = module._fold_done  # noqa: SLF001
        assert module._fold_reduce(self.STATE, done, budget=0) is None  # noqa: SLF001

    def test_the_reduction_finishes_when_it_is_given_room(self) -> None:
        r"""The positive control: the refusal above is the budget."""
        module = self.module()

        ops = module._fold_reduce(self.STATE, module._fold_done)  # noqa: SLF001
        assert ops is not None
        state = module._fold_norm(list(self.STATE))  # noqa: SLF001
        for op in ops:
            state = module._fold_step(state, op)  # noqa: SLF001
            assert state is not None
        assert module._fold_done(state)  # noqa: SLF001

    def test_no_rule_applies_to_a_walled_state(self) -> None:
        r"""Spans that fill the workspace leave the case analysis empty."""
        module = self.module()

        stuck = (
            (0, 3000, "0", frozenset({0})),
            (-10, 3000, "1", frozenset({1})),
        )
        assert module._fold_rule_move(stuck) is None  # noqa: SLF001

    def test_a_step_the_state_does_not_offer_answers_none(self) -> None:
        r"""``_fold_step`` re-checks a move rather than trusting it."""
        module = self.module()

        outside = ("d", 1, 99999, frozenset({3}))
        assert module._fold_step(self.STATE, outside) is None  # noqa: SLF001
        mixed = ("d", 2, 3004, frozenset({2, 3}))
        assert module._fold_step(self.STATE, mixed) is None  # noqa: SLF001
        everything = ("d", 4, 3004, frozenset({0, 1, 2, 3}))
        assert module._fold_step(self.STATE, everything) is None  # noqa: SLF001

    def test_a_clean_amount_skips_an_occupied_landing(self) -> None:
        r"""The first collision-free amount is computed, not the minimum."""
        module = self.module()

        state = (
            (0, 0, "1", frozenset({0})),
            (-3004, 0, "0", frozenset({1})),
        )
        assert module._fold_clean_amount(state, "d", 1) == 3005  # noqa: SLF001


class TestPctFoldPlan:
    r"""The plan's rotation pre-pass, and the bound that refuses a table."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_the_pre_pass_stops_when_no_bottom_wipe_is_offered(self) -> None:
        r"""Extent that no minimum-relocation wipe can clear ends the plan."""
        stuck = (
            (0, 3000, "0", frozenset({0})),
            (-10, 3000, "1", frozenset({1})),
        )
        assert self.module()._fold_plan(stuck) is None  # noqa: SLF001

    def test_the_pre_pass_clears_extent_when_it_can(self) -> None:
        r"""The positive control: ordinary extent is wiped and descends."""
        ok = (
            (0, 8, "0", frozenset({0, 1, 2})),
            (-40, 8, "1", frozenset({3, 4, 5})),
            (-80, 8, "0", frozenset({6, 7, 8})),
        )
        plan = self.module()._fold_plan(ok)  # noqa: SLF001
        assert plan is not None
        assert plan

    def test_a_reduction_that_cannot_finish_leaves_the_plan_empty(self) -> None:
        r"""The pre-pass can clear extent the rules still cannot use."""
        state = (
            (-40, 0, "0", frozenset({0})),
            (-48, 0, "1", frozenset({1})),
            (-3048, 8, "1", frozenset({2})),
            (-3448, 4, "0", frozenset({3})),
            (-3452, 400, "1", frozenset({4})),
        )
        assert self.module()._fold_plan(state) is None  # noqa: SLF001

    def test_a_table_too_wide_for_the_workspace_is_refused(self) -> None:
        r"""The ladder must fit the workspace, and the packed one fits longest."""
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001

        # Each ladder in turn gives out.
        assert limit < module._FOLD_STEP * (2**10 - 1)  # noqa: SLF001
        assert limit < module._FOLD_NARROW_STEP * (2**11 - 1)  # noqa: SLF001
        assert sum(module._fold_subset_weights(11)) <= limit  # noqa: SLF001
        assert module._fold_subset_weights(12) is None  # noqa: SLF001

        # Nothing serves twelve inputs,.
        # to be one the fold would.
        # every row, which is 4096 runs.
        # so it never reaches the fold.
        wide = "".join(str(((r >> 11) & 1) ^ ((r >> 10) & 1)) for r in range(2**12))
        assert module._cascade(wide, 12) is None  # noqa: SLF001
        assert module._fold(wide, 12) is None  # noqa: SLF001
        # A table inside the bound.
        # the workspace and not the.
        assert module._fold("0011", 2) is not None  # noqa: SLF001

    def test_the_packed_ladder_meets_the_distinctness_floor(self) -> None:
        r"""``2**n + 1`` is the least a distinct-position ladder can span."""
        module = self.module()
        assert module._sub_code(1) is None  # noqa: SLF001
        for n in range(2, 12):
            weights = module._fold_subset_weights(n)  # noqa: SLF001
            assert weights is not None
            assert sum(weights) == 2**n + 1, n
            assert min(weights) >= 2, n
            positions = module._fold_positions(n, weights)  # noqa: SLF001
            assert len(set(positions)) == 2**n, n

    @pytest.mark.parametrize("ladder", ["narrow", "packed"])
    def test_ladder_setters_are_equal_width(self, ladder: str) -> None:
        r"""Both branches match in width, and odd-width amounts are respelled."""
        module = self.module()
        n = 6
        weights = (
            module._fold_uniform(n, module._FOLD_NARROW_STEP)  # noqa: SLF001
            if ladder == "narrow"
            else module._fold_subset_weights(n)  # noqa: SLF001
        )
        assert weights is not None
        setters = module._fold_setters(n, weights)  # noqa: SLF001
        assert len(setters) == n
        for zero, one in setters:
            assert len(zero) == len(one)
            assert module._apply(0, zero) == 0  # noqa: SLF001
        # The whole chain lays every.
        positions = module._fold_positions(n, weights)  # noqa: SLF001
        for row in (0, 1, 2, 2**n - 1):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            code = "".join(setters[i][bits[i]] for i in range(n))
            assert module._apply(0, code) == positions[row]  # noqa: SLF001

    def test_every_setter_amount_past_the_reset_line_spells(self) -> None:
        r"""Amounts at and above the reset line respell by descending."""
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001
        for amount in (3002, 3003, 3006, 6006, 2 * limit + 2):
            zero, one = module._fold_setters(1, (amount,))[0]  # noqa: SLF001
            assert len(zero) == len(one), amount
            assert module._apply(0, zero) == 0, amount  # noqa: SLF001
            assert module._apply(0, one) == -amount, amount  # noqa: SLF001

    @pytest.mark.slow  # ~5s: ten inputs, 1024 rows.
    def test_a_low_run_ten_input_table_builds_and_runs(self) -> None:
        r"""A low-run ten-input table takes the skeleton path, and lays."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_pct_squared_minus_one

        n = 10
        table = "".join(
            str(((r >> (n - 1)) & 1) ^ ((r >> (n - 2)) & 1)) for r in range(2**n)
        )
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(2**n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], f"row {row}"
        assert len(widths) == 1, widths

    @pytest.mark.slow  # ~14s: eleven inputs, a.
    def test_the_packed_ladder_reaches_eleven_inputs(self) -> None:
        r"""Eleven inputs build on the packed ladder and print correctly."""
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_pct_squared_minus_one

        n = 11
        rng = random.Random(11011)
        table = "".join(rng.choice("01") for _ in range(2**n))
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(0, 2**n, 97):  # a stride coprime to the.
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], f"row {row}"
        assert len(widths) == 1, widths

    @pytest.mark.slow  # generic twelve-input fold:.
    def test_interleaved_fold_builds_a_generic_twelve_input_table(self) -> None:
        r"""A centred final embed escapes the all-row ladder's limit."""
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_pct_squared_minus_one

        rng = random.Random(1)
        table = "".join(rng.choice("01") for _ in range(2**12))
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(0, 2**12, 97):
            bits = [(row >> shift) & 1 for shift in range(11, -1, -1)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], row
        assert len(widths) == 1, widths

    @pytest.mark.slow  # packed prefix + sixteen-class.
    def test_interleaved_fold_builds_a_generic_thirteen_input_table(self) -> None:
        r"""The packed prefix ladder compacts to its cofactors before laying."""
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_pct_squared_minus_one

        rng = random.Random(13)
        table = "".join(rng.choice("01") for _ in range(2**13))
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(0, 2**13, 331):
            bits = [(row >> shift) & 1 for shift in range(12, -1, -1)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], row
        assert len(widths) == 1, widths

    def test_a_table_whose_plan_fails_builds_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""No plan means no template, not a partial one."""
        module = self.module()
        assert module._fold("0011", 2) is not None  # noqa: SLF001

        monkeypatch.setattr(module, "_fold_plan", lambda *_a, **_k: None)
        assert module._fold("0011", 2) is None  # noqa: SLF001


class TestPctAffineSolver:
    r"""The wide band's line solver, at the inputs it has to refuse."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_the_shorter_of_cascade_and_affine_ships(self) -> None:
        r"""The cascade is usually shorter at three inputs, but not always."""
        module = self.module()
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            shipped = len(boolean.pct_squared_minus_one(table))
            cascade = module._cascade(table, 3)  # noqa: SLF001
            assert cascade is None or shipped <= len(cascade), table
            improved += cascade is not None and shipped < len(cascade)
        assert improved == 42  # the other two tie, keeping.

    def test_affine_stays_gated_above_three_inputs(self) -> None:
        r"""The comparison must not reach the four-input enumeration."""
        module = self.module()
        assert module._affine.__doc__  # noqa: SLF001
        parity4 = "".join(str(bin(row).count("1") % 2) for row in range(16))
        # The deep band answers this.
        start = time.perf_counter()
        boolean.pct_squared_minus_one(parity4)
        assert time.perf_counter() - start < 10.0

    def test_constant_values_cannot_meet_differing_wants(self) -> None:
        r"""One value cannot map to two answers, whatever the line."""
        solve = self.module()._solve_affine  # noqa: SLF001

        assert solve((5, 5, 5), (1, 2, 3)) is None
        # The same shape with one want.
        # disagreement and not the.
        assert solve((0, 0), (4, 4)) == (0, 4)

    def test_a_constant_want_outside_the_offset_grid_is_refused(self) -> None:
        r"""The offset has to be one the language can spell."""
        module = self.module()
        beyond = max(module._WIDE_B_VALS) + 100  # noqa: SLF001

        assert module._solve_affine((0, 0), (beyond, beyond)) is None  # noqa: SLF001
        assert module._solve_affine((0, 1), (3, 5)) == (2, 3)  # noqa: SLF001

    def test_a_multiplier_off_the_grid_drops_the_realisation(self) -> None:
        r"""A ratio the grid does not carry is skipped, not rounded."""
        realise = self.module()._realisations  # noqa: SLF001

        assert realise((0, 1, 2, 3))
        assert realise((0, 1000, 1, 3)) == []


class TestPctAffineBand:
    r"""The three-input band's two skips, which the shipped budget hides."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_the_shipped_budget_stops_before_both_skips(self) -> None:
        r"""The premise: at 12 candidates neither guard is reached."""
        module = self.module()
        assert module._CANDIDATES == 12  # noqa: SLF001

    def test_a_candidate_with_no_realisation_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""Solving the two halves does not mean the vector can be spelled."""
        module = self.module()
        values = (12, 13, 13, 12)

        assert module._solve_affine(values, (0, 0, 0, 0)) is not None  # noqa: SLF001
        assert module._solve_affine(values, (0, 1, 1, 0)) is not None  # noqa: SLF001
        assert module._realisations(values) == []  # noqa: SLF001

        monkeypatch.setattr(module, "_CANDIDATES", 1000)
        assert module._affine("00010100", 3) is not None  # noqa: SLF001

    def test_a_relabelling_that_will_not_solve_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The final setter is solved again against the answer bits."""
        module = self.module()
        values = (12, 12, 12, 13)
        even, odd = (0, 0, 0, 0), (0, 0, 0, 1)

        assert module._solve_affine(values, even) is not None  # noqa: SLF001
        assert module._solve_affine(values, odd) is not None  # noqa: SLF001
        # Relabelling with one=0,.
        relabelled = tuple(0 if bit else 1 for bit in odd)
        assert module._solve_affine(values, relabelled) is None  # noqa: SLF001

        monkeypatch.setattr(module, "_CANDIDATES", 1000)
        assert module._affine("00000001", 3) is not None  # noqa: SLF001


class TestPctFoldSkeletonResolver:
    r"""The tabulated planner's refusals, driven on constructed states."""

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    # : One point: whichever way it.
    LONE = ((0, 0, "a", frozenset({0})),)

    # : Two points of one class,.
    PAIR = (
        (0, 0, "a", frozenset({0})),
        (-4, 0, "a", frozenset({1})),
    )

    @pytest.mark.parametrize("kind", ["d", "u"])
    def test_geometry_refuses_a_wipe_that_leaves_no_survivor(self, kind: str) -> None:
        r"""Both branches measure the window against the survivors."""
        module = self.module()
        assert module._fold_geometry(self.LONE, kind, 1) is None  # noqa: SLF001

    def test_resolve_passes_on_a_wipe_with_no_geometry(self) -> None:
        r"""A symbolic amount cannot be resolved where the window does not."""
        module = self.module()
        assert module._fold_resolve(self.LONE, "d", 1, "cmax") is None  # noqa: SLF001

    def test_resolve_refuses_a_landing_index_past_the_survivors(self) -> None:
        r"""``landN`` names a survivor by index, and one wipe leaves only one."""
        module = self.module()
        assert module._fold_resolve(self.PAIR, "d", 1, "land9") is None  # noqa: SLF001

    def test_resolve_refuses_a_landing_that_does_not_match(self) -> None:
        r"""A landing is a merge, so span, class and window all have to agree."""
        module = self.module()
        assert module._fold_resolve(self.PAIR, "d", 1, "land0") is None  # noqa: SLF001

    def test_construct_emits_an_empty_plan_for_a_finished_state(self) -> None:
        r"""Two wiped points of different classes is what ``_fold_done``."""
        module = self.module()
        finished = (
            (0, 0, "a", frozenset({0})),
            (-5, 0, "b", frozenset({1})),
        )
        assert module._fold_construct(finished) == []  # noqa: SLF001
