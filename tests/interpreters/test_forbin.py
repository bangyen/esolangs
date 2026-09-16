"""Forbin's I/O, its loops and functions, and the state it steps through.

The parser's refusals are in test_forbin_errors, and argument threading in
test_forbin_threading.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.interpreters.forbin_support import run_program


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
    # pylint: disable=duplicate-code
    # The overlap with the shared module's walk is the point, not an
    # oversight: see the docstring above.  Importing it instead would cut
    # this file from the mutation bundle whole, so the copy stays and the
    # similarity check is told so here rather than left to fail in CI.
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
        value-row branch of ``_exec_stmt``'s own ``for`` handling).
        """
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
    that deadlocks under ``pytest --cov`` (see ``the limitations ledger``).

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

        ``the limitations ledger`` notes that a genuinely changing argument would
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

    def test_an_anonymous_function_is_named_by_the_empty_string(self) -> None:
        """``""`` is a real value here, not a placeholder nobody reads.

        A function literal has no name, and the parser spells that as the
        empty string.  Nothing *prints* the name, so a mutant storing
        ``None`` or some other filler instead left every program's output
        untouched -- but ``frame_entry_key`` carries the name, which is
        what the hang check compares ancestors on, so the wrong filler
        changes which recursions are provably non-terminating.

        ``snapshot()`` cannot be used for this: it holds each function's
        ``repr``, which carries a memory address and differs between runs.
        ``frame_entry_key`` records the name itself and is stable.
        """
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
        # one frame pushed, for the anonymous function, named ""
        assert keys == [("", (), 0)]

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
