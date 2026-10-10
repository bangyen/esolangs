"""``scripts/mutate_one.py`` repoints imports at the bundled interpreter."""

from pathlib import Path
from typing import Any

import pytest

from tests.scripts.script_support import load
from tests.test_language_coupling import REFERENCE

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "mutate.py"


def load_script() -> Any:
    return load(SCRIPT)


class TestRewriteImports:
    def test_the_interpreter_module_import_becomes_the_bundle(self) -> None:
        """``import <interp> as m`` is an alias for the module being mutated."""
        script = load_script()
        out = script._rewrite_imports(  # noqa: SLF001
            "from esolangs.interpreters.grid_based import toy as module\n",
            "bundled",
            "grid_based.toy",
        )
        assert out.strip() == "import bundled as module"

    def test_a_generator_sharing_the_interpreters_name_is_left_alone(self) -> None:
        """A ``tools`` import is not the interpreter, even spelled alike."""
        script = load_script()
        for line, module in (
            ("from esolangs.tools import toy as gen", "toy"),
            (
                "from esolangs.tools.polynomial import polynomial as gen",
                "polynomial.polynomial",
            ),
            (
                "from esolangs.tools.dimensional import dimensional as gen",
                "dimensional.dimensional",
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
            out = script._rewrite_imports(  # noqa: SLF001
                f"{line}\n", "bundled", "grid_based.toy"
            )
            assert out.strip() == line

    def test_a_top_level_tools_import_is_left_alone(self) -> None:
        """The skip applies to an imported name as well as a submodule."""
        script = load_script()
        line = "from esolangs import tools as boolean_tools"
        out = script._rewrite_imports(  # noqa: SLF001
            f"{line}\n", "bundled", "tape_based.factor"
        )
        assert out.strip() == line

    def test_a_full_interpreter_module_alias_becomes_the_bundle(self) -> None:
        """Monkeypatches and direct imports must address the same module."""
        script = load_script()
        out = script._rewrite_imports(  # noqa: SLF001
            "import esolangs.interpreters.register_based.polynomial as module\n",
            "bundled",
            "register_based.polynomial",
        )
        assert out.strip() == "import bundled as module"

    def test_an_ordinary_package_import_is_repointed(self) -> None:
        """The names a bundled suite needs come from the bundle itself."""
        script = load_script()
        out = script._rewrite_imports(  # noqa: SLF001
            "from esolangs.interpreters.grid_based.toy import _Machine\n",
            "bundled",
            "grid_based.toy",
        )
        assert out.strip() == "from bundled import _Machine"


class TestDropUnbundledTests:
    """What counts as reaching past the bundle, and what only looks like it."""

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
        """A comment or docstring must not cut the test that carries it."""
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


@pytest.mark.medium
def test_scratch_directory_under_repo_does_not_inherit_xdist(tmp_path: Path) -> None:
    import tomllib

    script = load_script()
    proj, *_ = script._prepare(REFERENCE, tmp_path)  # noqa: SLF001
    config = tomllib.loads((proj / "pyproject.toml").read_text())
    assert config["tool"]["pytest"]["ini_options"]["addopts"] == ["-n", "0"]
