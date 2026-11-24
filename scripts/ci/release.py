"""Release helpers: normalize an sdist, smoke a distribution, print notes."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterator
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
    path = path.resolve(strict=True)
    fixed_metadata = {"mtime", "atime", "ctime", "uid", "gid", "uname", "gname"}
    with tempfile.TemporaryDirectory(dir=path.parent) as scratch:
        staged = Path(scratch) / path.name
        with (
            tarfile.open(path, "r:gz") as source,
            staged.open("wb") as stream,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=stream, mtime=epoch
            ) as compressed,
            tarfile.open(
                fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT
            ) as target,
        ):
            for member in source:
                member.mtime = epoch
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                # PAX values take precedence over these tar header fields.
                member.pax_headers = {
                    key: value
                    for key, value in member.pax_headers.items()
                    if key not in fixed_metadata
                }
                target.addfile(
                    member, source.extractfile(member) if member.isfile() else None
                )
        staged.chmod(stat.S_IMODE(path.stat().st_mode))
        staged.replace(path)


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
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-m", "esolangs", *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        if error.stderr:
            error.add_note(error.stderr.rstrip())
        raise
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


def smoke(*, image_extra: bool = False, image_only: bool = False) -> None:
    """Check installed resources and behaviour outside the source checkout."""
    import esolangs

    package = Path(esolangs.__file__).resolve().parent
    image_extra = image_extra or image_only
    _smoke_extras(image_extra=image_extra)
    if not image_only:
        _smoke_install(package)
        _smoke_files()
        _smoke_deadlines()
    _smoke_generators(package, image_extra=image_extra, raster_only=image_only)
    _smoke_rasters(image_extra=image_extra)


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
    _smoke_quickstart(executable)


def _smoke_quickstart(executable: Path) -> None:
    """Execute the README's Bash and compare its documented output."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = readme.partition("\n## Try it\n")[2].partition("\n## ")[0]
    example = re.search(
        r"^```bash\n(.*?)^```\n\s*^```text\n(.*?)^```$",
        quickstart,
        re.MULTILINE | re.DOTALL,
    )
    assert example is not None, "README quickstart needs Bash and output blocks"
    script, expected = example.groups()
    assert executable.is_file(), executable
    path = os.pathsep.join((str(executable.parent), os.environ.get("PATH", "")))
    with tempfile.TemporaryDirectory() as temporary:
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
            cwd=temporary,
            env={**os.environ, "PATH": path},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected, (result.stdout, expected)


def _smoke_generators(
    package: Path, *, image_extra: bool, raster_only: bool = False
) -> None:
    """Run every generator in its own process and check its shipped examples."""
    import esolangs

    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if facts.boolean_generator and (
            not raster_only or facts.source_kind == "raster"
        ):
            _generator_process(name, image_extra=image_extra)
            assert facts.examples, name
            for filename in facts.examples:
                assert not Path(filename).is_absolute(), filename
                assert (package / filename).is_file(), filename
    if raster_only:
        return
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
        source.write_text(
            _cli(["generate", "brainfuck", "-"], "0110\n"), encoding="utf-8"
        )
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
        _smoke_portable_artifact(source.with_suffix(".json"))
        _smoke_saved_template(source.parent)


def _smoke_portable_artifact(target: Path) -> None:
    """Round-trip a portable program with a nondefault dialect in the CLI."""
    import esolangs

    def overrides(facts: LanguageInfo) -> Iterator[tuple[str, str | int]]:
        return (
            (key, value)
            for key, setting in facts.dialect_settings.items()
            for value in setting["choices"]
            if value != setting["default"]
        )

    (language,) = _first_languages(
        lambda facts: (
            facts.source_kind == "text"
            and not facts.parameterized
            and facts.answer_mode == "output"
            and next(overrides(facts), None) is not None
        ),
        1,
    )
    key, value = next(overrides(esolangs.describe(language)))
    table = "0110"
    document = _cli(
        [
            "generate",
            "--artifact",
            "--settings",
            json.dumps({key: value}),
            language,
            table,
        ]
    )
    artifact = esolangs.from_json(language, document)
    assert isinstance(artifact, esolangs.ProgramArtifact)
    assert artifact.input_arity == 2
    assert artifact.settings is not None
    assert artifact.settings.options()[key] == value
    target.write_text(document, encoding="utf-8")
    for row, expected in enumerate(table):
        stdin = esolangs.encode_inputs(language, [row >> 1, row & 1])
        output = _cli(["run", "--artifact", language, str(target)], stdin)
        assert esolangs.read_answer(language, output) == expected, (language, row)


def _smoke_saved_template(directory: Path) -> None:
    """Save one XOR template and fill and run every row through the installed CLI."""
    import esolangs

    (language,) = _first_languages(
        lambda facts: facts.parameterized and facts.answer_mode == "output",
        1,
    )
    table = "0110"
    template = directory / "xor template.json"
    template.write_text(
        _cli(["generate", "--artifact", language, table]), encoding="utf-8"
    )
    filled = directory / "filled.json"
    for row, expected in enumerate(table):
        filled.write_text(
            _cli(
                [
                    "generate",
                    "--from-template",
                    str(template),
                    "--bits",
                    f"{row:02b}",
                    "--artifact",
                    language,
                ]
            ),
            encoding="utf-8",
        )
        output = _cli(["run", "--artifact", language, str(filled)])
        assert esolangs.read_answer(language, output) == expected, (language, row)


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
    image = parser.add_mutually_exclusive_group()
    image.add_argument("--image", action="store_true", help="full check with Pillow")
    image.add_argument(
        "--image-only", action="store_true", help="check PNG after the full wheel pass"
    )
    parser.add_argument("--language", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.language is not None:
        if args.image_only:
            parser.error("--image-only cannot be combined with --language")
        _generator(args.language, image_extra=args.image)
        return
    smoke(image_extra=args.image, image_only=args.image_only)
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
