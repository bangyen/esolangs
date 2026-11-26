"""Compare each lowered instruction with its original command boundaries."""

from bisect import bisect_left

import pytest

from esolangs.exceptions import InputExhaustedError
from esolangs.languages.brainfuck import _native
from esolangs.languages.brainfuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


def _compare(source, stdin, *, budget=10000):
    reference_io, native_io = ScriptedIO(stdin), ScriptedIO(stdin)
    reference = _Machine(source, reference_io)
    spans = []
    ops = _native._compile_ops(source, reference.brackets, spans=spans)
    starts = [first for first, _ in spans]
    tape = bytearray(1)
    state = (0, 0)
    steps = 0
    span = (0, 0)
    while True:
        # Comments and cancelled arithmetic have no compiled instruction.
        expected = bisect_left(starts, reference.ip)
        boundary = starts[expected] if expected < len(starts) else len(source)
        while reference.ip < boundary:
            reference.step()
            steps += 1
            assert steps <= budget, span
        ip, ptr = state
        padding = ptr - reference.ptr
        assert ip == expected, span
        assert padding >= 0, span
        assert not any(tape[:padding]), span
        assert tuple(tape[padding:]) == reference.tape, span
        assert native_io.progress() == reference_io.progress(), span
        assert native_io.getvalue() == reference_io.getvalue(), span
        if ip == len(ops):
            assert reference.halted, span
            return
        span = spans[ip]
        before = reference.snapshot()
        try:
            while True:
                reference.step()
                steps += 1
                assert steps <= budget, span
                if not span[0] < reference.ip < span[1]:
                    break
        except InputExhaustedError as error:
            assert reference.snapshot() == before, span
            assert _native._advance_compiled(state, ops, tape)[3], span
            with pytest.raises(type(error)) as native_error:
                native_io.input_char()
            assert str(native_error.value) == str(error), span  # noqa: PT017
            assert native_io.progress() == reference_io.progress(), span
            return
        moved, effects, output, needs_input = _native._advance_compiled(
            state, ops, tape
        )
        if needs_input:
            moved, effects, output, _ = _native._advance_compiled(
                state, ops, tape, native_io.input_char()
            )
        prefix, suffix, writes = effects
        tape[:0] = bytes(prefix)
        tape.extend(bytes(suffix))
        for cell, value in writes:
            tape[cell] = value
        if output is not None:
            native_io.print_char(output)
        state = moved


@pytest.mark.parametrize(
    ("source", "stdin"),
    [
        ("comment+-", ""),
        ("[>++<-]>.<", ""),
        ("+++[>++<-]>.[-][+]", ""),
        ("<<<++>>>>><<<[->+<]>.", ""),
        (",[>,.<-]", "\x02A"),
        (",.,.", "🙂"),
        ("++[>++[>+<-]<-]>>.", ""),
    ],
)
def test_compiled_boundaries(source, stdin):
    _compare(source, stdin)


def test_difference_reports_the_first_faulty_source_span(monkeypatch):
    advance = _native._advance_compiled

    def changed(state, ops, tape, byte=None):
        moved, edits, output, read = advance(state, ops, tape, byte)
        if ops[state[0]][0] == _native._ADD:
            edits = (0, 0, ((state[1], 99),))
        return moved, edits, output, read

    monkeypatch.setattr(_native, "_advance_compiled", changed)
    with pytest.raises(AssertionError, match=r"\(2, 5\)"):
        _compare(">>+++.", "")


def test_compiled_boundaries_on_generated_two_input_tables():
    import esolangs

    for mask in range(16):
        program = esolangs.generate("Brainfuck", f"{mask:04b}")
        for bits in ((0, 0), (0, 1), (1, 0), (1, 1)):
            _compare(program.source, esolangs.encode_inputs("Brainfuck", bits))
