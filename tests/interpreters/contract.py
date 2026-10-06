"""Shared bodies for the per-language tests whose *data* is the only thing
that differs between files.
"""

import re
from typing import Any, ClassVar

import pytest

# Every halting_program in the suite halts in well under this; the bound
# turns a mistaken entry into a readable failure rather than a hang.
_HALT_BUDGET = 100_000


class EmptyProgramContract:
    """What a language does with a program containing no instructions."""

    # The file's own helper -- run_and_capture, _run, run_program.  It
    # already knows whether the language wants a string or a list of lines,
    # and carries any limit the language needs, so the contract does not
    # have to model either.
    run: ClassVar[Any]

    # The empty program in this language's shape: "" or [].
    empty_program: ClassVar[Any] = ""

    # What running it prints, for the languages that accept it.  Almost
    # always "", so that is the default and only the exceptions say so.
    empty_output: ClassVar[str] = ""

    # Set instead by the languages that refuse an empty program: the exact
    # message, which is what decides between the two branches below.
    empty_raises: ClassVar[str | None] = None

    def test_empty_program(self) -> None:
        """An empty program either produces its output or is refused."""
        if self.empty_raises is not None:
            # The message is matched in full rather than as a `match=`
            # substring, which would also accept a message that had grown a
            # wider or wrong claim around the expected text.  `match=` still
            # gets the escaped message, since the lint rule wants
            # `pytest.raises(ValueError)` narrowed by something.
            expected = re.escape(self.empty_raises)
            with pytest.raises(ValueError, match=expected) as caught:
                type(self).run(self.empty_program)
            assert str(caught.value) == self.empty_raises
        else:
            assert type(self).run(self.empty_program) == self.empty_output


class SnapshotContract:
    """That a machine's snapshot can be hashed, and moves when it steps."""

    machine: ClassVar[Any]

    # A program with at least one step left in it, so the "changes" half
    # has something to observe.
    stepping_program: ClassVar[Any]

    def test_snapshot_is_hashable(self) -> None:
        """The state the cycle detector stores can go in a set."""
        assert hash(type(self).machine(self.stepping_program).snapshot()) is not None

    def test_snapshot_changes_after_a_step(self) -> None:
        """Stepping the machine moves it to a state that compares different."""
        machine = type(self).machine(self.stepping_program)
        before = machine.snapshot()
        machine.step()
        assert machine.snapshot() != before


class InputCursorContract:
    """That reading input moves the snapshot, and the reader with it."""

    #: Builds the machine from a program *and* its stdin, which the
    #: ``machine`` hook elsewhere in this module does not take -- the
    #: other contracts never need a machine that reads anything.
    reader: ClassVar[Any]

    #: A program that reads from its input, and the stdin it reads.
    reading_program: ClassVar[Any]
    reading_stdin: ClassVar[str]

    #: Steps run *before* the snapshot is taken, for a language that has
    #: to walk somewhere before it can read.  The comparison has to start
    #: after them: a warm-up moves the snapshot by itself, which would
    #: satisfy the "changed" half without the read doing anything.
    steps_before_read: ClassVar[int] = 0

    #: How many steps reach the read, and where the cursor stands after.
    steps_to_read: ClassVar[int] = 1
    position_after_read: ClassVar[int] = 1

    def test_snapshot_includes_the_input_cursor(self) -> None:
        """A read moves the snapshot, so a cat loop is not seen as a cycle."""
        machine = type(self).reader(self.reading_program, self.reading_stdin)
        for _ in range(self.steps_before_read):
            machine.step()
        before = machine.snapshot()
        for _ in range(self.steps_to_read):
            machine.step()
        assert machine.snapshot() != before
        assert machine.io.position() == self.position_after_read


class CycleContract:
    """What the hang detector concludes about two of a language's programs."""

    # The language's steppable class and the IO it takes, as
    # ``machine(program)`` -- a small function in the file supplies the IO,
    # since which of IO/ScriptedIO a language wants is its own business.
    machine: ClassVar[Any]

    halting_program: ClassVar[Any]

    looping_program: ClassVar[Any] = None
    no_cycle_reason: ClassVar[str | None] = None

    def test_cycle_fixture_or_obstruction_is_declared(self) -> None:
        assert (self.looping_program is None) == (self.no_cycle_reason is not None)
        if self.no_cycle_reason is not None:
            assert self.no_cycle_reason.strip()

    def test_halting_program_is_detected(self) -> None:
        """A program that reaches its halt is reported as halting."""
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(
            type(self).machine(self.halting_program), limit=_HALT_BUDGET
        )

    def test_loop_is_detected_as_a_cycle(self) -> None:
        """A program that revisits a snapshot is proven to hang."""
        from esolangs.vm import run_until_halt_or_cycle

        if self.looping_program is None:
            assert self.no_cycle_reason is not None
            pytest.skip(self.no_cycle_reason)
        assert not run_until_halt_or_cycle(
            type(self).machine(self.looping_program), limit=_HALT_BUDGET
        )

    def test_stepping_past_the_halt_does_not_raise(self) -> None:
        """A halted machine ignores a further step instead of failing."""
        machine = type(self).machine(self.halting_program)
        for _ in range(_HALT_BUDGET):
            if machine.halted:
                break
            machine.step()
        else:
            raise AssertionError("halting_program did not halt")
        machine.step()  # must not raise
        assert machine.halted


class StateViewContract:
    """That a machine's named views really read the state they claim."""

    machine: ClassVar[Any]

    #: The names to read off the machine.  Per file, because each language
    #: spells its own state -- ``acc``/``jumps`` in Unsquare, ``z``/``n`` in
    #: RAM0 -- and a name absent here is simply not part of that view.
    state_views: ClassVar[tuple[str, ...]]

    #: A program that moves every name in :attr:`state_views` except those
    #: listed in :attr:`constant_views`.
    viewing_program: ClassVar[Any]

    #: Views this language's program genuinely cannot move -- a dump flag
    #: that only flips past the halt, a store the program never writes.
    #: Naming them is the point: it separates "inert by nature" from "never
    #: exercised", which is what the old shape could not tell apart.  A view
    #: listed here that *does* move is an error too, so the list cannot rot
    #: into a blanket exemption.
    constant_views: ClassVar[frozenset[str]] = frozenset()

    def test_every_named_view_reads_the_machine(self) -> None:
        """Each name resolves, before and after a step, without raising."""
        machine = type(self).machine(self.viewing_program)
        for name in self.state_views:
            getattr(machine, name)
        if not machine.halted:
            machine.step()
        for name in self.state_views:
            getattr(machine, name)

    def test_every_view_moves_or_is_declared_constant(self) -> None:
        """Each named view takes more than one value, or is declared inert."""
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
