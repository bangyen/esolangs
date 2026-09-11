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
from esolangs.registry import LANGUAGES, RUNNERS, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

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


def _run_and_read(bundle_mod: object, arg: str | list[str], stdin: str = "") -> str:
    """Run ``bundle_mod.run`` on ``arg`` and return its captured output.

    Two arguments, like ``esolangs.run`` itself: the comparison below is
    against that function, which passes the program and the io object and
    nothing else.
    """
    io = ScriptedIO(stdin)
    bundle_mod.run(arg, io=io)
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

        Driven by ``BOOLEAN_EXAMPLES`` rather than by calling the generator
        with a table of this test's own choosing: a boolean program reads
        its input bits, and one run without them does not merely fail --
        several interpreters loop forever waiting, which pins a core
        instead of failing the suite.  The examples carry inputs that are
        known to drive their program to a halt.

        Compares outcome type and output so a ``SystemExit`` (Container) or
        interpreter keyword arguments (Suffolk's ``limit``) match too.
        """
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
        """Languages without a generator still bundle to importable files."""
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
        # The bundle reads through the interactive IO, which writes an
        # "Input: " prompt per read; the program's own output follows them.
        assert result.stdout == "Input: Input: 1"
