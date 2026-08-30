"""Unit tests for the parameterized (no-input) boolean generators.

Covers :mod:`esolangs.tools.boolean.parameterized`, whose languages take no
input and instead embed each input by substitution, plus the COD and Eval
generators that follow the same convention.
"""

import importlib
import io
import random
from contextlib import redirect_stdout
from unittest.mock import patch

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


@pytest.mark.slow  # 2.8s: builds every generator, up to n=4
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
    import importlib

    # ``from ... import minifuck`` binds the cache-wrapped generator that the
    # package re-exports, not the module the helper lives in.
    module = importlib.import_module("esolangs.tools.boolean.minifuck")

    assert module._reconverged("01", [], 1) is None  # noqa: SLF001
    assert module._reconverged("01011010", [0, 1, 2], 3) is None  # noqa: SLF001


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

    # The decode is exponential in the arity, so the cost is all in the two
    # widest cases: measured 4.1s at n=9, 13.0s at n=10 and 43.5s at n=11,
    # against a one-second budget.  n=9 stays in the fast run as the case
    # that still exercises the composed skip past a byte-sized index; the
    # two above it prove the same mechanism and sit out.
    @pytest.mark.parametrize(
        "n",
        [
            9,
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
        run(prog, io_, limit=500)
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

        ``docs/walls.md`` records NAND, NOR and XNOR as unreachable.  That
        is true of programs that *read* their inputs; embedding them lifts
        it, and this is the check that says so.

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

        def forbidden(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("a two-input table reached the search")

        with (
            patch.object(module, "_find_column", forbidden),
            patch.object(module, "_find_parked", forbidden),
        ):
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
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        for table_int in range(16):
            table = format(table_int, "04b")
            plan = module._derive_staging(table, 2)  # noqa: SLF001
            assert plan is not None, table
            sep_index, settle, brackets, acc = plan
            assert 0 <= sep_index < len(module._SEPS), (table, plan)  # noqa: SLF001
            assert settle in (0, 1), (table, plan)
            assert isinstance(brackets, int), (table, plan)
            assert 0 <= brackets <= module._MAX_BRACKETS, (table, plan)  # noqa: SLF001
            assert 9 <= acc <= module._MAX_ACC, (table, plan)  # noqa: SLF001

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

        def forbidden(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("a degenerate table reached the search")

        checked = 0
        with (
            patch.object(module, "_find_column", forbidden),
            patch.object(module, "_find_parked", forbidden),
        ):
            for table_int in range(256):
                table = format(table_int, "08b")
                if len(module._essential_inputs(table, 3)) > 2:  # noqa: SLF001
                    continue
                checked += 1
                template = module.minifuck.__wrapped__(table)
                for combo in range(8):
                    bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                    got = self.run_minifuck(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"
        assert checked == 38, checked

    @pytest.mark.slow  # 15.4s: the derivation runs for every staged arity
    def test_a_table_with_no_staging_falls_through(self) -> None:
        """An unplanned table returns None from ``_staged`` rather than raising.

        Both three-input plans are now complete, so the fall-through is
        exercised at an arity that has no plan at all -- which is the case
        that matters, since it is what lets a wider table reach the searches
        instead of failing outright.
        """
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.minifuck import _STAGED_ARITIES, _staged

        assert 4 not in _STAGED_ARITIES, "four inputs are expected to be ungated"
        # The gate is what makes the miss cheap: without it a four-input
        # table would grind through the whole enumeration before giving up.
        assert _staged("1" * 16, 4) is None
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

        def forbidden(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("reached the search")

        searched = []
        with (
            patch.object(module, "_find_column", forbidden),
            patch.object(module, "_find_parked", forbidden),
        ):
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
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        assert module._SEPS[:2] == module._SCAN_SEPS, module._SCAN_SEPS  # noqa: SLF001
        assert len(module._SEPS) > len(module._SCAN_SEPS), module._SEPS  # noqa: SLF001
        # Every separator index the enumeration yields must exist, and it
        # must offer all of them -- the ten stragglers that need separators
        # past the scanned pair are the whole reason ``_SEPS`` is wider.
        offered = {sep_index for sep_index, *_rest in module._stagings(3)}  # noqa: SLF001
        assert offered == set(range(len(module._SEPS))), offered  # noqa: SLF001
        # ...as must the index the one stored exception names.
        for plan in module._EXCEPTIONS.values():  # noqa: SLF001
            for key, (sep_index, *_rest) in plan.items():
                assert 0 <= sep_index < len(module._SEPS), (key, sep_index)  # noqa: SLF001

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
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        written_down = {
            "const1": 1,
            "~b0": 16,
            "b0": 17,
            "const0": 18,
            "~b1": 19,
            "b1": 20,
        }
        for n in (2, 3, 4):
            assert module._degenerate_cells(n) == written_down, n  # noqa: SLF001
        # One input leaves no ``b1`` to find, and the route asks for whatever
        # is there rather than assuming all six.
        assert module._degenerate_cells(1) == {  # noqa: SLF001
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
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        expected = [
            (sep_index, settle, brackets, acc)
            for sep_index in range(len(module._SEPS))  # noqa: SLF001
            for settle in (0, 1)
            for brackets in range(module._MAX_BRACKETS + 1)  # noqa: SLF001
            for acc in range(9, module._MAX_ACC + 1)  # noqa: SLF001
        ]
        assert list(module._stagings(3)) == expected  # noqa: SLF001
        # Every staging the derivation hands back is one the enumeration
        # offers -- so the caps and the loops cannot have drifted apart.
        offered = set(expected)
        for table, staging in module._derived_plans(2).items():  # noqa: SLF001
            assert staging in offered, (table, staging)

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
        earned would show up here.  It also covers the one stored exception,
        which is the entry no enumeration re-derives.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        plans = {
            2: {
                format(t, "04b"): module._derive_staging(format(t, "04b"), 2)  # noqa: SLF001
                for t in range(16)
            },
            3: {
                key: module._derive_staging(key, 3)  # noqa: SLF001
                for key in ("00000001", "01111111", "01101101", "00010111")
            },
        }
        for n, plan in sorted(plans.items()):
            for key, staging in sorted(plan.items()):
                assert staging is not None, (n, key)
                sep_index, settle, suffix, acc = staging
                joint = module._embed(  # noqa: SLF001
                    n,
                    settle=settle,
                    sep=module._SEPS[sep_index],  # noqa: SLF001
                )
                module._clamp(joint)  # noqa: SLF001
                module._walk_to(joint, module._BASE - 1)  # noqa: SLF001
                joint.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
                module._clamp(joint)  # noqa: SLF001
                arrived = None
                for cell7 in (0, 1):
                    probe = joint.fork()
                    code = module._find_pool(probe, cell7, acc - 1)  # noqa: SLF001
                    if code is None:
                        continue
                    probe.emit(code)
                    module._walk_to(probe, acc - 1)  # noqa: SLF001
                    column = "".join(str(b) for b in probe.col(acc))
                    complement = "".join(str(1 - int(c)) for c in column)
                    if key in (column, complement):
                        arrived = column
                        break
                assert arrived is not None, (n, key, sep_index, settle, suffix, acc)

    @pytest.mark.slow  # 7.8s: builds the searching two-input template
    def test_instantiations_have_equal_length(self) -> None:
        """No instantiation leaks its inputs through the program's length."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minifuck("0110")
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, f"unequal instantiation lengths: {lengths}"

    @pytest.mark.slow  # 9.0s: builds the searching two-input template
    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minifuck("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_bad_table_rejected(self) -> None:
        """A table whose length is not a power of two is rejected."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.minifuck("011")

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
        assert len(growing.tape) > 3, "the tape grows to meet the pointer"

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

    def test_a_search_from_a_dead_row_expands_nothing(self) -> None:
        """A state holding a dead row is pruned rather than explored.

        A dead row cannot be steered back, so every state below it is one
        the generator could never use.  Nothing in the search's own
        alphabet kills a row -- only a print does -- so the prune exists
        for a state that arrived dead, which is what this hands it.
        """
        from esolangs.tools.boolean.minifuck import _clamp, _embed, _search

        joint = _embed(2)
        _clamp(joint)
        # A print reads cells 0..7 as one byte and dies when it is zero, so
        # clear the byte and print from past it, where the flip lands outside.
        row = joint.ms[0]
        row.tape[:8] = [0] * 8
        row.ptr = 9
        row.exec(".")
        assert row.dead

        def accept(_new: list[object], _code: str) -> str | None:
            raise AssertionError("a pruned state must never reach accept")

        assert _search(joint, accept, 3) is None

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

    def test_the_parked_search_finds_a_column_under_the_pointer(self) -> None:
        """The last route asks for the answer *and* the pointer that reads it.

        Producing the column is not enough on its own: walking back to it
        re-crosses, and so changes, that very cell.  So a hit is a state
        whose rows agree on the pointer, with the wanted column (or its
        complement) immediately to the right of it, inside the window.
        """
        from esolangs.tools.boolean.minifuck import (
            _BASE,
            _SETTLE,
            _SPAN,
            _embed,
            _find_parked,
        )

        want = (0, 1, 1, 0)  # XOR's column
        window = _BASE + 2 * _SPAN + 14

        hits = _find_parked(_embed(2, settle=_SETTLE), want, window, 6, 3)
        assert hits, "the XOR column should be parked on within six steps"
        for code, cell in hits:
            assert set(code) <= set("<[x")
            assert 8 <= cell < window

        # The limit stops the collection early rather than filling it.
        assert len(_find_parked(_embed(2, settle=_SETTLE), want, window, 8, 1)) == 1

        # A window that excludes the answer's cell yields nothing.
        assert _find_parked(_embed(2, settle=_SETTLE), want, 10, 6, 3) == []

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

    def test_the_routes_are_tried_in_order_and_then_give_up(self) -> None:
        """With every route failing the generator refuses rather than guesses.

        The three routes are ordered by cost -- the scans, the column
        search, then the parked search -- and the cheap ones answer every
        table at this arity, so the later ones are never reached by a real
        build.  Blocking each in turn is what runs them: the column search
        is stubbed away and the parked search shrunk to a depth it cannot
        succeed at, leaving the final refusal.

        ``__wrapped__`` steps around the cache, so a stubbed build cannot
        be handed to a later caller as if it were real.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_try_print", lambda *_a, **_k: None)
            patch.setattr(module, "_find_column", lambda *_a, **_k: None)
            patch.setattr(module, "_PARKED_DEPTH", 6)
            patch.setattr(module, "_PARKED_LIMIT", 2)
            with pytest.raises(ValueError, match="could not build"):
                module.minifuck.__wrapped__("0110")

    def test_the_parked_route_returns_the_program_it_prints(self) -> None:
        """A parked candidate that prints ends the search there.

        Which of the collected candidates survives the endgame is settled
        by running it, so the route tries each in turn and returns the
        first that prints the table -- it does not rank them or keep
        looking once one works.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        from esolangs.tools.boolean.minifuck import _find_parked as real_parked

        parked = {"fired": False}

        def spy(*args: object, **kwargs: object) -> list[tuple[str, int]]:
            parked["fired"] = True
            return real_parked(*args, **kwargs)  # type: ignore[arg-type]

        class _Printed:
            def template(self) -> str:
                return "SENTINEL"

        def only_after_parking(*_a: object, **_k: object) -> object:
            return _Printed() if parked["fired"] else None

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_find_parked", spy)
            patch.setattr(module, "_try_print", only_after_parking)
            patch.setattr(module, "_find_column", lambda *_a, **_k: None)
            patch.setattr(module, "_PARKED_DEPTH", 6)
            patch.setattr(module, "_PARKED_LIMIT", 2)
            assert module.minifuck.__wrapped__("0110") == "SENTINEL"

        assert parked["fired"], "the parked route never ran"

    def test_a_found_column_is_walked_out_and_printed_from(self) -> None:
        """The column route emits its find, re-clamps, and scans for the print.

        A column is only half an answer -- the pointer still has to reach
        it -- so the route emits the search's code, clamps the rows back
        together, and then tries the accumulators in turn.  Stubbing the
        search to a cell it can reach is what exercises that body without
        paying for the search that normally finds it.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.minifuck")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_try_print", lambda *_a, **_k: None)
            patch.setattr(module, "_find_column", lambda *_a, **_k: ("", 20))
            patch.setattr(module, "_PARKED_DEPTH", 4)
            patch.setattr(module, "_PARKED_LIMIT", 1)
            with pytest.raises(ValueError, match="could not build"):
                module.minifuck.__wrapped__("0110")

    def test_a_park_the_walk_refuses_is_skipped(self) -> None:
        """The column route walks to each park in turn; some cannot be reached.

        ``_walk_to`` refuses a target it cannot reach rightward from a
        converged pointer, and that is a reason to try the next park rather
        than to fail the build.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        from esolangs.tools.boolean.minifuck import _BASE
        from esolangs.tools.boolean.minifuck import _walk_to as real_walk

        refused = {"n": 0}

        def refuse_first(joint: object, target: int) -> None:
            # The embed walks too, and to a fixed target; the route's parks
            # start one cell below it, so that is the one to refuse.
            if refused["n"] == 0 and target == _BASE - 2:
                refused["n"] += 1
                raise ValueError("forced: this park is unreachable")
            real_walk(joint, target)  # type: ignore[arg-type]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_try_print", lambda *_a, **_k: None)
            patch.setattr(module, "_find_column", lambda *_a, **_k: None)
            patch.setattr(module, "_walk_to", refuse_first)
            patch.setattr(module, "_PARKED_DEPTH", 4)
            patch.setattr(module, "_PARKED_LIMIT", 1)
            with pytest.raises(ValueError, match="could not build"):
                module.minifuck.__wrapped__("0110")

        assert refused["n"] == 1, "the forced refusal never fired"

    @pytest.mark.slow  # 2.4s: the XOR arm scans every accumulator and fails
    def test_a_degenerate_table_falls_back_to_searching_for_its_column(self) -> None:
        """Past the fixed cells the degenerate route searches, then reports.

        A table depending on at most one input is a constant, a projection,
        or a negated projection, and each of those already stands as a
        column somewhere after the embed -- at a known cell for the first
        two inputs, and at a searched one beyond that.  Every table at this
        arity is answered by the known cells, so the search below them only
        runs when those are taken away.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        from esolangs.tools.boolean.minifuck import _degenerate, _degenerate_cells

        # b1's cell carries "0101" at n == 2, so pointing the stubbed search
        # at it stands in for a search that succeeded.  The cell is measured
        # off the embed rather than written down, so read it from there.
        b1_cell = _degenerate_cells(2)["b1"]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_degenerate_cells", lambda _n: {})
            patch.setattr(module, "_find_column", lambda *_a, **_k: ("", b1_cell))
            found = _degenerate("0101", 2)
        assert found is not None, "the searched column should still print"
        assert "{X0}" in found
        assert "{X1}" in found

        # XOR is not degenerate, so no accumulator prints it however the
        # search claims to have gone: the scan runs out and reports that.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_degenerate_cells", lambda _n: {})
            patch.setattr(module, "_find_column", lambda *_a, **_k: ("", b1_cell))
            assert _degenerate("0110", 2) is None

        # And a search that finds nothing at all reports that directly.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_degenerate_cells", lambda _n: {})
            patch.setattr(module, "_find_column", lambda *_a, **_k: None)
            assert _degenerate("0101", 2) is None


@pytest.mark.slow  # 1.9s: builds every generator to compare fill widths
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
        from esolangs.tools.boolean import parameterized

        built = 0
        for value in range(256):
            table = format(value, "08b")
            try:
                template = parameterized.pct_squared_minus_one(table)
            except ValueError:
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

    def test_non_subcube_table_refused_not_miscomputed(self) -> None:
        """A table the cascade cannot build is refused rather than served wrong.

        ``00000110`` is neither a conjunction of literals nor the complement
        of one, so no cascade computes it and the generator says so.
        """
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="conjunction or disjunction"):
            parameterized.pct_squared_minus_one("00000110")

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
    """

    def run(self, program: str) -> str:
        return one_two_three_result(program)

    def instantiate(self, template: str, bits: list[int]) -> str:
        from esolangs.tools.boolean.one_two_three import ONE, ZERO

        for i, bit in enumerate(bits):
            template = template.replace(f"{{X{i}}}", ONE if bit else ZERO)
        return template

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every one- and two-input table halts or loops per its entry."""
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

        for n in (1, 2):
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

    def test_wider_tables_are_declined(self) -> None:
        """A three-input table raises rather than emitting a wrong program."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="one- and two-input tables"):
            parameterized.one_two_three("01101001")

    def test_each_input_is_embedded_once(self) -> None:
        """Each placeholder appears exactly once, and no {Ci} appears."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                xs = re.findall(r"\{X(\d+)\}", template)
                assert sorted(xs) == [str(i) for i in range(n)], (table, xs)
                assert not re.findall(r"\{C(\d+)\}", template), table
