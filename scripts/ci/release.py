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
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import islice
from pathlib import Path

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
    import esolangs

    refusal = _refused(
        esolangs.ArgumentError,
        lambda: esolangs.run("brainfuck", "+.", timeout=0.1),
        "unsupported signal timeout was accepted",
    )
    assert "Unix main thread" in str(refusal)


def _generator(name: str, *, math_extra: bool, image_extra: bool) -> None:
    """Execute all rows in one process; its parent supplies the deadline."""
    import esolangs
    from esolangs.registry import LANGUAGES, resolve
    from esolangs.runtime._evaluate import _evaluate

    controls = LANGUAGES[resolve(name)].benchmark_tables
    table = next((t for t in controls if "0" in t and "1" in t), "0110")
    generated = esolangs.generate(name, table)
    if image_extra and isinstance(generated, esolangs.Raster):
        generated = esolangs.Raster.from_png(generated.to_png())
    try:
        assert (
            _evaluate(name, generated, timeout=None, inputs=len(table).bit_length() - 1)
            == table
        ), name
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


def _refused(
    error: type[BaseException], action: Callable[[], object], failure: str
) -> BaseException:
    """Run ``action``, which must raise ``error``; return what it raised."""
    try:
        action()
    except error as exc:
        return exc
    raise AssertionError(failure)


def _first_languages(
    wanted: Callable[[Mapping[str, object]], object], count: int
) -> list[str]:
    """Return the first ``count`` boolean-generator languages ``wanted`` accepts."""
    import esolangs

    return list(
        islice(
            (
                name
                for name in esolangs.list_languages()
                if (facts := esolangs.describe(name))["boolean_generator"]
                and wanted(facts)
            ),
            count,
        )
    )


def smoke(*, math_extra: bool, image_extra: bool = False) -> None:
    """Check installed resources and behaviour outside the source checkout."""
    import esolangs

    package = Path(esolangs.__file__).resolve().parent
    _smoke_install(package)
    _smoke_generators(package, math_extra=math_extra, image_extra=image_extra)
    _smoke_files()
    _smoke_rasters(image_extra=image_extra)
    _smoke_deadlines()
    _smoke_extras(math_extra=math_extra, image_extra=image_extra)


def _smoke_install(package: Path) -> None:
    """Check the installed package, its entry point and the bounded runners."""
    import esolangs
    from esolangs.runtime._evaluate import _evaluate

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
    _refused(
        esolangs.ExecutionTimeoutError,
        lambda: esolangs.run("brainfuck", "+[]", max_steps=10),
        "the bounded runner accepted a diverging program",
    )
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


def _smoke_generators(package: Path, *, math_extra: bool, image_extra: bool) -> None:
    """Run every generator in its own process and check its shipped examples."""
    import esolangs

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


def _smoke_files() -> None:
    """Run generated source from a file through the API and the CLI's limits."""
    import esolangs
    from esolangs.runtime._evaluate import _evaluate

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


def _smoke_rasters(*, image_extra: bool) -> None:
    """Run two raster generators, through PNG only when the image extra is in."""
    import esolangs

    rasters = _first_languages(
        lambda facts: facts["source_kind"] == "raster" and not facts["parameterized"],
        2,
    )
    for language in rasters:
        raster = esolangs.generate(language, "0110")
        assert isinstance(raster, esolangs.Raster)
        if image_extra:
            decoded = esolangs.Raster.from_png(raster.to_png())
        else:
            decoded = raster
            for operation in (raster.to_png, lambda: esolangs.Raster.from_png(b"")):
                refusal = _refused(
                    esolangs.MissingDependencyError,
                    operation,
                    "PNG I/O ran without its image extra",
                )
                assert "esolangs[image]" in str(refusal)
        for row in range(4):
            bits = [row >> 1, row & 1]
            output = esolangs.run(
                language, decoded, stdin=esolangs.encode_inputs(language, bits)
            )
            assert esolangs.read_answer(language, output) == "0110"[row]


def _smoke_deadlines() -> None:
    """Check signal, thread and isolated deadlines, and termination answers."""
    import esolangs
    from esolangs.runtime._evaluate import _evaluate

    if hasattr(signal, "SIGALRM"):
        assert (
            _evaluate(
                "brainfuck", esolangs.generate("brainfuck", "0110"), timeout=1, inputs=2
            )
            == "0110"
        )
        _refused(
            esolangs.ExecutionTimeoutError,
            lambda: esolangs.run("brainfuck", "+[]", timeout=0.02),
            "signal timeout did not stop a loop",
        )
    else:
        _refuses_timeout()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_refuses_timeout).result(timeout=5)
    # A language never halting by itself, and one answering by termination;
    # each check drops out with the last language of its kind.
    for language in _first_languages(
        lambda facts: not facts["self_halts"] and facts["reads_input"], 1
    ):
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
    terminating = _first_languages(
        lambda facts: facts["answer_mode"] == "termination", 1
    )
    for language in terminating:
        assert (
            _evaluate(
                language, esolangs.generate(language, "01"), inputs=1, isolated=True
            )
            == "01"
        )
    _refused(
        esolangs.ExecutionTimeoutError,
        lambda: esolangs.run("brainfuck", "+[]", timeout=0.5, isolated=True),
        "isolated timeout did not stop a loop",
    )
    for language in terminating:
        assert (
            _evaluate(
                language, esolangs.generate(language, "01"), timeout=None, inputs=1
            )
            == "01"
        )


def _smoke_extras(*, math_extra: bool, image_extra: bool) -> None:
    """Check each optional dependency is present exactly when its extra is."""
    import esolangs
    from esolangs.registry import LANGUAGES
    from esolangs.runtime._evaluate import _evaluate

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
            _refused(
                esolangs.MissingDependencyError,
                partial(esolangs.run, language, program, stdin=""),
                f"{language} ran without its math extra",
            )


def smoke_main(argv: list[str] | None = None) -> None:
    """Run the artifact smoke check with or without its optional extra."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math", action="store_true")
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--language", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
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
        smoke_main(rest)
        return 0
    raise SystemExit(f"unknown subcommand {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
