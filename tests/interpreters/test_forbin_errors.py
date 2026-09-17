"""What Forbin refuses at scan and parse time, and what it says."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.interpreters.forbin_support import run_program
from tests.raises import raises_message


class TestScannerBoundaries:
    """Where the scanner stops: at punctuation, at a keyword, and at EOF.

    Three blind spots, all of them from programs that were too tidy.
    Every program in the suite put a space after each ``;`` and ``=``, so
    a cursor that advanced two characters instead of one simply landed on
    whitespace ``_skip_ws`` would have eaten anyway.  Every program closed
    its brackets, so no bound check was ever asked about the position one
    past the end.  And the names that begin with a keyword were all
    followed by a letter, never an underscore.
    """

    def test_punctuation_needs_no_space_after_it(self) -> None:
        """A cursor that steps two characters lands past the next token.

        With a space after every ``;`` and ``=`` the overshoot is
        invisible.  These programs remove the cushion.
        """
        assert run_program("main { a = 1;out 0,1,0,0,1,0,0,0; }") == "H"
        assert run_program("main { a =1; out 0,1,0,0,0,0,0,a; }") == "A"
        assert run_program("main{a=1;out 0,1,0,0,0,0,0,a;}") == "A"
        assert run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain{g 1;}") == "A"

    def test_a_name_may_be_a_keyword_followed_by_an_underscore(self) -> None:
        """``for_a`` is a name; the lookahead must not stop at ``for``.

        A keyword is only a keyword when what follows it cannot continue
        an identifier.  The suite had ``outx`` and ``fora`` -- a *letter*
        after the keyword -- but never an underscore, which is the other
        half of that character class.
        """
        assert run_program("main { for_a = 1; out 0,1,0,0,0,0,0,for_a; }") == "A"
        assert (
            run_program(
                "g { return_b = 1; return return_b; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "A"
        )

    def test_input_ending_mid_construct_is_a_clean_rejection(self) -> None:
        """Every bound check, asked about the position one past the end.

        A program that stops in the middle of a construct is what puts the
        cursor at ``i == n`` inside ``_expect``, ``_ident`` and the
        statement scanner.  Off by one there is the difference between a
        parse error naming what was wanted and an IndexError.
        """
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
        """``(g 0);`` parses as a statement, and then halts.

        The statement scanner accepts a ``call`` node as well as a ``var``,
        so the parenthesised form gets through parsing -- and then the
        evaluator treats the whole parenthesised call as the *callee* of a
        further call, which is not a function.  Both halves matter: the
        node tag has to be the one the scanner names, and the rejection has
        to be this one rather than a parse error.
        """
        with pytest.raises(HaltError) as caught:
            run("g { return 1; }\nmain { (g 0); }", ScriptedIO(""))
        assert str(caught.value) == "called value is not a function"


class TestIdentifierCharacters:
    """What may appear in a name, and where.

    ``_ident`` checks two character classes: the first character may be a
    letter or ``_``, and each character after it may be alphanumeric or
    ``_``.  The suite's names were all plain letters, so the underscore
    half of the *continuation* class was never exercised -- a name could
    stop being allowed to contain one and every test would still pass.
    """

    def test_an_underscore_may_appear_inside_a_name(self) -> None:
        """``a_b`` is one identifier, not ``a`` followed by ``_b``.

        Dropping ``_`` from the continuation class ends the name at the
        underscore, which leaves the rest as a separate token and changes
        what the program means rather than rejecting it outright.
        """
        assert run_program("main { a_b = 1; out 0,1,0,0,0,0,0,a_b; }") == "A"

    def test_a_name_may_start_with_an_underscore(self) -> None:
        """The first-character class allows ``_`` too."""
        assert run_program("main { _x = 1; out 0,1,0,0,0,0,0,_x; }") == "A"

    def test_a_name_may_contain_a_digit(self) -> None:
        """Digits are allowed after the first character, not before it."""
        assert run_program("main { a1 = 1; out 0,1,0,0,0,0,0,a1; }") == "A"
        with raises_message(
            ValueError, "statement must be a call, assignment, or return at position 9"
        ):
            run("main {\n 1a = 0;\n}\n", ScriptedIO(""))


class TestKeywordPrefixedNames:
    def test_an_identifier_may_start_with_a_keyword(self) -> None:
        """``returnvar`` is a name, not ``return`` followed by ``var``.

        The statement parser checks the character after each keyword and
        only takes the keyword branch when the word ends there, so a name
        that merely starts with one parses as an ordinary assignment.
        """
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
        """Only a line break ends a comment, not any character within it.

        The scan is over the two line-break characters alone, so a comment
        body is arbitrary text; the existing comment test happens to use
        only lowercase words, which a scan that also stopped on some other
        character would still pass.
        """
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
        """Both spellings fail, and at their own position.

        The single-target and multi-target paths reach the same message from
        different offsets, which is what tells them apart.
        """
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
        """A correct, terminating recursion past the old 250-level cap completes.

        Statement-position calls (``f(y);``, the language's only recursion
        idiom -- ``return`` exits a call immediately, so there is no
        return-value-threading pattern) push an explicit frame instead of
        recursing natively, so depth is no longer capped at all.
        """
        depth = 300
        lines = ["main { f0 0; }"]
        for i in range(depth):
            body = f"f{i + 1} 0;" if i + 1 < depth else "out 0,0,0,0,0,0,0,1;"
            lines.append(f"f{i} x {{ {body} }}")
        assert run_program("\n".join(lines)) == "\x01"

    def test_deep_expression_recursion_halts_instead_of_leaking(self) -> None:
        """Expression-position recursion halts rather than leaking a crash.

        ``x = (f y);`` needs the result back synchronously, so it recurses
        natively through ``_eval`` rather than pushing a frame, and deep
        enough it exhausts Python's stack.  The depth that survives is the
        host's, not the language's, so this asserts the *conversion* rather
        than a threshold: past it the caller sees the package's own
        ``HaltError``, not a ``RecursionError`` from the interpreter's
        internals.
        """
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
        """The conversion does not swallow a recursion that fits.

        Paired with the deep case: a catch that fired unconditionally, or a
        depth limit lowered by accident, would pass that test and fail this
        one.
        """
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
    """The wording of a rejection, not merely that one happened.

    Every message below was matched only loosely, or not at all, so an
    edit widening the literal that names the failing thing went unnoticed.
    Where the message interpolates a value, only the stable prefix is
    asserted: a ``_Function`` has no ``__repr__``, so the tail carries its
    address and differs between runs.
    """

    def test_every_message_is_asserted_whole(self) -> None:
        """Each rejection's text, in full, against the program that raises it.

        ``pytest.raises(match=...)`` is a *substring* search, so every test
        below this one passes just as happily against a message with extra
        text welded on either end -- which is exactly the edit mutation
        testing makes, and forty of them survived here.  Comparing
        ``str(caught.value)`` for equality closes that: each program is
        paired with the one message it must produce, so a widened literal
        fails, and a rejection firing in the *wrong place* fails too rather
        than matching some other entry's wording.

        The two interpolating messages are checked by prefix instead: a
        ``_Function`` has no ``__repr__``, so their tails carry an address
        that differs between runs.
        """
        exact = (
            ("main { out 0,1,0; }\n", "out needs exactly 8 bit arguments"),
            (
                "f { return 0; }\nmain { out 0,1,0,0,0,0,0,f; }\n",
                "out needs bit arguments",
            ),
            ("main {\n a = 1;\n a 0;\n}\n", "called value is not a function"),
            ("f { return 0; }\nmain { out 0,1,0,0,0,0,0,!f; }\n", "! needs a bit"),
            ("main {\n out 0,1,0,0,0,0,0,zz;\n}\n", "undeclared identifier 'zz'"),
            ("// c", "Forbin program has no main function"),
            (
                "main {\n for i:0.1 { out 0,1,0,0,0,0,0,i; }\n}\n",
                "expected '..' or an iteration list at position 15",
            ),
            (
                "main {\n 1 = 0;\n}\n",
                "assignment target must be a variable at position 10",
            ),
            (
                "main {\n a,b;\n}\n",
                "expected '=' after assignment targets at position 11",
            ),
            (
                "main {\n !0;\n}\n",
                "statement must be a call, assignment, or return at position 10",
            ),
            ("main { a = ", "expected a value at position 11"),
            ("main { ", "unterminated block, expected '}' at position 7"),
            (
                "main { out 0,1,0,0,1,0,0,0; }\n/",
                "expected an identifier at position 30",
            ),
            ("main x\n", "expected '{' after function name at position 7"),
        )
        for code, message in exact:
            with pytest.raises((HaltError, ValueError)) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value) == message

        # These two interpolate the offending value, whose repr carries an
        # address; the wording up to it is still pinned exactly.
        for code, prefix in (
            (
                "f { return 0; }\nmain {\n for i:0..f { f 0; }\n}\n",
                "for end bound must be a number, got ",
            ),
            (
                "f { return 0; }\nmain {\n for i:f..1 { f 0; }\n}\n",
                "for start bound must be a number, got ",
            ),
        ):
            with pytest.raises(HaltError) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value).startswith(prefix)

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
        """``start``/``end`` are spelled twice, and only one copy was tested.

        A top-level ``for`` is driven by the step machine, which builds its
        rows in ``_for_rows``; a ``for`` inside an *expression-position*
        call is evaluated recursively by ``_exec_stmt``, which carries its
        own copy of the same bound check.  Testing only the first left the
        second free to mislabel which bound was wrong.
        """
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
        """A single target and a target *list* are rejected separately.

        ``_statement`` checks the target twice -- once for ``x = ...``,
        once per name in ``a, b = ...`` -- and the suite only ever tripped
        the first.  A multi-target program is what reaches the second.
        """
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
        """A comment needs *two* slashes, and one at the end of input.

        The scanner looks ahead one character for the second ``/``, so the
        bound it checks matters most where there is no character to look
        at: a lone ``/`` as the last thing in the file.
        """
        with pytest.raises(ValueError, match="expected an identifier") as caught:
            run("main { out 0,1,0,0,1,0,0,0; }\n/", ScriptedIO(""))
        # Position 30 is the ``/`` itself: the bound held, so the scanner
        # stopped there rather than reading past the end of the input.
        assert str(caught.value) == "expected an identifier at position 30"
        assert run_program("main { out 0,1,0,0,1,0,0,0; }\n//") == "H"
        with pytest.raises(ValueError, match="no main function"):
            run("// c", ScriptedIO(""))
