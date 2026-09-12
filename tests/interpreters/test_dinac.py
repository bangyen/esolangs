r"""Unit tests for the DINAC interpreter and its generator."""

from typing import ClassVar

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.dinac import _Machine, run
from esolangs.tools.boolean import dinac
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import SnapshotContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message

# The wiki's programs, byte for.
# both matter: ``OUT ' `` *is*.
# has one the parser must.
HELLO_WORLD = (
    "OUT 'H\nOUT 'e\nOUT 'l\nOUT 'l\nOUT 'o\nOUT ',\nOUT ' \n"
    "OUT 'W\nOUT 'o\nOUT 'r \nOUT 'l\nOUT 'd\nOUT '!\nOUT \\n"
)

TRUTH_MACHINE = "\n".join(
    [
        r"SET zeroOrOne:\0",
        "IN zeroOrOne",
        "IF zeroOrOne = '1",
        "    WHILE 01",
        "        OUT '1",
        "ELSE",
        "    OUT 00",
    ]
)

CAT = "\n".join([r"SET c:\0", "IN c", "WHILE c", "    IN c", "    OUT c"])

PLUS_OR_MINUS = "\n".join(
    [
        r"DEF/\0 aschar n:00",
        r"    SET res:\0",
        "    WHILE n ! 00",
        "        res . res+",
        "        n . n-",
        "    GIVE res",
        r"SET c:\0",
        "SET acc:00",
        "IN c",
        "WHILE 01",
        "    IF c = '+",
        "        acc . acc+",
        "        IN c",
        "    ELSE",
        "        IF c = '-",
        "            OUT aschar(acc)",
        "            acc . acc-",
        "            IN c",
        "        ELSE",
        "            IN c",
    ]
)

# The wiki's STDLIB add, the.
STDLIB_ADD = "\n".join(
    [
        "DEF/00 add a:00 b:00",
        "    WHILE b",
        "        a . a+",
        "        b . b-",
        "    GIVE a",
    ]
)


def _run(code: str, stdin: str = "") -> str:
    return run_program(run, code, stdin)


class TestWikiExamples:
    r"""The page's own programs, which are the ground truth for the parser."""

    def test_hello_world(self) -> None:
        r"""Both trailing-space lines survive: the literal one and the stray."""
        assert _run(HELLO_WORLD) == "Hello, World!\n"

    def test_truth_machine_zero_prints_the_two_hex_digits(self) -> None:
        r"""``OUT 00`` prints a wubyte's 2-char literal, so "00" not "0"."""
        assert _run(TRUTH_MACHINE, "0\n") == "00"

    def test_truth_machine_one_loops_forever(self) -> None:
        r"""A repeated state proves the hang, so no timeout is needed."""
        io = ScriptedIO("1\n")
        assert run_until_halt_or_cycle(_Machine(TRUTH_MACHINE, io)) is False
        assert set(io.getvalue()) == {"1"}

    def test_cat_drops_its_first_character(self) -> None:
        r"""The wiki's cat re-reads before printing, so ``H`` is never shown."""
        assert _run(CAT, "H\ni\n!\n") == "i!\0"

    def test_cat_terminates_only_because_eof_is_falsy(self) -> None:
        r"""EOF must be falsy or the wiki's cat could never stop."""
        assert _run(CAT, "a\n") == "\0"

    def test_cat_stops_on_a_blank_line(self) -> None:
        r"""A consequence of the blank-line convention, worth pinning."""
        assert _run(CAT, "a\n\nb\n") == "\0"

    def test_plus_or_minus_interpreter(self) -> None:
        r"""Two ``+`` then a ``-`` prints chr(2); the outer WHILE never ends."""
        io = ScriptedIO("+\n+\n-\n")
        assert run_until_halt_or_cycle(_Machine(PLUS_OR_MINUS, io)) is False
        assert io.getvalue() == "\x02"

    def test_stdlib_add(self) -> None:
        r"""The STDLIB subpage's ``add``, called and printed as hex."""
        assert _run(f"{STDLIB_ADD}\nOUT add(03,04)") == "07"


class TestLiterals:
    r"""The three datatypes' spellings, including the ones examples force."""

    def test_a_bare_escape_is_an_aschar(self) -> None:
        r"""``OUT \n`` and ``SET c:\0`` are unquoted in the wiki's examples."""
        assert _run(r"OUT \n") == "\n"
        assert _run(r"OUT \t") == "\t"

    def test_a_quoted_escape_is_the_same_aschar(self) -> None:
        r"""The prose's ``'`` + escape spelling agrees with the bare one."""
        assert _run(r"OUT '\n") == "\n"

    def test_a_quote_takes_a_delimiter_character_literally(self) -> None:
        r"""``'#`` is a character, not the start of a comment."""
        assert _run("OUT '#") == "#"
        assert _run("OUT '(") == "("
        assert _run("OUT '+") == "+"

    def test_a_wubyte_prints_as_two_hex_digits(self) -> None:
        assert _run("OUT FF") == "FF"
        assert _run("OUT 0A") == "0A"

    def test_a_comment_runs_to_end_of_line(self) -> None:
        assert _run("OUT 'a # this is ignored\nOUT 'b") == "ab"

    def test_a_lone_snuval_prints_as_a_dollar(self) -> None:
        assert _run("OUT $") == "$"


class TestOperators:
    r"""Arithmetic, comparison, and the NOT operator."""

    def test_successor_wraps_a_wubyte_at_256(self) -> None:
        assert _run("OUT FF+") == "00"

    def test_predecessor_wraps_a_wubyte_below_zero(self) -> None:
        assert _run("OUT 00-") == "FF"

    def test_an_aschar_wraps_at_128(self) -> None:
        r"""The spec's aschar modulus is 128, so ``\0-`` is chr(127)."""
        assert _run(r"OUT \0-") == chr(127)

    def test_equality_and_inequality(self) -> None:
        assert _run("OUT 01 = 01") == "01"
        assert _run("OUT 01 = 02") == "00"
        assert _run("OUT 01 ! 02") == "01"

    def test_not_stacks(self) -> None:
        r"""``~~b`` normalizes to 0/1, which is what STDLIB's ``and`` returns."""
        assert _run("OUT ~00") == "01"
        assert _run("OUT ~~05") == "01"

    def test_parentheses_group_a_comparison(self) -> None:
        r"""The wiki's ``~(a = b)`` is how inequality is spelled with NOT."""
        assert _run("OUT ~(01 = 01)") == "00"

    def test_different_types_are_never_equal(self) -> None:
        r"""A wubyte and an aschar are disjoint value sets, so ``=`` is false."""
        assert _run("OUT 41 = 'A") == "00"
        assert _run("OUT 41 ! 'A") == "01"


class TestVariables:
    r"""Declaration, assignment, and the strong typing the spec insists on."""

    def test_set_then_assign(self) -> None:
        assert _run("SET x:00\nx . x+\nOUT x") == "01"

    def test_assigning_across_types_halts(self) -> None:
        r"""A variable's type is fixed by its initial value."""
        with raises_message(HaltError, "'x' is wubyte, cannot take a aschar"):
            run("SET x:00\nx . 'a\nOUT x", ScriptedIO())

    def test_a_snuval_may_be_assigned_to_any_variable(self) -> None:
        r"""The spec: the snuval is assignable to a variable of either type."""
        assert _run("SET x:00\nx . $\nOUT x") == "$"

    def test_setting_a_variable_to_a_snuval_is_refused(self) -> None:
        r"""A variable needs a non-snuval initial value to have a type."""
        with raises_message(HaltError, "SET 'x' needs a typed initial value"):
            run("SET x:$", ScriptedIO())

    def test_redeclaring_a_name_halts(self) -> None:
        with raises_message(HaltError, "'x' is already declared"):
            run("SET x:00\nSET x:01", ScriptedIO())

    def test_an_undeclared_name_halts(self) -> None:
        with raises_message(HaltError, "undeclared name 'nope'"):
            run("OUT nope", ScriptedIO())

    def test_a_lowercase_hex_token_is_an_identifier_not_a_literal(self) -> None:
        r"""The wiki: a wubyte is case-*sensitive*, so ``ff`` is a name."""
        with raises_message(HaltError, "undeclared name 'ff'"):
            run("OUT ff", ScriptedIO())


class TestInput:
    r"""``IN``'s typed reads, the empty-line rule, and the EOF decision."""

    def test_an_aschar_read_takes_the_first_character(self) -> None:
        assert _run(r"SET c:\0" + "\nIN c\nOUT c", "xyz\n") == "x"

    def test_an_empty_line_reads_as_the_package_convention(self) -> None:
        r"""0, not the wiki's ``\\n``."""
        assert _run(r"SET c:\0" + "\nIN c\nOUT c", "\n") == "\0"

    def test_a_wubyte_reads_decimal(self) -> None:
        r"""The wiki: 1-3 char base-10 form, so "255" is FF."""
        assert _run("SET n:00\nIN n\nOUT n", "255\n") == "FF"
        assert _run("SET n:00\nIN n\nOUT n", "7\n") == "07"

    def test_an_out_of_range_or_invalid_wubyte_reads_as_zero(self) -> None:
        r"""The wiki: invalid, <0 or >255 all return 00."""
        assert _run("SET n:00\nIN n\nOUT n", "999\n") == "00"
        assert _run("SET n:00\nIN n\nOUT n", "abc\n") == "00"
        assert _run("SET n:00\nIN n\nOUT n", "\n") == "00"

    def test_reading_past_the_end_gives_the_falsy_sentinel(self) -> None:
        r"""Undefined by the wiki; ``\0``/``00`` is what makes the cat halt."""
        assert _run(r"SET c:\0" + "\nIN c\nOUT c", "") == "\0"
        assert _run("SET n:00\nIN n\nOUT n", "") == "00"

    def test_each_in_consumes_exactly_one_line(self) -> None:
        assert _run(r"SET c:\0" + "\nIN c\nOUT c\nIN c\nOUT c", "a\nb\n") == "ab"


class TestFunctions:
    r"""``DEF``/``GIVE``, parameters, and overloading by parameter type."""

    def test_a_function_returns_its_value(self) -> None:
        assert _run("DEF/00 add1 n:00\n    GIVE n+\nOUT add1(01)") == "02"

    def test_overloads_are_chosen_by_parameter_type(self) -> None:
        r"""The wiki's own example: one ``add1`` per type, both legal."""
        program = "\n".join(
            [
                "DEF/00 add1 n:00",
                "    GIVE n+",
                r"DEF/\0 add1 n:\0",
                "    GIVE n+",
                "OUT add1(01)",
                "OUT add1('a)",
            ]
        )
        assert _run(program) == "02b"

    def test_a_missing_overload_halts(self) -> None:
        r"""The wiki: calling ``add(10,20)`` with no 2-wubyte overload errors."""
        with raises_message(
            HaltError, "no overload of 'add' takes ['wubyte', 'wubyte']"
        ):
            run("DEF/00 add n:00\n    GIVE n+\nOUT add(10,20)", ScriptedIO())

    def test_a_snuval_function_need_not_return(self) -> None:
        r"""The wiki: a ``DEF/$`` function may return nothing at all."""
        assert _run("DEF/$ shout\n    OUT 'h\n    OUT 'i\nshout()") == "hi"

    def test_a_typed_function_that_never_gives_is_refused(self) -> None:
        r"""A body with no GIVE anywhere cannot honour its declared type."""
        with raises_message(ValueError, "function 'f' returns wubyte but never GIVEs"):
            run("DEF/00 f n:00\n    OUT n", ScriptedIO())

    def test_returning_the_wrong_type_halts(self) -> None:
        with raises_message(HaltError, "'f' declares wubyte but gave aschar"):
            run(r"DEF/00 f n:00" + "\n    GIVE 'a\nOUT f(01)", ScriptedIO())

    def test_a_call_may_appear_inside_a_condition(self) -> None:
        r"""``WHILE and(a,b)`` is the wiki's shape; calls nest in expressions."""
        program = "\n".join(
            [
                "DEF/00 and a:00 b:00",
                "    IF a",
                "        GIVE ~~b",
                "    ELSE",
                "        GIVE 00",
                "OUT and(01,01)",
                "OUT and(01,00)",
            ]
        )
        assert _run(program) == "0100"

    def test_runaway_recursion_grows_frames_without_crashing(self) -> None:
        r"""No depth cap: frames grow on the heap, never on Python's stack."""
        machine = _Machine("DEF/00 f n:00\n    GIVE f(n)\nOUT f(01)", ScriptedIO())
        for _ in range(4000):
            machine.step()
        # Far past Python's own.
        assert len(machine.frames) > 1000
        assert not machine.halted

    def test_a_loop_inside_a_function_body_is_provable(self) -> None:
        r"""The reason calls are framed rather than evaluated inline."""
        program = "\n".join(
            [
                "DEF/00 spin n:00",
                "    WHILE 01",
                "        OUT n",
                "    GIVE n",
                "OUT spin(01)",
            ]
        )
        io = ScriptedIO()
        assert run_until_halt_or_cycle(_Machine(program, io)) is False
        assert set(io.getvalue()) == {"0", "1"}


class TestMalformedPrograms:
    r"""Structural rejections, which are ``ValueError`` per the conventions."""

    def test_an_if_without_an_else_is_refused(self) -> None:
        r"""The wiki: IF and ELSE "always come in pairs"."""
        with raises_message(ValueError, "IF without its ELSE"):
            run("IF 01\n    OUT 'a", ScriptedIO())

    def test_an_else_without_an_if_is_refused(self) -> None:
        with raises_message(ValueError, "ELSE without a matching IF"):
            run("ELSE\n    OUT 'a", ScriptedIO())

    def test_an_indent_that_is_not_a_multiple_of_four_is_refused(self) -> None:
        r"""The wiki fixes indentation at N x 4 spaces."""
        with raises_message(ValueError, "indent of 3 spaces is not a multiple of 4"):
            run("WHILE 00\n   OUT 'a", ScriptedIO())

    def test_an_empty_body_is_refused(self) -> None:
        with raises_message(ValueError, "WHILE needs an indented body"):
            run("WHILE 00\nOUT 'a", ScriptedIO())

    def test_a_nested_def_is_refused(self) -> None:
        with raises_message(ValueError, "a DEF may not be nested"):
            run("DEF/$ f\n    DEF/$ g\n        OUT 'a", ScriptedIO())

    def test_an_unparsable_statement_is_refused(self) -> None:
        with raises_message(ValueError, "malformed statement 'BLAH'"):
            run("BLAH", ScriptedIO())

    def test_an_aschar_holds_exactly_one_character(self) -> None:
        r"""There is no string type, so ``'hi`` is not a literal."""
        with raises_message(ValueError, 'malformed value "\'hi"'):
            run("OUT 'hi", ScriptedIO())

    def test_the_empty_program_halts_with_no_output(self) -> None:
        assert _run("") == ""
        assert _run("\n\n# just a comment\n") == ""


class TestSpaceSpellings:
    def test_both_spellings_of_a_space_print_the_same_character(self) -> None:
        r"""``OUT '!-`` prints a space, as does the wiki's ``OUT '`` + space."""
        program = "OUT 'a\nOUT '!-\nOUT 'b"
        assert "\n".join(line.rstrip() for line in program.split("\n")) == program
        assert _run(program) == "a b"
        assert _run("OUT ' ") == " "


class TestBooleanGenerator:
    r"""Every table to three inputs, executed on every input combination."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_computes_its_function(self, n: int) -> None:
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            program = dinac(table)
            for row in range(2**n):
                bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
                stdin = "".join(f"{bit}\n" for bit in bits)
                assert _run(program, stdin) == table[row], (table, row)

    def test_a_constant_table_still_reads_every_input(self) -> None:
        r"""The reads are the interface; folding may drop tests, never reads."""
        for table in ("00000000", "01101001"):
            io = ScriptedIO("0\n" * 8)
            run(dinac(table), io)
            assert io.position() == 3, table

    def test_a_one_dependency_table_folds(self) -> None:
        r"""A subtree whose rows agree collapses to one ``OUT``."""
        assert len(dinac("11110000")) < len(dinac("01101001"))

    def test_a_one_entry_table_is_refused(self) -> None:
        with raises_message(
            ValueError,
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function",
        ):
            dinac("0")


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    r"""The shared VM-protocol shapes, with this language's own programs."""

    machine: ClassVar = staticmethod(_machine)
    stepping_program: ClassVar = "OUT 'a\nOUT 'b"
