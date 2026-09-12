r"""Unit tests for the Alight interpreter and its generator."""

from typing import ClassVar

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.alight import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.boolean.alight import alight
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.runner import run_program

# --- the wiki's three.
# .
# Written as explicit lists of.
# the interior columns survive.
# whitespace: the vertical.
# and the row that is blank in.
# space, not padding.

CAT_TURN = [
    "                              d",
    "                              n",
    "                              e",
    "begin;var c;inp c;turn c = eof;",
    "           t                  t",
    "           h                  u",
    "           g                  r",
    "           i                  n",
    "           r                   ",
    "                              r",
    "           n                  i",
    "           r                  g",
    "           u                  h",
    "           t                  t",
    "           ;thgir nrut;;;c tuo;",
]

CAT_SKIP = [
    "begin;var c;inp c;skip c = eof;turn right;end",
    "           t                             t",
    "           h                             u",
    "           g                             r",
    "           i                             n",
    "           r                              ",
    "                                         r",
    "           n                             i",
    "           r                             g",
    "           u                             h",
    "           t                             t",
    "           ;thgir nrut;;;;;;;;;;;;;;c tuo;",
]

REVERSED_CAT = [
    (
        "begin;var c;var l;set l [];inp c;;;;;;;;;;;;;;;;;;;skip c = eof;tu"
        "rn right;var x;set x len{l}-0.5;;;;;;;;;;;skip sign{x} > 0;end;tur"
        "n right;"
    ),
    (
        "                          t                                       "
        "        t                      t                                  "
        "       t"
    ),
    (
        "                          h                                       "
        "        u                      h                                  "
        "       u"
    ),
    (
        "                          g                                       "
        "        r                      g                                  "
        "       r"
    ),
    (
        "                          i                                       "
        "        n                      i                                  "
        "       n"
    ),
    (
        "                          r                                       "
        "                               r                                  "
        "        "
    ),
    (
        "                                                                  "
        "        r                                                         "
        "       r"
    ),
    (
        "                          n                                       "
        "        i                      n                                  "
        "       i"
    ),
    (
        "                          r                                       "
        "        g                      r                                  "
        "       g"
    ),
    (
        "                          u                                       "
        "        h                      u                                  "
        "       h"
    ),
    (
        "                          t                                       "
        "        t                      t                                  "
        "       t"
    ),
    (
        "                          ;thgir nrut;}c ,5.0-}l{nel ,l{ta;}1 ,l{n"
        "el l tes;                      ;thgir nrut;1-x x tes;c tuo;}x ,l{t"
        "a c tes;"
    ),
]


def _run(code: list[str], stdin: str = "") -> str:
    return run_program(run, code, stdin)


def _machine(code: list[str]) -> _Machine:
    return _Machine(code, ScriptedIO("a\nb\n"))


class TestWikiExamples:
    r"""The page's own programs, run against their documented behaviour."""

    @pytest.mark.parametrize("program", [CAT_TURN, CAT_SKIP], ids=["turn", "skip"])
    @pytest.mark.parametrize(
        ("stdin", "expected"),
        [("h\ni\n", "hi"), ("a\nb\nc\n", "abc"), ("", ""), ("x\n", "x")],
    )
    def test_cat_echoes_until_eof(
        self, program: list[str], stdin: str, expected: str
    ) -> None:
        r"""Both cats echo their input and stop at EOF."""
        assert _run(program, stdin) == expected

    @pytest.mark.parametrize(
        ("stdin", "expected"),
        [("h\ni\n", "ih"), ("a\nb\nc\n", "cba"), ("", ""), ("z\n", "z")],
    )
    def test_reversed_cat_reverses(self, stdin: str, expected: str) -> None:
        r"""The reversed cat collects its input and prints it backwards."""
        assert _run(REVERSED_CAT, stdin) == expected

    def test_cat_geometry_closes_the_loop(self) -> None:
        r"""The turn-cat's loop returns to ``inp``, which only one geometry."""
        assert _run(CAT_TURN, "a\nb\nc\nd\ne\n") == "abcde"


class TestExpressions:
    r"""The expression language, pinned where the examples do not reach."""

    def _value(self, expr: str, stdin: str = "") -> str:
        return _run([f"begin;var v;set v {expr};out v;end;"], stdin)

    def test_evaluation_is_left_to_right_without_precedence(self) -> None:
        r"""``2+3*10`` is ``(2+3)*10``, not ``2+(3*10)``."""
        assert self._value("2+3*10") == "2"
        assert self._value("1*2+3*10") == "2"

    def test_character_and_string_literals(self) -> None:
        r"""``'c`` is a character's code and ``"str"`` a list of them."""
        assert self._value("'A") == "A"
        assert _run(['begin;var v;set v at{"AB", 1.5};out v;end;']) == "B"

    def test_a_semicolon_inside_a_string_is_data(self) -> None:
        r"""The wiki says a string may contain ``;``, so it cannot end a."""
        assert _run(['begin;var v;set v at{";x", 0.5};out v;end;']) == ";"

    def test_list_index_out_of_range_reads_nil(self) -> None:
        r"""Two-argument ``at`` past the end is ``nil``, not an error."""
        program = 'begin;var v;set v at{"A", 9.5};skip v = nil;end;set v 65;out v;end;'
        assert _run([program]) == "A"

    def test_a_non_half_index_is_a_runtime_error(self) -> None:
        r"""Indices are ``0.5 + k``; a whole number is the language's own trap."""
        with pytest.raises(HaltError, match=r"0\.5"):
            run(['begin;var v;set v at{"AB", 1};out v;end;'], ScriptedIO())

    def test_len_in_both_arities(self) -> None:
        r"""One argument measures; two pad with ``nil``."""
        assert self._value('len{"AB"}+48') == "2"
        assert self._value('len{len{"AB", 3}}+48') == "5"

    def test_trunc_and_sign(self) -> None:
        assert self._value("trunc{50.7}") == "2"
        assert self._value("sign{0-5}+49") == "0"
        assert self._value("sign{7}+48") == "1"

    @pytest.mark.parametrize(
        ("expr", "expected"),
        [
            ("left&left", "left"),
            ("left&right", "right"),
            ("left|right", "left"),
            ("right|right", "right"),
            ("left^left", "right"),
            ("left^right", "left"),
            ("!right", "left"),
            ("!left", "right"),
        ],
    )
    def test_logic_operators(self, expr: str, expected: str) -> None:
        r"""``!``, ``&``, ``|`` and ``^`` over the two booleans."""
        program = (
            f"begin;var v;set v {expr};skip v = {expected};end;set v 65;out v;end;"
        )
        assert _run([program]) == "A"

    def test_comparison_across_types_is_false_not_an_error(self) -> None:
        r"""``c = eof`` has to be askable of a character, which needs this."""
        assert _run(["begin;var v;set v 65 = eof;skip v = right;out v;end;"]) == ""

    def test_division_by_zero_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            run(["begin;var v;set v 1/0;end;"], ScriptedIO())


class TestErrors:
    r"""Malformed programs against invalid operations: ValueError vs."""

    def test_a_program_without_begin_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no 'begin'"):
            run(["var c;end;"], ScriptedIO())

    def test_a_reversed_end_does_not_halt(self) -> None:
        r"""The wiki says meeting ``dne`` is not meeting ``end``."""
        with pytest.raises(ValueError, match="unknown command 'dne'"):
            run(["begin;;dne;"], ScriptedIO())
        # And the same word travelling.
        # test above is about the.
        assert _run(["begin;;end;"]) == ""

    def test_walking_off_the_grid_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="walked off the grid"):
            run(["begin;;;"], ScriptedIO())

    def test_an_unknown_command_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown command"):
            run(["begin;frobnicate x;end;"], ScriptedIO())

    def test_an_undeclared_variable_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="no such variable"):
            run(["begin;set q 1;end;"], ScriptedIO())

    def test_a_redeclared_variable_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="already exists"):
            run(["begin;var q;var q;end;"], ScriptedIO())

    def test_a_non_boolean_guard_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="guard is not a boolean"):
            run(["begin;var v;set v 1;turn v;end;"], ScriptedIO())

    def test_outputting_a_non_character_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="cannot output"):
            run(["begin;var v;out v;end;"], ScriptedIO())

    def test_a_reserved_word_is_not_a_variable_name(self) -> None:
        with pytest.raises(ValueError, match="bad variable name"):
            run(["begin;var end;end;"], ScriptedIO())


class TestFunctions:
    r"""``func`` definitions, their namespaces, and the Evil Hack."""

    def test_a_function_returns_its_value(self) -> None:
        assert (
            _run(["begin;var v;set v twice{24};out v;end;", "func twice{n};end n+n;"])
            == "0"
        )

    def test_a_function_namespace_is_its_own(self) -> None:
        r"""The callee's ``n`` does not disturb the caller's."""
        assert (
            _run(
                [
                    "begin;var n;set n 65;var v;set v pick{66};out n;out v;end;",
                    "func pick{n};end n;",
                ]
            )
            == "AB"
        )

    def test_an_unknown_function_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="no such function"):
            run(["begin;var v;set v nope{1};end;"], ScriptedIO())

    def test_wrong_argument_count_is_a_runtime_error(self) -> None:
        with pytest.raises(HaltError, match="takes 1 arguments"):
            run(
                ["begin;var v;set v one{1, 2};end;", "func one{a};end a;"], ScriptedIO()
            )

    @pytest.mark.parametrize(
        "program",
        [
            ["begin;var v;set v loop{1};end;", "func loop{a};end loop{a};"],
            ["begin;var v;set v f{1};end;", "func f{a};var b;set b f{a};end b;"],
        ],
        ids=["return-position", "body-position"],
    )
    def test_unbounded_recursion_grows_walkers_without_crashing(
        self, program: list[str]
    ) -> None:
        r"""No depth cap: walkers grow on the heap, not Python's stack."""
        machine = _machine(program)
        for _ in range(3000):
            machine.step()
        # Far past Python's own.
        assert len(machine.walkers) > 1000
        assert not machine.halted

    def test_an_effectful_at_beside_a_call_fires_exactly_once(self) -> None:
        r"""The constraint that shapes how a command is re-entered."""
        program = [
            'begin;var l;set l "A";var v;'
            "set v len{at{l, 0.5, at{l, 0.5}+1}}+f{0};"
            "var c;set c at{l, 0.5};out c;end;",
            "func f{a};end a;",
        ]
        # 'A' is 65: one increment.
        assert _run(program) == "B"

    def test_two_calls_beside_an_effectful_at_still_fire_it_once(self) -> None:
        r"""Two re-entries rather than one, so a per-entry bug is louder."""
        program = [
            'begin;var l;set l "A";var v;'
            "set v len{at{l, 0.5, at{l, 0.5}+1}}+f{0}+g{0};"
            "var c;set c at{l, 0.5};out c;end;",
            "func f{a};end a;",
            "func g{a};end a;",
        ]
        assert _run(program) == "B"

    def test_a_ring_inside_a_called_function_is_provable(self) -> None:
        r"""The reason calls are framed rather than run inline."""
        # The proven ring from.
        # continuation rows shift right.
        # header, which is column 5 for.
        # ``func r{}``, so the arms.
        program = [
            "begin;var v;set v r{};end;",
            "func r{};turn right;",
            *["   " + line for line in TestCycles.looping_program[1:]],
        ]
        assert run_until_halt_or_cycle(_machine(program)) is False


class TestGenerators:
    r"""Both generators, checked by running what they emit."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_boolean_computes_every_table_at_every_row(self, n: int) -> None:
        r"""Exhaustive: all ``2**2**n`` tables, each on all ``2**n`` rows."""
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            program = alight(table)
            for combo in range(2**n):
                bits = "".join(f"{(combo >> (n - 1 - i)) & 1}\n" for i in range(n))
                assert _run(program.splitlines(), bits) == table[combo], (
                    f"table {table} row {combo}"
                )

    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_boolean_computes_wider_tables(self, n: int) -> None:
        r"""Sampled at the arities too wide to enumerate, still on every row."""
        import random

        rng = random.Random(n)
        for _ in range(3):
            table = "".join(rng.choice("01") for _ in range(2**n))
            program = alight(table)
            for combo in range(2**n):
                bits = "".join(f"{(combo >> (n - 1 - i)) & 1}\n" for i in range(n))
                assert _run(program.splitlines(), bits) == table[combo], (
                    f"n={n} row {combo}"
                )

    def test_boolean_reads_n_inputs_whatever_the_table_says(self) -> None:
        r"""The reads are the interface, so a constant table still consumes."""
        counts = set()
        for table in ("00000000", "01101001", "11111111"):
            io = ScriptedIO("0\n" * 8)
            run(alight(table).splitlines(), io)
            counts.add(io.position())
        assert counts == {3}

    def test_boolean_length_does_not_leak_the_table(self) -> None:
        r"""Every table of one arity renders to the same length."""
        lengths = {len(alight(bin(v)[2:].zfill(8))) for v in range(256)}
        assert len(lengths) == 1

    def test_boolean_refuses_a_nullary_table(self) -> None:
        with pytest.raises(ValueError, match="at least one input"):
            alight("0")

    def test_numeric_literals_print_characters_that_are_alight_syntax(self) -> None:
        r"""``out`` on a numeric literal sidesteps Alight's own quoting."""
        program = "begin;var c;set c 39;out c;set c 34;out c;set c 59;out c;end;"
        assert _run(program.splitlines()) == "'\";"

    def test_registered_generator_runs_through_the_public_api(self) -> None:
        r"""The registry entry wires the generator and the interpreter."""
        assert esolangs.run("Alight", alight("01"), "1\n") == "1"


class TestEmptyProgram(EmptyProgramContract):
    run = staticmethod(lambda code: _run(code))
    empty_program: ClassVar[list[str]] = [""]
    empty_raises = "empty program"


class TestSnapshot(SnapshotContract):
    machine = staticmethod(_machine)
    stepping_program = CAT_TURN

    def test_snapshot_includes_the_input_cursor(self) -> None:
        r"""Two states differing only in consumed input must not compare equal."""
        machine = _Machine(CAT_TURN, ScriptedIO("a\na\na\n"))
        seen = set()
        for _ in range(40):
            if machine.halted:
                break
            seen.add(machine.snapshot())
            machine.step()
        positions = {snap[-1] for snap in seen}
        assert len(positions) > 1

    def test_a_banked_snapshot_survives_a_later_list_mutation(self) -> None:
        r"""Freezing a list variable is what makes a snapshot a value."""
        machine = _Machine(REVERSED_CAT, ScriptedIO("a\nb\nc\n"))
        banked = None
        for _ in range(400):
            if machine.halted:
                break
            if banked is None and any(
                isinstance(v, list) and v for v in machine.vars.values()
            ):
                banked = machine.snapshot()
                copy = machine.snapshot()
            machine.step()
        assert banked is not None, "the run never held a non-empty list"
        # The list grew and was written.
        # unfrozen snapshot would have.
        # to a freshly taken one.
        assert banked == copy
        assert banked != machine.snapshot()


class TestCycles(CycleContract):
    machine = staticmethod(_machine)
    halting_program: ClassVar[list[str]] = ["begin;;end;"]
    # Four ``turn right`` commands.
    # cell past the previous one's.
    # forever reading no input and.
    # repeats exactly -- a real.
    looping_program: ClassVar[list[str]] = [
        "begin;turn right;",
        "     t          t",
        "     h          u",
        "     g          r",
        "     i          n",
        "     r",
        "                r",
        "     n          i",
        "     r          g",
        "     u          h",
        "     t          t",
        "     ;thgir nrut;",
    ]


class TestEdgeCases:
    r"""The error and edge paths the wiki examples never reach."""

    @pytest.mark.parametrize(
        ("program", "message"),
        [
            # An unterminated string runs.
            ('begin;var v;set v "abc;', "unterminated string"),
            # A '{' with no matching '}'.
            ("begin;var v;set v len{v;", "expected"),
            # A trailing ' shields the.
            # the grid edge still escaping.
            ("begin;var v;set v '", "unterminated string"),
            # An operator with no.
            ("begin;var v;set v 1+;", "expression ends early"),
            # Nothing that can start an.
            ("begin;var v;set v @;", "cannot parse operand"),
            # A list whose elements are not.
            ("begin;var v;set v [1 2];", "expected"),
            # Text after a complete.
            ("begin;var v;set v 1 2;", "trailing text"),
            # A command that is neither a.
            ("begin;var v;v 1;", "unknown command"),
            # A non-empty command with no.
            ("begin;+;", "cannot parse command"),
        ],
    )
    def test_malformed_programs_raise_value_error(
        self, program: str, message: str
    ) -> None:
        r"""Every structural error is a ``ValueError``, not a ``HaltError``."""
        with pytest.raises(ValueError, match=message):
            run([program], ScriptedIO())

    @pytest.mark.parametrize(
        ("program", "message"),
        [
            # Two lists can only be.
            ('begin;var v;set v "ab"*"cd";end;', "two lists"),
            # A list and a number can only.
            ('begin;var v;set v "ab"-2;end;', "list and"),
            # A repeat count has to be a.
            ('begin;var v;set v "ab"*1.5;end;', "repeat count"),
            # Arithmetic on a special value.
            ("begin;var v;set v nil+1;end;", "cannot apply"),
            # A pad count that is not a.
            ('begin;var v;set v len{"ab", 1.5};end;', "pad count"),
            # trunc/sign of something that.
            ("begin;var v;set v trunc{nil};end;", "takes one number"),
            # A list builtin applied to a.
            ("begin;var v;set v len{1};end;", "takes a list"),
            # Three-argument at past the.
            ('begin;var v;set v at{"ab", 9.5, 65};end;', "past the end"),
            # A code point outside the.
            ("begin;var v;set v 0-1;out v;end;", "not a character code"),
            # A non-integral code point.
            ("begin;var v;set v 65.5;out v;end;", "not a character code"),
            # A non-numeric list index.
            ('begin;var v;set v at{"ab", nil};end;', "index is not a number"),
        ],
    )
    def test_invalid_operations_raise_halt_error(
        self, program: str, message: str
    ) -> None:
        r"""Every runtime error is a ``HaltError``, not a ``ValueError``."""
        with pytest.raises(HaltError, match=message):
            run([program], ScriptedIO())

    def test_list_concatenation_and_repetition(self) -> None:
        r"""``+`` joins two lists and ``*`` repeats one, in either spelling."""
        joined = 'begin;var v;set v at{"ab"+"cd", 2.5};out v;end;'
        assert _run([joined]) == "c"
        repeated = 'begin;var v;set v at{"ab"*2, 3.5};out v;end;'
        assert _run([repeated]) == "b"
        # A number on the left repeats.
        commuted = 'begin;var v;set v at{2*"ab", 3.5};out v;end;'
        assert _run([commuted]) == "b"

    def test_nested_lists_and_the_type_check_on_at(self) -> None:
        r"""A list of lists is legal; mixing a number into one is not."""
        nested = "begin;var v;set v at{at{[[65], [66]], 1.5}, 0.5};out v;end;"
        assert _run([nested]) == "B"
        with pytest.raises(HaltError, match="wrong type"):
            run(["begin;var v;set v at{[[65]], 0.5, 66};end;"], ScriptedIO())

    def test_wait_is_a_nop_but_still_evaluates(self) -> None:
        r"""The argument runs -- an error in it fires -- and nothing is waited."""
        assert _run(["begin;var v;set v 65;wait 0;out v;end;"]) == "A"
        with pytest.raises(HaltError, match="no such variable"):
            run(["begin;wait q;end;"], ScriptedIO())

    def test_an_empty_input_line_reads_as_zero(self) -> None:
        r"""A blank line is a real line with no character, so it reads 0."""
        program = "begin;var c;inp c;skip c = 0;end;set c 65;out c;end;"
        assert _run([program], "\n") == "A"

    def test_a_function_with_no_arguments_and_a_bare_end(self) -> None:
        r"""``func f{}`` takes nothing and a bare ``end`` returns ``nil``."""
        program = [
            "begin;var v;set v f{};skip v = nil;end;set v 65;out v;end;",
            "func f{};end;",
        ]
        assert _run(program) == "A"

    def test_a_runaway_walk_is_proven_rather_than_capped(self) -> None:
        r"""A ring that never halts is *proved* to hang, not stopped by a count."""
        assert run_until_halt_or_cycle(_machine(TestCycles.looping_program)) is False

    def test_a_string_may_contain_a_quote_via_the_escape(self) -> None:
        r"""``'`` shields the next cell, so a quote can sit inside a command."""
        assert _run(["begin;var v;set v '\";out v;end;"]) == '"'

    def test_comparisons_between_mismatched_types_are_false(self) -> None:
        r"""``<`` and ``>`` are false on anything but two numbers."""
        program = "begin;var v;set v nil < 1;skip v = right;end;set v 65;out v;end;"
        assert _run([program]) == "A"

    def test_a_program_may_be_handed_over_as_a_string(self) -> None:
        r"""``run`` accepts a joined program as well as a list of lines."""
        io = ScriptedIO("")
        run("begin;var c;set c 65;out c;end;", io)
        assert io.getvalue() == "A"


class TestFunctionDefinitionEdges:
    r"""The ``func`` header paths, and the last few error branches."""

    @pytest.mark.parametrize(
        "definition",
        [
            # A different function's name.
            "func other{a};end a;",
            # A header whose parameter is a.
            "func g{end};end 65;",
            # A header with a parameter.
            "func g{a;end a;",
            # A header with a stray token.
            "func g{a}x;end a;",
            # A parameter separated by.
            "func g{a b};end a;",
        ],
    )
    def test_a_header_that_does_not_match_is_not_the_function(
        self, definition: str
    ) -> None:
        r"""None of these define ``f``, so calling ``f`` is a runtime error."""
        with pytest.raises(HaltError, match="no such function"):
            run(["begin;var v;set v f{1};end;", definition], ScriptedIO())

    def test_a_two_parameter_function(self) -> None:
        r"""A comma-separated header binds both arguments."""
        program = [
            "begin;var v;set v add{60, 5};out v;end;",
            "func add{a, b};end a+b;",
        ]
        assert _run(program) == "A"

    def test_a_function_may_call_another_function(self) -> None:
        r"""Each call gets its own frame, so nesting composes."""
        program = [
            "begin;var v;set v outer{64};out v;end;",
            "func outer{n};end inner{n}+1;",
            "func inner{n};end n;",
        ]
        assert _run(program) == "A"

    def test_division_by_zero_and_ordinary_division(self) -> None:
        r"""The guard fires only on a zero divisor."""
        assert _run(["begin;var v;set v 130/2;out v;end;"]) == "A"
        with pytest.raises(HaltError, match="division by zero"):
            run(["begin;var v;set v 1/0;end;"], ScriptedIO())

    @pytest.mark.parametrize(
        ("program", "message"),
        [
            # ``len`` with three arguments.
            ('begin;var v;set v len{"ab", 1, 2};end;', "optionally a count"),
            # ``at`` with four.
            ('begin;var v;set v at{"ab", 0.5, 65, 1};end;', "optionally a value"),
        ],
    )
    def test_builtin_arity_errors(self, program: str, message: str) -> None:
        r"""A builtin called with the wrong number of arguments halts."""
        with pytest.raises(HaltError, match=message):
            run([program], ScriptedIO())

    @pytest.mark.parametrize(
        ("lines", "message"),
        [
            # Trailing text after a.
            (["begin;var v x;end;"], "trailing text after variable name"),
            # Trailing text after a turn's.
            (["begin;turn right x;end;"], "trailing text"),
            # Trailing text after an end.
            (
                ["begin;var v;set v f{1};end;", "func f{a};end a b;"],
                "trailing text after end value",
            ),
        ],
    )
    def test_trailing_text_is_malformed(self, lines: list[str], message: str) -> None:
        r"""A command with text left over after its expression is malformed."""
        with pytest.raises(ValueError, match=message):
            run(lines, ScriptedIO())

    def test_a_string_literal_may_run_off_the_grid(self) -> None:
        r"""An unclosed ``"`` inside a command reaches the edge and is refused."""
        with pytest.raises(ValueError, match="unterminated string literal"):
            run(['begin;var v;set v "ab'], ScriptedIO())

    def test_a_bare_call_with_trailing_text_is_malformed(self) -> None:
        r"""Only a call that consumes the whole command is a command."""
        with pytest.raises(ValueError, match="unknown command"):
            run(["begin;len{1} x;end;"], ScriptedIO())

    def test_a_function_body_may_run_commands_before_its_end(self) -> None:
        r"""The callee is a real walk, not just an expression."""
        program = [
            "begin;var v;set v f{1};out v;end;",
            "func f{a};var b;set b a+64;end b;",
        ]
        assert _run(program) == "A"

    def test_a_parameter_that_is_not_alphanumeric_is_not_a_header(self) -> None:
        r"""A malformed parameter list means the function is not defined."""
        with pytest.raises(HaltError, match="no such function"):
            run(
                ["begin;var v;set v f{1};end;", "func f{a-b};end a;"],
                ScriptedIO(),
            )

    def test_an_unterminated_string_inside_a_list_is_malformed(self) -> None:
        r"""An unclosed ``"`` swallows its own terminator and runs to the edge."""
        with pytest.raises(ValueError, match="unterminated string literal"):
            run(['begin;var v;set v [1, "a];'], ScriptedIO())

    def test_a_malformed_number_literal_is_refused(self) -> None:
        r"""Two decimal points is not a number."""
        from esolangs.interpreters.grid_based.alight import _parse_number, _Parser

        with pytest.raises(ValueError, match="bad number literal"):
            _parse_number(_Parser("1.2.3"))

    def test_an_empty_parameter_name_is_not_a_header(self) -> None:
        r"""``func f{,}`` names no parameter, so it defines nothing."""
        with pytest.raises(HaltError, match="no such function"):
            run(
                ["begin;var v;set v f{1};end;", "func f{,};end 1;"],
                ScriptedIO(),
            )

    def test_a_long_function_body_runs_to_its_end(self) -> None:
        r"""A callee's length is its own business now that no budget is shared."""
        body = "set b a;" * 40
        program = [
            "begin;var v;set v f{65};out v;end;",
            f"func f{{a}};var b;{body}end a;",
        ]
        assert _run(program) == "A"

    def test_a_call_used_as_a_bare_command_runs_for_its_effect(self) -> None:
        r"""The reversed cat's shape, in miniature: a call whose value is."""
        program = (
            'begin;var l;set l "xy";at{l, 0.5, 65};var c;set c at{l, 0.5};out c;end;'
        )
        assert _run([program]) == "A"
