"""Tests for the Caballo interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.caballo.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import Seeded
from tests.interpreters.contract import CycleContract, EmptyProgramContract

#: The wiki's pairing function, as printed and with its last ``p`` dropped.
PAIRING = "q2[d2ii2](1+di-)pi q3[d32[d2ii2](1+di-)3](1+di-)pp"
PAIRING_REPAIRED = PAIRING[:-1]


def _run(code: str, stdin: str = "", seed: int | None = None) -> str:
    io = ScriptedIO(stdin)
    run(code, io, None if seed is None else Seeded(seed))
    return io.getvalue()


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


@pytest.mark.parametrize(("stdin", "out"), [("0", "[]"), ("5", "")])
def test_the_wiki_zero_test_keeps_only_a_zero_top(stdin: str, out: str) -> None:
    """On 0 the ``d`` fails; otherwise the two branches cancel."""
    assert _run("(1+di-)", stdin) == out


@pytest.mark.parametrize(("stdin", "out"), [("0", "[2]"), ("1", "[1,1]")])
def test_the_wiki_conditional_runs_one_branch(stdin: str, out: str) -> None:
    assert _run("(diqi+(1+di-)qii)", stdin) == out


def test_the_wiki_addition_adds_the_top_two() -> None:
    assert _run("[d2i2] (1+di-)p", "2 1") == "[3]"


def test_the_wiki_lookup_table_separates_entries_with_bars() -> None:
    assert _run("((1+di-)qi|d(1+di-)iqii)", "1") == "[2,1]"


def test_the_wiki_pairing_pops_its_result_with_pp() -> None:
    """``(x, y) -> (2x+1)·2**y`` needs one ``p``; the printed ``pp`` empties it."""
    assert _run(PAIRING, "1 2") == "[]"
    assert _run(PAIRING_REPAIRED, "1 2") == "[12]"


def test_decrement_drops_a_zero_top_above_other_elements() -> None:
    assert _run("d", "0 4") == ""


def test_bottom_zeros_vanish_and_swaps_reach_them() -> None:
    assert _run("q", "") == "[]"
    assert _run("3", "7") == "[0,0,7]"


def test_equal_results_add_their_weights() -> None:
    machine = _machine("(1+1)")
    while not machine.halted:
        machine.step()
    assert machine.memory == [((), 2)]


def test_negative_weights_are_discarded_at_the_end() -> None:
    assert _run("-", "3") == ""


def test_zero_empties_the_mapping() -> None:
    assert _run("0i", "3") == ""


def test_the_output_is_drawn_by_weight() -> None:
    # Weights 1 and 2: a seeded draw is reproducible, and both stacks occur.
    draws = {_run("(1+qi+qi)", "", seed) for seed in range(20)}
    assert draws == {"[]", "[1]"}
    assert _run("(1+qi+qi)", "", 3) == _run("(1+qi+qi)", "", 3)


class _Fixed:
    """A draw source that always answers ``value``."""

    def __init__(self, value: int) -> None:
        self.value = value

    def randbelow(self, upper: int) -> int:
        assert self.value < upper
        return self.value


def test_a_ticket_equal_to_the_first_weight_picks_the_second_stack() -> None:
    """Weights 1 and 2 cover tickets 0 | 1, 2; ticket 1 belongs to ``[1]``."""
    outputs = []
    for ticket in range(3):
        io = ScriptedIO("")
        run("(1+qi+qi)", io, _Fixed(ticket))
        outputs.append(io.getvalue())
    assert outputs == ["[]", "[1]", "[1]"]


def test_the_branching_halt_flag_is_the_done_flag() -> None:
    """With no input read, ``done`` is True while the progress count is 0."""
    machine = _machine("1")
    assert not machine.branching_halted(machine.snapshot())
    while not machine.halted:
        machine.step()
    assert machine.branching_halted(machine.snapshot())


def test_input_must_be_naturals() -> None:
    with pytest.raises(HaltError, match="not a natural number"):
        _run("1", "-1")


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("(1+di", "'\\(' is never closed"),
        ("[d", "'\\[' is never closed"),
        ("1)", "has no opening bracket"),
        ("x", "'x' is not a Caballo command"),
    ],
)
def test_malformed_programs_are_refused(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = _run
    machine = _machine
    # The empty program is the identity: it prints the empty input stack.
    empty_output = "[]"
    halting_program = "p"
    # ``-`` alternates the mapping's sign, so ``[-]`` never empties it and
    # its sum flips between the input and nothing: the state repeats.
    looping_program = "[-]"
