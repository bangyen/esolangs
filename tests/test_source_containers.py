"""Execution keeps the same behavior across source and input containers."""

import io
from pathlib import Path
from threading import Event
from typing import Any

import pytest

import esolangs
from esolangs import _check_program
from esolangs._evaluate import _evaluate
from esolangs.debugger import make_debugger
from tests.pick import languages
from tests.test_language_coupling import REFERENCE

_RASTERS = languages(source_kind="raster", boolean_generator=True)


@pytest.mark.parametrize("language", [REFERENCE, *_RASTERS])
# Isolation forwards whatever the container held, so one container covers it;
# each isolated case spawns a worker.
@pytest.mark.parametrize(
    ("container", "mode"),
    [
        ("bytes", "normal"),
        ("text_stream", "normal"),
        ("binary_stream", "normal"),
        pytest.param("bytes", "isolated", marks=pytest.mark.medium),
    ],
)
def test_execution_container_parity(language: str, container: str, mode: str) -> None:
    program = esolangs.generate(language, "01")
    data = (
        program.to_png() if isinstance(program, esolangs.Raster) else program.encode()
    )
    source: Any = data
    if container == "text_stream":
        source = (
            io.BytesIO(data)
            if isinstance(program, esolangs.Raster)
            else io.StringIO(program)
        )
    elif container == "binary_stream":
        source = io.BytesIO(data)
    stdin = io.BytesIO(b"1")
    bounds: dict[str, Any] = {}
    if mode == "steps":
        bounds["max_steps"] = 10000
    elif mode == "isolated":
        bounds["isolated"] = True
    assert esolangs.run(language, source, stdin=stdin, **bounds) == "1"
    assert stdin.tell() == 1
    assert not stdin.closed
    if hasattr(source, "closed"):
        assert not source.closed


@pytest.mark.parametrize("language", [REFERENCE, *_RASTERS])
def test_streams_work_with_bound_api_debugging_and_evaluation(language: str) -> None:
    api = esolangs.Language(language)
    program = api.generate("01")
    data = (
        program.to_png() if isinstance(program, esolangs.Raster) else program.encode()
    )
    assert _evaluate(api.name, io.BytesIO(data), inputs=1) == "01"
    debugger = make_debugger(language, io.BytesIO(data), stdin=io.StringIO("1"))
    assert debugger.run(max_steps=10000) == "halted"
    assert debugger.output == "1"


def test_nonseekable_streams_are_read_once_from_the_current_position() -> None:
    class Stream:
        def __init__(self, value: str | bytes) -> None:
            self.value = value
            self.reads = 0

        def read(self) -> str | bytes:
            self.reads += 1
            assert self.reads == 1
            return self.value

    program, stdin = Stream(b",.,."), Stream("\n\x00")
    assert _check_program("brainfuck", program, stdin) == ",.,."
    assert stdin.reads == 0
    assert esolangs.run("brainfuck", ",.,.", stdin=stdin) == "\n\x00"
    assert (program.reads, stdin.reads) == (1, 1)
    source = io.StringIO("ignored,.")
    source.seek(7)
    assert esolangs.run("brainfuck", source, stdin="Z") == "Z"


@pytest.mark.parametrize(
    "stdin", ["é", "é".encode(), io.StringIO("é"), io.BytesIO("é".encode())]
)
def test_binary_stdin_uses_the_same_unicode_character_stream(stdin: Any) -> None:
    assert esolangs.run("brainfuck", ",.", stdin=stdin) == "é"


def test_path_loading_retains_existing_newline_normalization(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"+,\r\n.\r\n")
    assert _check_program("brainfuck", path) == "+,\n."
    assert esolangs.run("brainfuck", path, stdin="Q") == "Q"


@pytest.mark.parametrize("mode", ["normal", "steps", "isolated"])
def test_stream_failures_keep_public_error_types(mode: str) -> None:
    bounds: dict[str, Any] = {}
    if mode == "steps":
        bounds["max_steps"] = 100
    elif mode == "isolated":
        bounds["isolated"] = True

    class Broken:
        def read(self) -> str:
            raise OSError("broken stream")

    class Wrong:
        def read(self) -> int:
            return 4

    class NeedsArgument:
        def read(self, _argument: int) -> str:
            return "A"

    for stream in (Broken(), Wrong(), NeedsArgument()):
        with pytest.raises(esolangs.ProgramError):
            esolangs.run("brainfuck", stream, **bounds)  # type: ignore[arg-type]
        with pytest.raises(esolangs.ArgumentError):
            esolangs.run("brainfuck", ",.", stdin=stream, **bounds)  # type: ignore[arg-type]


@pytest.mark.parametrize("blocked", ["program", "stdin"])
def test_isolated_deadline_bounds_stream_acquisition(
    blocked: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from esolangs import _isolated

    entered, release, finished = Event(), Event(), Event()

    class Stream:
        def read(self) -> str:
            entered.set()
            release.wait(5)
            finished.set()
            return ",." if blocked == "program" else "A"

    def launch(_request: str, _timeout: float) -> str:
        pytest.fail("a blocked read must time out before launching the child")

    monkeypatch.setattr(_isolated, "_launch", launch)
    program: Any = Stream() if blocked == "program" else ",."
    stdin: Any = Stream() if blocked == "stdin" else "A"
    try:
        with pytest.raises(esolangs.ExecutionTimeoutError, match="loading input"):
            esolangs.run("brainfuck", program, stdin=stdin, isolated=True, timeout=0.1)
        assert entered.is_set()
        assert not finished.is_set()
    finally:
        release.set()
        assert finished.wait(1)
