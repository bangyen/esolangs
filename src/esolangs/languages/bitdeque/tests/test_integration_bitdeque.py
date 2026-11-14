"""Bitdeque through the shared API, CLI and machinery."""

import json
import pickle

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from tests.support.evaluation import _evaluate


class TestEveryDumpSaysWhereTheAnswerIs:
    """A dump prints the whole final state, so "where" is the question."""

    def test_bitdeques_note_is_true(self) -> None:
        """It claims the whole dump is the answer bit.  Check that, do not trust it."""
        note = str(esolangs.describe("Bitdeque").answer_convention)
        assert "the whole dump is the answer" in note
        template = esolangs.generate("Bitdeque", "0110")
        for combo in range(4):
            bits = [(combo >> (1 - i)) & 1 for i in range(2)]
            program = esolangs.instantiate("Bitdeque", template, bits)
            dump = run(
                "Bitdeque",
                program,
                stdin="",
                limits=esolangs.ExecutionLimits(execution_timeout=10),
            ).output
            assert dump == "0110"[combo], bits
            assert len(dump) == 1, dump


@pytest.mark.parametrize("template", [False, True])
def test_text_pickle_retains_settings(template) -> None:
    settings = esolangs.Language("Bitdeque").settings()
    source = esolangs.generate("Bitdeque", "0110", settings=settings)
    if not template:
        source = esolangs.instantiate("Bitdeque", source, [1, 0])
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings == settings
    assert type(restored) is type(source)
    if template:
        restored = esolangs.instantiate("Bitdeque", restored, [1, 0])
    assert run("Bitdeque", restored).output == "1"


def test_settings_through_explicit_template_and_override() -> None:
    settings = esolangs.Language("Bitdeque").settings()
    template = esolangs.generate("Bitdeque", "0110", settings=settings)
    assert not hasattr(template.source, "settings")
    explicit = esolangs.TemplateArtifact(
        template.source, template.language, template.bindings
    )
    filled = esolangs.instantiate("Bitdeque", explicit, [1, 0], settings=settings)
    assert filled.settings is settings
    assert run("Bitdeque", filled).output == "1"

    source = esolangs.generate("Brainfuck", "01")
    assert source.settings is None
    assert (
        run(
            "Brainfuck",
            source,
            stdin="1",
            settings=esolangs.Language("Brainfuck").settings(),
        ).output
        == "1"
    )
    filled = esolangs.instantiate(
        "Bitdeque", template, [1, 0], settings=esolangs.Language("Bitdeque").settings()
    )
    assert filled.settings == settings
    assert run("Bitdeque", filled).output == "1"


@pytest.mark.parametrize("restored", [False, True])
def test_balanced_bitdeque_setters(restored) -> None:
    settings = esolangs.Language("Bitdeque").settings()
    table = "10010110"
    program = esolangs.generate("Bitdeque", table, balance=True, settings=settings)
    for row, expected in enumerate(table):
        source = (
            esolangs.from_json("Bitdeque", esolangs.to_json("Bitdeque", program))
            if restored
            else program
        )
        bits = tuple(map(int, format(row, "03b")))
        filled = esolangs.instantiate(
            "Bitdeque", source, bits, truth_table=table, settings=settings
        )
        assert run("Bitdeque", filled, settings=settings).output == expected


@pytest.mark.medium
def test_filled_template_becomes_portable_text() -> None:
    source = esolangs.generate(
        "Bitdeque", "0110", settings=esolangs.Language("Bitdeque").settings()
    )
    filled = esolangs.instantiate("Bitdeque", source, [1, 0])
    document = esolangs.to_json("Bitdeque", filled)
    assert json.loads(document)["kind"] == "text"
    assert run("Bitdeque", esolangs.from_json("Bitdeque", document)).output == "1"


def test_foreign_language_is_rejected() -> None:
    source = esolangs.generate(
        "Bitdeque", "0110", settings=esolangs.Language("Bitdeque").settings()
    )
    with pytest.raises(esolangs.ProgramError):
        esolangs.to_json("Brainfuck", source)
    with pytest.raises(esolangs.ProgramError, match="program language"):
        esolangs.from_json("Brainfuck", esolangs.to_json("Bitdeque", source))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("char", 1),
        ("char", "$$"),
        ("setters", None),
        ("setters", [["x"]]),
        ("setters", [["x", "yy"]]),
        ("setters", []),
    ],
)
def test_invalid_template_fields(field, value) -> None:
    document = json.loads(
        esolangs.to_json("Bitdeque", esolangs.generate("Bitdeque", "0110"))
    )
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.from_json("Bitdeque", json.dumps(document))


@pytest.mark.medium
def test_bound_language_round_trip() -> None:
    language = esolangs.Language("Bitdeque")
    source = language.generate(
        "0110", settings=esolangs.Language("Bitdeque").settings()
    )
    document = language.to_json(source)
    restored = language.from_json(document)
    assert _evaluate(language.name, restored, inputs=2) == "0110"
    filled = language.instantiate(source, [1, 0])
    document = language.to_json(
        filled, settings=esolangs.Language("Bitdeque").settings()
    )
    assert language.run(language.from_json(document)).output == "1"


class TestBitdeque:
    def test_cursor_deque_and_register(self) -> None:
        vm = debugger_api.make_vm("Bitdeque", "PUSH INVERT")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [0])
        vm.step()  # PUSH appends the register
        assert (vm.ip, vm.memory) == (1, [0])
        vm.step()  # INVERT flips the register
        assert vm.stack == [1]
        assert vm.halted
        assert vm.output == ""  # the deque is not rendered until the next step
        vm.step()  # the post-halt step renders it, as run's own last step does
        assert vm.output == "0"
        vm.step()  # and rendering happens once, not once per step past the halt
        assert vm.output == "0"
