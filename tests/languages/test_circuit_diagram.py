"""Circuit Diagram through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.tui import History, Mark, render
from esolangs.tui_loop import drive
from tests.generator_support import evaluate_generated
from tests.samples import CIRCUIT_PRIME_TESTER, bits_of
from tests.test_tui import (
    _drive,
    _frame,
    _highlighted,
    _Keys,
    _marked_both,
    _marked_break,
    _selected,
)
from tests.test_vm import _run_all


class TestBreakAtWhereThereIsNoShape:
    """A machine with no position cannot disagree with a breakpoint's kind."""

    def test_a_language_with_no_ip_accepts_either_kind(self) -> None:
        """Circuit Diagram's ip is None, so there is nothing to compare."""
        program = esolangs.generate("Circuit Diagram", "0110")
        stdin = esolangs.encode_inputs("Circuit Diagram", [0, 1], truth_table="0110")
        debugger = debugger_api.make_debugger("Circuit Diagram", program, stdin=stdin)
        assert debugger.ip is None
        debugger.break_at(3)
        debugger.break_at((1, 2))


class TestSelector:
    """A selector that can reach where the run has not."""

    def test_it_starts_on_the_running_position(self) -> None:
        assert _selected(_drive("+++", "q").screens[0]) == ["+"]

    @pytest.mark.parametrize(
        ("keys", "expected"), [("l", ">"), ("j", "<"), ("ljhk", "+")]
    )
    def test_the_movement_keys_move_it(self, keys: str, expected: str) -> None:
        keyboard = _drive("+>\n<-", keys + "q")
        assert _selected(keyboard.screens[-1]) == [expected]

    def test_moving_does_not_move_the_run(self) -> None:
        assert "step 0" in _drive("+++", "lllq").headers()[-1]

    def test_it_stops_at_the_edges(self) -> None:
        keyboard = _drive("+++", "hhhhkkkkq")
        assert _selected(keyboard.screens[-1]) == ["+"]

    def test_stepping_snaps_it_back_to_the_run(self) -> None:
        keyboard = _drive("+>-<", "ll q")
        assert _selected(keyboard.screens[-1]) == [">"]

    def test_a_breakpoint_can_be_set_where_the_run_has_not_reached(self) -> None:
        keyboard = _drive("+>-<", "lltcq")
        assert "step 2" in keyboard.headers()[-1]

    def test_marking_ahead_paints_there_not_here(self) -> None:
        keyboard = _drive("+>-<", "lltq")
        assert _marked_break(keyboard.screens[-1]) == ["-"]
        assert _highlighted(keyboard.screens[-1]) == "+"

    def test_the_pane_follows_the_selector(self) -> None:
        program = "." * 400 + "@" + "." * 400
        screen = render(_frame(program, 0), width=60, picked=Mark(0, 400))
        assert _selected(screen) == ["@"]

    def test_a_language_with_no_position_has_no_selector(self) -> None:
        keyboard = _Keys("llq")
        drive(History("Circuit Diagram", "-.\n", ""), keyboard.read, keyboard.write)
        assert _selected(keyboard.screens[-1]) == []


class TestCircuitDiagram:
    def test_wire_values_are_per_generation_events(self) -> None:
        vm = debugger_api.make_vm(
            "Circuit Diagram", CIRCUIT_PRIME_TESTER, stdin=bits_of(3)
        )
        assert vm.ip is None  # nothing moves through a circuit
        assert vm.stack == []
        vm.step()
        assert vm.memory == [0, 0, 1, 1]  # the input port, most significant first
        assert _run_all(vm) == "1"

    def test_stepping_detects_exactly_the_primes(self) -> None:
        """The page's worked example, replayed a generation at a time."""
        detected = {
            n
            for n in range(16)
            if _run_all(
                debugger_api.make_vm(
                    "Circuit Diagram", CIRCUIT_PRIME_TESTER, stdin=bits_of(n)
                )
            )
            == "1"
        }
        assert detected == {2, 3, 5, 7, 11, 13}


class TestAFailedRowSaysWhichRow:
    """``execution exceeded the 0.2-second timeout`` and nothing else."""

    def test_the_note_names_the_row_and_the_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failure forced at a chosen row, since a real one lands on row 0."""
        real_run = esolangs.run

        def fail_on_the_sixth(
            language: str, program: object, stdin: str = "", timeout: object = None
        ) -> str:
            if stdin == "101":  # row 5 of an eight-row table
                raise esolangs.ExecutionTimeoutError("execution exceeded the bound")
            return real_run(language, program, stdin=stdin, timeout=timeout)  # type: ignore[arg-type]

        monkeypatch.setattr(esolangs, "run", fail_on_the_sixth)
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            evaluate_generated("brainfuck", "01101001", timeout=10)
        note = "\n".join(getattr(caught.value, "__notes__", []))
        assert "row 5 of 8" in note
        assert "inputs 101" in note
        assert "after 5 rows" in note
        assert "01101" in note  # the answers that did come back

    def test_a_real_timeout_carries_one_too(self) -> None:
        """Not only the stand-in: the path a caller actually hits."""
        from esolangs.interpreters.grid_based import circuit_diagram

        table = "".join(str(bin(r).count("1") & 1) for r in range(128))
        # A warm compile cache (another test, same worker) beats 5 ms a row.
        circuit_diagram._compile.cache_clear()  # noqa: SLF001
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            evaluate_generated("Circuit Diagram", table, timeout=0.005)
        note = "\n".join(getattr(caught.value, "__notes__", []))
        assert "row 0 of 128" in note


class TestToggleKey:
    def test_t_marks_the_position_the_run_is_on(self) -> None:
        keyboard = _drive("+++", " tq")
        assert _marked_both(keyboard.screens[-1]) == ["+"]
        assert "1 break" in keyboard.headers()[-1]
        assert "step 1" in keyboard.headers()[-1]

    def test_t_again_clears_it(self) -> None:
        keyboard = _drive("+++", "ttq")
        assert "break" not in keyboard.headers()[-1]

    def test_continue_does_not_stop_where_it_already_is(self) -> None:
        keyboard = _drive("+++", "tcq")
        assert "step 0" not in keyboard.headers()[-1]

    def test_a_language_with_no_position_cannot_be_marked(self) -> None:
        keyboard = _Keys("tq")
        drive(History("Circuit Diagram", "-.\n", ""), keyboard.read, keyboard.write)
        assert "break" not in keyboard.headers()[-1]

    def test_a_position_given_on_the_command_line_starts_marked(self) -> None:
        keyboard = _Keys("q")
        drive(History("brainfuck", "+>-<", ""), keyboard.read, keyboard.write, at=(2,))
        assert _marked_break(keyboard.screens[0]) == ["-"]
