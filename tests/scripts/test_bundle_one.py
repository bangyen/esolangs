r"""The single-file bundle reproduces every interpreter's behavior."""

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES, RUNNERS, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bundle_one.py"

# Example stems are the.
# display name.
# hand-maintained table.
_BY_ID = {lang.id: name for name, lang in LANGUAGES.items()}


def _display_name(stem: str) -> str | None:
    r"""Return the display name an example stem belongs to, if registered."""
    return _BY_ID.get(canonical_id(stem.replace("-", " ")))


def load_script() -> object:
    r"""Import the bundler as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("bundle_one", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_bundle(tmp_path: Path) -> object:
    r"""Import a bundled file from ``tmp_path``, returning its module."""
    spec = importlib.util.spec_from_file_location("bundle_mod", tmp_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["bundle_mod"] = module
    spec.loader.exec_module(module)
    return module


def _run_and_read(bundle_mod: object, arg: str | list[str], stdin: str = "") -> str:
    r"""Run ``bundle_mod.run`` on ``arg`` and return its captured output."""
    io = ScriptedIO(stdin)
    bundle_mod.run(arg, io=io)
    return io.getvalue()


def _outcome(fn: object) -> tuple[str, str | None]:
    r"""Run ``fn`` and normalize its result to (kind, detail) for."""
    try:
        return ("ok", str(fn()))
    except BaseException as exc:
        return (type(exc).__name__, str(exc))


class TestBundleCompiles:
    def test_every_bundle_exposes_run(self, tmp_path: Path) -> None:
        r"""Every bundled file is importable and defines ``run``."""
        bundle_one = load_script()
        for name in RUNNERS:
            out = tmp_path / f"{name}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            module = _load_bundle(out)
            assert callable(module.run), name


class TestBundleMatchesPackage:
    def test_generator_languages_match(self, tmp_path: Path) -> None:
        r"""A generated program runs the same through the bundle and the."""
        bundle_one = load_script()
        tested = 0
        for stem, example in sorted(BOOLEAN_EXAMPLES.items()):
            name = _display_name(stem)
            if name is None or name not in RUNNERS:
                continue
            program = example.build(width=None)
            stdin = "".join(f"{line}\n" for line in example.inputs)
            out = tmp_path / f"{stem}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            bundle_mod = _load_bundle(out)

            _module, split = RUNNERS[name]
            arg = program.splitlines() if split else program
            expected = _outcome(
                lambda name=name, program=program, stdin=stdin: esolangs.run(
                    name, program, stdin
                )
            )
            actual = _outcome(
                lambda bundle_mod=bundle_mod, arg=arg, stdin=stdin: _run_and_read(
                    bundle_mod, arg, stdin
                )
            )
            assert actual == expected, name
            tested += 1
        assert tested > 0

    def test_no_generator_languages_import(self, tmp_path: Path) -> None:
        r"""Languages without a generator still bundle to importable files."""
        bundle_one = load_script()
        for name, (module, _split) in RUNNERS.items():
            if LANGUAGES[name].boolean is not None:
                continue
            out = tmp_path / f"{name}.py"
            bundle_one.bundle(name, bundle_one.Source(None), out)
            bundled = _load_bundle(out)
            expected = importlib.import_module("esolangs.interpreters." + module)
            assert callable(bundled.run), name
            assert callable(expected.run), name


# 2.9s over 18 tests: shells.
@pytest.mark.medium
class TestBundleDetails:
    def test_sympy_required_note(self, tmp_path: Path) -> None:
        r"""Factor's bundle tells the user sympy is required."""
        bundle_one = load_script()
        out = tmp_path / "factor.py"
        bundle_one.bundle("Factor", bundle_one.Source(None), out)
        assert "Requires: pip install sympy" in out.read_text()

    def test_transitive_interpreter_inlined(self, tmp_path: Path) -> None:
        r"""Factor's bundle inlines the brainfuck interpreter it depends on."""
        bundle_one = load_script()
        out = tmp_path / "factor.py"
        bundle_one.bundle("Factor", bundle_one.Source(None), out)
        assert "inlined from esolangs/interpreters/tape_based/brainfuck.py" in (
            out.read_text()
        )

    def test_bundle_runs_from_command_line(self, tmp_path: Path) -> None:
        r"""The bundle honors the ``python file.py program.txt`` convention."""
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
            input="0\n1\n",
        )
        assert result.returncode == 0
        # The bundle reads through the.
        # "Input: " prompt per read;.
        assert result.stdout == "Input: Input: 1"
