"""``scripts/mutate_one.py`` repoints imports at the bundled interpreter.

The mutation harness rewrites a language's test suite so it exercises the
single bundled module rather than the installed package -- otherwise no
mutant is visible and the run aborts before scoring anything.  These tests
pin which imports that rewrite may touch, because the failure mode is
quiet: a wrongly-rewritten import does not raise at rewrite time, it makes
the *bundled* suite fail in a way that looks like the interpreter's own
tests are broken.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "mutate_one.py"


def load_script() -> object:
    """Import the harness as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("mutate_one", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestRewriteImports:
    def test_the_interpreter_module_import_becomes_the_bundle(self) -> None:
        """``import <interp> as m`` is an alias for the module being mutated.

        This is the case the module-alias rule exists for: the suite wants
        the interpreter *module*, and the bundle is that module.
        """
        script = load_script()
        out = script._rewrite_imports(  # noqa: SLF001
            "from esolangs.interpreters.grid_based import streetcode as module\n",
            "bundled",
            "grid_based.streetcode",
        )
        assert out.strip() == "import bundled as module"

    def test_a_generator_sharing_the_interpreters_name_is_left_alone(self) -> None:
        """A ``tools`` import is not the interpreter, even spelled alike.

        Several languages name their generator after the interpreter, so
        ``from esolangs.tools.boolean import streetcode as gen`` has the
        same leaf as ``grid_based.streetcode``.  The module-alias rule used
        to match it and bind ``gen`` to the bundled interpreter; the suite
        then called ``gen("00110100")`` and died with "'module' object is
        not callable" before a single mutant ran.  ``tools`` is on the
        skip list for exactly this reason, and the rule has to honour it.
        """
        script = load_script()
        for line, module in (
            ("from esolangs.tools.boolean import streetcode as gen", "streetcode"),
            (
                "from esolangs.tools.text.register import polynomial as gen",
                "register.polynomial",
            ),
            (
                "from esolangs.tools.boolean.tape import dimensional as gen",
                "tape.dimensional",
            ),
        ):
            out = script._rewrite_imports(f"{line}\n", "bundled", module)  # noqa: SLF001
            assert out.strip() == line, module

    def test_the_vm_and_registry_imports_are_left_alone(self) -> None:
        """Nothing outside the bundle is mutated, so those keep resolving."""
        script = load_script()
        for line in (
            "from esolangs.vm import run_until_halt_or_cycle",
            "from esolangs.registry import RUNNERS",
        ):
            out = script._rewrite_imports(f"{line}\n", "bundled", "grid_based.cod")  # noqa: SLF001
            assert out.strip() == line

    def test_an_ordinary_package_import_is_repointed(self) -> None:
        """The names a bundled suite needs come from the bundle itself."""
        script = load_script()
        out = script._rewrite_imports(  # noqa: SLF001
            "from esolangs.interpreters.grid_based.streetcode import _Machine\n",
            "bundled",
            "grid_based.streetcode",
        )
        assert out.strip() == "from bundled import _Machine"
