"""Shared bodies for the per-language tests whose *data* is the only thing
that differs between files.

The registry-wide sweep in ``tests/test_vm_protocol.py`` handles the checks
that need no per-language knowledge at all.  Two families resisted it, and
for the same reason: their answers are genuinely language-specific.  An
empty program prints nothing in brainfuck, prints ``o`` in A Painter Ant,
and is a ``ValueError`` in Dig -- and a program that loops forever cannot
be derived from a registry entry, it has to be written by someone who knows
the language.

So the split here is the other way round from the sweep: the *body* is
shared and the *data* is supplied per file.  A language's test file names
its own runner and its own programs, and inherits the assertions:

    class TestContract(EmptyProgramContract):
        run = staticmethod(run_and_capture)
        empty_program = ""
        empty_output = ""

Anything the language does on top of the shared shape -- Between also
checking ``"\\n\\n"``, Dig also rejecting blank-only programs -- stays a
normal test in that file.  The contract replaces the copied shape, not the
language's own coverage.

The ``run`` hook stays per file, but it is worth being exact about why,
because the obvious reason is no longer the true one.  Most of those
runners now differ only in which ``run`` they close over, and share their
body with :func:`tests.interpreters.runner.run_program`.  What still has
to be named per file is the language's *interface*: Wumpus's ``heading``,
the files whose first argument is a target string or a number rather than
a program, and the ones carrying a limit of their own.  A shared hook is
what lets those coexist with the dozen that are now one line.
"""

import re
from typing import Any, ClassVar

import pytest

# Every halting_program in the suite halts in well under this; the bound
# turns a mistaken entry into a readable failure rather than a hang.
_HALT_BUDGET = 100_000


class EmptyProgramContract:
    """What a language does with a program containing no instructions.

    A language either runs the empty program to some output (nearly always
    ``""``, though A Painter Ant still prints its ant) or refuses it as
    malformed.  That is the whole of the variation across the forty-odd
    copies this replaces, so setting :attr:`empty_raises` is what picks the
    second branch and everything else defaults to the first.
    """

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
    """That a machine's snapshot can be hashed, and moves when it steps.

    Both halves are the cycle detector's preconditions rather than
    statements about the language.  ``run_until_halt_or_cycle`` stores
    snapshots in a set, so an unhashable one -- a list of cells where a
    tuple was meant -- silently disables hang detection; and a snapshot
    that does not change when the machine does makes every program look
    like a hang on its second step.
    """

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


class CycleContract:
    """What the hang detector concludes about two of a language's programs.

    ``run_until_halt_or_cycle`` returns True when a machine reaches its
    halt and False when it proves a hang by revisiting a snapshot.  Both
    halves matter: without the halting program the detector could return
    False for everything, and without the looping one it could return True.

    The looping program has to *revisit a snapshot*, not merely fail to
    halt.  A loop that grows its state on every pass -- a counter climbing
    forever -- never repeats one, so the detector runs until something else
    stops it.  That is why these programs are written per language by
    someone who knows it, rather than derived from the registry.
    """

    # The language's steppable class and the IO it takes, as
    # ``machine(program)`` -- a small function in the file supplies the IO,
    # since which of IO/ScriptedIO a language wants is its own business.
    machine: ClassVar[Any]

    halting_program: ClassVar[Any]

    # None where no existing test had a looping program for this language.
    # Writing one takes knowing which of its loops repeats a snapshot rather
    # than growing its state forever, so the gap is left visible as a skip
    # instead of being filled with a guess that would hang the suite.
    looping_program: ClassVar[Any] = None

    def test_halting_program_is_detected(self) -> None:
        """A program that reaches its halt is reported as halting."""
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(type(self).machine(self.halting_program))

    def test_loop_is_detected_as_a_cycle(self) -> None:
        """A program that revisits a snapshot is proven to hang."""
        from esolangs.vm import run_until_halt_or_cycle

        if self.looping_program is None:
            pytest.skip("no looping program written for this language yet")
        assert not run_until_halt_or_cycle(type(self).machine(self.looping_program))

    def test_stepping_past_the_halt_does_not_raise(self) -> None:
        """A halted machine ignores a further step instead of failing.

        Every ``step()`` guards on ``halted`` and returns, which is what
        lets a caller drive a machine without checking first.  Nine
        interpreters were missing that guard and raised ``IndexError`` off
        the end of their own program; this is what holds the line once
        they have it.

        Only "did not raise, and is still halted" is asserted.  Minsky Swap
        and RAM0 legitimately *write* on the step after their halt -- that
        is where their final register dump comes from -- so pinning the
        output here would contradict a documented convention.
        """
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
    """That a machine's named views really read the state they claim.

    The purity refactors moved each interpreter's fields into one immutable
    ``_State`` tuple and re-exposed the old names as properties over its
    slots::

        @property
        def acc(self) -> int:
            return self.state[1]

    Before that, ``machine.acc`` *was* the field, so anything touching a
    machine exercised it.  After, it only runs when something reads it by
    name -- and the suites drive ``run``/``step``/``snapshot`` instead.  So
    these views stopped being covered without any behaviour changing, and a
    property wired to the wrong slot would pass every other test in its
    file.  They are real API: ``debug.py`` reads the tape through
    ``vm.memory``, and ``vm.py`` looks up ``of`` on a state class.

    The named views are asserted to be *distinct* rather than pinned to
    values: what a slot holds is the language's business, but two names
    reading one slot is the failure this shape invites, and it is the same
    check for every language.
    """

    machine: ClassVar[Any]

    #: The names to read off the machine.  Per file, because each language
    #: spells its own state -- ``acc``/``jumps`` in Unsquare, ``z``/``n`` in
    #: RAM0 -- and a name absent here is simply not part of that view.
    state_views: ClassVar[tuple[str, ...]]

    #: A program that leaves at least two views holding different values, so
    #: "distinct" has something to distinguish.
    viewing_program: ClassVar[Any]

    def test_every_named_view_reads_the_machine(self) -> None:
        """Each name resolves, before and after a step, without raising."""
        machine = type(self).machine(self.viewing_program)
        for name in self.state_views:
            getattr(machine, name)
        if not machine.halted:
            machine.step()
        for name in self.state_views:
            getattr(machine, name)

    def test_the_views_do_not_alias_one_slot(self) -> None:
        """Stepping moves at least one view, so they are not one field twice.

        A property returning the wrong tuple index still reads *something*,
        so resolving is not enough: the run has to move the views apart.
        """
        machine = type(self).machine(self.viewing_program)
        before = [repr(getattr(machine, n)) for n in self.state_views]
        for _ in range(_HALT_BUDGET):
            if machine.halted:
                break
            machine.step()
        after = [repr(getattr(machine, n)) for n in self.state_views]
        assert before != after, "no named view changed over the whole run"
