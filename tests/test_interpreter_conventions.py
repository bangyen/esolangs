r"""Source-shape conventions the interpreters share, swept over the."""

import ast
import inspect
import pathlib
import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.registry import RUNNERS

# The interpreter tree,.
# directory: the suite is run.
# relative path resolves.
_INTERPRETERS = pathlib.Path(__file__).resolve().parents[1] / (
    "src/esolangs/interpreters"
)

# ``run`` is the entry point.
# machine, drives it, and is.
# one module-level function.
_IO_OWNER = "run"

# Functions and methods that.
# ``run``/``_Machine`` shells.
# lapse, and the reason.
# .
# * ``forbin._call`` and.
# documented, nonconforming.
# exempt them: a read or write.
# so making either pure would.
# ordered I/O effects.
# that architecture earns its.
# * ``_BitReader.read`` and.
# recursive-evaluation boundary.
# .
# Pinned as a set, in both.
# go stale -- the same shape as.
_MAY_REACH_IO = frozenset(
    {
        ("other/forbin.py", "_BitReader.read"),
        ("other/forbin.py", "_call"),
        ("other/suptiftam.py", "_State._read_cell"),
        ("register_based/myscript.py", "_schedule_expr"),
        ("register_based/myscript.py", "_apply_builtin"),
    }
)


def _io_surface() -> frozenset[str]:
    r"""Return the IO effect method names, read off the ``IO`` classes."""
    return frozenset(
        name
        for cls in (IO, ScriptedIO)
        for name, _ in inspect.getmembers(cls, callable)
        if not name.startswith("__") and name != "position"
    )


def _module_files() -> list[pathlib.Path]:
    r"""Return every interpreter module, read off the tree."""
    return sorted(
        path for path in _INTERPRETERS.glob("*/*.py") if not path.name.startswith("_")
    )


def _is_io_receiver(node: ast.expr) -> bool:
    r"""Whether ``node`` is the ``io`` object an effect is called through."""
    return (isinstance(node, ast.Name) and node.id == "io") or (
        isinstance(node, ast.Attribute) and node.attr == "io"
    )


def _io_calls(function: ast.FunctionDef, surface: frozenset[str]) -> list[str]:
    r"""Return the IO effect methods ``function`` calls through an IO."""
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
    r"""Return every non-shell function or method that calls into ``IO``."""
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


def _machine_declarations(path: pathlib.Path) -> tuple[ast.ClassDef, ast.FunctionDef]:
    r"""Return a module's one steppable machine and its constructor."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert any(
        (isinstance(node, ast.ClassDef) and node.name == "_State")
        or (
            isinstance(node, ast.TypeAlias)
            and isinstance(node.name, ast.Name)
            and node.name.id == "_State"
        )
        for node in tree.body
    ), f"{path.relative_to(_INTERPRETERS)} must declare its complete _State"
    machine = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "_Machine"
        ),
        None,
    )
    assert machine is not None, f"{path.relative_to(_INTERPRETERS)} has no _Machine"
    init = next(
        (
            node
            for node in machine.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        ),
        None,
    )
    assert init is not None, (
        f"{path.relative_to(_INTERPRETERS)} has no _Machine.__init__"
    )
    return machine, init


class TestTheSweepCanSee:
    r"""The detector's own coverage, which the checks below take on trust."""

    def test_every_registered_interpreter_is_walked(self) -> None:
        r"""The glob reaches every module the registry names."""
        walked = {
            path.relative_to(_INTERPRETERS).as_posix().removesuffix(".py")
            for path in _module_files()
        }
        registered = {module.replace(".", "/") for module, _ in RUNNERS.values()}
        assert sorted(registered - walked) == []

    def test_the_io_surface_is_not_empty(self) -> None:
        r"""``IO`` still has effect methods under the names this reads."""
        surface = _io_surface()
        assert {"print_str", "print_char", "print_value", "input_str"} <= surface


class TestMachineConventions:
    r"""The common construction and state boundary stay explicit."""

    @pytest.mark.parametrize(
        "path",
        _module_files(),
        ids=lambda path: path.relative_to(_INTERPRETERS).as_posix(),
    )
    def test_machine_declares_state_and_accepts_io(self, path: pathlib.Path) -> None:
        r"""A machine has one named state boundary and a source/I/O constructor."""
        machine, init = _machine_declarations(path)
        members = {
            node.name
            for node in machine.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert {"step", "snapshot"} <= members
        assert "of" not in members
        has_halted_assignment = any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr == "halted"
                for target in node.targets
            )
            for node in ast.walk(init)
        )
        assert "halted" in members or has_halted_assignment

        positional = init.args.posonlyargs + init.args.args
        assert len(positional) >= 3
        assert positional[0].arg == "self"
        assert positional[2].arg == "io"


class TestTransitionsDoNotReachIO:
    r"""The convention itself, pinned in both directions."""

    def test_no_unlisted_module_function_calls_io(self) -> None:
        r"""Only ``run`` and the pinned exceptions reach the ports."""
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
        r"""The exception list is exact, so it cannot become a stale roster."""
        assert (module, function) in _reaching_functions()


# : Interpreters still raising.
# :.
# : A bare ``raise HaltError``.
# : ``esolangs run`` forwarded.
# : at all and exited 1 --.
# : successful program that.
# : Modulous was not special,.
# :.
# :.
# : these is silent.
# : of fault and admits it does.
# : work that remains rather.
# : because its four were given.
# : stack is empty, so there is.
# :.
# : The numbers only go down.
# : point: the cheap thing when.
# : and move on, and that is.
_WORDLESS_HALTS: dict[str, int] = {}

# : A ``raise`` of a bare.
_BARE_RAISE = re.compile(
    r"^\s*raise (HaltError|ValueError|ProgramError|EOFError)\s*(\(\s*\))?\s*$"
)


def _wordless_halts() -> dict[str, int]:
    r"""Count the bare raises in every interpreter, keyed by relative path."""
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
    r"""The floor under all of them, so none is ever silent again."""
    assert str(HaltError()) == HaltError.DEFAULT
    assert str(HaltError()).strip()
    # And a real message is not.
    assert str(HaltError("the stack is empty")) == "the stack is empty"


def test_no_interpreter_halts_without_saying_why() -> None:
    r"""The inventory only shrinks."""
    found = _wordless_halts()
    grew = {
        name: (count, _WORDLESS_HALTS.get(name, 0))
        for name, count in found.items()
        if count > _WORDLESS_HALTS.get(name, 0)
    }
    assert not grew, (
        "these interpreters gained a wordless halt (now, allowed): "
        f"{grew} -- give it a message rather than raising the bare class"
    )
    fixed = {
        name: (found.get(name, 0), allowed)
        for name, allowed in _WORDLESS_HALTS.items()
        if found.get(name, 0) < allowed
    }
    assert not fixed, (
        f"these improved and the table did not follow: {fixed} -- "
        "lower the counts in _WORDLESS_HALTS"
    )


def test_the_scan_finds_the_ones_it_is_meant_to() -> None:
    r"""A regex that matched nothing would make the guard above vacuous."""
    assert sum(_wordless_halts().values()) == sum(_WORDLESS_HALTS.values())
    # The ledger is empty, so the.
    # than against a count of the.
    assert _BARE_RAISE.match("    raise HaltError")
    assert _BARE_RAISE.match("        raise ValueError()")
    assert not _BARE_RAISE.match('    raise HaltError("division by zero")')
    # Modulous was the reported.
    assert "stack_based/modulous.py" not in _wordless_halts()
