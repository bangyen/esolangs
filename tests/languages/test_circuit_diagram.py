"""Circuit Diagram through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.tui import History, Mark, render
from esolangs.tui_loop import drive
from tests.samples import CIRCUIT_PRIME_TESTER, bits_of
from tests.test_tui import _drive, _frame, _highlighted, _Keys, _marked_break, _selected
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
