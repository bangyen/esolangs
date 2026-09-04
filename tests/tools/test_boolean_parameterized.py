"""Unit tests for the parameterized (no-input) boolean generators.

Covers :mod:`esolangs.tools.boolean.parameterized`, whose languages take no
input and instead embed each input by substitution, plus the COD and Eval
generators that follow the same convention.
"""

import importlib
import io
import random
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.parameterized import _instantiate_arrowqueue
from tests.tools.boolean_runners import one_two_three_result


def _parameterized_generators():
    from esolangs.tools.boolean import parameterized

    return [
        (name, parameterized.__dict__[name])
        for name in (
            "arrowqueue",
            "bio",
            "back",
            "nocomment",
            "bfpda",
            "lamfunc",
            "bitdeque",
            "ram0",
            "minsky_swap",
            "eval",
            "minifuck",
            "one_two_three",
            "pct_squared_minus_one",
        )
    ]


@pytest.mark.slow  # ~4s: builds every generator, up to n=4 — the bulk
# is 123's constructed four-input template, which is derived, not stored
def test_parameterized_generators_embed_each_input_once() -> None:
    """Every no-input generator embeds each input exactly once.

    An input-capable language reads each of its n inputs exactly once per
    run; a no-input language's parameterized generator should match, so each
    {Xi} appears exactly once -- never re-embedded at multiple decision
    nodes.

    A {Ci} complement placeholder must not appear at all.  instantiate no
    longer fills one, so a template carrying it would ship the literal text
    to the interpreter instead of failing, which is worth catching here.
    """
    import re

    checked = 0
    for name, gen in _parameterized_generators():
        for n in (1, 2, 3, 4):
            table = format(0, f"0{2**n}b")
            try:
                template = gen(table)
            except ValueError:
                # A generator need not cover every arity -- %^2^-1 derives
                # one- and two-input tables only.  The invariant here is about
                # the templates a generator *does* emit, so an uncovered arity
                # is skipped rather than failed; the count below keeps that
                # from quietly emptying the sweep.
                continue
            checked += 1
            xs = re.findall(r"\{X(\d+)\}", template)
            cs = re.findall(r"\{C(\d+)\}", template)
            assert sorted(xs) == [str(i) for i in range(n)], (name, n, xs)
            assert len(xs) == n, (name, n, xs)
            assert not cs, (name, n, cs)
    # Guard the skip above: every generator covers at least n == 2, so a run
    # that checked far fewer templates than that means the sweep stopped
    # exercising the generators rather than the generators getting stricter.
    assert checked >= len(_parameterized_generators()), checked


# Slot order is not needed for correctness -- :func:`instantiate` substitutes
# each ``{Xi}`` by name, replacing a unique token wherever it sits -- but it
# is worth holding to, because an out-of-order load is a restructured load.
#
# Every generator emits its slots in name order.  A generator whose order
# carried information would also have to emit a different *drawing* for a
# different order, or the permutation is a relabelling and its saving is
# fictitious -- the pairing below, which now covers ``back`` alone.
#
# There is no "reversed" category.  Bitdeque and BF-PDA used to push
# back-to-front so the first pop was the most significant bit; that only
# fixes which input the root tests, and testing the last input first costs
# nothing, so both now load in name order (verified byte-identical totals).
# Minifuck used to be the exception, carried as a strict xfail.  It no longer
# is, and how it was closed is worth keeping, because the obvious fix is the
# one that does not work.
#
# Its ignored inputs trailed the ``.``, which left name order whenever an
# ignored index sat below an essential one -- 24 of the 38 degenerate n=3
# tables.  *Relocating* an ignored fill does not fix that, measured rather
# than argued: a fill writes the live tape (``[<`` flips a cell), so moving
# one in front of the essential embeddings shifts every later one and the
# program stops computing -- 2 wrong rows at n == 2 and 6 at n == 3.
#
# Two routes closed it instead, neither of them a relocation:
#
# * Decline to project.  ``_embed`` lays every slot down in ascending order,
#   so a table solved at its *full* arity is in name order by construction.
#   That covers most of them.
# * Emit the ignored inputs first, then erase them.  The setters still have
#   to appear -- the harness has a bit for every input -- but a reconverging
#   suffix drives every row to one identical state, after which nothing
#   downstream can tell which bits they were, and the table is a one-input
#   problem in its single essential input.  That covers ``01010101`` and
#   ``10101010``, the projections onto the *last* input, which the first
#   route cannot reach: x2 stands in no cell after the embed under either
#   separator.  Note the reconvergence is to a common *non-blank* state --
#   a blank tape is unreachable, since the all-ones row ends a cell right of
#   the others and ``<`` clamps without writing.
#
# The two-essential tables keep projecting deliberately.  Full-arity solving
# is not merely unnecessary there, it is worse: ``00000101`` and
# ``00001010`` fail after about 130 seconds each against seconds to project,
# and a cheap scan-only attempt hits 1 table in 8 while costing ~9s per miss.
# Coverage and build cost both come before slot order.

_SLOT_ORDER_TABLES = ("0110", "01101001", "10101010", "11110000", "00111100")


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


@pytest.mark.slow  # builds every generator over several tables
def test_slots_run_in_name_order() -> None:
    """Every template emits ``{X0}``..``{Xn-1}`` in ascending order.

    Ordering is not needed for correctness -- :func:`instantiate` replaces
    each placeholder by name, wherever it sits -- but it is the shape every
    generator here holds to, and a load that leaves it is a load that has
    been restructured.  That is worth a failure rather than a shrug.

    Every generator is swept, with no exceptions carried -- Minifuck was the
    last one and is covered in its own test below, which pins the specific
    tables that used to leave sequence.
    """
    checked = 0
    for name, gen in _parameterized_generators():
        for table in _SLOT_ORDER_TABLES:
            slots = _slot_order(gen, table)
            if slots is None:
                continue
            checked += 1
            assert slots == sorted(slots), (name, table, slots)
    assert checked >= len(_parameterized_generators()), checked


def _drawing(template: str) -> str:
    """The template with every placeholder *name* erased.

    What the reorder bar tests is the emitted drawing, so comparing
    templates directly would count a mere relabelling as a change.  Erasing
    the names leaves exactly what a relabelling cannot alter.
    """
    import re

    return re.sub(r"\{X\d+\}", "{X}", template)


@pytest.mark.slow  # builds every permuting generator over several tables
def test_a_permuting_generator_changes_its_drawing() -> None:
    """A generator that permutes its slots must emit a different *drawing*.

    This is the reorder bar, and it is the one thing that could make a
    template's slot permutation a redefined benchmark rather than a smaller
    program.  ``instantiate`` substitutes by name, and ``_fill_back``'s
    setter is ``lambda _i, b:`` -- it ignores the index -- so if two input
    orders produced the same drawing they would emit *byte-identical
    programs* and any "saving" between them would be booked against the
    harness's fill order alone.

    They do not.  Back's tree is built on the permuted table, so a different
    order folds differently and draws a different program: at ``10101010``
    the identity order draws 115 characters and the winning order 44.  The
    permuted slot names are a consequence of choosing the order, not the
    source of the saving -- orders that share a drawing measure exactly the
    same size.

    Asserting that is what gives this teeth.  A future change that made the
    reorder cosmetic -- permuting names while emitting one drawing -- would
    still pass every correctness test in this class and fail here.
    """
    from itertools import permutations

    from esolangs.tools.boolean import parameterized
    from esolangs.tools.boolean.helpers import permute_truth_table

    checked = 0
    for name in ("back",):
        build = parameterized._back_ordered  # noqa: SLF001
        for table in ("10101010", "11001100", "00111100"):
            n = 3
            builds: dict[str, set[int]] = {}
            for perm in permutations(range(n)):
                built = build(permute_truth_table(table, perm), perm)
                builds.setdefault(_drawing(built), set()).add(len(built))
            checked += 1
            # The orders must not all collapse onto one drawing, or the
            # reorder is a relabelling.
            assert len(builds) > 1, (
                name,
                table,
                "every input order draws the same program, so permuting the "
                "slots emits an identical program and books a fake saving",
            )
            # And size must be a function of the drawing, not of the labels:
            # orders sharing a drawing are the same program.
            for drawing, sizes in builds.items():
                assert len(sizes) == 1, (name, table, len(drawing), sorted(sizes))
    assert checked >= 3, checked


class TestParameterizedBIO:
    """Input-by-substitution generators for the no-input language BIO."""

    def run_bio(self, prog: str, bits: list[int]) -> str:
        from tests.interpreters.runner import run_program

        run = importlib.import_module("esolangs.interpreters.register_based.bio").run
        return run_program(run, prog, "".join(f"{b}\n" for b in bits))

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_bio

        return _fill_bio(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bio(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bio(self.instantiate(template, bits), bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bio("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        """The packing scheme embeds each input exactly once."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.bio(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero pads against the unread ``z``, so the program's length
        does not reveal the inputs."""
        from esolangs.tools.boolean.examples import _fill_bio

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bio(placeholder, zeros)) == len(
                    _fill_bio(placeholder, ones)
                ), f"n={n} input {i}"

    def test_padding_never_touches_a_read_register(self) -> None:
        """``z`` is inert: the generator emits no command that reads it."""
        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            template = parameterized.bio(format(0, f"0{2**n}b"))
            assert "z" not in template.lower()


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # Back has no output instruction: it dumps the whole tape at halt.
        # The generator puts the answer in cell n, so the dump's (n+1)th
        # field is the result -- no need to track the head, which the dump
        # does not report.
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import run

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_back

        return _fill_back(tpl, bits)

    def test_program_length_is_the_same_for_every_input(self) -> None:
        """Both bits cost one command, so the size reveals nothing."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_back

        for n in (1, 2, 3):
            template = parameterized.back(format(0, f"0{2**n}b"))
            sizes = {
                len(_fill_back(template, [(c >> (n - 1 - i)) & 1 for i in range(n)]))
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"n={n} sizes {sorted(sizes)}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_back(self.instantiate(template, bits), n)
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.back(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_back(self.instantiate(template, bits), n)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        """Each input is embedded once in the tape load, not re-embedded."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.back(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_tree_uses_tape_decision_nodes(self) -> None:
        """The decision tree routes via '+\\' nodes and a down-transition."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back("0110")
        assert "+\\" in template  # a decision node
        assert "*" in template  # leaves halt

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not load order.

        ``10101010`` depends on its last input alone, so it folds nothing
        loaded in order and everything once that input sits in cell 0.  It
        reaches the cheap shape and lands far under the table that folds
        under no order at all; the two one-dependency tables differ only by
        the walk that carries the pointer, two characters a step.
        """
        from esolangs.tools.boolean import parameterized

        scattered = len(parameterized.back("10101010"))
        aligned = len(parameterized.back("11110000"))
        parity = len(parameterized.back("01101001"))
        assert scattered < parity
        assert aligned < parity
        assert abs(scattered - aligned) < 0.2 * parity

    def test_input_reordering_never_grows_a_template(self) -> None:
        """No table comes out larger than its identity build.

        ``best_input_order`` builds the identity first and keeps it on a
        tie, so reordering can only ever shrink a template.  Checked against
        ``_back_ordered`` at the identity rather than against a stored
        number, so it stays true as the construction changes.

        Note this is *not* "parity keeps the identity build".  It used to
        be, while the load emitted no walk; now that the units are emitted
        in reverse name order, some orders spend a shorter walk than the
        identity does, and parity shrinks 126 to 118 without folding
        anything.  The invariant that survives is the one-sided one.
        """
        from esolangs.tools.boolean import parameterized

        for table in ("01101001", "10101010", "11110000", "00111100", "10010110"):
            n = (len(table) - 1).bit_length()
            identity = parameterized._back_ordered(table, tuple(range(n)))  # noqa: SLF001
            assert len(parameterized.back(table)) <= len(identity), table

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_templates_compute_the_table(self, table: str) -> None:
        """A reordered template still computes its function.

        Back's node is ``+\\>`` -- test the current cell, *then* advance --
        so level ``k`` tests cell ``k``, one lower than the generators whose
        node steps first.  Loading an input into the wrong cell computes a
        different function rather than failing to draw, so only running it
        catches the slip.
        """
        from esolangs.tools.boolean import parameterized

        template = parameterized.back(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = self.run_back(self.instantiate(template, bits), 3)
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_pays_a_walk_and_keeps_name_order(self) -> None:
        """A permuted load spends rows on the walk, and keeps its slots sorted.

        This is the trade Back deliberately takes.  Filling in *cell* order
        -- putting ``{X perm[c]}`` in cell ``c`` -- emits no walk and is a
        few percent smaller, but leaves the placeholders out of name order,
        which no other generator in this module does.  Loading in name order
        and walking the pointer costs about two characters a step and keeps
        the templates uniform.

        Both halves are pinned here, because either alone would be wrong: a
        build with no walk cannot be reordering at all, and one whose slots
        left sequence would have taken the other side of the trade without
        the docstring being updated.
        """
        import re
        from itertools import permutations

        from esolangs.tools.boolean import parameterized

        walked = 0
        for table in ("0110", "10101010", "01101001"):
            n = (len(table) - 1).bit_length()
            for perm in permutations(range(n)):
                permuted = parameterized.permute_truth_table(table, perm)
                built = parameterized._back_ordered(permuted, perm)  # noqa: SLF001
                names = re.findall(r"\{X(\d+)\}", built)
                assert names == sorted(names), (table, perm, names)
                column = [ln[0] for ln in built.split("\n") if ln[:1].strip()]
                walked += column.count("<")
        # A non-identity order has to step the pointer back at some point;
        # a build with no leftward step is not reordering anything.
        assert walked > 0

    def test_placeholders_run_in_name_order_while_still_reordering(self) -> None:
        """Back reorders through the *walk*, not through its slot order.

        The load emits ``{X0}``..``{Xn-1}`` in sequence whatever the input
        order, and the reorder lives in the ``>``/``<`` runs that carry the
        pointer to each input's cell.  Both halves matter: dropping the
        walk would leave the order inert, and permuting the names instead
        would emit the slots out of sequence, which every other generator in
        this module avoids.

        The units are emitted in reverse name order because the load is
        drawn bottom-to-top up column 0, so the template's *text* reads them
        backwards -- loading input ``n-1`` first is what puts ``{X0}`` first
        on the page.
        """
        import re

        from esolangs.tools.boolean import parameterized

        walked = 0
        for table in ("11110000", "10101010", "01101001", "00111100"):
            template = parameterized.back(table)
            names = re.findall(r"\{X(\d+)\}", template)
            assert names == sorted(names), f"{table} slots {names}"
            assert sorted(names) == ["0", "1", "2"], f"{table} embeds each once"
            # The load column carries the walk; a table whose best order is
            # not the identity spends more than the n-1 steps a plain load
            # would.
            column = [line[0] for line in template.split("\n") if line[:1].strip()]
            walked += column.count("<")
        # At least one of these tables reorders, so at least one leftward
        # step is emitted -- a plain ascending load never steps back.
        assert walked > 0

    def test_reordering_keeps_the_equal_width_embedding(self) -> None:
        """Reordered loads still cost the same for either bit.

        The walk goes before an input's ``-``/``{Xi}`` pair and never
        between its halves, so the primer and the placeholder stay one
        unit and both bits still cost the same two rows.  Splitting them
        would let the template's height reveal an input.
        """
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_back

        for table in ("10101010", "11001100", "01101001"):
            template = parameterized.back(table)
            sizes = {
                len(_fill_back(template, [(c >> (2 - i)) & 1 for i in range(3)]))
                for c in range(8)
            }
            assert len(sizes) == 1, f"{table} sizes {sorted(sizes)}"


class TestParameterizedNoComment:
    """Input-by-substitution boolean generator for the no-input language NoComment."""

    def run_nocomment(self, prog: str, tape: int | None = None) -> str:
        from esolangs.interpreters.tape_based.nocomment import _TAPE, run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, IO(), _TAPE if tape is None else tape)
        return buffer.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "c" if b == 0 else "i",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.nocomment(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        """A one-bit template computes the index then skips to the output."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment("10")
        assert template.startswith("{X0}")
        assert "{C0}" not in template  # the complement is computed at runtime
        assert template.endswith("o")  # a single final output
        assert template.count("s") == 3  # NOT gate + guarded increment + index skip
        assert template.count("o") == 1

    def test_four_input_works(self) -> None:
        """A dense four-input table assembles and runs correctly."""
        from esolangs.tools.boolean import parameterized

        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            template = parameterized.nocomment("1010101010101010")
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int("1010101010101010"[combo])), f"inputs {bits}"

    # The decode is exponential in the arity, so all three widest cases cost
    # seconds: measured 9.3s at n=9, 29.0s at n=10 and 99.4s at n=11.  n=9
    # used to stay in the fast run as the case exercising the composed skip
    # past a byte-sized index, but it is four times the one-second budget
    # every other case is held to.  The mechanism is still proved on every
    # push, just not at push time: CI's `test` matrix job runs pytest
    # unfiltered, so a slow-marked case runs there like any other.  (The
    # separate `-m slow` job is scoped to the differential fuzzer's file
    # and never selects these.)
    #
    # These are ~2x the figures first recorded here (4.1/13.0/43.5s), which
    # were measured before NoComment's tape became immutable.  The write
    # buffer that made that change affordable collapses *runs* of writes,
    # and this decode has none -- it writes a cell and moves -- so it pays a
    # tape rebuild on ~66% of steps.  Storing the tape as `bytes` rather
    # than a tuple of ints took the rebuild back to a memcpy and these cases
    # from 45.7/139.7/561.6s to what they are now; the residue over the
    # original is the immutable state the purity refactor bought.
    @pytest.mark.parametrize(
        "n",
        [
            pytest.param(9, marks=pytest.mark.slow),
            pytest.param(10, marks=pytest.mark.slow),
            pytest.param(11, marks=pytest.mark.slow),
        ],
    )
    def test_wide_arity_is_exact(self, n: int) -> None:
        """Past a byte-sized index the composed-skip decode still computes the table.

        A single ``s`` cannot carry an index past 255, which is what caps
        the narrow path at eight inputs.  Composing skips lifts that, so
        these arities must be exactly right on *every* input, not merely
        renderable -- each table below is run through the interpreter for
        all ``2**n`` combinations.
        """
        from esolangs.tools.boolean import parameterized

        tables = {
            "alternating": "01" * (2 ** (n - 1)),
            "parity": "".join(str(bin(r).count("1") % 2) for r in range(2**n)),
            "constant": "0" * (2**n),
            "and": "0" * (2**n - 1) + "1",
        }
        for name, table in tables.items():
            template = parameterized.nocomment(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == table[combo], f"{name} n={n} inputs {bits}"

    def test_narrow_path_needs_a_byte_sized_index(self) -> None:
        """The single-skip decode covers exactly the arities whose index fits a byte.

        Derived from the interpreter's cell range rather than pinned: the
        skip amount is peeked off the stack and everything there came from a
        byte-sized cell, so the widest single-skip index is 255.
        """
        from esolangs.tools.boolean.parameterized import (
            _NOCOMMENT_NARROW_MAX,
            _NOCOMMENT_SKIP_MAX,
        )

        assert 2**_NOCOMMENT_NARROW_MAX - 1 <= _NOCOMMENT_SKIP_MAX
        assert 2 ** (_NOCOMMENT_NARROW_MAX + 1) - 1 > _NOCOMMENT_SKIP_MAX

    def test_cap_is_the_tape_not_the_skip(self) -> None:
        """The remaining cap is the interpreter's tape, and it is derived.

        The refusal must name the tape, and the boundary must be wherever
        the layout stops fitting -- so the largest arity that builds is
        found by asking, not asserted as a literal, and the next one up
        must raise.
        """
        from esolangs.interpreters.tape_based.nocomment import _TAPE
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.parameterized import _NOCOMMENT_NARROW_MAX

        widest = 0
        for n in range(1, 16):
            try:
                parameterized.nocomment("0" * (2**n))
            except ValueError:
                break
            widest = n

        # The cap is past the byte-sized-index bound the narrow path has,
        # which is the whole point of the composed-skip decode.
        assert widest > _NOCOMMENT_NARROW_MAX
        with pytest.raises(ValueError, match=str(_TAPE)) as caught:
            parameterized.nocomment("0" * (2 ** (widest + 1)))
        assert "tape" in str(caught.value)

    def test_a_bigger_tape_lifts_the_cap(self) -> None:
        """The cap is the tape size, so a bigger tape moves it -- and still computes.

        The arity the default refuses is built against a larger tape and run
        on an interpreter given that same size, which is what makes this a
        lifted bound rather than a longer program that nothing can execute.
        A spot-check of inputs, not the sweep: :meth:`test_wide_arity_is_exact`
        already runs every combination at the arities the default reaches, and
        ``2**12`` runs of a 51k-command program is far too slow for the suite.
        """
        from esolangs.interpreters.tape_based.nocomment import _TAPE
        from esolangs.tools.boolean import parameterized

        n, tape = 12, 16384
        table = "".join(str((r * r + r // 3) % 2) for r in range(2**n))

        with pytest.raises(ValueError, match=str(_TAPE)):
            parameterized.nocomment(table)

        template = parameterized.nocomment(table, tape=tape)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 1234, 2731):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits), tape)
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.nocomment("011")


class TestParameterizedLamfunc:
    """Input-by-substitution boolean generator for the no-input language Lamfunc."""

    def run_lamfunc(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.lamfunc import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # each {Xi} fills a `vs v{i}` store with the binary literal
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "0b" + str(b),
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.lamfunc(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_lamfunc(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.lamfunc(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_lamfunc(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.lamfunc("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        """The store-once scheme embeds each input exactly once."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.lamfunc(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits the stores plus a single p with no branching."""
        from esolangs.tools.boolean import parameterized

        assert parameterized.lamfunc("0000") == "vs v0 {X0} vs v1 {X1} p 0"
        assert parameterized.lamfunc("1111") == "vs v0 {X0} vs v1 {X1} p 1"

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.lamfunc("011")


class TestParameterizedBitdeque:
    """Input-by-substitution boolean generator for the no-input language Bitdeque."""

    def run_bitdeque(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        # Deliberately the shipped fill rather than a copy of its rule: an
        # earlier duplicate here kept passing after the load order changed
        # under it, so the suite disagreed with the harness it is meant to
        # mirror.
        from esolangs.tools.boolean.examples import _fill_bitdeque

        return _fill_bitdeque(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bitdeque(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bitdeque(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bitdeque(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a drain-and-push leaf with no branching."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque("0000")
        assert "POP" in template
        assert "GOTO" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bitdeque("011")


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0.

    RAM0 prints a full state dump at halt; the generator's answer is the
    final ``z`` value, read from the dump's ``z: N`` line.
    """

    def run_ram0(self, prog: str) -> str:
        import re

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import run

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # Z resets absolutely, so the setter is the same at every position:
        # "Z A" for a one, "Z Z" for a zero, each exactly two commands.
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "Z A" if b else "Z Z",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_ram0(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.ram0(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_ram0(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a single leaf with no branching."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0("0000")
        assert "C" not in template
        assert "Z" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.ram0("011")


class TestParameterizedMinskySwap:
    """Input-by-substitution boolean generator for the no-input language Minsky Swap.

    Minsky Swap prints the two registers at halt; the generator's answer is
    stored in ``reg[1]``, so it is the second number of the dump line.
    """

    def run_minsky_swap(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.minsky_swap import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().split()[1]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        n = len(bits)

        def set_bit(i: int, b: int) -> str:
            if i == n - 1:  # LSB: length-4 block, no "~"
                return "+*+*" if b else "****"
            w = 2 ** (n - 1 - i)  # this bit's weight
            if b:
                return "+" * w + "*" * (2**n - w)
            return "*" * 2**n

        return parameterized.instantiate(
            tpl,
            bits,
            set_bit,
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minsky_swap(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minsky_swap(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.minsky_swap(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_minsky_swap(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minsky_swap("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.minsky_swap("011")

    @pytest.mark.parametrize("bits", [(0, 0), (0, 1), (1, 0), (1, 1)])
    def test_examples_fill_sets_either_bit_in_either_position(
        self, bits: tuple[int, int]
    ) -> None:
        """``_fill_minsky_swap`` spells a set bit above the LSB too.

        The catalogue entry runs one fixed pair, ``(0, 1)``, which leaves
        the non-LSB always zero -- so its weighted ``"+" * weight`` block
        is never emitted there.  Each pair below is run, not merely built,
        because a wrong weight or pad would still produce a plausible
        string.
        """
        from esolangs.tools.boolean import minsky_swap
        from esolangs.tools.boolean.examples import AND2, _fill_minsky_swap

        program = _fill_minsky_swap(minsky_swap(AND2), list(bits))
        assert self.run_minsky_swap(program) == AND2[(bits[0] << 1) | bits[1]]

    def test_examples_fill_weights_the_non_lsb(self) -> None:
        """A set non-LSB is its weight in ``+`` then a pad to the block size.

        The pad keeps every block the same even length, which is what stops
        the register pointer drifting; ``"+*+*"`` is the LSB's exception.
        """
        from esolangs.tools.boolean import minsky_swap
        from esolangs.tools.boolean.examples import AND2, _fill_minsky_swap

        template = minsky_swap(AND2)
        assert "++**" in _fill_minsky_swap(template, [1, 1])
        assert "++**" not in _fill_minsky_swap(template, [0, 1])


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue.

    ArrowQueue has no output, so the generator's answer is read from the
    termination convention: an instantiated program halts for a ``0`` table
    entry and loops forever for a ``1`` entry.  The run is bounded by
    state-cycle detection (the queue stays bounded on the sustaining rings),
    so the repeated-snapshot proof reports the ``1`` cases immediately.
    """

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input halts or loops per its table entry."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_arrowqueue(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
        from esolangs.tools.boolean import parameterized

        random.seed(13)
        for n in (1, 2, 3, 4, 5):
            for _ in range(2):
                table = "".join(random.choice("01") for _ in range(2**n))
                template = parameterized.arrowqueue(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = self.run_arrowqueue(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.arrowqueue("011")

    @pytest.mark.parametrize(
        ("table", "mixed"),
        [
            ("1111", "1010"),
            ("11110000", "10010110"),
            ("1111111100000000", "1001011001101001"),
        ],
    )
    def test_constant_subtrees_fold(self, table: str, mixed: str) -> None:
        """A constant subtree emits one drained leaf, not a full branch set.

        The comparison table has the same ones-count, so a shorter template
        means the tree folded rather than that something else shrank.
        """
        from esolangs.tools.boolean import parameterized

        assert len(parameterized.arrowqueue(table)) < len(
            parameterized.arrowqueue(mixed)
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1" * 16, 4),
            ("0" * 16, 4),
            ("1111111100000000", 4),
            ("1111000000000000", 4),
            ("1" * 32, 5),
            ("1" * 16 + "0" * 16, 5),
        ],
    )
    def test_folded_tables_past_three_inputs(self, table: str, n: int) -> None:
        """Folded leaves stay correct deeper than the exhaustive n <= 3 sweep."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    def test_folded_one_leaf_drains_the_bits_it_skipped(self) -> None:
        """The drain is load-bearing: a ring needs the queue it expects.

        A folded ``1`` leaf pops a direction at each of its ring's corners
        and requires exactly ``R, D, L, U``.  Without the drains, the bits
        the skipped branches never popped sit ahead of those components, the
        corners pop the wrong directions, the ring does not close, and the
        program halts -- reporting ``0`` for a ``1`` entry.  Dropping the
        drains here must therefore break the table.
        """
        from esolangs.tools.boolean.parameterized import _TREE_1, _drained_leaf

        undrained = _drained_leaf("1", 0)  # no drains at all
        assert [row.strip() for row in undrained if row.strip()] == [
            row.strip() for row in _TREE_1
        ]

        # With two levels skipped the drained leaf is strictly taller than
        # the bare ring, and that extra height is the drain chain.
        drained = _drained_leaf("1", 2)
        assert len(drained) == len(_TREE_1) + 2
        assert sum(row.count("+") for row in drained) == 4 + 2  # ring + drains

    def test_folded_zero_leaf_needs_no_drain(self) -> None:
        """A ``0`` leaf halts by leaving the grid, which the queue cannot stop."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.parameterized import _TREE_0, _drained_leaf

        # It carries no drain at all.  Paying for one is not free: the
        # staircase sits a column right of the branches it replaces, so
        # ``_compact`` finds fewer all-blank columns and the instantiated
        # program grows -- which is what made AND-2 larger than before the
        # fold until this case was carved out.
        assert _drained_leaf("0", 3) == list(_TREE_0)
        for table, n in (("0000", 2), ("0" * 8, 3)):
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert self.run_arrowqueue(self.instantiate(template, bits)) == "0"

    def test_folding_never_grows_a_program(self) -> None:
        """No instantiated program is larger than its unfolded equivalent.

        A fold that costs characters is not a fold.  AND-2 briefly regressed
        (124 to 128 bytes) when ``0`` leaves were drained too: a folded
        ``00`` half gained a staircase where the branch pair it replaced was
        cheaper, and the extra column blocked ``_compact``.  This pins the
        whole n <= 2 space, where such a regression showed up.
        """
        from esolangs.tools.boolean.parameterized import (
            _TREE_0,
            _TREE_1,
            _connect,
            _tree,
        )

        def unfolded(values: list[str]) -> list[str]:
            """The pre-fold construction: a branch per level, never collapsed."""
            if len(values) == 2:
                return _connect(
                    _TREE_1 if values[0] == "1" else _TREE_0,
                    _TREE_1 if values[1] == "1" else _TREE_0,
                )
            half = len(values) // 2
            return _connect(unfolded(values[:half]), unfolded(values[half:]))

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                folded = _tree(list(table))
                plain = unfolded(list(table))
                assert sum(len(r.rstrip()) for r in folded) <= sum(
                    len(r.rstrip()) for r in plain
                ), table

    def test_fold_keeps_equal_width_embedding(self) -> None:
        """Every instantiation of a folded template is the same length.

        The fold shrinks the tree, which is shared by all instantiations, so
        the program's size still cannot leak which bits were embedded.
        """
        from esolangs.tools.boolean import parameterized

        for table, n in (("1111", 2), ("1100", 2), ("11110000", 3)):
            template = parameterized.arrowqueue(table)
            sizes = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"{table}: {sizes}"


class TestParameterizedBfpda:
    """Input-by-substitution boolean generator for the no-input language BF-PDA."""

    def run_bfpda(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bf_pda import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_bfpda

        return _fill_bfpda(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is four characters whichever bit it carries."""
        from esolangs.tools.boolean.examples import _fill_bfpda

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bfpda(placeholder, zeros)) == len(
                    _fill_bfpda(placeholder, ones)
                ), f"n={n} input {i}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bfpda(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bfpda(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bfpda(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        """Each input is embedded once (pre-loaded), not re-embedded per node."""
        import re

        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template  # the marker is a constant, not a complement
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2  # n embeds

    def test_leaf_print_is_balanced(self) -> None:
        """A leaf pops the remaining bits, prints the answer, and pops it."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("10")  # NOT: one-leaf prints 1
        assert "<@.>" in template
        assert "<.>" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bfpda("011")


class TestParameterizedHomeRow:
    """Input-by-substitution boolean generator for the no-input language Home Row."""

    def run_home_row(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.home_row import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_home_row

        return _fill_home_row(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
        from esolangs.tools.boolean.examples import _fill_home_row

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_home_row(placeholder, zeros)) == len(
                    _fill_home_row(placeholder, ones)
                ), f"n={n} input {i}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_home_row(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_five_inputs_sample(self) -> None:
        """A sample of dense five-input tables, past the removed n <= 2 cap."""
        import random

        from esolangs.tools.boolean import parameterized

        n = 5
        rng = random.Random(0)
        for _ in range(5):
            table = "".join(rng.choice("01") for _ in range(2**n))
            template = parameterized.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_embedded_once(self) -> None:
        import re

        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.home_row("011")


class TestParameterizedCOD:
    """Input-by-substitution boolean generator for the no-input language COD."""

    def run_cod(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.cod import run
        from esolangs.interpreters.io import ScriptedIO

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # each {Xi} sets the cod's value to the bit: ')' for one, space
        # for zero, read at the start of that input's '+' fork
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: ")" if b else " ",
        )

    @pytest.mark.parametrize(
        "table",
        [
            "0000",  # constant zero
            "1111",  # constant one
            "0001",  # AND
            "0111",  # OR
            "0110",  # XOR
            "1001",  # XNOR
            "1110",  # NAND
            "1000",  # NOR
            "0100",  # A and not B
            "1101",  # A or not B
        ],
    )
    def test_truth_table(self, table: str) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod(table)
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            got = self.run_cod(self.instantiate(template, bits))
            assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every one of the sixteen two-input tables produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.cod(table)
            for combo in range(4):
                bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.slow  # 1.1s: all 256 three-input tables through COD
    def test_all_three_input_tables(self) -> None:
        """Every one of the 256 three-input tables produces the right result.

        Unlike the two-input template, whose forks always split directly
        into leaves, the three-input template has forks whose zero-branch
        is itself an internal node -- so a cod can rejoin an earlier
        junction's row after a deeper fork, and that junction's own reset
        gauntlet is what stops it from circulating forever instead of
        halting.  This test is the only thing that would have caught that
        class of bug (a "backflow" cod wandering junctions indefinitely),
        since it is invisible from reading the grid.
        """
        from esolangs.tools.boolean import parameterized

        for table_int in range(256):
            table = format(table_int, "08b")
            template = parameterized.cod(table)
            for combo in range(8):
                bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_program_always_terminates_with_one_value(self) -> None:
        """Every run prints exactly one value and leaves no cod alive."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            code = self.instantiate(template, bits)
            io_ = ScriptedIO("")
            machine = _Machine(code, io_)
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            # one print, so one character: the answer, no separator
            assert len(io_.getvalue()) == 1

    def test_three_input_program_always_terminates_with_one_value(self) -> None:
        """Every three-input run prints exactly one value and halts."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("01101001")
        for combo in range(8):
            bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
            code = self.instantiate(template, bits)
            io_ = ScriptedIO("")
            machine = _Machine(code, io_)
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            # one print, so one character: the answer, no separator
            assert len(io_.getvalue()) == 1

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_embedded_once(self) -> None:
        """The routing embeds each input exactly once, not per leaf."""
        import re

        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert len(re.findall(r"\{X\d+\}", template)) == 2

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.cod("011")

    def test_constant_table_rejected(self) -> None:
        """n == 0 (a single-entry table, no inputs) is not supported."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="n >= 1"):
            parameterized.cod("0")

    def test_four_input_tables(self) -> None:
        """n == 4 (beyond the old n <= 3 cap) produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table in ("1111111011111110", "0110100110010110", "1000000000000000"):
            template = parameterized.cod(table)
            for combo in range(16):
                bits = [(combo >> (4 - 1 - i)) & 1 for i in range(4)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.parametrize("table", ["10", "01", "00", "11"])
    def test_one_input_truth_table(self, table: str) -> None:
        """n == 1 has no fork of its own: a bare entry into the leaf cascade."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod(table)
        assert "{X0}" in template
        assert "{X1}" not in template
        for x0 in range(2):
            got = self.run_cod(self.instantiate(template, [x0]))
            assert got == f"{table[x0]}", f"table {table} input {x0}"


class TestEvalBoolean:
    """Input-by-substitution boolean generator for the no-input language Eval."""

    def run_eval(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.eval import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_eval

        return _fill_eval(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
        from esolangs.tools.boolean.examples import _fill_eval

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_eval(placeholder, zeros)) == len(
                    _fill_eval(placeholder, ones)
                ), f"n={n} input {i}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.eval(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_eval(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_constant_subtrees_fold_in_place(self) -> None:
        """A constant subtree becomes a leaf; its slots empty but remain.

        The heap is positional -- a node's ``;`` run is a function of its
        own index and its children sit at pinned offsets -- so the folded
        subtree cannot be *removed* without shifting every later index.
        The slots stay and are emptied instead, which is why the string
        count never changes while the program still gets shorter.
        """
        from esolangs.tools.boolean import parameterized

        full = parameterized.eval("10010110")
        folded = parameterized.eval("11111111")
        assert len(folded) < len(full)
        # every heap slot is still present, just empty
        assert folded.count('"') == full.count('"')
        assert '""' in folded

    def test_folding_keeps_both_bits_equal_width(self) -> None:
        """Folding shrinks the template, never one instantiation.

        The embedding's whole point is that ``len(program)`` cannot reveal
        the inputs.  A fold that depended on the bits would reintroduce
        exactly that leak, so this pins equal width on folded tables too.
        """
        from esolangs.tools.boolean import parameterized

        for table in ("11111111", "11110000", "11001100", "0001"):
            n = len(table).bit_length() - 1
            template = parameterized.eval(table)
            widths = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(widths) == 1, f"{table} leaks its inputs: {widths}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_heap_tree_structure(self) -> None:
        """The template is a flat heap tree pushed BFS-order then reversed."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval("0110")
        # Staged forward, like every other parameterized generator: each
        # block pushes its bit on the tree stack and `=` moves it across.
        # Which order they are staged in only decides *which* arrangement
        # costs no reorder ops, since `*` reverses either way.
        assert template.startswith("{X0}{X1}")
        assert template.endswith("*!")
        assert '"~=~?;!"' in template  # root node: one discard
        assert '"~=~?;;!"' in template  # BFS index 1: two discards
        assert template.count('"~=~?') == 3  # 2**2 - 1 internal nodes
        assert template.count('"0+.') + template.count('"0.') == 4  # leaves
        # leaves are the XOR table in heap order: 0 1 1 0
        assert template.endswith('"0.""0+.""0+.""0."*!')

    def test_reordering_only_shrinks(self) -> None:
        """No table is longer than the arrangement staging already produces.

        The candidates are sorted by op cost with the free arrangement
        first and the comparison is strict, so a table no reorder helps
        emits exactly what it emitted before.
        """
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.helpers import permute_truth_table
        from esolangs.tools.boolean.parameterized import _eval_ordered

        # Staging pushes X0 first, so the free arrangement's split order is
        # the reversal -- the no-ops build is not the identity permutation.
        free = tuple(reversed(range(3)))
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(parameterized.eval(table))
            staged = len(_eval_ordered(permute_truth_table(table, free), ""))
            assert dispatched <= staged, table
            improved += dispatched < staged
        assert improved == 114

    def test_reorder_ops_run_outside_the_placeholders(self) -> None:
        """The rearrangement is emitted code, not a change to the fills.

        This is what makes it a reorder rather than a relabelling: the
        ``{Xi}`` blocks keep their slots and the harness fills them exactly
        as before, while the emitted program gains ops that rearrange the
        stack its nodes pop from.  Equal-width embedding therefore still
        holds, since nothing inside a placeholder moved.
        """
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_eval

        # A table whose cheapest order is not the free one.
        table = "00001101"
        template = parameterized.eval(table)
        assert template.startswith("{X0}{X1}{X2}")  # slots unmoved
        widths = {
            len(_fill_eval(template, [(c >> (2 - i)) & 1 for i in range(3)]))
            for c in range(8)
        }
        assert len(widths) == 1  # every fill the same length

    def test_stack_ops_reach_every_arrangement(self) -> None:
        """Two stacks with a reverse and a cross-move permute the bits.

        ``~`` switches stacks, ``*`` reverses the active one and ``=`` moves
        its top across; the pair is a spindle, so the three compose to reach
        every arrangement at n <= 4.  Unlike Forþ's ``o``, ``*`` is usable
        here because the staging leaves the bits alone on that stack.
        """
        from math import factorial

        from esolangs.tools.boolean.parameterized import _eval_stack_programs

        for n in (2, 3, 4):
            assert len(_eval_stack_programs(n)) == factorial(n)
        # The free arrangement is the one staging produces, and costs nothing.
        assert _eval_stack_programs(3)[(0, 1, 2)] == ""

    def test_scales_to_more_inputs(self) -> None:
        """The heap tree grows to any n (spot-checked at n = 6)."""
        from esolangs.tools.boolean import parameterized

        n = 6
        table = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
        template = parameterized.eval(table)
        assert len(template) < 3000
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.eval("011")

    def test_non_binary_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="only '0' and '1'"):
            parameterized.eval("02")


@pytest.mark.slow  # 2.6s: every fill of every parameterized generator
def test_fills_embed_a_zero_and_a_one_at_equal_width() -> None:
    """No fill may spell a 0 shorter than a 1, or the length leaks the input.

    A program whose length depends on its inputs reveals them without being
    read: an earlier BIO embedding ran to 236/240/244/248 characters for the
    four ``n == 2`` instantiations, so ``len(program)`` alone recovered the
    bits.  Every ``_fill_*`` therefore pads the two sides to equal width, an
    invariant stated on :func:`~esolangs.tools.boolean.helpers.instantiate`
    and enforced here.

    The check is per-generator rather than global: fills legitimately differ
    from each other in width, but for one generator and one table every
    instantiation must come out the same length.
    """
    import itertools

    from esolangs.tools.boolean import examples as ex

    fills = [
        (name, getattr(ex, name))
        for name in dir(ex)
        if name.startswith("_fill_") and callable(getattr(ex, name))
    ]
    assert fills, "no _fill_* functions found"

    for name, fill in fills:
        gen_name = name.removeprefix("_fill_")
        gen = getattr(ex, gen_name, None) or getattr(
            importlib.import_module("esolangs.tools.boolean"), gen_name, None
        )
        if gen is None:  # pragma: no cover - fill without a same-named generator
            continue
        for n in (1, 2):
            template = gen(format(0, f"0{2**n}b"))
            lengths = {
                len(fill(template, list(bits)))
                for bits in itertools.product((0, 1), repeat=n)
            }
            assert len(lengths) == 1, (
                f"{name} embeds bits at unequal width for n={n}: {sorted(lengths)}"
            )


class TestParameterizedOneTwoThree:
    """Input-by-substitution boolean generator for the no-input language 123.

    123's ``2`` reads real stdin, so a decision tree cannot read its inputs;
    the generator embeds them instead, ``1`` for a one and ``2`` for a zero.
    Like ArrowQueue the answer is the termination convention -- halt for a
    ``0`` entry, loop for a ``1`` -- decided by state-cycle detection.

    ``docs/walls.md`` had this route capped at the monotone tables.  That
    ceiling was the displacement-neutral ``12``/``21`` setter's, not the
    language's: the +-1 fill used here breaks position lockstep, so XOR and
    NAND come out too and all sixteen two-input tables are covered.

    All 256 three-input tables build as well.  The bare mod-four counter
    carries only popcount *parity* at three inputs, so the tables that are
    not parity functions need ``3``'s TRUE-backward re-run; ``01111110``,
    TRUE unless all three inputs agree, was the last to build.
    """

    def run(self, program: str) -> str:
        return one_two_three_result(program)

    def instantiate(self, template: str, bits: list[int]) -> str:
        from esolangs.tools.boolean.one_two_three import ONE, ZERO

        for i, bit in enumerate(bits):
            template = template.replace(f"{{X{i}}}", ONE if bit else ZERO)
        return template

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every one-, two- and three-input table halts or loops per its entry."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.one_two_three(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run(self.instantiate(template, bits))
                assert got == table[combo], (table, bits)

    def test_the_tables_walls_md_called_unreachable(self) -> None:
        """XOR and NAND build, against the recorded monotone ceiling.

        These are the two the monotonicity argument specifically forbids: a
        set bit can only add a pass under the neutral setter, so the looping
        set is upward-closed and neither table can appear.  Both are here.
        """
        from esolangs.tools.boolean import parameterized

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
        plan with such a row would hang the suite rather than report a 1.
        Every looping row must therefore revisit a state, which this checks
        by bounding the pointer: a run that neither halts nor cycles within
        the budget, while pushing the pointer past the program, is exactly
        the shape that must not ship.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools.boolean import parameterized

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

    def test_slots_run_in_name_order(self) -> None:
        """Every emitted template embeds {X0} before {X1}."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.one_two_three(table)
            assert template.index("{X0}") < template.index("{X1}"), table

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero and a one embed at equal width, so length leaks nothing."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.one_two_three(table)
            sizes = {
                len(self.instantiate(template, [(c >> 1) & 1, c & 1])) for c in range(4)
            }
            assert len(sizes) == 1, (table, sizes)

    @pytest.mark.slow  # ~2s: one four-input construction, replayed
    def test_a_wider_table_is_constructed(self) -> None:
        """A four-input table builds through the constructed route.

        This used to assert a :class:`ValueError`: the recorded reason was
        that an inert embed shifts the pointer phase the plan decodes.
        That bound the phase-decode shape, not the language — the
        constructed route re-synchronizes every instantiation's pointer
        after each embed (see ``one_two_three_construct``) — so the gate
        fell.  Every row of the template is replayed here on the real
        interpreter, the same execution gate the generator itself applies
        before returning.  Tables whose verdict search cannot converge
        inside the deterministic work budget still raise, so wider
        coverage is partial; ``docs/limitations.md`` records the split.
        """
        from esolangs.tools.boolean import parameterized

        table = "0000000000000000"
        template = parameterized.one_two_three(table)
        xs = [template.index(f"{{X{i}}}") for i in range(4)]
        assert xs == sorted(xs), table
        sizes = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            sizes.add(len(program))
            assert self.run(program) == table[combo], (table, bits)
        assert len(sizes) == 1, (table, sizes)

    # Was ~10s and marked slow; the construction speedups took it to well
    # under a tenth of a second, so it belongs in the default suite.
    def test_construction_moves_all_fire_on_one_table(self) -> None:
        """A single table forces every move kind the search offers.

        ``00111000`` needs kills, single- and group-boosts, and a ring
        round to converge — separation and the pre-verdict residue
        alignment run on every table — so this one build is a witness
        that each gadget the module-level docstring describes is not
        just reachable in principle but taken on a real trajectory, not
        only inferred from ``construct()``'s success.  (Found by an
        exhaustive three-input sweep: most tables now chain bottom-up
        kills without ever needing a boost, so a witness for the rarer
        moves has to be picked deliberately.)
        """
        from esolangs.tools.boolean import one_two_three_construct as construct_mod

        called: set[str] = set()
        originals = {
            name: getattr(construct_mod, name)
            for name in (
                "_gap_fix",
                "_align_residues",
                "_group_boost",
                "_ring_round",
                "_boost_row",
                "_try_kill",
                "_separate",
            )
        }

        def watch(name: str, fn: object) -> object:
            def wrapper(*args: object, **kwargs: object) -> object:
                called.add(name)
                return fn(*args, **kwargs)  # type: ignore[operator]

            return wrapper

        for name, fn in originals.items():
            setattr(construct_mod, name, watch(name, fn))
        try:
            # verify=False: every row is replayed below, and the
            # generator's own closing replay is the same execution twice.
            template = construct_mod.construct("00111000", verify=False)
        finally:
            for name, fn in originals.items():
                setattr(construct_mod, name, fn)

        assert called == set(originals), called
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            program = self.instantiate(template, bits)
            assert self.run(program) == "00111000"[combo], bits

    def test_an_exhausted_work_budget_is_declined(self) -> None:
        """A table that would build still raises once the work runs out.

        ``_work`` is deterministic (simulated commands, not wall clock),
        so shrinking :data:`_WORK_BUDGET` reproduces the exhausted-budget
        branch instantly and exactly -- the same path a genuinely
        unconvergent search would take, without paying for one.
        """
        from esolangs.tools.boolean import one_two_three_construct as construct_mod

        original_budget = construct_mod._WORK_BUDGET  # noqa: SLF001
        construct_mod._WORK_BUDGET = 50  # noqa: SLF001
        try:
            with pytest.raises(ValueError, match="work budget ran out"):
                construct_mod.construct("00000000")
        finally:
            construct_mod._WORK_BUDGET = original_budget  # noqa: SLF001

    def test_an_exhausted_move_budget_is_declined(self) -> None:
        """A verdict search that never finds a kill still terminates.

        ``_verdict_search``'s own ``budget`` counts DFS nodes rather than
        simulated commands, so it needs its own exhaustion check: a
        one-node budget on a table with a live 1-row cannot find any
        move, and the search must return ``None`` rather than loop or
        raise past that ceiling.  ``_work`` is reset by hand because this
        calls the pipeline stages directly instead of going through
        :func:`construct`, which is the only place that resets it.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            _WORK_BUDGET,
            _align_residues,
            _Builder,
            _close,
            _gap_fix,
            _phase_a,
            _separate,
            _verdict_search,
            _work,
        )

        n = 3
        table = "10000000"
        _work[0] = _WORK_BUDGET
        b = _Builder(n)
        marks = [2 ** (n + 1) * 3**i + 1 for i in range(n)]
        _phase_a(b, marks)
        _close(b)
        _separate(b, marks)
        _gap_fix(b, table)
        _align_residues(b, table)
        assert _verdict_search(b, table, budget=1) is None

    def test_distinct_ok_reports_a_real_collision(self) -> None:
        """Two live rows at one exact state disagree only if their verdicts differ.

        ``_distinct_ok`` tolerates two 0-rows landing on the same state
        (a cut erases a 0-row's history for good, so nothing distinguishes
        it from another 0-row sharing the state) but not a 0-row and a
        1-row: the kill machinery discriminates by state, so a collision
        between different verdicts is unrecoverable and must be reported.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            _Builder,
            _distinct_ok,
            _mask,
            _Row,
        )

        def two_rows_at(pos: int, tape: int) -> _Builder:
            zero = _Row((0, 0))
            one = _Row((0, 1))
            zero.pos = one.pos = pos
            zero.tape = one.tape = tape
            b = _Builder.__new__(_Builder)
            b.n = 2
            b.chunks = []
            b.seg = []
            b.rows = [zero, one]
            return b

        # table index 0 -> '0', index 1 -> '1': the two rows disagree
        assert _distinct_ok(two_rows_at(5, _mask({1, 2, 3})), "0100") is False
        # table index 0 -> '0', index 1 -> '0': both 0-rows, tolerated
        assert _distinct_ok(two_rows_at(5, _mask({1, 2, 3})), "0000") is True

    def test_one_row_collided_flags_a_live_one_row(self) -> None:
        """A 1-row sharing a position with any other live row is a trap."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _Builder,
            _mask,
            _one_row_collided,
            _Row,
        )

        zero = _Row((0, 0))
        one = _Row((1, 0))
        zero.pos = one.pos = 5
        zero.tape = one.tape = _mask({1, 2, 3})
        b = _Builder.__new__(_Builder)
        b.n = 2
        b.chunks = []
        b.seg = []
        b.rows = [zero, one]
        # table index 2 (bits (1,0)) -> '1'
        assert _one_row_collided(b, "0010") is True

    def test_normalize_reports_a_live_locked_ring(self) -> None:
        """Four distinct rows pinned to all four ring cells cannot escape.

        ``_normalize`` steps every live row together (one shared ``1`` or
        ``2`` per round), so four *different* rows already sitting one
        each on -1, -2, -3 and 0 never converge on a single move: the
        round that frees the -3 row re-occupies -4 -> 0 while another
        stays put, so the occupied set does not shrink.  This is a
        contrived state (real builds keep all rows in lockstep), but the
        function must still terminate on it rather than spin.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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

        ``_close`` walks right looking for a position where every live
        row is simultaneously on a FALSE cell; a row whose tape covers
        the whole search window can never supply one, so the search
        must give up rather than walk forever.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _close,
            _mask,
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

        A dense tape lets a single ``2`` keep the row TRUE at every
        position while it marches right forever, so the rerun neither
        escapes nor repeats within the fixpoint cap -- the shape a
        genuinely diverging candidate segment would take.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _mask,
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
        """``test(kill=...)`` requires the named victim to provably loop."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _mask,
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
            b.test(kill=(0,))

    def test_test_reports_a_kill_that_never_fires(self) -> None:
        """``test(kill=...)`` refuses a close where the victim tested FALSE.

        A kill whose victim never lands on a TRUE cell would silently
        leave the row alive; the close must report it instead, because
        every adopted kill claims one specific row is now provably
        looping.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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
            b.test(kill=(0,))

    def test_test_reports_an_unintended_loop(self) -> None:
        """A plain ``test()`` requires every TRUE row to escape, not loop."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _mask,
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
            b.test(kill=False)

    def test_an_empty_table_is_declined(self) -> None:
        """A table implying zero inputs raises rather than building nothing.

        ``"1"`` is a well-formed truth table of length ``2**0``, so it
        clears the power-of-two check and is refused on arity instead.
        123 used to carry its own message for this; the rule is now the
        shared validator's, since every boolean generator owes it (see
        ``test_boolean_contract``), so this asserts the shared wording.
        """
        from esolangs.tools.boolean import parameterized

        # ``match`` is a substring search, so the equality below is what
        # actually pins the message.
        with pytest.raises(ValueError, match="at least one input") as caught:
            parameterized.one_two_three("1")
        assert str(caught.value) == (
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function"
        )

    def test_out_of_order_slots_are_refused(self) -> None:
        """The name-order invariant is asserted, not assumed.

        Every table the generator builds satisfies it, so the guard is
        reachable only by handing the helper a body that violates it -- which
        is what a mistyped plan would look like.
        """
        from esolangs.tools.boolean.one_two_three import _in_name_order

        assert _in_name_order("{X0}{X1}", 2) == "{X0}{X1}"

        with pytest.raises(ValueError, match="out of name order") as caught:
            _in_name_order("{X1}{X0}", 2)
        assert str(caught.value) == (
            "template '{X1}{X0}' emits slots out of name order"
        )

    def test_each_input_is_embedded_once(self) -> None:
        """Each placeholder appears exactly once, and no {Ci} appears."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                xs = re.findall(r"\{X(\d+)\}", template)
                assert sorted(xs) == [str(i) for i in range(n)], (table, xs)
                assert not re.findall(r"\{C(\d+)\}", template), table

    def test_every_batched_run_charges_the_work_budget(self) -> None:
        """Each closed form in ``_exec_run`` has to stop on a drained budget.

        The batched paths exist so a long run costs O(1) instead of ``w``
        trips through ``_exec_char``, but the budget counts *simulated
        commands* and must not depend on which path ran them.  Each case
        below is the shape that selects one path, with the budget set just
        under what that path is about to charge.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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

    def test_the_walk_shortcut_declines_what_it_cannot_decide(self) -> None:
        """``_true_set_after_walk`` is exact only from a clean, non-negative state.

        It reads the verdict off the tape instead of simulating, which is
        sound only where the walk provably cannot loop or read: no pending
        segment, and every row at ``pos >= 0``.  Outside that it declines,
        and it also declines a landing chain longer than the fixpoint's
        64-re-run cap rather than reporting a set the fixpoint would reject.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _true_set_after_walk,
            _work,
        )

        _work[0] = _WORK_BUDGET

        def flat(n: int = 1) -> _Builder:
            b = _Builder(n)
            for row in b.rows:
                row.pos, row.tape = 0, 0
            return b

        below = flat()
        below.rows[0].pos = -1
        assert _true_set_after_walk(below, 4) is None

        pending = flat()
        pending.seg.append("1")
        assert _true_set_after_walk(pending, 4) is None

        # One marked landing at cell 4, and nothing beyond it: a finite chain.
        landed = flat()
        landed.rows[0].tape = 1 << (4 + _RING)
        assert _true_set_after_walk(landed, 4) == {(0,)}

        # Every multiple of the stride marked: the chain never escapes.
        endless = flat()
        endless.rows[0].tape = sum(1 << (4 * k + _RING) for k in range(1, 200))
        assert _true_set_after_walk(endless, 4) is None

    def test_predict_rejects_a_true_row_that_will_not_escape(self) -> None:
        """A candidate whose TRUE row loops is declined, not emitted.

        Eight ``1``s inside the ring is two whole laps: every ring cell
        toggles twice, so position and tape both return to exactly where
        they started.  That is a proven state revisit, which is a ``loop``
        where no kill was named -- and a kill is what a loop has to be.
        A stdin read reaches the same answer through ``ConstructError``.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _predict,
            _work,
        )

        _work[0] = _WORK_BUDGET

        def sitting_on_a_mark(pos: int) -> _Builder:
            b = _Builder(1)
            for row in b.rows:
                row.pos, row.tape = pos, 1 << (pos + _RING)
            return b

        assert _predict(sitting_on_a_mark(0), "1" * 8) is None

        reads_stdin = _Builder(1)
        for row in reads_stdin.rows:
            row.pos, row.tape = -3, 0
        assert _predict(reads_stdin, "2") is None

    def test_the_arithmetic_kill_screens_agree_on_their_refusals(self) -> None:
        """``_after_ones_pop`` and ``_kill_fate`` decide fates without simulating.

        Both are closed forms over ``(pos, tape)``, which is what lets the
        kill sweep price every descent for free.  Their two refusals are a
        ``2`` landing at -3 -- a stdin read, fatal under the harness's empty
        script -- and a fixpoint that reaches neither verdict inside the pass
        cap.  The latter needs a row that stays marked without ever repeating
        a state: with a trailing flip on an empty tape every pass turns a
        *fresh* cell on and the position advances, so no state recurs.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            _after_ones_pop,
            _kill_fate,
        )

        # rem == 2 lands on -3, where the following `2` would read stdin.
        assert _after_ones_pop(0, 0, 3) is None
        assert _after_ones_pop(0, 0, 1) is not None

        assert _kill_fate(0, 0, 3, None) == "invalid"  # the read.
        assert _kill_fate(0, 0, 1, 3) == "invalid"  # the pass cap.
        assert _kill_fate(0, 0, 1, None) == "skip"


def test_nocomment_wide_declines_when_the_plan_outgrows_the_skip() -> None:
    """Past fifteen inputs the summand plan leaves no room to widen.

    ``room`` is what is left of a byte-sized skip once the guarded
    contribution's move-add-return block is paid for, and it goes negative at
    ``n == 15`` -- the plan stays at its one-cell form rather than being
    re-planned wider.  The build then stops on the tape limit, which is the
    reachable end of this path: the cell it would need is past 4096.
    """
    from esolangs.tools.boolean import parameterized

    table = "0" * (2**15 - 1) + "1"
    with pytest.raises(ValueError, match="past the interpreter's 4096-cell tape"):
        parameterized._nocomment_wide(table, 15, parameterized._TAPE)  # noqa: SLF001
