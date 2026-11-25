"""Release helpers: normalize an sdist, smoke a distribution, print notes."""

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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs import LanguageInfo

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


def notes(version: str, changelog: str) -> str:
    """Return the ``## version`` section of ``changelog``, heading dropped.

    A missing or empty section raises: a release without notes is a tag that
    skipped the changelog step.
    """
    heading = f"## {version.removeprefix('v')}"
    lines = changelog.splitlines()
    if heading not in lines:
        raise SystemExit(f"docs/CHANGELOG.md has no {heading!r} section")
    start = lines.index(heading) + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise SystemExit(f"docs/CHANGELOG.md's {heading!r} section is empty")
    return body + "\n"


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


@cache
def _evaluator() -> Callable[..., str]:
    """Load the checkout's test helpers while importing the installed package."""
    # Isolated Python omits the checkout. Add its root for tests.support,
    # leaving src off the import path.
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from tests.support.evaluation import _evaluate

    return _evaluate


def _generator(name: str, *, image_extra: bool) -> None:
    """Execute all rows in one process; its parent supplies the deadline."""
    import esolangs
    from esolangs.registry import LANGUAGES, resolve
    from esolangs.registry._certification import load as load_certification

    _evaluate = _evaluator()

    controls = load_certification(LANGUAGES[resolve(name)]).benchmark_tables
    table = next((t for t in controls if "0" in t and "1" in t), "0110")
    generated = esolangs.generate(name, table)
    if image_extra and isinstance(generated.source, esolangs.Raster):
        assert isinstance(generated, esolangs.ProgramArtifact)
        generated = esolangs.ProgramArtifact(
            esolangs.Raster.from_png(generated.source.to_png()),
            generated.language,
            settings=generated.settings,
            scale=generated.scale,
        )
    assert (
        _evaluate(name, generated, timeout=None, inputs=len(table).bit_length() - 1)
        == table
    ), name


def _generator_process(name: str, *, image_extra: bool) -> None:
    """Bound one language's four rows together, retaining process isolation."""
    args = [
        sys.executable,
        "-I",
        str(Path(__file__).resolve()),
        "smoke",
        "--language",
        name,
    ]
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


def _first_languages(wanted: Callable[[LanguageInfo], object], count: int) -> list[str]:
    """Return the first ``count`` boolean-generator languages ``wanted`` accepts."""
    import esolangs

    return list(
        islice(
            (
                name
                for name in esolangs.list_languages()
                if (facts := esolangs.describe(name)).boolean_generator
                and wanted(facts)
            ),
            count,
        )
    )


def smoke(*, image_extra: bool = False) -> None:
    """Check installed resources and behaviour outside the source checkout."""
    import esolangs

    package = Path(esolangs.__file__).resolve().parent
    _smoke_install(package)
    _smoke_generators(package, image_extra=image_extra)
    _smoke_files()
    _smoke_rasters(image_extra=image_extra)
    _smoke_deadlines()
    _smoke_extras(image_extra=image_extra)


def _smoke_install(package: Path) -> None:
    """Check the installed package, its entry point and the bounded runners."""
    import esolangs

    _evaluate = _evaluator()

    assert package.parent.name in {"site-packages", "dist-packages"}, package
    assert (package / "py.typed").is_file()
    assert "brainfuck" in _cli(["list"])
    bound = esolangs.Language("BRAINFUCK")
    program = bound.generate("0110", balance=True)
    assert (
        _evaluate(bound.name, program, inputs=2, isolated=True, max_output=1) == "0110"
    )
    assert (
        bound.read_answer(bound.run(program, stdin=bound.encode_inputs([0, 1])).output)
        == "1"
    )
    assert (
        esolangs.run(
            "brainfuck", "+.", limits=esolangs.ExecutionLimits(max_steps=2)
        ).output
        == "\x01"
    )
    assert (
        esolangs.run(
            "brainfuck",
            "+.",
            limits=esolangs.ExecutionLimits(execution_timeout=1),
            isolated=True,
        ).output
        == "\x01"
    )
    _refused(
        esolangs.ExecutionCapError,
        lambda: (
            esolangs.run(
                "brainfuck", "+[]", limits=esolangs.ExecutionLimits(max_steps=10)
            ).output
        ),
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


def _smoke_generators(package: Path, *, image_extra: bool) -> None:
    """Run every generator in its own process and check its shipped examples."""
    import esolangs

    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if facts.boolean_generator:
            _generator_process(name, image_extra=image_extra)
            assert facts.examples, name
            for filename in facts.examples:
                assert not Path(filename).is_absolute(), filename
                assert (package / filename).is_file(), filename
    examples = esolangs.describe("brainfuck").examples
    assert examples
    example = package / examples[0]
    assert (
        esolangs.read_answer(
            "brainfuck", esolangs.run("brainfuck", example, stdin="0\n1\n").output
        )
        == "0"
    )


def _smoke_files() -> None:
    """Run generated source from a file through the API and the CLI's limits."""
    import esolangs

    _evaluate = _evaluator()

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
            (",.+[]", ["--execution-timeout", "2"], 124, "A", "2.0-second timeout"),
            (",[.]", ["--max-output", "3"], 124, "AAA", "output limit exceeded"),
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
        lambda facts: facts.source_kind == "raster" and not facts.parameterized,
        2,
    )
    for language in rasters:
        program = esolangs.generate(language, "0110")
        assert isinstance(program, esolangs.ProgramArtifact)
        raster = program.source
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
        artifact = esolangs.ProgramArtifact(
            decoded, program.language, settings=program.settings, scale=program.scale
        )
        for row in range(4):
            bits = [row >> 1, row & 1]
            output = esolangs.run(
                language, artifact, stdin=esolangs.encode_inputs(language, bits)
            ).output
            assert esolangs.read_answer(language, output) == "0110"[row]


def _smoke_deadlines() -> None:
    """Check worker deadlines, thread execution and termination answers."""
    import esolangs

    _evaluate = _evaluator()

    if hasattr(signal, "SIGALRM"):
        assert (
            _evaluate(
                "brainfuck",
                esolangs.generate("brainfuck", "0110"),
                timeout=1,
                inputs=2,
            )
            == "0110"
        )
    _refused(
        esolangs.ExecutionTimeoutError,
        lambda: (
            esolangs.run(
                "brainfuck",
                "+[]",
                limits=esolangs.ExecutionLimits(execution_timeout=0.02),
            ).output
        ),
        "worker timeout did not stop a loop",
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert (
            pool.submit(
                lambda: (
                    esolangs.run(
                        "brainfuck",
                        "+.",
                        limits=esolangs.ExecutionLimits(execution_timeout=2),
                    ).output
                )
            ).result(timeout=5)
            == "\x01"
        )
    # A language never halting by itself, and one answering by termination;
    # each check drops out with the last language of its kind.
    for language in _first_languages(
        lambda facts: not facts.self_halts and facts.reads_input, 1
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
    terminating = _first_languages(lambda facts: facts.answer_mode == "termination", 1)
    for language in terminating:
        assert (
            _evaluate(
                language,
                esolangs.generate(language, "01"),
                inputs=1,
                isolated=True,
            )
            == "01"
        )
    _refused(
        esolangs.ExecutionTimeoutError,
        lambda: (
            esolangs.run(
                "brainfuck",
                "+[]",
                limits=esolangs.ExecutionLimits(execution_timeout=0.5),
                isolated=True,
            ).output
        ),
        "isolated timeout did not stop a loop",
    )
    for language in terminating:
        assert (
            _evaluate(
                language,
                esolangs.generate(language, "01"),
                timeout=None,
                inputs=1,
            )
            == "01"
        )


def _smoke_extras(*, image_extra: bool) -> None:
    """Check the optional dependency is present exactly when its extra is."""
    assert (importlib.util.find_spec("PIL") is not None) == image_extra


def smoke_main(argv: list[str] | None = None) -> None:
    """Run the artifact smoke check with or without its optional extra."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--language", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.language is not None:
        _generator(args.language, image_extra=args.image)
        return
    smoke(image_extra=args.image)
    print("installed distribution smoke check passed")


def main(argv: list[str] | None = None) -> int:
    """Dispatch one release subcommand."""
    argv = sys.argv[1:] if argv is None else argv
    usage = "usage: release.py {normalize|smoke|notes} ..."
    if argv[:1] in (["-h"], ["--help"]):
        print(f"{usage}\n\n{__doc__}")
        return 0
    if not argv:
        raise SystemExit(usage)
    command, rest = argv[0], argv[1:]
    if command == "normalize":
        return normalize_main(rest)
    if command == "smoke":
        smoke_main(rest)
        return 0
    if command == "notes":
        if len(rest) != 1:
            raise SystemExit("usage: release.py notes <version>")
        changelog = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
        sys.stdout.write(notes(rest[0], changelog))
        return 0
    raise SystemExit(f"unknown subcommand {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
