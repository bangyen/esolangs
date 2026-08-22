"""The single-file bundle reproduces every interpreter's behavior.

``scripts/bundle_one.py`` inlines a language's interpreter together with the
shared ``esolangs.exceptions`` and ``esolangs.interpreters.io`` modules (and
any interpreter it imports) into one runnable file.  These tests pin the two
things that make that useful: the bundle compiles for every language, and
running it produces exactly what the packaged interpreter produces.
"""

import importlib
import importlib.util
import sys
from pathlib import Path

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES, RUNNERS

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "bundle_one.py"


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


def _run_and_read(
    bundle_mod: object,
    arg: str | list[str],
    kwargs: dict[str, int],
) -> str:
    """Run ``bundle_mod.run`` on ``arg`` and return its captured output."""
    io = ScriptedIO()
    bundle_mod.run(arg, io=io, **kwargs)
    return io.getvalue()


def _outcome(fn: object) -> tuple[str, str | None]:
    """Run ``fn`` and normalize its result to (kind, detail) for comparison.

    The caller builds ``fn`` with loop variables bound as default arguments,
    so a late-binding closure cannot pick up a later iteration's values.
    """
    try:
        return ("ok", str(fn()))
    except BaseException as exc:
        return (type(exc).__name__, str(exc))


class TestBundleCompiles:
    def test_every_language_bundles(self, tmp_path: Path) -> None:
        """Every registered interpreter produces a compiling bundle."""
        bundle_one = load_script()
        for name in RUNNERS:
            out = tmp_path / f"{name}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            compile(out.read_text(), out.name, "exec")

    def test_every_bundle_exposes_run(self, tmp_path: Path) -> None:
        """Every bundled file is importable and defines ``run``."""
        bundle_one = load_script()
        for name in RUNNERS:
            out = tmp_path / f"{name}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            module = _load_bundle(out)
            assert callable(module.run), name


class TestBundleMatchesPackage:
    def test_generator_languages_match(self, tmp_path: Path) -> None:
        """A generated program runs the same through the bundle and the package.

        Compares outcome type and output so a ``SystemExit`` (Container) or
        interpreter keyword arguments (Suffolk's ``limit``) match too.
        """
        bundle_one = load_script()
        tested = 0
        for name in RUNNERS:
            generator = LANGUAGES[name].generator
            if generator is None:
                continue
            try:
                program = generator("Hi")
            except ValueError:
                continue  # the generator rejects "Hi"; nothing to compare
            out = tmp_path / f"{name}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            bundle_mod = _load_bundle(out)

            _module, split, kwargs = RUNNERS[name]
            arg = program.splitlines() if split else program
            expected = _outcome(
                lambda name=name, program=program: esolangs.run(name, program)
            )
            actual = _outcome(
                lambda bundle_mod=bundle_mod, arg=arg, kwargs=kwargs: (
                    _run_and_read(bundle_mod, arg, kwargs)
                )
            )
            assert actual == expected, name
            tested += 1
        assert tested > 0

    def test_no_generator_languages_import(self, tmp_path: Path) -> None:
        """Languages without a generator still bundle to importable files."""
        bundle_one = load_script()
        for name, (module, _split, _kwargs) in RUNNERS.items():
            if LANGUAGES[name].generator is not None:
                continue
            out = tmp_path / f"{name}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            bundled = _load_bundle(out)
            expected = importlib.import_module("esolangs.interpreters." + module)
            assert callable(bundled.run), name
            assert callable(expected.run), name


class TestBundleDetails:
    def test_sympy_required_note(self, tmp_path: Path) -> None:
        """Factor's bundle tells the user sympy is required."""
        bundle_one = load_script()
        out = tmp_path / "factor.py"
        bundle_one.bundle("Factor", bundle_one.Source(None), out)
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
        program = esolangs.generate("brainfuck", "Hi")
        prog_file = tmp_path / "prog.txt"
        prog_file.write_text(program)
        out = tmp_path / "brainfuck.py"
        bundle_one.bundle("brainfuck", bundle_one.Source(None), out)
        result = subprocess.run(
            [sys.executable, str(out), str(prog_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == "Hi"
