"""Unit tests for the A Painter Ant interpreter."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.languages.a_painter_ant import interpreter as native_interpreter
from esolangs.languages.a_painter_ant.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import EmptyProgramContract
from tests.support.execution import run_observed


def run_program(code: str, passes: int = 1) -> str:
    """Step ``code`` for exactly ``passes`` whole cycles and render."""
    machine = _Machine(code)
    span = len(machine.prog)
    for _ in range(passes * span):
        machine.step()
    return machine.render()


class TestMovement:
    def test_lowercase_moves_on_black_and_uppercase_does_not(self) -> None:
        assert run_program("n") == "o\n."  # n/e/s/w move onto adjacent black
        assert run_program("s") == ".\no"
        assert run_program("e") == ".o"
        assert run_program("w") == "o."
        # N/E/S/W only move onto white; all cells start black, so no move.
        for command in "NSEW":
            assert run_program(command) == "o"

    def test_uppercase_moves_onto_white(self) -> None:
        assert run_program("nPsN") == "@\n."

    def test_conditional_movement_leaves_ant_in_place(self) -> None:
        # P whites the origin, n leaves, N finds a black cell north: no move.
        assert run_program("PnN") == "o\n#"


class TestPaintingAndLoop:
    def test_paint_then_move_writes_the_trail(self) -> None:
        # Each pass paints the current cell, then steps north and wraps.
        assert run_program("Pn", 3) == "o\n#\n#\n#"
        assert run_program("Pn", 4) == "o\n#\n#\n#\n#"

    def test_diamond_example(self) -> None:
        assert run_program("PnPwPsPe", 3) == ".##\n###\n##.\n.#o"

    def test_run_finds_the_first_repeated_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``run`` renders at the first pass boundary whose state repeats."""
        io = ScriptedIO()
        run("NPsP", io)
        assert io.getvalue() == run_program("NPsP", 2)
        assert io.getvalue() != run_program("NPsP", 1)

        language = esolangs.Language("A Painter Ant")
        source = "N P\nsP"
        expected = language.run(source)
        calls = []
        parse = native_interpreter._prepare_source

        def counted(code):
            calls.append(code)
            return parse(code)

        with monkeypatch.context() as patch:
            patch.setattr(native_interpreter, "_prepare_source", counted)
            prepared = language.prepare(source)
            first, second = prepared.make_vm(), prepared.make_vm()
            before = second.snapshot()
            first.step()
            first.step()
            assert first.snapshot() != before
            assert second.snapshot() == before
            assert prepared.run() == expected
            assert prepared.execute().unwrap() == expected
            assert calls == [source]

        from .oracle_checks import _check

        empty = run_observed("A Painter Ant", "", timeout=5)
        _check(
            _Machine,
            "",
            passes=empty.completion.cycle.repeat_pass,
            cycle=empty.completion.cycle,
            output=empty.output,
        )

        checked = 0
        sample = None
        for inputs in (1, 2):
            for mask in range(1 << (1 << inputs)):
                table = f"{mask:0{1 << inputs}b}"
                template = esolangs.generate("A Painter Ant", table)
                for row in range(len(table)):
                    bits = [int(bit) for bit in f"{row:0{inputs}b}"]
                    source = esolangs.instantiate("A Painter Ant", template, bits)
                    native = run_observed("A Painter Ant", source, timeout=5)
                    cycle = native.completion.cycle
                    _check(
                        _Machine,
                        source.source,
                        passes=cycle.repeat_pass,
                        cycle=cycle,
                        output=native.output,
                    )
                    sample = source, native
                    checked += 1
        assert checked == 72
        source, native = sample
        cycle = native.completion.cycle
        for damaged in (
            replace(cycle, state=("wrong",)),
            replace(cycle, commands_per_pass=cycle.commands_per_pass + 1),
        ):
            with pytest.raises(AssertionError):
                _check(
                    _Machine,
                    source.source,
                    passes=damaged.repeat_pass,
                    cycle=damaged,
                    output=native.output,
                )
        with pytest.raises(AssertionError):
            _check(
                _Machine,
                source.source,
                passes=cycle.repeat_pass,
                cycle=cycle,
                output=native.output + "!",
            )


class TestFormat:
    def test_unknown_instruction_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown instruction"):
            run_program("Px", 10)


class TestStepMachine:
    def test_step_tracks_ip_grid_and_position(self) -> None:
        machine = _Machine("Pn")
        assert machine.halted is False
        assert machine.ip == 0
        machine.step()  # P whites the origin
        assert machine.ip == 1
        assert machine.grid[(0, 0)] == 1
        machine.step()  # n moves north
        assert machine.ip == 0  # wrapped past the last instruction
        assert (machine.x, machine.y) == (0, -1)

    def test_snapshot_is_a_hashable_complete_state(self) -> None:
        machine = _Machine("Pn")
        first = machine.snapshot()
        assert hash(first) is not None
        machine.step()
        assert machine.snapshot() != first  # the paint changed the state

    def test_blocked_instruction_loops_and_is_a_cycle(self) -> None:
        # N never fires (all cells start black), so the run revisits state.
        assert run_until_halt_or_cycle(_Machine("N")) is False


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    empty_output = "o"


class TestPainterAntDumpsOnce:
    def test_stepping_an_interrupted_machine_again_does_not_redump(self) -> None:
        """The picture is printed once, however often the machine is stepped."""
        io = ScriptedIO()
        machine = _Machine("Pn", io)
        machine.interrupt()
        machine.step()
        first = io.getvalue()
        assert first
        machine.step()
        machine.step()
        assert io.getvalue() == first


def test_workspace_ignores_cycle_cache_and_retains_visited_extent():
    machine = _Machine("pN")
    machine.step()
    saved = machine.workspace_snapshot()
    retained = {saved}
    machine._frozen = frozenset({((999, 999), 1)})
    machine.snapshot = lambda: ("unrelated cycle key",)
    assert machine.workspace_snapshot() == saved
    assert saved in retained
    assert saved.parts[0] == frozenset(machine.grid.items())
    machine.visited.add((-999, -999))
    assert machine.workspace_snapshot().parts == (
        *saved.parts[:-1],
        (-999, 0, -999, 0),
    )
    assert saved in retained
    machine = _Machine("ew")
    before, picture = machine.workspace_snapshot(), machine.render()
    machine.step()
    machine.step()
    assert before.parts[:-1] == machine.workspace_snapshot().parts[:-1]
    assert before != machine.workspace_snapshot()
    assert picture != machine.render()
