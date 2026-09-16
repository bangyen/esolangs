"""Covers :mod:`esolangs.tools.pct_squared_minus_one` end to end.

The routes with modules of their own have files to match:
test_boolean_pct_fold and test_boolean_pct_helpers.
"""

import importlib
import time

import pytest

from esolangs import tools as boolean


def _cross_class_diffs(truth_table: str, n: int) -> list[tuple[int, ...]]:
    """Difference vectors of the row pairs a weighting must keep apart.

    The oracle for the deep band's legality test.  Two rows collide when
    their weighted sums tie, and a tie is a vanishing signed combination of
    the weights: writing ``d`` for the coordinatewise difference of the two
    rows' bits, the pair collides under ``units`` and ``mask`` exactly when
    ``sum(u_k * (-1)**mask_k * d_k) == 0``.  Only pairs of *different* class
    matter, and a vector and its negation forbid the same weightings, so
    each is kept once.  This walks every row pair; the shipped test reads
    class purity off the weighted values instead, and the test below holds
    the two to the same verdict.
    """
    seen: set[int] = set()
    size = 2**n
    for row in range(size):
        for other in range(row + 1, size):
            if truth_table[row] == truth_table[other]:
                continue
            # ``other > row``, so the highest bit the two differ on is
            # always other's: ``other & ~row`` therefore always exceeds
            # ``row & ~other``, and the canonical order is the swap every
            # time rather than a comparison.
            plus, minus = other & ~row, row & ~other
            seen.add((plus << n) | minus)
    diffs = []
    for key in seen:
        plus, minus = key >> n, key & (size - 1)
        diffs.append(
            tuple(
                ((plus >> (n - 1 - k)) & 1) - ((minus >> (n - 1 - k)) & 1)
                for k in range(n)
            )
        )
    return sorted(diffs)


def _weighting_is_legal(
    units: tuple[int, ...], mask: int, diffs: list[tuple[int, ...]]
) -> bool:
    """Whether no cross-class pair collides under this weighting."""
    for diff in diffs:
        total = 0
        for k, unit in enumerate(units):
            total += -unit * diff[k] if (mask >> k) & 1 else unit * diff[k]
        if total == 0:
            return False
    return True


class TestParameterizedPctSquaredMinusOne:
    """Input-by-substitution boolean generator for %^2^-1.

    The wall proved for %^2^-1 (``the relevant tests``) shows no program
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
        from esolangs.tools.examples import _fill_pct_squared_minus_one

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
        from esolangs.tools import parameterized

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
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.pct_squared_minus_one(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_pct(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_instantiations_share_a_length(self) -> None:
        """All four programs are the same length, so none leaks its inputs."""
        from esolangs.tools import parameterized

        template = parameterized.pct_squared_minus_one("0110")
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, lengths

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools import parameterized

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
        from esolangs.tools import parameterized

        for table_int in range(16):
            template = parameterized.pct_squared_minus_one(format(table_int, "04b"))
            for a in (0, 1):
                for b in (0, 1):
                    assert "n" not in self.instantiate(template, [a, b])

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
        from esolangs.tools import parameterized

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
        from esolangs.tools import parameterized

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
        from esolangs.tools import parameterized

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
        from esolangs.tools.pct_squared_minus_one import _cascade

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
        from esolangs.tools import parameterized
        from esolangs.tools.pct_squared_minus_one import _cascade

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
        from esolangs.tools import parameterized

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
        from esolangs.tools import parameterized

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
        from esolangs.tools import parameterized

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
        from esolangs.tools.pct_squared_minus_one import (
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
        from esolangs.tools import parameterized

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
        from esolangs.tools.pct_squared_minus_one import _HEADER_END, _fold

        table = "00000101"
        template = _fold(table, 3)
        assert template is not None
        # The body, not the header: the ``m`` is the doubling the body does.
        body = template.partition(_HEADER_END)[2]
        assert "m" in body, "the doubling never fired"
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
        from esolangs.tools.pct_squared_minus_one import _fold

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
        from esolangs.tools.pct_squared_minus_one import _fold

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
        from esolangs.tools.pct_squared_minus_one import _fold

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
        from esolangs.tools import parameterized

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
        from esolangs.tools.pct_squared_minus_one import (
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
        from esolangs.tools.pct_squared_minus_one import _deep_band

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
        from esolangs.tools.pct_squared_minus_one import _affine

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
        from esolangs.tools.pct_squared_minus_one import _affine

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
        from esolangs.tools.pct_squared_minus_one import _affine

        assert _affine("0110", 2) is None
        assert _affine("0110100110010110", 4) is None

    def test_cascade_reach_is_exactly_the_subcubes(self) -> None:
        """The cascade builds exactly the tables that are a subcube or one's
        complement, which is what its docstring claims at any arity.

        Checked at three inputs against the whole arity.  A subcube here is
        the 1-set agreeing on some inputs and free on the rest, so the count
        of ones is ``2 ** (free inputs)``.
        """
        from esolangs.tools.pct_squared_minus_one import _cascade

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

        Pinned because a counterexample would not raise: the planner would
        return ``None``, the loop would move on, and the only visible effect
        would be a longer program from a later construction.  Failures do
        exist outside the budget, at ``sum(units) * 256`` past the limit,
        which is why :func:`_deep_weightings` drops those.
        """
        from esolangs.tools.pct_squared_minus_one import (
            _deep_plan,
            _deep_values,
            _deep_weightings,
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
        from esolangs.tools.pct_squared_minus_one import (
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
        from esolangs.tools.pct_squared_minus_one import _deep_band

        parity = "".join(str(bin(r).count("1") % 2) for r in range(32))
        majority = "".join("1" if bin(r).count("1") >= 3 else "0" for r in range(32))
        assert _deep_band(parity, 5) is not None
        assert _deep_band(majority, 5) is not None
        # One flipped row breaks the popcount symmetry and is screened out.
        asymmetric = list(parity)
        asymmetric[7] = "0" if asymmetric[7] == "1" else "1"
        assert _deep_band("".join(asymmetric), 5) is None

    def test_deep_band_zeroes_the_unit_of_an_ignored_input(self) -> None:
        """Below the screen a weighting may drop an input the table ignores.

        Three-input parity padded with an ignored first input has no
        class-boundary flip on that input, so it is not a singleton and the
        walk keeps weightings with a zero unit there -- and takes one: the
        served setter for input 0 holds on both branches.  Every weighting
        with a zero unit on an *essential* input is skipped before any mask
        is tested.  Executed on all sixteen rows.
        """
        from esolangs.interpreters.io import IO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools.pct_squared_minus_one import (
            _deep_band,
            fill,
            pct_squared_minus_one,
        )

        table = "0110100101101001"
        template = _deep_band(table, 4)
        assert template is not None
        assert template.startswith("0=|;")
        assert pct_squared_minus_one(table) == template

        class Capture(IO):
            def __init__(self) -> None:
                super().__init__()
                self.out: list[str] = []

            def print_char(self, char: str) -> None:
                self.out.append(char)

        for row in range(16):
            bits = [(row >> (3 - i)) & 1 for i in range(4)]
            io = Capture()
            run(fill(template, bits), io)
            assert "".join(io.out) == table[row], (row, io.out)

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
        from esolangs.tools import parameterized
        from esolangs.tools.pct_squared_minus_one import _affine, _cascade

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
        from esolangs.tools.pct_squared_minus_one import (
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
        from esolangs.tools.pct_squared_minus_one import (
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

    def test_spell_bases_follow_the_direct_rule(self) -> None:
        """Every grid map is derived with the required width parities."""
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        bases = module._spell_bases()  # noqa: SLF001
        longest = 0
        for a in module._WIDE_A_VALS:  # noqa: SLF001
            for b in module._WIDE_B_VALS:  # noqa: SLF001
                direct = module._wide_affine_code(a, b)  # noqa: SLF001
                even, odd = bases[a, b]
                if a == 0:
                    assert (even, odd) == (direct, None)
                    codes = (direct,)
                else:
                    other = direct + module._ODD_AFFINE_IDENTITY  # noqa: SLF001
                    expected: list[str | None] = [None, None]
                    expected[len(direct) % 2] = direct
                    expected[len(other) % 2] = other
                    assert (even, odd) == tuple(expected)
                    codes = (direct, other)
                longest = max(longest, *(len(code) for code in codes))
                assert all(
                    module._apply(value, code) == a * value + b  # noqa: SLF001
                    for code in codes
                    for value in module._SPELL_WINDOW  # noqa: SLF001
                )
        assert longest == module._SPELL_MAX == 18  # noqa: SLF001

    def test_every_derived_spelling_behaves_at_every_width(self) -> None:
        """Each width's string realises its map, padding included.

        The spellings derive from :func:`_spell_bases` -- one base per parity,
        widened by ``pp`` suffixes, or by ``s`` prefixes where
        the erase forgets them -- so this checks the *derived* strings, not
        just the bases: every entry of every map's width dict is run over
        the admission window and must land on ``a*x + b`` exactly.
        """
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
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
        from esolangs.tools.pct_squared_minus_one import _affine_code, _apply

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

    def test_a_tail_is_not_always_available(self) -> None:
        """Not every pair of class values can be printed apart.

        The tail has to land the one-class on exactly 1 and the zero-class
        on 0 (or past the reset limit).  Two classes that share a value are
        the clearest case that no tail can separate -- ``l`` prints one
        accumulator, so identical inputs cannot print differently.
        """
        from esolangs.tools.pct_squared_minus_one import _tail_for

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
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        from esolangs.tools.pct_squared_minus_one import _derive

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_solution", lambda *_a, **_k: None)
            assert _derive("0110") is None


class TestPctAffineSolver:
    """The wide band's line solver, at the inputs it has to refuse.

    ``_solve_affine`` fits ``a * v + b == p`` over a fixed grid of
    multipliers and offsets, dividing rather than searching: two points
    with distinct values determine the line.  Constant values leave the
    multiplier free, which is the separate arm below.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

    # Builds 256 tables both ways and compares lengths; nothing is executed,
    # so this is cost rather than behaviour and takes no marker.
    def test_the_shorter_of_cascade_and_affine_ships(self) -> None:
        """The cascade is usually shorter at three inputs, but not always.

        Both paths are cheap at this arity, so both are built and the shorter
        kept.  The direct spelling bases improve 30 tables; the largest saving
        is seven characters, 41 against 34.
        """
        module = self.module()
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            shipped = len(boolean.pct_squared_minus_one(table))
            cascade = module._cascade(table, 3)  # noqa: SLF001
            assert cascade is None or shipped <= len(cascade), table
            improved += cascade is not None and shipped < len(cascade)
        assert improved == 30

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
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

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
