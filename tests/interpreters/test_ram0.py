"""Unit tests for RAM0 interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.ram0 import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)


def dump(code: str) -> str:
    """Run ``code`` and return the state dump it prints."""
    with redirect_stdout(io.StringIO()) as f:
        run(code, io=IO())
    return f.getvalue()


_DUMPS = {
    # Increment z to 3, then zero it
    "z_command_zero_register": ("A A A Z", "z: 0\nn: 0\nram: {}"),
    "a_command_increment": ("A A A", "z: 3\nn: 0\nram: {}"),
    # z=3, then copy to n
    "n_command_copy_z_to_n": ("A A A N", "z: 3\nn: 3\nram: {}"),
    # Store 5 at address 2, then L loads from uninitialized address 7: 0
    "l_command_load_from_memory": (
        "A A N A A A S A A L",
        "z: 0\nn: 2\nram: {\n    2: 5\n}",
    ),
    "s_command_store_to_memory": ("A A N A A A S", "z: 5\nn: 2\nram: {\n    2: 5\n}"),
    # Skip A if z is zero (it is)
    "c_command_conditional_skip": ("C A", "z: 0\nn: 0\nram: {}"),
    # z=1, then conditionally skip A (should not skip)
    "c_command_no_skip_when_nonzero": ("A C A", "z: 2\nn: 0\nram: {}"),
    # All three A commands executed (goto doesn't skip as expected)
    "goto_command_jump": ("A 3 A A", "z: 3\nn: 0\nram: {}"),
    # Store 2 at address 1, 6 at address 4
    "multiple_memory_locations": (
        "A N A S A A N A A S",
        "z: 6\nn: 4\nram: {\n    1: 2,\n    4: 6\n}",
    ),
    "empty_program": ("", "z: 0\nn: 0\nram: {}"),
    # Only A command executes, but L command loads from uninitialized address
    "invalid_commands_ignored": (
        "A invalid B C D E F G H I J K L M O P Q R T U V W X Y Z",
        "z: 0\nn: 0\nram: {}",
    ),
    "comments_in_code": (
        "A /* comment */ A // another comment A",
        "z: 3\nn: 0\nram: {}",
    ),
    # A skipped goto 0 is harmless; leading zeros are decimal (004 is 4).
    "skipped_goto_zero": ("C 0 A", "z: 1\nn: 0\nram: {}"),
    "leading_zero_goto": ("Z 004 A A", "z: 1\nn: 0\nram: {}"),
    # Jump to non-existent instruction: terminates after first A
    "large_goto_number": ("A 999 A", "z: 1\nn: 0\nram: {}"),
}


@pytest.mark.parametrize(("code", "expected"), _DUMPS.values(), ids=list(_DUMPS))
def test_dump(code: str, expected: str) -> None:
    assert dump(code) == expected


def test_goto_zero_names_no_command() -> None:
    """Digits are not comments ("characters other than ZANCLS and digits")."""
    with pytest.raises(HaltError, match="count from 1"):
        dump("A A 0 A")


class TestStepMachine:
    def test_the_dump_flag_is_set_by_the_step_past_the_end(self) -> None:
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", IO())
        machine.step()
        assert not machine.dumped
        machine.step()
        assert machine.dumped

    def test_load_reads_the_address_in_z(self) -> None:
        """L loads RAM at the address z holds, not at a fixed one."""
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A N S L", IO())
        while not machine.halted:
            machine.step()
        assert (machine.z, machine.ram) == (1, {1: 1})

    def test_conditional_skip_is_relative(self) -> None:
        """C skips the next command; it does not jump to a fixed index."""
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A Z C A A", IO())
        while not machine.halted:
            machine.step()
        # exactly one A was skipped: skipping none leaves 2, skipping both 0
        assert machine.z == 1

    def test_state_is_dumped_only_once(self) -> None:
        """Stepping a halted machine again does not repeat the dump."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import _Machine

        machine = _Machine("A", ScriptedIO(""))
        while not machine.halted:
            machine.step()
        machine.step()  # dumps
        machine.step()  # must not dump again
        assert machine.io.getvalue() == "z: 1\nn: 0\nram: {}"

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # Z1: Z zeroes z (already zero, a net no-op), then the goto to
        # token 1 sets ind back to 0 -- a genuine state cycle, not
        # unbounded growth.
        from esolangs.interpreters.register_based.ram0 import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("Z1", IO())) is False


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.ram0 import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "A"
    halting_program = "ZA"
    looping_program = "Z1"
    # `Z` zeroes the accumulator and `A` increments it, so the cursor and
    # `z` move while `n` stays put -- three slots, not one read thrice.
    state_views = ("ind", "z", "n", "ip", "memory")
    # `S` is what moves `n`; "ZA" left it at its initial value.
    viewing_program = "A N S"


if __name__ == "__main__":
    pytest.main([__file__])


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_n_and_z_are_separate_registers(self) -> None:
        """One step in they differ; by the end of the run they agree."""
        machine = _machine("A N S")
        machine.step()
        assert (machine.z, machine.n) == (1, 0)
