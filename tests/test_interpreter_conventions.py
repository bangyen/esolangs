"""Source-shape conventions the interpreters share, swept over the tree.

``_template.py`` asks every interpreter to be written as a *pure
transition* over an immutable state: the module-level helpers take a state
and return the next one, reaching no ``IO``, and ``_Machine.step`` is the
thin shell that performs the reads and writes.  That split is what lets a
test call a transition on a hand-built state, and it keeps the effects in
one place instead of scattered through the dispatch.

Nothing enforced it.  The convention is prose in a template, and the two
sweeps that look like they would catch a violation do not: the VM protocol
tests drive machines and never read the source, and
:meth:`~tests.test_vm_protocol.TestEveryLanguageIsPure.
test_a_run_writes_nothing_to_the_real_streams` catches output escaping to
the *real* stdout, which a helper writing properly through the ``io`` it
was handed does not do.  A language that moved its dispatch into a
module-level function and let it print would pass every existing test.

So this file asks the source-shape question the runtime cannot: which
functions call an IO effect outside the public ``run``/``_Machine`` shell.
The answer is a closed, deliberate set -- there is no drift to fix, which
is the point.  The sweep is a net that fails when it grows.
"""

import ast
import inspect
import pathlib

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.registry import RUNNERS

# The interpreter tree, anchored to this file rather than the working
# directory: the suite is run from the repo root and from ``extra/``, and a
# relative path resolves differently in the two.
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
# * ``forbin._call`` and MyScript's ``_parse_expr``/``_apply_builtin`` are
#   documented, nonconforming recursive evaluators.  The template does not
#   exempt them: a read or write happens part-way down a recursive descent,
#   so making either pure would require an explicit continuation stack and
#   ordered I/O effects.  The exceptions stay narrow and visible here until
#   that architecture earns its risk.
# * ``_BitReader.read`` and Suptiftam's ``_State._read_cell`` are the same
#   recursive-evaluation boundary under their owning helper types.
#
# Pinned as a set, in both directions, so it cannot quietly grow and cannot
# go stale -- the same shape as ``RAISES_ON_THE_POST_HALT_STEP``.
_MAY_REACH_IO = frozenset(
    {
        ("other/forbin.py", "_BitReader.read"),
        ("other/forbin.py", "_call"),
        ("other/suptiftam.py", "_State._read_cell"),
        ("register_based/myscript.py", "_parse_expr"),
        ("register_based/myscript.py", "_apply_builtin"),
    }
)


def _io_surface() -> frozenset[str]:
    """Return the IO effect method names, read off the ``IO`` classes.

    Derived rather than listed.  A hand-written list is a second thing to
    keep in step with ``io.py``, and the first draft of this sweep proved
    the cost: it omitted ``print_value``, so MyScript's ``_apply_builtin``
    -- which prints through exactly that -- looked pure.  A detector with a
    hole in it reports a clean tree because it is not looking, which is the
    failure this whole file exists to prevent.
    """
    return frozenset(
        name
        for cls in (IO, ScriptedIO)
        for name, _ in inspect.getmembers(cls, callable)
        if not name.startswith("__") and name != "position"
    )


def _module_files() -> list[pathlib.Path]:
    """Return every interpreter module, read off the tree.

    Globbed rather than listed by category.  ``scripts/check_docstrings.py``
    walked a hard-coded four-name category tuple that predated
    ``grid_based`` and ``queue_based``, so twelve of the sixty-three
    interpreters were exempt from it and three real violations sat behind
    the omission.  A walk that discovers the tree cannot acquire that hole.
    """
    return sorted(
        path for path in _INTERPRETERS.glob("*/*.py") if not path.name.startswith("_")
    )


def _is_io_receiver(node: ast.expr) -> bool:
    """Whether ``node`` is the ``io`` object an effect is called through.

    A method named ``position`` is not necessarily :meth:`IO.position`:
    code cursors use the same ordinary word.  The original module-level
    sweep happened not to see that collision; walking methods makes the
    receiver part of the question.  Ports are either a local ``io`` or an
    attribute such as ``self.io``/``reader.io``.
    """
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


def _machine_declarations(path: pathlib.Path) -> tuple[ast.ClassDef, ast.FunctionDef]:
    """Return a module's one steppable machine and its constructor.

    This deliberately reads the source instead of importing it.  Importing
    proves only that today's module happens to build a VM; this pins the
    convention a new interpreter must follow before its runner is ever
    registered.  The runtime protocol suite separately proves that the
    declared members work.
    """
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
    """The detector's own coverage, which the checks below take on trust."""

    def test_every_registered_interpreter_is_walked(self) -> None:
        """The glob reaches every module the registry names.

        Without this the sweep could pass by walking the wrong directory,
        or by missing a category the way the docstring checker missed two.
        """
        walked = {
            path.relative_to(_INTERPRETERS).as_posix().removesuffix(".py")
            for path in _module_files()
        }
        registered = {module.replace(".", "/") for module, _ in RUNNERS.values()}
        assert sorted(registered - walked) == []

    def test_the_io_surface_is_not_empty(self) -> None:
        """``IO`` still has effect methods under the names this reads.

        A rename in ``io.py`` that emptied the derived surface would make
        every check below vacuous -- passing because it detects nothing.
        """
        surface = _io_surface()
        assert {"print_str", "print_char", "print_value", "input_str"} <= surface


class TestMachineConventions:
    """The common construction and state boundary stay explicit.

    The VM protocol checks a constructed machine's behaviour, but cannot
    tell whether a module has drifted back to an ``of`` factory or stopped
    naming its complete state.  Every registered module therefore names its
    state and takes the source plus I/O at the machine boundary.  Extra
    constructor arguments remain free for genuine language dependencies
    such as deterministic randomness.
    """

    @pytest.mark.parametrize(
        "path",
        _module_files(),
        ids=lambda path: path.relative_to(_INTERPRETERS).as_posix(),
    )
    def test_machine_declares_state_and_accepts_io(self, path: pathlib.Path) -> None:
        """A machine has one named state boundary and a source/I/O constructor."""
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
    """The convention itself, pinned in both directions."""

    def test_no_unlisted_module_function_calls_io(self) -> None:
        """Only ``run`` and the pinned exceptions reach the ports.

        A language that moved its dispatch to a module-level helper and
        printed from it -- abandoning the transition/shell split without
        anybody noticing -- fails here and nowhere else.
        """
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
        """The exception list is exact, so it cannot become a stale roster.

        An entry whose function was renamed, deleted, or refactored back
        into a shell stops excusing anything.  Left unchecked the list
        would slowly fill with names nobody had reconfirmed, which is how
        an exception set turns into a place violations hide.
        """
        assert (module, function) in _reaching_functions()
