"""3x transition fallback and shared VM contracts."""

from fractions import Fraction

from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)


class TestStepMachine:
    def test_stack_commands_replace_or_consume_their_operands(self) -> None:
        """Arithmetic, output, and swap do not leave stale operands behind."""
        from esolangs.interpreters.stack_based.three_x import _advance

        three = Fraction(3)
        zero = Fraction(0)
        assert _advance((0, (three, three, three), (), ()), "x") == (
            1,
            (zero,),
            (),
            (),
        )
        assert _advance((0, (three, zero), (), ()), "!") == (1, (three,), (), ())
        assert _advance((0, (three, zero), (), ()), "#") == (1, (zero, three), (), ())

    def test_an_open_paren_on_zero_skips_only_when_it_has_a_target(self) -> None:
        """``(`` on a zero jumps past the loop, or advances with no target.

        The shell supplies the matching ``)`` as ``target``; a caller that
        does not know one leaves it ``None``, and then the cursor simply
        moves on rather than jumping nowhere.
        """
        from esolangs.interpreters.stack_based.three_x import _advance

        zero = Fraction(0)
        assert _advance((0, (zero,), (), ()), "(") == (1, (zero,), (), ())
        assert _advance((0, (zero,), (), ()), "(", None, 9) == (10, (zero,), (), ())


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.three_x import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "3"
    halting_program = "3!"
    looping_program = "3()"
    state_views = ("ind", "variables", "ip")
    # Assigns a variable, so `variables` moves.
    viewing_program = "3333xv3^!"
