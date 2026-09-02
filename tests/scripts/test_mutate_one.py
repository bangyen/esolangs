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


class TestDropUnbundledTests:
    """What counts as reaching past the bundle, and what only looks like it.

    A dropped test is invisible in the score: it does not fail, it stops
    existing, and the mutants only it could kill read as survivors.  So
    both directions matter -- dropping a test that would have run costs
    coverage silently, and keeping one that cannot run marks every mutant
    killed for the wrong reason.
    """

    def test_a_reach_is_dropped_however_it_is_spelled(self) -> None:
        """Every syntax that actually leaves the bundle still cuts the test."""
        script = load_script()
        reaches = (
            "from esolangs.vm import run_until_halt_or_cycle",
            "from esolangs.registry import LANGUAGES",
            "import esolangs.vm",
            'import esolangs; esolangs.run("brainfuck", "+")',
        )
        for reach in reaches:
            src = (
                "\nclass TestX:\n"
                "    def test_reaches(self) -> None:\n"
                f"        {reach}\n"
            )
            out, dropped = script._drop_unbundled_tests(src)  # noqa: SLF001
            assert dropped == 1, reach
            assert "test_reaches" not in out, reach

    def test_naming_a_module_in_prose_is_not_a_reach(self) -> None:
        """A comment or docstring must not cut the test that carries it.

        This is a real regression, not a hypothetical.  The check used to
        be a substring scan over the test's text, which cannot tell an
        import from a mention of one -- so a test whose docstring
        explained *why* it copies a shared helper was dropped whole, and
        the mutants only its programs catch went quietly missing.

        The last case is the other half: a module named inside a *string*
        is data, not an import, and this suite really does carry program
        text spelled that way.
        """
        script = load_script()
        mentions = (
            "# unlike esolangs.vm, this one needs no shared walk",
            'x = "from esolangs.vm import run_until_halt_or_cycle"',
            "x = 'mirrors the walk in esolangs.registry, deliberately'",
        )
        for mention in mentions:
            src = (
                "\nclass TestX:\n"
                "    def test_mentions(self) -> None:\n"
                f"        {mention}\n"
                "        assert True\n"
            )
            out, dropped = script._drop_unbundled_tests(src)  # noqa: SLF001
            assert dropped == 0, mention
            assert "test_mentions" in out, mention

    def test_a_module_named_in_a_docstring_is_not_a_reach(self) -> None:
        """The near-miss that prompted this: a test explaining its own copy."""
        script = load_script()
        quotes = '"' * 3
        src = (
            "\nclass TestX:\n"
            "    def test_mentions(self) -> None:\n"
            f"        {quotes}Mirrors the walk in esolangs.vm.{quotes}\n"
            "        assert True\n"
        )
        out, dropped = script._drop_unbundled_tests(src)  # noqa: SLF001
        assert dropped == 0
        assert "test_mentions" in out

    def test_a_test_calling_a_reaching_helper_is_dropped(self) -> None:
        """The reach can be one call deep, and the caller carries no marker."""
        script = load_script()
        src = (
            "\ndef _verdict(machine):\n"
            "    from esolangs.vm import run_until_halt_or_cycle\n"
            "    return run_until_halt_or_cycle(machine)\n"
            "\nclass TestX:\n"
            "    def test_uses_helper(self) -> None:\n"
            "        assert _verdict(None)\n"
            "\n    def test_independent(self) -> None:\n"
            "        assert True\n"
        )
        out, dropped = script._drop_unbundled_tests(src)  # noqa: SLF001
        assert dropped == 1
        assert "test_uses_helper" not in out
        assert "test_independent" in out
