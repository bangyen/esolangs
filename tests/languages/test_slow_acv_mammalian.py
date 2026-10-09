"""SLOW ACV MAMMALIAN through the shared API, CLI and machinery."""

import json

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.tagged import _Tagged
from tests.cli_support import call_both


@pytest.mark.medium
@pytest.mark.parametrize("command", ["run", "debug"])
def test_partial_override_inherits_cell_modulus(tmp_path, capsys, command):
    source = _Tagged(
        "SEED " * 255 + "DIGEST PRONOUNCE",
        "SLOW ACV MAMMALIAN",
        DialectSettings(cell_modulus=256, io_modulus=255),
    )
    path = tmp_path / "program.json"
    path.write_text(
        esolangs.dump_program("SLOW ACV MAMMALIAN", source), encoding="utf-8"
    )
    output, error = call_both(
        [
            command,
            "--portable",
            "--settings",
            '{"io_modulus":256}',
            "SLOW ACV MAMMALIAN",
            str(path),
        ],
        capsys,
    )
    assert error == ""
    if command == "run":
        assert output == chr(255)
    else:
        assert "halted: yes" in output
        assert "output: 'ÿ'" in output


@pytest.mark.medium
@pytest.mark.parametrize("word", ["comment", "seed"])
def test_mammalian_rejects_unknown_words_before_output(word):
    with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
        esolangs.run("SLOW ACV MAMMALIAN", f"PRONOUNCE {word}", timeout=1)


def test_partial_overrides_merge_and_validate():
    settings = DialectSettings(cell_modulus=256, io_modulus=255)
    source = _Tagged("SEED " * 255 + "DIGEST PRONOUNCE", "SLOW ACV MAMMALIAN", settings)
    assert esolangs.run("SLOW ACV MAMMALIAN", source) == chr(0)
    assert esolangs.run(
        "SLOW ACV MAMMALIAN", source, settings=DialectSettings(io_modulus=256)
    ) == chr(255)
    assert source.settings is settings
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(
            "SLOW ACV MAMMALIAN", source, settings=DialectSettings(cell_modulus=257)
        )
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run("SLOW ACV MAMMALIAN", source, settings={})


def test_large_integer_setting_is_rejected():
    document = json.loads(esolangs.dump_program("SLOW ACV MAMMALIAN", "SEED"))
    document["settings"] = {"cell_modulus": {"integer": hex(1 << 20_000)}}
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("SLOW ACV MAMMALIAN", json.dumps(document))
