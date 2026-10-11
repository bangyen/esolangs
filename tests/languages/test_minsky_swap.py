"""Minsky Swap through the shared API, CLI and machinery."""

import esolangs
import esolangs.debugger as debugger_api
from tests.reference import REFERENCE
from tests.support.samples import SAMPLES


class TestARunFinishesTheDump:
    """Six languages finished a *run* holding an empty output."""

    @staticmethod
    def _dumping() -> list[str]:
        """The languages whose answer arrives after the halt, from the data."""
        return [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["dumps_on_the_post_halt_step"]
        ]

    def test_a_breakpoint_can_fire_on_the_dump_step_itself(self) -> None:
        """``run`` reports the breakpoint, not ``"halted"``, when it does."""
        program, stdin = SAMPLES["Minsky Swap"]
        plain = debugger_api.make_debugger("Minsky Swap", program, stdin=stdin)
        assert plain.run(timeout=10) == "halted"
        assert plain.output

        stopped = debugger_api.make_debugger("Minsky Swap", program, stdin=stdin)
        stopped.break_on_output(plain.output)
        assert stopped.run(timeout=10) == "breakpoint"
        assert stopped.output == plain.output

    def test_the_dumping_sets_are_distinct(self) -> None:
        """Named from the registry, and not the *dump answer* set."""
        assert "Minsky Swap" in self._dumping()
        mode = {
            n
            for n in esolangs.list_languages()
            if esolangs.describe(n)["answer_mode"] == "dump"
        }
        assert "Minsky Swap" in mode
        assert mode != set(self._dumping())

    def test_run_leaves_the_output_and_agrees_with_run(self) -> None:
        """The bug was invisible on the non-dumping languages; compare."""
        empty = []
        for name in self._dumping():
            program = esolangs.generate(name, "0110")
            if esolangs.describe(name)["parameterized"]:
                program, stdin = esolangs.instantiate(name, program, [0, 0]), ""
            else:
                stdin = esolangs.encode_inputs(name, [0, 0], truth_table="0110")
            debugger = debugger_api.make_debugger(name, program, stdin=stdin)
            assert debugger.run(timeout=30) == "halted"
            assert debugger.output == esolangs.run(
                name, program, stdin=stdin, timeout=30
            ), name
            if not debugger.output:
                empty.append(name)
        assert not empty

    def test_an_ordinary_language_takes_no_extra_step(self) -> None:
        """The step is a no-op elsewhere, but it would land in every watch."""
        debugger = debugger_api.make_debugger(REFERENCE, "+++.", stdin="")
        history = debugger.watch_cell(0)
        debugger.run(timeout=10)
        assert len(history) == 4  # three increments and the print, no more
