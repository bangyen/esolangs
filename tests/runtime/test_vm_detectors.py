"""The five hang detectors."""

import pytest

from esolangs.languages.brainfuck.interpreter import _Machine as Brainfuck
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import (
    make_vm,
    run_until_halt,
    run_until_halt_or_all_branches_cycle,
    run_until_halt_or_ancestor,
    run_until_halt_or_cycle,
    run_until_halt_or_growth,
    run_until_halt_or_value_growth,
)
from tests.support.reference import REFERENCE


def _bf(code: str, stdin: str = "") -> Brainfuck:
    return Brainfuck(code, ScriptedIO(stdin))


class TestRunUntilHaltOrCycle:
    def test_a_machine_already_halted_is_reported_as_halting(self) -> None:
        """The loop is never entered, and the answer is still ``True``."""
        vm = make_vm(REFERENCE, "++")
        run_until_halt(vm)
        assert vm.halted
        assert run_until_halt_or_cycle(vm) is True


class TestTheDetectorsTakeAVM:
    """Every detector accepts what ``make_vm`` returns, not just a ``_Machine``."""

    def test_the_growth_detector_takes_a_vm(self) -> None:
        """``+[>]`` walks off onto a zero; ``+[>+]`` grows a cell a lap."""
        assert run_until_halt_or_growth(make_vm(REFERENCE, "+[>]")) is True
        assert run_until_halt_or_growth(make_vm(REFERENCE, "+[>+]")) is False

    def test_the_value_growth_detector_refuses_a_bounded_language(self) -> None:
        """Brainfuck's cells wrap, so a climb there is a cycle, not a proof."""
        with pytest.raises(TypeError, match="affine machine"):
            run_until_halt_or_value_growth(make_vm(REFERENCE, "+[>+]"))

    def test_an_object_that_is_neither_raises_type_error(self) -> None:
        """The unwrap looks one level deep, and no further."""
        with pytest.raises(TypeError, match="steppable with a snapshot"):
            run_until_halt_or_cycle(object())

    def test_a_zero_branch_cap_stops_before_exploring(self) -> None:
        """A zero cap stops before exploring the initial branching state."""

        class _Unbounded:
            def branching_snapshot(self) -> int:
                return 0

            def branching_halted(self, _state: int) -> bool:
                return False

            def branching_successors(self, state: int, _limit: int) -> list[int]:
                return [state + 1]

        with pytest.raises(TimeoutError, match="branching states"):
            run_until_halt_or_all_branches_cycle(
                _Unbounded(),
                limit=0,
            )


@pytest.mark.parametrize(("program", "limit"), [("", 0), ("+", 1)])
def test_growth_detector_accepts_halt_at_step_limit(program: str, limit: int) -> None:
    assert run_until_halt_or_growth(make_vm("Brainfuck", program), limit) is True


@pytest.mark.parametrize(
    "detector",
    [
        run_until_halt_or_cycle,
        run_until_halt_or_all_branches_cycle,
        run_until_halt_or_growth,
        run_until_halt_or_value_growth,
        run_until_halt,
        run_until_halt_or_ancestor,
    ],
)
@pytest.mark.parametrize("limit", [float("nan"), float("inf"), 1.5, "3", True, -1])
def test_invalid_limit_is_refused_before_machine_acquisition(detector, limit) -> None:
    from esolangs.exceptions import ArgumentError

    with pytest.raises(ArgumentError, match="limit"):
        detector(object(), limit=limit)


class _Climber:
    """Never halts: each step walks onto a fresh cell, pushes a frame with
    the same entry, and adds one to a value -- a hang all three proofs see."""

    halted = False
    ip = 0

    def __init__(self) -> None:
        self.n = 0

    def step(self) -> None:
        self.n += 1

    @property
    def ptr(self) -> int:
        return self.n

    @property
    def tape(self) -> tuple[int, ...]:
        return (1,) + (0,) * self.n

    def input_position(self) -> int:
        return 0

    @property
    def frames(self) -> list[int]:
        return list(range(self.n + 1))

    def frame_entry_key(self, _frame: object) -> int:
        return 0

    key = 0
    clamp_slack = None

    @property
    def values(self) -> tuple[int, ...]:
        return (self.n,)


class _RandomClimber(_Climber):
    """The same machine, declaring a draw it could branch on."""

    def branching_snapshot(self) -> int:
        return self.n

    def branching_halted(self, _state: object) -> bool:
        return False

    def branching_successors(self, state: object, _limit: int) -> list[object]:
        return [state]


_PROOFS = [
    run_until_halt_or_ancestor,
    run_until_halt_or_growth,
    run_until_halt_or_value_growth,
]


@pytest.mark.parametrize("detector", _PROOFS)
def test_a_lap_proof_refuses_a_random_machine(detector) -> None:
    """A draw can change the next lap, which every lap proof assumes away."""
    assert detector(_Climber()) is False  # control: the deterministic hang is proved
    with pytest.raises(TypeError, match="random machines"):
        detector(_RandomClimber())
