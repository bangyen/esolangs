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
        selected = script._test_files(script._KINDS["boolean"])  # noqa: SLF001
        assert selected == sorted(p.name for p in TOOLS_TESTS.glob("test_*.py"))

    def test_the_suites_that_only_import_the_package_are_included(self) -> None:
        """The specific files import-based selection used to drop.

        ``test_boolean_other`` imports ``boolean`` and nothing below it, so
        a scan for ``esolangs.tools.boolean.<module>`` does not select it --
        and it is where every ``laserfuck`` test lives.  Named individually
        because the general assertion above would still pass if the
        directory itself lost it.
        """
        script = load_script()
        selected = script._test_files(script._KINDS["boolean"])  # noqa: SLF001
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
        kind = script._KINDS["boolean"]  # noqa: SLF001
        args = script._pytest_args(kind, ["test_boolean_tape.py"])  # noqa: SLF001
        assert "-m" not in args

    def test_xdist_is_turned_off(self) -> None:
        """``-n 0``, against the repo's ``addopts`` pinning ``-n 4``.

        Without it every one of a few thousand mutants spawns four xdist
        workers to run a suite that takes seconds.
        """
        script = load_script()
        kind = script._KINDS["boolean"]  # noqa: SLF001
        args = script._pytest_args(kind, ["test_boolean_tape.py"])  # noqa: SLF001
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
        kind = script._KINDS["boolean"]  # noqa: SLF001
        tests = ["test_boolean_tape.py"]
        command = script._runner_command(kind, tests)  # noqa: SLF001
        expected = script._pytest_args(kind, tests)  # noqa: SLF001
        assert shlex.split(command)[3:] == expected


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

    def test_the_conftest_skips_the_alarm_during_the_stats_pass(self) -> None:
        """The stats pass runs under tracing, which the budget never priced.

        This is the failure that reported a 0/711 score with a passing
        baseline.  A suite baselining under a second lands the budget at its
        floor; the traced run outruns it, the alarm fails mutmut's *stats*
        pass rather than a mutant, no stats are written, and every mutant is
        skipped as "not checked" while a percentage is still printed.

        mutmut marks that pass by setting ``MUTANT_UNDER_TEST`` to the
        literal ``stats``, so the conftest tells it apart exactly rather
        than by a timing heuristic.  Both directions are asserted: skipping
        under the sentinel is only correct if the alarm still installs for
        the mutant runs it was measured for.
        """
        script = load_script()
        conftest = script._CONFTEST  # noqa: SLF001
        assert (
            '_STATS_PASS = os.environ.get("MUTANT_UNDER_TEST") == "stats"' in conftest
        )
        assert "if _budget and not _STATS_PASS:" in conftest

    def test_a_failed_stats_pass_is_not_reported_as_a_score(self) -> None:
        """mutmut leaves a full meta of zeros when it cannot collect stats.

        Every exit code is still at its initial 0, which scores as
        "everything survived" rather than as the failure it is.  The
        kill-rate floor catches the total case; this message is what catches
        a partial one, and it names the cause instead of leaving a
        plausible-looking percentage to be believed.
        """
        source = (REPO_ROOT / "scripts" / "mutate_generator.py").read_text()
        assert '"failed to collect stats" in mutation.stdout' in source


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


class TestParseTarget:
    def test_a_qualified_target_resolves_in_each_family(self) -> None:
        """Both kinds are reachable, named ``family/module``."""
        script = load_script()
        assert script._parse_target("boolean/register") == ("boolean", "register")  # noqa: SLF001
        assert script._parse_target("tools/wrap") == ("tools", "wrap")  # noqa: SLF001

    def test_an_unambiguous_bare_name_still_resolves(self) -> None:
        """The boolean-only spelling keeps working where it is unambiguous."""
        script = load_script()
        assert script._parse_target("minifuck") == ("boolean", "minifuck")  # noqa: SLF001

    def test_a_name_in_both_families_is_refused(self) -> None:
        """The failure this prevents is silent, which is why it is an error.

        No two kinds currently share a module name -- the text family, which
        shared eight with boolean, is gone -- so the guard has no real input
        and would rot untested.  The kinds are a table, so a synthetic entry
        exercises the same path a future overlap would take: defaulting a
        bare ambiguous name would mutate the wrong file and still print a
        plausible percentage, which is why it is an error.
        """
        import pytest

        script = load_script()
        assert not set(script._modules("boolean")) & set(script._modules("tools"))  # noqa: SLF001
        kinds = script._KINDS  # noqa: SLF001
        kinds["mirror"] = kinds["boolean"]
        # ``_FAMILIES`` is a snapshot taken at import, so the new kind has to
        # be added to both or the lookup never sees it.
        script._FAMILIES = (*script._FAMILIES, "mirror")  # noqa: SLF001
        try:
            with pytest.raises(SystemExit) as excinfo:
                script._parse_target("register")  # noqa: SLF001
            message = str(excinfo.value)
            assert "boolean/register" in message
            assert "mirror/register" in message
        finally:
            del kinds["mirror"]

    def test_an_unknown_module_lists_the_choices(self) -> None:
        """The error names what may be run rather than only what may not."""
        import pytest

        script = load_script()
        with pytest.raises(SystemExit) as excinfo:
            script._parse_target("nosuchmodule")  # noqa: SLF001
        message = str(excinfo.value)
        assert "nosuchmodule" in message
        assert "register" in message

    def test_an_unknown_family_is_refused(self) -> None:
        """A qualified target with a bad family names the families instead."""
        import pytest

        script = load_script()
        with pytest.raises(SystemExit) as excinfo:
            script._parse_target("nosuchfamily/register")  # noqa: SLF001
        message = str(excinfo.value)
        assert "nosuchfamily" in message
        assert "boolean" in message
        assert "tools" in message

    def test_entry_points_are_not_targets(self) -> None:
        """``__init__`` and ``__main__`` hold no generation logic.

        Offering either as a target would spend a run mutating a re-export
        surface or an argv check.
        """
        script = load_script()
        for family in ("boolean", "tools"):
            modules = script._modules(family)  # noqa: SLF001
            assert "__init__" not in modules
            assert "__main__" not in modules

    def test_every_listed_module_is_a_file_in_its_family(self) -> None:
        """A listed target resolves to a real file, in every kind.

        Every kind is the same table, so a path built wrong for one is
        caught here rather than by a run that cannot find its target.
        """
        script = load_script()
        for family in ("boolean", "tools"):
            kind = script._KINDS[family]  # noqa: SLF001
            for name in script._modules(family):  # noqa: SLF001
                assert (kind.pkg_dir / f"{name}.py").exists()

    def test_the_bare_tools_modules_are_a_target_kind(self) -> None:
        """``wrap`` is reachable, and the subpackages are not swept in.

        The kind globs ``*.py`` directly under ``esolangs/tools``, so it
        picks up the modules that sit beside the generator family without
        listing ``boolean`` a second time -- a directory does not match the
        glob.
        """
        script = load_script()
        modules = script._modules("tools")  # noqa: SLF001
        assert "wrap" in modules
        assert "boolean" not in modules
        kind = script._KINDS["tools"]  # noqa: SLF001
        assert kind.rel_target("wrap") == "esolangs/tools/wrap.py"


class TestPrepare:
    def test_the_mutated_path_is_the_requested_family(self, tmp_path: Path) -> None:
        """``paths_to_mutate`` must name the family that was asked for.

        The bug this pins shipped once: the path was built with a literal
        ``boolean`` while the score was read from the target's own family, so
        a target in the other family mutated *boolean's* file and then found
        no result file where it looked.  That mismatch is what made it loud.
        Had both sides shared the wrong literal it would have been silent --
        a run reporting a real, plausible score for a module nobody asked
        about.
        """
        script = load_script()
        proj, _ = script._prepare("tools", "wrap", tmp_path, slow=False)  # noqa: SLF001
        config = (proj / "pyproject.toml").read_text()
        assert 'paths_to_mutate = ["esolangs/tools/wrap.py"]' in config
        assert "boolean/wrap.py" not in config

    def test_the_mutated_path_and_the_score_path_agree(self, tmp_path: Path) -> None:
        """The file mutmut writes is the file the score is read from.

        Asserted as a pair rather than separately: they are two spellings of
        one path in different functions, and the failure mode is them
        drifting apart.
        """
        script = load_script()
        proj, _ = script._prepare("boolean", "tape", tmp_path, slow=False)  # noqa: SLF001
        config = (proj / "pyproject.toml").read_text()
        mutated = config.split('paths_to_mutate = ["')[1].split('"]')[0]
        # The same expression ``_score`` uses to find mutmut's result file.
        scored = proj / "mutants" / "esolangs" / "tools" / "boolean" / "tape.py.meta"
        assert scored == proj / "mutants" / f"{mutated}.meta"
