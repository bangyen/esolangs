"""Forbin's I/O, its loops and functions, and the state it steps through.

The parser's refusals are in test_forbin_errors, and argument threading in
test_forbin_threading.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
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
