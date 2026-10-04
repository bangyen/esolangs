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
kept empty; the execution check now steps every halted machine again
and fails directly if any of them regresses.
"""

import contextlib
import io
from pathlib import Path
from typing import cast

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.registry import INTERPRETERS
from esolangs.vm import VM, make_vm, run_until_halt

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
    instead, so every language is covered rather than two being skipped.
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

    def test_post_halt_exceptions_stay_empty(self) -> None:
        assert not RAISES_ON_THE_POST_HALT_STEP

    def test_every_registry_language_has_a_sample(self) -> None:
        assert sorted(set(INTERPRETERS) - set(SAMPLES)) == []

    def test_no_sample_names_a_language_the_registry_lost(self) -> None:
        assert sorted(set(SAMPLES) - set(INTERPRETERS)) == []

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
        assert sorted(exceptions - set(INTERPRETERS)) == []


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageHonoursTheProtocol:
    """Execute each sample once for the shared halt and snapshot contract."""

    def test_execution_and_post_halt_state(
        self, language: str, program: str, stdin: str
    ) -> None:
        vm = make_vm(language, program, stdin)
        assert vm.self_halts == (language not in NEVER_SELF_HALTS)
        assert vm.dumps_on_the_post_halt_step == (
            language in DUMPS_ON_THE_POST_HALT_STEP
        )
        machine = _machine_of(vm)
        assert machine is not None, f"{language}'s adapter wraps no state object"
        hash(machine.snapshot())  # type: ignore[attr-defined]
        if language in NEVER_SELF_HALTS:
            return

        at_halt = _drive(vm)
        assert vm.halted
        vm.step()
        assert (vm.output != at_halt) == vm.dumps_on_the_post_halt_step
        if language not in NONDETERMINISTIC_AGAINST_RUN:
            assert vm.output == esolangs.run(language, program, stdin=stdin)

        settled = _observe(vm)
        state = vm.snapshot()
        hash(machine.snapshot())  # type: ignore[attr-defined]
        vm.step()
        assert vm.halted
        assert _observe(vm) == settled
        assert vm.snapshot() == state


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageImplementsTheSameInterface:
    """Position metadata lets the debugger locate a moving instruction."""

    def test_a_positional_ip_says_what_it_counts(
        self, language: str, program: str, stdin: str
    ) -> None:
        """A machine reporting a tuple ``ip`` declares how to read it.

        This is the one convention here whose breach is *silent*.  Forget
        ``self_halts`` and a driving loop hangs; forget ``ip_shape`` and a
        tuple simply stops being drawable, so a new grid language would
        quietly lose its highlight and nothing else would change.

        The declaration exists because the value cannot be read without it.
        A cell, a call depth paired with a cursor, and a stack of one
        position per frame are all tuples of small ints, and six languages
        were marked in the *wrong* place for exactly as long as the screen
        tried to tell them apart by looking.
        """
        vm = make_vm(language, program, stdin)
        shapes = set()
        for _ in range(10):
            if vm.halted:
                break
            shapes.add(type(vm.ip))
            with contextlib.suppress(Exception):
                vm.step()
        if tuple in shapes:
            assert vm.ip_shape != "offset", (
                f"{language} reports a tuple ip but declares no ip_shape, "
                "so its position cannot be drawn"
            )

    def test_a_declared_ip_shape_is_one_the_reader_knows(
        self, language: str, program: str, stdin: str
    ) -> None:
        """A misspelled shape is the same silent failure one level up.

        ``locate`` answers an unknown shape with "not located", so
        ``ip_shape = "gird"`` would read exactly like declaring nothing.
        """
        shape = make_vm(language, program, stdin).ip_shape
        assert shape in {"offset", "grid", "line", "opaque"}, (
            f"{language} declares ip_shape={shape!r}, which nothing reads"
        )


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageIsPure:
    """Interleaved runs stay deterministic and write only through their IO."""

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
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
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
                    raise AssertionError(
                        f"no halt within {_STEP_BUDGET} interleaved steps"
                    )
                if language in DUMPS_ON_THE_POST_HALT_STEP:
                    first.step()
                    second.step()
            assert _observe(first) == expected
            assert _observe(second) == expected
        assert out.getvalue() == ""
        assert err.getvalue() == ""


class TestTheCoordinateOrderIsRowThenColumn:
    """``VM.ip``'s arity is unstable and the *order* is not, and only one
    of those was written down.

    The paragraph above it correctly refuses to promise a shape -- the
    registry has 1-, 2-, 3-, 4- and 6-tuples and six languages change
    mid-run -- which reads as though the order were unknowable too.  A
    reader worked it out by construction instead.
    """

    def test_a_single_row_grid_moves_in_the_second_component(self) -> None:
        """Alight and Super SNUSP lay their programs on one row.

        The only move they can make is along the column, so whichever
        component changes *is* the column -- no reasoning about headings
        required.
        """
        for name in ("Alight", "Super SNUSP"):
            program, stdin = _row_for(name)
            assert program.count("\n") == 0, name  # one row
            assert _first_move(name, program, stdin)[0] == 0, name

    def test_a_downward_start_moves_in_the_first_component(self) -> None:
        """Dig, Flowchart, LaserFuck and Streetcode begin vertically.

        The other half of the pincer: these cannot move along a row first,
        so the component that changes is the row.

        Flowchart is asked for a width: unconstrained it now answers with
        the two-row deque lookup, whose entry node sits on a row and steps
        along it, and only the tree the width brings back starts downward.
        """
        widths = {"Flowchart": 1}
        for name in ("Dig", "Flowchart", "LaserFuck", "Streetcode"):
            program, stdin = _row_for(name, widths.get(name))
            before, after = _first_move_pair(name, program, stdin)
            assert before[0] != after[0], name
            assert before[1] == after[1], name


def _row_for(name: str, width: int | None = None) -> tuple[str, str]:
    """A runnable program and its stdin for a two-input table."""
    table = "0110"
    program = (
        esolangs.generate(name, table)
        if width is None
        else esolangs.generate(name, table, width)
    )
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0], table)


def _first_move_pair(
    name: str, program: str, stdin: str
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The coordinate before and after the first move that changes it."""
    vm = debugger_api.make_vm(name, program, stdin)
    start = vm.ip
    assert isinstance(start, tuple)
    for _ in range(400):
        if vm.halted:
            break
        vm.step()
        here = vm.ip
        if isinstance(here, tuple) and len(here) >= 2 and here[:2] != start[:2]:
            return start[:2], here[:2]
    raise AssertionError(f"{name} never moved")


def _first_move(name: str, program: str, stdin: str) -> tuple[int, int]:
    """Which components changed on the first move, as a (row, col) pair."""
    before, after = _first_move_pair(name, program, stdin)
    return (before[0] != after[0], before[1] != after[1])


class TestPathAndTextTrailingNewline:
    """Path input strips one trailing newline; string input preserves it."""

    def test_lf_ignored_by_cvnc_makes_path_and_text_agree(self, tmp_path: Path) -> None:
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110", 3) + "\n")
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], "0110")
        assert esolangs.run("CV(N)(C)", path, stdin, 5) == "0"
        assert esolangs.run("CV(N)(C)", path.read_text(), stdin, 5) == "0"

    def test_they_agree_without_one(self, tmp_path: Path) -> None:
        """The difference is the newline and nothing else."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110"))
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], "0110")
        assert esolangs.run("CV(N)(C)", path, stdin, 5) == esolangs.run(
            "CV(N)(C)", path.read_text(), stdin, 5
        )
