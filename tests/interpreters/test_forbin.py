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


def walk_until_halt_or_ancestor(machine: object, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor.

    A local copy of the shared framed-machine walk, deliberately *not*
    imported: the mutation harness cannot inline the shared module, so a
    test that reached for it was dropped from the bundle whole -- taking
    with it every mutant that only these programs catch.  Driving the
    interpreter's own ``_Machine`` here keeps the class in the run.

    Each newly-pushed frame is compared against the frames beneath it via
    ``machine.frame_entry_key``.  A frame entering the same function, with
    the same bindings, at the same input position as an ancestor is about
    to replay what that ancestor is still in the middle of, so the
    recursion cannot terminate: returns ``False``.  Returns ``True`` when
    the machine halts first.

    ``limit`` bounds the walk in *pushes examined*; exhausting it raises
    :class:`TimeoutError` rather than returning a verdict, so a program the
    check cannot decide is never reported as halting.  ``steps`` is a
    second belt for a mutant that neither halts nor pushes -- without it
    such a mutant spins until the harness alarm rather than failing fast.
    """
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
        # A shallower frame at this index belongs to a call that has since
        # returned, so drop it rather than compare against a dead ancestor.
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
        """The whole message is asserted, position included.

        ``_fail`` appends ``at position {self.i}``, and that offset is the
        only reader of the parser's cursor at the point it gives up, so a
        substring match leaves both the wording and the position untested.
        """
        with pytest.raises(ValueError, match="expected") as caught:
            run_program("main { out 0,0,0,0,0,0,0 } extra")
        assert str(caught.value) == "expected '{' after function name at position 32"


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


class TestDiscardTarget:
    """``_`` as an assignment target evaluates the value and drops it."""

    def test_discard_in_a_paired_assignment(self) -> None:
        """The remaining name still takes the value opposite *its* position.

        Both targets are assigned by position, so the ``_`` consumes the
        first value and ``x`` the second rather than the first surviving
        into it.
        """
        code = "main { _, x = 1, 0; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x00"

        code = "main { x, _ = 1, 0; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x01"

    def test_discard_in_a_broadcast_assignment(self) -> None:
        """One value for several targets skips the ``_`` and fills the rest."""
        code = "main { _, x = 1; out 0,0,0,0,0,0,0,x; }"
        assert run_program(code) == "\x01"

    def test_discard_is_not_readable_afterwards(self) -> None:
        """``_`` is dropped rather than stored, so reading it is an error."""
        with pytest.raises(HaltError, match="undeclared identifier"):
            run_program("main { _ = 1; out 0,0,0,0,0,0,0,_; }")

    def test_every_binding_site_honours_the_discard(self) -> None:
        """Each of the four places a name is bound must skip ``_``.

        The sentinel is compared in four separate places -- broadcast
        assignment, paired assignment, the step machine's ``for`` row
        binder, and the recursive evaluator's row binder -- and a test
        that reaches only one of them leaves the other three free to stop
        honouring ``_`` unnoticed.  Each program below is the witness for
        exactly one site: breaking that site alone makes it print
        ``\x01`` instead of halting, and breaking any other leaves it
        halting.

        The last two run their loop inside an *expression-position* call,
        which is evaluated recursively rather than by pushing a frame --
        the only route to the recursive binder.
        """
        for code in (
            # broadcast assignment
            "main { _ = 1; out 0,0,0,0,0,0,0,_; }",
            # paired assignment, where the value comes by position
            "main { _, x = 1, 0; out 0,0,0,0,0,0,0,_; }",
            # the step machine's row binder, range and iteration spellings
            "main { for _:0..1 { } out 0,0,0,0,0,0,0,_; }",
            "main { for _:(0, 1) { } out 0,0,0,0,0,0,0,_; }",
            # the recursive binder, reached through an expression-position call
            "g { for _:0..1 { } return _; }\nmain { x = (g 0); }\n",
            "g { for _:(0, 1) { } return _; }\nmain { x = (g 0); }\n",
        ):
            with pytest.raises(HaltError) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value) == "undeclared identifier '_'"


class TestCallingANonFunction:
    """A call whose callee resolves to a bit rather than to a function.

    An undeclared name is rejected earlier, as an unknown identifier, so
    reaching the "not a function" check needs a callee that *does* resolve
    -- a local holding a bit -- rather than one that does not.
    """

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
        # The programs here settle in fifteen steps or fewer.  The cap is
        # headroom, not a timeout: a mutant that stops one halting should
        # fail this in microseconds, and at 20000 it burnt 5.7 seconds
        # apiece instead -- once per such mutant, over eleven hundred.
        while not machine.halted and steps < 200:
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

    def test_the_loop_body_cursor_advances_by_exactly_one(self) -> None:
        """``for_body_pos`` moves one statement at a time, both ways out.

        ``_step_for`` advances the cursor on two separate paths -- the one
        that pushes a frame for a statement-position call, and the one that
        runs the statement in place -- and each was invisible to a suite
        asserting only output.  Setting the cursor rather than incrementing
        it re-runs a statement forever; adding two skips one.

        The programs below put a call and a plain statement in the same
        loop body in both orders, so a cursor that lands wrong on either
        path shows up as a different step count, a different byte string,
        or a program that stops halting.
        """
        # A call first, then a statement: the pushing path's cursor.
        steps, out, deepest = self._drive(
            "g { out 0,1,0,0,0,0,0,1; }\nh { out 0,1,0,0,0,1,0,0; }\n"
            "main { for i:0..0 { g 0; h 0; } }\n"
        )
        assert (steps, out, deepest) == (10, "AD", 2)

        # A statement first, then a call: the in-place path's cursor.
        steps, out, deepest = self._drive(
            "g { out 0,1,0,0,0,0,0,1; }\n"
            "main { for i:0..1 { out 0,1,0,0,0,1,0,i; g 0; } }\n"
        )
        assert (steps, out, deepest) == (13, "DAEA", 2)

        # Two plain statements over two rows: the in-place path again, with
        # the row change in between.
        steps, out, deepest = self._drive(
            "main { for i:0..1 { out 0,1,0,0,0,0,0,i; out 0,1,0,0,0,0,1,i; } }"
        )
        assert (steps, out, deepest) == (9, "@BAC", 1)

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

    A whole-state cycle detector cannot catch a Forbin hang: a call that
    never returns pushes one frame per step and pops none, so the
    whole-machine snapshot grows forever and never repeats.  Every Forbin
    hang is in that unbounded-growth class, which is why this language had
    no hang test at all and leaned on the wall-clock backstop -- the one
    that deadlocks under ``pytest --cov`` (see ``docs/walls.md``).

    :func:`walk_until_halt_or_ancestor` is the narrower check that class
    allows: a frame entering the same function, with the same bindings, at
    the same input position as an ancestor is about to replay what that
    ancestor is still in the middle of.  What it keys on is the
    interpreter's own ``frame_entry_key``, which is what these tests pin.
    """

    @staticmethod
    def _verdict(code: str, stdin: str = "") -> bool:
        from esolangs.interpreters.other.forbin import _Machine

        return walk_until_halt_or_ancestor(_Machine(code, ScriptedIO(stdin)))

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

    def test_an_undecided_walk_raises_rather_than_claiming_a_halt(self) -> None:
        """Exhausting the bound is not a verdict, and must not read as one.

        A machine whose entry key never repeats is one the check cannot
        decide.  Returning ``True`` there would report a hanging program as
        halting, and -- because the walk ran to a generous bound first --
        would do it slowly: a mutant that defeats the early return took 4.5
        seconds to answer wrongly, once per mutant, which is what made a
        mutation run of this module crawl.
        """
        from esolangs.interpreters.other.forbin import _Machine

        class _NeverRepeats(_Machine):
            """Stands in for any mutant whose key stops repeating."""

            counter = 0

            def frame_entry_key(self, _frame: object) -> tuple[object, ...]:
                _NeverRepeats.counter += 1
                return ("unique", _NeverRepeats.counter)

        machine = _NeverRepeats("main {\n f {\n  f 0;\n }\n f 0;\n}\n", ScriptedIO(""))
        with pytest.raises(TimeoutError, match="undecided"):
            walk_until_halt_or_ancestor(machine)


class TestArgumentThreading:
    r"""Programs that notice ``_eval``'s arguments going astray.

    A mutation run left 216 survivors, and half of them replace one
    argument of ``_eval(node, frame, globals_, reader, depth)`` with
    ``None`` at one call site.  Such an edit is invisible unless something
    that *consumes* that argument is evaluated in that syntactic position:

        ``globals_``  a reference to a top-level function
        ``reader``    an ``in``
        ``frame``     a local variable
        ``depth``     a nested call, which increments it

    and the consuming construct has to sit **at** the position rather than
    be assigned to a local first -- reading a local forces ``frame``, not
    whatever filled it.  So each program below puts one forcing construct
    in one place a value can appear: a range bound, an iteration pattern,
    a call argument, an ``out`` argument, a ``!``, a return.
    """

    def test_a_call_returning_a_call(self) -> None:
        """``globals_`` and ``depth`` threaded through nested returns.

        ``f`` returns the result of calling ``one``, so the return value
        is evaluated in a frame one deeper than the call that produced it.
        """
        assert (
            run_program(
                "one { return 1; }\nf { return (one 0); }\n"
                "main {\n a = (f 0);\n out 0,1,0,0,0,0,0,a;\n}\n"
            )
            == "A"
        )

    def test_a_call_as_a_range_bound(self) -> None:
        """A ``for`` bound is a value, so it may itself be a call."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..(one 0) { g i; }\n}\n"
            )
            == "@A"
        )

    def test_a_call_in_a_nested_loop_bound(self) -> None:
        """The inner bound is re-evaluated on every row of the outer loop."""
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\none { return 1; }\n"
                "main {\n for i:0..1 {\n  for j:0..(one 0) { g j; }\n }\n}\n"
            )
            == "@A@A"
        )

    def test_a_call_opens_a_range_through_not(self) -> None:
        r"""``!`` is how a call reaches the *start* of a range.

        ``for i:(one 0)..1`` does not parse -- a leading ``(`` is claimed
        by the iteration-list branch of ``_for_spec`` -- but ``!`` is read
        by ``_value``, where ``(`` builds a call.  So ``!(zero 0)`` both
        parses and evaluates a call in start position, which no other
        program here reaches.  The same route carries an ``in``.
        """
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
        """The call twins of the ``in`` cases: argument, pattern, multi-RHS.

        A call and an ``in`` force different arguments through the same
        slot -- ``globals_`` and ``depth`` for the call, ``reader`` for the
        input -- so each position needs both.
        """
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
        """``in`` at the position, not assigned to a local first.

        Binding the byte to a local and using the local forces ``frame``;
        only an ``in`` sitting in the slot forces the bit reader through
        it.
        """
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
        """``_lookup`` walks ``frame.parent`` until it finds the name."""
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
        """``*`` doubles the row count, and the columns are independent.

        One wildcard cannot tell a product over the wildcard *count* from
        a product over a fixed repeat, nor the order the expanded columns
        are filled in; two can.
        """
        assert (
            run_program(
                "g x { out 0,1,0,0,0,0,0,x; }\n"
                "main {\n for (i,j):((*,*)) { g i; g j; }\n}\n"
            )
            == "@@@AA@AA"
        )

    def test_arity_mismatches_are_tolerated(self) -> None:
        """Extra arguments are dropped and missing ones default to zero.

        The zips that bind parameters and loop variables are deliberately
        not ``strict``; a mismatch is a documented case, not an error.
        """
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
        """``_`` is the discard name, so it must not enter the frame."""
        with pytest.raises(HaltError, match="undeclared identifier '_'"):
            run(
                "main {\n for _:0..0 { out 0,1,0,0,0,0,0,0; }\n"
                " out 0,1,0,0,0,0,0,_;\n}\n",
                ScriptedIO(""),
            )


class TestThreadedResources:
    """Every evaluator argument, loaded in every position that forwards it.

    ``_eval``/``_exec_stmt``/``_call`` thread four things through every
    recursive step -- the frame, the globals, the bit reader, and the call
    depth -- and a suite whose programs never *use* one of them in a given
    position cannot notice that position forwarding the wrong thing.  Each
    program below puts a load on exactly one resource:

    ``(in 0)`` needs the reader, a bare local name needs the frame, a call
    needs the globals, and a call nested inside an expression-position
    call needs the depth, which is read once as ``depth + 1``.

    The positions matter as much as the loads.  A loop bound, a call
    argument, an assignment right-hand side, and an iteration pattern are
    four separate forwarding sites, and the whole set is duplicated between
    the step machine and the recursive evaluator an expression-position
    call runs in.
    """

    def test_the_reader_reaches_every_position_that_can_read(self) -> None:
        """``(in 0)`` in each spot that forwards the reader.

        ``in`` yields one bit, most significant first, so the stdin byte
        here is ``\xff`` -- a leading 1.  That matters: a leading 0 would
        make the read indistinguishable from an unset variable, and the
        test would pass against a reader that was never consulted.
        """
        assert (
            run_program(
                "main { for i:0..(in 0) { out 0,1,0,0,0,0,0,i; } }", "\xff"
            )
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
        # inside an expression-position call, which runs recursively
        assert (
            run_program(
                "g { x = (in 0); return x; }\n"
                "main { y = (g 0); out 0,1,0,0,0,0,0,y; }\n",
                "\xff",
            )
            == "A"
        )

    def test_the_frame_reaches_every_position_that_reads_a_local(self) -> None:
        """A bare local name in each spot that forwards the frame."""
        assert run_program("main { n = 1; for i:0..n { out 0,1,0,0,0,0,0,i; } }") == "@A"
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
        """A call in each spot that forwards the function table."""
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

    def test_a_call_nested_in_a_call_is_what_reads_the_depth(self) -> None:
        """``depth`` is forwarded everywhere and read once, as ``depth + 1``.

        That single read is in ``_call``, so it needs a call reached from
        *inside* another call's recursive evaluation -- one level of
        expression-position nesting is not enough to notice a depth that
        arrived as something other than a number.
        """
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


class TestPairedLengthsAreNotChecked:
    """Forbin pairs by position and stops at the shorter side.

    Five ``zip`` calls bind names to values -- parameters to arguments
    (twice, once per call path), targets to right-hand sides, and loop
    variables to a row (twice again).  Each passes ``strict=False``, and
    tightening any one of them to ``strict=True`` turns a length mismatch
    from a tolerated program into a crash.  The suite ran no program whose
    two sides differed, so every one of those edits was invisible.
    """

    def test_arity_mismatch_is_tolerated_on_both_call_paths(self) -> None:
        """A statement call and an expression call bind arguments separately."""
        # statement-position call: too few arguments, then too many
        assert run_program("g a, b { out 0,1,0,0,0,0,0,a; }\nmain { g 1; }\n") == "A"
        assert run_program("g a { out 0,1,0,0,0,0,0,a; }\nmain { g 1, 0; }\n") == "A"
        # expression-position call, which binds through the other zip
        assert (
            run_program(
                "g a { return a; }\nmain { x = (g 1, 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "A"
        )

    def test_an_assignment_may_have_uneven_sides(self) -> None:
        """Extra targets stay unset and extra values are dropped."""
        assert run_program("main { a, b = 1, 0, 1; out 0,1,0,0,0,0,0,a; }") == "A"
        assert run_program("main { a, b, c = 1, 0; out 0,1,0,0,0,0,0,a; }") == "A"

    def test_a_row_narrower_than_its_variable_list_is_tolerated(self) -> None:
        """Two loop variables over one-wide rows leave the second unbound."""
        assert (
            run_program("main { for (i,j):((0),(1)) { out 0,1,0,0,0,0,0,i; } }") == "@A"
        )
        # and again through the recursive evaluator
        assert (
            run_program(
                "g { for (i,j):((0),(1)) { return 0; } return 0; }\n"
                "main { x = (g 0); out 0,1,0,0,0,0,0,x; }\n"
            )
            == "@"
        )


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
            with pytest.raises(ValueError) as caught:
                run(code, ScriptedIO(""))
            assert str(caught.value) == (
                f"assignment target must be a variable at position {position}"
            )

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


class TestSnapshotWithoutTheCycleDetector:
    """What the cycle detector sees, checked without importing it.

    ``snapshot`` is otherwise exercised only through the shared runner,
    which the bundled build used for mutation testing does not inline --
    so those tests are correctly dropped there, and the method then reads
    as wholly untested.  That is a property of the harness rather than of
    the suite.  Driving the machine directly covers the same ground with
    nothing to drop.
    """

    def test_a_snapshot_distinguishes_the_states_it_must(self) -> None:
        """Every component of the snapshot has to move something.

        The cycle detector only sees what ``snapshot`` reports, and the
        tests that exercise it go through the shared runner, which the
        bundled mutation build does not inline -- so they are dropped and
        the whole method reads as untested.  These assertions need only
        the interpreter: they drive two machines directly and compare.

        Each pair below differs in exactly one field, so a snapshot that
        stopped reporting that field would collapse the two together.
        """
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

        # the same machine at the same point is the same state
        assert at(prog, 2) == at(prog, 2)
        # the statement cursor advances
        assert at(prog, 1) != at(prog, 2)
        # a different binding is a different state, at the same cursor
        assert at("main {\n a = 0;\n}\n", 1) != at("main {\n a = 1;\n}\n", 1)
        # so is a different loop row, and a different position within a body
        assert at(prog, 3) != at(prog, 4)
        # frames are part of it: inside a call is not the same as before it
        nested = "f { out 0,1,0,0,0,0,0,1; }\nmain {\n f 0;\n}\n"
        assert at(nested, 1) != at(nested, 2)
        # and so is the input cursor, with everything else equal
        read = "main {\n a,b,c,d,e,f,g,h = (in 0);\n}\n"
        assert at(read, 0, "HH") != at(read, 1, "HH")

    def test_a_frame_outside_a_loop_reports_a_sentinel(self) -> None:
        """The two loop counters need a value meaning "not in a loop".

        A frame that is not running a ``for`` has no row index and no
        position within a body, and the snapshot reports ``-1`` for both.
        The choice matters: the sentinel has to be a number no real
        counter can take, or a frame between loops would compare equal to
        one part-way through iterating.  ``for_ind`` reaches 1 on the
        second row, so a sentinel of ``+1`` collides with it, and reading
        the two the other way round -- sentinel while looping, counter
        while not -- swaps every frame in the tuple.
        """
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

        # a frame that has not entered its loop yet reports the sentinel
        assert frames(looping, 0) == (("main", 0, (), -1, -1),)
        # once iterating, both counters are real and start at zero
        assert frames(looping, 1) == (("main", 0, (), 0, 0),)
        # the row index counts up, so it takes the values a sentinel must avoid
        assert frames(looping, 2) == (("main", 0, (("i", "0"),), 1, 0),)
        assert frames(looping, 6) == (("main", 0, (("i", "1"),), 2, 0),)
        # a called frame is not looping, so it carries the sentinel
        assert frames(looping, 3)[1] == ("g", 0, (("x", "0"),), -1, -1)
        # and a program with no loop at all reports it for every step
        for step in range(4):
            assert all(f[3] == -1 and f[4] == -1 for f in frames(flat, step))
