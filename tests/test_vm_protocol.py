r"""The VM protocol, swept over every language rather than per language."""

import contextlib
import io
from pathlib import Path
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

# The sweep drives every.
# hang the suite rather than.
# so in well under a hundred.
# into a readable failure.
_STEP_BUDGET = 100_000

_PARAMS = [
    pytest.param(name, program, stdin, id=name)
    for name, (program, stdin) in sorted(SAMPLES.items())
]


def _drive(vm: VM) -> str:
    r"""Step ``vm`` to its halt and return everything it wrote."""
    if not run_until_halt(vm, _STEP_BUDGET):
        raise AssertionError(f"no halt within {_STEP_BUDGET} steps")
    return vm.output


# The prefix the never-halting.
# halt.
# same state after the same.
# .
# Output alone will not do it.
# steps, but A Painter Ant's.
# steps and not at ten.
# so comparing its output would.
# matter what the interpreter.
# observable state as well,.
_PREFIX_STEPS = 100

# What a run is compared on:.
# ended up.
# copies rather than views into.
_Observed = tuple[str, object, list[int], list[object]]


def _observe(vm: VM) -> _Observed:
    r"""Return everything ``vm`` exposes about its current state."""
    return (vm.output, vm.ip, vm.memory, vm.stack)


def _settle(vm: VM, language: str) -> _Observed:
    r"""Drive ``vm`` as far as it goes and return its observable state."""
    if language in NEVER_SELF_HALTS:
        for _ in range(_PREFIX_STEPS):
            vm.step()
        return _observe(vm)
    _drive(vm)
    if language in DUMPS_ON_THE_POST_HALT_STEP:
        vm.step()
    return _observe(vm)


def _machine_of(vm: VM) -> object | None:
    r"""Return the interpreter state object an adapter wraps, if it has one."""
    for value in vars(vm).values():
        if hasattr(value, "snapshot"):
            return cast(object, value)
    return None


class TestSamplesCoverEveryLanguage:
    r"""The table is the sweep's coverage, so it is the thing to lock."""

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
        r"""A renamed language must not leave an exception silently inert."""
        assert sorted(exceptions - set(RUNNERS)) == []

    def test_most_samples_write_something(self) -> None:
        r"""The output-comparing sweeps are not comparing nothing."""
        writes = sum(
            bool(_settle(make_vm(name, program, stdin), name)[0])
            for name, (program, stdin) in SAMPLES.items()
        )
        assert writes >= 3 * len(SAMPLES) // 4


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageHonoursTheProtocol:
    r"""The shared invariants, once each, for every registry language."""

    def test_stepping_matches_running(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""A VM stepped to completion writes exactly what ``run`` writes."""
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} halts only on run's external limit")
        if language in NONDETERMINISTIC_AGAINST_RUN:
            pytest.skip(f"{language}'s run draws a random heading")
        expected = esolangs.run(language, program, stdin=stdin)
        vm = make_vm(language, program, stdin)
        _drive(vm)
        if language in DUMPS_ON_THE_POST_HALT_STEP:
            vm.step()  # the dump, which run performs.
        assert vm.output == expected

    def test_the_sample_reaches_a_halt(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""Every sample halts, which the sweeps above depend on."""
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} has no self-halt")
        vm = make_vm(language, program, stdin)
        _drive(vm)
        assert vm.halted

    def test_step_after_halt_is_a_noop(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""Stepping a halted machine neither raises nor writes anything more."""
        if language in NEVER_SELF_HALTS:
            pytest.skip(f"{language} has no self-halt")
        if language in RAISES_ON_THE_POST_HALT_STEP:
            pytest.xfail(f"{language}.step() raises IndexError past its halt")
        vm = make_vm(language, program, stdin)
        _drive(vm)
        if language in DUMPS_ON_THE_POST_HALT_STEP:
            vm.step()
        settled = vm.output
        state = vm.snapshot()
        vm.step()
        assert vm.halted
        assert vm.output == settled
        assert vm.snapshot() == state

    def test_the_post_halt_step_raises_only_where_recorded(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""The xfail set above is exact in both directions."""
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
        r"""``vm.self_halts`` is exact against the set above, both ways."""
        vm = make_vm(language, program, stdin)
        assert vm.self_halts == (language not in NEVER_SELF_HALTS)

    def test_the_dump_convention_matches_what_the_vm_reports(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""``vm.dumps_on_the_post_halt_step`` is exact, and is behavioural."""
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
        r"""The state the cycle detector stores can go in a set."""
        machine = _machine_of(make_vm(language, program, stdin))
        assert machine is not None, f"{language}'s adapter wraps no state object"
        hash(machine.snapshot())  # type: ignore[attr-defined]


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageImplementsTheSameInterface:
    r"""Structural conformance, as against the behavioural sweep above."""

    def test_a_positional_ip_says_what_it_counts(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""A machine reporting a tuple ``ip`` declares how to read it."""
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
        r"""A misspelled shape is the same silent failure one level up."""
        shape = make_vm(language, program, stdin).ip_shape
        assert shape in {"offset", "grid", "line", "opaque"}, (
            f"{language} declares ip_shape={shape!r}, which nothing reads"
        )

    def test_the_wrapped_machine_implements_the_shape_protocol(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""Every interpreter describes its own VM shape."""
        machine = _machine_of(make_vm(language, program, stdin))
        assert machine is not None, f"{language}'s adapter wraps no state object"
        assert isinstance(machine, _StepMachineWithShape)

    def test_the_vm_implements_the_public_protocol(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""Every language's wrapper satisfies the published ``VM``."""
        assert isinstance(make_vm(language, program, stdin), VM)


@pytest.mark.parametrize(("language", "program", "stdin"), _PARAMS)
class TestEveryLanguageIsPure:
    r"""A run is a function of ``(program, stdin)`` and nothing else."""

    def test_two_runs_end_in_the_same_state(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""Determinism, at the VM boundary."""
        first = _settle(make_vm(language, program, stdin), language)
        second = _settle(make_vm(language, program, stdin), language)
        assert first == second

    def test_interleaved_machines_do_not_disturb_each_other(
        self, language: str, program: str, stdin: str
    ) -> None:
        r"""Two live machines of one language stay independent."""
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
        r"""All output goes through the VM's ``ScriptedIO``, none past it."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            _settle(make_vm(language, program, stdin), language)
        assert out.getvalue() == ""
        assert err.getvalue() == ""


class TestTheCoordinateOrderIsRowThenColumn:
    r"""``VM.ip``'s arity is unstable and the *order* is not, and only one."""

    def test_a_single_row_grid_moves_in_the_second_component(self) -> None:
        r"""Alight and Super SNUSP lay their programs on one row."""
        for name in ("Alight", "Super SNUSP"):
            program, stdin = _row_for(name)
            assert program.count("\n") == 0, name  # one row.
            assert _first_move(name, program, stdin)[0] == 0, name

    def test_a_downward_start_moves_in_the_first_component(self) -> None:
        r"""Dig, Flowchart, LaserFuck and Streetcode begin vertically."""
        for name in ("Dig", "Flowchart", "LaserFuck", "Streetcode"):
            program, stdin = _row_for(name)
            before, after = _first_move_pair(name, program, stdin)
            assert before[0] != after[0], name
            assert before[1] == after[1], name

    def test_the_docstring_says_so(self) -> None:
        r"""And says it without re-promising the arity that was retired."""
        doc = esolangs.VM.ip.__doc__ or ""
        assert "row then column" in doc
        assert "not stable within" in doc  # the older warning survives.


def _row_for(name: str) -> tuple[str, str]:
    r"""A runnable program and its stdin for a two-input table."""
    table = "0110"
    program = esolangs.generate(name, table)
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0], table)


def _first_move_pair(
    name: str, program: str, stdin: str
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    r"""The coordinate before and after the first move that changes it."""
    vm = esolangs.make_vm(name, program, stdin)
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
    r"""Which components changed on the first move, as a (row, col) pair."""
    before, after = _first_move_pair(name, program, stdin)
    return (before[0] != after[0], before[1] != after[1])


class TestAPathAndItsTextDifferOnTheTrailingNewline:
    r"""``run(lang, path)`` and ``run(lang, path.read_text())`` disagree."""

    def test_they_disagree_where_a_newline_is_not_legal(self, tmp_path: Path) -> None:
        r"""CV(N)(C) has no newline in its alphabet, so it is the visible case."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110") + "\n")
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], "0110")
        assert esolangs.run("CV(N)(C)", path, stdin, 5) == "0"
        with pytest.raises(esolangs.ProgramError):
            esolangs.run("CV(N)(C)", path.read_text(), stdin, 5)

    def test_they_agree_without_one(self, tmp_path: Path) -> None:
        r"""The difference is the newline and nothing else."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110"))
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], "0110")
        assert esolangs.run("CV(N)(C)", path, stdin, 5) == esolangs.run(
            "CV(N)(C)", path.read_text(), stdin, 5
        )

    def test_the_docstring_says_so(self) -> None:
        r"""A surprise is only acceptable while it is written down."""
        assert "not quite the same argument" in (esolangs.run.__doc__ or "")
