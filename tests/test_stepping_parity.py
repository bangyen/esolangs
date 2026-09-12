r"""The step path and :func:`esolangs.run` must agree, or say why they."""

from __future__ import annotations

import pathlib
from collections.abc import Callable

import pytest

import esolangs
from esolangs.vm import machine_traits, run_until_halt

# : Enough for every generated.
# : slowest needs a few hundred.
_STEP_BUDGET = 2_000_000


def _row(name: str, table: str, bits: list[int]) -> tuple[str, str]:
    r"""Return the ``(program, stdin)`` for one row, without naming a."""
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, esolangs.generate(name, table), bits), ""
    return esolangs.generate(name, table), esolangs.encode_inputs(name, bits, table)


def _drive(vm: esolangs.VM) -> str:
    r"""Step ``vm`` to its answer, honouring the two traits that say how."""
    run_until_halt(vm, _STEP_BUDGET)
    if vm.dumps_on_the_post_halt_step:
        vm.step()
    return vm.output


class TestTheTraitsAreReportedBeforeAMachineExists:
    r"""A caller deciding *how* to drive should not have to build one first."""

    @pytest.mark.parametrize(
        "key", ["self_halts", "dumps_on_the_post_halt_step", "steppable_to_answer"]
    )
    def test_describe_carries_each_trait(self, key: str) -> None:
        r"""They were VM properties only, so seventeen needed bits to read one."""
        assert all(key in esolangs.describe(n) for n in esolangs.list_languages())

    def test_describe_agrees_with_the_machine(self) -> None:
        r"""The class attribute and the live wrapper must not drift apart."""
        for name in ("brainfuck", "Suffolk", "RAM0", "A Painter Ant", "LaserFuck"):
            facts = esolangs.describe(name)
            for key, value in machine_traits(name).items():
                assert facts[key] == value, (name, key)

    def test_a_painter_ant_is_the_one_that_cannot_be_stepped(self) -> None:
        r"""Stated as data: three million steps leave it with no output."""
        unsteppable = [
            n
            for n in esolangs.list_languages()
            if not esolangs.describe(n)["steppable_to_answer"]
        ]
        assert unsteppable == ["A Painter Ant"]

    def test_the_debugger_mirrors_them_too(self) -> None:
        r"""Reading them meant reaching through ``.vm``, which decides nothing."""
        d = esolangs.make_debugger("RAM0", _row("RAM0", "0110", [0, 1])[0])
        assert d.dumps_on_the_post_halt_step is True
        assert d.self_halts is True
        assert d.steppable_to_answer is True


class TestSteppingReachesTheSameAnswer:
    r"""The sweep that would have caught all seven at once."""

    @pytest.mark.slow
    def test_every_steppable_language_agrees_with_run(self) -> None:
        r"""62/69 was six refused dump steps and one raise, not seven wrong."""
        table = "0110"
        disagreed = []
        # Counted, because a filter.
        # leave this passing on nothing.
        checked = 0
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            # The three that answer by.
            # so there is nothing for the.
            # run forever on half the rows,.
            if not facts["steppable_to_answer"]:
                continue
            if facts["answer_mode"] == "termination":
                continue
            for row, bits in enumerate(([0, 0], [0, 1], [1, 0], [1, 1])):
                program, stdin = _row(name, table, bits)
                want = esolangs.run(name, program, stdin, timeout=30)
                try:
                    got = _drive(esolangs.make_vm(name, program, stdin))
                except esolangs.EsolangError as exc:
                    disagreed.append(f"{name} row {row}: stepping raised {exc!r}")
                    continue
                checked += 1
                if got != want:
                    disagreed.append(f"{name} row {row}: stepped {got!r} ran {want!r}")
        assert not disagreed, "\n".join(disagreed)
        # 69 languages, less A Painter.
        # diverging, times four rows.
        assert checked == 65 * 4, checked

    def test_suffolk_no_longer_disagrees_with_itself(self) -> None:
        r"""``run`` answered and the debugger raised, for the same call."""
        table = "0110"
        for bits, want in (([0, 0], "0"), ([0, 1], "1"), ([1, 0], "1"), ([1, 1], "0")):
            program, stdin = _row("Suffolk", table, bits)
            assert esolangs.run("Suffolk", program, stdin, timeout=20) == want
            debugger = esolangs.make_debugger("Suffolk", program, stdin)
            assert debugger.run(max_steps=_STEP_BUDGET) == "halted"
            assert debugger.output == want

    def test_a_dump_is_reachable_without_touching_the_wrapped_vm(self) -> None:
        r"""``Debugger.step`` returned early on ``halted``; the dump *is* that."""
        program, _ = _row("RAM0", "0110", [0, 1])
        debugger = esolangs.make_debugger("RAM0", program)
        assert debugger.run(max_steps=_STEP_BUDGET) == "halted"
        assert esolangs.read_answer("RAM0", debugger.output) == "1"
        # And the step after the dump.
        # so a caller who does step.
        before = debugger.output
        debugger.step()
        assert debugger.output == before


class TestStepPastHaltIsSafeEverywhere:
    r"""The claim that made the unconditional delegation defensible."""

    @pytest.mark.slow
    def test_no_language_faults_when_stepped_past_its_halt(self) -> None:
        r"""``Debugger.step`` now delegates always, so this must hold for all."""
        broke = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["steppable_to_answer"] or not facts["self_halts"]:
                continue
            if facts["answer_mode"] == "termination":
                continue
            program, stdin = _row(name, "0110", [0, 1])
            vm = esolangs.make_vm(name, program, stdin)
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
    r"""``check_program`` was called and its *return value* thrown away."""

    @pytest.mark.parametrize("build", [esolangs.make_vm, esolangs.make_debugger])
    def test_a_path_is_read_rather_than_handed_to_the_interpreter(
        self, build: object
    ) -> None:
        r"""It validated the file's contents, then passed the Path itself on."""
        example = pathlib.Path(str(esolangs.describe("brainfuck")["examples"][0]))
        machine = build("brainfuck", example, "1\n0\n")  # type: ignore[operator]
        assert machine.halted is False

    def test_the_path_and_the_source_build_the_same_machine(self) -> None:
        r"""Reading it here must match what a caller reading it gets."""
        example = pathlib.Path(str(esolangs.describe("brainfuck")["examples"][0]))
        source = example.read_text().rstrip("\n")
        from_path = _drive(esolangs.make_vm("brainfuck", example, "1\n0\n"))
        from_text = _drive(esolangs.make_vm("brainfuck", source, "1\n0\n"))
        assert from_path == from_text


class TestTheEofTraitIsOnTheVmToo:
    r"""``describe`` reads the class; a driving caller holds the wrapper."""

    def test_the_wrapper_reports_it(self) -> None:
        r"""Same value from both, or one of them is lying."""
        for name in ("DINAC", "brainfuck"):
            program = esolangs.generate(name, "0110")
            stdin = esolangs.encode_inputs(name, [0, 1], "0110")
            vm = esolangs.make_vm(name, program, stdin)
            assert vm.eof_is_a_value == esolangs.describe(name)["eof_is_a_value"]


# : The arity and shapes the.
_WIDER_ARITY = 6

# : Four rows rather than all.
# : the program, not of the row.
# : row that reached the broken.
# : the second shape for a.
_WIDER_ROWS = (0, 1, 32, 63)


def _one_hot(n: int) -> str:
    r"""1 exactly where one input is set."""
    return "".join(str(int(bin(row).count("1") == 1)) for row in range(2**n))


def _one_minterm(n: int) -> str:
    r"""A single 1, which makes every input essential at minimum size."""
    return "1" + "0" * (2**n - 1)


@pytest.mark.slow
@pytest.mark.parametrize(
    "make", [_one_minterm, _one_hot], ids=["one_minterm", "one_hot"]
)
def test_stepping_agrees_at_a_wider_arity_and_shape(
    make: Callable[[int], str],
) -> None:
    r"""The sweep above uses ``0110`` -- two inputs, one shape."""
    table = make(_WIDER_ARITY)
    disagreed = []
    checked = 0
    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if not facts["steppable_to_answer"]:
            continue
        if facts["answer_mode"] == "termination":
            continue
        program = esolangs.generate(name, table)
        for row in _WIDER_ROWS:
            bits = [(row >> (_WIDER_ARITY - 1 - i)) & 1 for i in range(_WIDER_ARITY)]
            if facts["parameterized"]:
                source, stdin = esolangs.instantiate(name, program, bits), ""
            else:
                source, stdin = program, esolangs.encode_inputs(name, bits, table)
            want = esolangs.run(name, source, stdin, timeout=30)
            try:
                got = _drive(esolangs.make_vm(name, source, stdin))
            except esolangs.EsolangError as exc:
                disagreed.append(f"{name} row {row}: stepping raised {exc!r}")
                continue
            checked += 1
            if got != want:
                disagreed.append(f"{name} row {row}: stepped {got!r} ran {want!r}")
    assert not disagreed, "\n".join(disagreed)
    # A filter that quietly.
    assert checked == 65 * len(_WIDER_ROWS), checked
