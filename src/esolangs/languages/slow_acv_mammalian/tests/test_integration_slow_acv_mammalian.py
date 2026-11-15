"""SLOW ACV MAMMALIAN through the shared API, CLI and machinery."""

import json

import pytest

import esolangs
from esolangs import run
from tests.support.cli_support import run_cli


@pytest.mark.medium
@pytest.mark.parametrize("word", ["comment", "seed"])
def test_mammalian_rejects_unknown_words_before_output(word) -> None:
    with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
        run(
            "SLOW ACV MAMMALIAN",
            f"PRONOUNCE {word}",
            limits=esolangs.ExecutionLimits(execution_timeout=1),
        )


def test_partial_overrides_merge_and_validate() -> None:
    language = esolangs.Language("SLOW ACV MAMMALIAN")
    settings = language.settings(cell_modulus=256)
    source = esolangs.ProgramArtifact(
        "SEED " * 255 + "DIGEST PRONOUNCE", "SLOW ACV MAMMALIAN", settings=settings
    )
    assert run("SLOW ACV MAMMALIAN", source).output == chr(0)
    # A choice the artifact does not retain merges in; one it does is fixed.
    assert run(
        "SLOW ACV MAMMALIAN", source, settings=language.settings(io_modulus=256)
    ).output == chr(255)
    with pytest.raises(esolangs.ProgramError, match="cell_modulus=256, not 255"):
        run("SLOW ACV MAMMALIAN", source, settings=language.settings(cell_modulus=255))
    assert source.settings is settings
    with pytest.raises(esolangs.ArgumentError):
        run(
            "SLOW ACV MAMMALIAN",
            source,
            settings=esolangs.Language("SLOW ACV MAMMALIAN").settings(cell_modulus=257),
        )
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        run("SLOW ACV MAMMALIAN", source, settings={})


def test_large_integer_setting_is_rejected() -> None:
    document = json.loads(esolangs.to_json("SLOW ACV MAMMALIAN", "SEED"))
    document["settings"] = {"cell_modulus": {"integer": hex(1 << 20_000)}}
    with pytest.raises(esolangs.ProgramError):
        esolangs.from_json("SLOW ACV MAMMALIAN", json.dumps(document))


@pytest.mark.medium
def test_cli_repeated_set_uses_last_value(tmp_path) -> None:
    language = esolangs.Language("SLOW ACV MAMMALIAN")
    settings = language.settings(io_modulus=256)
    artifact = language.generate("01", settings=settings)
    path = tmp_path / "program.txt"
    language.to_file(artifact, path, normalize=True)
    overrides = ["--set", "io_modulus=bogus", "--set", "io_modulus=0x100"]

    generated = run_cli("generate", *overrides, language.name, "01")
    assert generated.returncode == 0, generated.stderr
    assert generated.stdout.encode("utf-8") == path.read_bytes()
    stdin = language.encode_inputs([1])
    executed = run_cli("run", *overrides, language.name, str(path), stdin=stdin)
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout == language.run(artifact, stdin=stdin).output == "1"

    refused = run_cli("generate", *overrides[2:], *overrides[:2], language.name, "01")
    assert refused.returncode == 2
    assert not refused.stdout
    assert "--set io_modulus needs an integer" in refused.stderr
