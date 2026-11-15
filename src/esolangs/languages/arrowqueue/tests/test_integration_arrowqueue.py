"""ArrowQueue through the shared API, CLI and machinery."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from tests.support.evaluation import _evaluate


@pytest.mark.medium
def test_run_does_not_wait_for_stdin_eof(tmp_path: Path) -> None:
    path = tmp_path / "program"
    path.write_text("~")
    reader, writer = os.pipe()
    with os.fdopen(reader, "rb") as source, os.fdopen(writer, "wb"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "esolangs",
                "run",
                "--execution-timeout",
                "2",
                "ArrowQueue",
                str(path),
            ],
            stdin=source,
            capture_output=True,
            timeout=10,
            check=False,
        )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"0", b"")


def test_termination_input_exhaustion_is_a_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exhausted(*_args: object, **_kwargs: object) -> None:
        raise esolangs.InputExhaustedError(2, 1)

    program = esolangs.generate("ArrowQueue", "01")
    monkeypatch.setattr("esolangs.runtime._termination._make_vm", exhausted)
    with pytest.raises(esolangs.InputExhaustedError) as exc:
        _evaluate("ArrowQueue", program, inputs=1)
    assert any("row 0" in note for note in exc.value.__notes__)


class TestArrowQueue:
    def test_ip_is_position_and_heading(self) -> None:
        vm = debugger_api.make_vm("ArrowQueue", "~+*")
        assert vm.ip == (0, 0, 0)
        vm.step()
        assert vm.ip == (0, 1, 0)
        assert vm.stack == [0]
        vm.step()  # + pops the queued direction (right) and keeps going
        assert vm.ip == (0, 2, 0)
        assert vm.stack == []
        vm.step()  # * turns down off the single row and halts
        assert vm.halted
        assert vm.memory == []
        vm.step()  # stepping a halted VM is a no-op
