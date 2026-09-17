"""What every parameterized generator owes, and the small ones' own tests.

The rule the family is built on -- each input embedded exactly once, at equal
width, with the slots in name order -- is checked here across all of them.
The languages with a source file of their own have a test file to match:
test_boolean_one_two_three, _arrowqueue, _cod, _eval, _back and _nocomment.
"""

import importlib
import random
import re
from itertools import pairwise

import pytest


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
    from esolangs.tools import parameterized

    return [
        (name, parameterized.__dict__[name])
        for name in parameterized.__all__
        if name != "instantiate"
    ]


# The five generators that spell their inputs as runs of ``$`` themselves,
# by public name, and the module attribute each is.
_RUN_FORM = {
    "BIO": "bio",
    "Bitdeque": "bitdeque",
    "Minsky Swap": "minsky_swap",
    "BF-PDA": "bfpda",
    "Home Row": "home_row",
}


def _embedded_inputs(gen: object, template: str, n: int) -> list[int]:
    """The inputs ``template`` embeds, in the order it embeds them.

    A generator emits one run of the language's character per input; the
    runs are read off the example's setters -- :func:`~esolangs.tools.helpers.runs`
    refuses a run of the wrong width, a stray character or a run left over,
    so a template that embeds an input twice or out of step with its setters
    fails here rather than reading as in order.
    """
    from esolangs.tools.examples import BOOLEAN_EXAMPLES
    from esolangs.tools.helpers import runs

    example = next(e for e in BOOLEAN_EXAMPLES.values() if e.generator is gen)
    spans = runs(template, example.char, example.setters(template, n))
    return list(range(len(spans)))


def _run_form(setters: object, n: int) -> str:
    """A bare template of ``n`` runs, one per input, as wide as its setter.

    The synthetic template the width tests fill: nothing but the runs, so
    the filled length is the setters' alone.
    """
    return "".join("$" * len(zero) for zero, _one in setters("", n))


@pytest.mark.parametrize(("language", "attr"), sorted(_RUN_FORM.items()))
def test_run_form_generators_spell_their_own_runs(language: str, attr: str) -> None:
    """The generator emits the public runs itself: no ``{Xi}`` anywhere.

    The public template is the generator's output verbatim, and its runs
    of ``$`` sum to exactly its setters' widths -- one run per input,
    each as long as the code that replaces it.
    """
    import esolangs
    from esolangs.tools import parameterized

    for table in ("01", "0110", "01101001"):
        raw = getattr(parameterized, attr)(table)
        assert "{X" not in raw, (language, table)
        template = esolangs.generate(language, table)
        assert str(template) == raw, (language, table)
        assert template.count("$") == sum(len(zero) for zero, _ in template.setters)
        assert template.inputs == len(table).bit_length() - 1


@pytest.mark.slow  # ~3s: builds every generator, up to n=4
def test_parameterized_generators_embed_each_input_once() -> None:
    """Every no-input generator embeds each input exactly once.

    An input-capable language reads each of its n inputs exactly once per
    run; a no-input language's parameterized generator should match, so each
    input is embedded exactly once -- never re-embedded at multiple decision
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
            xs = _embedded_inputs(gen, template, n)
            cs = re.findall(r"\{C(\d+)\}", template)
            assert sorted(xs) == list(range(n)), (name, n, xs)
            assert len(xs) == n, (name, n, xs)
            assert not cs, (name, n, cs)
    # Guard the skip above: every generator covers at least n == 2, so a run
    # that checked far fewer templates than that means the sweep stopped
    # exercising the generators rather than the generators getting stricter.
    assert checked >= len(_parameterized_generators()), checked


# Slot order is the template's definition -- the k-th run is input k -- so
# what is checked is that every run fits its setter, one run per input.
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
    """The input indices in the order ``gen`` emits them, or None."""

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover every arity
    return _embedded_inputs(gen, template, len(table).bit_length() - 1)


@pytest.mark.slow  # builds every generator over several tables
def test_slots_run_in_name_order() -> None:
    """Every template's runs fit its setters, one run per input, in order.

    The k-th run *is* input k, so order cannot be wrong; what can is a run
    of the wrong width, a stray character or a run left over, which the
    reader refuses, and a load restructured that way is worth a failure
    rather than a shrug.

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
    """The template as the drawing the reorder bar compares.

    Every input is a run of the same character, so a mere relabelling of
    inputs already leaves the text unchanged: the drawing is the template.
    """
    return template


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

    from esolangs.tools import parameterized
    from esolangs.tools.helpers import permute_truth_table

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
        from tests.tools.fills import _fill_bio

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
        from esolangs.tools import parameterized

        template = parameterized.bio(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bio(self.instantiate(template, bits), bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_bio
        from esolangs.tools.helpers import runs

        template = parameterized.bio("0110")
        # weight 2 then weight 1: eight then four characters of ``$``
        assert template.startswith("$$$$$$$$ $$$$ ")
        assert runs(template, "$", _setters_bio(template, 2)) == [(0, 8), (9, 13)]

    def test_each_input_is_stored_once(self) -> None:
        """The packing scheme embeds each input exactly once."""

        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_bio
        from esolangs.tools.helpers import runs

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.bio(table)
            assert len(runs(template, "$", _setters_bio(template, n))) == n

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero pads against the unread ``z``, so the program's length
        does not reveal the inputs."""
        from esolangs.tools.examples import _setters_bio
        from tests.tools.fills import _fill_bio

        for n in (1, 2, 3):
            template = _run_form(_setters_bio, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bio(template, zeros)) == len(
                    _fill_bio(template, ones)
                ), f"n={n} input {i}"

    def test_padding_never_touches_a_read_register(self) -> None:
        """``z`` is inert: the generator emits no command that reads it."""
        from esolangs.tools import parameterized

        for n in (1, 2, 3):
            template = parameterized.bio(format(0, f"0{2**n}b"))
            assert "z" not in template.lower()


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
        from tests.tools.fills import _fill_bitdeque

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
        from esolangs.tools import parameterized

        template = parameterized.bitdeque(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bitdeque(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bitdeque(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bitdeque(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits.

        Both routes: the tree's run is the eleven characters of ``PUSH
        INVERT``, the linear route's the width of its discard block.
        """
        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_bitdeque
        from esolangs.tools.helpers import runs

        template = parameterized.bitdeque("0110")
        assert "{X" not in template
        spans = runs(template, "$", _setters_bitdeque(template, 2))
        assert [end - start for start, end in spans] == [11, 11]

        n = 5
        template = parameterized.bitdeque("0" * 2**n)
        assert "{X" not in template
        setters = _setters_bitdeque(template, n)
        spans = runs(template, "$", setters)
        assert [end - start for start, end in spans] == [len(z) for z, _ in setters]

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a drain-and-push leaf with no branching."""
        from esolangs.tools import parameterized

        template = parameterized.bitdeque("0000")
        assert "POP" in template
        assert "GOTO" in template

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Only the trampoline itself repeats the widening end address."""
        from esolangs.tools import parameterized

        template = parameterized.bitdeque("01101001")
        assert template.startswith("GOTO 3 INVERT GOTO 4 GOTO ")
        assert template.count("GOTO 0") == 8

    def test_linear_discard_executes_wide_rows(self) -> None:
        """Head/tail discards leave sampled six-input answers."""
        from esolangs.tools import parameterized

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = parameterized.bitdeque(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_bitdeque(self.instantiate(template, bits)) == table[row]

    def test_linear_discard_growth(self) -> None:
        """Wide templates and their fills scale with table size."""
        from esolangs.tools import parameterized

        templates = []
        filled = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            template = parameterized.bitdeque(table)
            templates.append(len(template))
            filled.append(len(self.instantiate(template, [0] * n)))
        assert all(b <= 2 * a for a, b in pairwise(templates))
        assert all(b <= 2 * a for a, b in pairwise(filled))


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
        """Fill through the shipped filler, not a copy of it.

        ``Z`` resets absolutely, so the setter is the same at every
        position -- ``Z A`` for a one, ``Z Z`` for a zero, two commands
        either way -- which is what made a local copy look safe.  It is
        still a second spelling of a construction the generator counts
        positions against, and that is the shape that hung the suite when
        Minsky Swap's copy drifted.
        """
        from tests.tools.fills import _fill_ram0

        return _fill_ram0(tpl, bits)

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
        from esolangs.tools import parameterized

        template = parameterized.ram0(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_ram0(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.ram0(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_ram0(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_ram0
        from esolangs.tools.helpers import TEMPLATE_CHAR, runs

        template = parameterized.ram0("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, _setters_ram0(template, 2))) == 2

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a single leaf with no branching."""
        from esolangs.tools import parameterized

        template = parameterized.ram0("0000")
        assert template.count("C") == 1  # entry trampoline only
        assert "Z" in template

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Every leaf jumps to 2; only the trampoline names the end."""
        from esolangs.tools import parameterized

        template = parameterized.ram0("01101001")
        tokens = template.split()
        assert tokens[0] == "C"
        assert tokens.count("2") == 8

    def test_linear_lookup_executes_wide_rows(self) -> None:
        """The straight-line RAM table returns sampled six-input rows."""
        from esolangs.tools import parameterized

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = parameterized.ram0(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]

    def test_linear_lookup_growth(self) -> None:
        """Wide parity templates grow by at most the table-size ratio."""
        from esolangs.tools import parameterized

        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(parameterized.ram0(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))


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
        """Fill the template the way a caller does, not the way this file did.

        This used to carry its own copy of the setter -- the same blocks,
        padded to ``2**n``.  A copy of a construction is free to drift from
        it, and this one did: when the generator shortened each block to its
        own bit's weight, the copy went on emitting full-length ones, so the
        template's jump targets addressed commands that were no longer
        there.  The program did not fail, it ran off into a loop, and the
        suite hung rather than reporting anything.

        The shipped filler is the thing under test here anyway: what this
        class pins is the truth table the instantiated program computes, and
        that is checked below either way.
        """
        from tests.tools.fills import _fill_minsky_swap

        return _fill_minsky_swap(tpl, bits)

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
        from esolangs.tools import parameterized

        template = parameterized.minsky_swap(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minsky_swap(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.minsky_swap(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_minsky_swap(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits.

        The MSB's run is its weight (two), the LSB's the fixed four; the
        jump targets count those same widths.
        """
        from esolangs.tools import parameterized

        template = parameterized.minsky_swap("0110")
        assert "{X" not in template
        assert template.startswith("$$ $$$$ ~")

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
        from esolangs.tools import minsky_swap
        from esolangs.tools.examples import AND2
        from tests.tools.fills import _fill_minsky_swap

        program = _fill_minsky_swap(minsky_swap(AND2), list(bits))
        assert self.run_minsky_swap(program) == AND2[(bits[0] << 1) | bits[1]]

    def test_examples_fill_weights_the_non_lsb(self) -> None:
        """A non-LSB block is its own weight long, in ``+`` or in ``*``.

        Not padded to the table's length: equal width is required of a bit
        against *itself*, so that the program's length cannot report the bit,
        and block ``i`` owes block ``j`` nothing.  Padding them all to
        ``2**n`` ran ``(n-1) * 2**n`` commands to load ``n`` bits.

        The length stays even either way, which is what stops the register
        pointer drifting -- a one does no swapping at all and a zero an even
        number of swaps.  ``"+*+*"`` is the LSB's exception.
        """
        from esolangs.tools import minsky_swap
        from esolangs.tools.examples import AND2
        from tests.tools.fills import _fill_minsky_swap

        template = minsky_swap(AND2)
        # Weight 2 at the MSB of a two-input table, so two commands, and the
        # LSB's four -- six, where padding to the table gave eight.
        assert _fill_minsky_swap(template, [1, 1]).startswith("++ +*+*")
        assert _fill_minsky_swap(template, [0, 1]).startswith("** +*+*")
        assert "++**" not in _fill_minsky_swap(template, [1, 1])


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
        from tests.tools.fills import _fill_bfpda

        return _fill_bfpda(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is four characters whichever bit it carries."""
        from esolangs.tools.examples import _setters_bfpda
        from tests.tools.fills import _fill_bfpda

        for n in (1, 2, 3):
            template = _run_form(_setters_bfpda, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bfpda(template, zeros)) == len(
                    _fill_bfpda(template, ones)
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
        from esolangs.tools import parameterized

        template = parameterized.bfpda(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bfpda(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bfpda(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bfpda(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs.tools import parameterized

        template = parameterized.bfpda("0110")
        assert "{X" not in template
        assert template.startswith("<@$$$$<@$$$$")

    def test_program_structure(self) -> None:
        """Each input is embedded once (pre-loaded), not re-embedded per node."""

        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_bfpda
        from esolangs.tools.helpers import runs

        template = parameterized.bfpda("0110")
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert runs(template, "$", _setters_bfpda(template, 2)) == [(2, 6), (8, 12)]
        assert "{C0}" not in template  # the marker is a constant, not a complement
        assert "{C1}" not in template

    def test_leaf_print_is_balanced(self) -> None:
        """A leaf pops the remaining bits, prints the answer, and pops it."""
        from esolangs.tools import parameterized

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
        from tests.tools.fills import _fill_home_row

        return _fill_home_row(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
        from esolangs.tools.examples import _setters_home_row
        from tests.tools.fills import _fill_home_row

        for n in (1, 2, 3):
            template = _run_form(_setters_home_row, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_home_row(template, zeros)) == len(
                    _fill_home_row(template, ones)
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
        from esolangs.tools import parameterized

        template = parameterized.home_row(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_home_row(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_five_inputs_sample(self) -> None:
        """A sample of dense five-input tables, past the removed n <= 2 cap."""

        from esolangs.tools import parameterized

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
        """The template has input runs, not hardcoded bits."""
        from esolangs.tools import parameterized

        template = parameterized.home_row("0110")
        assert "{X" not in template
        # each packing line opens with its two-character run
        assert "$$lsffffaafl$$lsffffafl" in template

    def test_each_input_embedded_once(self) -> None:

        from esolangs.tools import parameterized
        from esolangs.tools.examples import _setters_home_row
        from esolangs.tools.helpers import runs

        template = parameterized.home_row("0110")
        # ``runs`` refuses a stray ``$``, so two spans is exactly two embeds
        assert len(runs(template, "$", _setters_home_row(template, 2))) == 2
        assert "{C0}" not in template
        assert "{C1}" not in template


@pytest.mark.slow  # 2.6s: every fill of every parameterized generator
def test_fills_embed_a_zero_and_a_one_at_equal_width() -> None:
    """No fill may spell a 0 shorter than a 1, or the length leaks the input.

    A program whose length depends on its inputs reveals them without being
    read: an earlier BIO embedding ran to 236/240/244/248 characters for the
    four ``n == 2`` instantiations, so ``len(program)`` alone recovered the
    bits.  Every ``_fill_*`` therefore pads the two sides to equal width, an
    invariant stated on :func:`~esolangs.tools.helpers.instantiate`
    and enforced here.

    The check is per-generator rather than global: fills legitimately differ
    from each other in width, but for one generator and one table every
    instantiation must come out the same length.
    """
    import itertools

    from esolangs.tools import examples as ex

    fills = [
        (name, getattr(ex, name))
        for name in dir(ex)
        if name.startswith("_fill_") and callable(getattr(ex, name))
    ]
    assert fills, "no _fill_* functions found"

    for name, fill in fills:
        gen_name = name.removeprefix("_fill_")
        gen = getattr(ex, gen_name, None) or getattr(
            importlib.import_module("esolangs.tools"), gen_name, None
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


class TestConstructorWorkBudget:
    """Two paths that lost their exerciser with the text generators.

    The constructor's work budget and its per-row fill resolution were
    reached by the exhaustive four-input sweep, which was a one-shot script
    rather than a suite entry.  Both are live code, so they are driven
    directly here.
    """

    def test_a_fill_token_resolves_to_the_row_own_bit(self) -> None:
        """A tuple token is an input fill: the row decides its character.

        ``_row_runs`` resolves it once per row rather than on every replay,
        so the bit it reads has to be the row's own -- a fill resolved
        against the wrong row spells the wrong program for that row alone,
        which no aggregate length check would catch.
        """
        from esolangs.tools.one_two_three_construct import (
            _ONE,
            _ZERO,
            _Row,
            _row_runs,
        )

        one = _Row((1,))
        zero = _Row((0,))
        assert _row_runs(one, [("x", 0)]) == [(_ONE, 1)]
        assert _row_runs(zero, [("x", 0)]) == [(_ZERO, 1)]

    def test_a_fill_coalesces_with_the_run_beside_it(self) -> None:
        """Adjacent equal characters become one run, fills included."""
        from esolangs.tools.one_two_three_construct import (
            _ONE,
            _Row,
            _row_runs,
        )

        row = _Row((1,))
        assert _row_runs(row, [_ONE * 2, ("x", 0)]) == [(_ONE, 3)]

    def test_painting_past_the_budget_is_refused(self) -> None:
        """``_paint_all`` prices its whole paint before writing any of it.

        The budget is what stops a construction running away; charging for
        the paint up front is what makes the refusal cheap rather than
        something noticed a million commands later.
        """
        from esolangs.tools.one_two_three_construct import (
            _Builder,
            _paint_all,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        row = _Row((0,))
        row.pos = 1
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = [row]
        # Two offsets, so the paint is priced over both before any is
        # written -- one would leave the second offset's cost uncounted.
        # One of them is exactly 1, which has no shrunk ``k - 1`` pair to
        # paint: the guard that skips it is the only thing keeping a pair
        # of empty strings out of the price.
        _work[0] = 1  # _paint_all is called outside construct() here
        with pytest.raises(_WorkExhaustedError):
            _paint_all(b, (1, 3))
