"""RAM0 through the shared API, CLI and machinery."""

import subprocess
import sys
from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs._evaluate import _evaluate
from tests.cli.test_cli import call_main
from tests.reference import REFERENCE
from tests.support.stdin_check import _check_stdin
from tests.vm.test_stepping_parity import _STEP_BUDGET, _row


def test_bound_template_language_runs_each_input_row():
    language = esolangs.Language("RAM0")
    template = language.generate("0110", width=1)
    assert _evaluate(language.name, template, timeout=None, inputs=2) == "0110"
    for row, answer in enumerate("0110"):
        bits = tuple(map(int, format(row, "02b")))
        program = language.instantiate(template, bits, width=1, truth_table="0110")
        assert language.read_answer(language.run(program, max_steps=1000)) == answer


# waits out real stdin timeouts: drives the CLI as a subprocess.
@pytest.mark.medium
class TestStdinCannotHangTheCommandForever:
    """`run` read stdin to EOF before doing anything, and --timeout missed it."""

    def _run_with_open_stdin(self, args: list[str], wait: float) -> tuple[int, str]:
        """Start the CLI with stdin held open and never written."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "esolangs", *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, ""
        finally:
            if proc.stdin:
                proc.stdin.close()
        return proc.returncode, proc.stderr.read() if proc.stderr else ""

    @pytest.mark.slow
    def test_a_timeout_bounds_the_read(self, tmp_path: Path) -> None:
        """It bounded execution only, and the block happens before that."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate(REFERENCE, "0110"))
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "2", REFERENCE, str(path)], 20
        )
        assert code == 124
        assert "no input arrived on stdin" in err

    @pytest.mark.slow
    def test_an_unknown_language_is_named_without_reading_stdin(
        self, tmp_path: Path
    ) -> None:
        """It blocked forever before saying the one thing it already knew."""
        path = tmp_path / "p.txt"
        path.write_text("+.")
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "30", "NotALang", str(path)], 20
        )
        assert code == 2
        assert "unknown language" in err

    @pytest.mark.slow
    def test_a_language_that_reads_no_stdin_is_told_so(self, tmp_path: Path) -> None:
        """RAM0 embeds its inputs, so the wait was for input nobody wanted."""
        path = tmp_path / "p.txt"
        path.write_text(
            esolangs.instantiate("RAM0", esolangs.generate("RAM0", "0110"), [0, 1])
        )
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "2", "RAM0", str(path)], 20
        )
        assert code == 124
        assert "read no stdin" in err


@pytest.mark.medium
def test_execution_does_not_require_examples_or_docstrings(monkeypatch) -> None:
    from esolangs import _describe
    from esolangs.tools import examples

    def refuse_documentation(_language):
        raise AssertionError("execution requested documentation")

    program = esolangs.generate(REFERENCE, "0110")
    monkeypatch.setattr(_describe, "_spec", refuse_documentation)
    monkeypatch.setattr(examples, "BOOLEAN_EXAMPLES", {})
    assert esolangs.encode_inputs(REFERENCE, [0, 1]) == "01"
    _check_stdin(REFERENCE, "01", "0110")
    assert esolangs.read_answer("RAM0", "z: 1\nn: 0") == "1"
    assert _evaluate(REFERENCE, program, inputs=2) == "0110"


def test_the_debugger_mirrors_them_too() -> None:
    """Reading them meant reaching through ``.vm``, which decides nothing."""
    d = debugger_api.make_debugger("RAM0", _row("RAM0", "0110", [0, 1])[0])
    assert d.dumps_on_the_post_halt_step is True
    assert d.self_halts is True
    assert d.steppable_to_answer is True


def test_a_dump_is_reachable_without_touching_the_wrapped_vm() -> None:
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


def test_read_answer_finds_a_dumped_answer(capsys: pytest.CaptureFixture[str]) -> None:
    """RAM0's answer is its `z` register, three lines from the end."""
    program = esolangs.instantiate("RAM0", esolangs.generate("RAM0", "0110"), [0, 1])
    output = esolangs.run("RAM0", program, timeout=20)
    assert call_main(["read-answer", "RAM0"], capsys, stdin=output).strip() == "1"


def test_reading_a_dump_needs_no_parsing_by_the_caller() -> None:
    ram0 = "z: 1\nn: 1\nram: {\n    0: 0,\n    1: 1\n}"
    assert esolangs.read_answer("RAM0", ram0) == "1"
    assert esolangs.read_answer("RAM0", ram0.replace("z: 1", "z: 0")) == "0"
