"""Buffered byte boundaries for declared bit-tape machines."""

from dataclasses import replace

import esolangs
from esolangs.debugger import make_debugger
from esolangs.runtime._lifecycle import Completion


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
        native = esolangs.run(name, source)
        assert result == replace(native, steps=result.steps)
        assert esolangs.run(name, source, isolated=True) == native
        debug.step()
        assert debug.run(max_steps=0) == "halted"
        assert (debug.observation, debug.snapshot()) == (result, snapshot)
    retained = set_command == "1"
    cases = [
        (set_command + ",;", "", chr(int(retained)), 0, 0, 1),
        (",;" * 9, "\x80", "\x80" + chr(int(retained)), 1, 1, 1),
        (",;", "Ā", "\0", 1, 1, 0),
    ]
    for source, stdin, output, position, reads, past_end in cases:
        native = esolangs.run(name, source, stdin=stdin)
        assert (
            native.output,
            native.input_position,
            native.input_reads,
            native.input_past_end,
        ) == (output, position, reads, past_end)
        debug = make_debugger(name, source, stdin=stdin)
        assert debug.run(max_steps=100) == "halted"
        assert debug.observation == replace(native, steps=debug.observation.steps)
        assert esolangs.run(name, source, stdin=stdin, isolated=True) == native
