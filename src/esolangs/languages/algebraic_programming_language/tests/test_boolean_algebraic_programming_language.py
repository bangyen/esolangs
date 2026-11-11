"""algebraic_programming_language generator tests."""

import itertools
import random
import re
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run as execute_program
from esolangs.languages.algebraic_programming_language import generator as boolean
from esolangs.languages.algebraic_programming_language.generator import (
    _NAMES,
    _apl_reduced_ordered,
    _apl_tree_ordered,
    algebraic_programming_language,
)
from esolangs.languages.algebraic_programming_language.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.generators.boolean_runners import _runner
from tests.generators.sample_tables import five_input_sample
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    assert_parity_at_most_doubles,
    assert_saved_rows,
    constant_programs,
    verify_generated,
)
from tests.support.screen_support import corpus, execute
from tests.support.witness_tables import witnesses

_run_apl = _runner("algebraic_programming_language", newline=True)


class TestAlgebraicProgrammingLanguage:
    """The folded-tree generator, whose whole program is one executed line."""

    @staticmethod
    def _run(program: str, n: int, combo: int) -> str:
        return _run_apl(program, list(f"{combo:0{n}b}"))

    def test_every_one_and_two_input_table(self) -> None:
        """All 4 one-input and 16 two-input tables build and compute."""
        assert_analysis_complement(
            "Algebraic Programming Language", "decision.complemented_diagram"
        )
        assert_analysis_complement("Algebraic Programming Language", "read_at", width=1)
        assert {"_Key", "_Ref", "subtree_ids"}.isdisjoint(vars(boolean))
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
        _check_constants()
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
        _check_arithmetic_twins()
        program = boolean.algebraic_programming_language("0110")
        for combo in range(4):
            assert self._run(program, 2, combo).strip() in {"0", "1"}

    def test_the_complement_operator_is_the_wikis_own(self) -> None:
        """The header is the wiki's ``!x`` definition, spaces aside."""
        program = boolean.algebraic_programming_language("1110")
        assert program.startswith("!x={\nx&$0\n$1\n}\n")

    def test_a_one_entry_table_is_refused(self) -> None:
        """A nullary table is a constant, not a function of any input."""
        with pytest.raises(ValueError, match="a one-entry table is a constant"):
            boolean.algebraic_programming_language("0")

    def test_no_function_definition_omits_its_parentheses(self) -> None:
        """The wiki defines ``F() = ...``; the bare ``A=`` form is our extension."""
        rng = random.Random(0)
        tables = [t for n in (1, 2, 3) for t in witnesses(n)]
        for n in range(4, 9):
            tables += ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(5)]
        for table in tables:
            for width in (None, 1, 30):
                program = boolean.algebraic_programming_language(table, width)
                for line in program.splitlines():
                    assert not re.match(r"[A-Z]+=", line), (table, width, line)

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
            got = _run_apl(program, bits)
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
        assert list(_NAMES) == sorted(_NAMES)
        assert len(set(_NAMES)) == len(_NAMES)

    def test_constant_arms_need_no_guard(self) -> None:
        """A node over a constant arm is one literal and one operator."""
        tail = {
            "0110": "(a+b)%2",
            "0001": "a&b",
            "0111": "a|b",
            "1101": "!a|b",
        }
        for table, expression in tail.items():
            program = boolean.algebraic_programming_language(table)
            assert program.endswith(f"a&b&0|{expression}")
            self._check(table, 2)
        total = sum(
            len(_apl_tree_ordered(f"{value:08b}", (0, 1, 2))) for value in range(256)
        )
        assert total == 18201

    def test_the_reduced_diagram_skips_idle_tests_and_complements(self) -> None:
        """The fixed-order reduced diagram stays within the retirement budget."""
        assert boolean.algebraic_programming_language("00011110").endswith(
            "a&b&c&0|(a+(b&c))%2"
        )
        assert boolean.algebraic_programming_language("0101010100110011").endswith(
            "a&b&c&d&0|!a&d|a&c"
        )
        three = [f"{value:08b}" for value in range(256)]
        for tables, before, after in (
            (three, 18201, 8592),
            (five_input_sample(), 47399, 20863),
        ):
            inline = [
                len(_apl_tree_ordered(t, tuple(range(len(t).bit_length() - 1))))
                for t in tables
            ]
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
            ).source
            for row, expected in enumerate(table):
                bits = list(format(row, f"0{n}b"))
                assert _run_apl(program, bits) == expected + "\n"


def test_apl_elementary_floor_and_corpus_size() -> None:
    language = esolangs.Language("Algebraic Programming Language")
    for witness in construction_boundaries(language.name)[
        "short_operator_arity_cutoff"
    ]:
        table = witness.table()
        with patch.object(
            boolean, "_apl_short_operators", wraps=boolean._apl_short_operators
        ) as operators:
            artifact = language.generate(table, width=1)
        assert operators.call_count == int(witness.arity == 3)
        assert_saved_rows(language, artifact, table, range(len(table)))

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
@pytest.mark.parametrize("as_source", [False, True])
def test_apl_elementary_public_artifact_and_source(
    width: int, *, as_source: bool
) -> None:
    program = esolangs.generate("Algebraic Programming Language", "0110", width=width)
    if as_source:
        program = program.source
    for bits, expected in (("00", "0"), ("01", "1"), ("10", "1"), ("11", "0")):
        stdin = "\n".join(bits) + "\n"
        assert (
            execute_program(
                "Algebraic Programming Language", program, stdin=stdin
            ).output
            == expected + "\n"
        )


@pytest.mark.parametrize("width", [1, 40])
def test_apl_width_layout_drops_an_ignored_input(width: int) -> None:
    """A width layout tests only the essential inputs, yet still reads all."""
    lang = "Algebraic Programming Language"
    table = "0110" * 8  # inputs 0, 1 and 2 ignored
    program = esolangs.generate(lang, table, width=width).source
    assert len(str(program)) < len(
        esolangs.generate(lang, "01101001" * 4, width=width).source
    )
    for combo in range(32):
        stdin = "\n".join(format(combo, "05b")) + "\n"
        assert execute_program(lang, program, stdin=stdin).output == table[combo] + "\n"


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
    program = esolangs.generate(
        "Algebraic Programming Language", table, width=width
    ).source
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
    program = esolangs.generate("Algebraic Programming Language", "0110", width=1)
    assert max(map(len, program.source.splitlines())) == 4
    assert len(program.source) == 49
    for row, expected in enumerate("0110"):
        stdin = "\n".join(format(row, "02b"))
        for source in (program, program.source):
            assert (
                execute_program(
                    "Algebraic Programming Language", source, stdin=stdin
                ).output
                == expected + "\n"
            )
    assert algebraic_programming_language("0110", 4) == program.source
    assert max(map(len, algebraic_programming_language("0110", 5).splitlines())) == 5


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.algebraic_programming_language, (7, 8), 31)


@pytest.mark.medium
def test_default_reuses_emitted_frames() -> None:
    table = corpus(8)["tiled"]
    plain = _apl_reduced_ordered(table, tuple(range(8)))
    program = boolean.algebraic_programming_language(table)
    assert (len(plain), len(program)) == (1019, 341)
    assert (
        execute(
            "Algebraic Programming Language",
            esolangs.ProgramArtifact(program, "Algebraic Programming Language"),
            table,
            {},
            all_rows=True,
        )
        == 256
    )


def test_a_wide_table_keeps_its_one_line_tail_under_the_frame_floor() -> None:
    """Seven inputs raise the frame floor with n, so the short tail stays inline."""
    lang = "Algebraic Programming Language"
    table = "10" * 64  # NOT of the last input; the other six are ignored
    program = esolangs.generate(lang, table, width=1).source
    assert len(program) == 35
    for combo in (0, 1, 2, 127):
        stdin = "\n".join(format(combo, "07b")) + "\n"
        assert execute_program(lang, program, stdin=stdin).output == table[combo] + "\n"


def _check_constants() -> None:
    for n, bit, _options, program in constant_programs(
        "Algebraic Programming Language", range(1, 13)
    ):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(
                esolangs.encode_inputs(
                    "Algebraic Programming Language", [int(b) for b in row]
                )
                + "7\n",
                expected=n,
            )
            assert_constant_output(run, program, io, bit + "\n", n)
            assert io.input_num() == 7


def _check_arithmetic_twins() -> None:
    class ReadFirstIO(ScriptedIO):
        def print_str(self, text: str) -> None:
            assert self.position() == 2 * inputs - 1
            super().print_str(text)

    for inputs, used in ((2, (0, 1)), (4, (0, 3)), (6, (2, 4)), (8, (1, 7))):
        table = "".join(
            str(sum((row >> (inputs - 1 - bit)) & 1 for bit in used) % 2)
            for row in range(1 << inputs)
        )
        source = boolean.algebraic_programming_language(table)
        assert "%2" in source
        for row in (0, 1, (1 << inputs) - 1):
            bits = format(row, f"0{inputs}b")
            io = ReadFirstIO(" ".join(bits) + " Q")
            machine = _Machine(source, io)
            while not machine.halted:
                machine.step()
            assert io.getvalue() == table[row] + "\n"
            assert io.input_token() == "Q"
    mutant = boolean.algebraic_programming_language("0110").replace("%2", "%3")
    io = ScriptedIO("1 1")
    machine = _Machine(mutant, io)
    while not machine.halted:
        machine.step()
    assert io.getvalue() == "2\n"
