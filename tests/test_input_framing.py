"""Input framing changes acquisition while preserving generated functions."""

import importlib

import pytest

import esolangs
from esolangs import DialectSettings, Language
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import complete_vm, make_vm
from tests.cli_support import call_both

LANGUAGES = ["Unsquare", "Decleq", "AddSubJump", "Minifuck"]
STREAMS = LANGUAGES[:3]
ECHOES = [
    ("Unsquare", "io", "stack_based.unsquare"),
    ("Decleq", "-1 9 0 -2 9 0 0 0 10 0", "register_based.decleq"),
    ("AddSubJump", "8 -1 4 -7 -1 8 -1 -7 0", "register_based.addsubjump"),
    ("Minifuck", "<[<.[<.", "tape_based.minifuck"),
]
TOKENS = DialectSettings(input_framing="integer_tokens")


@pytest.mark.parametrize(("language", "source", "_module"), ECHOES)
def test_framing_witness_and_shared_cursor(language, source, _module):
    assert esolangs.run(language, source, stdin="A") == "A"
    assert esolangs.run(language, source, stdin="65") == (
        "\x16" if language == "Minifuck" else "6"
    )
    assert esolangs.run(language, source, stdin=" \n+65\t", settings=TOKENS) == "A"
    vm = make_vm(language, source, stdin="65 66", settings=TOKENS)
    assert complete_vm(vm, 100) == "A"
    assert vars(vm)["_machine"].io.input_num() == 66


@pytest.mark.parametrize(("_language", "source", "module"), ECHOES)
@pytest.mark.parametrize("framing", ["characters", "integer_tokens"])
def test_eof_and_bad_numeric_input(_language, source, module, framing):
    interpreter = importlib.import_module("esolangs.interpreters." + module)
    with pytest.raises(EOFError):
        interpreter.run(source, ScriptedIO(""), input_framing=framing)
    if framing == "integer_tokens":
        with pytest.raises(esolangs.ArgumentError, match="integer"):
            interpreter.run(source, ScriptedIO("A"), input_framing=framing)


@pytest.mark.parametrize("language", STREAMS)
def test_encoding_and_validation(language):
    bound = Language(language)
    assert esolangs.encode_inputs(language, [0, 1], "0110") == "01"
    encoded = bound.encode_inputs([0, 1], "0110", settings=TOKENS)
    assert encoded == "48\n49\n"
    bound.check_stdin(encoded, "0110", settings=TOKENS)
    bound.check_stdin(" +48\t0049 ", "0110", settings=TOKENS)
    bound.check_stdin("48", settings=TOKENS)
    for bad, text in [("A", "integer"), ("0 1", "48 and 49"), ("48", "2 tokens")]:
        with pytest.raises(esolangs.ArgumentError, match=text):
            bound.check_stdin(bad, "0110", settings=TOKENS)
    with pytest.raises(esolangs.ArgumentError, match="unexpected"):
        bound.check_stdin(encoded)


@pytest.mark.parametrize("language", LANGUAGES)
def test_invalid_settings_precede_acquisition(language):
    class Unreadable:
        def read(self):
            raise AssertionError("invalid settings acquired source")

    settings = DialectSettings(input_framing="bad")
    with pytest.raises(esolangs.ArgumentError, match="input_framing"):
        esolangs.run(language, Unreadable(), settings=settings)
    with pytest.raises(esolangs.ArgumentError, match="input_framing"):
        esolangs.generate(language, "01", settings=settings)
    with pytest.raises(esolangs.ArgumentError, match="input_framing"):
        esolangs.encode_inputs(language, [0], settings=settings)
    with pytest.raises(esolangs.ArgumentError, match="input_framing"):
        esolangs.check_stdin(language, "0", settings=settings)


def test_templates_still_embed_inputs():
    with pytest.raises(esolangs.ArgumentError, match="embeds"):
        esolangs.encode_inputs("Minifuck", [0], settings=TOKENS)
    with pytest.raises(esolangs.ArgumentError, match="embeds"):
        esolangs.check_stdin("Minifuck", "48", settings=TOKENS)


@pytest.mark.medium
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("framing", ["characters", "integer_tokens"])
@pytest.mark.parametrize("n", [1, 2, 3])
def test_generated_corpus(language, framing, n):
    settings = DialectSettings(input_framing=framing)
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        for balance in (False, True):
            source = esolangs.generate(
                language, table, settings=settings, balance=balance
            )
            assert esolangs.evaluate(language, source, inputs=n) == table


@pytest.mark.medium
@pytest.mark.parametrize("language", LANGUAGES)
def test_portable_isolated_evaluation(language):
    source = esolangs.generate(language, "0110", settings=TOKENS)
    restored = esolangs.load_program(language, esolangs.dump_program(language, source))
    assert esolangs.evaluate(language, restored, inputs=2, isolated=True) == "0110"
    assert (
        esolangs.evaluate(
            language,
            restored,
            inputs=2,
            settings=DialectSettings(input_framing="characters"),
        )
        == "0110"
    )


@pytest.mark.parametrize("language", STREAMS)
def test_cli_encoder_checker_answer_and_portable_judge(language, tmp_path, capsys):
    choices = '{"input_framing":"integer_tokens"}'
    encoded, _ = call_both(["encode", "--settings", choices, language, "10"], capsys)
    assert encoded == "49\n48\n"
    call_both(
        ["check-stdin", "--settings", choices, "--table", "0110", language],
        capsys,
        stdin=encoded,
    )
    output, _ = call_both(
        ["answer", "--settings", choices, language, "0110", "10"], capsys
    )
    assert output.strip() == "1"
    document, _ = call_both(
        ["generate", "--portable", "--settings", choices, language, "0110"], capsys
    )
    path = tmp_path / "program.json"
    path.write_text(document)
    output, _ = call_both(
        ["run", "--judge", "--portable", "--table", "0110", language, str(path)],
        capsys,
        stdin=encoded,
    )
    assert output.strip() == "1"
    output, error = call_both(
        ["debug", "--portable", "--table", "0110", language, str(path)],
        capsys,
        stdin=encoded,
    )
    assert "halted: yes" in output
    assert "output: '1'" in output
    assert error == ""


def test_cli_invalid_settings_precede_stdin(capsys, monkeypatch):
    def unread(*_args, **_kwargs):
        raise AssertionError("invalid settings consumed stdin")

    monkeypatch.setattr("esolangs.cli._read_stdin", unread)
    with pytest.raises(SystemExit):
        call_both(
            ["check-stdin", "--settings", '{"input_framing":"bad"}', "Unsquare"], capsys
        )


@pytest.mark.parametrize("language", LANGUAGES)
def test_metadata(language):
    choices = esolangs.describe(language)["dialect_settings"]["input_framing"]
    assert choices["default"] == "characters"
    assert choices["choices"] == ("characters", "integer_tokens")
