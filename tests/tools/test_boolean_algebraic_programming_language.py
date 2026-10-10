"""algebraic_programming_language generator tests."""

import itertools
import random

import pytest

import esolangs
from esolangs import generate
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import _Machine
from esolangs.tools.helpers import best_input_order
from tests.generator_support import assert_parity_at_most_doubles, verify_generated
from tests.tools.boolean_runners import (
    run_algebraic_programming_language,
)
from tests.tools.sample_tables import five_input_sample
from tests.witness_tables import witnesses


class TestAlgebraicProgrammingLanguage:
    """The folded-tree generator, whose whole program is one executed line."""

    @staticmethod
    def _run(program: str, n: int, combo: int) -> str:
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        return run_algebraic_programming_language(program, bits)

    def test_every_one_and_two_input_table(self) -> None:
        """All 4 one-input and 16 two-input tables build and compute."""
        for n in (1, 2):
            for table in ("".join(t) for t in itertools.product("01", repeat=2**n)):
                program = boolean.algebraic_programming_language(table)
                for combo in range(2**n):
                    got = self._run(program, n, combo)
                    assert got == table[combo] + "\n", f"{table} combo {combo}"

    @pytest.mark.medium
    def test_every_three_input_table(self) -> None:
        """All 256 three-input tables build and compute their function."""
        for table in witnesses(3):
            program = boolean.algebraic_programming_language(table)
            for combo in range(8):
                got = self._run(program, 3, combo)
                assert got == table[combo] + "\n", f"{table} combo {combo}"

    def test_the_constant_zero_table_still_reads_every_input(self) -> None:
        """A table with no minterms names each input so the reads still happen."""
        program = boolean.algebraic_programming_language("0000")
        for name in ("a", "b"):
            assert name in program
        for combo in range(4):
            assert self._run(program, 2, combo) == "0\n"

    def test_reads_are_in_ascending_name_order(self) -> None:
        """A variable is read when the line first names it."""
        program = boolean.algebraic_programming_language("01101001")
        line = program.splitlines()[-1]
        firsts = [min(line.index(n) for n in (v,)) for v in "abc"]
        assert firsts == sorted(firsts)

    def test_every_value_stays_zero_or_one(self) -> None:
        """The program prints a bit, not an arbitrary truth value."""
        program = boolean.algebraic_programming_language("0110")
        for combo in range(4):
            assert self._run(program, 2, combo).strip() in {"0", "1"}

    def test_the_complement_operator_is_the_wikis_own(self) -> None:
        """The header is the wiki's ``!x`` definition, verbatim."""
        program = boolean.algebraic_programming_language("0001")
        assert program.startswith("!x = {\nx & $0\n$1\n}\n")

    def test_a_one_entry_table_is_refused(self) -> None:
        """A nullary table is a constant, not a function of any input."""
        with pytest.raises(ValueError, match="a one-entry table is a constant"):
            boolean.algebraic_programming_language("0")

    def test_a_width_spreads_the_sum_over_definitions(self) -> None:
        """A narrower program is the same sum, named a piece at a time."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.algebraic_programming_language(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(
                len(row)
                for row in boolean.algebraic_programming_language(table, 1).splitlines()
            )
            for width in (1, 25, 40, 60, wide):
                narrow = boolean.algebraic_programming_language(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    got = self._run(narrow, n, combo)
                    assert got == table[combo] + "\n", (table, width, combo)

    def test_the_executed_line_still_names_every_input(self) -> None:
        """Naming a term moves it off the one line that reads."""
        table = "0110100110010110"
        narrow = boolean.algebraic_programming_language(table, 30)
        # the ``!x`` header is the first four lines and its body sits inside
        # braces; past it, a line without an ``=`` is one that runs, and
        # there must be exactly one however much was hoisted
        lines = narrow.splitlines()
        assert lines[:4] == ["!x={", "x&$0", "$1", "}"], lines[:4]
        executed = [line for line in lines[4:] if "=" not in line]
        assert len(executed) == 1, executed
        line = executed[0]
        assert line.startswith("(a&b&c&d&0)|"), line
        # and every input is still read exactly once, in order
        assert sorted({ch for ch in line if ch in "abcd"}) == ["a", "b", "c", "d"]
        for row, output in enumerate(table):
            assert self._run(narrow, 4, row) == output + "\n"

    def test_narrowing_below_the_floor_does_not_widen(self) -> None:
        """Asking for less than it can do returns its narrowest, not a worse one."""
        for table in ("11111111", "0110100110010110", "01111111"):
            widths = [
                max(
                    len(row)
                    for row in boolean.algebraic_programming_language(
                        table, w
                    ).splitlines()
                )
                for w in (1, 5, 10)
            ]
            assert widths == sorted(widths), (table, widths)

    def test_compact_narrow_tree_executes_every_small_table(self) -> None:
        """Operator definitions preserve binding and reduce the XOR floor to four."""
        program = boolean.algebraic_programming_language("0110", 1)
        assert max(map(len, program.splitlines())) == 4
        for n in range(1, 4):
            for table in witnesses(n):
                program = boolean.algebraic_programming_language(table, 1)
                for row, output in enumerate(table):
                    assert self._run(program, n, row) == output + "\n"

    def test_narrow_tree_keeps_asymmetric_large_input_bindings(self) -> None:
        """Hoisting a prefix would leave variables unbound inside definitions."""

        rng = random.Random(42)
        for n in range(4, 7):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            for width in (1, 18, 30):
                program = boolean.algebraic_programming_language(table, width)
                for row, output in enumerate(table):
                    assert self._run(program, n, row) == output + "\n"


class TestAlgebraicProgrammingLanguageShapes:
    """The structural corners of the decision tree, at four inputs."""

    @staticmethod
    def _check(table: str, n: int = 4) -> None:
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_algebraic_programming_language(program, bits)
            assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_the_all_zero_table(self) -> None:
        """No minterms at all: the constant-zero branch."""
        self._check("0" * 16)

    def test_the_all_one_table(self) -> None:
        """Every row set, so the sum carries all sixteen terms."""
        self._check("1" * 16)

    def test_a_single_minterm(self) -> None:
        """One term, which is the fewest a non-constant table can have."""
        self._check("0000000000000001")

    def test_four_input_parity(self) -> None:
        """Eight terms and no constant subtree anywhere -- nothing folds."""
        self._check("0110100110010110")

    def test_the_all_zero_table_still_reads_every_input(self) -> None:
        """The constant needs its reads: the contract wants ``n`` of them."""
        program = boolean.algebraic_programming_language("0" * 16)
        for name in "abcd":
            assert name in program

    def test_the_name_alphabet_is_codepoint_ascending(self) -> None:
        """``_order_key`` sorts literals by name to keep reads in order."""
        from esolangs.tools.algebraic_programming_language import _NAMES

        assert list(_NAMES) == sorted(_NAMES)
        assert len(set(_NAMES)) == len(_NAMES)

    def test_constant_arms_need_no_guard(self) -> None:
        """A node over a constant arm is one literal and one operator."""
        from esolangs.tools.algebraic_programming_language import _apl_tree_ordered

        tail = {
            "0110": "((!a & b) | (a & !b))",
            "0001": "(a & b)",
            "0111": "(a | b)",
            "1101": "(!a | b)",
        }
        for table, expression in tail.items():
            program = boolean.algebraic_programming_language(table)
            assert program.endswith(f"(a & b & 0) | {expression}")
            self._check(table, 2)
        total = sum(
            len(best_input_order(f"{value:08b}", _apl_tree_ordered))
            for value in range(256)
        )
        assert total == 16303

    def test_the_reduced_diagram_skips_idle_tests_and_complements(self) -> None:
        """The fixed-order reduced diagram stays within the retirement budget."""
        from esolangs.tools.algebraic_programming_language import _apl_tree_ordered

        assert boolean.algebraic_programming_language("00011110").endswith(
            "(a & b & c & 0) | ((!a & (b & c)) | (a & !(b & c)))"
        )
        assert boolean.algebraic_programming_language("0101010100110011").endswith(
            "(a & b & c & d & 0) | ((!a & d) | (a & c))"
        )
        three = [f"{value:08b}" for value in range(256)]
        for tables, before, after in (
            (three, 16303, 16527),
            (five_input_sample(), 42875, 35147),
        ):
            inline = [len(best_input_order(t, _apl_tree_ordered)) for t in tables]
            reduced = [len(boolean.algebraic_programming_language(t)) for t in tables]
            assert (sum(inline), sum(reduced)) == (before, after)
            previous = 16067 if len(tables) == 256 else 40684
            assert sum(reduced) * 100 < previous * 105
        for n in (4, 5, 6):
            for value in (0x6996, 0x1234ABCD5678EF01, 0xF0F0CCCC5A5A3C3C):
                table = format(value % 2**2**n, f"0{2**n}b")
                assert verify_generated("Algebraic Programming Language", table)


@pytest.mark.parametrize("width", [1, 7, 9, 17, 40, 80])
def test_apl_elementary_definitions_compute_every_small_table(width: int) -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            program = esolangs.generate(
                "Algebraic Programming Language", table, width=width
            )
            for row, expected in enumerate(table):
                bits = list(format(row, f"0{n}b"))
                assert (
                    run_algebraic_programming_language(program, bits) == expected + "\n"
                )


def test_apl_elementary_floor_and_corpus_size() -> None:
    assert (
        max(map(len, boolean.algebraic_programming_language("0110", 1).splitlines()))
        == 4
    )
    assert (
        sum(
            len(boolean.algebraic_programming_language(format(v, "08b"), 1))
            for v in range(256)
        )
        == 19968
    )


@pytest.mark.parametrize("width", [1, 9, 17, 40])
@pytest.mark.parametrize("as_string", [False, True])
def test_apl_elementary_public_tagged_and_plain_source(
    width: int, *, as_string: bool
) -> None:
    program = esolangs.generate("Algebraic Programming Language", "0110", width=width)
    if as_string:
        program = str(program)
    for bits, expected in (("00", "0"), ("01", "1"), ("10", "1"), ("11", "0")):
        stdin = "\n".join(bits) + "\n"
        assert (
            esolangs.run("Algebraic Programming Language", program, stdin=stdin)
            == expected + "\n"
        )


@pytest.mark.parametrize("width", [1, 40])
def test_apl_width_layout_drops_an_ignored_input(width: int) -> None:
    """A width layout tests only the essential inputs, yet still reads all."""
    lang = "Algebraic Programming Language"
    table = "0110" * 8  # inputs 0, 1 and 2 ignored
    program = esolangs.generate(lang, table, width=width)
    assert len(str(program)) < len(esolangs.generate(lang, "01101001" * 4, width=width))
    for combo in range(32):
        stdin = "\n".join(format(combo, "05b")) + "\n"
        assert esolangs.run(lang, program, stdin=stdin) == table[combo] + "\n"


# Below the five-column floor, at it, and above it -- less where a table
# builds the same program at two of those widths.
@pytest.mark.parametrize(
    ("table", "width"),
    [
        *[(table, width) for table in ("00", "0110") for width in (1, 5, 9)],
        ("0001", 1),
        ("0001", 9),
        ("10010110", 1),
    ],
)
def test_operator_binding_reads_every_input_once(table: str, width: int) -> None:
    n = len(table).bit_length() - 1
    program = generate("Algebraic Programming Language", table, width=width)
    assert max(map(len, program.splitlines())) <= max(width, 5)
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")))
        machine = _Machine(program, io)
        for _ in range(200):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert io.reads == n
        assert io.getvalue() == expected + "\n"


def test_xor_arithmetic_family_reaches_four_columns() -> None:
    import esolangs
    from esolangs.tools.algebraic_programming_language import (
        algebraic_programming_language,
    )

    program = generate("Algebraic Programming Language", "0110", width=1)
    assert max(map(len, program.splitlines())) == 4
    assert len(program) == 49
    for row, expected in enumerate("0110"):
        stdin = "\n".join(format(row, "02b"))
        for source in (program, str(program)):
            assert (
                esolangs.run("Algebraic Programming Language", source, stdin=stdin)
                == expected + "\n"
            )
    assert algebraic_programming_language("0110", 4) == program
    assert max(map(len, algebraic_programming_language("0110", 5).splitlines())) == 5


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.algebraic_programming_language, (7, 8), 31)


@pytest.mark.medium
def test_default_reuses_emitted_frames() -> None:
    from esolangs.tools.algebraic_programming_language import _apl_reduced_ordered
    from scripts.screens.canonical import corpus, execute

    table = corpus(8)["tiled"]
    plain = _apl_reduced_ordered(table, tuple(range(8)))
    program = boolean.algebraic_programming_language(table)
    assert (len(plain), len(program)) == (1019, 428)
    assert (
        execute("Algebraic Programming Language", program, table, {}, all_rows=True)
        == 256
    )
