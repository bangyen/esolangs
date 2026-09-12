r"""Unit tests for the Forbin interpreter."""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.raises import raises_message


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


def walk_until_halt_or_ancestor(machine: object, limit: int = 64) -> bool:
    r"""Step ``machine`` until it halts or a call provably replays an."""
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    keys: dict[int, object] = {}
    pushes, steps = 0, 0
    while pushes < limit:
        if machine.halted:
            return True
        if steps >= 20000:
            raise AssertionError("walk made no progress: neither halted nor pushed")
        depth_before = len(machine.frames)
        machine.step()
        steps += 1
        if len(machine.frames) <= depth_before:
            continue
        pushes += 1
        depth = len(machine.frames) - 1
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        keys = {d: k for d, k in keys.items() if d < depth}
        keys[depth] = machine.frame_entry_key(machine.frames[-1])
        if keys[depth] in [k for d, k in keys.items() if d < depth]:
            return False
    raise TimeoutError(
        f"undecided after {limit} pushed frames: neither halted nor repeated "
        "an ancestor's entry state"
    )


class TestOutput:
    def test_out_literals(self) -> None:
        code = "main { out 0,1,0,0,1,0,0,0; }"
        assert run_program(code) == "H"

    def test_out_arbitrary_byte(self) -> None:
        code = "main { out 1,1,1,1,1,1,1,1; }"
        assert run_program(code) == "\xff"

    def test_empty_program_rejected(self) -> None:
        with pytest.raises(ValueError, match="no main"):
            run_program("loop { out 0,0,0,0,0,0,0,0; }")

    def test_out_wrong_arity_halts(self) -> None:
        with pytest.raises(HaltError, match="8 bit"):
            run_program("main { out 0,0,0,0,0,0,0; }")


class TestInput:
    def test_in_reads_a_byte_msb_first(self) -> None:
        # pylint: disable=duplicate-code
        code = "main { a,b,c,d,e,f,g,h = (in 0); out a,b,c,d,e,f,g,h; }"
        assert run_program(code, "A") == "A"

    def test_in_running_out_raises_eof(self) -> None:
        code = "main { a,b,c,d,e,f,g,h = (in 0); }"
        with pytest.raises(EOFError):
            run(code, ScriptedIO(""))

    def test_truth_machine_zero(self) -> None:
        r"""A "0" byte is echoed and the program halts."""
        code = "\n".join(
            [
                "main {",
                "  a,b,c,d,e,f,g,h = (in 0);",
                "  out a,b,c,d,e,f,g,h;",
                "  for _:!h..h {",
                "    loop 0;",
                "  }",
                "}",
                "loop {",
                "  out 0,0,1,1,0,0,0,1;",
                "  loop 0;",
                "}",
            ]
        )
        assert run_program(code, "0") == "0"


class TestLoops:
    def test_range_loops_once_and_twice(self) -> None:
        # pylint: disable=duplicate-code
        code = """
            main {
              n = 0;
              for i:0..0 { n = !n; }
              out 0,0,0,0,0,0,0,n;
              n = 0;
              for i:0..1 { n = !n; }
              out 0,0,0,0,0,0,0,n;
            }
        """
        assert run_program(code) == "\x01\x00"

    def test_range_as_if_statement(self) -> None:
        # pylint: disable=duplicate-code
        code = """
            main {
              c = 0;
              for _:!c..c { out 0,1,0,0,0,0,0,1; }
              c = 1;
              for _:!c..c { out 0,1,0,0,0,0,0,1; }
            }
        """
        assert run_program(code) == "AA"

    def test_iteration_loop_over_variables(self) -> None:
        code = """
            main {
              any = 0;
              for i:(0, 0, 1) { for _:!i..i { any = 1; } }
              out 0,0,0,0,0,0,0,any;
            }
        """
        assert run_program(code) == "\x01"

    def test_iteration_wildcard_expands(self) -> None:
        code = """
            main {
              s = 0;
              for (i, j):((1, *)) { for _:!i..i { s = 1; } }
              out 0,0,0,0,0,0,0,s;
            }
        """
        assert run_program(code) == "\x01"

    def test_underscore_loop_variable(self) -> None:
        code = "main { for _:0..1 { out 0,1,0,0,0,0,0,1; } }"
        assert run_program(code) == "AA"

    def test_wildcard_iteration_loop_inside_an_expression_position_call(self) -> None:
        r"""An expression-position call (``(f 0)``) natively recurses through."""
        code = """
            f {
              s = 0;
              for (i, j):((1, *)) { for _:!i..i { s = j; } }
              return s;
            }
            main {
              r = (f 0);
              out 0,0,0,0,0,0,0,r;
            }
        """
        assert run_program(code) == "\x01"

    def test_non_wildcard_iteration_loop_inside_an_expression_position_call(
        self,
    ) -> None:
        r"""Same as above, but the pattern has no wildcard (the plain value-row."""
        code = """
            f {
              s = 0;
              for i:(0, 1) { s = i; }
              return s;
            }
            main {
              r = (f 0);
              out 0,0,0,0,0,0,0,r;
            }
        """
        assert run_program(code) == "\x01"


class TestFunctions:
    def test_not(self) -> None:
        code = "main { a = 1; a = !a; out 0,0,0,0,0,0,0,a; }"
        assert run_program(code) == "\x00"

    def test_unpassed_parameter_is_zero(self) -> None:
        r"""Unpassed parameters are set to 0 (per the wiki)."""
        code = """
            main {
              f a, b { out 0,0,0,0,0,0,0,b; }
              r = (f 1);
            }
        """
        assert run_program(code) == "\x00"

    def test_bare_block_is_function_literal(self) -> None:
        r"""A bare {code} block is a function literal in value position."""
        code = """
            main {
              x = { return 1; };
              out 0,0,0,0,0,0,0,(x 0);
            }
        """
        assert run_program(code) == "\x01"

    def test_function_returns(self) -> None:
        code = """
            one { return 1; }
            main {
              a = (one 0);
              out 0,0,0,0,0,0,0,a;
            }
        """
        assert run_program(code) == "\x01"

    def test_forward_reference(self) -> None:
        # pylint: disable=duplicate-code
        code = """
            main {
              h = 0;
              for _:!h..h { helper 0; }
            }
            helper { out 1,1,1,1,1,1,1,1; }
        """
        assert run_program(code) == ""

    def test_recursion(self) -> None:
        code = """
            main {
              a,b,c,d,e,f,g,h = (in 0);
              out a,b,c,d,e,f,g,h;
              for _:!h..h { again 0; }
            }
            again { out 0,0,1,1,0,0,0,1; }
        """
        # pylint: disable=duplicate-code
        assert run_program(code, "0") == "0"

    def test_function_as_argument(self) -> None:
        # pylint: disable=duplicate-code
        code = """
            eq a, b {
              equal = 0;
              for _:a..b { equal = !equal; }
              return equal;
            }
            main {
              x = 1;
              y = 1;
              r = (eq x, y);
              out 0,0,0,0,0,0,0,r;
            }
        """
        assert run_program(code) == "\x01"

    def test_undeclared_identifier_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared"):
            run_program("main { out 0,0,0,0,0,0,0,x; }")

    def test_not_on_function_halts(self) -> None:
        with pytest.raises(HaltError, match="needs a bit"):
            run_program("main { f { } f 0; a = !f; }")

    def test_malformed_syntax(self) -> None:
        r"""The whole message is asserted, position included."""
        with pytest.raises(ValueError, match="expected") as caught:
            run_program("main { out 0,0,0,0,0,0,0 } extra")
        assert str(caught.value) == "expected '{' after function name at position 32"


class TestScannerBoundaries:
    r"""Where the scanner stops: at punctuation, at a keyword, and at EOF."""

    def test_punctuation_needs_no_space_after_it(self) -> None:
        r"""A cursor that steps two characters lands past the next token."""
        assert run_program("main { a = 1;out 0,1,0,0,1,0,0,0; }") == "H"
        assert run_program("main { a =1; out 0,1,0,0,0,0,0,a; }") == "A"
        assert run_program("main{a=1;out 0,1,0,0,0,0,0,a;}") == "A"
        assert run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain{g 1;}") == "A"

    def test_a_name_may_be_a_keyword_followed_by_an_underscore(self) -> None:
        r"""``for_a`` is a name; the lookahead must not stop at ``for``."""
        assert run_program("main { for_a = 1; out 0,1,0,0,0,0,0,for_a; }") == "A"
        assert (
            run_program(
                "g { return_b = 1; return return_b; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "A"
        )

    def test_input_ending_mid_construct_is_a_clean_rejection(self) -> None:
        r"""Every bound check, asked about the position one past the end."""
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
        r"""``(g 0);`` parses as a statement, and then halts."""
        with pytest.raises(HaltError) as caught:
            run("g { return 1; }\nmain { (g 0); }", ScriptedIO(""))
        assert str(caught.value) == "called value is not a function"


class TestIdentifierCharacters:
    r"""What may appear in a name, and where."""

    def test_an_underscore_may_appear_inside_a_name(self) -> None:
        r"""``a_b`` is one identifier, not ``a`` followed by ``_b``."""
        assert run_program("main { a_b = 1; out 0,1,0,0,0,0,0,a_b; }") == "A"

    def test_a_name_may_start_with_an_underscore(self) -> None:
        r"""The first-character class allows ``_`` too."""
        assert run_program("main { _x = 1; out 0,1,0,0,0,0,0,_x; }") == "A"

    def test_a_name_may_contain_a_digit(self) -> None:
        r"""Digits are allowed after the first character, not before it."""
        assert run_program("main { a1 = 1; out 0,1,0,0,0,0,0,a1; }") == "A"
        with raises_message(
            ValueError, "statement must be a call, assignment, or return at position 9"
        ):
            run("main {\n 1a = 0;\n}\n", ScriptedIO(""))


class TestKeywordPrefixedNames:
    def test_an_identifier_may_start_with_a_keyword(self) -> None:
        r"""``returnvar`` is a name, not ``return`` followed by ``var``."""
        eight = lambda name: ",".join([name] * 8)  # noqa: E731
        code = (
            "main { returnvar = 1,1,1,1,1,1,1,1;"
            " forvar = 0,1,0,0,0,0,0,1;"
            f" out {eight('returnvar')};"
            f" out {eight('forvar')}; }}"
        )
        assert run_program(code) == "\xff\x00"


class TestDiscardTarget:
    r"""``_`` as an assignment target evaluates the value and drops it."""

    def test_discard_in_a_paired_assignment(self) -> None:
        r"""The remaining name still takes the value opposite *its* position."""
        code = "main { _, x = 1, 0; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x00"

        code = "main { x, _ = 1, 0; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x01"

    def test_discard_in_a_broadcast_assignment(self) -> None:
        r"""One value for several targets skips the ``_`` and fills the rest."""
        code = "main { _, x = 1; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x01"

    def test_discard_is_not_readable_afterwards(self) -> None:
        r"""``_`` is dropped rather than stored, so reading it is an error."""
        with pytest.raises(HaltError, match="undeclared identifier"):
            run_program("main { _ = 1; out 0,0,0,0,0,0,0,_; }")

    def test_every_binding_site_honours_the_discard(self) -> None:
        r"""Each of the four places a name is bound must skip ``_``."""
        for code in (
            # pylint: disable=duplicate-code
            "main { _ = 1; out 0,0,0,0,0,0,0,_; }",
            # pylint: disable=duplicate-code
            "main { _, x = 1, 0; out 0,0,0,0,0,0,0,_; }",
            # pylint: disable=duplicate-code
            "main { for _:0..1 { } out 0,0,0,0,0,0,0,_; }",
            "main { for _:(0, 1) { } out 0,0,0,0,0,0,0,_; }",
            # pylint: disable=duplicate-code
            "g { for _:0..1 { } return _; }\nmain { x = (g 0); }\n",
            "g { for _:(0, 1) { } return _; }\nmain { x = (g 0); }\n",
        ):
            with pytest.raises(HaltError) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value) == "undeclared identifier '_'"


class TestCallingANonFunction:
    r"""A call whose callee resolves to a bit rather than to a function."""

    def test_calling_a_local_with_arguments(self) -> None:
        with pytest.raises(HaltError, match="called value is not a function"):
            run_program("main { y = 1; y 1,0; }")

    def test_calling_a_local_without_arguments(self) -> None:
        with pytest.raises(HaltError, match="called value is not a function"):
            run_program("main { y = 1; y; }")


class TestParserErrors:
    def test_line_comments_are_ignored(self) -> None:
        code = "main { // header\n a = 1; // trailing\n out 0,0,0,0,0,0,0,a; }"
        assert run_program(code) == "\x01"

    def test_a_comment_runs_to_the_newline_whatever_it_holds(self) -> None:
        r"""Only a line break ends a comment, not any character within it."""
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
        # pylint: disable=duplicate-code
        assert run_program("main { f a, { out 0,0,0,0,0,0,0,0; } }") == ""

    def test_unterminated_block(self) -> None:
        with pytest.raises(ValueError, match="unterminated") as caught:
            run_program("main {")
        assert str(caught.value) == "unterminated block, expected '}' at position 6"

    def test_assignment_target_must_be_a_variable(self) -> None:
        r"""Both spellings fail, and at their own position."""
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
        r"""A correct, terminating recursion past the old 250-level cap."""
        depth = 300
        lines = ["main { f0 0; }"]
        for i in range(depth):
            body = f"f{i + 1} 0;" if i + 1 < depth else "out 0,0,0,0,0,0,0,1;"
            lines.append(f"f{i} x {{ {body} }}")
        assert run_program("\n".join(lines)) == "\x01"

    def test_deep_expression_recursion_halts_instead_of_leaking(self) -> None:
        r"""Expression-position recursion halts rather than leaking a crash."""
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
        r"""The conversion does not swallow a recursion that fits."""
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


class TestStepMachine:
    def test_main_with_parameters_defaults_to_zero(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine

        machine = _Machine("main a { out 0,0,0,0,0,0,0,a; }", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "\x00"

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine

        machine = _Machine("main { }", ScriptedIO())
        while not machine.halted:
            machine.step()
        machine.step()  # stepping a halted machine is.
        assert machine.halted

    def test_statement_call_inside_a_for_loop_body_pushes_a_frame(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        code = """
            helper { out 0,1,0,0,1,0,0,0; }
            main { for _:0..0 { helper 0; } }
        """
        assert run_program(code) == "H"

    def test_bare_return_at_top_level_pops_the_frame(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        code = "main { return 1; out 0,0,0,0,0,0,0,1; }"
        assert run_program(code) == ""

    def test_return_inside_a_for_loop_body_pops_the_frame(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        code = "main { for _:0..0 { return 1; } out 0,0,0,0,0,0,0,1; }"
        assert run_program(code) == ""

    def test_return_inside_a_non_range_for_loop_in_a_nested_call(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        code = """
            f {
              for i:(1, 0) { return i; }
              return 0;
            }
            main {
              r = (f 0);
              out 0,0,0,0,0,0,0,r;
            }
        """
        assert run_program(code) == "\x01"

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine

        machine = _Machine("main { out 0,0,0,0,0,0,0,1; }", ScriptedIO())
        assert hash(machine.snapshot()) is not None
        machine.step()
        assert hash(machine.snapshot()) is not None

    def test_non_numeric_range_bound_halts(self) -> None:
        r"""A ``for`` bound has to be a number, not a function."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_program("f { return 0; }\nmain { for _:f..1 { return 0; } return 0; }")

    def test_non_bit_out_argument_halts(self) -> None:
        r"""``out`` takes bits, matching the rule ``!`` already enforces."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_program("f { return 0; }\nmain { out f,0,1,1,0,0,0,1; return 0; }")


class TestForbinMutationSurvivors:
    r"""The step granularity a mutation survived, pinned by counting steps."""

    @staticmethod
    def _drive(code: str, stdin: str = "") -> tuple[int, str, int]:
        r"""Run ``code`` to a halt; return (steps, output, deepest frame stack)."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine

        machine = _Machine(code, ScriptedIO(stdin))
        steps, deepest = 0, 0
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        while not machine.halted and steps < 200:
            machine.step()
            steps += 1
            deepest = max(deepest, len(machine.frames))
        assert machine.halted
        return steps, machine.io.getvalue(), deepest

    def test_a_statement_position_call_is_its_own_step(self) -> None:
        r"""A call pushes a frame rather than recursing inside one step."""
        code = "main {\n helper x { out 0,1,0,0,0,0,0,x; }\n helper 1;\n helper 0;\n}\n"
        steps, out, deepest = self._drive(code)
        assert out == "A@"
        assert steps == 7
        assert deepest == 2  # main, plus the frame each.

    def test_a_for_loop_steps_once_per_row(self) -> None:
        r"""The loop yields between rows instead of running to completion."""
        once_and_twice = (
            "main {\n n = 0;\n for i:0..0 { n = !n; }\n"
            " out 0,0,0,0,0,0,0,n;\n n = 0;\n for i:0..1 { n = !n; }\n"
            " out 0,0,0,0,0,0,0,n;\n}\n"
        )
        steps, out, _ = self._drive(once_and_twice)
        assert out == "\x01\x00"
        assert steps == 15

        as_if = (
            "main {\n c = 0;\n for _:!c..c { out 0,1,0,0,0,0,0,1; }\n"
            " c = 1;\n for _:!c..c { out 0,1,0,0,0,0,0,1; }\n}\n"
        )
        steps, out, _ = self._drive(as_if)
        assert out == "AA"
        assert steps == 11

    def test_the_loop_body_cursor_advances_by_exactly_one(self) -> None:
        r"""``for_body_pos`` moves one statement at a time, both ways out."""
        # pylint: disable=duplicate-code
        steps, out, deepest = self._drive(
            "g { out 0,1,0,0,0,0,0,1; }\nh { out 0,1,0,0,0,1,0,0; }\n"
            "main { for i:0..0 { g 0; h 0; } }\n"
        )
        assert (steps, out, deepest) == (10, "AD", 2)

        # pylint: disable=duplicate-code
        steps, out, deepest = self._drive(
            "g { out 0,1,0,0,0,0,0,1; }\n"
            "main { for i:0..1 { out 0,1,0,0,0,1,0,i; g 0; } }\n"
        )
        assert (steps, out, deepest) == (13, "DAEA", 2)

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        steps, out, deepest = self._drive(
            "main { for i:0..1 { out 0,1,0,0,0,0,0,i; out 0,1,0,0,0,0,1,i; } }"
        )
        assert (steps, out, deepest) == (9, "@BAC", 1)

    def test_an_iteration_loop_selects_the_wildcard_columns(self) -> None:
        r"""``*`` marks the columns to expand, and the test is ``==``."""
        code = (
            "main {\n any = 0;\n for i:(0, 0, 1) { for _:!i..i { any = 1; } }\n"
            " out 0,0,0,0,0,0,0,any;\n}\n"
        )
        steps, out, _ = self._drive(code)
        assert out == "\x01"
        assert steps == 11


class TestForbinAncestorHangDetection:
    r"""Infinite recursion, proven rather than waited out."""

    @staticmethod
    def _verdict(code: str, stdin: str = "") -> bool:
        from esolangs.interpreters.other.forbin import _Machine

        return walk_until_halt_or_ancestor(_Machine(code, ScriptedIO(stdin)))

    def test_an_unconditional_self_call_is_a_proven_hang(self) -> None:
        r"""``f`` calls itself with nothing changed, so it never returns."""
        assert self._verdict("main {\n f {\n  f 0;\n }\n f 0;\n}\n") is False

    def test_mutual_recursion_is_a_proven_hang(self) -> None:
        r"""The ancestor need not be the same function, only the same state."""
        assert self._verdict("a { b 0; }\nb { a 0; }\nmain { a 0; }\n") is False

    def test_a_flipping_argument_still_repeats(self) -> None:
        r"""``f !x`` alternates, so the second lap re-enters the first's state."""
        assert self._verdict("main {\n f x {\n  f !x;\n }\n f 0;\n}\n") is False

    def test_a_terminating_program_is_not_flagged(self) -> None:
        r"""The ordinary programs the suite already runs must stay unflagged."""
        assert self._verdict("main {\n h x { out 0,1,0,0,0,0,0,x; }\n h 1;\n h 0;\n}\n")
        assert self._verdict(
            "main {\n g x {\n  for _:!x..x { return 0; }\n  g 1;\n }\n g 0;\n}\n"
        )

    def test_the_same_helper_called_twice_is_not_recursion(self) -> None:
        r"""Two sequential calls share a key but neither is the other's."""
        assert self._verdict("main {\n h x { out 0,1,0,0,0,0,0,x; }\n h 1;\n h 1;\n}\n")

    def test_recursion_waiting_on_input_is_not_a_hang(self) -> None:
        r"""The input cursor is in the key, and that is what keeps it sound."""
        code = (
            "f {\n a,b,c,d,e,g,h,i = (in 0);\n for _:!i..i { return 0; }\n f 0;\n}\n"
            "main { f 0; }\n"
        )
        assert self._verdict(code, "@\nA") is True

    def test_an_undecided_walk_raises_rather_than_claiming_a_halt(self) -> None:
        r"""Exhausting the bound is not a verdict, and must not read as one."""
        from esolangs.interpreters.other.forbin import _Machine

        class _NeverRepeats(_Machine):
            r"""Stands in for any mutant whose key stops repeating."""

            counter = 0

            def frame_entry_key(self, _frame: object) -> tuple[object, ...]:
                _NeverRepeats.counter += 1
                return ("unique", _NeverRepeats.counter)

        machine = _NeverRepeats("main {\n f {\n  f 0;\n }\n f 0;\n}\n", ScriptedIO(""))
        with pytest.raises(TimeoutError, match="undecided"):
            walk_until_halt_or_ancestor(machine)


class TestArgumentThreading:
    r"""Programs that notice ``_eval``'s arguments going astray."""

    def test_a_call_returning_a_call(self) -> None:
        r"""``globals_`` and ``depth`` threaded through nested returns."""
        assert (
            run_program(
                "one { return 1; }\nf { return (one 0); }\n"
                "main {\n a = (f 0);\n out 0,1,0,0,0,0,0,a;\n}\n"
            )
            == "A"
        )

    def test_a_call_as_a_range_bound(self) -> None:
        r"""A ``for`` bound is a value, so it may itself be a call."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..(one 0) { g i; }\n}\n"
            )
            == "@A"
        )

    def test_a_call_in_a_nested_loop_bound(self) -> None:
        r"""The inner bound is re-evaluated on every row of the outer loop."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..1 {\n  for j:0..(one 0) { g j; }\n }\n}\n"
            )
            == "@A@A"
        )

    def test_a_call_opens_a_range_through_not(self) -> None:
        r"""``!`` is how a call reaches the *start* of a range."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nzero { return 0; }\n"
                "main {\n for i:!(zero 0)..1 { g i; }\n}\n"
            )
            == "A"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:!(in 0)..1 { g i; }\n}\n",
                "\x00",
            )
            == "A"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..!(one 0) { g i; }\n}\n"
            )
            == "@"
        )

    def test_a_call_at_the_remaining_positions(self) -> None:
        r"""The call twins of the ``in`` cases: argument, pattern, multi-RHS."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\nmain { g (one 0); }\n"
            )
            == "A"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:((one 0)) { g i; }\n}\n"
            )
            == "A"
        )
        assert (
            run_program(
                "one { return 1; }\n"
                "main {\n a,b = (one 0),(one 0);\n out 0,1,0,0,0,0,b,a;\n}\n"
            )
            == "C"
        )

    def test_input_read_at_each_position(self) -> None:
        r"""``in`` at the position, not assigned to a local first."""
        assert run_program("main { out 0,1,0,0,0,0,0,(in 0); }\n", "\x01") == "@"
        assert run_program("main { out 0,1,0,0,0,0,0,!(in 0); }\n", "\x00") == "A"
        assert (
            run_program("g x { out 0,1,0,0,0,0,0,x; }\nmain { g (in 0); }\n", "\x01")
            == "@"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:0..(in 0) { g i; }\n}\n",
                "\x01",
            )
            == "@"
        )
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:((in 0)) { g i; }\n}\n",
                "\x01",
            )
            == "@"
        )
        assert (
            run_program(
                "f { return (in 0); }\nmain {\n a = (f 0);\n out 0,1,0,0,0,0,0,a;\n}\n",
                "\x01",
            )
            == "@"
        )
        assert (
            run_program(
                "main {\n a,b = (in 0),(in 0);\n out 0,1,0,0,0,0,b,a;\n}\n", "\x01\x01"
            )
            == "@"
        )

    def test_a_nested_definition_reads_the_enclosing_frame(self) -> None:
        r"""``_lookup`` walks ``frame.parent`` until it finds the name."""
        assert (
            run_program(
                "main {\n a = 1;\n inner { out 0,1,0,0,0,0,0,a; }\n inner 0;\n}\n"
            )
            == "A"
        )
        assert (
            run_program(
                "main {\n a = 1;\n mid {\n  deep { out 0,1,0,0,0,0,0,a; }\n"
                "  deep 0;\n }\n mid 0;\n}\n"
            )
            == "A"
        )

    def test_two_wildcards_expand_to_four_rows(self) -> None:
        r"""``*`` doubles the row count, and the columns are independent."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\n"
                "main {\n for (i,j):((*,*)) { g i; g j; }\n}\n"
            )
            == "@@@AA@AA"
        )

    def test_arity_mismatches_are_tolerated(self) -> None:
        r"""Extra arguments are dropped and missing ones default to zero."""
        assert run_program("f x,y { out 0,1,0,0,0,0,y,x; }\nmain { f 1; }\n") == "A"
        assert run_program("f x { out 0,1,0,0,0,0,0,x; }\nmain { f 1,1,1; }\n") == "A"
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\n"
                "main {\n for (i,j):((0,1),(1)) { g i; }\n}\n"
            )
            == "@A"
        )

    def test_a_loop_variable_named_underscore_stays_unbound(self) -> None:
        r"""``_`` is the discard name, so it must not enter the frame."""
        with pytest.raises(HaltError, match="undeclared identifier '_'"):
            run(
                "main {\n for _:0..0 { out 0,1,0,0,0,0,0,0; }\n"
                " out 0,1,0,0,0,0,0,_;\n}\n",
                ScriptedIO(""),
            )


class TestThreadedResources:
    r"""Every evaluator argument, loaded in every position that forwards it."""

    def test_the_reader_reaches_every_position_that_can_read(self) -> None:
        r"""``(in 0)`` in each spot that forwards the reader."""
        assert (
            run_program("main { for i:0..(in 0) { out 0,1,0,0,0,0,0,i; } }", "\xff")
            == "@A"
        )
        assert (
            run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { g (in 0); }\n", "\xff")
            == "A"
        )
        assert run_program("main { x = (in 0); out 0,1,0,0,0,0,0,x; }", "\xff") == "A"
        assert (
            run_program("main { for i:((in 0)) { out 0,1,0,0,0,0,0,i; } }", "\xff")
            == "A"
        )
        # pylint: disable=duplicate-code
        assert (
            run_program(
                "g { x = (in 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n",
                "\xff",
            )
            == "A"
        )

    def test_the_frame_reaches_every_position_that_reads_a_local(self) -> None:
        r"""A bare local name in each spot that forwards the frame."""
        assert (
            run_program("main { n = 1; for i:0..n { out 0,1,0,0,0,0,0,i; } }") == "@A"
        )
        assert (
            run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { n = 1; g n; }\n") == "A"
        )
        assert (
            run_program(
                "g { n = 1; return n; }\nmain { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )

    def test_the_globals_reach_every_position_that_can_call(self) -> None:
        r"""A call in each spot that forwards the function table."""
        assert (
            run_program(
                "h { return 1; }\nmain { for i:0..(h 0) { out 0,1,0,0,0,0,0,i; } }\n"
            )
            == "@A"
        )
        assert (
            run_program(
                "h { return 1; }\ng a { out 0,1,0,0,0,0,0,a; }\nmain { g (h 0); }\n"
            )
            == "A"
        )

    def test_an_argument_list_carries_its_own_resources(self) -> None:
        r"""``_eval``'s argument list is a separate forwarding site."""
        # pylint: disable=duplicate-code
        assert (
            run_program(
                "k { return 1; }\nh a { return a; }\n"
                "g { x = (h (k 0)); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )
        # pylint: disable=duplicate-code
        assert (
            run_program(
                "h a { return a; }\ng { x = (h (in 0)); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n",
                "\xff",
            )
            == "A"
        )

    def test_a_call_nested_in_a_call_is_what_reads_the_depth(self) -> None:
        r"""``depth`` is forwarded everywhere and read once, as ``depth + 1``."""
        assert (
            run_program(
                "h { return 1; }\ng { x = (h 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )
        assert (
            run_program(
                "k { return 1; }\nh { x = (k 0); return x; }\n"
                "g { x = (h 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n"
            )
            == "A"
        )


class TestWildcardExpansion:
    r"""``*`` in an iteration pattern expands to every bit combination."""

    def test_three_wildcards_expand_to_eight_rows_in_order(self) -> None:
        r"""Three ``*`` need a cursor that reaches index two."""
        code = (
            "g a, b, c { out 0,1,0,0,0,0,0,a; out 0,1,0,0,0,1,0,b; "
            "out 0,1,0,0,1,0,0,c; }\n"
            "main { for (i,j,k):((*,*,*)) { g i, j, k; } }\n"
        )
        assert run_program(code) == "@DH@DI@EH@EIADHADIAEHAEI"

    def test_the_recursive_copy_expands_too(self) -> None:
        r"""The same expansion, reached through an expression-position call."""
        assert (
            run_program(
                "g { for (i,j):((*,*)) { return 0; } return 1; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert (
            run_program(
                "g { for (i,j,k):((1,*,0)) { return j; } return 1; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )


class TestCallResultDefaults:
    r"""What a call evaluates to when it returns nothing."""

    def test_a_function_that_returns_nothing_evaluates_to_zero(self) -> None:
        assert run_program("g { }\nmain { x = (g 0); out 0,1,0,0,0,0,0,x; }\n") == "@"

    def test_out_evaluates_to_zero(self) -> None:
        r"""``out`` is a call like any other and yields a value."""
        assert (
            run_program("main { x = (out 0,1,0,0,0,0,0,1); out 0,1,0,0,0,0,0,x; }")
            == "A@"
        )


class TestPairedLengthsAreNotChecked:
    r"""Forbin pairs by position and stops at the shorter side."""

    def test_arity_mismatch_is_tolerated_on_both_call_paths(self) -> None:
        r"""A statement call and an expression call bind arguments separately."""
        # pylint: disable=duplicate-code
        assert run_program("g a, b { out 0,1,0,0,0,0,0,a; }\nmain { g 1; }\n") == "A"
        assert run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { g 1, 0; }\n") == "A"
        # pylint: disable=duplicate-code
        assert (
            run_program(
                "g a { return a; }\nmain { x = (g 1, 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "A"
        )

    def test_an_assignment_may_have_uneven_sides(self) -> None:
        r"""Extra targets stay unset and extra values are dropped."""
        assert run_program("main { a, b = 1, 0, 1; out 0,1,0,0,0,0,0,a; }") == "A"
        assert run_program("main { a, b, c = 1, 0; out 0,1,0,0,0,0,0,a; }") == "A"

    def test_a_row_narrower_than_its_variable_list_is_tolerated(self) -> None:
        r"""Two loop variables over one-wide rows leave the second unbound."""
        assert (
            run_program("main { for (i,j):((0),(1)) { out 0,1,0,0,0,0,0,i; } }") == "@A"
        )
        # pylint: disable=duplicate-code
        assert (
            run_program(
                "g { for (i,j):((0),(1)) { return 0; } return 0; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )


class TestErrorMessages:
    r"""The wording of a rejection, not merely that one happened."""

    def test_every_message_is_asserted_whole(self) -> None:
        r"""Each rejection's text, in full, against the program that raises it."""
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

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
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
        r"""``start`` and ``end`` name which bound was wrong."""
        with pytest.raises(HaltError, match="for end bound must be a number"):
            run("f { return 0; }\nmain {\n for i:0..f { f 0; }\n}\n", ScriptedIO(""))
        with pytest.raises(HaltError, match="for start bound must be a number"):
            run("f { return 0; }\nmain {\n for i:f..1 { f 0; }\n}\n", ScriptedIO(""))

    def test_out_rejects_the_two_ways_of_being_wrong(self) -> None:
        r"""A wrong count and a non-bit argument are different complaints."""
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
        r"""``start``/``end`` are spelled twice, and only one copy was tested."""
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
        r"""A single target and a target *list* are rejected separately."""
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
        r"""A comment needs *two* slashes, and one at the end of input."""
        with pytest.raises(ValueError, match="expected an identifier") as caught:
            run("main { out 0,1,0,0,1,0,0,0; }\n/", ScriptedIO(""))
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert str(caught.value) == "expected an identifier at position 30"
        assert run_program("main { out 0,1,0,0,1,0,0,0; }\n//") == "H"
        with pytest.raises(ValueError, match="no main function"):
            run("// c", ScriptedIO(""))


class TestSnapshotWithoutTheCycleDetector:
    r"""What the cycle detector sees, checked without importing it."""

    def test_a_snapshot_distinguishes_the_states_it_must(self) -> None:
        r"""Every component of the snapshot has to move something."""
        from esolangs.interpreters.other.forbin import _Machine

        def at(code: str, steps: int, stdin: str = "") -> tuple[object, ...]:
            machine = _Machine(code, ScriptedIO(stdin))
            for _ in range(steps):
                if machine.halted:
                    break
                machine.step()
            return machine.snapshot()

        prog = (
            "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n a = 0;\n for i:0..1 { g i; }\n}\n"
        )

        # pylint: disable=duplicate-code
        assert at(prog, 1) != at(prog, 2)
        # pylint: disable=duplicate-code
        assert at("main {\n a = 0;\n}\n", 1) != at("main {\n a = 1;\n}\n", 1)
        # pylint: disable=duplicate-code
        assert at(prog, 3) != at(prog, 4)
        # pylint: disable=duplicate-code
        nested = "f { out 0,1,0,0,0,0,0,1; }\nmain {\n f 0;\n}\n"
        assert at(nested, 1) != at(nested, 2)
        # pylint: disable=duplicate-code
        read = "main {\n a,b,c,d,e,f,g,h = (in 0);\n}\n"
        assert at(read, 0, "HH") != at(read, 1, "HH")

    def test_an_anonymous_function_is_named_by_the_empty_string(self) -> None:
        r"""``""`` is a real value here, not a placeholder nobody reads."""
        from esolangs.interpreters.other.forbin import _Machine

        machine = _Machine(
            "main { f = { out 0,1,0,0,1,0,0,0; }; f 0; }", ScriptedIO("")
        )
        keys, steps, depth = [], 0, len(machine.frames)
        while not machine.halted and steps < 200:
            machine.step()
            steps += 1
            if len(machine.frames) > depth:
                keys.append(machine.frame_entry_key(machine.frames[-1]))
            depth = len(machine.frames)
        assert machine.halted
        assert machine.io.getvalue() == "H"
        # pylint: disable=duplicate-code
        assert keys == [("", (), 0)]

    def test_a_frame_outside_a_loop_reports_a_sentinel(self) -> None:
        r"""The two loop counters need a value meaning "not in a loop"."""
        from esolangs.interpreters.other.forbin import _Machine

        def frames(code: str, steps: int) -> tuple[object, ...]:
            machine = _Machine(code, ScriptedIO(""))
            for _ in range(steps):
                if machine.halted:
                    break
                machine.step()
            return machine.snapshot()[0]

        looping = "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n for i:0..1 { g i; }\n}\n"
        flat = "g x { out 0,1,0,0,0,0,0,x; }\nmain {\n g 0;\n g 1;\n}\n"

        # pylint: disable=duplicate-code
        assert frames(looping, 0) == (("main", 0, (), -1, -1),)
        # pylint: disable=duplicate-code
        assert frames(looping, 1) == (("main", 0, (), 0, 0),)
        # pylint: disable=duplicate-code
        assert frames(looping, 2) == (("main", 0, (("i", "0"),), 1, 0),)
        assert frames(looping, 6) == (("main", 0, (("i", "1"),), 2, 0),)
        # pylint: disable=duplicate-code
        assert frames(looping, 3)[1] == ("g", 0, (("x", "0"),), -1, -1)
        # pylint: disable=duplicate-code
        for step in range(4):
            assert all(f[3] == -1 and f[4] == -1 for f in frames(flat, step))
