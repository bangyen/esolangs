"""Unary through the shared API and generator contract."""

import pytest

import esolangs
from esolangs import run
from tests.support.cli_support import call_main


def test_describe_writes_no_raw_nul(capsys: pytest.CaptureFixture[str]) -> None:
    """Its zero bit is NUL; ``describe`` wrote it raw into the input line."""
    out = call_main(["describe", "Unary"], capsys)
    assert "\x00" not in out
    assert "\\x00" in out.splitlines()[1]


def test_unary_generator_declares_byte_inputs_and_termination_answers() -> None:
    description = esolangs.describe("Unary")
    assert description.input_encoding == ("\x00", "\xff")
    assert description.answer_mode == "termination"
    assert esolangs.encode_inputs("Unary", (0, 1)) == "\x00\xff"
    assert len(esolangs.generate("Unary", "01").source) == 887


def test_compressed_and_plain_sources_share_execution(tmp_path) -> None:
    program = esolangs.generate("Unary", "0001")
    assert isinstance(program.source, esolangs.CompressedText)
    assert len(program.source) == 27_452_351
    assert len(program.source.to_gzip()) == 26_712
    path = tmp_path / "and.txt.gz"
    esolangs.to_file("Unary", program, path)
    for source in (program, program.source.to_gzip(), path, str(program.source)):
        assert (
            run(
                "Unary",
                source,
                stdin="\x00\xff",
                limits=esolangs.ExecutionLimits(max_steps=20),
            ).output
            == ""
        )
    restored = esolangs.from_json("Unary", esolangs.to_json("Unary", program))
    assert isinstance(restored, esolangs.ProgramArtifact)
    assert isinstance(restored.source, esolangs.CompressedText)
    assert restored == program
    assert (
        run(
            "Unary",
            program,
            stdin="\x00\xff",
            isolated=True,
            limits=esolangs.ExecutionLimits(execution_timeout=5),
        ).output
        == ""
    )


def test_cli_exports_gzip_by_default_and_plain_on_request(tmp_path) -> None:
    import gzip
    import subprocess
    import sys

    command = [sys.executable, "-m", "esolangs", "generate", "Unary", "01"]
    options = {"capture_output": True, "timeout": 10}
    packed = subprocess.run(command, check=True, **options)
    plain = subprocess.run([*command, "--plain"], check=True, **options)
    assert str(esolangs.CompressedText(packed.stdout)) == "0" * 887
    assert plain.stdout == b"0" * 887
    path = tmp_path / "source.txt.gz"
    module = esolangs.registry.INTERPRETERS["Unary"]
    for body in (packed.stdout, plain.stdout):
        path.write_bytes(body)
        native = subprocess.run(
            [sys.executable, "-m", module, str(path)],
            input=b"\0",
            check=True,
            **options,
        )
        assert native.stdout == b"Input: "

    note = f"note: {path} contains no source, so there was no program to run\n"
    for source, expected, diagnostic in (
        (b"", b"", note.encode()),
        (b" ", b"", b""),
        (b"0" * 84, b"\x01", b""),
    ):
        for body in (source, gzip.compress(source, mtime=0)):
            path.write_bytes(body)
            result = subprocess.run(
                [sys.executable, "-m", "esolangs", "run", "Unary", str(path)],
                input=b"",
                check=True,
                **options,
            )
            assert result.stdout == expected
            assert result.stderr == diagnostic


@pytest.mark.medium
def test_cli_loads_its_large_plain_export(tmp_path) -> None:
    import subprocess
    import sys

    command = [sys.executable, "-m", "esolangs"]
    path = tmp_path / "plain.txt"
    with path.open("wb") as destination:
        subprocess.run(
            [*command, "generate", "--plain", "Unary", "0001"],
            stdout=destination,
            check=True,
            timeout=10,
        )
    assert path.stat().st_size > 1024 * 1024
    stdin = esolangs.encode_inputs("Unary", [0, 1]).encode()
    result = subprocess.run(
        [*command, "run", "--max-steps", "20", "unary", str(path)],
        input=stdin,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == result.stderr == b""
