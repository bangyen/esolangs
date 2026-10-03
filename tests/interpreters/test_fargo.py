"""Fargo frame-state contracts beyond observable expression results."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fargo import _Machine


class TestMachine:
    def test_step_after_halting_is_a_no_op(self) -> None:
        machine = _Machine("$\n", ScriptedIO("0\n"))
        while not machine.halted:
            machine.step()
        state = machine.snapshot()
        machine.step()
        assert machine.snapshot() == state

    @staticmethod
    def _states(code: str, stdin: str = "0\n") -> list[object]:
        """Every snapshot one run passes through, halt included."""
        machine = _Machine(code, ScriptedIO(stdin))
        seen: list[object] = []
        for _ in range(200):
            seen.append(machine.snapshot())
            if machine.halted:
                break
            machine.step()
        return seen

    def test_snapshot_separates_the_state_it_claims_to_carry(self) -> None:
        """Each field matters, so a run's states are all distinct.

        The cycle detector's soundness rests on the snapshot being
        *complete*: a field it drops is a difference two runs can hide
        behind.  These three pairs differ only in a frame's bindings, its
        pending arguments, and its result respectively -- the parts that
        are captured through ``repr()`` and so are easiest to hollow out
        without any output changing.
        """
        assert self._states("f x | x 0\nf 1\n$\n") != self._states(
            "f x | x 0\nf 0\n$\n"
        ), "bindings do not reach the snapshot"
        assert self._states("% 0 | 1 0\n$\n") != self._states("% 0 | 0 0\n$\n"), (
            "pending arguments do not reach the snapshot"
        )
        assert self._states("g | 1 0\n% 0 : 1 g\n$\n") != self._states(
            "g | 0 0\n% 0 : 1 g\n$\n"
        ), "a frame's result does not reach the snapshot"

    def test_every_step_of_a_run_has_its_own_state(self) -> None:
        """No two steps collide, so nothing is a spurious cycle."""
        seen = self._states("f x | x 0\nf 1\n$\n")
        assert len(set(seen)) == len(seen)

    def test_frame_entry_key_separates_differing_bindings(self) -> None:
        """Two calls of one function with different arguments differ.

        The ancestor check calls a frame a replay when its key matches an
        ancestor's, so bindings dropped from the key would make an
        ordinary recursion look like a hang.
        """
        machine = _Machine("f x | x 0\nf 1\n$\n", ScriptedIO("0\n"))
        keys = []
        while not machine.halted:
            machine.step()
            if machine.frames:
                keys.append(machine.frame_entry_key(machine.frames[-1]))
        other = _Machine("f x | x 0\nf 0\n$\n", ScriptedIO("0\n"))
        others = []
        while not other.halted:
            other.step()
            if other.frames:
                others.append(other.frame_entry_key(other.frames[-1]))
        assert keys != others
