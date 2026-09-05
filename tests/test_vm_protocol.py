"""The VM protocol, swept over every language rather than per language.

Each of these checks was written by hand in the per-language test files,
between ten and thirty-odd times over, differing only in which ``_Machine``
to import and which program to hand it.  None of them is about a language:
they are the contract every adapter owes -- that a machine reports its own
halt, that stepping past that halt changes nothing, that its snapshot can
be hashed (the cycle detector's precondition), and that driving it a step
at a time lands where :func:`esolangs.run` lands.

Sweeping them from :data:`~tests.samples.SAMPLES` means a language added to
the registry is covered the moment its sample lands, instead of when
somebody remembers to copy the bodies into a new file.  The copies that
remain in the per-language files are the ones asserting something
language-specific on top of the shared invariant -- BF-PDA's stack after
the no-op step, Container's tick -- which the sweep cannot know about.

Three conventions keep the sweep honest rather than being papered over,
and each is a named set in :mod:`tests.samples`:
:data:`~tests.samples.DUMPS_ON_THE_POST_HALT_STEP` (the output arrives one
step past the halt), :data:`~tests.samples.NEVER_SELF_HALTS` (``run`` stops
the program from outside, so there is no halt to drive to), and
:data:`~tests.samples.NONDETERMINISTIC_AGAINST_RUN` (``run`` draws a random
heading, so the two sides are not comparable).  Absorbing any of them into
the driver would make the sweep pass while hiding the distinction.

Two of those three are not only the sweep's business.  A caller outside
this suite writing ``while not vm.halted: vm.step()`` hangs on the
never-halting languages and reads ``""`` from the dumping ones, with
nothing in the protocol to warn them, so both are now declared on the
interpreters and reported by :attr:`esolangs.vm.VM.self_halts` and
:attr:`esolangs.vm.VM.dumps_on_the_post_halt_step`.  The sets stay -- the
sweep needs the answer without building a machine -- and two tests below
lock them against the traits in both directions.

A fourth set, :data:`~tests.samples.RAISES_ON_THE_POST_HALT_STEP`, was not
a convention but the sweep's first finding: nine adapters raised
``IndexError`` when stepped past their halt instead of doing nothing, and
none of the fifteen hand-written copies of that check covered any of them.
All nine now carry the guard the rest already had, so the set is empty --
kept, rather than deleted, because the companion test compares it against
what actually raises and would fail if any of them regressed.
"""

import contextlib
import io
from typing import cast

import pytest

import esolangs
from esolangs.registry import RUNNERS
from esolangs.vm import VM, _StepMachineWithShape, make_vm, run_until_halt

from .samples import (
    DUMPS_ON_THE_POST_HALT_STEP,
    NEVER_SELF_HALTS,
    NONDETERMINISTIC_AGAINST_RUN,
    RAISES_ON_THE_POST_HALT_STEP,
    SAMPLES,
)

# The sweep drives every machine to its halt, so a runaway sample would
# hang the suite rather than fail it.  Every sample that halts at all does
# so in well under a hundred steps; this is the bound that turns a hang
# into a readable failure.
_STEP_BUDGET = 100_000

_PARAMS = [
    pytest.param(name, program, stdin, id=name)
    for name, (program, stdin) in sorted(SAMPLES.items())
]


def _drive(vm: VM) -> str:
    """Step ``vm`` to its halt and return everything it wrote.

    The budget is shared with the other consumers through
    :func:`~esolangs.vm.run_until_halt`; what stays here is the overrun
    policy, which for a test is to fail loudly rather than to return a
    partial run's output as if it were a halt's.
    """
    if not run_until_halt(vm, _STEP_BUDGET):
        raise AssertionError(f"no halt within {_STEP_BUDGET} steps")
    return vm.output


# The prefix the never-halting languages are compared over instead of a
# halt.  They have no halt to drive to, so "the same run" has to mean "the
# same state after the same number of steps".
#
# Output alone will not do it.  Suffolk's sample writes within this many
# steps, but A Painter Ant's writes nothing at all -- not at a hundred
# steps and not at ten thousand, because it paints rather than prints --
# so comparing its output would be comparing "" against "" and passing no
# matter what the interpreter did.  The comparison is therefore over the
# observable state as well, which both of them do move.
_PREFIX_STEPS = 100

# What a run is compared on: everything the VM exposes about where it
# ended up.  ``memory`` and ``stack`` are lists, so this is a tuple of
# copies rather than views into the machine.
_Observed = tuple[str, object, list[int], list[object]]


def _observe(vm: VM) -> _Observed:
    """Return everything ``vm`` exposes about its current state."""
    return (vm.output, vm.ip, vm.memory, vm.stack)


def _settle(vm: VM, language: str) -> _Observed:
    """Drive ``vm`` as far as it goes and return its observable state.

    Three of the file's conventions meet here.  A language with a halt is
    driven to it; the never-halting two are stepped a fixed distance
    instead, so all sixty-three are covered rather than two being skipped.
    And the dumping languages are stepped once more, because that step is
    where their output is written -- every one of them is still empty at
    the halt itself, so a comparison that stopped there would be comparing
    nothing.
    """
    if language in NEVER_SELF_HALTS:
        for _ in range(_PREFIX_STEPS):
            vm.step()
        return _observe(vm)
    _drive(vm)
    if language in DUMPS_ON_THE_POST_HALT_STEP:
        vm.step()
    return _observe(vm)


def _machine_of(vm: VM) -> object | None:
    """Return the interpreter state object an adapter wraps, if it has one.

    The adapters keep it under different names, so look for the attribute
    carrying ``snapshot()`` rather than naming one.
    """
    for value in vars(vm).values():
        if hasattr(value, "snapshot"):
            return cast(object, value)
    return None


class TestSamplesCoverEveryLanguage:
    """The table is the sweep's coverage, so it is the thing to lock.

    A language can be added to the registry with an adapter and no sample,
    and every test below would still pass -- on the other fifty-nine.  The
    set equality is what makes the omission fail.
    """

    def test_every_registry_language_has_a_sample(self) -> None:
        assert sorted(set(RUNNERS) - set(SAMPLES)) == []

    def test_no_sample_names_a_language_the_registry_lost(self) -> None:
        assert sorted(set(SAMPLES) - set(RUNNERS)) == []

    @pytest.mark.parametrize(
        "exceptions",
        [
            DUMPS_ON_THE_POST_HALT_STEP,
            NEVER_SELF_HALTS,
            NONDETERMINISTIC_AGAINST_RUN,
            RAISES_ON_THE_POST_HALT_STEP,
        ],
        ids=["dumps", "never-halts", "nondeterministic", "raises"],
    )
    def test_the_named_exceptions_are_real_languages(
        self, exceptions: frozenset[str]
    ) -> None:
        """A renamed language must not leave an exception silently inert.

        An exception set naming a language the registry no longer has would
        stop excusing anything, and the sweep would start asserting the
        wrong invariant on whichever language inherited the behaviour.
        """
        assert sorted(exceptions - set(RUNNERS)) == []

    def test_most_samples_write_something(self) -> None:
        """The output-comparing sweeps are not comparing nothing.

        Eight samples write nothing at all -- they move memory, paint, or
        push, and that is a fair thing for a sample to do -- so the sweeps
        compare ``ip``/``memory``/``stack`` too rather than output alone.
        This is what keeps that from quietly becoming the norm: if a
        change left most samples silent, the purity and leakage sweeps
        would still pass while checking almost nothing, and only this
        would fail.

        Deliberately a floor rather than an exact set, which would be a
        ninth exception list to maintain for no gain.
        """
        writes = sum(
            bool(_settle(make_vm(name, program, stdin), name)[0])
            for name, (program, stdin) in SAMPLES.items()
        )
        assert writes >= 3 * len(SAMPLES) // 4


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageHonoursTheProtocol:
    """The shared invariants, once each, for every registry language."""

    def test_stepping_matches_running(
        self, language: str, program: str, stdin: str
    ) -> None:
        """A VM stepped to completion writes exactly what ``run`` writes.

        This is the invariant the per-file copies were really after: an
        adapter that drops a command, or writes its output somewhere the
        wrapper does not read, differs from the interpreter here and
        nowhere else.
        """
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} halts only on run's external limit")
        if language in NONDETERMINISTIC_AGAINST_RUN:
            pytest.skip(f"{language}'s run draws a random heading")
        expected = esolangs.run(language, program, stdin=stdin)
        vm = make_vm(language, program, stdin)
        _drive(vm)
        if language in DUMPS_ON_THE_POST_HALT_STEP:
            vm.step()  # the dump, which run performs after its own loop
        assert vm.output == expected

    def test_the_sample_reaches_a_halt(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Every sample halts, which the sweeps above depend on."""
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} has no self-halt")
        vm = make_vm(language, program, stdin)
        _drive(vm)
        assert vm.halted

    def test_step_after_halt_is_a_noop(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Stepping a halted machine neither raises nor writes anything more.

        A wrapper that kept executing past the halt would write its output
        twice, which is what this pins.  For the dumping languages the
        first post-halt step is the dump, so the no-op under test is the
        step after that one -- and that the dump fires exactly once is
        itself part of the contract.
        """
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} has no self-halt")
        if language in RAISES_ON_THE_POST_HALT_STEP:
            pytest.xfail(f"{language}.step() raises IndexError past its halt")
        vm = make_vm(language, program, stdin)
        _drive(vm)
        if language in DUMPS_ON_THE_POST_HALT_STEP:
            vm.step()
        settled = vm.output
        vm.step()
        assert vm.halted
        assert vm.output == settled

    def test_the_post_halt_step_raises_only_where_recorded(
        self, language: str, program: str, stdin: str
    ) -> None:
        """The xfail set above is exact in both directions.

        Without this, a language whose ``step()`` grew an early return
        would keep its excuse forever, and the set would slowly become a
        list of languages nobody had rechecked.
        """
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} has no self-halt")
        vm = make_vm(language, program, stdin)
        _drive(vm)
        if language in DUMPS_ON_THE_POST_HALT_STEP:
            vm.step()
        try:
            vm.step()
        except IndexError:
            raised = True
        else:
            raised = False
        assert raised == (language in RAISES_ON_THE_POST_HALT_STEP)

    def test_the_halting_convention_matches_what_the_vm_reports(
        self, language: str, program: str, stdin: str
    ) -> None:
        """``vm.self_halts`` is exact against the set above, both ways.

        The trait is what a caller outside this suite reads, so the two
        have to say the same thing.  Only a declaration check is possible
        here: a language claiming it never halts cannot be *proved* not to
        by stepping it, which is the whole reason the fact is declared.
        """
        vm = make_vm(language, program, stdin)
        assert vm.self_halts == (language not in NEVER_SELF_HALTS)

    def test_the_dump_convention_matches_what_the_vm_reports(
        self, language: str, program: str, stdin: str
    ) -> None:
        """``vm.dumps_on_the_post_halt_step`` is exact, and is behavioural.

        Unlike the halting trait this one is checkable against the machine
        itself: driving to the halt writes everything ``run`` writes,
        except on the four, where the last step is still owed.  So the
        declaration is compared against what the language actually does --
        a machine whose dump moved back into ``run`` would fail here rather
        than keeping a trait nobody rechecked.
        """
        vm = make_vm(language, program, stdin)
        assert vm.dumps_on_the_post_halt_step == (
            language in DUMPS_ON_THE_POST_HALT_STEP
        )
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} has no self-halt to drive to")
        if language in RAISES_ON_THE_POST_HALT_STEP:
            pytest.xfail(f"{language}.step() raises IndexError past its halt")
        at_halt = _drive(vm)
        vm.step()
        assert (vm.output != at_halt) == vm.dumps_on_the_post_halt_step

    def test_snapshot_is_hashable(
        self, language: str, program: str, stdin: str
    ) -> None:
        """The state the cycle detector stores can go in a set.

        ``run_until_halt_or_cycle`` proves a hang by seeing a snapshot
        twice, so an unhashable snapshot -- a list of cells rather than a
        tuple of them -- silently disables hang detection for that
        language.
        """
        machine = _machine_of(make_vm(language, program, stdin))
        assert machine is not None, f"{language}'s adapter wraps no state object"
        hash(machine.snapshot())  # type: ignore[attr-defined]


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageImplementsTheSameInterface:
    """Structural conformance, as against the behavioural sweep above.

    The tests before this one drive a machine and check what it does.
    None of them would notice an adapter that satisfied the protocol only
    for the sample it was handed -- a ``memory`` that exists because the
    sample never asked for ``stack``, say.  These two ask the narrower
    question directly: does every language expose the *same* surface?

    ``_StepMachineWithShape`` is the interface ``_DelegatingVM`` forwards
    to, so a machine failing it is one the shared adapter cannot wrap, and
    the language would need per-language code back in ``vm.py`` -- which
    is exactly what deriving every adapter from ``RUNNERS`` removed.

    Both protocols are ``runtime_checkable``, so ``isinstance`` checks that
    the members are *present*, not that their signatures or return types
    match.  Types are mypy's half of this; the sweeps above are what pin
    the behaviour behind the names.
    """

    def test_the_wrapped_machine_implements_the_shape_protocol(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Every interpreter describes its own VM shape.

        ``ip``/``memory``/``stack`` live on the interpreter rather than in
        ``vm.py``; a machine missing one of them cannot be wrapped by the
        derived adapter at all.
        """
        machine = _machine_of(make_vm(language, program, stdin))
        assert machine is not None, f"{language}'s adapter wraps no state object"
        assert isinstance(machine, _StepMachineWithShape)

    def test_the_vm_implements_the_public_protocol(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Every language's wrapper satisfies the published ``VM``.

        ``test_vm.py`` asserted this for brainfuck.  One language passing
        says nothing about the other sixty-two, which is the whole reason
        the checks in this file are swept.
        """
        assert isinstance(make_vm(language, program, stdin), VM)


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageIsPure:
    """A run is a function of ``(program, stdin)`` and nothing else.

    The interpreters are not pure in the literal sense -- ``step()``
    mutates the machine in place and returns ``None``, by construction.
    The claim worth pinning is about the whole run: the same program on the
    same input lands in the same state, every time, no matter what else has
    run before or is running alongside it, and whatever it writes goes
    *only* through the ``ScriptedIO`` the VM handed it.

    "The same state" is all four of ``output``/``ip``/``memory``/``stack``,
    not output alone, because a language need not print to be running --
    A Painter Ant's sample writes nothing whatever, so an output-only
    comparison would pass on it for any interpreter at all.

    That is what makes the generator suites and the differential fuzzers
    mean anything.  A language holding state on its module or its class --
    a memo, a cached parse, a tape allocated once -- would still pass every
    test above, which builds one machine at a time and never asks whether
    a second one is affected by the first.

    None of the three is skipped for the never-halting languages: they are
    compared over a fixed step prefix instead of at a halt, so all
    sixty-three are covered.
    """

    def test_two_runs_end_in_the_same_state(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Determinism, at the VM boundary.

        ``LaserFuck`` is in :data:`NONDETERMINISTIC_AGAINST_RUN` because
        ``run`` draws its heading at random -- but ``make_vm`` passes a
        seeded source, so it is deterministic *here*, and is asserted to
        be rather than excused.  A language that started drawing from
        ``secrets`` behind the VM's back would fail this.
        """
        first = _settle(make_vm(language, program, stdin), language)
        second = _settle(make_vm(language, program, stdin), language)
        assert first == second

    def test_interleaved_machines_do_not_disturb_each_other(
        self, language: str, program: str, stdin: str
    ) -> None:
        """Two live machines of one language stay independent.

        This is the check determinism cannot make.  Running one machine to
        completion and then another would hide state shared on the class
        or the module -- the second run may reset it on the way in.
        Stepping both at once does not: whatever they share, they share
        while both are using it.
        """
        expected = _settle(make_vm(language, program, stdin), language)
        first = make_vm(language, program, stdin)
        second = make_vm(language, program, stdin)
        if language in NEVER_SELF_HALTS:
            for _ in range(_PREFIX_STEPS):
                first.step()
                second.step()
        else:
            for _ in range(_STEP_BUDGET):
                if first.halted and second.halted:
                    break
                if not first.halted:
                    first.step()
                if not second.halted:
                    second.step()
            else:
                raise AssertionError(f"no halt within {_STEP_BUDGET} interleaved steps")
            if language in DUMPS_ON_THE_POST_HALT_STEP:
                first.step()
                second.step()
        assert _observe(first) == expected
        assert _observe(second) == expected

    def test_a_run_writes_nothing_to_the_real_streams(
        self, language: str, program: str, stdin: str
    ) -> None:
        """All output goes through the VM's ``ScriptedIO``, none past it.

        An interpreter reaching for ``print`` or ``sys.stdout`` directly
        would still show the right ``vm.output`` if it also wrote to the
        io object, and the sweeps above would pass.  It would also corrupt
        any caller's stdout -- the CLI's, a generator's -- so the absence
        of the second write is part of the contract.

        The redirect has to cover the dump step, which is where all four
        dumping languages do their writing: every one of them is still
        empty at the halt, so stopping there would run the check over a
        machine that had not written anything yet.  :func:`_settle` takes
        that step, which is why the whole call is inside the block.

        Not every sample writes at all -- eight of them only move memory --
        so what stops this sweep from being vacuous is the companion
        ``test_most_samples_write_something`` above, rather than a
        per-language assertion that would need a ninth exception set.
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            _settle(make_vm(language, program, stdin), language)
        assert out.getvalue() == ""
        assert err.getvalue() == ""
