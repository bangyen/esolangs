"""Execution tests for the Unlambda interpreter."""

import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.unlambda import (
    _advance,
    _App,
    _Machine,
    _parse,
    _Promise,
    run,
)
from tests.interpreters.runner import run_program

#: The wiki's Hello world: a left-nested chain of prints, newline first.
#: Spelled from its atoms rather than by hand, because ``n`` atoms need
#: exactly ``n - 1`` backticks and miscounting them is a parse error.
_HELLO_ATOMS = ["r", *(f".{char}" for char in "Hello, world"), "i"]
HELLO = "`" * (len(_HELLO_ATOMS) - 1) + "".join(_HELLO_ATOMS)


def test_the_reference_greeting_prints() -> None:
    assert run_program(run, HELLO) == "\nHello, world"


def test_the_combinators() -> None:
    assert run_program(run, "`i`.Xi") == "X"
    assert run_program(run, "``k`.Ai`.Bi") == "AB"  # A then B, value is A's
    assert run_program(run, "```s.A.Bi") == "AB"
    assert run_program(run, "`v`.Ai") == "A"  # the argument still evaluates


def test_d_delays_and_applying_the_promise_forces_it() -> None:
    assert run_program(run, "`d`.Ai") == ""  # never forced
    assert run_program(run, "``d`.Aii") == "A"  # forced by the application


def test_a_read_and_a_test_on_the_character() -> None:
    program = "`@`d````?0i`d`.zivi"
    assert run_program(run, program, "0\n") == "z"
    assert run_program(run, program, "1\n") == ""


def test_the_pipe_hands_over_the_character_read() -> None:
    assert run_program(run, "`@`d``|ii", "Q\n") == "Q"


def test_the_pipe_before_any_read_is_v() -> None:
    """The spec's no-character branch, which ``@`` cannot reach here."""
    assert run_program(run, "``|ii") == ""


def test_an_empty_line_reads_as_a_newline() -> None:
    assert run_program(run, "`@`d``|ii", "\n") == "\n"


#: ``\b. ((b (`d `.Xi)) v)``: ``k`` keeps the promise and ``v`` swallows it,
#: so forcing the survivor with ``i`` prints X only on ``@``'s success branch.
#: ``v`` absorbs every argument, so the failure arm cannot run anything of its
#: own -- silence is what it looks like, and that is the language's, not this
#: interpreter's.
_ON_READ = "``@``s``si`k`d`.Xi`kvi"


def test_a_read_at_end_of_input_takes_the_spec_branch() -> None:
    """``@`` hands its argument ``v`` at EOF rather than letting it escape.

    ``suppress_eof=False`` so a leaked ``EOFError`` fails the test rather
    than being swallowed into the same empty output the spec branch gives.
    """
    assert run_program(run, _ON_READ, "0\n", suppress_eof=False) == "X"
    assert run_program(run, _ON_READ, "", suppress_eof=False) == ""


def test_the_character_survives_a_read_that_found_nothing() -> None:
    """A read at EOF preserves the character previously read."""
    assert run_program(run, "``k`@i``k`@i``|ii", "Q", suppress_eof=False) == "Q"


def test_e_ends_the_run() -> None:
    assert run_program(run, "``k`.Ai`e.B") == "A"


def test_call_cc_returns_a_usable_continuation() -> None:
    assert run_program(run, "`.A`ci") == "A"


def test_a_continuation_abandons_the_rest_of_its_caller() -> None:
    """``c``'s argument applies the continuation, so its own tail is dropped."""
    # ``s i (k v)`` applied to the continuation applies it to v, and the
    # print after that application never runs.
    assert run_program(run, "``c``si`kv.A") == ""


def test_a_comment_runs_to_the_end_of_its_line() -> None:
    assert run_program(run, "#skipped\n`.Ai") == "A"


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("", "cannot be empty"),
        ("`i", "missing one of its two terms"),
        ("ii", "spells a second one"),
        ("`i.", "has no character after it"),
        ("z", "not an Unlambda command"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)


def test_the_parser_is_iterative_over_a_long_chain() -> None:
    """A deep application chain must not exhaust the recursion limit."""
    depth = 5000
    term = _parse("`" * depth + "i" * (depth + 1))
    assert isinstance(term, _App)


def test_the_continuation_is_the_stack_the_vm_shows() -> None:
    machine = _Machine("`.A`.Bi", ScriptedIO(""))
    machine.step()
    assert machine.stack  # a frame is waiting on the argument
    while not machine.halted:
        machine.step()
    assert not machine.stack


def test_stepping_past_the_halt_is_a_no_op() -> None:
    machine = _Machine("`.Ai", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    before = machine.snapshot()
    machine.step()
    assert machine.snapshot() == before


def test_d_applied_as_a_value_promises_what_it_was_given() -> None:
    """``d`` delays whatever is *written* after it, so reaching it as a plain
    function needs a combinator to hand it an already-evaluated argument.
    ``c`` is the one that can: it applies ``d`` to the continuation, and the
    answer is a promise of that value rather than of an unevaluated term."""
    machine = _Machine("`cd", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert isinstance(machine.state[0].value, _Promise)
    # Applying that promise forces it, and the continuation answers ``i``.
    assert run_program(run, "```cdii") == ""


def test_stepping_a_finished_machine_changes_nothing() -> None:
    machine = _Machine("`.Ai", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.state[3] is True
    assert _advance(machine.state) == (machine.state, None)
