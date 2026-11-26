"""HQ9+ output, accumulator and quine dialect controls."""

import gzip
import os
import subprocess
import sys

import pytest

from esolangs import Language
from esolangs.languages.hq9.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.interpreters.runner import run_program
from tests.support.vm_support import assert_rejected_output_retry
from tests.support.workspace_oracle import WorkspaceOracle


@pytest.mark.parametrize("code", ["H", "h"])
def test_greeting(code: str) -> None:
    assert run_program(run, code) == "Hello, world!\n"


@pytest.mark.parametrize("code", ["Q", "q", " Q\n☃", "qQ"])
def test_quine_preserves_source(code: str, tmp_path) -> None:
    assert run_program(run, code) == code * sum(char in "Qq" for char in code)
    if code == "Q":
        _check_native_quine_files(tmp_path)


def _check_native_quine_files(tmp_path) -> None:
    import esolangs

    api = Language("HQ9+")
    native = esolangs.registry.INTERPRETERS[api.name]
    path = tmp_path / "quine.hq9"
    for data in (b"Q", "Q\r\n☃\r".encode()):
        for packed in (False, True):
            api.to_file(data, path, gzip=packed, normalize=True)
            saved = path.read_bytes()
            assert (gzip.decompress(saved) if packed else saved) == data
            assert api.run(path).unwrap().output.encode() == data
            assert (
                api.run(api.from_file(path, normalize=True)).unwrap().output.encode()
                == data
            )
            for command in ([native], ["esolangs", "run", api.name]):
                result = subprocess.run(
                    [sys.executable, "-m", *command, str(path)],
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
                native_text = os.name == "nt" and command == [native]
                expected = data.replace(b"\n", b"\r\n") if native_text else data
                assert (result.returncode, result.stdout, result.stderr) == (
                    0,
                    expected,
                    b"",
                )


def test_execution_order_and_silent_accumulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from esolangs.languages.hq9.tests.oracle_checks import check_raw_hq9

    check_raw_hq9()
    greeting = "Hello, world!\n"
    assert_rejected_output_retry(
        "HQ9+",
        "HQ",
        greeting,
        greeting + "HQ",
        prefix=0,
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=("HQ",),
    )
    assert_rejected_output_retry(
        "HQ9+",
        "☃Q",
        "☃Q",
        "☃Q",
        prefix=1,
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )
    for code, peak, accumulator, output in (
        ("h++qH", 5, 2, "Hello, world!\nh++qHHello, world!\n"),
        ("h+q", 3, 1, "Hello, world!\nh+q"),
    ):
        io = ScriptedIO("unused")
        machine = _Machine(code, io)
        measured = WrittenState(machine.workspace_snapshot())
        oracle = WorkspaceOracle(machine.workspace_snapshot())

        while not machine.halted:
            machine.step()
            captured = machine.workspace_snapshot()
            assert captured.parts == (*machine.state, machine.io.progress())
            measured.sample(captured)
            oracle.sample(captured)
            assert measured.bits == oracle.bits
        assert measured.bits == peak
        assert io.getvalue() == output
        assert machine.memory == [accumulator]
        assert io.position() == 0


@pytest.mark.parametrize("code", ["", "xyz☃\n", "+++", "\u210e\uff28\uff31"])
def test_other_characters_are_ignored(code: str) -> None:
    assert run_program(run, code) == ""


def test_song_covers_every_verse_and_singular_boundary() -> None:
    verses = run_program(run, "9").rstrip("\n").split("\n\n")
    assert len(verses) == 100
    for count, verse in zip(range(99, 0, -1), verses[:-1], strict=True):
        first, second = verse.splitlines()
        noun = "bottle" if count == 1 else "bottles"
        assert first == f"{count} {noun} of beer on the wall, {count} {noun} of beer."
        remaining = (
            "no more bottles"
            if count == 1
            else "1 bottle"
            if count == 2
            else f"{count - 1} bottles"
        )
        assert (
            second
            == f"Take one down and pass it around, {remaining} of beer on the wall."
        )
    assert verses[-1] == (
        "No more bottles of beer on the wall, no more bottles of beer.\n"
        "Go to the store and buy some more, 99 bottles of beer on the wall."
    )
    assert run_program(run, "99") == run_program(run, "9") * 2
