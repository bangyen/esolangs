"""Buffered byte boundaries for declared bit-tape machines."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._vm_adapter import _capture_workspace
from esolangs.runtime.io import ScriptedIO


def check_byte_lifecycle(name: str, set_command: str) -> None:
    """Check full bytes, final padding and idle completion through public routes."""
    for bits in range(1, 10):
        source = set_command + ";" * bits + " "
        debug = make_debugger(name, source)
        for _ in range(bits + 1):
            debug.step()
        assert not debug.halted
        assert debug.observation.completion is None
        assert debug.observation.steps == bits + 1
        assert debug.observation.output == ("\xff" if bits >= 8 else "")
        debug.step()
        expected = ("\xff" if bits >= 8 else "") + (
            chr((1 << (bits % 8)) - 1) if bits % 8 else ""
        )
        result, snapshot = debug.observation, debug.snapshot()
        assert result.output == expected
        assert result.completion is not None
        assert result.completion.kind is Completion.HALTED
        assert result.steps == bits + 2
        native = esolangs.run(name, source).unwrap()
        assert result == replace(native, steps=result.steps)
        assert esolangs.run(name, source, isolated=True).unwrap() == native
        debug.step()
        assert debug.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
        assert (debug.observation, debug.snapshot()) == (result, snapshot)
    retained = set_command == "1"
    cases = [
        (set_command + ",;", "", chr(int(retained)), 0, 0, 1),
        (",;" * 9, "\x80", "\x80" + chr(int(retained)), 1, 1, 1),
        (",;", "Ā", "\0", 1, 1, 0),
    ]
    for source, stdin, output, position, reads, past_end in cases:
        native = esolangs.run(name, source, stdin=stdin).unwrap()
        assert (
            native.output,
            native.input_position,
            native.input_reads,
            native.input_past_end,
        ) == (output, position, reads, past_end)
        debug = make_debugger(name, source, stdin=stdin)
        assert debug.run(limits=esolangs.ExecutionLimits(max_steps=100)) == "halted"
        assert debug.observation == replace(native, steps=debug.observation.steps)
        assert esolangs.run(name, source, stdin=stdin, isolated=True).unwrap() == native


def check_byte_retry(
    name: str,
    source: str,
    output: str,
    before_write: int,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdin: str = "",
    flush: bool = False,
) -> None:
    """Accept none or all of a byte, then resume with the same IO and state."""
    language = esolangs.Language(name)
    limits = esolangs.ExecutionLimits(max_steps=32)
    clean = language.make_debugger(source, stdin=stdin)
    assert clean.run(limits=limits) == "halted"
    assert clean.observation.output == output
    native = language.run(source, stdin=stdin).unwrap()
    assert clean.observation == replace(native, steps=clean.observation.steps)
    write = ScriptedIO._write
    attempts: list[object] = []
    prefix = ""

    def reject_first(port: ScriptedIO, value: object) -> None:
        attempts.append(value)
        if len(attempts) == 1:
            write(port, prefix)
            raise esolangs.HaltError("temporary byte refusal")
        write(port, value)

    for accepted in (0, 1):
        attempts.clear()
        prefix = output[:accepted]
        live = language.make_debugger(source, stdin=stdin)
        for _ in range(before_write):
            live.step()
        before, boundary = live.observation, live.snapshot()
        ip, memory = live.ip, live.memory
        with monkeypatch.context() as scoped:
            scoped.setattr(ScriptedIO, "_write", reject_first)
            with pytest.raises(esolangs.HaltError, match="byte refusal") as error:
                live.step()
            partial = replace(
                clean.observation if flush else before,
                output=prefix,
                completion=None,
                steps=before_write,
            )
            assert error.value.observation == live.observation == partial
            assert not live.halted
            assert (live.ip, live.memory) == (ip, memory)
            stopped = live.snapshot()
            if flush:
                assert stopped[:-2] == boundary[:-1]
                assert stopped[-2] == partial.input_position
                pending = stopped[-1]
                assert isinstance(pending, tuple)
                assert pending[-1] == accepted
            else:
                assert stopped == ((*boundary, accepted) if accepted else boundary)
            assert live.run(limits=limits) == "halted"
        assert attempts == [output[0], *output[accepted:]]
        assert live.observation == clean.observation
        assert live.snapshot() == clean.snapshot()
        assert _capture_workspace(live.vm) == _capture_workspace(clean.vm)
        assert error.value.observation == partial


def check_final_byte_retry(
    name: str, set_command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep the final command active after its flush fails, including input."""
    for source, stdin, prefix in (
        (";,", "\x01\x02", 1),
        (";,", "", 1),
        (";" + set_command, "", 1),
        (";[" + set_command + "]", "", 1),
    ):
        check_byte_retry(
            name, source, "\0", prefix, monkeypatch, stdin=stdin, flush=True
        )
    check_byte_retry(name, ";" * 8, "\0", 7, monkeypatch)
