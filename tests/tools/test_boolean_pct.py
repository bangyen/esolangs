"""Unit tests for the %^2^-1 boolean generator.

Covers :mod:`esolangs.tools.boolean.pct_squared_minus_one`, split out of
``test_boolean_parameterized.py``: the generator derives its programs through
several ordered constructions and its tests are the second-largest block
there.
"""

import importlib

import pytest


class TestParameterizedPctSquaredMinusOne:
    """Input-by-substitution boolean generator for %^2^-1.

    The Lean proof in ``Esolangs.PctBooleanWall`` shows no %^2^-1 program
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
            ("0110", 2),  # XOR -- the function the Lean wall forbids a reader
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

        This is what separates the generator from the model the Lean wall
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
    def test_fold_beams_the_states_too_wide_to_search(self) -> None:
        """A 21-point table plans quickly instead of exhausting the search.

        The beam's target is what makes this table cheap.  With the target
        set just under the width at which the exhaustive search starts to
        struggle, a 21-point state was too wide to search and too narrow to
        beam: the search explored for fifty seconds and gave up, so the
        generator *refused a table it can build*.  Beaming to eight points
        plans it in under a second.  Pinned as the regression, and executed
        rather than merely planned, because a plan that does not compute is
        not a fix.
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

    def test_parameter_sets_leaving_one_vector_are_searched_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Distinct ladder parameters can leave the same rungs.

        The suffix search depends only on the stage-one vector, so a repeat
        of one is skipped rather than swept again.  No shipped pair
        collides, so the guard is driven by duplicating an entry: the
        tables built must be exactly those the single entry builds.
        """
        module = self.module()
        entry = ((250, 500, 250), 1000)

        monkeypatch.setattr(module, "_LADDERS", (entry, entry))
        module._ladder_tables.cache_clear()  # noqa: SLF001
        twice = module._ladder_tables(3)  # noqa: SLF001

        monkeypatch.setattr(module, "_LADDERS", (entry,))
        module._ladder_tables.cache_clear()  # noqa: SLF001
        once = module._ladder_tables(3)  # noqa: SLF001

        assert twice == once
        # The cache outlives the patch, so the shipped table has to be the
        # one memoized when this test leaves.
        module._ladder_tables.cache_clear()  # noqa: SLF001


class TestPctFoldEmitter:
    """The emitter's mirror, driven at the steps the descent rarely asks for.

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
