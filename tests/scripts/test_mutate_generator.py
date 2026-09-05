"""``scripts/mutate_generator.py`` selects the suites and shapes the run.

Every failure this pins is silent.  A generator mutation run that selects
too few suites still prints a percentage, and the percentage looks
plausible -- it is simply over a smaller set of killers than exist, so
survivors are reported that the suite would in fact have caught.  Selecting
by import did exactly that for 19 of the 27 generator modules before it was
replaced by a glob, which is why the breadth is asserted here rather than
trusted to stay wide.

The other two are the same shape: a ``-m`` that mutmut's stats pass ignores
scores every mutant zero, and an uncapped per-test alarm sits above
mutmut's RLIMIT and never fires.  Neither raises; both just produce a wrong
number.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "mutate_generator.py"
TOOLS_TESTS = REPO_ROOT / "tests" / "tools"
BOOLEAN = REPO_ROOT / "src" / "esolangs" / "tools" / "boolean"


def load_script() -> object:
    """Import the harness as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("mutate_generator", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestTestFiles:
    def test_every_suite_in_tests_tools_is_selected(self) -> None:
        """Selection is the whole directory, not the suites naming a module.

        The narrowings that were tried each left a blind spot: importing
        misses the suites that reach a generator through the package
        re-export (``boolean.laserfuck``), and resolving attribute access
        still misses ``test_generate``, which dispatches through a table.
        Comparing against the directory listing means a new suite is
        included the moment it is added, with nothing to remember.
        """
        script = load_script()
        selected = script._test_files()  # noqa: SLF001
        assert selected == sorted(p.name for p in TOOLS_TESTS.glob("test_*.py"))

    def test_the_suites_that_only_import_the_package_are_included(self) -> None:
        """The specific files import-based selection used to drop.

        ``test_generate`` and ``test_boolean_other`` import ``boolean`` and
        nothing below it, so a scan for ``esolangs.tools.boolean.<module>``
        selects neither -- while ``test_boolean_other`` is where every
        ``laserfuck`` test lives.  Named individually because the general
        assertion above would still pass if the directory itself lost them.
        """
        script = load_script()
        selected = script._test_files()  # noqa: SLF001
        assert "test_generate.py" in selected
        assert "test_boolean_other.py" in selected
        assert "test_boolean_contract.py" in selected


class TestPytestArgs:
    def test_the_marker_filter_is_not_a_runner_argument(self) -> None:
        """``-m`` must not ride on the runner; mutmut's stats pass ignores it.

        The stats pass supplies its own arguments, so a ``-m "not slow"``
        here filtered the baseline and the mutant runs while the stats pass
        collected the slow tests anyway.  A 4s Minifuck build then ran under
        mutmut's tracing, blew the per-test alarm, and failed the stats pass
        -- scoring every mutant zero.  The filter belongs in the work
        directory's ``addopts``, which all three passes honour.
        """
        script = load_script()
        args = script._pytest_args(["test_boolean_tape.py"])  # noqa: SLF001
        assert "-m" not in args

    def test_xdist_is_turned_off(self) -> None:
        """``-n 0``, against the repo's ``addopts`` pinning ``-n 4``.

        Without it every one of a few thousand mutants spawns four xdist
        workers to run a suite that takes seconds.
        """
        script = load_script()
        args = script._pytest_args(["test_boolean_tape.py"])  # noqa: SLF001
        assert args[args.index("-n") + 1] == "0"

    def test_the_runner_command_quotes_its_arguments(self) -> None:
        """mutmut splits the runner with ``shlex``, so it must be quoted.

        Joining the list on spaces and splitting it again is what turned
        ``-m "not slow"`` into two arguments, matching no tests at all --
        which the baseline then reported as the suite failing before any
        mutation.
        """
        import shlex

        script = load_script()
        tests = ["test_boolean_tape.py"]
        command = script._runner_command(tests)  # noqa: SLF001
        assert shlex.split(command)[3:] == script._pytest_args(tests)  # noqa: SLF001


class TestAlarmBudget:
    def test_the_budget_is_bounded_at_both_ends(self) -> None:
        """The alarm has to undercut mutmut's RLIMIT to be worth anything.

        It converts a mutant that *hangs* the suite into one that fails it;
        both are kills, but a hang costs the whole ``(estimate + 1) * 30``
        CPU-second limit.  ``elapsed * _ALARM_FACTOR`` off the ~40s baseline
        this harness measures would sit far above that and never fire.  The
        floor guards the other direction, where a slow-but-passing test is
        failed and scored as a kill no mutation earned.
        """
        script = load_script()
        assert script._MIN_ALARM < script._MAX_ALARM  # noqa: SLF001
        # 20s against a measured worst single test of 2.98s.
        assert script._MAX_ALARM >= 3 * 2.98  # noqa: SLF001


class TestUndecorateClasses:
    def test_a_decorated_dataclass_is_rewritten(self, tmp_path: Path) -> None:
        """mutmut skips a decorated ``ClassDef``, yielding it no mutants.

        ``tape.py`` has five ``@dataclass`` nodes modelling the emitted
        program, so left decorated they contribute nothing while the run
        still prints a percentage over whatever else was mutated.
        """
        script = load_script()
        target = tmp_path / "gen.py"
        target.write_text(
            "from dataclasses import dataclass\n\n\n"
            "@dataclass\nclass _Cmd:\n    x: int\n"
        )
        moved = script._undecorate_classes(target)  # noqa: SLF001
        assert moved == ["dataclass to _Cmd"]
        text = target.read_text()
        assert "@dataclass\nclass _Cmd" not in text
        assert "_Cmd = dataclass(_Cmd)" in text

    def test_an_undecorated_module_is_left_alone(self, tmp_path: Path) -> None:
        """Nothing to move means the file is not rewritten at all."""
        script = load_script()
        target = tmp_path / "gen.py"
        source = "def build(table: str) -> str:\n    return table\n"
        target.write_text(source)
        assert script._undecorate_classes(target) == []  # noqa: SLF001
        assert target.read_text() == source

    def test_the_rewrite_preserves_the_dataclass_behaviour(
        self, tmp_path: Path
    ) -> None:
        """Applying the decorator below the body is what the syntax means.

        The point of the rewrite is that the class still behaves
        identically -- same ``__init__``, same ``__eq__`` -- so this
        executes the rewritten module rather than reading it.
        """
        script = load_script()
        target = tmp_path / "gen.py"
        target.write_text(
            "from dataclasses import dataclass\n\n\n"
            "@dataclass\nclass _Cmd:\n    x: int\n    y: str = 'a'\n"
        )
        script._undecorate_classes(target)  # noqa: SLF001
        namespace: dict[str, object] = {}
        exec(compile(target.read_text(), str(target), "exec"), namespace)
        cmd = namespace["_Cmd"]
        assert cmd(1) == cmd(1, "a")  # type: ignore[operator]
        assert cmd(1) != cmd(2, "a")  # type: ignore[operator]


class TestModulePath:
    def test_a_real_generator_module_resolves(self) -> None:
        """Every module the package ships is a valid target."""
        script = load_script()
        assert script._module_path("register") == BOOLEAN / "register.py"  # noqa: SLF001

    def test_an_unknown_module_lists_the_choices(self) -> None:
        """The error names what may be run rather than only what may not."""
        import pytest

        script = load_script()
        with pytest.raises(SystemExit) as excinfo:
            script._module_path("nosuchmodule")  # noqa: SLF001
        message = str(excinfo.value)
        assert "nosuchmodule" in message
        assert "register" in message
