"""Arity-tagged programs consume one record on shared input."""

from io import BytesIO, StringIO

import pytest

from esolangs import ExecutionLimits, Language
from esolangs.registry import LANGUAGES

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
        baseline = lang.run(artifact, stdin=first)
        assert lang.read_answer(baseline.output) == table[row]
        assert lang.run(artifact, stdin=first + second) == baseline

        text = StringIO(first + second)
        assert prepared.run(stdin=text) == baseline
        assert text.read() == second

        binary = BytesIO((first + second).encode())
        limited = prepared.run(
            stdin=binary,
            limits=ExecutionLimits(max_steps=50_000, preparation_timeout=5),
        )
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

    result = lang.run(artifact, stdin=stream, isolated=True)

    assert lang.read_answer(result.output) == "0"
    assert result.input_position == len(first)
    assert stream.read() == second.encode()
