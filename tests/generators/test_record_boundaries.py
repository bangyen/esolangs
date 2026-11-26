"""Arity-tagged programs consume one record on shared input."""

from io import BytesIO, StringIO

import pytest

from esolangs import ArgumentError, ExecutionLimits, Language
from esolangs.registry import LANGUAGES
from esolangs.registry._contracts import BooleanContract
from esolangs.runtime._input import InputFrame, read_input

FRAMED = [entry.name for entry in LANGUAGES.values() if entry.contract.frame_stdin]


@pytest.mark.parametrize("name", FRAMED)
def test_boolean_artifact_keeps_the_next_record(name):
    lang = Language(name)
    table = "0001"
    artifact = lang.generate(table)
    portable = lang.from_json(lang.to_json(artifact))
    prepared = lang.prepare(portable)
    second = lang.encode_inputs([1, 1])

    for row in range(4):
        first = lang.encode_inputs([row >> 1, row & 1])
        baseline = lang.run(artifact, stdin=first).unwrap()
        assert lang.read_answer(baseline.output) == table[row]
        assert lang.run(artifact, stdin=first + second).unwrap() == baseline

        text = StringIO(first + second)
        assert prepared.run(stdin=text).unwrap() == baseline
        assert text.read() == second

        binary = BytesIO((first + second).encode())
        limited = prepared.run(
            stdin=binary,
            limits=ExecutionLimits(max_steps=50_000, preparation_timeout=5),
        ).unwrap()
        assert limited.output == baseline.output
        assert limited.input_position == baseline.input_position == len(first)
        assert limited.input_past_end == baseline.input_past_end
        assert binary.read() == second.encode()


@pytest.mark.parametrize("name", FRAMED)
def test_isolated_boolean_artifact_keeps_the_next_record(name):
    lang = Language(name)
    artifact = lang.generate("0001")
    first = lang.encode_inputs([0, 0])
    second = lang.encode_inputs([1, 1])
    stream = BytesIO((first + second).encode())

    result = lang.run(artifact, stdin=stream, isolated=True).unwrap()

    assert lang.read_answer(result.output) == "0"
    assert result.input_position == len(first)
    assert stream.read() == second.encode()


def test_framed_input_accepts_a_partial_record():
    frame = InputFrame(2, lines=True)

    assert read_input("first\nsecond", frame=frame) == "first\nsecond"
    assert read_input(BytesIO(b"first\nsecond"), frame=frame) == "first\nsecond"


def test_framed_input_counts_decoded_characters():
    stream = BytesIO("éλtail".encode())

    assert read_input(stream, frame=InputFrame(2, lines=False)) == "éλ"
    assert stream.read() == b"tail"


@pytest.mark.parametrize(
    ("chunks", "message"),
    [
        ((b"\xc3", "é"), "changed from bytes to text"),
        ((42,), "must return a string or bytes"),
        (("ab",), r"too much input for read\(1\)"),
    ],
)
def test_framed_input_rejects_invalid_reader_responses(chunks, message):
    class Reader:
        def read(self, size):
            assert size == 1
            return next(responses)

    responses = iter(chunks)
    with pytest.raises(ArgumentError, match=message):
        read_input(Reader(), frame=InputFrame(1, lines=False))


@pytest.mark.parametrize(
    "contract",
    [
        BooleanContract(frame_stdin=True, input_shape="row_number"),
        BooleanContract(frame_stdin=True, input_shape="row_index"),
        BooleanContract(frame_stdin=True, alphabet=("no", "yes")),
        BooleanContract(
            frame_stdin=True, input_shape="char_stream", alphabet=("αβ", "γδ")
        ),
        BooleanContract(
            frame_stdin=True, input_shape="char_stream", alphabet=("a", "βγ")
        ),
    ],
)
def test_encoding_frames_its_own_adjacent_records(contract):
    first = contract.encode_row("test", [0, 1])
    second = contract.encode_row("test", [1, 0])
    frame = contract.input_frame(2)
    assert frame.prefix(first + second) == first
    for stream in (StringIO(first + second), BytesIO((first + second).encode())):
        assert read_input(stream, frame=frame) == first
        assert read_input(stream, frame=frame) == second
        assert read_input(stream, frame=frame) == ""
