"""Deadfish through the shared API, CLI and machinery."""

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

import esolangs
from esolangs.languages.deadfish.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE


def test_generate_refuses_a_language_with_no_generator() -> None:
    """A registered language may have no generator, and must say so."""
    with pytest.raises(esolangs.ArgumentError) as exc:
        esolangs.generate("Deadfish", "0110")
    message = str(exc.value)
    assert "no boolean generator" in message
    assert "generator contracts" in message
    assert "'int'" in message


@pytest.mark.medium
@pytest.mark.parametrize(
    "limits", [(), ("--max-steps", "5"), ("--isolated", "--execution-timeout", "2")]
)
def test_cli_leaves_unused_stdin_unread(
    tmp_path: Path, limits: tuple[str, ...]
) -> None:
    path = tmp_path / "program"
    path.write_text("io")
    reader, writer = os.pipe()
    with os.fdopen(reader, "rb") as source, os.fdopen(writer, "wb") as feed:
        feed.write(b"\xff")
        feed.flush()
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "run", *limits, "Deadfish", str(path)],
            stdin=source,
            capture_output=True,
            timeout=10,
            check=False,
        )
        feed.close()
        assert source.read() == b"\xff"
    assert (result.returncode, result.stdout, result.stderr) == (0, b"1\n", b"")


@pytest.mark.medium
def test_large_accumulator_prints_each_number_under_host_digit_cap(
    tmp_path: Path,
) -> None:
    source = "oiii" + "s" * 14 + "oio"
    value = 3 ** (1 << 14)
    expected = f"0\n{Decimal(value):f}\n{Decimal(value + 1):f}\n"
    limit = sys.int_info.str_digits_check_threshold
    previous = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(limit)
    try:
        native = ScriptedIO()
        run(source, native)
        assert native.getvalue() == expected
        assert esolangs.run("Deadfish", source).unwrap().output == expected
    finally:
        sys.set_int_max_str_digits(previous)

    path = tmp_path / "program"
    path.write_text(source)
    for options in ([], ["--isolated"]):
        cli = subprocess.run(
            [sys.executable, "-m", "esolangs", "run", *options, "Deadfish", str(path)],
            env={**os.environ, "PYTHONINTMAXSTRDIGITS": str(limit)},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert (cli.returncode, cli.stdout, cli.stderr) == (0, expected.encode(), b"")


def test_supplied_program_never_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("evaluation called a generator")

    monkeypatch.setattr(esolangs, "generate", refuse)
    assert _evaluate(REFERENCE, ",>,<.", inputs=2) == "0011"
    assert _evaluate("Deadfish", "o", inputs=1) == "00"
