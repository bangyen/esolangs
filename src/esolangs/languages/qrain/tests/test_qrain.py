"""Qrain queue, output-bitstream and loop semantics, each output derived by hand."""

from dataclasses import replace

import pytest

from esolangs import ExecutionLimits, Language
from esolangs.exceptions import HaltError
from esolangs.languages.qrain import interpreter as native
from esolangs.languages.qrain.interpreter import run
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime._vm_adapter import _capture_workspace
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import native_runner
from tests.support.execution import assert_cycle_proof_replays
from tests.support.prepared_support import check_image_reuse

_run = native_runner(run)


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        (",.", "A", "A"),
        (",.", "", "\x00"),
        # The second '.' moves nothing from an empty queue.
        (",..", "A", "A"),
        (",.,.", "AB", "AB"),
        # '[-]' pops A's low bit 1; the rest of A is never printed.
        (",[-]>,.", "AB", "B"),
        # '[' on an empty queue (front 0) skips its body, so '-' never raises.
        ("[-]", "", ""),
        # '+' on an empty queue enqueues 1: one bit, short of a byte.
        ("+.", "", ""),
        # A's last seven bits (0,0,0,0,0,1,0) then B's first (0): 0x20.
        (",-.>,.", "AB", " "),
        # Output [1] pending makes '+' copy the front bit: 1,1,0,... = 3, then
        # the copy 1 and eight 0 bits leave 0,1,0,... = 2.
        ("+.>,+..>,.", "\x01\x00", "\x03\x02"),
        # ']' re-tests: 0x0b = 1,1,0,1,... pops two bits, six remain (0,1,0,...)
        # and with eight more zero bits give 0,1,0,0,0,0,0,0 = 2.
        (",[-].>,.", "\x0b\x00", "\x02"),
        ("ignored text", "", ""),
    ],
)
def test_semantics(code: str, stdin: str, expected: str) -> None:
    assert _run(code, stdin) == expected


def test_dequeue_of_empty_queue_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from esolangs.languages.qrain.tests.oracle_checks import check_raw_qrain

    check_raw_qrain()
    check_image_reuse(
        "Qrain",
        ",[-]>,.",
        native,
        "_prepare_source",
        monkeypatch,
        cases=(("AB", "B"), ("AZ", "Z"), ("AQ", "Q")),
    )
    with pytest.raises(HaltError):
        _run("<-")

    _check_output_retry(monkeypatch)
    assert_cycle_proof_replays("Qrain", ",.", ",.+[]", "1")


def _check_output_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    language = Language("Qrain")
    limits = ExecutionLimits(max_steps=8)
    write = ScriptedIO._write
    attempts: list[object] = []
    prefix_output = ""

    def reject_first(port: ScriptedIO, value: object) -> None:
        attempts.append(value)
        if len(attempts) == 1:
            write(port, prefix_output)
            raise HaltError("temporary writer refusal")
        write(port, value)

    for source, stdin, char, prefix, eof in (
        ("+.>,.", "A", "\x83", 4, 0),
        (",.", "", "\x00", 1, 1),
    ):
        clean = language.make_debugger(source, stdin=stdin)
        assert clean.run(limits=limits) == "halted"
        assert clean.observation.output == char
        assert clean.observation.input_past_end == eof
        for accepted in (0, 1):
            replay = language.make_debugger(source, stdin=stdin)
            for _ in range(prefix):
                replay.step()
            before = replay.observation
            boundary = replay.snapshot()
            workspace = _capture_workspace(replay.vm)
            control, *workspace_state = workspace.parts
            assert isinstance(control, tuple)
            attempts.clear()
            prefix_output = char[:accepted]

            with monkeypatch.context() as scoped:
                scoped.setattr(ScriptedIO, "_write", reject_first)
                with pytest.raises(HaltError, match="temporary writer refusal") as exc:
                    replay.step()
                partial = replace(before, output=prefix_output)
                assert exc.value.observation == replay.observation == partial
                if accepted:
                    assert replay.snapshot() == (*boundary, accepted)
                    assert _capture_workspace(replay.vm).parts == (
                        WorkspaceVariant("pending_output", (*control, accepted)),
                        *workspace_state,
                    )
                else:
                    assert replay.snapshot() == boundary
                    assert _capture_workspace(replay.vm) == workspace
                assert replay.run(limits=limits) == "halted"
            assert attempts == [char] * (2 - accepted)
            assert replay.observation == clean.observation
            assert replay.snapshot() == clean.snapshot()
            assert _capture_workspace(replay.vm) == _capture_workspace(clean.vm)
            assert exc.value.observation == partial
