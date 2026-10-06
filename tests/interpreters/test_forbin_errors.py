"""What Forbin refuses at scan and parse time, and what it says."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.interpreters.forbin_support import run_program
from tests.raises import raises_message


class TestScannerBoundaries:
    """Where the scanner stops: at punctuation, at a keyword, and at EOF."""

    def test_punctuation_needs_no_space_after_it(self) -> None:
        """A cursor that steps two characters lands past the next token."""
        assert run_program("main { a = 1;out 0,1,0,0,1,0,0,0; }") == "H"
        assert run_program("main { a =1; out 0,1,0,0,0,0,0,a; }") == "A"
        assert run_program("main{a=1;out 0,1,0,0,0,0,0,a;}") == "A"
        assert run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain{g 1;}") == "A"

    def test_a_name_may_be_a_keyword_followed_by_an_underscore(self) -> None:
        """``for_a`` is a name; the lookahead must not stop at ``for``."""
        assert run_program("main { for_a = 1; out 0,1,0,0,0,0,0,for_a; }") == "A"
        assert (
            run_program(
                "g { return_b = 1; return return_b; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "A"
        )

    def test_input_ending_mid_construct_is_a_clean_rejection(self) -> None:
        """Every bound check, asked about the position one past the end."""
        for code, message in (
            ("main { x = (g 0", "expected ',' at position 15"),
            ("main { x = (", "expected an identifier at position 12"),
            ("main { a, ", "expected a value at position 10"),
            ("main { for", "expected an identifier at position 10"),
            ("main { a =", "expected a value at position 10"),
        ):
            with raises_message(ValueError, message):
                run(code, ScriptedIO(""))

    def test_a_parenthesised_call_in_statement_position(self) -> None:
        """``(g 0);`` parses as a statement, and then halts."""
        with pytest.raises(HaltError) as caught:
            run("g { return 1; }\nmain { (g 0); }", ScriptedIO(""))
        assert str(caught.value) == "called value is not a function"


class TestIdentifierCharacters:
    """What may appear in a name, and where."""

    def test_a_name_may_contain_a_digit(self) -> None:
        """Digits are allowed after the first character, not before it."""
        assert run_program("main { a1 = 1; out 0,1,0,0,0,0,0,a1; }") == "A"
        with raises_message(
            ValueError, "statement must be a call, assignment, or return at position 9"
        ):
            run("main {\n 1a = 0;\n}\n", ScriptedIO(""))


class TestKeywordPrefixedNames:
    def test_an_identifier_may_start_with_a_keyword(self) -> None:
        """``returnvar`` is a name, not ``return`` followed by ``var``."""
        eight = lambda name: ",".join([name] * 8)  # noqa: E731
        code = (
            "main { returnvar = 1,1,1,1,1,1,1,1;"
            " forvar = 0,1,0,0,0,0,0,1;"
            f" out {eight('returnvar')};"
            f" out {eight('forvar')}; }}"
        )
        assert run_program(code) == "\xff\x00"


class TestParserErrors:
    def test_line_comments_are_ignored(self) -> None:
        code = "main { // header\n a = 1; // trailing\n out 0,0,0,0,0,0,0,a; }"
        assert run_program(code) == "\x01"

    def test_a_comment_runs_to_the_newline_whatever_it_holds(self) -> None:
        """Only a line break ends a comment, not any character within it."""
        code = "main { // note X here: 3+4 = }{ ;\n out 0,1,0,0,1,0,0,0; }"
        assert run_program(code) == "H"

    def test_missing_paren_after_anon_func(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            run_program("main { x = (a@ { return 1; }; }")

    def test_digit_where_an_identifier_is_expected(self) -> None:
        with pytest.raises(ValueError, match="identifier"):
            run_program("main { for 1:0..1 { } }")

    def test_value_at_end_of_input(self) -> None:
        with pytest.raises(ValueError, match="value"):
            run_program("main { x =")

    def test_anonymous_function_literal(self) -> None:
        code = "main { f = (a@ { out 0,0,0,0,0,0,0,a; }); r = (f 1); }"
        assert run_program(code) == "\x01"

    def test_unexpected_character(self) -> None:
        with pytest.raises(ValueError, match="character"):
            run_program("main { x = 2; }")

    def test_range_needs_two_dots(self) -> None:
        with pytest.raises(ValueError, match=r"\.\."):
            run_program("main { for i:0 1 { } }")

    def test_trailing_comma_header(self) -> None:
        # f a, { is a header whose parameter list ends after the comma
        assert run_program("main { f a, { out 0,0,0,0,0,0,0,0; } }") == ""

    def test_unterminated_block(self) -> None:
        with pytest.raises(ValueError, match="unterminated") as caught:
            run_program("main {")
        assert str(caught.value) == "unterminated block, expected '}' at position 6"

    def test_assignment_target_must_be_a_variable(self) -> None:
        """Both spellings fail, and at their own position."""
        with pytest.raises(ValueError, match="target must be a variable") as caught:
            run_program("main { (f 1) = 2; }")
        assert str(caught.value) == (
            "assignment target must be a variable at position 13"
        )
        with pytest.raises(ValueError, match="target must be a variable") as caught:
            run_program("main { a, !b = 0, 1; }")
        assert str(caught.value) == (
            "assignment target must be a variable at position 14"
        )

    def test_multi_target_needs_equals(self) -> None:
        with pytest.raises(ValueError, match="after assignment"):
            run_program("main { a, b 2; }")

    def test_statement_must_be_a_call_or_assignment(self) -> None:
        with pytest.raises(ValueError, match="statement must be"):
            run_program("main { 1; }")

    def test_calling_a_non_function_halts(self) -> None:
        with pytest.raises(HaltError, match="not a function"):
            run_program("main { x = 0; r = (x 1); }")

    def test_deep_recursion_no_longer_capped(self) -> None:
        """A correct, terminating recursion past the old 250-level cap completes."""
        depth = 300
        lines = ["main { f0 0; }"]
        for i in range(depth):
            body = f"f{i + 1} 0;" if i + 1 < depth else "out 0,0,0,0,0,0,0,1;"
            lines.append(f"f{i} x {{ {body} }}")
        assert run_program("\n".join(lines)) == "\x01"

    def test_deep_expression_recursion_halts_instead_of_leaking(self) -> None:
        """Expression-position recursion halts rather than leaking a crash."""
        depth = 400
        lines = ["main { r = (f0 0); }"]
        for i in range(depth):
            body = (
                f"r = (f{i + 1} 0); return r;"
                if i + 1 < depth
                else "out 0,0,0,0,0,0,0,1;"
            )
            lines.append(f"f{i} x {{ {body} }}")
        with raises_message(
            HaltError, "expression-position recursion exceeded the host's depth limit"
        ):
            run_program("\n".join(lines))

    def test_shallow_expression_recursion_still_completes(self) -> None:
        """The conversion does not swallow a recursion that fits."""
        depth = 100
        lines = ["main { r = (f0 0); }"]
        for i in range(depth):
            body = (
                f"r = (f{i + 1} 0); return r;"
                if i + 1 < depth
                else "out 0,0,0,0,0,0,0,1;"
            )
            lines.append(f"f{i} x {{ {body} }}")
        assert run_program("\n".join(lines)) == "\x01"

    def test_multi_assignment(self) -> None:
        code = "main { a, b = 1, 0; out 0,0,0,0,0,0,0,a; out 0,0,0,0,0,0,0,b; }"
        assert run_program(code) == "\x01\x00"


class TestErrorMessages:
    """The wording of a rejection, not merely that one happened."""

    def test_a_range_bound_that_is_not_a_number(self) -> None:
        """``start`` and ``end`` name which bound was wrong."""
        with pytest.raises(HaltError, match="for end bound must be a number"):
            run("f { return 0; }\nmain {\n for i:0..f { f 0; }\n}\n", ScriptedIO(""))
        with pytest.raises(HaltError, match="for start bound must be a number"):
            run("f { return 0; }\nmain {\n for i:f..1 { f 0; }\n}\n", ScriptedIO(""))

    def test_out_rejects_the_two_ways_of_being_wrong(self) -> None:
        """A wrong count and a non-bit argument are different complaints."""
        with pytest.raises(HaltError, match="out needs exactly 8 bit arguments"):
            run("main { out 0,1,0; }\n", ScriptedIO(""))
        with pytest.raises(HaltError, match="out needs bit arguments"):
            run("f { return 0; }\nmain { out 0,1,0,0,0,0,0,f; }\n", ScriptedIO(""))

    def test_calling_and_negating_the_wrong_thing(self) -> None:
        with pytest.raises(HaltError, match="called value is not a function"):
            run("main {\n a = 1;\n a 0;\n}\n", ScriptedIO(""))
        with pytest.raises(HaltError, match=r"! needs a bit"):
            run("f { return 0; }\nmain { out 0,1,0,0,0,0,0,!f; }\n", ScriptedIO(""))

    def test_the_parser_names_what_it_wanted(self) -> None:
        for code, message in (
            (
                "main {\n for i:0.1 { out 0,1,0,0,0,0,0,i; }\n}\n",
                "expected '..' or an iteration list",
            ),
            ("main {\n 1 = 0;\n}\n", "assignment target must be a variable"),
            ("main {\n a,b;\n}\n", "expected '=' after assignment targets"),
            ("main {\n !0;\n}\n", "statement must be a call, assignment, or return"),
            ("main { a = ", "expected a value"),
            ("main { ", "unterminated block"),
        ):
            with pytest.raises(ValueError, match=message):
                run(code, ScriptedIO(""))

    def test_the_recursive_evaluator_names_its_bounds_too(self) -> None:
        """``start``/``end`` are spelled twice, and only one copy was tested."""
        for code, which in (
            (
                "h { return 0; }\ng { for i:0..h { return 0; } return 0; }\n"
                "main { x = (g 0); }\n",
                "end",
            ),
            (
                "h { return 0; }\ng { for i:h..1 { return 0; } return 0; }\n"
                "main { x = (g 0); }\n",
                "start",
            ),
        ):
            with pytest.raises(HaltError) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value).startswith(
                f"for {which} bound must be a number, got "
            )

    def test_both_assignment_target_checks_are_reached(self) -> None:
        """A single target and a target *list* are rejected separately."""
        for code, position in (
            ("main {\n 1 = 0;\n}\n", 10),
            ("main {\n 1, b = 0, 1;\n}\n", 14),
            ("main {\n a, 1 = 0, 1;\n}\n", 14),
        ):
            with raises_message(
                ValueError,
                f"assignment target must be a variable at position {position}",
            ):
                run(code, ScriptedIO(""))

    def test_a_stray_slash_is_not_a_comment(self) -> None:
        """A comment needs *two* slashes, and one at the end of input."""
        with pytest.raises(ValueError, match="expected an identifier") as caught:
            run("main { out 0,1,0,0,1,0,0,0; }\n/", ScriptedIO(""))
        # Position 30 is the ``/`` itself: the bound held, so the scanner
        # stopped there rather than reading past the end of the input.
        assert str(caught.value) == "expected an identifier at position 30"
        assert run_program("main { out 0,1,0,0,1,0,0,0; }\n//") == "H"
        with pytest.raises(ValueError, match="no main function"):
            run("// c", ScriptedIO(""))
