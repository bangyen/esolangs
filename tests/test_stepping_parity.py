"""The step path and :func:`esolangs.run` must agree, or say why they cannot."""

from __future__ import annotations

import pathlib
from importlib.resources import files

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.vm import machine_traits, run_until_halt

#: Enough for every generated boolean program in the suite to finish; the
#: slowest needs a few hundred thousand.
_STEP_BUDGET = 2_000_000


def _row(name: str, table: str, bits: list[int]) -> tuple[str, str]:
    """Return the ``(program, stdin)`` for one row, without naming a language."""
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, esolangs.generate(name, table), bits), ""
    return esolangs.generate(name, table), esolangs.encode_inputs(
        name, bits, truth_table=table
    )


def _drive(vm: debugger_api.VM) -> str:
    """Step ``vm`` to its answer, honouring the two traits that say how."""
    run_until_halt(vm, _STEP_BUDGET)
    if vm.dumps_on_the_post_halt_step:
        vm.step()
    return vm.output


class TestTheTraitsAreReportedBeforeAMachineExists:
    """A caller deciding *how* to drive should not have to build one first."""

    @pytest.mark.parametrize(
        "key", ["self_halts", "dumps_on_the_post_halt_step", "steppable_to_answer"]
    )
    def test_describe_carries_each_trait(self, key: str) -> None:
        """They were VM properties only, so seventeen needed bits to read one."""
        assert all(key in esolangs.describe(n) for n in esolangs.list_languages())

    def test_describe_agrees_with_the_machine(self) -> None:
        """The class attribute and the live wrapper must not drift apart."""
        for name in ("brainfuck", "Suffolk", "RAM0", "A Painter Ant", "LaserFuck"):
            facts = esolangs.describe(name)
            for key, value in machine_traits(name).items():
                assert facts[key] == value, (name, key)

    def test_a_painter_ant_is_the_one_that_cannot_be_stepped(self) -> None:
        """Stated as data: three million steps leave it with no output."""
        unsteppable = [
            n
            for n in esolangs.list_languages()
            if not esolangs.describe(n)["steppable_to_answer"]
        ]
        assert unsteppable == ["A Painter Ant"]

    def test_the_debugger_mirrors_them_too(self) -> None:
        """Reading them meant reaching through ``.vm``, which decides nothing."""
        d = debugger_api.make_debugger("RAM0", _row("RAM0", "0110", [0, 1])[0])
        assert d.dumps_on_the_post_halt_step is True
        assert d.self_halts is True
        assert d.steppable_to_answer is True


def _steppable_languages() -> list[str]:
    """Return the languages this file's parity sweeps compare, by the same rule."""
    return [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["boolean_generator"]
        and esolangs.describe(name)["steppable_to_answer"]
        and esolangs.describe(name)["answer_mode"] != "termination"
    ]


#: The floor the derived count has to clear.  Without it a filter that
#: admitted nothing would make ``checked == 0 == expected`` and pass.
_MIN_STEPPABLE = 50


class TestSteppingReachesTheSameAnswer:
    """The sweep that would have caught all seven at once."""

    @pytest.mark.slow
    def test_every_steppable_language_agrees_with_run(self) -> None:
        """58/65 was six refused dump steps and one raise, not seven wrong bits."""
        table = "0110"
        disagreed = []
        # Counted, because a filter that quietly excluded everything would
        # leave this passing on nothing at all.
        checked = 0
        languages = _steppable_languages()
        assert len(languages) >= _MIN_STEPPABLE, languages
        for name in languages:
            for row, bits in enumerate(([0, 0], [0, 1], [1, 0], [1, 1])):
                program, stdin = _row(name, table, bits)
                want = esolangs.run(name, program, stdin=stdin, timeout=30)
                try:
                    got = _drive(debugger_api.make_vm(name, program, stdin=stdin))
                except esolangs.EsolangError as exc:
                    disagreed.append(f"{name} row {row}: stepping raised {exc!r}")
                    continue
                checked += 1
                if got != want:
                    disagreed.append(f"{name} row {row}: stepped {got!r} ran {want!r}")
        assert not disagreed, "\n".join(disagreed)
        # Every admitted language on every row: anything that raised took
        # the ``except`` above and is missing from the count.
        assert checked == len(languages) * 4, checked

    def test_suffolk_no_longer_disagrees_with_itself(self) -> None:
        """``run`` answered and the debugger raised, for the same call."""
        table = "0110"
        for bits, want in (([0, 0], "0"), ([0, 1], "1"), ([1, 0], "1"), ([1, 1], "0")):
            program, stdin = _row("Suffolk", table, bits)
            assert esolangs.run("Suffolk", program, stdin=stdin, timeout=20) == want
            debugger = debugger_api.make_debugger("Suffolk", program, stdin=stdin)
            assert debugger.run(max_steps=_STEP_BUDGET) == "halted"
            assert debugger.output == want

    def test_a_dump_is_reachable_without_touching_the_wrapped_vm(self) -> None:
        """``Debugger.step`` returned early on ``halted``; the dump *is* that step."""
        program, _ = _row("RAM0", "0110", [0, 1])
        debugger = debugger_api.make_debugger("RAM0", program)
        assert debugger.run(max_steps=_STEP_BUDGET) == "halted"
        assert esolangs.read_answer("RAM0", debugger.output) == "1"
        # And the step after the dump is the no-op the docstring promises,
        # so a caller who does step again is not punished for it.
        before = debugger.output
        debugger.step()
        assert debugger.output == before


class TestStepPastHaltIsSafeEverywhere:
    """The claim that made the unconditional delegation defensible."""

    @pytest.mark.slow
    def test_no_language_faults_when_stepped_past_its_halt(self) -> None:
        """``Debugger.step`` now delegates always, so this must hold for all."""
        broke = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["boolean_generator"]:
                continue
            if not facts["steppable_to_answer"] or not facts["self_halts"]:
                continue
            if facts["answer_mode"] == "termination":
                continue
            program, stdin = _row(name, "0110", [0, 1])
            vm = debugger_api.make_vm(name, program, stdin=stdin)
            run_until_halt(vm, _STEP_BUDGET)
            if not vm.halted:
                continue
            settled = vm.output if not vm.dumps_on_the_post_halt_step else None
            try:
                for _ in range(3):
                    vm.step()
            except Exception as exc:
                broke.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            if settled is not None and vm.output != settled:
                broke.append(f"{name}: output changed past the halt")
        assert not broke, "\n".join(broke)


class TestTheConstructorsTakeWhatRunTakes:
    """``check_program`` was called and its *return value* thrown away."""

    @pytest.mark.parametrize(
        "build", [debugger_api.make_vm, debugger_api.make_debugger]
    )
    def test_a_path_is_read_rather_than_handed_to_the_interpreter(
        self, build: object
    ) -> None:
        """It validated the file's contents, then passed the Path itself on."""
        example = pathlib.Path(
            str(files("esolangs") / esolangs.describe("brainfuck")["examples"][0])
        )
        machine = build("brainfuck", example, stdin="1\n0\n")  # type: ignore[operator]
        assert machine.halted is False

    def test_the_path_and_the_source_build_the_same_machine(self) -> None:
        """Reading it here must match what a caller reading it gets."""
        example = pathlib.Path(
            str(files("esolangs") / esolangs.describe("brainfuck")["examples"][0])
        )
        source = example.read_text().rstrip("\n")
        from_path = _drive(debugger_api.make_vm("brainfuck", example, stdin="1\n0\n"))
        from_text = _drive(debugger_api.make_vm("brainfuck", source, stdin="1\n0\n"))
        assert from_path == from_text
