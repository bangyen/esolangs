"""The growth certificate's rejecting arms, one construction each.

:func:`_climbs_forever` certifies an affine climb from three visits to
one key.  Each of its four conditions refuses a different way the three
can fail to line up, and a program reaching every one of them is far
harder to write than the triples themselves.
"""

from unittest.mock import patch

import pytest

import esolangs
from esolangs import vm as vm_module
from esolangs.exceptions import InterpreterLimitError, ProgramError
from esolangs.vm import _climbs_forever

# Three visits, ten steps apart, whose values climb by a constant 1 with
# the input cursor never moving: the shape the certificate accepts.
CLIMBING = [(0, (0,), 0), (10, (1,), 0), (20, (2,), 0)]


class TestClimbsForever:
    def test_a_constant_positive_step_with_held_clamps_is_certified(self) -> None:
        assert _climbs_forever(CLIMBING, [None] * 21) is True

    def test_a_moving_input_cursor_is_not_certified(self) -> None:
        """Consuming input between visits means the laps are not alike."""
        visits = [(0, (0,), 0), (10, (1,), 1), (20, (2,), 1)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_changing_value_count_is_not_certified(self) -> None:
        visits = [(0, (0,), 0), (10, (1, 1), 0), (20, (2, 2), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_two_different_steps_are_not_certified(self) -> None:
        """The second lap climbs by 2 where the first climbed by 1."""
        visits = [(0, (0,), 0), (10, (1,), 0), (20, (3,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_step_that_stands_still_is_not_certified(self) -> None:
        visits = [(0, (5,), 0), (10, (5,), 0), (20, (5,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_descending_step_is_not_certified(self) -> None:
        """Falling values reach a floor rather than climbing forever."""
        visits = [(0, (5,), 0), (10, (4,), 0), (20, (3,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_drifting_clamp_is_not_certified(self) -> None:
        """The step repeats, but a slack sinking toward zero will flip."""
        slacks: list[int | None] = [5] * 10 + [3] * 11
        assert _climbs_forever(CLIMBING, slacks) is False


class TestTheArmsThatTranslateWhatAnInterpreterRaises:
    """``make_vm`` and ``step`` promise every deliberate failure is ours.

    Each arm here is reached only when an interpreter raises something the
    wrapper has to restate, so none of them is on a path an ordinary
    program takes.  Patched rather than provoked: a language that raises
    ``ProgramError`` from its constructor today may not tomorrow, and a
    test that silently stops exercising the arm is worse than one that
    says what it is doing.
    """

    @staticmethod
    def _adapter(fault: BaseException) -> object:
        def build(*_args: object, **_kwargs: object) -> object:
            raise fault

        return build

    def test_a_program_error_from_the_loader_passes_through(self) -> None:
        """Already ours, so it is re-raised rather than wrapped twice."""
        planted = ProgramError("unmatched something")
        with (
            patch.dict(
                vm_module._VM_ADAPTERS,  # noqa: SLF001 - the arm is private
                {"brainfuck": self._adapter(planted)},
            ),
            pytest.raises(ProgramError) as exc,
        ):
            esolangs.make_vm("brainfuck", "+")
        assert exc.value is planted

    def test_a_recursion_error_from_the_loader_becomes_a_limit(self) -> None:
        """A loader that recurses past CPython's stack is a limit, not a bug."""
        with (
            patch.dict(
                vm_module._VM_ADAPTERS,  # noqa: SLF001 - the arm is private
                {"brainfuck": self._adapter(RecursionError())},
            ),
            pytest.raises(InterpreterLimitError, match="recursed deeper"),
        ):
            esolangs.make_vm("brainfuck", "+")

    def test_a_program_error_from_a_step_passes_through(self) -> None:
        """The same promise one layer down, where the machine is running."""
        machine = esolangs.make_vm("brainfuck", "+++")
        planted = ProgramError("bad instruction")

        def boom() -> None:
            raise planted

        with (
            patch.object(machine._machine, "step", boom),  # noqa: SLF001 - the arm
            pytest.raises(ProgramError) as exc,
        ):
            machine.step()
        assert exc.value is planted
