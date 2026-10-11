"""Distribution batches retain all rows and a bounded isolated process."""

import subprocess

import pytest

from scripts.ci import release as smoke


def test_generator_batch_executes_all_rows() -> None:
    smoke._generator("Brainfuck", math_extra=False, image_extra=True)  # noqa: SLF001


def test_generator_batch_rejects_a_wrong_table(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "_evaluate", lambda *_args, **_kwargs: "0000")
    with pytest.raises(AssertionError, match="Brainfuck"):
        smoke._generator("Brainfuck", math_extra=False, image_extra=False)  # noqa: SLF001


@pytest.mark.parametrize("math_extra", [False, True])
def test_missing_math_is_only_allowed_without_the_extra(
    monkeypatch, math_extra
) -> None:
    def missing(*_args, **_kwargs):
        raise smoke.esolangs.MissingDependencyError("math extra missing")

    monkeypatch.setattr(smoke, "_evaluate", missing)
    if math_extra:
        with pytest.raises(AssertionError):
            smoke._generator("Brainfuck", math_extra=True, image_extra=False)  # noqa: SLF001
    else:
        smoke._generator("Brainfuck", math_extra=False, image_extra=False)  # noqa: SLF001


@pytest.mark.parametrize("extra", [False, True])
def test_generator_process_keeps_the_deadline_and_propagates_failure(
    monkeypatch, extra
):
    def run(args, **kwargs):
        assert "-I" in args
        assert args[args.index("--language") + 1] == "Brainfuck"
        assert ("--math" in args) == extra
        assert ("--image" in args) == extra
        assert kwargs == {"timeout": 30, "check": True}
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(smoke.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        smoke._generator_process("Brainfuck", math_extra=extra, image_extra=extra)  # noqa: SLF001
