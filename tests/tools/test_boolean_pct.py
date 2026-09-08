"""Unit tests for the %^2^-1 boolean generator.

Covers :mod:`esolangs.tools.boolean.pct_squared_minus_one`, split out of
``test_boolean_parameterized.py``: the generator derives its programs through
several ordered constructions and its tests are the second-largest block
there.
"""

import importlib
import itertools
import time

import pytest

from esolangs.tools import boolean


class TestParameterizedPctSquaredMinusOne:
    """Input-by-substitution boolean generator for %^2^-1.

    The wall proved for %^2^-1 (``docs/proofs.md``) shows no program
    that *reads* its inputs computes XOR or AND at any length.  That bounds
    the reading model, not the language: these programs embed their bits
    instead, so the read that erases the accumulator never happens, and
    every two-input table builds.

    ``l`` prints the accumulator in decimal, so the answer is read straight
    off stdout as ``"0"`` or ``"1"`` -- no branch is needed, which suits a
    language whose only jump target is position 0.
    """

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
            ("10", 1),  # NOT
            ("01", 1),  # identity
            # The two constant tables are the slow ones to derive -- 1.1s
            # and 1.0s against 0.04s for NOT -- putting them alone over
            # the fast run's one-second budget.
            pytest.param("00", 1, marks=pytest.mark.slow),  # constant zero
            pytest.param("11", 1, marks=pytest.mark.slow),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR -- the function the wall forbids a reader
            ("1001", 2),  # XNOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_pct(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    # Derives every table at that arity: 2.0s at n=1 and 5.3s at n=2, both
    # over the fast run's one-second budget.  No single table dominates --
    # the cost is the count -- so the whole sweep is marked, not a case.
    @pytest.mark.slow
    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.pct_squared_minus_one(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_pct(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_instantiations_share_a_length(self) -> None:
        """All four programs are the same length, so none leaks its inputs."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one("0110")
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, lengths

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    @pytest.mark.slow  # 5.3s: derives all sixteen two-input tables
    def test_programs_never_read_input(self) -> None:
        """No emitted program contains ``n``, the input command.

        This is what separates the generator from the model the wall
        bounds: the bits arrive by substitution, so the read that overwrites
        the accumulator never runs.
        """
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            template = parameterized.pct_squared_minus_one(format(table_int, "04b"))
            for a in (0, 1):
                for b in (0, 1):
                    assert "n" not in self.instantiate(template, [a, b])

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.pct_squared_minus_one("011")

    @pytest.mark.parametrize("n", [3, 4, 5, 6])
    def test_minterm_cascade_lifts_the_two_input_cap(self, n: int) -> None:
        """Single-minterm tables build at any arity, past the derived path's cap.

        The derived two-input path composes one affine map per input into a
        shared value, which forces each cofactor of the table to be constant
        or an affine image of one shared function -- the constraint that caps
        it at two inputs.  The cascade escapes it by using the erase
        multiplier as a conditional: the accumulator is loaded with 1 and
        wiped by the first input whose bit misses the minterm, so *where* the
        wipe happens depends on the inputs.  That is a branch realised
        arithmetically in a language whose only jump target is position 0.
        """
        from esolangs.tools.boolean import parameterized

        for index in range(2**n):
            table = "".join("1" if i == index else "0" for i in range(2**n))
            template = parameterized.pct_squared_minus_one(table)
            for row in range(2**n):
                bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
                assert self.run_pct(self.instantiate(template, bits)) == table[row]

    def test_cascade_branches_are_equal_width(self) -> None:
        """No instantiation leaks its inputs through ``len()``.

        Both cascade branches are two characters -- ``pp`` is two negations
        composing to the identity, ``'p`` zeroes and negates zero -- so a
        one-character ``'`` erase, whose odd shortfall has no ``pp`` padding,
        is never what a setter spells.
        """
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
        """``ips`` maps a 0/1 accumulator to ``1 - r``, so complements are free.

        ``AND``-``n`` and single minterms are subcubes and build directly;
        ``OR``-``n`` and ``NAND``-``n`` are the complements of subcubes and
        build by appending that one three-character negation.
        """
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
        """Every conjunction of literals builds, free inputs included.

        A subcube leaves the inputs its conjunction does not mention free, and
        their setters are the identity on both branches -- which is what makes
        the coverage wider than the single-minterm family.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _cascade

        # The cascade is asked directly rather than through the generator,
        # which now falls back to the composed-affine path when no subcube
        # serves -- counting the generator's successes would measure both
        # constructions and no longer pin this one.
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
        # The count is exactly ``2 * 3**n - 2*n``.  There are ``3**n``
        # subcubes (each input is pinned to 0, pinned to 1, or free), and as
        # many complements; the overlap is precisely the ``2*n`` single-literal
        # tables, the only subcubes whose complement is also a subcube.  The
        # constant tables do not double-count, because :func:`_subcube_of`
        # rejects an empty ON-set.  Pinned so a regression in the acceptor is
        # caught rather than passing quietly.
        assert built == 2 * 3**3 - 2 * 3 == 48

    # The cost is the three-input composition, which is derived once for the
    # whole arity and cached -- 4.9s on the first table and free thereafter,
    # so it is the arity that is marked, not this table.
    @pytest.mark.slow
    def test_affine_path_builds_three_input_parity(self) -> None:
        """XOR3 builds, which no subcube is and the cascade refuses.

        Parity is the canonical table outside the subcube family: its ON-set
        is four disjoint minterms, so no conjunction of literals describes it
        and neither does its complement.  It composes from one affine setter
        per input instead, which is the construction that lifts the cap.
        """
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
        """A composed-affine program leaks nothing through ``len()``.

        The branches are respelled to a common width rather than padded with
        ``pp``, so this checks the property the respelling is there to keep.
        """
        from esolangs.tools.boolean import parameterized

        template = parameterized.pct_squared_minus_one("01101001")
        lengths = {
            len(self.instantiate(template, [(row >> (2 - k)) & 1 for k in range(3)]))
            for row in range(8)
        }
        assert len(lengths) == 1, lengths

    @pytest.mark.slow
    def test_three_inputs_are_total(self) -> None:
        """All 256 three-input tables build, and every one of them runs.

        Totality comes from the band construction, which prints with ``e``
        rather than ``l``: ``e`` writes ``chr(acc & 0xFF)``, so a row only has
        to be *congruent* to 48 or 49 mod 256 instead of being exactly 0 or 1,
        and repeated resets then cut the weighted row order into one band per
        run of the table.  Every table that builds is executed here, so a
        construction that grew coverage by emitting a wrong program fails
        rather than raising the count.
        """
        from esolangs.tools.boolean import parameterized

        for value in range(256):
            table = format(value, "08b")
            # No ``except`` here: a refusal is a failure now, not a skip.
            template = parameterized.pct_squared_minus_one(table)
            lengths = set()
            for row in range(8):
                bits = [(row >> (2 - k)) & 1 for k in range(3)]
                program = self.instantiate(template, bits)
                lengths.add(len(program))
                assert self.run_pct(program) == table[row], (table, bits)
            # Both branches of every setter share a width, so no program leaks
            # its inputs through ``len()``.
            assert len(lengths) == 1, (table, sorted(lengths))

    def test_deep_band_builds_four_input_parity(self) -> None:
        """Parity-4 builds and runs, which no earlier path reached.

        An earlier *positive* band construction capped its weights at
        ``3003 // 256 == 11`` units, because building the ladder upward makes
        every row sum sit under the limit at once; four inputs need
        ``2**4 - 1 == 15``, so it had no weighting at all and was removed once
        the deep band strictly dominated it (same coverage, a quarter the
        program length).  The deep band subtracts instead, so the ladder is
        negative -- nothing resets below zero -- and the budget does not exist.

        Parity is the case the popcount ladder serves: every weight is one, so
        the span is ``n`` units rather than ``2**n - 1``.
        """
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
        """A weighting whose collision splits a class is refused, not served.

        Rows sharing a value are merged by the first cut that reaches them and
        can never be told apart again, so a weighting that collides two rows of
        different classes cannot compute the table.  The planner has to reject
        it rather than emit a program for the wrong function.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _deep_plan,
            _deep_values,
        )

        # Weights (1, 1) collide rows 01 and 10 on one value.  XOR puts both in
        # the same class, so the collision is harmless and the table plans.
        collided = _deep_values(2, (1, 1), 0)
        assert collided[1] == collided[2]
        assert _deep_plan("0110", 2, collided) is not None
        # A table that disagrees on exactly those two rows is refused: no
        # schedule can separate rows the ladder has already merged.  ``"0010"``
        # is 1 on row 10 and 0 on row 01.
        assert _deep_plan("0010", 2, collided) is None

    def test_deep_band_builds_symmetric_tables_at_five_inputs(self) -> None:
        """Symmetric tables build past four inputs on the deep band.

        What bounds the deep band is distinctness rather than run count.  Two
        rows sharing a value are merged by the first cut that reaches them and
        can never be separated, so a weighting serves a table only if every
        collision it forces joins rows of one class.  Keeping all rows distinct
        needs a span of ``(2**n - 1) * 256``, which is 7936 at five inputs
        against a limit of 3003, so every weighting inside the limit collides
        *some* rows there.  A symmetric table tolerates exactly that: the
        popcount ladder spans only ``n * 256`` and merges the rows such a table
        already agrees on.
        """
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
        from esolangs.tools.boolean.pct_squared_minus_one import _fold

        table = "00000101"
        template = _fold(table, 3)
        assert template is not None
        assert "m" in template.partition("\n")[2], "the doubling never fired"
        lengths = set()
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row], (table, bits)
        assert len(lengths) == 1, sorted(lengths)

    @pytest.mark.slow  # a 19-run plan plus 32 interpreter runs
    def test_fold_closes_five_inputs(self) -> None:
        """A five-input table the deep band refuses computes on the fold.

        The table is pinned because finding one is expensive, not because
        they are rare: ``_deep_band`` refuses it only after exhausting its
        whole weighting family, an ~18s sweep that was run once to select
        this witness and is not re-run here.  (Near-parity is *not* such a
        witness -- a weighting tolerates its collisions and the deep band
        serves it in milliseconds -- which is why a random table is pinned
        instead.)  The fold is called directly to keep the test at its own
        cost; the dispatch reaches it by falling through the same refusal.
        The template is executed on all 32 rows at equal fill length.
        """
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

    @pytest.mark.slow  # a 21-point plan plus 32 interpreter runs
    def test_a_wide_state_plans_and_executes(self) -> None:
        """A 21-point table plans in milliseconds and computes every row.

        Pinned when this table was a planner regression: an earlier
        search-based configuration explored it for fifty seconds and then
        *refused a table it can build*.  The rule construction plans it
        outright, and the rows are executed rather than merely planned,
        because a plan that does not compute is not a fix.
        """
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
        """A constant table leaves one point, which ``finish`` aligns alone.

        Every other fold test lands two points, one per class, so the pair's
        mutual gap carries the residue.  A constant table has no second
        class: ``finish`` takes its one-point arm instead, where there is no
        gap to make congruent and the only work is shifting that point onto
        its answer byte within the room left below the limit.

        Both constants are run because the arm subtracts 256 until the shift
        fits, and the two answer bytes sit at different distances from the
        limit -- so they do not take that loop the same number of times.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _fold

        table = bit * 8
        template = _fold(table, 3)
        assert template is not None
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            assert self.run_pct(self.instantiate(template, bits)) == bit

    @pytest.mark.slow  # three arities' worth of interpreter runs
    @pytest.mark.parametrize(
        ("table", "reaches"),
        [
            # A weighting whose setter spelling is empty for some input --
            # the pair `_deep_setters` appends when a unit contributes
            # nothing, which every other table's weighting avoids.
            ("1100110001110111", "an empty setter pair"),
            # The deep band's own refusal, reached through the dispatch:
            # this table exhausts the weighting family before the fold
            # picks it up.
            ("1101000011010101", "the deep band's refusal"),
            # The fold's narrow-gap endgame: the two surviving points land
            # within 258 of each other, so `finish` cannot solve the
            # congruence directly and parks the upper point past the limit
            # to reopen the gap first.
            ("00001111101010010010001011101101", "finish's narrow-gap reopen"),
        ],
    )
    def test_tables_that_reach_the_rarer_arms(self, table: str, reaches: str) -> None:
        """Witnesses for arms no other table in the suite takes.

        Found by tracing the public entry over every table at one, two and
        three inputs and a few hundred at four and five, then keeping the
        first table to reach each arm -- so these are reachable in
        production, not constructed by calling an internal with a state its
        caller cannot produce.

        Executed rather than merely built: a program that reaches a new arm
        and computes the wrong function is the failure this is here to
        catch, so every row runs and the fills stay one width.
        """
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
        """The public entry reaches the fold, not just ``_fold`` called directly.

        Both fold tests above call ``_fold`` themselves to keep their cost
        to the plan they are pinning, so nothing exercised the last arm of
        ``pct_squared_minus_one``'s own ordering -- the one that runs after
        the deep band refuses.  A generator whose dispatch stopped handing
        five-input tables to the fold would still pass every test here.

        Cheap because the witness is already pinned: the ~18s sweep that
        found a table the deep band refuses was paid once, above.  This
        asserts the refusal still holds (so the fall-through is the arm
        being taken, not a deep band that quietly started serving it) and
        that the dispatch returns what the fold returns.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _deep_band,
            _fold,
            pct_squared_minus_one,
        )

        table = "11011111100100101001101110111000"
        assert _deep_band(table, 5) is None  # the arm above must still refuse
        assert pct_squared_minus_one(table) == _fold(table, 5)

    def test_deep_band_refuses_past_its_span_budget_without_enumerating(
        self,
    ) -> None:
        """Past eleven inputs no weighting fits, and the refusal is instant.

        Each unit prices a whole residue system, so even the all-ones
        weighting costs ``n * 256`` against the 3003 limit.  Without the
        up-front gate, ``_deep_weightings`` walks ``7**n`` tuples before
        its sum filter -- hours at twelve inputs -- so this test hanging
        rather than failing is what removing the gate looks like.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _deep_band

        parity = "".join(str(bin(r).count("1") & 1) for r in range(2**12))
        assert _deep_band(parity, 12) is None

    @pytest.mark.slow  # derives the whole three-input arity once
    def test_affine_reach_is_exactly_characterized(self) -> None:
        """The composed-affine path's 86/256 is a predicate, not a measurement.

        A three-input table is reachable iff its cofactors on the **last**
        input are equal, complementary or constant -- the shared-cofactor
        law -- and it is not constant, the constants being served by earlier
        paths.  The law and the path coincide exactly: 86 of the 88 tables
        the law admits, the two missing ones being the constants.

        Pinned because the docs used to record the law as *crossing* this
        path rather than containing it -- a claim that came from testing the
        law on the first input instead of the last.  ``x0 ^ x2`` was also
        excluded for a while, and that was an artefact of the enumeration
        this path used to run rather than a property of the model.
        """
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
        """``x0 ^ x2`` builds, and short, which the old enumeration refused.

        The path used to compose every branch pair layer by layer, keeping
        six value vectors per induced partition and choosing them by
        arrival.  Vectors sharing a partition are not interchangeable -- a
        later setter translates by a bounded offset, so one far from zero
        cannot be moved onto the values a tail needs -- and for this table's
        partition the six banked witnesses were all out of reach while the
        usable one was dropped.  The construction has no such choice to get
        wrong: it reads the partition off the table and solves.

        Kept as the regression, with the length checked too: the table was
        served by the deep band at 3054 characters while this path builds it
        in well under a hundred.
        """
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
        """The construction serves the arity the dispatch calls it for.

        The pre-vector it solves has four entries, one per pair of leading
        bits, so the derivation is written for three inputs; the deep band
        covers every table this would reach above that, and the dispatch
        calls it at three only.  Declining rather than guessing keeps the
        two facts in one place.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _affine

        assert _affine("0110", 2) is None
        assert _affine("0110100110010110", 4) is None

    def test_cascade_reach_is_exactly_the_subcubes(self) -> None:
        """The cascade builds exactly the tables that are a subcube or one's
        complement, which is what its docstring claims at any arity.

        Checked at three inputs against the whole arity.  A subcube here is
        the 1-set agreeing on some inputs and free on the rest, so the count
        of ones is ``2 ** (free inputs)``.
        """
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

    @pytest.mark.slow  # every weighting inside the budget, over a table sample
    def test_a_legal_weighting_always_schedules(self) -> None:
        """Legality decides the deep band; the schedule then follows.

        A weighting collides rows whose weighted sums tie, and a collision is
        survivable exactly when it joins rows of one class -- so a weighting
        is *legal* for a table when no cross-class pair ties.  The
        construction rests on legality being sufficient as well as necessary:
        it picks the first legal weighting inside the span budget and calls
        the planner once, where the search called it per candidate.

        Pinned because a counterexample would not raise.  The planner would
        return ``None``, the loop would move on, and the only visible effect
        would be a longer program from a later construction -- so the
        property is checked rather than assumed.  Failures do exist outside
        the budget, at ``sum(units) * 256`` past the limit, which is why
        :func:`_deep_weightings` drops those rather than trying them.
        """
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
        """The dropped weightings are dropped for a stated reason.

        A weighting is measured in whole residue systems, so its span is
        ``sum(units) * 256`` and the limit allows ``3003 // 256 == 11`` of
        them.  Every weighting seen to fail with legal collisions failed
        exactly there -- sum 12, span 3072 -- which is what makes the budget
        a derivation rather than a tuning knob.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _BAND_UNIT,
            _LIMIT,
            _deep_weightings,
        )

        for units in _deep_weightings(4):
            assert sum(units) * _BAND_UNIT <= _LIMIT, units
        assert max(sum(u) for u in _deep_weightings(4)) == _LIMIT // _BAND_UNIT

    def test_deep_band_is_screened_above_four_inputs(self) -> None:
        """Asymmetric five-input tables are screened, symmetric ones built.

        The deep band cannot serve a five-input table unless the table
        agrees on every popcount class -- its weightings force collisions
        there -- and proving that by enumeration cost about eighteen
        seconds per table.  The screen settles it immediately, so the
        expensive refusal is skipped while the tables it really does build
        still take its (much shorter) programs.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _deep_band

        parity = "".join(str(bin(r).count("1") % 2) for r in range(32))
        majority = "".join("1" if bin(r).count("1") >= 3 else "0" for r in range(32))
        assert _deep_band(parity, 5) is not None
        assert _deep_band(majority, 5) is not None
        # One flipped row breaks the popcount symmetry and is screened out.
        asymmetric = list(parity)
        asymmetric[7] = "0" if asymmetric[7] == "1" else "1"
        assert _deep_band("".join(asymmetric), 5) is None

    @pytest.mark.slow  # 8.3s: the ladder build plus eight interpreter runs
    def test_ladder_builds_majority_three(self) -> None:
        """Majority-3 builds, which no affine composition of setters reaches.

        It is the smallest OR of disjoint subcubes, and the docs recorded it as
        out of reach on the grounds that chaining indicator gadgets needs a
        running total to survive a gadget that erases.  The ladder keeps that
        total in the accumulator and lets the over-3003 reset read it as a
        threshold, so the argument does not bind.  Executed on all eight rows
        rather than asserted structurally.
        """
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.pct_squared_minus_one import _affine, _cascade

        table = "00010111"
        # The other two paths really do refuse it, so this pins the ladder.
        assert _cascade(table, 3) is None
        assert _affine(table, 3) is None
        template = parameterized.pct_squared_minus_one(table)
        lengths = set()
        for row in range(8):
            bits = [(row >> (2 - k)) & 1 for k in range(3)]
            program = self.instantiate(template, bits)
            lengths.add(len(program))
            assert self.run_pct(program) == table[row]
        # Both branches of every setter share a width, so no program leaks its
        # inputs through ``len()``.
        assert len(lengths) == 1, lengths

    @pytest.mark.slow  # the whole setter grid, pairwise
    def test_every_branch_pair_shares_a_spelling_width(self) -> None:
        """No setter in the grid needs the "no shared width" fallback.

        Both branches of a setter must be the same width or the program leaks
        its inputs through ``len()``.  :func:`_spell_affine` gives up when two
        branches share no width -- but for the shipped grid that never
        happens, which is why the guard carries a coverage pragma.  Pinned
        here so the pragma rests on a checked property: narrowing the grid or
        the spelling depth makes this fail rather than silently making dead
        code live.
        """
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
        """``_WIDE_A_VALS`` is generated, and the generator is the language.

        ``m`` doubles and ``p`` negates, so the reachable multipliers are
        the signed powers of two plus the erase -- a closure over the two
        commands, not a list of measured answers.  Only the *bound* is
        measured, which is why it is a separate constant.

        Order is asserted alongside the set because the wide search takes
        the first spelling that behaves: ascending magnitude, positive
        before negative.  Reordering would change which spelling wins
        without changing what is reachable, so a set-only assertion would
        not see it.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import (
            _WIDE_A_LIMIT,
            _WIDE_A_VALS,
            _wide_a_vals,
        )

        assert _WIDE_A_VALS == (0, 1, -1, 2, -2, 4, -4)
        assert _wide_a_vals(_WIDE_A_LIMIT) == _WIDE_A_VALS

        # The closure itself: reachable by doubling and negating from 1.
        reach = {0, 1}
        for _ in range(_WIDE_A_LIMIT.bit_length()):
            reach |= {2 * v for v in reach} | {-v for v in reach}
        assert set(_WIDE_A_VALS) == {v for v in reach if abs(v) <= _WIDE_A_LIMIT}

        # Widening is a knob, not a rewrite: the next power just appears.
        assert _wide_a_vals(8) == (0, 1, -1, 2, -2, 4, -4, 8, -8)

    def test_built_spell_bases_match_the_frozen_witnesses(self) -> None:
        """The fold reproduces the enumeration's witnesses exactly.

        These are what the old breadth-first walk over ``simp'`` found:
        the shortest spelling of each grid map at each width parity, with
        ``a == 0`` carrying one base because the erase forgets the prefix.
        The module grows the same strings; this remembers what they were.
        """
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
        """Each width's string realises its map, padding included.

        The spellings derive from :func:`_spell_bases` -- a minimal witness
        per parity, widened by ``pp`` suffixes, or by ``s`` prefixes where
        the erase forgets them -- so this checks the *derived* strings, not
        just the bases: every entry of every map's width dict is run over
        the admission window and must land on ``a*x + b`` exactly.
        """
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
        """``'`` is the constant map: it discards whatever it was given.

        The setters are affine maps ``x -> a*x + b``, and ``a == 0`` is the
        one that cannot be reached by scaling -- it needs the reset command.
        Both inputs must land on the same value, which is what makes it a
        constant rather than merely a steep slope.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _affine_code, _apply

        code = _affine_code(0, 5)
        assert code is not None
        assert "'" in code, "a constant map has to reset the accumulator"
        assert _apply(7, code) == 5
        assert _apply(0, code) == 5

        # Only four multipliers have a spelling; anything else has no code.
        assert _affine_code(3, 0) is None
        # The offset needs one too: 1 is the gap `s`/`i` cannot express.
        assert _affine_code(1, -1) is None

    def test_the_model_mirrors_every_command_the_language_has(self) -> None:
        """``_apply`` stands in for the interpreter, so it owes it every op.

        The emitted tails only ever translate, so ``m`` and the over-3003
        reset are not on the path a built program takes -- but they are
        what the *language* does, and a model that quietly disagreed with
        the interpreter would let a future tail shape be validated against
        a machine that does not exist.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _LIMIT, _apply

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

    def test_a_tail_is_not_always_available(self) -> None:
        """Not every pair of class values can be printed apart.

        The tail has to land the one-class on exactly 1 and the zero-class
        on 0 (or past the reset limit).  Two classes that share a value are
        the clearest case that no tail can separate -- ``l`` prints one
        accumulator, so identical inputs cannot print differently.
        """
        from esolangs.tools.boolean.pct_squared_minus_one import _tail_for

        assert _tail_for(-5, -5) is None
        assert _tail_for(1, 0) is not None, "the trivial pair still works"
        # Two classes further apart than a step have no tail either: the
        # translation moves both together, so it cannot close a wider gap.
        assert _tail_for(5, 0) is None

    def test_a_table_no_candidate_realizes_is_reported(self) -> None:
        """With every parameter set rejected the derivation reports nothing.

        The enumeration is small and structural -- the constants input 0
        contributes, the spelling, and the class pair -- and some candidate
        always works out for a two-input table.  Rejecting all of them is
        what exercises the empty answer, which the caller turns into its
        own refusal rather than emitting a program for the wrong function.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        from esolangs.tools.boolean.pct_squared_minus_one import _derive

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_solution", lambda *_a, **_k: None)
            assert _derive("0110") is None


class TestPctSquaredHelpers:
    """The %^2^-1 spelling helpers, at the inputs their guards exist for.

    These are pure functions over small integers, so the edges the search
    itself only reaches incidentally are reachable directly: a width that
    admits no spelling and the zero shortcut.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_sub_of_width_rejects_an_unreachable_split(self) -> None:
        """A width too narrow to spell ``k`` has no ``i``/``s`` split."""
        assert self.module()._sub_of_width(1, 1) is None  # noqa: SLF001

    @pytest.mark.parametrize("name", ["_even_width_for"])
    def test_zero_needs_no_width(self, name: str) -> None:
        """Subtracting nothing is width zero, not a search."""
        assert getattr(self.module(), name)(0) == 0

    @pytest.mark.parametrize("name", ["_even_width_for"])
    @pytest.mark.parametrize("k", [1, 2, 3, 7])
    def test_unspellable_weights_return_none(self, name: str, k: int) -> None:
        """Some weights have no even-width spelling at all."""
        assert getattr(self.module(), name)(k) is None

    @pytest.mark.parametrize("name", ["_even_width_for"])
    def test_odd_starting_width_is_bumped_even(self, name: str) -> None:
        """``k == 8`` starts the scan at an odd width, so it is bumped."""
        width = getattr(self.module(), name)(8)
        assert width is not None
        assert width % 2 == 0

    def test_a_ladder_refuses_an_unspellable_base(self) -> None:
        """The lead is spelled first, so its width decides before any weight.

        7 is one of the four values with no even-width spelling, and a
        ladder led by it cannot be built whatever its weights are.
        """
        assert self.module()._ladder_setters((12,), 7) is None  # noqa: SLF001

    def test_a_ladder_refuses_an_unspellable_weight(self) -> None:
        """One bad weight refuses the ladder even under a legal lead.

        The base here spells at width 4, so the refusal can only come from
        the weight -- which separates this from the lead's own guard.
        """
        assert self.module()._ladder_setters((7,), 12) is None  # noqa: SLF001

    def test_a_ladder_spells_both_branches_at_one_width(self) -> None:
        """A legal ladder holds and subtracts at the same length.

        The hold is ``pp`` repeated and the subtraction is the same width,
        so no program leaks which bit it embeds through ``len()``.
        """
        got = self.module()._ladder_setters((12,), 12)  # noqa: SLF001
        assert got is not None
        setters, lead = got
        hold, code = setters[0]
        assert len(hold) == len(code)
        assert lead == code

    def test_every_tabulated_ladder_entry_computes_its_split(self) -> None:
        """Each built ladder entry is checked by arithmetic, not trust.

        The suffix was once found by a breadth-first composition over the
        rungs, then frozen as data; it is computed now, so this re-derives
        what the search used to guarantee: running the suffix over every
        rung of its ladder's stage-one vector -- through :func:`_apply`,
        the exact model of the interpreter's step -- leaves each row's
        answer in the accumulator.  ``l`` is a no-op to the model, so the
        final value is what the program prints.
        """
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
        """The gadget rule reproduces the five searched spellings, byte for byte.

        These strings are what the rung-composition search froze; the
        module now spells each from its ``(cut, slope)`` pair, so this is
        the fixture that keeps the construction honest.  The order matters
        too -- the fold is first-claim-wins over shortest-first gadgets.
        """
        module = self.module()
        assert module._LADDER_GADGETS == (  # noqa: SLF001
            "pspmsmipsp",
            "mpspmipsp",
            "smpspmipsp",
            "mmpspmipsp",
            "pspmimmipsp",
        )

    def test_the_move_algebra_refuses_what_it_cannot_place(self) -> None:
        """Each refusal in ``_fold_step`` is a placement the window forbids.

        These are the guards a plan search only meets by accident, so they
        are driven from constructed states instead: a doubling whose result
        leaves the window, a degenerate state with nothing to double, and
        an everything-wipe while two classes are still live (which would
        merge points the suffix still has to tell apart).  Each is paired
        with the state that *is* accepted, so a guard that stopped firing
        would fail here rather than silently widening the algebra.
        """
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001
        double = ("m", 0, 0, frozenset())

        # A doubling has to leave the whole state inside the window.
        too_wide = (
            (limit, 0, "a", frozenset({0})),
            (-limit, 0, "a", frozenset({1})),
        )
        assert fold_step(too_wide, double) is None

        # A single point at the origin has a zero span, which is refused by
        # the same guard's lower bound -- there is nothing to scale.
        flat = ((0, 0, "a", frozenset({0})),)
        assert fold_step(flat, double) is None

        # A state that does fit doubles: the normalization re-anchors the
        # top at 0, so what the scaling shows up as is the doubled gap.
        fits = ((10, 0, "a", frozenset({0})), (0, 0, "a", frozenset({1})))
        doubled = fold_step(fits, double)
        assert doubled is not None
        positions = sorted(p for p, _, _, _ in doubled)
        assert positions[-1] - positions[0] == 20

        # The everything-wipe merges all points onto one, so it is legal
        # only once a single class is left.
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
        """``u`` mirrors ``d``: the survivors move relative to the victim bottom.

        The two directions are separate arms of the same wipe, and only the
        dive is on the common path, so the rise is driven here directly.
        Both must land every group inside the window and keep one merged
        victim point, which is what makes the resulting state legal.
        """
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
            # One group is wiped onto the origin; the other two survive.
            assert len(moved) == 3, kind
            assert any(p == 0 for p, _, _, _ in moved), kind
            # Every id is still accounted for -- a wipe merges, never drops.
            assert {x for _, _, _, ids in moved for x in ids} == {0, 1, 2}, kind

    def test_a_wipe_whose_survivors_will_not_fit_is_refused(self) -> None:
        """The span is re-checked *after* the relocation, not only before it.

        A wipe's amount is picked from the landing window, so it always
        passes the window check -- but an extent rides along with its group
        and is not scaled by the move, so a wide enough one puts the
        relocated state outside the accumulator's range even at a legal
        amount.  That is what the second span check catches, and nothing
        earlier can: the same wipe on the same positions is accepted once
        the extent is small.
        """
        module = self.module()
        fold_step = module._fold_step  # noqa: SLF001

        positions = ((0, 10, 20), ("a", "a", "a"))
        wide = (
            (0, 6000, "a", frozenset({0})),
            (10, 0, "a", frozenset({1})),
            (20, 0, "a", frozenset({2})),
        )
        assert fold_step(wide, ("u", 1, 3004, frozenset())) is None

        # Same geometry, ordinary extent: the wipe goes through.
        narrow = tuple(
            (p, 0, c, frozenset({i}))
            for i, (p, c) in enumerate(zip(*positions, strict=True))
        )
        assert fold_step(narrow, ("u", 1, 3004, frozenset())) is not None

    def test_a_clean_amount_needs_a_frame_to_land_in(self) -> None:
        """With no room to relocate into, there is no amount to return.

        A single point has no survivor to measure a window against, so the
        frame is undefined and the caller gets ``None`` rather than an
        amount that would collide.  A state with survivors returns the
        first free landing instead.
        """
        module = self.module()
        clean_amount = module._fold_clean_amount  # noqa: SLF001
        limit = module._LIMIT  # noqa: SLF001

        assert clean_amount(((0, 0, "a", frozenset({0})),), "d", 1) is None

        spread = ((10, 0, "a", frozenset({0})), (0, 0, "b", frozenset({1})))
        for kind in ("d", "u"):
            assert clean_amount(spread, kind, 1) == limit + 1

    def test_a_reduction_gives_up_when_its_own_move_is_refused(self) -> None:
        """The rules can name a move the algebra then rejects, and that ends it.

        These are two different refusals and only one of them is "no move
        exists": here ``_fold_rule_move`` does return an op -- a rise of the
        bottom group -- but the extents riding along put the relocated state
        outside the window, so ``_fold_step`` refuses it.  The reduction
        stops rather than skipping to a second-choice move, because the
        rules are a construction and not a search.
        """
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
        # The state is unfinished and the rules do offer a move for it ...
        assert fold_done(state) is False
        move = fold_rule_move(state)
        assert move is not None
        # ... but that very move is one the algebra will not take.
        assert fold_step(state, move) is None
        assert fold_reduce(state, fold_done, budget=5) is None

    def test_a_reduction_gives_up_when_no_move_applies(self) -> None:
        """``_fold_reduce`` returns ``None`` rather than an unfinished plan.

        A state whose only candidate moves are refused cannot be driven to
        the done condition, and reporting a partial op list would hand the
        emitter a plan that does not reach the answer.  The budget is
        small here so the loop ends on the refusal, not on exhaustion.
        """
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
        """``_fold_moves`` offers the everything-wipe only where it is legal.

        It collapses every point onto one, so it is offered only once a
        single class remains -- and only when some group still carries a
        position or an extent, since collapsing an already-collapsed state
        is not a move.
        """
        module = self.module()
        fold_moves = module._fold_moves  # noqa: SLF001

        def kinds(state: object) -> list[tuple[str, int]]:
            return [(m[0], m[1]) for m in fold_moves(state)]

        one_class = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "a", frozenset({1})),
        )
        # k == len(state) is the everything-wipe.
        assert ("d", 2) in kinds(one_class)

        two_classes = (
            (10, 0, "a", frozenset({0})),
            (0, 0, "b", frozenset({1})),
        )
        assert ("d", 2) not in kinds(two_classes)

        # Already collapsed: nothing to offer at all.
        assert kinds(((0, 0, "a", frozenset({0})),)) == []

    def test_sub_units_borrows_an_i_back_to_pay_a_remainder_of_one(self) -> None:
        """A remainder of 1 cannot be spelled directly, so a whole ``i`` is broken up.

        ``s`` takes 2 and ``i`` takes 3, so the shortest spelling packs
        as many ``i`` as it can.  A remainder of 1 has no spelling of its
        own -- nothing costs a single unit -- so the rule borrows one
        ``i`` back and pays the resulting 4 as two ``s``.  Every arm is
        pinned here because the lengths are what the width arithmetic
        upstream budgets against.
        """
        module = self.module()
        sub_units = module._sub_units  # noqa: SLF001

        # Exact multiples of 3: all i, nothing left over.
        assert sub_units(3) == "i"
        assert sub_units(9) == "iii"
        # Remainder 2: one trailing s pays it exactly.
        assert sub_units(2) == "s"
        assert sub_units(5) == "is"
        # Remainder 1: borrow an i back, so 4 units spell as two s.
        assert sub_units(4) == "ss"
        assert sub_units(7) == "iss"
        assert sub_units(10) == "iiss"

        # Whatever the arm, the spelling has to be worth what was asked,
        # and no other spelling of the same value may be shorter.
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
        """When the largest power overshoots the cut, ``j`` steps down one.

        ``j`` is picked as the largest doubling that fits under the cut,
        but that first choice can leave a remainder that is negative (the
        threshold already passed the cut) or odd (``k`` pays it two units
        at a time and cannot spell a half).  Either way the only repair is
        a smaller ``j``, and the assertions just past it are what say the
        second choice always lands -- so a gadget still comes back.
        """
        module = self.module()
        ladder_gadget = module._ladder_gadget  # noqa: SLF001

        def chosen_j(cut: int) -> tuple[int, bool]:
            """Return the j the gadget settles on, and whether it backed off."""
            j = (3004 // cut).bit_length() - 1
            remainder = -(-3004 // (1 << j)) - cut
            if remainder < 0 or remainder % 2 != 0:
                return j - 1, True
            return j, False

        # The back-off is the common case, not a corner: most cuts need it.
        assert sum(chosen_j(cut)[1] for cut in range(1, 3005)) > 1000

        # A slope has to be a whole number of doublings at the settled j,
        # so it is picked from that j rather than fixed in advance.
        backed_off = ladder_gadget(1, 2 << chosen_j(1)[0])
        assert chosen_j(1)[1] is True
        assert "psp" in backed_off
        assert backed_off.endswith("ipsp")

        # A cut that does not overshoot keeps its first j, same shape.
        clean_cut = next(cut for cut in range(1, 3005) if not chosen_j(cut)[1])
        clean = ladder_gadget(clean_cut, 2 << chosen_j(clean_cut)[0])
        assert "psp" in clean
        assert clean.endswith("ipsp")

    def test_built_ladder_matches_the_frozen_witnesses(self) -> None:
        """The fold reproduces the table it replaced, entry for entry.

        These twenty-four are what the breadth-first harvest froze: the
        table each ladder-plus-suffix pair serves, and the pair the harvest
        picked for it.  Two things the fold may legitimately differ on are
        allowed for: it names two tables the harvest never listed (the
        constants, which every earlier path serves in a tenth the
        characters), and for two more it picks a shorter gadget than the
        harvest did.  What is asserted is that every frozen table is still
        served and that the pair chosen computes it -- and, where the pair
        differs, that the ladder is not what the generator emits anyway.
        """
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
                # Two tables are reached by a shorter gadget than the
                # harvest picked.  Both compute the table, and neither is
                # emitted: every earlier path serves these in a tenth the
                # characters, so the ladder is never consulted for them.
                assert module.pct_squared_minus_one(table) != module._ladder(  # noqa: SLF001
                    table, 3
                )

    def test_built_fold_skeletons_match_the_mined_plans(self) -> None:
        """The peel/park/close rule reproduces the mined plans exactly.

        These twelve are what the harvest froze: the plan for each run-length
        word the three-phase construction serves.  The module builds them
        from ``r``, ``delta`` and ``pat[1]`` now; this remembers what they
        were.  ``pat[1]`` is ignored at ``r == 5`` -- both pairs there agree
        -- so the ten distinct plans cover twelve keys.
        """
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
        """``_fold_served`` accepts exactly the buildable low-run keys.

        The predicate replaced a twelve-entry table whose comment called
        its four absences a corpus measurement.  They are structural, so
        this re-derives the set rather than pinning it: enumerating every
        run pattern reproduces the accepted keys exactly, and no key the
        predicate accepts is one no pattern can produce.

        ``delta`` is set when every middle index of the pattern is ``1``.
        For ``r`` of 2, 3 and 4 that set contains index 1, so ``delta``
        implies ``pat[1]``; at ``r == 3`` index 1 is the *only* middle, so
        the implication runs both ways there.
        """
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
        """Every shipped ladder has three weights, so only ``n == 3`` serves.

        The harvest the tabulation froze was empty at every other arity;
        the guard makes that an explicit decline rather than a lookup miss.
        """
        module = self.module()
        assert module._ladder("0110", 2) is None  # noqa: SLF001
        assert module._ladder("01" * 8, 4) is None  # noqa: SLF001


class TestPctInterleavedFold:
    """The staged replacement emits real code between its placeholders."""

    def test_interleaved_template_replays_every_three_input_row(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        table = "00001111"  # X1 creates equal suffix cofactors before X2
        template = module._interleaved_fold(table, 3)  # noqa: SLF001
        assert template is not None
        slots = [template.index("{X" + str(i) + "}") for i in range(3)]
        assert slots == sorted(slots)
        # Slots remain in stream order even when a stage coalesces directly
        # through equal branches instead of needing a relocation.
        assert template.count("{X") == 3
        for row, want in enumerate(table):
            bits = [(row >> 2) & 1, (row >> 1) & 1, row & 1]
            io = ScriptedIO()
            run(module.fill(template, bits), io)
            assert io.getvalue() == want

    # Split by cost, measured: the 256 builds are 0.28s and the 1088
    # interpreter replays are 5.15s.  The build sweep carries the contract a
    # mutant can break -- the selective count, decline-is-None, slot order --
    # so it stays in the fast run, and the exhaustive replay moves to the
    # slow-marked sibling below.  Splitting rather than sampling keeps the
    # whole 256-table space on the route-reaching half.
    def test_every_three_input_table_builds_or_declines_exactly(self) -> None:
        """Sweep all 256 three-input tables through the staged build.

        One table exercises one route; the whole space is what reaches the
        merge, split and refusal arms, and it is the only way to hold the
        two outcomes to their contracts at once.  A decline must be exactly
        ``None``, never a partial template a caller might emit.  That a
        build *computes* its table is the sibling's job.
        """
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
            assert slots == sorted(slots), table  # slots stay in stream order
        # The route is selective by design -- it runs before the all-row
        # fallback -- so pin that it neither builds everything nor nothing.
        assert built == 136

    @pytest.mark.slow  # ~5s: 1088 interpreter replays
    def test_every_three_input_build_computes_its_table(self) -> None:
        """Every table the route builds is replayed row by row.

        A template that computes the wrong table is worse than a decline, so
        the rows are checked on the interpreter rather than the shape being
        trusted.  The build half runs in the fast loop; this is the half that
        costs interpreter time.
        """
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

    @pytest.mark.slow  # ~10s: 4096 four-input builds
    def test_four_input_tables_build_or_decline_without_raising(self) -> None:
        """At four inputs the merge has room to act, so its arms are reached here.

        Build-only on a stride: what is under test is that every table
        either yields a well-formed template or declines cleanly.  A raise
        would mean the planner emitted a move its own algebra refuses,
        which is the failure the guards exist to prevent, and no amount of
        row replay would reveal it if the build never returned.
        """
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
        """A late-ignored suffix stays compact instead of spending 4096 rungs.

        Rows are *sampled* on a stride, as at eleven inputs above: the build
        itself is instant, and all 4096 rows through the interpreter were
        seven seconds of this module's budget for one table.  The stride is
        coprime to the arity's runs and covers all four values of the two
        bits the table actually reads, so every branch of the answer is
        still executed -- the suffix is ignored by construction, which is
        the property under test.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        n = 12
        # XOR of the first two bits: it is neither a cascade subcube nor a
        # threshold, and the all-row fold cannot lay its 4096 positions.
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
    """The emitter's mirror, driven at the steps the planner rarely asks for.

    :class:`_FoldEmitter` tracks every row's accumulator exactly, so its
    moves can be checked as arithmetic: build one over a small table and
    read ``pos`` before and after.  ``s`` subtracts 2 and ``i`` subtracts
    3, and ``p`` negates, so a rise is spelled as a negated descent.
    """

    @staticmethod
    def emitter(table: str = "01", n: int = 1):
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        return module._FoldEmitter(table, n)  # noqa: SLF001

    def test_a_zero_step_emits_nothing(self) -> None:
        """Moving by zero is not spelled at all, in either direction."""
        for move in ("descend", "plain_rise"):
            em = self.emitter()
            getattr(em, move)(0)
            assert em.body == []

    def test_a_single_step_is_spelled_as_three_against_two(self) -> None:
        """One has no spelling of its own: ``s`` is 2 and ``i`` is 3.

        So a step of 1 is a step of 3 the other way against a step of 2
        back -- the only combination of the two primitives that lands one
        away.  Both directions net exactly one, and every row moves
        together, since the accumulator is shared.
        """
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
        """The last shift is a residue, and only one lift of it fits.

        ``finish`` moves the surviving point onto its answer byte, which
        pins it only modulo 256.  Taken as a positive residue that shift
        can exceed the headroom to the limit, so it is lowered by 256 until
        it fits -- the same residue, reached from below.  A point near the
        ceiling therefore ends up *under* where it started while still
        landing on the byte.
        """
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
        """``p`` needs two to work with, so a shorter rise makes room.

        The rise is ``p``, a subtraction, ``p``, and the subtraction has
        no spelling below 2.  When the victims sit so high that the
        relocation leaves less than that, the emitter drops everything
        first and recomputes the distance from the new bottom.  A victim
        one lower needs no preshift, which is what separates the two.
        """
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        limit = module._LIMIT  # noqa: SLF001

        def rise_from(victim_top: int) -> list[str]:
            em = self.emitter()
            keys = list(em.pos)
            em.pos = {keys[0]: victim_top, keys[1]: -10}
            em.cls = {keys[0]: "0", keys[1]: "1"}
            em.rise(limit + 1, frozenset({keys[0]}))
            return em.body

        # u == 1: below the floor, so a preshift of 1 is spelled first.
        assert rise_from(limit) == ["i", "psp", "psp", "s"]
        # u == 2: exactly the floor, so the rise is spelled on its own.
        assert rise_from(limit - 1) == ["psp", "s"]


class TestPctFoldMoves:
    """The fold's move generator, at the guards that refuse a relocation.

    A ``_FoldPoint`` is ``(top, span, class, ids)`` and a state is a tuple
    of them.  The guards below are properties of the arithmetic, so they
    are driven with states built by hand: the spacings involved are wider
    than any table's own starting layout, which is four per run.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_a_collision_across_classes_is_not_a_merge(self) -> None:
        """Two points at one value are indistinguishable forever after.

        So a collision is legal only within a class -- and only between
        points already wiped, since a group with extent has rows at
        several values and an equal top is not an equal anything.
        """
        module = self.module()
        merge = module._fold_merge  # noqa: SLF001

        cross = [(0, 0, "0", frozenset({0})), (0, 0, "1", frozenset({1}))]
        assert merge(cross) is None

        extent = [(0, 0, "0", frozenset({0})), (0, 3, "0", frozenset({1}))]
        assert merge(extent) is None

        legal = [(0, 0, "0", frozenset({0})), (0, 0, "0", frozenset({1}))]
        assert merge(legal) == ((0, 0, "0", frozenset({0, 1})),)

    def test_a_survivor_reaching_below_the_victims_offers_no_window(self) -> None:
        """The relocation window is the gap to the nearest survivor's bottom.

        A survivor whose span reaches down past the victims' top closes
        that gap entirely, so there is no amount to relocate by and the
        dive is skipped rather than spelled.  Both the ascending and the
        descending half apply the same rule.
        """
        state = (
            (0, 400, "0", frozenset({0})),
            (-100, 0, "0", frozenset({1})),
            (-200, 0, "1", frozenset({2})),
        )
        assert len(list(self.module()._fold_moves(state, kcap=3))) == 1  # noqa: SLF001

    def test_a_relocation_that_would_overflow_the_span_is_skipped(self) -> None:
        """Every wipe caps the spread, so a move that widens it is refused.

        Two survivors far from *each other* are what reaches this: the
        near one bounds how far the state may travel, and the far one is
        still far after travelling that distance.  The guard is what keeps
        the yielded states inside the accumulator's range, so it is
        checked on the output rather than only executed.
        """
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
    """The rule construction's refusals, driven through their own guards.

    :func:`_fold_reduce` runs the case analysis of ``_fold_rule_move`` to a
    ``done`` state.  It answers ``None`` rather than raising when no rule
    applies or the budget runs out, so the refusals are reachable without
    contriving an unsolvable table.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    #: Four points, alternating classes: not already finished, and small
    #: enough that the rules answer quickly.
    STATE = (
        (0, 0, "0", frozenset({0})),
        (-4, 0, "1", frozenset({1})),
        (-8, 0, "0", frozenset({2})),
        (-12, 0, "1", frozenset({3})),
    )

    def test_the_reduction_gives_up_on_its_budget(self) -> None:
        """A budget of zero takes no step and answers ``None``.

        The default budget is derived from the state and is a latency
        guard the corpus never reaches; passing one drives the refusal
        without a state the rules genuinely dead-end on.
        """
        module = self.module()

        done = module._fold_done  # noqa: SLF001
        assert module._fold_reduce(self.STATE, done, budget=0) is None  # noqa: SLF001

    def test_the_reduction_finishes_when_it_is_given_room(self) -> None:
        """The positive control: the refusal above is the budget.

        Without this a ``None`` could just as well mean the state was
        malformed, or that no rule ever applies to it.
        """
        module = self.module()

        ops = module._fold_reduce(self.STATE, module._fold_done)  # noqa: SLF001
        assert ops is not None
        state = module._fold_norm(list(self.STATE))  # noqa: SLF001
        for op in ops:
            state = module._fold_step(state, op)  # noqa: SLF001
            assert state is not None
        assert module._fold_done(state)  # noqa: SLF001

    def test_no_rule_applies_to_a_walled_state(self) -> None:
        """Spans that fill the workspace leave the case analysis empty.

        Two groups whose extents nearly fill the workspace offer no legal
        wipe in either direction -- the gap ``q1`` is negative both ways --
        and the spread is past the doubling bound, so every case falls
        through and the move is ``None``.
        """
        module = self.module()

        stuck = (
            (0, 3000, "0", frozenset({0})),
            (-10, 3000, "1", frozenset({1})),
        )
        assert module._fold_rule_move(stuck) is None  # noqa: SLF001

    def test_a_step_the_state_does_not_offer_answers_none(self) -> None:
        """``_fold_step`` re-checks a move rather than trusting it.

        An amount outside the window, a wipe with mixed-class victims, and
        an everything-wipe on a two-class state are each refused, so an op
        that was never legal cannot be applied by accident.
        """
        module = self.module()

        outside = ("d", 1, 99999, frozenset({3}))
        assert module._fold_step(self.STATE, outside) is None  # noqa: SLF001
        mixed = ("d", 2, 3004, frozenset({2, 3}))
        assert module._fold_step(self.STATE, mixed) is None  # noqa: SLF001
        everything = ("d", 4, 3004, frozenset({0, 1, 2, 3}))
        assert module._fold_step(self.STATE, everything) is None  # noqa: SLF001

    def test_a_clean_amount_skips_an_occupied_landing(self) -> None:
        """The first collision-free amount is computed, not the minimum.

        A survivor sitting exactly 3004 above the victims occupies the
        window's first value, so the clean amount is 3005 -- landing there
        would be a merge the algebra refuses when the classes differ.
        """
        module = self.module()

        state = (
            (0, 0, "1", frozenset({0})),
            (-3004, 0, "0", frozenset({1})),
        )
        assert module._fold_clean_amount(state, "d", 1) == 3005  # noqa: SLF001


class TestPctFoldPlan:
    """The plan's rotation pre-pass, and the bound that refuses a table.

    ``_fold_plan`` wipes every group that still has extent before the
    rules run, because a group with extent cannot be a collision target.
    The pre-pass stops on its own when no such wipe is on offer.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_the_pre_pass_stops_when_no_bottom_wipe_is_offered(self) -> None:
        """Extent that no minimum-relocation wipe can clear ends the plan.

        Two groups whose spans nearly fill the workspace leave no room for
        the relocation a wipe needs, so the pre-pass breaks out with the
        extent still there and the rules that follow have nothing to
        work with.  The answer is ``None``, not a partial plan.
        """
        stuck = (
            (0, 3000, "0", frozenset({0})),
            (-10, 3000, "1", frozenset({1})),
        )
        assert self.module()._fold_plan(stuck) is None  # noqa: SLF001

    def test_the_pre_pass_clears_extent_when_it_can(self) -> None:
        """The positive control: ordinary extent is wiped and descends.

        Three groups with room around them plan normally, so the refusal
        above is the geometry and not the presence of extent.
        """
        ok = (
            (0, 8, "0", frozenset({0, 1, 2})),
            (-40, 8, "1", frozenset({3, 4, 5})),
            (-80, 8, "0", frozenset({6, 7, 8})),
        )
        plan = self.module()._fold_plan(ok)  # noqa: SLF001
        assert plan is not None
        assert plan

    def test_a_reduction_that_cannot_finish_leaves_the_plan_empty(self) -> None:
        """The pre-pass can clear extent the rules still cannot use.

        Here the wipes run to completion but the reduction that follows
        reaches no two-point state -- every case of the rule analysis
        falls through -- so the whole plan is ``None`` and the caller
        moves on to the next construction rather than emitting a partial
        one.
        """
        state = (
            (-40, 0, "0", frozenset({0})),
            (-48, 0, "1", frozenset({1})),
            (-3048, 8, "1", frozenset({2})),
            (-3448, 4, "0", frozenset({3})),
            (-3452, 400, "1", frozenset({4})),
        )
        assert self.module()._fold_plan(state) is None  # noqa: SLF001

    def test_a_table_too_wide_for_the_workspace_is_refused(self) -> None:
        """The ladder must fit the workspace, and the packed one fits longest.

        The emitter lays the rows from a zero accumulator, so a ladder has to
        fit ``[-_LIMIT, _LIMIT]`` -- not the ``2 * _LIMIT`` span a *relative*
        plan state may occupy.  Checking only the latter lets the planner spend
        thousands of moves on a geometry the emitter refuses on its first op.

        Which ladder is offered sets the reach.  The uniform ones spend
        ``step * (2**n - 1)`` and give out at nine and ten inputs; the packed
        ladder spends only ``2**n + 1`` and carries eleven.  Twelve exceeds
        even that, so no ladder is offered and the fold refuses.
        """
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001

        # Each ladder in turn gives out one or two arities later than the last.
        assert limit < module._FOLD_STEP * (2**10 - 1)  # noqa: SLF001
        assert limit < module._FOLD_NARROW_STEP * (2**11 - 1)  # noqa: SLF001
        assert sum(module._fold_subset_weights(11)) <= limit  # noqa: SLF001
        assert module._fold_subset_weights(12) is None  # noqa: SLF001

        # Nothing serves twelve inputs, so the fold declines.  The table has
        # to be one the fold would otherwise plan: ``"01" * 2048`` alternates
        # every row, which is 4096 runs and a subcube the *cascade* builds,
        # so it never reaches the fold at all.  A low-run table does.
        wide = "".join(str(((r >> 11) & 1) ^ ((r >> 10) & 1)) for r in range(2**12))
        assert module._cascade(wide, 12) is None  # noqa: SLF001
        assert module._fold(wide, 12) is None  # noqa: SLF001
        # A table inside the bound still builds, so the ``None`` above is
        # the workspace and not the arity itself.
        assert module._fold("0011", 2) is not None  # noqa: SLF001

    def test_the_packed_ladder_meets_the_distinctness_floor(self) -> None:
        """``2**n + 1`` is the least a distinct-position ladder can span.

        The ``2**n`` subset sums are distinct non-negative integers, so the
        largest is at least ``2**n - 1``.  The minimum weight is 2 -- ``2a +
        3b`` cannot spell 1 -- so no subset sums to 1, and by symmetry none
        sums to ``S - 1``; two values inside ``[0, S]`` are unattainable and
        ``S >= 2**n + 1``.  The shipped ladder meets that exactly, which is
        what buys the arity over a uniform one.
        """
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
        """Both branches match in width, and odd-width amounts are respelled.

        The identity has no odd-width spelling, so an amount whose cheapest
        subtraction is one character (2, spelled ``"s"``) can never be padded
        to match a hold and is respelled wider instead.  Both ladders contain
        such an amount.  Checked by execution, not by reading the spelling.
        """
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
        # The whole chain lays every row exactly where the ladder says.
        positions = module._fold_positions(n, weights)  # noqa: SLF001
        for row in (0, 1, 2, 2**n - 1):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            code = "".join(setters[i][bits[i]] for i in range(n))
            assert module._apply(0, code) == positions[row]  # noqa: SLF001

    def test_every_setter_amount_past_the_reset_line_spells(self) -> None:
        """Amounts at and above the reset line respell by descending.

        The overshoot respelling negates, so from 3002 up it leaves the
        accumulator above the 3003 reset: the reset zeroes it and the
        add-back nets ``+k`` rather than ``-amount``.  All 1504 amounts in
        3002..6008 failed that way and *raised* instead of declining, which
        ``_interleaved_fold`` reaches through ``span + 2`` once the spread
        hits 3000.  A pure ``s``/``i`` descent never rises, so it has no
        such ceiling.

        The whole range a setter can be asked for is checked, since
        positions span ``+-_LIMIT``: the widest gap is 6006 and the caller
        adds 2.  Boundaries are checked by execution.
        """
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001
        for amount in (3002, 3003, 3006, 6006, 2 * limit + 2):
            zero, one = module._fold_setters(1, (amount,))[0]  # noqa: SLF001
            assert len(zero) == len(one), amount
            assert module._apply(0, zero) == 0, amount  # noqa: SLF001
            assert module._apply(0, one) == -amount, amount  # noqa: SLF001

    @pytest.mark.slow  # ~5s: ten inputs, 1024 rows filled and run
    def test_a_low_run_ten_input_table_builds_and_runs(self) -> None:
        """A low-run ten-input table takes the skeleton path, and lays.

        This is the regression the ladder gate closed.  ``x0 ^ x1`` widened
        to ten inputs has three runs, so it is no subcube (the cascade
        misses) and reaches the fold, where ``_fold_construct``'s ``r <= 5``
        skeletons plan it in three ops.  Those skeletons were mined on the
        wide ladder, whose ten-input span is 4092 against a 3003-value
        workspace -- so the emitter could not lay the plan, and the build
        died on a bare ``AssertionError`` rather than building or refusing.

        On the narrow ladder the same plan lays.  Every row is executed,
        because a plan that the emitter accepts is still not evidence that
        the program computes the table.
        """
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

    @pytest.mark.slow  # ~14s: eleven inputs, a sampled row sweep
    def test_the_packed_ladder_reaches_eleven_inputs(self) -> None:
        """Eleven inputs build on the packed ladder and print correctly.

        The uniform ladders both overrun the workspace here -- 8188 and 4094
        against 3003 -- so this arity exists only because the packed ladder
        spends ``2**n + 1``.  Rows are *sampled* rather than swept: all 2048
        take about two minutes on the interpreter, well past this module's
        budget, and the full sweep is a notes probe instead.
        """
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
        for row in range(0, 2**n, 97):  # a stride coprime to the arity's runs
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], f"row {row}"
        assert len(widths) == 1, widths

    @pytest.mark.slow  # generic twelve-input fold: ~12s to plan
    def test_interleaved_fold_builds_a_generic_twelve_input_table(self) -> None:
        """A centred final embed escapes the all-row ladder's limit."""
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

    @pytest.mark.slow  # packed prefix + sixteen-class compaction: ~60s to plan
    def test_interleaved_fold_builds_a_generic_thirteen_input_table(self) -> None:
        """The packed prefix ladder compacts to its cofactors before laying.

        Thirteen inputs need the eleven-input packed ladder, whose unit gaps
        jam the conveyor; the pre-lay compaction to at most sixteen cofactor
        points, and the collision-free split total, are what this exercises.
        """
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
        """No plan means no template, not a partial one.

        Every table tried plans successfully -- the fold is documented as
        found in practice rather than proved total -- so the refusal is
        driven by making the planner decline instead of hunting for a
        table that defeats it.  The table used here builds normally when
        the planner is left alone.
        """
        module = self.module()
        assert module._fold("0011", 2) is not None  # noqa: SLF001

        monkeypatch.setattr(module, "_fold_plan", lambda *_a, **_k: None)
        assert module._fold("0011", 2) is None  # noqa: SLF001


class TestPctAffineSolver:
    """The wide band's line solver, at the inputs it has to refuse.

    ``_solve_affine`` fits ``a * v + b == p`` over a fixed grid of
    multipliers and offsets, dividing rather than searching: two points
    with distinct values determine the line.  Constant values leave the
    multiplier free, which is the separate arm below.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_the_shorter_of_cascade_and_affine_ships(self) -> None:
        """The cascade is usually shorter at three inputs, but not always.

        The dispatch used to return it on sight, which served 44 of 256
        tables a longer program than the affine path builds.  Both are
        cheap at this arity, so both are built and the shorter kept;
        ``00000101`` is the worst case, 40 characters against 33.
        """
        module = self.module()
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            shipped = len(boolean.pct_squared_minus_one(table))
            cascade = module._cascade(table, 3)  # noqa: SLF001
            assert cascade is None or shipped <= len(cascade), table
            improved += cascade is not None and shipped < len(cascade)
        assert improved == 42  # the other two tie, keeping the cascade

    def test_affine_stays_gated_above_three_inputs(self) -> None:
        """The comparison must not reach the four-input enumeration.

        ``_affine`` derives a whole arity at once -- 36458 composition
        states at n == 4, about two minutes a table -- so the deep band
        serves those instead.  Building both would pay that cost on every
        four-input table, served or not.
        """
        module = self.module()
        assert module._affine.__doc__  # noqa: SLF001
        parity4 = "".join(str(bin(row).count("1") % 2) for row in range(16))
        # The deep band answers this instantly; reaching _affine would not.
        start = time.perf_counter()
        boolean.pct_squared_minus_one(parity4)
        assert time.perf_counter() - start < 10.0

    def test_constant_values_cannot_meet_differing_wants(self) -> None:
        """One value cannot map to two answers, whatever the line.

        With every ``value`` equal there is no second point to fix the
        multiplier, so the fit is possible only when every ``wanted`` is
        equal too.  Mixed wants are refused before the grid is searched.
        """
        solve = self.module()._solve_affine  # noqa: SLF001

        assert solve((5, 5, 5), (1, 2, 3)) is None
        # The same shape with one want is solvable, so the refusal is the
        # disagreement and not the constant values.
        assert solve((0, 0), (4, 4)) == (0, 4)

    def test_a_constant_want_outside_the_offset_grid_is_refused(self) -> None:
        """The offset has to be one the language can spell.

        With the values all zero the offset *is* the wanted value, so a
        want beyond the grid leaves no multiplier that helps -- the loop
        runs out rather than returning a line off the grid.
        """
        module = self.module()
        beyond = max(module._WIDE_B_VALS) + 100  # noqa: SLF001

        assert module._solve_affine((0, 0), (beyond, beyond)) is None  # noqa: SLF001
        assert module._solve_affine((0, 1), (3, 5)) == (2, 3)  # noqa: SLF001

    def test_a_multiplier_off_the_grid_drops_the_realisation(self) -> None:
        """A ratio the grid does not carry is skipped, not rounded.

        ``_realisations`` divides the two differences by the pivot gap, and
        a quotient outside the admitted multipliers cannot be spelled, so
        that placement is dropped.  Values a few apart realise many ways;
        values a thousand apart realise none.
        """
        realise = self.module()._realisations  # noqa: SLF001

        assert realise((0, 1, 2, 3))
        assert realise((0, 1000, 1, 3)) == []


class TestPctAffineBand:
    """The three-input band's two skips, which the shipped budget hides.

    ``_affine`` weighs its candidate pre-vectors cheapest first and stops
    after :data:`_CANDIDATES` of them.  Both guards below sit past that
    cut at the shipped value of 12 -- measured over all 256 three-input
    tables, neither runs -- because the vectors that trip them are built
    from the largest offsets and sort last.  They are not dead: widening
    the budget reaches both, which is what these tests do.  The budget is
    a bound on *program length*, not on which tables build, so widening
    it changes nothing about the answers.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    def test_the_shipped_budget_stops_before_both_skips(self) -> None:
        """The premise: at 12 candidates neither guard is reached.

        Without this the tests below would look like ordinary coverage of
        a path the generator walks every day, when in fact the shipped
        configuration never gets there.
        """
        module = self.module()
        assert module._CANDIDATES == 12  # noqa: SLF001

    def test_a_candidate_with_no_realisation_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Solving the two halves does not mean the vector can be spelled.

        ``_solve_affine`` asks whether a line exists over the grid;
        ``_realisations`` asks whether the pair of setters that produce
        the vector can be written down.  A candidate can pass the first
        and fail the second, and then it is dropped rather than priced.
        """
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
        """The final setter is solved again against the answer bits.

        The earlier solves fit the table's own halves; this one fits the
        0/1 the program actually prints, both ways round.  One of the two
        can fail where the halves succeeded, and that spelling is passed
        over rather than emitted half-formed.
        """
        module = self.module()
        values = (12, 12, 12, 13)
        even, odd = (0, 0, 0, 0), (0, 0, 0, 1)

        assert module._solve_affine(values, even) is not None  # noqa: SLF001
        assert module._solve_affine(values, odd) is not None  # noqa: SLF001
        # Relabelling with one=0, other=1 leaves the odd half unsolvable.
        relabelled = tuple(0 if bit else 1 for bit in odd)
        assert module._solve_affine(values, relabelled) is None  # noqa: SLF001

        monkeypatch.setattr(module, "_CANDIDATES", 1000)
        assert module._affine("00000001", 3) is not None  # noqa: SLF001


class TestPctFoldSkeletonResolver:
    """The tabulated planner's refusals, driven on constructed states.

    ``_fold_construct`` builds a plan with :func:`_fold_skeleton` and
    resolves each symbolic amount against the live state, so every refusal
    is a property of the *geometry* rather than of a table.  Building the
    states directly is what reaches them: a wipe that leaves no survivor and
    a landing that does not match are both shapes the fold's own planner
    steers around, so no generated table drives one.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

    #: One point: whichever way it is wiped, nothing survives.
    LONE = ((0, 0, "a", frozenset({0})),)

    #: Two points of one class, four apart and both already wiped.
    PAIR = (
        (0, 0, "a", frozenset({0})),
        (-4, 0, "a", frozenset({1})),
    )

    @pytest.mark.parametrize("kind", ["d", "u"])
    def test_geometry_refuses_a_wipe_that_leaves_no_survivor(self, kind: str) -> None:
        """Both branches measure the window against the survivors."""
        module = self.module()
        assert module._fold_geometry(self.LONE, kind, 1) is None  # noqa: SLF001

    def test_resolve_passes_on_a_wipe_with_no_geometry(self) -> None:
        """A symbolic amount cannot be resolved where the window does not exist."""
        module = self.module()
        assert module._fold_resolve(self.LONE, "d", 1, "cmax") is None  # noqa: SLF001

    def test_resolve_refuses_a_landing_index_past_the_survivors(self) -> None:
        """``landN`` names a survivor by index, and one wipe leaves only one."""
        module = self.module()
        assert module._fold_resolve(self.PAIR, "d", 1, "land9") is None  # noqa: SLF001

    def test_resolve_refuses_a_landing_that_does_not_match(self) -> None:
        """A landing is a merge, so span, class and window all have to agree."""
        module = self.module()
        assert module._fold_resolve(self.PAIR, "d", 1, "land0") is None  # noqa: SLF001

    def test_construct_emits_an_empty_plan_for_a_finished_state(self) -> None:
        """Two wiped points of different classes is what ``_fold_done`` accepts."""
        module = self.module()
        finished = (
            (0, 0, "a", frozenset({0})),
            (-5, 0, "b", frozenset({1})),
        )
        assert module._fold_construct(finished) == []  # noqa: SLF001
