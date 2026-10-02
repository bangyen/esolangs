"""Executed tests for the five classic-language boolean generators.

FALSE, Thue and Unlambda read a line per bit and print the answer; FRACTRAN
and Bitwise Cyclic Tag have no I/O, so their bits are embedded -- FRACTRAN's
answer is the value its run stops on, BCT's is the bit its last deletion
consumed.  Every assertion here runs the generated program: the exhaustive
sweeps cover ``n <= 3``, which is 256 tables and 2,048 executed rows apiece.
"""

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run as run_fractran
from esolangs.interpreters.other.thue import run as run_thue
from esolangs.interpreters.other.unlambda import run as run_unlambda
from esolangs.interpreters.queue_based.bitwise_cyclic_tag import (
    _Machine as BctMachine,
)
from esolangs.interpreters.queue_based.bitwise_cyclic_tag import (
    run as run_bct,
)
from esolangs.interpreters.randomness import Seeded
from esolangs.interpreters.stack_based.false import run as run_false
from esolangs.tools.bitwise_cyclic_tag import PAIR as BCT_PAIR
from esolangs.tools.fractran import PAIR as FRACTRAN_PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.generator_support import evaluate_generated, verify_generated
from tests.tools.boolean_runners import five_input_sample

#: The line-reading three, each as ``(generator, interpreter run)``.
_READERS = {
    "false": (boolean.false, run_false),
    "thue": (boolean.thue, run_thue),
    "unlambda": (boolean.unlambda, run_unlambda),
}

_TABLES = [
    "01",  # identity
    "10",  # NOT
    "0001",  # AND
    "1110",  # NAND
    "0110",  # XOR
    "00000000",  # constant, which folds all the way down
    "01101001",  # parity, which folds nothing
    "10100101",
    "1000000000000000",  # AND4
]


def _bits(row: int, n: int) -> list[int]:
    return [(row >> (n - 1 - i)) & 1 for i in range(n)]


def _read_answer(name: str, table: str, row: int) -> tuple[str, int]:
    """Return what the generated program printed, and how many lines it read."""
    generate, run = _READERS[name]
    n = len(table).bit_length() - 1
    io = ScriptedIO(esolangs.encode_inputs(name, _bits(row, n)))
    run(generate(table), io)
    return io.getvalue(), io.reads


def _fractran_answer(table: str, row: int) -> str:
    """Return what the instantiated FRACTRAN program stopped on."""
    n = len(table).bit_length() - 1
    template = boolean.fractran(table)
    program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
    io = ScriptedIO("")
    run_fractran(program, io)
    return io.getvalue()


def _bct_program(table: str, row: int) -> str:
    """Return the instantiated BCT source for one row."""
    n = len(table).bit_length() - 1
    template = boolean.bitwise_cyclic_tag(table)
    return fill_runs(template, TEMPLATE_CHAR, [BCT_PAIR] * n, _bits(row, n))


def _bct_answer(table: str, row: int) -> str:
    """Return the bit the generated BCT program's last deletion consumed."""
    io = ScriptedIO("")
    run_bct(_bct_program(table, row), io)
    return io.getvalue()


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.parametrize("table", _TABLES)
def test_a_reader_answers_every_row(name: str, table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        printed, reads = _read_answer(name, table, row)
        assert printed == table[row], (name, table, row)
        assert reads == n, (name, table, row)


@pytest.mark.parametrize("table", _TABLES)
def test_fractran_answers_every_row(table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        answer = "2" if table[row] == "1" else "1"
        assert _fractran_answer(table, row) == answer, (table, row)


@pytest.mark.parametrize("name", sorted(_READERS))
@pytest.mark.slow
def test_a_reader_answers_every_table_to_three_inputs(name: str) -> None:
    """Exhaustive: every table at ``n <= 3``, every row of each."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                printed, reads = _read_answer(name, table, row)
                assert printed == table[row], (name, table, row)
                assert reads == n


@pytest.mark.slow
def test_fractran_answers_every_table_to_three_inputs() -> None:
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                answer = "2" if table[row] == "1" else "1"
                assert _fractran_answer(table, row) == answer, (table, row)


@pytest.mark.parametrize("name", sorted(_READERS))
def test_a_constant_table_still_reads_every_input(name: str) -> None:
    """Folding shortens the body; it must not drop the reads."""
    printed, reads = _read_answer(name, "00000000", 5)
    assert printed == "0"
    assert reads == 3


def test_fractran_spends_nothing_a_run_never_divides() -> None:
    """No ``p^1``, no clear a block's path spends, no phase on the parity.

    A block's path consumes every input and the offset, so the ``1/p``
    clears are for a folded leaf alone; and the parity fractions come after
    every phase prime's own exit, so they need no guard.  The 256
    three-input tables went from 50,700 characters to 41,010.  Five inputs,
    since a smaller table ships as the plain tree.
    """
    from esolangs.tools.fractran import _packed

    parity = str(boolean.fractran("0110100110010110" * 2))
    assert "^1 " not in parity
    assert "^1*" not in parity
    assert parity.endswith(" 1/3^2 2/3")  # no leaf folds, so nothing to clear
    tables = [format(i, "08b") for i in range(256)]
    assert sum(len(_packed(t, 3)) for t in tables) == 41_010


def _fractran_steps(template: str, n: int) -> int:
    """Return the steps every row of ``template`` runs to its halt, summed."""
    from esolangs.interpreters.other.fractran import _Machine

    steps = 0
    for row in range(2**n):
        program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
        machine = _Machine(program, ScriptedIO(""))
        while not machine.halted:
            machine.step()
            steps += 1
    return steps


@pytest.mark.medium
def test_fractran_ships_the_plain_tree_where_the_decoder_costs_more() -> None:
    """Small trees beat packed blocks in source size and executed steps."""
    from esolangs.tools.fractran import _packed, _plain

    tables = [format(i, "08b") for i in range(256)]
    size = steps = old_size = old_steps = 0
    for table in tables:
        template, packed = boolean.fractran(table), _packed(table, 3)
        assert template == _plain(table, 3), table
        cost, old_cost = _fractran_steps(template, 3), _fractran_steps(packed, 3)
        assert len(template) <= len(packed), table
        assert cost <= old_cost, table
        size, steps = size + len(template), steps + cost
        old_size, old_steps = old_size + len(packed), old_steps + old_cost
    assert (old_size, size) == (41_010, 27_842)
    assert (old_steps, steps) == (34_314, 9_592)


def test_folding_shortens_a_constant_table() -> None:
    """The three tree generators collapse a table whose rows agree."""
    for name in ("false", "unlambda"):
        generate, _run = _READERS[name]
        assert len(generate("00000000")) < len(generate("01101001")), name
    assert len(boolean.fractran("00000000")) < len(boolean.fractran("01101001"))


def test_false_tests_the_low_bit_and_prints_a_constant_pair() -> None:
    """``1&`` is the bit, and a node over two constant halves is a literal.

    ``'0`` and ``'1`` differ in their low bit and ``?`` takes any nonzero
    flag, so ``$1=`` is not needed; halves ``0``/``1`` print the bit itself
    and ``1``/``0`` its ``'0=_`` complement.  Over every three-input table
    the program falls from 22,170 characters to 12,034.
    """
    from tests.tools.plain_oracles import false_plain as _plain

    assert boolean.false("0110") == "^1&$[^'0=_.]?0=[^1&.]?"
    assert boolean.false("0001") == "^1&$[^1&.]?0=[^%0.]?"
    total = sum(len(_plain(f"{value:08b}", 3)) for value in range(256))
    assert total == 12034


def test_false_stores_repeated_halves_and_skips_equal_ones() -> None:
    """The reduced diagram cuts both totals and lengthens no table.

    A repeated half is stored once, ``[text]x:``, and fetched ``x;``; a node
    whose halves agree is ``^%`` and the half.  12,034 characters over the
    256 three-input tables fall to 10,634 (11.6%), and 45,372 over the
    seeded five-input sample to 35,721 (21.3%).
    """
    from tests.tools.plain_oracles import false_plain as _plain

    three = [format(value, "08b") for value in range(256)]
    assert boolean.false("01101001") == (
        "[^'0=_.]a:^1&$[^1&$[^1&.]?0=a;?]?0=[^1&$a;?0=[^1&.]?]?"
    )
    assert boolean.false("0101010100110011") == "^1&$[^%^1&^%.]?0=[^%^%^1&.]?"
    for tables, arity, before, after in (
        (three, 3, 12034, 10634),
        (five_input_sample(), 5, 45372, 35721),
    ):
        plain = [len(_plain(table, arity)) for table in tables]
        shared = [len(boolean.false(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("FALSE", table), table


@pytest.mark.medium
def test_false_runs_out_of_variables_and_writes_the_rest_inline() -> None:
    """Past 26 repeated halves the rest stay written out, and still run."""
    import random

    table = format(random.Random(0).getrandbits(512), "0512b")
    program = boolean.false(table)
    assert all(f"]{name}:" in program for name in "abcdefghijklmnopqrstuvwxyz")
    assert verify_generated("FALSE", table)


@pytest.mark.medium  # both builds of 456 tables: 0.95s alone
def test_unlambda_binds_repeated_subtrees_and_skips_equal_halves() -> None:
    """Share-taking nodes cut both totals and lengthen no table.

    A node returns ``s`` over its selected promises, so a repeated subtree
    bound once as ```` `N`dX ```` is ``i`` wherever it recurs below, and a
    node whose halves agree reads and runs the half.  41,074 characters over
    the 256 three-input tables fall to 32,522 (20.8%), and 144,722 over the
    seeded five-input sample to 100,963 (30.2%).
    """
    from tests.tools.plain_oracles import unlambda_plain as _plain

    three = [format(value, "08b") for value in range(256)]
    assert boolean.unlambda("01101001") == (
        "``@`d`k``s``?0i`d`@`d`k``s``?0ii``?1i`d`@`d`k``s``?0i`d`.1v``?1i`d`.0v"
        "``?1i`d`@`d`k``s``?1ii``?0i`d`@`d`k``s``?0i`d`.1v``?1i`d`.0v"
        "`d`@`d`k``s``?0i`d`.0v``?1i`d`.1v"
    )
    for tables, before, after in (
        (three, 41074, 32522),
        (five_input_sample(), 144722, 100963),
    ):
        plain = [len(_plain(table)) for table in tables]
        shared = [len(boolean.unlambda(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for table in five_input_sample()[::10]:
        for row in range(32):
            assert _read_answer("unlambda", table, row) == (table[row], 5)
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("Unlambda", table), table


def test_thue_spells_the_table_once_and_its_rules_are_fixed() -> None:
    """Its emission is the table plus a constant: ``T + 187`` characters.

    ``T + 199`` before the line read became the marker itself: the rules
    ``0::=P`` and ``1::=Q`` only renamed it, so every three-input table
    sheds twelve characters, 52,992 to 49,920 over all 256.
    """
    sizes = [len(boolean.thue("01" * (2 ** (n - 1)))) for n in (1, 2, 3, 4)]
    assert sizes == [2**n + 187 for n in (1, 2, 3, 4)]
    total = sum(len(boolean.thue(f"{value:08b}")) for value in range(256))
    assert total == 49920


@pytest.mark.parametrize("table", _TABLES)
def test_thue_never_leaves_the_draw_a_choice(table: str) -> None:
    """Every state a generated program reaches offers exactly one rewrite.

    Thue picks the rewrite at random, by spec, and the interpreter draws.
    What makes these programs reproducible anyway is this invariant, so it is
    asserted by running them rather than argued in a docstring: one applicable
    rule at one position, in every state, on every row.
    """
    from esolangs.interpreters.other.thue import _Machine, _matches

    n = len(table).bit_length() - 1
    program = boolean.thue(table)
    for row in range(2**n):
        stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
        machine = _Machine(program, ScriptedIO(stdin), Seeded(row))
        while not machine.halted:
            found = _matches(machine.state, machine.rules)
            assert len(found) == 1, (table, row, machine.state[:60], found)
            machine.step()


@pytest.mark.parametrize("table", _TABLES)
def test_thue_answers_the_same_under_every_draw(table: str) -> None:
    """Three seeds and the unseeded ``secrets`` draw agree, row by row."""
    n = len(table).bit_length() - 1
    program = boolean.thue(table)
    for row in range(2**n):
        stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
        answers = set()
        for rng in (Seeded(0), Seeded(1), Seeded(9), None):
            io = ScriptedIO(stdin)
            run_thue(program, io, rng)
            answers.add(io.getvalue())
        assert answers == {table[row]}, (table, row, answers)


def test_the_emissions_grow_by_a_line() -> None:
    """Successive differences at a fixed parity quadruple, exactly."""
    from tests.tools.plain_oracles import false_plain as _plain
    from tests.tools.plain_oracles import unlambda_plain as _plain_unlambda

    # FALSE's and Unlambda's shipped builds fold and share this table's
    # subtrees, so their plain trees are the ones measured.
    trees = (lambda table: _plain(table, len(table).bit_length() - 1),)
    for generate in (*trees, boolean.thue, _plain_unlambda):
        sizes = [len(generate("01" * (2 ** (n - 1)))) for n in (4, 6, 8)]
        assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) == 4.0


def test_fractran_runs_inside_the_block_it_reads() -> None:
    """A run is bounded by one block, never by the table.

    The tree spends a step a level and the decoder traverses a single block's
    exponent, so a run costs ``O(2**w)`` for a block of ``w`` entries -- and
    ``w = Theta(n)``, which makes the step count polylogarithmic in ``T``.
    That is what the packed text buys its characters with, and why
    ``_plan`` holds the width near ``n / 3``: this ceiling is the thing that
    would grow if it stopped.
    """
    from esolangs.interpreters.other.fractran import _Machine
    from esolangs.tools.fractran import _plan

    for n in range(2, 8):
        table = "".join(str((row * row + 1) % 2) for row in range(2**n))
        v, wide = _plan(n)
        widest = 1 << (v + 1 if wide else v)
        ceiling = 4 * (1 << widest) + 4 * n
        template = boolean.fractran(table)
        for row in range(2**n):
            program = fill_runs(
                template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n)
            )
            machine = _Machine(program, ScriptedIO(""))
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert steps <= ceiling, (n, row, steps, ceiling)


def test_bitwise_cyclic_tag_answers_every_row() -> None:
    for table in _TABLES:
        n = len(table).bit_length() - 1
        for row in range(2**n):
            assert _bct_answer(table, row) == table[row], (table, row)


@pytest.mark.slow
def test_bitwise_cyclic_tag_answers_every_table_to_three_inputs() -> None:
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                assert _bct_answer(table, row) == table[row], (table, row)


def test_bitwise_cyclic_tag_spells_the_table_at_a_fixed_rate() -> None:
    """Size is exactly ``8T + 2n + 1``, not merely ``O(T)``.

    Four bits of program per row for the table, four more per row for the
    walk that addresses it, and the data-string's ``n`` inputs, sentinel and
    separator.  Exact rather than bounded because the construction has no
    table-dependent choices at all: a folded table emits the same length as
    parity does, which is the trade for having no branch to fold into.
    """
    for n in (1, 2, 3, 4, 8):
        rows = 2**n
        sizes = {
            len(boolean.bitwise_cyclic_tag(table))
            for table in ("0" * rows, "1" * rows, ("01" * rows)[:rows])
        }
        assert sizes == {8 * rows + 2 * n + 1}, n


def test_bitwise_cyclic_tag_runs_in_a_fixed_number_of_steps() -> None:
    """The walk is linear in the table and ends on the row it addressed.

    ``5T + n`` at the last row and fewer below it, since the walk stops as
    soon as it arrives: the step count *is* the address, which is the whole
    construction.  A regression that made the pointer traverse the table
    more than once would show here and nowhere else -- the answers would
    still be right.
    """
    for n in (1, 2, 3, 6):
        rows = 2**n
        table = ("01" * rows)[:rows]
        counts = []
        for row in range(rows):
            machine = BctMachine(_bct_program(table, row), ScriptedIO(""))
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            counts.append(steps)
        assert max(counts) == 5 * rows + n, (n, counts)
        assert counts == sorted(counts), (n, counts)
        assert counts[-1] - counts[0] == 3 * (rows - 1), (n, counts)


def test_bitwise_cyclic_tag_never_wraps_its_program() -> None:
    """The cyclic schedule is unused: the pointer only ever moves forward.

    That is what makes the emission loop-less.  The interpreter's wrap is
    real and covered by its own tests; this asserts the *generator* never
    needs it, which is the property a step-count bound rests on.
    """
    table = "01101001"
    for row in range(8):
        machine = BctMachine(_bct_program(table, row), ScriptedIO(""))
        previous = -1
        while not machine.halted:
            assert machine.head > previous, (row, machine.head, previous)
            previous = machine.head
            machine.step()


def test_bitwise_cyclic_tag_does_not_cascade_a_one() -> None:
    """A 1 answer must not run on into the rows below it.

    The readout appends the answer to the data-string, so the cell that
    produced it has to consume it too -- otherwise the next row's ``1x``
    reads it and a 1 walks down the table until it meets a 0, returning that
    instead.  Row 0 of ``1000`` is the case: a 1 with nothing but 0s after
    it, so a cascade would answer 0 and every other row would still pass.
    """
    assert _bct_answer("1000", 0) == "1"
    assert _bct_answer("1" + "0" * 15, 0) == "1"


@pytest.mark.medium
def test_thue_contracted_heads_keep_a_unique_rewrite() -> None:
    """Ready and waiting symbols leave exactly one rewrite before each read."""
    from esolangs.interpreters.other.thue import _Machine, _matches

    assert max(map(len, boolean.thue("0110", 1).splitlines())) == 7
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            program = boolean.thue(table, 1)
            for row, expected in enumerate(table):
                stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
                io = ScriptedIO(stdin)
                machine = _Machine(program, io, Seeded(row))
                while not machine.halted:
                    assert len(_matches(machine.state, machine.rules)) == 1
                    machine.step()
                assert io.getvalue() == expected


@pytest.mark.medium
def test_thue_fixed_width_chunk_names_expand_before_reading() -> None:
    """The marker alphabet excludes every table and control symbol."""
    from esolangs.interpreters.other.thue import _Machine, _matches

    for n in range(4, 7):
        table = "".join(
            str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n)
        )
        program = boolean.thue(table, 1)
        assert max(map(len, program.splitlines())) == 9
        for row, expected in enumerate(table):
            stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
            io = ScriptedIO(stdin)
            machine = _Machine(program, io, Seeded(row))
            while not machine.halted:
                assert len(_matches(machine.state, machine.rules)) == 1
                machine.step()
            assert io.getvalue() == expected


@pytest.mark.parametrize("width", [1, 4, 9, 40, 80])
def test_fractran_phase_parity_all_small_tables(width: int) -> None:

    for n in range(1, 4):
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            assert evaluate_generated("FRACTRAN", table, width=width) == table


@pytest.mark.parametrize("width", [1, 4, 5, 8, 9, 80])
@pytest.mark.parametrize("as_string", [False, True])
def test_fractran_phase_parity_public_uniform_setters(
    width: int, *, as_string: bool
) -> None:
    from esolangs.tools.fractran import fractran_setters

    template = esolangs.generate("FRACTRAN", "0110", width)
    if as_string:
        template = str(template)
    pairs = fractran_setters(template, 2)
    assert len(set(pairs)) == 1
    for row, expected in enumerate("0110"):
        program = esolangs.instantiate(
            "FRACTRAN", template, [row // 2, row % 2], truth_table="0110"
        )
        assert (
            esolangs.read_answer("FRACTRAN", esolangs.run("FRACTRAN", program))
            == expected
        )
        if width < 9:
            assert max(map(len, program.splitlines())) <= max(width, 4)
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("FRACTRAN", template, [0, 1], truth_table="0001")


def test_fractran_phase_parity_exact_resolver_and_size() -> None:
    from esolangs.tools.fractran import fractran, fractran_setters

    template = fractran("0110", 1)
    assert len(template) == 14
    assert max(map(len, template.splitlines())) == 3
    assert fractran_setters(template, 2) == (("1", "2"),) * 2
    legacy = fractran("0110", 4)
    assert fractran_setters(legacy, 2) == (("1", "5"),) * 2
    assert fractran_setters(legacy.replace("1/25", "1/5"), 2) == (("0", "1"),) * 2


@pytest.mark.parametrize("n", [4, 5, 6])
def test_fractran_phase_parity_retains_larger_layout_execution(n: int) -> None:

    table = "".join(str(row.bit_count() % 2) for row in range(2**n))
    for width in [1, 4, 80]:
        program = esolangs.generate("FRACTRAN", table, width)
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            bits = list(map(int, format(row, f"0{n}b")))
            filled = esolangs.instantiate("FRACTRAN", program, bits)
            assert (
                esolangs.read_answer("FRACTRAN", esolangs.run("FRACTRAN", filled))
                == table[row]
            )
