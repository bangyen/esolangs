"""Circuit Diagram through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from tests.reference import REFERENCE
from tests.support.generator_support import evaluate_generated
from tests.support.samples import CIRCUIT_PRIME_TESTER, bits_of
from tests.vm.test_vm import _run_all


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
            evaluate_generated(REFERENCE, "01101001", timeout=10)
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
