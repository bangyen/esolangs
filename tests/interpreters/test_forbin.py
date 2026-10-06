"""Forbin's I/O, its loops and functions, and the state it steps through."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run
from tests.interpreters.forbin_support import run_program


def walk_until_halt_or_ancestor(machine: object, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor."""
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
        """A "0" byte is echoed and the program halts."""
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

    def test_wildcard_loop_in_an_expression_position_call(self) -> None:
        """``(*, 1)`` expands only the wildcard column in the recursive path too."""
        code = """
            f { for (i, j):((*, 1)) { out 0,1,0,0,0,0,i,j; } return 1; }
            main { r = (f 0); }
        """
        assert run_program(code) == "AC"

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
    """The step granularity a mutation survived, pinned by counting steps."""

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
        """A call pushes a frame rather than recursing inside one step."""
        code = "main {\n helper x { out 0,1,0,0,0,0,0,x; }\n helper 1;\n helper 0;\n}\n"
        steps, out, deepest = self._drive(code)
        assert out == "A@"
        assert steps == 7
        assert deepest == 2  # main, plus the frame each call pushes

    def test_an_iteration_loop_selects_the_wildcard_columns(self) -> None:
        """``*`` marks the columns to expand, and the test is ``==``."""
        code = (
            "main {\n any = 0;\n for i:(0, 0, 1) { for _:!i..i { any = 1; } }\n"
            " out 0,0,0,0,0,0,0,any;\n}\n"
        )
        steps, out, _ = self._drive(code)
        assert out == "\x01"
        assert steps == 11


class TestForbinAncestorHangDetection:
    """Infinite recursion, proven rather than waited out."""

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
        """``f !x`` alternates, so the second lap re-enters the first's state."""
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
        """The input cursor is in the key, and that is what keeps it sound."""
        code = (
            "f {\n a,b,c,d,e,g,h,i = (in 0);\n for _:!i..i { return 0; }\n f 0;\n}\n"
            "main { f 0; }\n"
        )
        assert self._verdict(code, "@\nA") is True

    def test_an_undecided_walk_raises_rather_than_claiming_a_halt(self) -> None:
        """Exhausting the bound is not a verdict, and must not read as one."""
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
    """What the cycle detector sees, checked without importing it."""

    def test_a_snapshot_distinguishes_the_states_it_must(self) -> None:
        """Every component of the snapshot has to move something."""
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
        """``""`` is a real value here, not a placeholder nobody reads."""
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
        # one frame pushed, for the anonymous function, named ""; the key
        # now holds the function itself, then visible bindings and input.
        assert len(keys) == 1
        assert keys[0][0].name == ""
        assert keys[0][2:] == (0, (), 0)

    def test_a_frame_outside_a_loop_reports_a_sentinel(self) -> None:
        """The two loop counters need a value meaning "not in a loop"."""
        from esolangs.interpreters.other.forbin import _Machine

        def frames(code: str, steps: int) -> tuple[object, ...]:
            machine = _Machine(code, ScriptedIO(""))
            for _ in range(steps):
                if machine.halted:
                    break
                machine.step()
            # Fields past the two loop counters (function, rows, names) are
            # the loop's own state; this test reads the first five.
            return tuple(frame[:5] for frame in machine.snapshot()[0])

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


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        # Wiki "Variable assignments": multiple assignment works as in Python.
        ("main { a, b = 1, 0; a, b = b, a; out 0,1,0,0,0,0,a,b; }", "A"),
        # Wiki "Iteration loops": (i, j):(*, *) loops over every combination.
        ("main { i, j = 0, 0; for (i, j):(*, *) { out 0,1,0,0,0,0,i,j; } }", "@ABC"),
        # Wiki: variables can be global.
        ("x = 1;\nmain { out 0,1,0,0,0,0,0,x; }", "A"),
        # Wiki "With arguments": (arg1, ..., argN @ {code}).
        ("main { f = (a, b @ { out 0,1,0,0,0,0,a,b; }); f 1, 0; }", "B"),
        # Wiki "Function literals": {code} 0; runs code.
        ("main { { out 0,1,0,0,0,0,0,1; } 0; }", "A"),
        # A definition in a loop body belongs to the enclosing function.
        ("main { i = 0; for i:0..0 { g { out 0,1,0,0,0,0,0,1; } } g 0; }", "A"),
    ],
)
def test_wiki_syntax_forms(program: str, expected: str) -> None:
    assert run_program(program) == expected
