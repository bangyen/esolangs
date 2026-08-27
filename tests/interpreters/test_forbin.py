"""Unit tests for the Forbin interpreter.

Covers the bit ``in``/``out`` I/O, the iteration and range for-loops (ranges
double as if-statements), the NOT operator, function calls and recursion,
and the documented error conventions.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


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
        # 'A' is 0b01000001
        code = "main { a,b,c,d,e,f,g,h = (in 0); out a,b,c,d,e,f,g,h; }"
        assert run_program(code, "A") == "A"

    def test_in_running_out_raises_eof(self) -> None:
        code = "main { a,b,c,d,e,f,g,h = (in 0); }"
        with pytest.raises(EOFError):
            run(code, ScriptedIO(""))

    def test_truth_machine_zero(self) -> None:
        """A "0" byte is echoed and the program halts.

        Forbin is byte-oriented, so the machine echoes the input character
        and the range for-loop doubles as the if: ``!h..h`` is empty for
        '0' (low bit clear) and entered for '1', where ``loop`` prints '1'
        forever.  Only the terminating branch is exercised.
        """
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
        # 0..0 runs once (i=0), 0..1 runs twice (i=0,1)
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
        # for _:!c..c runs the body iff c is 1 (twice, since 0..1 iterates)
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
        """An expression-position call (``(f 0)``) natively recurses through
        ``_run``/``_exec_stmt``, which has its own ``for`` handling separate
        from ``_Machine.step()``'s frame-stack version -- this exercises the
        iteration (non-range) loop and wildcard-pattern expansion there.
        """
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
        """Same as above, but the pattern has no wildcard (the plain
        value-row branch of ``_exec_stmt``'s own ``for`` handling)."""
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
        """Unpassed parameters are set to 0 (per the wiki)."""
        code = """
            main {
              f a, b { out 0,0,0,0,0,0,0,b; }
              r = (f 1);
            }
        """
        assert run_program(code) == "\x00"

    def test_bare_block_is_function_literal(self) -> None:
        """A bare {code} block is a function literal in value position."""
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
        # loop is defined after main but still callable
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
        # input '0' (h=0): no recursion
        assert run_program(code, "0") == "0"

    def test_function_as_argument(self) -> None:
        # the wiki's eq helper, called via a passed function
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
        with pytest.raises(ValueError, match="expected"):
            run_program("main { out 0,0,0,0,0,0,0 } extra")


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
        with pytest.raises(ValueError, match="unterminated"):
            run_program("main {")

    def test_assignment_target_must_be_a_variable(self) -> None:
        with pytest.raises(ValueError, match="target must be a variable"):
            run_program("main { (f 1) = 2; }")
        with pytest.raises(ValueError, match="target must be a variable"):
            run_program("main { a, !b = 0, 1; }")

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

    def test_multi_assignment(self) -> None:
        code = "main { a, b = 1, 0; out 0,0,0,0,0,0,0,a; out 0,0,0,0,0,0,0,b; }"
        assert run_program(code) == "\x01\x00"


class TestStepMachine:
    def test_main_with_parameters_defaults_to_zero(self) -> None:
        # main's own parameters are set to 0 (per the wiki), same as any
        # other function's unpassed arguments
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
        machine.step()  # stepping a halted machine is a no-op
        assert machine.halted

    def test_statement_call_inside_a_for_loop_body_pushes_a_frame(self) -> None:
        # a statement-position call inside a for-loop body is stepped
        # through _step_for's own frame-push, not _exec_stmt's
        code = """
            helper { out 0,1,0,0,1,0,0,0; }
            main { for _:0..0 { helper 0; } }
        """
        assert run_program(code) == "H"

    def test_bare_return_at_top_level_pops_the_frame(self) -> None:
        # a return statement run directly by step() (not through a pushed
        # frame) still pops the current frame via its own got-is-not-None path
        code = "main { return 1; out 0,0,0,0,0,0,0,1; }"
        assert run_program(code) == ""

    def test_return_inside_a_for_loop_body_pops_the_frame(self) -> None:
        # a return statement inside a for-loop body, run through
        # _step_for's own statement handling, also pops the frame
        code = "main { for _:0..0 { return 1; } out 0,0,0,0,0,0,0,1; }"
        assert run_program(code) == ""

    def test_return_inside_a_non_range_for_loop_in_a_nested_call(self) -> None:
        # a return inside a for-loop body, reached through the recursive
        # _run/_exec_stmt/_exec_block path (an expression-position call),
        # propagates out through _exec_block's own got-is-not-None return
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
        """A ``for`` bound has to be a number, not a function."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_program("f { return 0; }\nmain { for _:f..1 { return 0; } return 0; }")

    def test_non_bit_out_argument_halts(self) -> None:
        """``out`` takes bits, matching the rule ``!`` already enforces."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_program("f { return 0; }\nmain { out f,0,1,1,0,0,0,1; return 0; }")


class TestForbinMutationSurvivors:
    """The step granularity a mutation survived, pinned by counting steps.

    Mutation testing (mutmut against a ``bundle_one`` build of this module)
    reported thirteen changes no test noticed, and every one of them left
    the output byte-for-byte identical while changing *how many* ``step()``
    calls the program took.  That is exactly the module's central claim --
    ``step()`` is interruptible between statements, between a ``for``
    loop's rows, and between statement-position calls -- and the suite
    asserted only what each program printed, so a mutant that collapsed the
    frame-stack path back into the recursive evaluator was invisible.

    Each was confirmed by loading the mutant and the original side by side
    and diffing their behaviour.
    """

    @staticmethod
    def _drive(code: str, stdin: str = "") -> tuple[int, str, int]:
        """Run ``code`` to a halt; return (steps, output, deepest frame stack)."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine

        machine = _Machine(code, ScriptedIO(stdin))
        steps, deepest = 0, 0
        while not machine.halted and steps < 20000:
            machine.step()
            steps += 1
            deepest = max(deepest, len(machine.frames))
        assert machine.halted
        return steps, machine.io.getvalue(), deepest

    def test_a_statement_position_call_is_its_own_step(self) -> None:
        """A call pushes a frame rather than recursing inside one step.

        ``_start_statement_call`` returns the pushed frame, and a mutant
        that returned ``None`` instead ran the call natively through
        ``_exec_stmt``: same two bytes out, seven steps down to three, and
        the stack never reached the depth a pushed frame gives it.
        """
        code = "main {\n helper x { out 0,1,0,0,0,0,0,x; }\n helper 1;\n helper 0;\n}\n"
        steps, out, deepest = self._drive(code)
        assert out == "A@"
        assert steps == 7
        assert deepest == 2  # main, plus the frame each call pushes

    def test_a_for_loop_steps_once_per_row(self) -> None:
        """The loop yields between rows instead of running to completion.

        A mutant of ``_Machine.step`` ran each loop out inside one step:
        every program still printed the right bytes, in half the steps.
        """
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

    def test_an_iteration_loop_selects_the_wildcard_columns(self) -> None:
        """``*`` marks the columns to expand, and the test is ``==``.

        ``_for_rows`` collects the wildcard positions with ``p[0] == "*"``.
        Read as ``!=`` it expanded every *non*-wildcard column instead, and
        the loop still reached the same answer -- over six more rows.
        """
        code = (
            "main {\n any = 0;\n for i:(0, 0, 1) { for _:!i..i { any = 1; } }\n"
            " out 0,0,0,0,0,0,0,any;\n}\n"
        )
        steps, out, _ = self._drive(code)
        assert out == "\x01"
        assert steps == 11


class TestForbinAncestorHangDetection:
    """Infinite recursion, proven rather than waited out.

    ``run_until_halt_or_cycle`` cannot catch a Forbin hang: a call that
    never returns pushes one frame per step and pops none, so the
    whole-machine snapshot grows forever and never repeats.  Every Forbin
    hang is in that unbounded-growth class, which is why this language had
    no hang test at all and leaned on the wall-clock backstop -- the one
    that deadlocks under ``pytest --cov`` (see ``docs/walls.md``).

    ``run_until_halt_or_ancestor`` is the narrower check that class allows:
    a frame entering the same function, with the same bindings, at the same
    input position as an ancestor is about to replay what that ancestor is
    still in the middle of.
    """

    @staticmethod
    def _verdict(code: str, stdin: str = "") -> bool:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.forbin import _Machine
        from esolangs.vm import run_until_halt_or_ancestor

        return run_until_halt_or_ancestor(_Machine(code, ScriptedIO(stdin)))

    def test_an_unconditional_self_call_is_a_proven_hang(self) -> None:
        """``f`` calls itself with nothing changed, so it never returns."""
        assert self._verdict("main {\n f {\n  f 0;\n }\n f 0;\n}\n") is False

    def test_mutual_recursion_is_a_proven_hang(self) -> None:
        """The ancestor need not be the same function, only the same state."""
        assert self._verdict("a { b 0; }\nb { a 0; }\nmain { a 0; }\n") is False

    def test_a_flipping_argument_still_repeats(self) -> None:
        """``f !x`` alternates, so the second lap re-enters the first's state.

        ``docs/walls.md`` notes that a genuinely changing argument would
        slip through.  Forbin's only datatype is bits, so an argument that
        changes still has to come back around, and the key repeats within
        two frames.
        """
        assert self._verdict("main {\n f x {\n  f !x;\n }\n f 0;\n}\n") is False

    def test_a_terminating_program_is_not_flagged(self) -> None:
        """The ordinary programs the suite already runs must stay unflagged."""
        assert self._verdict("main {\n h x { out 0,1,0,0,0,0,0,x; }\n h 1;\n h 0;\n}\n")
        assert self._verdict(
            "main {\n g x {\n  for _:!x..x { return 0; }\n  g 1;\n }\n g 0;\n}\n"
        )

    def test_the_same_helper_called_twice_is_not_recursion(self) -> None:
        """Two sequential calls share a key but neither is the other's ancestor."""
        assert self._verdict("main {\n h x { out 0,1,0,0,0,0,0,x; }\n h 1;\n h 1;\n}\n")

    def test_recursion_waiting_on_input_is_not_a_hang(self) -> None:
        """The input cursor is in the key, and that is what keeps it sound.

        This function re-enters with identical bindings every lap -- its
        base case depends on a byte it has not read yet.  Keyed on bindings
        alone it is called a hang while it is one read from returning; the
        ``'@'`` lap recurses and the ``'A'`` lap returns.
        """
        code = (
            "f {\n a,b,c,d,e,g,h,i = (in 0);\n for _:!i..i { return 0; }\n f 0;\n}\n"
            "main { f 0; }\n"
        )
        assert self._verdict(code, "@\nA") is True
