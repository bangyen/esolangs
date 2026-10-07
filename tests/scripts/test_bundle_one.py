"""The single-file bundle reproduces every interpreter's behavior."""

import functools
import importlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import esolangs
from esolangs import Program
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES, RUNNERS, canonical_id
from esolangs.tools.examples import BOOLEAN_EXAMPLES

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bundle_one.py"

# Example stems are the hyphenated display slug; the registry is keyed by
# display name.  Going through ``canonical_id`` joins them without a second
# hand-maintained table.
_BY_ID = {lang.id: name for name, lang in LANGUAGES.items()}


def _display_name(stem: str) -> str | None:
    """Return the display name an example stem belongs to, if registered."""
    return _BY_ID.get(canonical_id(stem.replace("-", " ")))


def load_script() -> object:
    """Import the bundler as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("bundle_one", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_bundle(tmp_path: Path) -> object:
    """Import a bundled file from ``tmp_path``, returning its module."""
    spec = importlib.util.spec_from_file_location("bundle_mod", tmp_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["bundle_mod"] = module
    spec.loader.exec_module(module)
    return module


def _run_and_read(bundle_mod: object, arg: Program | list[str], stdin: str = "") -> str:
    """Run ``bundle_mod.run`` on ``arg`` and return its captured output."""
    io = ScriptedIO(stdin)
    bundle_mod.run(arg, io=io)
    return io.getvalue()


def _outcome(fn: object) -> tuple[str, str | None]:
    """Run ``fn`` and normalize its result to (kind, detail) for comparison."""
    try:
        return ("ok", str(fn()))
    except BaseException as exc:
        return (type(exc).__name__, str(exc))


class TestBundleCompiles:
    # Bundles and imports every generated file.
    @pytest.mark.medium
    def test_every_bundle_exposes_run(self, tmp_path: Path) -> None:
        """Every bundled file is importable and defines ``run``."""
        bundle_one = load_script()
        for name in RUNNERS:
            out = tmp_path / f"{canonical_id(name)}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            module = _load_bundle(out)
            assert callable(module.run), name


class TestBundleMatchesPackage:
    @pytest.mark.slow
    def test_generator_languages_match(self, tmp_path: Path) -> None:
        """A generated program runs the same through the bundle and the package."""
        bundle_one = load_script()
        tested = set()
        for stem, example in sorted(BOOLEAN_EXAMPLES.items()):
            name = _display_name(stem)
            if name is None or name not in RUNNERS:
                continue
            program = example.build(width=None)
            stdin = example.stdin
            out = tmp_path / f"{stem}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            bundle_mod = _load_bundle(out)

            _module, split = RUNNERS[name]
            arg = program.splitlines() if split else program
            expected = _outcome(
                lambda name=name, program=program, stdin=stdin: esolangs.run(
                    name, program, stdin=stdin
                )
            )
            actual = _outcome(
                lambda bundle_mod=bundle_mod, arg=arg, stdin=stdin: _run_and_read(
                    bundle_mod, arg, stdin
                )
            )
            assert actual == expected, name
            tested.add(name)
        assert tested == {
            name for name, language in LANGUAGES.items() if language.boolean is not None
        }

    def test_no_generator_languages_import(self, tmp_path: Path) -> None:
        """Languages without a generator still bundle to importable files."""
        bundle_one = load_script()
        for name, (module, _split) in RUNNERS.items():
            if LANGUAGES[name].boolean is not None:
                continue
            out = tmp_path / f"{canonical_id(name)}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            bundled = _load_bundle(out)
            expected = importlib.import_module("esolangs.interpreters." + module)
            assert callable(bundled.run), name
            assert callable(expected.run), name


# 2.9s over 18 tests: shells out to the bundler.
@pytest.mark.medium
class TestBundleDetails:
    def test_sympy_required_note(self, tmp_path: Path) -> None:
        """Polynomial's bundle tells the user sympy is required."""
        bundle_one = load_script()
        out = tmp_path / "polynomial.py"
        bundle_one.bundle("Polynomial", bundle_one.Source(None), out)
        assert "Requires: pip install sympy" in out.read_text()

    def test_transitive_interpreter_inlined(self, tmp_path: Path) -> None:
        """Factor's bundle inlines the brainfuck interpreter it depends on."""
        bundle_one = load_script()
        out = tmp_path / "factor.py"
        bundle_one.bundle("Factor", bundle_one.Source(None), out)
        assert "inlined from esolangs/interpreters/tape_based/brainfuck.py" in (
            out.read_text()
        )

    def test_bundle_runs_from_command_line(self, tmp_path: Path) -> None:
        """The bundle honors the ``python file.py program.txt`` convention."""
        import subprocess

        bundle_one = load_script()
        program = esolangs.generate("brainfuck", "0110")
        prog_file = tmp_path / "prog.txt"
        prog_file.write_text(program)
        out = tmp_path / "brainfuck.py"
        bundle_one.bundle("brainfuck", bundle_one.Source(None), out)
        result = subprocess.run(
            [sys.executable, str(out), str(prog_file)],
            capture_output=True,
            text=True,
            input="01",
        )
        assert result.returncode == 0
        # The bundle reads through the interactive IO, which writes an
        # "Input: " prompt per buffered line; the program's output follows it.
        assert result.stdout == "Input: 1"


#: The environment the installer is handed: deliberately bare, so the script
#: is exercised the way a piped ``curl`` would run it rather than inside this
#: suite's virtualenv.
_INSTALLER_ENV: dict[str, str] = {}


@pytest.mark.slow
def test_install_one_downloads_and_runs_a_bundle() -> None:
    """The public shell installer fetches and runs representative bundles."""
    if shutil.which("curl") is None:
        pytest.skip("curl is not installed")
    # The installer runs on whatever ``python3`` resolves to, and an older one
    # cannot parse the PEP 695 aliases the interpreters use -- the installer
    # says so and stops, which is a pass for the installer and no test of the
    # bundle.  Probed under the same bare environment the run below gives it,
    # not this process's: with no PATH, ``sh`` falls back to the system one
    # and finds a different python3 from the venv running these tests.
    version = subprocess.run(
        ["python3", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
        env=_INSTALLER_ENV,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if tuple(int(part) for part in version.split(".")) < (3, 12):
        pytest.skip(f"the python3 the installer would use is {version}, not 3.12+")

    class QuietHandler(SimpleHTTPRequestHandler):
        """Serve the checkout without logging individual requests."""

        def log_message(self, _format: str, *args: object) -> None:
            pass

    handler = functools.partial(QuietHandler, directory=str(REPO_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cases = {
        "brainfuck": ("++++++++[>++++++++<-]>.", "@"),
        "Factor": ("21666143160021789415877957258569906604219402892572113", "A"),
    }
    try:
        for language, (program, expected) in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                workdir = Path(directory)
                result = subprocess.run(
                    ["sh", str(REPO_ROOT / "scripts/install_one.sh"), language],
                    cwd=workdir,
                    env=_INSTALLER_ENV
                    | {"ESOLANGS_BASE": f"http://127.0.0.1:{server.server_port}"},
                    capture_output=True,
                    text=True,
                )
                assert result.returncode == 0, result.stderr
                program_path = workdir / "program.txt"
                program_path.write_text(program)
                bundle = next(workdir.glob("esolangs_*.py"))
                output = subprocess.run(
                    [sys.executable, str(bundle), str(program_path)],
                    capture_output=True,
                    text=True,
                )
                assert output.stdout == expected
    finally:
        server.shutdown()


@pytest.mark.slow
@pytest.mark.parametrize("language", ["Line", "Piet"])
@pytest.mark.parametrize("scale", [1, 2])
def test_raster_bundle_matches_pixels_and_runs_standalone(
    language: str, scale: int, tmp_path: Path
) -> None:
    module = load_script()
    out = tmp_path / "bundle.py"
    module.bundle(language, module.Source(None), out)
    bundled = _load_bundle(out)
    program = esolangs.generate(language, "0110", balance=True, scale=scale)
    path = tmp_path / "program.png"
    path.write_bytes(program.to_png())
    for bits in ("00", "01", "10", "11"):
        stdin = "\n".join(bits) + "\n"
        assert _run_and_read(bundled, program, stdin) == esolangs.run(
            language, program, stdin=stdin
        )
        result = subprocess.run(
            [sys.executable, "-I", str(out), str(path)],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.removeprefix("Input: Input: ") == esolangs.run(
            language, path, stdin=stdin
        )


@pytest.mark.parametrize("language", ["Line", "Piet"])
@pytest.mark.medium
def test_raster_module_entry_point_matches_the_library(
    language: str, tmp_path: Path
) -> None:
    canonical = "esolangs.interpreters." + LANGUAGES[language].interpreter
    entry = importlib.import_module(canonical + ".__main__")
    assert entry.run is importlib.import_module(canonical).run
    path = tmp_path / "program.png"
    path.write_bytes(esolangs.generate(language, "0110", balance=True).to_png())
    result = subprocess.run(
        [sys.executable, "-m", canonical, str(path)],
        input="0\n1\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Input: Input: 1"


@pytest.mark.medium
def test_package_bundle_also_supports_text_without_pillow(tmp_path: Path) -> None:
    module = load_script()
    files = {
        "registry/_table.py": 'LANGUAGES = {"Demo": Language("Demo", "other.demo")}',
        "interpreters/other/demo/__init__.py": (
            "from pathlib import Path\nfrom .ops import run\n"
            "load_source = Path.read_text\n"
        ),
        "interpreters/other/demo/__main__.py": (
            "from esolangs.interpreters._entry import script_main\n"
            "from . import run, load_source\n"
            "if __name__ == '__main__':\n"
            "    script_main(run, loader=load_source)\n"
        ),
        "interpreters/other/demo/ops.py": (
            "def run(program, io):\n    io.print_str(program)\n"
        ),
    }

    class MemorySource(module.Source):
        def get(self, relative):
            if relative in files:
                return files[relative]
            return super().get(relative)

    out = tmp_path / "demo.py"
    module.bundle("Demo", MemorySource(None), out)
    assert "pip install Pillow" not in out.read_text()
    source = tmp_path / "program.txt"
    source.write_text("hello")
    result = subprocess.run(
        [sys.executable, "-I", str(out), str(source)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello"


@pytest.mark.parametrize("language", ["Line", "Piet"])
@pytest.mark.medium
def test_raster_package_bundles_from_raw_http_sources(
    language: str, tmp_path: Path
) -> None:
    module = load_script()

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, _format, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(REPO_ROOT))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        out = tmp_path / "bundle.py"
        module.bundle(
            language, module.Source(f"http://127.0.0.1:{server.server_port}"), out
        )
        assert "Requires: pip install Pillow" in out.read_text()
        bundled = _load_bundle(out)
        program = esolangs.generate(language, "01")
        assert _run_and_read(bundled, program, "1\n") == "1"
    finally:
        server.shutdown()
        server.server_close()
