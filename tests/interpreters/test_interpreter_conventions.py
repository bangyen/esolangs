"""Source-shape conventions the interpreters share, swept over the tree."""

import ast
import importlib
import inspect
import pathlib
import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.registry import LANGUAGES
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import machine_traits
from tests.interpreters.spec_sections import (
    PUBLIC_ERRORS,
    SECTIONS,
    error_entries,
    headers,
)

# The interpreter tree, anchored to this file rather than the working
# directory, so the sweep finds the same modules wherever pytest was
# started from.
_INTERPRETERS = pathlib.Path(__file__).resolve().parents[2] / ("src/esolangs")

# ``run`` is the entry point the template puts the IO on -- it builds the
# machine, drives it, and is handed the ``IO`` to do it with.  It is the
# one module-level function that is *supposed* to reach the ports.
_IO_OWNER = "run"

#: A module's own ``REACHES_IO`` names the functions and methods that call
#: an IO effect outside the normal ``run``/``_Machine`` shells -- each a
#: documented decision, with its reason beside it.  Pinned in both
#: directions below, so the list cannot quietly grow or go stale, and it
#: leaves with its language.
_EXCEPTIONS = "REACHES_IO"


def _may_reach_io() -> frozenset[tuple[str, str]]:
    """Return every ``(module, function)`` a module lists in ``REACHES_IO``."""
    found: set[tuple[str, str]] = set()
    for path in _module_files():
        relative = path.relative_to(_INTERPRETERS).as_posix()
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == _EXCEPTIONS
                    for t in node.targets
                )
                and isinstance(node.value, ast.Call)
            ):
                for name in ast.literal_eval(node.value.args[0]):
                    found.add((relative, name))
    return frozenset(found)


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
    paths = []
    for language in LANGUAGES.values():
        if language.interpreter is None:
            continue
        module = importlib.import_module(
            f"esolangs.languages.{language.id}.interpreter"
        )
        paths.append(pathlib.Path(inspect.getfile(module)))
    return sorted(paths)


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
            pathlib.Path(
                inspect.getfile(
                    importlib.import_module(f"esolangs.languages.{lang.id}.interpreter")
                )
            )
            .relative_to(_INTERPRETERS)
            .as_posix()
            .removesuffix("/__init__.py")
            .removesuffix(".py")
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
            if where not in _may_reach_io()
        }
        assert unexpected == {}

    @pytest.mark.parametrize(
        ("module", "function"),
        sorted(_may_reach_io()),
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
    for path in sorted(
        set((_INTERPRETERS / "interpreters").rglob("*.py")) | set(_module_files())
    ):
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
    # The public name: the runtime turns an interpreter's ValueError into
    # ProgramError, which is what a caller catches.
    if "raise ValueError" in source and not {"ValueError", "ProgramError"} & set(
        re.findall(r"\w+", doc)
    ):
        issues.append("raises ValueError but does not document it")
    if re.search(r"^Implementation:$", doc, re.MULTILINE):
        issues.append("implementation notes belong in comments beside the code")
    if language is not None:
        files = (
            sorted(path.parent.glob("*.py")) if path.name == "__init__.py" else [path]
        )
        package = "\n".join(f.read_text(encoding="utf-8") for f in files)
        # A read at EOF raises unless the language supplies a value there or
        # (Suffolk) catches EOFError to halt.
        eof_raises = (
            re.search(r"\.input_(char|str|num)\b", package) is not None
            and not machine_traits(language)["eof_is_a_value"]
            and "except EOFError" not in package
        )
        issues += _spec_issues(doc, package, eof_raises=eof_raises)
    return issues


def _spec_issues(doc: str, package: str, *, eof_raises: bool = False) -> list[str]:
    """Return violations of the spec template (``runtime/_template.py``).

    ``package`` is the source of every module in the interpreter's package.
    """
    issues = []
    found = headers(doc)
    names = [name for _, name in found]
    if unknown := [name for name in names if name not in SECTIONS]:
        issues.append(f"sections outside the template: {unknown}")
    known = [name for name in names if name in SECTIONS]
    if known != sorted(set(known), key=SECTIONS.index):
        issues.append(f"sections out of order or repeated: {known}")
    lines = doc.splitlines()
    for i, name in found:
        if i + 1 >= len(lines) or not lines[i + 1].startswith("    "):
            issues.append(f"{name}: body is not indented")
    entries = error_entries(doc)
    if entries - PUBLIC_ERRORS:
        issues.append(f"Errors: names non-public {sorted(entries - PUBLIC_ERRORS)}")
    if "raise HaltError" in package and "HaltError" not in entries:
        issues.append("raises HaltError but Errors: does not list it")
    # A ValueError surfaces as ProgramError, or as ArgumentError when it
    # rejects a dialect setting (run() validates those first).
    if (
        "raise ValueError" in package
        and not {"ProgramError", "ArgumentError"} & entries
    ):
        issues.append("raises ValueError but Errors: does not list ProgramError")
    if eof_raises and "InputExhaustedError" not in entries:
        issues.append("a read at EOF raises but Errors: omits InputExhaustedError")
    if ".input_num" in package and "ArgumentError" not in entries:
        issues.append("reads numbers but Errors: omits ArgumentError")
    return issues


@pytest.mark.parametrize(
    ("doc", "package", "expected"),
    [
        ("A.\n\nNotes:\n    x", "", "outside the template"),
        ("A.\n\nErrors:\n    HaltError: x\n\nCommands:\n    x", "", "out of order"),
        ("A.\n\nErrors:\nHaltError: x", "", "not indented"),
        ("A.\n\nErrors:\n    ValueError: x", "", "non-public"),
        ("A.\n\nHaltError in prose.", "raise HaltError(x)", "HaltError but"),
        ("A.\n\nErrors:\n    HaltError: x", "raise ValueError(x)", "ProgramError"),
        (
            "A.\n\nErrors:\n    InputExhaustedError: x",
            "io.input_num()",
            "ArgumentError",
        ),
    ],
)
def test_the_spec_check_catches_each_violation(
    doc: str, package: str, expected: str
) -> None:
    """Positive control: each rule fires on a docstring that breaks it."""
    assert any(expected in issue for issue in _spec_issues(doc, package))


def test_the_spec_check_requires_input_exhausted_where_eof_raises() -> None:
    """Positive control for the EOF rule, which the caller decides."""
    issues = _spec_issues("A.\n\nEOF raises.", "", eof_raises=True)
    assert any("InputExhaustedError" in issue for issue in issues)


def test_the_spec_check_passes_the_template_shape() -> None:
    """Negative control: a conforming spec raises nothing."""
    doc = (
        "A.\n\nInput/output:\n    EOF reads 0.\n\nErrors:\n"
        "    ProgramError: x\n    HaltError: y\n    ArgumentError: z"
    )
    package = "raise ValueError\nraise HaltError\nio.input_num()"
    assert _spec_issues(doc, package) == []


def test_interpreter_docstrings_follow_the_template() -> None:
    """Every registered interpreter is walked and documents its behavior."""
    names = {
        lang.interpreter: name for name, lang in LANGUAGES.items() if lang.interpreter
    }
    named_paths = {}
    for module, name in names.items():
        path = pathlib.Path(
            inspect.getfile(
                importlib.import_module(f"esolangs.languages.{module}.interpreter")
            )
        )
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


#: The modules an interpreter draws from; a generator's ``random`` is not one.
_RANDOM_SOURCES = {"random", "esolangs.runtime.randomness"}


def _draws_at_random(module: str) -> bool:
    """Whether the interpreter's own files import a randomness source."""
    path = pathlib.Path(
        inspect.getfile(
            importlib.import_module(f"esolangs.languages.{module}.interpreter")
        )
    )
    files = sorted(path.parent.glob("*.py")) if path.name == "__init__.py" else [path]
    for file in files:
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import) and any(
                alias.name in _RANDOM_SOURCES for alias in node.names
            ):
                return True
            if isinstance(node, ast.ImportFrom) and node.module in _RANDOM_SOURCES:
                return True
    return False


def test_the_random_flag_matches_the_interpreter() -> None:
    """``random=`` is declared by hand; the interpreter's imports decide it."""
    drawing = {
        name
        for name, lang in LANGUAGES.items()
        if lang.interpreter and _draws_at_random(lang.interpreter)
    }
    flagged = {name for name, lang in LANGUAGES.items() if lang.random}
    assert drawing  # the import scan fires, so an empty diff is not vacuous
    assert {
        "drawing but not random=True": sorted(drawing - flagged),
        "random=True but never drawing": sorted(flagged - drawing),
    } == {"drawing but not random=True": [], "random=True but never drawing": []}


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
