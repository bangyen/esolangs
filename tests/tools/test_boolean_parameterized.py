"""Unit tests for the parameterized (no-input) boolean generators.

Covers :mod:`esolangs.tools.boolean.parameterized`, whose languages take no
input and instead embed each input by substitution, plus the COD and Eval
generators that follow the same convention.
"""

import importlib
import io
import random
import re
from collections.abc import Iterable
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.parameterized import _instantiate_arrowqueue
from tests.tools.boolean_runners import one_two_three_result


def _parameterized_generators():
    """Return every parameterized generator the module exports.

    Read off ``__all__`` rather than hand-listed.  The roster used to name
    thirteen of the seventeen exports, so ``a_painter_ant``, ``cod`` and
    ``wii2d`` were silently exempt from the exactly-once and slot-order
    invariants below -- including ``cod``, which this module's own docstring
    claims to cover.  The exemption bought nothing (all three satisfy both
    invariants), which is what makes a silent roster worse than an explicit
    one: nobody chose it.  ``instantiate`` is the shared helper, not
    a generator, so it is the one name excluded, by name and for a reason.
    """
    from esolangs.tools.boolean import parameterized

    return [
        (name, parameterized.__dict__[name])
        for name in parameterized.__all__
        if name != "instantiate"
    ]


@pytest.mark.slow  # ~3s: builds every generator, up to n=4
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

    # The decode is exponential in the arity, so the swept cases cost
    # seconds: measured 9.3s at n=9 and 29.0s at n=10 (n=11 swept was 99.4s,
    # now sampled below).  n=9 used to stay in the fast run as the case
    # exercising the composed skip past a byte-sized index, but it is four
    # times the one-second budget every other case is held to.  The
    # mechanism is still proved on every push, just not at push time: CI's
    # `test` matrix job runs pytest unfiltered, so a slow-marked case runs
    # there like any other.  (The separate `-m slow` job is scoped to the
    # differential fuzzer's file and never selects these.)
    #
    # These are ~2x the figures first recorded here (4.1/13.0/43.5s), which
    # were measured before NoComment's tape became immutable.  The write
    # buffer that made that change affordable collapses *runs* of writes,
    # and this decode has none -- it writes a cell and moves -- so it pays a
    # tape rebuild on ~66% of steps.  Storing the tape as `bytes` rather
    # than a tuple of ints took the rebuild back to a memcpy and these cases
    # from 45.7/139.7/561.6s to what they are now; the residue over the
    # original is the immutable state the purity refactor bought.
    # n=11 is sampled rather than swept: the summand plan introduces no new
    # stage shape above n=10.  Measured plan sizes are q=2/4/6/10 at
    # n=8/9/10/11; n=9 first splits one bit's weight across stages, n=10
    # first carries both a repeated full stage and a mixed-cell stage, and
    # n=11 only repeats those same two shapes more often.  The emitter is a
    # uniform loop over plan entries with no branch keyed on stage index or
    # cell, so every shape is already swept exhaustively at the smallest
    # arity where it appears.  Sweeping n=11 cost 99.4s to re-prove that.
    @pytest.mark.parametrize(
        "n",
        [
            pytest.param(9, marks=pytest.mark.slow),
            pytest.param(10, marks=pytest.mark.slow),
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
        self._check_wide_arity(n, range(2**n))

    @pytest.mark.slow  # ~3s: the same decode at n=11, sampled
    def test_the_widest_arity_is_exact_on_sampled_rows(self) -> None:
        """The n=11 decode is checked where a stage boundary can go wrong.

        The rows are chosen rather than swept: every single-bit index, the
        all-zero and all-one rows, and both sides of each byte boundary --
        which is where a composed skip hands off between stages -- plus a
        stride through the rest so no region goes unvisited.
        """
        n = 11
        rows = {0, 2**n - 1}
        rows.update(1 << i for i in range(n))
        for edge in (255, 511, 1023, 2047):
            rows.update({edge - 1, edge, edge + 1} & set(range(2**n)))
        rows.update(range(0, 2**n, 41))
        self._check_wide_arity(n, sorted(rows))

    def _check_wide_arity(self, n: int, rows: Iterable[int]) -> None:
        """Run the four probe tables at arity ``n`` over ``rows``."""
        from esolangs.tools.boolean import parameterized

        tables = {
            "alternating": "01" * (2 ** (n - 1)),
            "parity": "".join(str(bin(r).count("1") % 2) for r in range(2**n)),
            "constant": "0" * (2**n),
            "and": "0" * (2**n - 1) + "1",
        }
        rows = list(rows)
        for name, table in tables.items():
            template = parameterized.nocomment(table)
            for combo in rows:
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


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0.

    RAM0 prints a full state dump at halt; the generator's answer is the
    final ``z`` value, read from the dump's ``z: N`` line.
    """

    def run_ram0(self, prog: str) -> str:

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
        """The drain is required: a ring needs the queue it expects.

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

    def test_bare_ring_is_entry_sensitive(self) -> None:
        """A bare ring sustains on right-entry and *halts* on down-entry.

        The two ways a subtree is entered are not interchangeable, which is
        the sharpest edge in the construction: the tree's top level is
        entered heading down at column 1, while every recursive subtree is
        entered heading right at its own ``(0, 0)``.  A bare
        :data:`_TREE_1` only loops under the second.  Pinned because a
        refactor that "simplified" the top-level entry to hand a bare ring
        the down-entry would silently turn every constant-``1`` table into
        a halt -- reporting ``0`` for every entry.

        See ``docs/arrowqueue_generator.md`` (lemmas L2/L2'/L4).
        """
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.tools.boolean.parameterized import _TREE_1
        from esolangs.vm import run_until_halt_or_cycle

        rdlu = (0, 1, 2, 3)

        def verdict(state: tuple[int, int, int, tuple[int, ...]]) -> str:
            machine = _Machine(list(_TREE_1))
            machine.state = (*state, not machine.grid)
            return "0" if run_until_halt_or_cycle(machine) else "1"

        assert verdict((0, 0, 0, rdlu)) == "1"  # right-entry: the ring closes
        assert verdict((0, 1, 1, rdlu)) == "0"  # down-entry: it does not

    def test_constant_one_never_tops_out_as_a_bare_ring(self) -> None:
        """The top-level tree always carries a drain, so down-entry is safe.

        What makes the entry-sensitivity above harmless: a constant table
        folds to ``_drained_leaf(v, n)`` with ``n >= 1`` (a one-entry table
        is refused), so the top-level leaf's first ``+`` sits at ``(0, 1)``
        -- exactly where the header's descent lands -- and the bare ring
        appears only nested at column offset 3, where entry is rightward.
        """
        from esolangs.tools.boolean.parameterized import (
            _TREE_1,
            _drained_leaf,
            _tree,
        )

        for n in range(1, 6):
            assert _tree(list("1" * (2**n))) == _drained_leaf("1", n)

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                assert _tree(list(table)) != list(_TREE_1), table


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

        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2


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

        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert len(re.findall(r"\{X\d+\}", template)) == 2

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 5, 20),
            ("0110", 9, 44),
            ("0001", 9, 44),
            ("11110000", 8, 20),
            ("01101001", 17, 96),
        ],
    )
    def test_the_template_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        """The drawing's extents, per table.

        COD's template is a grid of boxes: walls sized from their contents,
        rows padded to a common width, blocks stacked and joined.  Every
        one of those is arithmetic on a length, and getting one wrong
        leaves a *working* program -- the cod still routes to the same
        leaf, the box is just a character wider or the padding lands on
        the other side.  The truth-table sweeps in this class read the
        printed bit and see none of it.

        ``11110000`` is the reduction case: it depends on one of its three
        inputs and draws at 8 by 20 where a real three-input table needs
        17 by 96.
        """
        from esolangs.tools.boolean import parameterized

        grid = parameterized.cod(table).split("\n")
        assert len(grid) == rows
        assert max(len(row) for row in grid) == columns

    def test_a_dead_box_wall_frames_its_contents(self) -> None:
        """The wall is two wider than the names it encloses.

        One name gives ``~~~`` and two give ``~~~~``: a wall that grew or
        shrank by one would still draw a box, and the cod would still be
        trapped in it, since what stops the cod is meeting a wall at all
        rather than the wall's length.
        """
        from esolangs.tools.boolean.cod import _cod_dead_box

        one = _cod_dead_box((0,)).split("\n")
        assert one == ["~~~", "~{X0}~", "~~~"]

        two = _cod_dead_box((0, 1)).split("\n")
        assert two == ["~~~~", "~{X0}{X1}~", "~~~~"]

    def test_the_grid_uses_only_cod_characters(self) -> None:
        """Nothing but the language's glyphs, the slots, and layout space."""
        from esolangs.tools.boolean import parameterized

        allowed = set(" ()+-012<>X{}~\n")
        for table in ("01", "0110", "01101001", "11110000"):
            assert set(parameterized.cod(table)) <= allowed, table

    def test_no_row_carries_trailing_space(self) -> None:
        """Rows are trimmed, so a row's length is its content's length."""
        from esolangs.tools.boolean import parameterized

        for table in ("01", "0110", "01101001"):
            for row in parameterized.cod(table).split("\n"):
                assert row == row.rstrip(), (table, repr(row))

    def test_a_table_ignoring_inputs_takes_the_reduced_build(self) -> None:
        """The reduction is kept only when it is strictly shorter.

        Both builds compute the table, so no truth-table assertion can see
        which was taken; the choice is a single length comparison.  Of the
        276 tables through three inputs, 46 have a reduction available at
        all.  The lengths are exact rather than bounded: a bound catches an
        inflating mutant only when the inflation happens to cross it, and
        says nothing about one that changes the drawing without growing it.
        """
        from esolangs.tools.boolean import parameterized

        for table in ("11110000", "00001111", "10101010"):
            assert len(parameterized.cod(table)) == 113, table
        assert len(parameterized.cod("01101001")) == 1504

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

    def test_reorder_cost_selects_the_emitted_template(self) -> None:
        """The pricing model matches every candidate and picks the shortest."""
        from esolangs.tools import boolean
        from esolangs.tools.boolean.helpers import permute_truth_table
        from esolangs.tools.boolean.parameterized import (
            _eval_cost,
            _eval_ordered,
            _eval_stack_programs,
        )

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                costs = []
                for arrangement, ops in _eval_stack_programs(n).items():
                    permuted = permute_truth_table(table, tuple(reversed(arrangement)))
                    assert _eval_cost(permuted, ops) == len(
                        _eval_ordered(permuted, ops)
                    )
                    costs.append(_eval_cost(permuted, ops))
                assert len(boolean.eval(table)) == min(costs)

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

    def test_reorder_catalog_invariants(self) -> None:
        """The built words are capped, deduplicated and (length, ~<*<=)-sorted.

        The sort order is required: ``_eval_stack_programs`` folds the
        words first-claim-wins, so cheapest-first is what makes every
        claimed string minimal, and the ``~`` < ``*`` < ``=`` tie order is
        what keeps the fold byte-identical to the search it replaced.
        """
        from esolangs.tools.boolean.parameterized import (
            _EVAL_MAX_OPS,
            _eval_reorders,
        )

        built = _eval_reorders()
        assert len(set(built)) == len(built)
        assert built[0] == ""
        assert all(len(ops) <= _EVAL_MAX_OPS for ops in built)
        rank = {"~": 0, "*": 1, "=": 2}
        keys = [(len(ops), [rank[op] for op in ops]) for ops in built]
        assert keys == sorted(keys)

    def test_reorder_words_are_the_capped_reachable_set(self) -> None:
        """Every built word replays, and the built set is exactly the cap's.

        The construction admits words the old catalog never listed -- longer
        spellings of arrangements a shorter word already claims -- so the
        pin is on what survives the fold, not on the raw word list.  The
        count that must hold is the arrangement count: 735 from ``n == 12``
        on, which is where the catalog froze.
        """
        from esolangs.tools.boolean.parameterized import _eval_stack_programs

        assert len(_eval_stack_programs(12)) == 735
        assert len(_eval_stack_programs(13)) == 735
        assert len(_eval_stack_programs(7)) == 620
        assert len(_eval_stack_programs(4)) == 24

    def test_reorder_catalog_matches_search(self) -> None:
        """The catalog fold reproduces the search it replaced, byte for byte.

        The breadth-first walk over (tree stack, input stack, active stack)
        that used to run inside ``_eval_stack_programs`` lives on here as
        the specification.  Equality is asserted on the item *lists*, not
        the dicts: the shipped fold must claim the same arrangements with
        the same op strings in the same order, because ``eval``'s stable
        sort breaks total-length ties by that order.
        """
        from collections import deque

        from esolangs.tools.boolean.parameterized import (
            _EVAL_MAX_OPS,
            _eval_stack_programs,
        )

        def searched(n: int) -> dict[tuple[int, ...], str]:
            start: tuple[tuple[int, ...], tuple[int, ...], int] = (
                (),
                tuple(range(n)),
                0,
            )
            seen = {start: ""}
            frontier = deque([start])
            reached: dict[tuple[int, ...], str] = {}
            while frontier:
                state = frontier.popleft()
                tree, read, active = state
                ops = seen[state]
                if active == 0 and not tree and read not in reached:
                    reached[read] = ops
                if len(ops) >= _EVAL_MAX_OPS:
                    continue
                stacks = {0: tree, 1: read}
                moves = [((tree, read, 1 - active), "~")]
                flipped = tuple(reversed(stacks[active]))
                moves.append(
                    ((flipped, read, active), "*")
                    if active == 0
                    else ((tree, flipped, active), "*")
                )
                if stacks[active]:
                    moved, rest = stacks[active][-1], stacks[active][:-1]
                    other = (*stacks[1 - active], moved)
                    moves.append(
                        ((rest, other, active), "=")
                        if active == 0
                        else ((other, rest, active), "=")
                    )
                for next_state, op in moves:
                    if next_state not in seen:
                        seen[next_state] = ops + op
                        frontier.append(next_state)
            return reached

        for n in range(6):
            assert list(_eval_stack_programs(n).items()) == list(searched(n).items())

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

    Every arity is *constructed* -- the stored plan tables that used to
    serve ``n <= 3`` are retired (see git history).  Small arities build
    in ``one_two_three`` from a bare-fill seed and frozen separation
    schedules; wider tables go through ``one_two_three_construct``
    unchanged.  Both routes replay every row on the real interpreter
    before returning a template, and the sweeps here re-check every
    ``n <= 3`` row against a per-command run of the interpreter.
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
        template with such a row would hang the suite rather than report a 1.
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

    def test_batched_gate_agrees_with_the_interpreter(self) -> None:
        """The construction's replay gate matches a per-command run.

        ``_replay_verdict`` executes a maximal ``1``/``2`` run at a time in
        closed form instead of one command at a time, which is what makes
        the gate affordable on a six-input template (95s to 0.28s at five
        inputs).  That batching is only safe if it decides exactly what the
        real interpreter decides, so every row of every emitted template through
        three inputs is checked both ways here -- against a per-command run
        of :class:`_Machine`, not against the builder's own model, which
        shares no code with either.

        Divergence is the case worth pinning: a batched cycle detector that
        sampled the wrong events could miss a loop and call it a halt.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.one_two_three_construct import _replay_verdict

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

        ``_replay_verdict`` is a general 123 interpreter -- it batches
        maximal runs into closed form -- but every other test drives it on
        programs the construction *built*, which are a narrow, well-behaved
        shape: the pointer stays in range, the reads never fire, the loops
        are the ones the plan laid.  An executor that is wrong outside that
        shape agrees on all of them and still ships.

        Random programs over the three commands close that.  The comparison
        is against a per-command run of :class:`_Machine`, which shares no
        code with the batching, and both sides are treated alike: a program
        that reads stdin, or that neither halts nor repeats a state inside
        the budget, is skipped rather than counted as a disagreement.

        Sampled at a fixed seed so a failure is reproducible; the baseline
        is 177 comparable programs and zero disagreements.
        """
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools.boolean.one_two_three_construct import _replay_verdict

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

        The two exact-template tests above go through
        ``parameterized.one_two_three``, which sends ``n <= 3`` to the
        separation-law route and never enters this module at all.  So the
        wider construction had no golden of its own, and a plan that
        emitted three bytes more per table, or two fewer, changed nothing
        any test compared.
        """
        from esolangs.tools.boolean.one_two_three_construct import construct

        assert construct("01") == (
            "22{X0}11121211222211112332332233222211112221113311111112222222123311111111"
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        The paint flag and the separation law move a handful of bytes
        per table without changing a verdict, so no single table is a
        reliable witness -- ``00111000`` moves by two and ``11111111`` by
        two the other way.  The sum over the sweep is, and it is the same
        shape of assertion the small route already carries.
        """
        from esolangs.tools.boolean.one_two_three_construct import construct

        total = sum(len(construct(format(value, "08b"))) for value in range(256))
        assert total == 155074

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

    def test_a_wider_table_is_constructed(self) -> None:
        """A four-input table builds through the constructed route.

        This used to assert a :class:`ValueError`: the recorded reason was
        that an inert embed shifts the pointer phase the plan decodes.
        That bound the phase-decode shape, not the language — the
        constructed route re-synchronizes every instantiation's pointer
        after each embed (see ``one_two_three_construct``) — so the gate
        fell.  Every row of the template is replayed here on the real
        interpreter, the same execution gate the generator itself applies
        before returning.  A build that drains the deterministic work
        budget still raises rather than emitting; ``docs/limitations.md``
        records the coverage.
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

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("00000000", 72),
            ("10000000", 368),
            ("00010111", 210),
            ("01101001", 160),
        ],
    )
    def test_three_inputs_take_the_small_route(self, table: str, length: int) -> None:
        """``n == 3`` builds from the separation law, not the wide route.

        Both routes emit a *correct* template, so every truth-table
        assertion above passes either way and the choice is invisible to
        them.  It is worth a great deal though: swept over all 256
        three-input tables, the wide constructor's template is larger on
        every one of them, from 1.5x up to 10.5x (``00000001`` is 90 bytes
        small against 944 wide).  These lengths pin the routing boundary at
        ``n > 3``.
        """
        from esolangs.tools.boolean import parameterized

        assert len(parameterized.one_two_three(table)) == length

    @pytest.mark.slow
    def test_the_separation_law_is_the_least_mean(self) -> None:
        """The law's constants are re-derived, not trusted.

        ``_LAWS`` claims one selection rule at every arity: over constant
        walk seeds and alternating pure-test displacement vectors, the
        law with the least mean template length.  This re-runs that sweep
        at ``n <= 2`` and checks the shipped constants win it, so a
        hand-edited constant fails here rather than shipping quietly.
        ``n == 3`` is left to the exhaustive build sweep -- its domain is
        13 laws over 256 tables, minutes rather than seconds.
        """
        from itertools import product

        from esolangs.tools.boolean.one_two_three import (
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

    def test_the_wide_route_is_bigger_where_they_overlap(self) -> None:
        """The small route earns its place at the arity they share.

        The routing boundary is only defensible if the two constructions
        are actually compared at an arity both can serve, which this does
        directly rather than through the emitted length above.
        """
        from esolangs.tools.boolean.one_two_three import one_two_three
        from esolangs.tools.boolean.one_two_three_construct import construct

        for table in ("00000000", "00000001", "01101001"):
            assert len(construct(table)) > len(one_two_three(table)), table

    @pytest.mark.parametrize(
        ("table", "template"),
        [
            ("01", "{X0}223311122212331111"),
            ("0001", "22{X0}22{X1}22331113322331111332133121233111111121121"),
        ],
    )
    def test_the_emitted_template_is_exact(self, table: str, template: str) -> None:
        """The construction is deterministic down to the byte.

        ``_construct_small`` builds one prototype per arity, so there is
        no candidate field and no tie-break: the emission is a function
        of the law and the table alone.  Pinning two templates exactly is
        what turns "deterministic" from a claim into a check -- a change
        to the law's constants, or to the order its tests fire in, moves
        these bytes even where it leaves every truth-table assertion
        passing.
        """
        from esolangs.tools.boolean import parameterized

        assert parameterized.one_two_three(table) == template

    def test_the_paint_pass_is_only_run_when_something_was_painted(
        self,
    ) -> None:
        """``b.test()`` after the paints is conditional, and the flag varies.

        Of the 276 tables through three inputs, 10 need no paint at all,
        so the flag is genuinely two-valued rather than a constant
        dressed as one.  Forcing it either way leaves every template
        correct -- the extra or missing test costs or saves commands
        without changing the verdict -- so only the emitted size sees it.
        The total is asserted rather than one table because the flag's
        effect is spread across the whole sweep; it also pins the
        separation law's price, 55238 characters against the retired
        schedules' 43020 and the wide constructor's 158152 -- the law
        gives up 1.28x to delete the table and keeps 2.9x over the route
        that needs none.
        """
        from esolangs.tools.boolean import parameterized

        total = 0
        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                total += len(parameterized.one_two_three(table))
        assert total == 55238

    def test_a_seed_with_even_positions_is_refused(self) -> None:
        """The junky verdict rejects a seed whose rows are not distinct odd.

        The paint offsets are collision-free only because every live row
        sits at a distinct *odd* position -- two rows sharing an offset
        would have to sit one cell apart, which odd-and-distinct forbids.
        So the precondition is what the collision-freedom argument rests
        on.  The shipped law separates to odd positions at every arity,
        so no build reaches the raise; the state is constructed here
        instead, which is what keeps the guard checked rather than
        merely asserted.
        """
        from esolangs.tools.boolean.one_two_three import (
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

        ``00111000`` has 1-rows above 0-rows, so its build takes the
        shield paints as well as the embed, separation, kill, and
        endgame — a witness that every stage is on a real trajectory,
        not only inferred from ``construct()``'s success.
        """
        from esolangs.tools.boolean import one_two_three_construct as construct_mod

        called: set[str] = set()
        originals = {
            name: getattr(construct_mod, name)
            for name in ("_phase_a", "_separate", "_paint", "_verdict", "_endgame")
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

    def test_the_searched_routes_worst_tables_build_at_once(self) -> None:
        """The tables that starved the searched verdict are ordinary now.

        ``1000110011010101`` burned a whole four-input budget under one
        mark geometry and ``0100000011001001`` exhausted the other —
        the pair that forced the old geometry probe.  The planned
        verdict never anchors a test on a mark cell, so a single
        geometry serves both; each build is checked row by row on the
        interpreter.
        """
        from esolangs.tools.boolean.one_two_three_construct import construct

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

        The full sweep belongs in ``scripts/check_123_four_input.py`` rather
        than the test suite.  This one-table witness keeps its execution gate
        local: all sixteen rows must halt or revisit an exact interpreter
        state with the table's verdict, never pass through a fuel limit.
        """
        from esolangs.tools.boolean.one_two_three_construct import construct

        table = "1100010001000111"
        template = construct(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            assert self.run(program) == table[combo], (table, bits)

    def test_paint_marks_one_cell_and_restores_every_position(self) -> None:
        """``_paint(k)`` flips exactly cell ``pos + k`` per row, in place.

        The shield algebra rests on this: two walk-descend blocks whose
        stripes cancel everywhere but the top cell.  Checked across rows
        at distinct positions with junk tapes, for the ``k == 1`` short
        form and a spread of wider offsets.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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

    def test_the_verdict_checks_its_position_preconditions(self) -> None:
        """A state violating the parity law raises instead of emitting.

        The shield algebra needs every live position distinct and odd;
        separation has delivered that at every probed arity, but the
        verdict re-checks rather than assumes, so a wider arity that
        ever broke the parity would raise — never hand out a template
        whose fates the plan cannot vouch for.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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
        """``test(kills=...)`` requires every named victim to provably loop."""
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
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_a_kill_that_never_fires(self) -> None:
        """``test(kills=...)`` refuses a close where a victim tested FALSE.

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
            b.test(kills=frozenset({(0,)}))

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
            b.test()

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

    def test_the_endgame_parks_survivors_and_reports_a_state_it_cannot(
        self,
    ) -> None:
        """Parking is what makes a template halt, so failing it must raise.

        A state with no survivors is already parked.  Four occupied residues
        mod 4 take the ring round -- rows of equal residue land on the same
        cell and fuse, so a class has to be freed before the descent can
        collapse them.  The convergence allowance is ``64 * 2**n + 64``
        passes, and a builder carrying a small ``n`` beside rows spread far
        wider than that ``n`` implies is what outlasts it: the guard is a
        real exit, not decoration.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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
        from esolangs.tools.boolean import one_two_three_construct as module

        def refuse(*_: object, **__: object) -> None:
            raise module.ConstructError("verdict precondition: constructed refusal")

        monkeypatch.setattr(module, "_verdict", refuse)
        with pytest.raises(ValueError, match="123 construction failed"):
            module.construct("0110")

    def test_a_looping_row_reads_as_a_one(self) -> None:
        """A 1-row is decided by cycle detection, not by halting.

        A 1-row does not halt -- it is the loop the kill built -- so the
        verdict comes from Brent's cycle detection rather than from the
        machine stopping.  Both readings of that row are pinned here: the
        real interpreter's, which is the shipped contract, and
        :func:`_replay_verdict`'s, the in-module executor the suite uses
        elsewhere.  They must agree, and the 1-row must be the looping one.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
            _replay_verdict,
            construct,
        )

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
        from esolangs.tools.boolean.one_two_three_construct import construct

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
        after which the rest is a plain right-walk, and it charges the budget
        like every other closed form.  ``apply_token`` resolves a ``{Xi}``
        fill against the row's own bits; a plain token is passed straight
        through.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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
        merely wrong -- the builder has to decline the candidate that
        reached this cell instead of emitting it.  The neighbouring
        positions are the contrast: -2 lands on 0 (printing a junk byte no
        snapshot sees) and anything else is a plain step right.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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

        A fresh builder starts every row on cell 0 with a blank tape, which
        is already a FALSE cell, so the close is free.  Flipping cell 0
        first forces the walk, and the emitted ``2``s are what carry every
        row to a clean cell -- emitting none there would leave the next
        segment starting on a TRUE cell.
        """
        from esolangs.tools.boolean.one_two_three_construct import (
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
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _replay_twos,
        )

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
        from esolangs.tools.boolean.one_two_three_construct import _replay_verdict

        assert _replay_verdict("") == "0"
        assert _replay_verdict("xyz") == "0"  # no command: nothing to run
        # The NOPs are skipped, so padding a program cannot change its verdict.
        assert _replay_verdict("1x1") == _replay_verdict("11")
        assert _replay_verdict("x1y1z") == _replay_verdict("11")


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
