r"""Shared bodies for the per-language tests whose *data* is the only."""

import re
from typing import Any, ClassVar

import pytest

# Every halting_program in the.
# turns a mistaken entry into a.
_HALT_BUDGET = 100_000


class EmptyProgramContract:
    r"""What a language does with a program containing no instructions."""

    # The file's own helper --.
    # already knows whether the.
    # and carries any limit the.
    # have to model either.
    run: ClassVar[Any]

    # The empty program in this.
    empty_program: ClassVar[Any] = ""

    # What running it prints, for.
    # always "", so that is the.
    empty_output: ClassVar[str] = ""

    # Set instead by the languages.
    # message, which is what.
    empty_raises: ClassVar[str | None] = None

    def test_empty_program(self) -> None:
        r"""An empty program either produces its output or is refused."""
        if self.empty_raises is not None:
            # The message is matched in.
            # substring, which would also.
            # wider or wrong claim around.
            # gets the escaped message,.
            # `pytest.raises(ValueError)`.
            expected = re.escape(self.empty_raises)
            with pytest.raises(ValueError, match=expected) as caught:
                type(self).run(self.empty_program)
            assert str(caught.value) == self.empty_raises
        else:
            assert type(self).run(self.empty_program) == self.empty_output


class SnapshotContract:
    r"""That a machine's snapshot can be hashed, and moves when it steps."""

    machine: ClassVar[Any]

    # A program with at least one.
    # has something to observe.
    stepping_program: ClassVar[Any]

    def test_snapshot_is_hashable(self) -> None:
        r"""The state the cycle detector stores can go in a set."""
        assert hash(type(self).machine(self.stepping_program).snapshot()) is not None

    def test_snapshot_changes_after_a_step(self) -> None:
        r"""Stepping the machine moves it to a state that compares different."""
        machine = type(self).machine(self.stepping_program)
        before = machine.snapshot()
        machine.step()
        assert machine.snapshot() != before


class InputCursorContract:
    r"""That reading input moves the snapshot, and the reader with it."""

    # : Builds the machine from a.
    # : ``machine`` hook elsewhere.
    # : other contracts never need.
    reader: ClassVar[Any]

    # : A program that reads from.
    reading_program: ClassVar[Any]
    reading_stdin: ClassVar[str]

    # : Steps run *before* the.
    # : to walk somewhere before it.
    # : after them: a warm-up moves.
    # : satisfy the "changed" half.
    steps_before_read: ClassVar[int] = 0

    # : How many steps reach the.
    steps_to_read: ClassVar[int] = 1
    position_after_read: ClassVar[int] = 1

    def test_snapshot_includes_the_input_cursor(self) -> None:
        r"""A read moves the snapshot, so a cat loop is not seen as a cycle."""
        machine = type(self).reader(self.reading_program, self.reading_stdin)
        for _ in range(self.steps_before_read):
            machine.step()
        before = machine.snapshot()
        for _ in range(self.steps_to_read):
            machine.step()
        assert machine.snapshot() != before
        assert machine.io.position() == self.position_after_read


class CycleContract:
    r"""What the hang detector concludes about two of a language's programs."""

    # The language's steppable.
    # ``machine(program)`` -- a.
    # since which of IO/ScriptedIO.
    machine: ClassVar[Any]

    halting_program: ClassVar[Any]

    # None where no existing test.
    # Writing one takes knowing.
    # than growing its state.
    # instead of being filled with.
    looping_program: ClassVar[Any] = None

    def test_halting_program_is_detected(self) -> None:
        r"""A program that reaches its halt is reported as halting."""
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(type(self).machine(self.halting_program))

    def test_loop_is_detected_as_a_cycle(self) -> None:
        r"""A program that revisits a snapshot is proven to hang."""
        from esolangs.vm import run_until_halt_or_cycle

        if self.looping_program is None:
            pytest.skip("no looping program written for this language yet")
        assert not run_until_halt_or_cycle(type(self).machine(self.looping_program))

    def test_stepping_past_the_halt_does_not_raise(self) -> None:
        r"""A halted machine ignores a further step instead of failing."""
        machine = type(self).machine(self.halting_program)
        for _ in range(_HALT_BUDGET):
            if machine.halted:
                break
            machine.step()
        else:
            raise AssertionError("halting_program did not halt")
        machine.step()  # must not raise.
        assert machine.halted


class StateViewContract:
    r"""That a machine's named views really read the state they claim."""

    machine: ClassVar[Any]

    # : The names to read off the.
    # : spells its own state --.
    # : RAM0 -- and a name absent.
    state_views: ClassVar[tuple[str, ...]]

    # : A program that moves every.
    # : listed in.
    viewing_program: ClassVar[Any]

    # : Views this language's.
    # : that only flips past the.
    # : Naming them is the point:.
    # : exercised", which is what.
    # : listed here that *does*.
    #: into a blanket exemption.
    constant_views: ClassVar[frozenset[str]] = frozenset()

    def test_every_named_view_reads_the_machine(self) -> None:
        r"""Each name resolves, before and after a step, without raising."""
        machine = type(self).machine(self.viewing_program)
        for name in self.state_views:
            getattr(machine, name)
        if not machine.halted:
            machine.step()
        for name in self.state_views:
            getattr(machine, name)

    def test_every_view_moves_or_is_declared_constant(self) -> None:
        r"""Each named view takes more than one value, or is declared inert."""
        machine = type(self).machine(self.viewing_program)
        names = self.state_views
        seen: dict[str, set[str]] = {n: {repr(getattr(machine, n))} for n in names}
        for _ in range(_HALT_BUDGET):
            if machine.halted:
                break
            machine.step()
            for name in names:
                seen[name].add(repr(getattr(machine, name)))

        moved = {n for n in names if len(seen[n]) > 1}
        declared = set(self.constant_views)
        assert declared <= set(names), (
            f"constant_views names no such view: {declared - set(names)}"
        )
        assert moved == set(names) - declared, (
            f"views that moved: {sorted(moved)}; "
            f"expected to move: {sorted(set(names) - declared)}"
        )
