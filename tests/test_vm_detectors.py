"""The five hang detectors."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine as Brainfuck
from esolangs.vm import (
    make_vm,
    run_until_halt,
    run_until_halt_or_all_branches_cycle,
    run_until_halt_or_cycle,
    run_until_halt_or_growth,
    run_until_halt_or_value_growth,
)


def _bf(code: str, stdin: str = "") -> Brainfuck:
    return Brainfuck(code, ScriptedIO(stdin))


class TestRunUntilHaltOrCycle:
    def test_a_machine_already_halted_is_reported_as_halting(self) -> None:
        """The loop is never entered, and the answer is still ``True``."""
        vm = make_vm("brainfuck", "++")
        run_until_halt(vm)
        assert vm.halted
        assert run_until_halt_or_cycle(vm) is True


class TestTheDetectorsTakeAVM:
    """Every detector accepts what ``make_vm`` returns, not just a ``_Machine``."""

    def test_the_growth_detector_takes_a_vm(self) -> None:
        """``+[>]`` walks off onto a zero; ``+[>+]`` grows a cell a lap."""
        assert run_until_halt_or_growth(make_vm("brainfuck", "+[>]")) is True
        assert run_until_halt_or_growth(make_vm("brainfuck", "+[>+]")) is False

    def test_the_value_growth_detector_refuses_a_bounded_language(self) -> None:
        """Brainfuck's cells wrap, so a climb there is a cycle, not a proof."""
        with pytest.raises(TypeError, match="affine machine"):
            run_until_halt_or_value_growth(make_vm("brainfuck", "+[>+]"))

    def test_an_object_that_is_neither_raises_type_error(self) -> None:
        """The unwrap looks one level deep, and no further."""
        with pytest.raises(TypeError, match="steppable with a snapshot"):
            run_until_halt_or_cycle(object())  # type: ignore[arg-type]

    def test_a_negative_branch_cap_stops_rather_than_exploring_free(self) -> None:
        """A cap below zero is still a cap."""

        class _Unbounded:
            def branching_snapshot(self) -> int:
                return 0

            def branching_halted(self, _state: int) -> bool:
                return False

            def branching_successors(self, state: int, _limit: int) -> list[int]:
                return [state + 1]

        for limit in (0, -1):
            with pytest.raises(TimeoutError, match="branching states"):
                run_until_halt_or_all_branches_cycle(
                    _Unbounded(),  # type: ignore[arg-type]
                    limit=limit,
                )


@pytest.mark.parametrize(("program", "limit"), [("", 0), ("+", 1)])
def test_growth_detector_accepts_halt_at_step_limit(program: str, limit: int) -> None:
    assert run_until_halt_or_growth(make_vm("Brainfuck", program), limit) is True
