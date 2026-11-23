"""SLOW ACV MAMMALIAN through the shared API, CLI and machinery."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
from esolangs import run
from esolangs.registry import _table
from tests.support.cli_support import _failure, call_both, run_cli


@pytest.mark.medium
@pytest.mark.parametrize("word", ["comment", "seed"])
def test_mammalian_rejects_unknown_words_before_output(word) -> None:
    with pytest.raises(ValueError, match="unknown SLOW ACV MAMMALIAN command"):
        run(
            "SLOW ACV MAMMALIAN",
            f"PRONOUNCE {word}",
            limits=esolangs.ExecutionLimits(execution_timeout=1),
        )


def test_partial_overrides_merge_and_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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

    declaration = language.catalog.languages[language.name]
    runtime = declaration.runtime
    error = esolangs.ArgumentError("local dialect forbids both moduli being 255")
    error.add_note("hint: choose a modulus of 256")

    def validate(**choices):
        if choices.get("cell_modulus") == choices.get("io_modulus") == 255:
            raise error
        runtime.dialect(**choices)

    scoped = replace(declaration, runtime=replace(runtime, dialect=validate))
    scope = esolangs.Catalog([scoped]).bind(language.name)
    partial = scope.settings(cell_modulus=255)
    assert partial.options() == {"cell_modulus": 255}
    row = "SEED ACCEPT DIGEST PRONOUNCE"

    class Unread:
        def read(self):
            pytest.fail("invalid effective settings consumed input")

    refused = scope.execute(row, stdin=Unread(), settings=partial)
    assert refused.status == "rejected"
    assert refused.error is error
    with pytest.raises(esolangs.ArgumentError) as generated_error:
        scope.generate("01", settings=partial)
    assert generated_error.value is error

    retained = scope.from_source(row, settings=scope.settings(io_modulus=256))
    assert scope.prepare(retained, settings=partial).run(stdin="ÿ\n").output == "\x01"
    full = scope.settings(cell_modulus=255, io_modulus=256)
    artifact = scope.generate("01", settings=full)
    assert scope.evaluate(artifact, [1]).answer == "1"

    path = tmp_path / "program.txt"
    path.write_text(row)
    monkeypatch.setattr(_table, "CATALOG", scope.catalog)
    command = ["run", "--set", "cell_modulus=255", language.name, str(path)]
    output, diagnostic = _failure(command, capsys)
    assert output == ""
    assert diagnostic.splitlines() == [str(error), *error.__notes__]
    assert call_both([*command, "--set", "io_modulus=256"], capsys, "ÿ\n") == (
        "\x01",
        "",
    )

    rejected = json.dumps({"cell_modulus": 255, "io_modulus": 255})
    for options in (
        ["--set", "cell_modulus=255", "--set", "io_modulus=255"],
        ["--settings", rejected],
        ["-s", rejected],
    ):
        for cmd, operand in (("run", str(path)), ("generate", "01")):
            output, diagnostic = _failure(
                [cmd, *options, language.name, operand], capsys
            )
            assert output == ""
            assert diagnostic.splitlines() == [str(error), *error.__notes__]

    generated, diagnostic = call_both(
        ["generate", "-s", json.dumps(full.options()), language.name, "01"], capsys
    )
    assert '--settings={"cell_modulus":255,"io_modulus":256}' in diagnostic
    assert (
        scope.run(generated, stdin=scope.encode_inputs([1]), settings=full).output
        == "1"
    )

    schema = runtime.dialect_schema
    assert schema is not None
    bad_defaults = esolangs.DialectSchema(
        language.name, schema.choices, schema.defaults | {"cell_modulus": 255}
    )
    default_runtime = replace(scoped.runtime, dialect_schema=bad_defaults)
    default_scope = esolangs.Catalog([replace(scoped, runtime=default_runtime)]).bind(
        language.name
    )
    stored = default_scope.from_json(
        default_scope.to_json(default_scope.from_file(path))
    )
    assert stored.settings is None
    for limits in (None, esolangs.ExecutionLimits(max_steps=10)):
        outcome = default_scope.execute(stored, stdin=Unread(), limits=limits)
        assert outcome.status == "rejected"
        assert outcome.error is error
    for use in (
        lambda: default_scope.generate("01"),
        lambda: default_scope.prepare(stored),
        lambda: esolangs.PreparedProgram(stored, default_scope.catalog),
        lambda: default_scope.make_vm(stored, stdin=Unread()),
    ):
        with pytest.raises(esolangs.ArgumentError) as caught:
            use()
        assert caught.value is error

    override = default_scope.settings(io_modulus=256)
    assert (
        default_scope.prepare(stored, settings=override).run(stdin="ÿ\n").output
        == "\x01"
    )
    monkeypatch.setattr(_table, "CATALOG", default_scope.catalog)
    output, diagnostic = _failure(["run", language.name, str(path)], capsys)
    assert output == ""
    assert diagnostic.splitlines() == [str(error), *error.__notes__]


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
