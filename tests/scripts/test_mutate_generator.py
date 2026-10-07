"""``tests/tools/mutate_generator.py`` selects the suites and shapes the run."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tests" / "tools" / "mutate_generator.py"
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
        """Selection is the whole directory, not the suites naming a module."""
        script = load_script()
        selected = script._test_files(script._KINDS["tools"])  # noqa: SLF001
        assert selected == sorted(p.name for p in TOOLS_TESTS.glob("test_*.py"))

    def test_the_suites_that_only_import_the_package_are_included(self) -> None:
        """Include suites that reach generators through package re-exports."""
        script = load_script()
        selected = script._test_files(script._KINDS["tools"])  # noqa: SLF001
        assert "test_boolean_three_x.py" in selected
        assert "test_boolean_contract.py" in selected


class TestPytestArgs:
    def test_the_marker_filter_is_not_a_runner_argument(self) -> None:
        """``-m`` must not ride on the runner; mutmut's stats pass ignores it."""
        script = load_script()
        kind = script._KINDS["tools"]  # noqa: SLF001
        args = script._pytest_args(kind, ["test_boolean_rotfuck.py"])  # noqa: SLF001
        assert "-m" not in args

    def test_xdist_is_turned_off(self) -> None:
        """``-n 0``, against the repo's ``addopts`` pinning ``-n 4``."""
        script = load_script()
        kind = script._KINDS["tools"]  # noqa: SLF001
        args = script._pytest_args(kind, ["test_boolean_rotfuck.py"])  # noqa: SLF001
        assert args[args.index("-n") + 1] == "0"

    def test_the_runner_command_quotes_its_arguments(self) -> None:
        """Mutmut splits the runner with ``shlex``, so it must be quoted."""
        import shlex

        script = load_script()
        kind = script._KINDS["tools"]  # noqa: SLF001
        tests = ["test_boolean_rotfuck.py"]
        command = script._runner_command(kind, tests)  # noqa: SLF001
        expected = script._pytest_args(kind, tests)  # noqa: SLF001
        assert shlex.split(command)[3:] == expected


class TestAlarmBudget:
    def test_the_budget_is_bounded_at_both_ends(self) -> None:
        """The alarm has to undercut mutmut's RLIMIT to be worth anything."""
        script = load_script()
        assert script._MIN_ALARM < script._MAX_ALARM  # noqa: SLF001
        # 20s against a measured worst single test of 2.98s.
        assert script._MAX_ALARM >= 3 * 2.98  # noqa: SLF001

    def test_the_conftest_skips_the_alarm_during_the_stats_pass(self) -> None:
        """The stats pass runs under tracing, which the budget never priced."""
        script = load_script()
        conftest = script._CONFTEST  # noqa: SLF001
        assert (
            '_STATS_PASS = os.environ.get("MUTANT_UNDER_TEST") == "stats"' in conftest
        )
        assert "if _budget and not _STATS_PASS:" in conftest

    def test_a_failed_stats_pass_is_not_reported_as_a_score(self) -> None:
        """Mutmut leaves a full meta of zeros when it cannot collect stats."""
        source = (REPO_ROOT / "tests" / "tools" / "mutate_generator.py").read_text()
        assert '"failed to collect stats" in mutation.stdout' in source


class TestUndecorateClasses:
    def test_a_decorated_dataclass_is_rewritten(self, tmp_path: Path) -> None:
        """Mutmut skips a decorated ``ClassDef``, yielding it no mutants."""
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
        """Applying the decorator below the body is what the syntax means."""
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
        assert script._parse_target("tools/decleq") == ("tools", "decleq")  # noqa: SLF001
        assert script._parse_target("tools/wrap") == ("tools", "wrap")  # noqa: SLF001

    def test_an_unambiguous_bare_name_still_resolves(self) -> None:
        """The bare spelling keeps working where it is unambiguous."""
        script = load_script()
        assert script._parse_target("minifuck") == ("tools", "minifuck")  # noqa: SLF001

    def test_a_name_in_both_families_is_refused(self) -> None:
        """The failure this prevents is silent, which is why it is an error."""
        import pytest

        script = load_script()
        kinds = script._KINDS  # noqa: SLF001
        kinds["mirror"] = kinds["tools"]
        # ``_FAMILIES`` is a snapshot taken at import, so the new kind has to
        # be added to both or the lookup never sees it.
        script._FAMILIES = (*script._FAMILIES, "mirror")  # noqa: SLF001
        try:
            with pytest.raises(SystemExit) as excinfo:
                script._parse_target("decleq")  # noqa: SLF001
            message = str(excinfo.value)
            assert "tools/decleq" in message
            assert "mirror/decleq" in message
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
        assert "decleq" in message

    def test_an_unknown_family_is_refused(self) -> None:
        """A qualified target with a bad family names the families instead."""
        import pytest

        script = load_script()
        with pytest.raises(SystemExit) as excinfo:
            script._parse_target("nosuchfamily/register")  # noqa: SLF001
        message = str(excinfo.value)
        assert "nosuchfamily" in message
        assert "tools" in message

    def test_entry_points_are_not_targets(self) -> None:
        """``__init__`` and ``__main__`` hold no generation logic."""
        script = load_script()
        for family in ("tools",):
            modules = script._modules(family)  # noqa: SLF001
            assert "__init__" not in modules
            assert "__main__" not in modules

    def test_every_listed_module_is_a_file_in_its_family(self) -> None:
        """A listed target resolves to a real file, in every kind."""
        script = load_script()
        for family in ("tools",):
            kind = script._KINDS[family]  # noqa: SLF001
            for name in script._modules(family):  # noqa: SLF001
                assert (REPO_ROOT / "src" / kind.rel_target(name)).is_file()

    def test_the_bare_tools_modules_are_a_target_kind(self) -> None:
        """Tools packages expose their implementations and helpers as targets."""
        script = load_script()
        modules = script._modules("tools")  # noqa: SLF001
        assert "wrap" in modules
        assert "boolean" not in modules
        assert {"malbolge", "malbolge.core", "malbolge.digits"} <= set(modules)
        assert script._parse_target("tools/malbolge.core") == ("tools", "malbolge.core")  # noqa: SLF001
        assert script._KINDS["streetcode"].rel_target("geometry") == (  # noqa: SLF001
            "esolangs/interpreters/grid_based/streetcode/geometry.py"
        )
        kind = script._KINDS["tools"]  # noqa: SLF001
        assert kind.rel_target("wrap") == "esolangs/tools/wrap.py"


class TestPrepare:
    @pytest.mark.medium
    def test_focused_generator_baseline_collects(self, tmp_path: Path) -> None:
        script = load_script()
        proj, _ = script._prepare(  # noqa: SLF001
            "tools", "underload", tmp_path, slow=False, selection="underload"
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/tools"],
            cwd=proj,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_the_mutated_path_is_the_requested_family(self, tmp_path: Path) -> None:
        """``paths_to_mutate`` must name the family that was asked for."""
        script = load_script()
        proj, _ = script._prepare("tools", "wrap", tmp_path, slow=False)  # noqa: SLF001
        config = (proj / "pyproject.toml").read_text()
        assert 'paths_to_mutate = ["esolangs/tools/wrap.py"]' in config

    def test_the_mutated_path_and_the_score_path_agree(self, tmp_path: Path) -> None:
        """The file mutmut writes is the file the score is read from."""
        script = load_script()
        proj, _ = script._prepare("tools", "brainfuck", tmp_path, slow=False)  # noqa: SLF001
        config = (proj / "pyproject.toml").read_text()
        mutated = config.split('paths_to_mutate = ["')[1].split('"]')[0]
        # The same expression ``_score`` uses to find mutmut's result file.
        scored = proj / "mutants" / "esolangs" / "tools" / "brainfuck.py.meta"
        assert scored == proj / "mutants" / f"{mutated}.meta"


@pytest.mark.parametrize("selection", [None, "suffolk"])
def test_config_isolates_xdist_and_applies_selection_to_every_pass(
    tmp_path: Path,
    selection: str | None,
) -> None:
    import tomllib

    script = load_script()
    proj, _ = script._prepare(  # noqa: SLF001
        "tools", "suffolk", tmp_path, slow=False, selection=selection
    )
    config = tomllib.loads((proj / "pyproject.toml").read_text())
    options = config["tool"]["pytest"]["ini_options"]["addopts"]
    assert options[:4] == ["-n", "0", "-m", "not slow"]
    assert options[4:] == ([] if selection is None else ["-k", "suffolk"])


def test_interpreter_mutation_discovery_includes_nested_packages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "ROOT", tmp_path)
    package = tmp_path / "src/esolangs/interpreters/demo"
    (package / "ops").mkdir(parents=True)
    for relative in ("__init__.py", "__main__.py", "ops/__init__.py", "ops/step.py"):
        (package / relative).write_text("")
    kind = script._Kind("demo", "interpreters/demo", "tests", (), include_init=True)  # noqa: SLF001
    monkeypatch.setitem(script._KINDS, "demo", kind)  # noqa: SLF001
    assert script._modules("demo") == ["__init__", "ops", "ops.step"]  # noqa: SLF001
    assert kind.rel_target("ops") == "esolangs/interpreters/demo/ops/__init__.py"
    assert kind.rel_target("ops.step") == "esolangs/interpreters/demo/ops/step.py"
