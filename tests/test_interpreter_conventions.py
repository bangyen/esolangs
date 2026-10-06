"""Source-shape conventions the interpreters share, swept over the tree."""

import ast
import inspect
import pathlib
import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.registry import LANGUAGES

# The interpreter tree, anchored to this file rather than the working
# directory, so the sweep finds the same modules wherever pytest was
# started from.
_INTERPRETERS = pathlib.Path(__file__).resolve().parents[1] / (
    "src/esolangs/interpreters"
)

# ``run`` is the entry point the template puts the IO on -- it builds the
# machine, drives it, and is handed the ``IO`` to do it with.  It is the
# one module-level function that is *supposed* to reach the ports.
_IO_OWNER = "run"

# Functions and methods that call an IO effect outside the normal
# ``run``/``_Machine`` shells.  Each is a documented decision rather than a
# lapse, and the reason differs:
#
# * ``forbin._call`` is a documented, nonconforming recursive evaluator.
#   The template does not exempt it: a read or write happens part-way down
#   a recursive descent, so making it pure would require an explicit
#   continuation stack and ordered I/O effects.  The exception stays narrow
#   and visible here until that architecture earns its risk.
# * ``_BitReader.read`` and Suptiftam's ``_State._read_cell`` are the same
#   recursive-evaluation boundary under their owning helper types.
#
# Pinned as a set, in both directions, so it cannot quietly grow and cannot
# go stale.
_MAY_REACH_IO = frozenset(
    {
        ("other/forbin.py", "_BitReader.read"),
        ("other/forbin.py", "_call"),
    }
)


def _io_surface() -> frozenset[str]:
    """Return the IO effect method names, read off the ``IO`` classes."""
    return frozenset(
        name
        for cls in (IO, ScriptedIO)
        for name, _ in inspect.getmembers(cls, callable)
        if not name.startswith("__") and name != "position"
    )


def _module_files() -> list[pathlib.Path]:
    """Return every interpreter module, read off the tree."""
    return sorted(
        [path for path in _INTERPRETERS.glob("*/*.py") if not path.name.startswith("_")]
        + list(_INTERPRETERS.glob("*/*/__init__.py"))
    )


def _is_io_receiver(node: ast.expr) -> bool:
    """Whether ``node`` is the ``io`` object an effect is called through."""
    return (isinstance(node, ast.Name) and node.id == "io") or (
        isinstance(node, ast.Attribute) and node.attr == "io"
    )


def _io_calls(function: ast.FunctionDef, surface: frozenset[str]) -> list[str]:
    """Return the IO effect methods ``function`` calls through an IO receiver."""
    return sorted(
        {
            node.attr
            for node in ast.walk(function)
            if (
                isinstance(node, ast.Attribute)
                and node.attr in surface
                and _is_io_receiver(node.value)
            )
        }
    )


def _reaching_functions() -> dict[tuple[str, str], list[str]]:
    """Return every non-shell function or method that calls into ``IO``."""
    surface = _io_surface()
    found: dict[tuple[str, str], list[str]] = {}
    for path in _module_files():
        relative = path.relative_to(_INTERPRETERS).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name == _IO_OWNER:
                    continue
                calls = _io_calls(node, surface)
                if calls:
                    found[(relative, node.name)] = calls
            elif isinstance(node, ast.ClassDef):
                if node.name == "_Machine":
                    continue
                for method in node.body:
                    if not isinstance(method, ast.FunctionDef):
                        continue
                    calls = _io_calls(method, surface)
                    if calls:
                        found[(relative, f"{node.name}.{method.name}")] = calls
    return found


class TestTheSweepCanSee:
    """The detector's own coverage, which the checks below take on trust."""

    def test_every_registered_interpreter_is_walked(self) -> None:
        """The glob reaches every module the registry names."""
        walked = {
            path.relative_to(_INTERPRETERS)
            .as_posix()
            .removesuffix("/__init__.py")
            .removesuffix(".py")
            for path in _module_files()
        }
        registered = {
            lang.interpreter.replace(".", "/")
            for lang in LANGUAGES.values()
            if lang.interpreter
        }
        assert sorted(registered - walked) == []

    def test_the_io_surface_is_not_empty(self) -> None:
        """``IO`` still has effect methods under the names this reads."""
        surface = _io_surface()
        assert {"print_str", "print_char", "print_value", "input_str"} <= surface


class TestTransitionsDoNotReachIO:
    """The convention itself, pinned in both directions."""

    def test_no_unlisted_module_function_calls_io(self) -> None:
        """Only ``run`` and the pinned exceptions reach the ports."""
        unexpected = {
            where: calls
            for where, calls in _reaching_functions().items()
            if where not in _MAY_REACH_IO
        }
        assert unexpected == {}

    @pytest.mark.parametrize(
        ("module", "function"),
        sorted(_MAY_REACH_IO),
        ids=lambda value: value.replace("/", ".") if isinstance(value, str) else value,
    )
    def test_each_listed_exception_still_reaches_io(
        self, module: str, function: str
    ) -> None:
        """The exception list is exact, so it cannot become a stale roster."""
        assert (module, function) in _reaching_functions()


#: A ``raise`` of a bare exception class, or one with no arguments at all.
_BARE_RAISE = re.compile(
    r"^\s*raise (HaltError|ValueError|ProgramError|EOFError)\s*(\(\s*\))?\s*$"
)


def _wordless_halts() -> dict[str, int]:
    """Count the bare raises in every interpreter, keyed by relative path."""
    found: dict[str, int] = {}
    for path in sorted(_INTERPRETERS.rglob("*.py")):
        hits = sum(
            bool(_BARE_RAISE.match(line))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
        if hits:
            found[str(path.relative_to(_INTERPRETERS))] = hits
    return found


def test_a_bare_halt_still_says_something() -> None:
    """The floor under all of them, so none is ever silent again."""
    assert str(HaltError()) == HaltError.DEFAULT
    assert str(HaltError()).strip()
    # And a real message is not replaced by it.
    assert str(HaltError("the stack is empty")) == "the stack is empty"


def test_no_interpreter_halts_without_saying_why() -> None:
    """A bare ``raise HaltError`` reaches the user as an empty message."""
    found = _wordless_halts()
    assert not found, f"wordless halts: {found} -- give each a message"
    # Pin the regex against samples, so the guard above is not vacuous.
    assert _BARE_RAISE.match("    raise HaltError")
    assert _BARE_RAISE.match("        raise ValueError()")
    assert not _BARE_RAISE.match('    raise HaltError("division by zero")')
    # Modulous was the reported case and is fixed, so it must not be here.
    assert "stack_based/modulous.py" not in _wordless_halts()


def _docstring_issues(path: pathlib.Path, language: str | None) -> list[str]:
    """Return documentation-convention violations for one interpreter."""
    source = path.read_text(encoding="utf-8")
    doc = ast.get_docstring(ast.parse(source)) or ""

    def compact(text: str) -> str:
        """Return a name in comparison form."""
        return re.sub(r"[^a-z0-9]", "", text.lower())

    issues = []
    if len(doc.splitlines()) < 3:
        issues.append("docstring is a bare stub")
    if language is not None and compact(language) not in compact(doc):
        issues.append(f"does not name the language ({language!r})")
    if re.search(r"\.input_(char|str|num)\b", source) and "EOF" not in doc:
        issues.append("reads input but does not document EOF")
    if "raise HaltError" in source and "HaltError" not in doc:
        issues.append("raises HaltError but does not document it")
    if "raise ValueError" in source and "ValueError" not in doc:
        issues.append("raises ValueError but does not document it")
    return issues


def test_interpreter_docstrings_follow_the_template() -> None:
    """Every registered interpreter is walked and documents its behavior."""
    names = {
        lang.interpreter: name for name, lang in LANGUAGES.items() if lang.interpreter
    }
    named_paths = {}
    for module, name in names.items():
        relative = pathlib.Path(*module.split("."))
        path = _INTERPRETERS / relative.with_suffix(".py")
        if not path.exists():
            path = _INTERPRETERS / relative / "__init__.py"
        assert path.is_file(), module
        named_paths[path] = name
    paths = sorted(set(_module_files()) | set(named_paths))
    failures = {
        path.relative_to(_INTERPRETERS).as_posix(): _docstring_issues(
            path, named_paths.get(path)
        )
        for path in paths
    }
    assert {path: issues for path, issues in failures.items() if issues} == {}


class TestEntryPointConventions:
    """The shared ``__main__`` body stays shared, and declares the right shape."""

    @staticmethod
    def _main_call(path: pathlib.Path) -> ast.Call:
        if path.name == "__init__.py":
            path = path.with_name("__main__.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        blocks = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]
        assert len(blocks) == 1, f"{path.name} has {len(blocks)} __main__ blocks"
        (statement,) = blocks[0].body
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Call)
        return statement.value

    @pytest.mark.parametrize(
        "path",
        _module_files(),
        ids=lambda path: path.relative_to(_INTERPRETERS).as_posix(),
    )
    def test_the_shape_matches_what_run_accepts(self, path: pathlib.Path) -> None:
        """``text`` goes to a ``str`` parameter, the line shapes to ``list[str]``."""
        call = self._main_call(path)
        assert isinstance(call.func, ast.Name)
        assert call.func.id == "script_main"
        assert [ast.unparse(arg) for arg in call.args] == ["run"]
        assert {keyword.arg for keyword in call.keywords} <= {"shape", "loader"}
        shape = "text"
        for keyword in call.keywords:
            if keyword.arg == "loader":
                assert ast.unparse(keyword.value) == "load_source"
                shape = "loaded"
                continue
            assert isinstance(keyword.value, ast.Constant)
            shape = keyword.value.value
        assert shape in ("text", "keep", "strip", "loaded")

        tree = ast.parse(path.read_text(encoding="utf-8"))
        run = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == _IO_OWNER
        )
        annotation = run.args.args[0].annotation
        assert annotation is not None, f"{path.name}: run's source is unannotated"
        # Three interpreters accept either form, so membership rather than
        # equality: the shape has to be among what `run` takes, not the only
        # thing it takes.
        accepted = {part.strip() for part in ast.unparse(annotation).split("|")}
        wanted = (
            "Raster"
            if shape == "loaded"
            else ("str" if shape == "text" else "list[str]")
        )
        assert wanted in accepted, (
            f"{path.name}: shape={shape!r} but run takes {accepted}"
        )
