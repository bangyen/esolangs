"""Release helpers: normalize an sdist and smoke an installed distribution."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import io
import os
import signal
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES

ROOT = Path(__file__).resolve().parents[2]


def normalize(path: Path, epoch: int) -> None:
    """Preserve payloads while fixing gzip and tar metadata deterministically."""
    buffer = io.BytesIO()
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as target,
    ):
        for member in source.getmembers():
            member.mtime = epoch
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {
                key: value
                for key, value in member.pax_headers.items()
                if key not in {"mtime", "atime", "ctime"}
            }
            target.addfile(
                member, source.extractfile(member) if member.isfile() else None
            )
    with (
        path.open("wb") as stream,
        gzip.GzipFile(
            filename="", mode="wb", fileobj=stream, mtime=epoch
        ) as compressed,
    ):
        compressed.write(buffer.getvalue())


def normalize_main(argv: list[str]) -> int:
    """Normalize every archive named on the command line to SOURCE_DATE_EPOCH."""
    epoch = int(os.environ["SOURCE_DATE_EPOCH"])
    for name in argv:
        normalize(Path(name), epoch)
    return 0


def _cli(args: list[str], stdin: str = "") -> str:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "esolangs", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout


def _refuses_timeout() -> None:
    try:
        esolangs.run("brainfuck", "+.", timeout=0.1)
    except esolangs.ArgumentError as exc:
        message = str(exc)
    else:
        raise AssertionError("unsupported signal timeout was accepted")
    assert "Unix main thread" in message


def _generator(name: str, *, math_extra: bool, image_extra: bool) -> None:
    """Execute all rows in one process; its parent supplies the deadline."""
    generated = esolangs.generate(name, "0110")
    if image_extra and isinstance(generated, esolangs.Raster):
        generated = esolangs.Raster.from_png(generated.to_png())
    try:
        assert _evaluate(name, generated, timeout=None, inputs=2) == "0110", name
    except esolangs.MissingDependencyError:
        assert not math_extra, name


def _generator_process(name: str, *, math_extra: bool, image_extra: bool) -> None:
    """Bound one language's four rows together, retaining process isolation."""
    args = [
        sys.executable,
        "-I",
        str(Path(__file__).resolve()),
        "smoke",
        "--language",
        name,
    ]
    if math_extra:
        args.append("--math")
    if image_extra:
        args.append("--image")
    subprocess.run(args, timeout=30, check=True)


def smoke(*, math_extra: bool, image_extra: bool = False) -> None:
    """Check installed resources and behaviour outside the source checkout."""
    package = Path(esolangs.__file__).resolve().parent
    assert package.parent.name in {"site-packages", "dist-packages"}, package
    assert (package / "py.typed").is_file()
    assert "brainfuck" in _cli(["list"])
    bound = esolangs.Language("BRAINFUCK")
    program = bound.generate("0110", balance=True)
    assert (
        _evaluate(bound.name, program, inputs=2, isolated=True, max_output=1) == "0110"
    )
    assert (
        bound.read_answer(bound.run(program, stdin=bound.encode_inputs([0, 1]))) == "1"
    )
    assert esolangs.run("brainfuck", "+.", max_steps=2) == "\x01"
    assert esolangs.run("brainfuck", "+.", timeout=1, isolated=True) == "\x01"
    try:
        esolangs.run("brainfuck", "+[]", max_steps=10)
    except esolangs.ExecutionTimeoutError:
        pass
    else:
        raise AssertionError("the bounded runner accepted a diverging program")

    executable = Path(sys.executable).with_name(
        "esolangs.exe" if sys.platform == "win32" else "esolangs"
    )
    entrypoint = subprocess.run(
        [str(executable), "list"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "brainfuck" in entrypoint.stdout
    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if facts["boolean_generator"]:
            _generator_process(name, math_extra=math_extra, image_extra=image_extra)
            assert facts["examples"], name
            for filename in facts["examples"]:
                assert not Path(filename).is_absolute(), filename
                assert (package / filename).is_file(), filename
    examples = esolangs.describe("brainfuck")["examples"]
    assert examples
    example = package / examples[0]
    assert (
        esolangs.read_answer(
            "brainfuck", esolangs.run("brainfuck", example, stdin="0\n1\n")
        )
        == "0"
    )
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "xor.txt"
        source.write_text(_cli(["generate", "brainfuck", "0110"]), encoding="utf-8")
        for row in range(4):
            stdin = esolangs.encode_inputs("brainfuck", [row >> 1, row & 1])
            assert (
                esolangs.read_answer(
                    "brainfuck", _cli(["run", "brainfuck", str(source)], stdin)
                )
                == "0110"[row]
            )
        assert _evaluate("brainfuck", source, timeout=None, inputs=2) == "0110"
        for program, options, code, output, diagnostic in (
            (",.+[]", ["--timeout", "2"], 124, "A\n", "deadline"),
            (",[.]", ["--max-output", "3"], 1, "AAA\n", "output limit exceeded"),
        ):
            source.write_text(program, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "esolangs",
                    "run",
                    "--isolated",
                    *options,
                    "brainfuck",
                    str(source),
                ],
                input="A",
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert result.returncode == code, result
            assert result.stdout == output, result
            assert diagnostic in result.stderr, result
        source.write_text(",>,<.", encoding="utf-8")
        assert _evaluate("brainfuck", source, timeout=None, inputs=2) == "0011"
    rasters = [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["source_kind"] == "raster"
        and esolangs.describe(name)["boolean_generator"]
        and not esolangs.describe(name)["parameterized"]
    ]
    for language in rasters[:2]:
        raster = esolangs.generate(language, "0110")
        assert isinstance(raster, esolangs.Raster)
        if image_extra:
            decoded = esolangs.Raster.from_png(raster.to_png())
        else:
            decoded = raster
            for operation in (raster.to_png, lambda: esolangs.Raster.from_png(b"")):
                try:
                    operation()
                except esolangs.MissingDependencyError as exc:
                    message = str(exc)
                else:
                    raise AssertionError("PNG I/O ran without its image extra")
                assert "esolangs[image]" in message
        for row in range(4):
            bits = [row >> 1, row & 1]
            output = esolangs.run(
                language, decoded, stdin=esolangs.encode_inputs(language, bits)
            )
            assert esolangs.read_answer(language, output) == "0110"[row]
    if hasattr(signal, "SIGALRM"):
        assert (
            _evaluate(
                "brainfuck", esolangs.generate("brainfuck", "0110"), timeout=1, inputs=2
            )
            == "0110"
        )
        try:
            esolangs.run("brainfuck", "+[]", timeout=0.02)
        except esolangs.ExecutionTimeoutError:
            pass
        else:
            raise AssertionError("signal timeout did not stop a loop")
    else:
        _refuses_timeout()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_refuses_timeout).result(timeout=5)
    # A language never halting by itself, and one answering by termination;
    # each check drops out with the last language of its kind.
    for language in [
        name
        for name in esolangs.list_languages()
        if not esolangs.describe(name)["self_halts"]
        and esolangs.describe(name)["boolean_generator"]
        and esolangs.describe(name)["reads_input"]
    ][:1]:
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert (
                pool.submit(
                    _evaluate,
                    language,
                    esolangs.generate(language, "0110"),
                    inputs=2,
                    isolated=True,
                ).result(timeout=30)
                == "0110"
            )
    terminating = [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["answer_mode"] == "termination"
        and esolangs.describe(name)["boolean_generator"]
    ][:1]
    for language in terminating:
        assert (
            _evaluate(
                language, esolangs.generate(language, "01"), inputs=1, isolated=True
            )
            == "01"
        )
    try:
        esolangs.run("brainfuck", "+[]", timeout=0.5, isolated=True)
    except esolangs.ExecutionTimeoutError:
        pass
    else:
        raise AssertionError("isolated timeout did not stop a loop")
    for language in terminating:
        assert (
            _evaluate(
                language, esolangs.generate(language, "01"), timeout=None, inputs=1
            )
            == "01"
        )
    assert (importlib.util.find_spec("PIL") is not None) == image_extra
    # Each language whose interpreter needs the math extra runs with it and
    # refuses without it; none left means nothing to check.
    for language in [n for n, lang in LANGUAGES.items() if lang.extra == "math"]:
        program = esolangs.generate(language, "01")
        if math_extra:
            assert importlib.util.find_spec("sympy") is not None
            assert _evaluate(language, program, timeout=None, inputs=1) == "01"
        else:
            assert importlib.util.find_spec("sympy") is None
            try:
                esolangs.run(language, program, stdin="")
            except esolangs.MissingDependencyError:
                pass
            else:
                raise AssertionError(f"{language} ran without its math extra")


def smoke_main() -> None:
    """Run the artifact smoke check with or without its optional extra."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math", action="store_true")
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--language", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.language is not None:
        _generator(args.language, math_extra=args.math, image_extra=args.image)
        return
    smoke(math_extra=args.math, image_extra=args.image)
    print("installed distribution smoke check passed")


def main(argv: list[str] | None = None) -> int:
    """Dispatch one release subcommand."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit("usage: release.py {normalize|smoke} ...")
    command, rest = argv[0], argv[1:]
    if command == "normalize":
        return normalize_main(rest)
    if command == "smoke":
        sys.argv = [sys.argv[0], *rest]
        smoke_main()
        return 0
    raise SystemExit(f"unknown subcommand {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
