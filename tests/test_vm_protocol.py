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

A fourth set, :data:`~tests.samples.RAISES_ON_THE_POST_HALT_STEP`, is not a
convention but the sweep's first finding: nine adapters raise
``IndexError`` when stepped past their halt instead of doing nothing, and
none of the fifteen hand-written copies of that check covered any of them.
It is carried as an xfail with a companion test pinning the set exactly, so
the gap is recorded rather than either hidden or silently widened.
"""

from typing import cast

import pytest

import esolangs
from esolangs.registry import RUNNERS
from esolangs.vm import VM, make_vm

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
    """Step ``vm`` to its halt and return everything it wrote."""
    for _ in range(_STEP_BUDGET):
        if vm.halted:
            return vm.output
        vm.step()
    raise AssertionError(f"no halt within {_STEP_BUDGET} steps")


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
