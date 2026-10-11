"""Tests for the new-language scaffolder."""

import sys
from pathlib import Path

import pytest

from scripts import new_language, remove_language
from tests.reference import REFERENCE


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    template = tmp_path / "src/esolangs/interpreters/_template.py"
    template.parent.mkdir(parents=True)
    template.write_text('"""Template for a new esolang interpreter.\n"""\n')
    monkeypatch.setattr(new_language, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.usefixtures("root")
def test_scaffold_creates_source_generator_and_tests() -> None:
    source, test, generator, generator_test, *packages = new_language.scaffold(
        "Tiny Lang", "other"
    )
    assert (source.name, generator.name) == ("interpreter.py", "generator.py")
    assert (
        source.parent
        == generator.parent
        == new_language.ROOT / "src/esolangs/languages/tiny_lang"
    )
    assert {path.name for path in packages} == {"__init__.py"}
    assert test.parent == generator_test.parent == source.parent / "tests"
    assert (test.name, generator_test.name) == (
        "test_tiny_lang.py",
        "test_boolean_tiny_lang.py",
    )
    assert "Interpreter for Tiny Lang." in source.read_text()
    assert "def tiny_lang(truth_table: str) -> str:" in generator.read_text()


@pytest.mark.usefixtures("root")
def test_an_interpreter_only_language_gets_no_generator() -> None:
    paths = new_language.scaffold("Tiny", "other", generator=False)
    assert [path.name for path in paths[:2]] == ["interpreter.py", "test_tiny.py"]
    assert paths[1].parent == paths[0].parent / "tests"
    assert not any(path.name == "generator.py" for path in paths)
    assert not (new_language.ROOT / "src/esolangs/tools/tiny.py").exists()


def test_scaffold_records_the_language_as_unassessed(root: Path) -> None:
    curation = root / "tests/support/fixtures/curation.toml"
    curation.parent.mkdir(parents=True)
    curation.write_text('[languages]\nKept = { route = "fame" }\n')
    new_language.scaffold("Tiny Lang", "other", generator=False)
    assert curation.read_text().endswith('"Tiny Lang" = { route = "unassessed" }\n')


def test_scaffold_refuses_overwrite(root: Path) -> None:
    target = root / "src/esolangs/languages/tiny/interpreter.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")


def test_scaffold_refuses_a_shared_namespace_module(root: Path) -> None:
    target = root / "src/esolangs/languages/generators.py"
    target.parent.mkdir(parents=True)
    target.write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Generators", "other")
    assert target.read_text() == "owned"
    assert not target.with_suffix("").exists()


@pytest.mark.parametrize("argv", [[], ["Tiny", "--category", "other"]])
def test_start_requires_an_explicit_command(root: Path, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        new_language.main(argv)
    assert caught.value.code == 2
    assert not (root / "src/esolangs/languages").exists()


def test_registration_ignores_old_generator_locations(root: Path) -> None:
    old = root / "src/esolangs/tools/tiny.py"
    old.parent.mkdir(parents=True)
    old.write_text("owned")
    (gap,) = new_language._unregistered("Tiny", "tiny")  # noqa: SLF001
    assert gap.where == "src/esolangs/registry/_table.py"


def test_the_slug_is_the_registry_id() -> None:
    """A second slug rule refused ``123`` and gave Piet++ Piet's file."""
    from esolangs.registry import LANGUAGES

    for name, lang in LANGUAGES.items():
        assert new_language._slug(name) == lang.id, name  # noqa: SLF001
    with pytest.raises(ValueError, match="keyword"):
        new_language._slug("class")  # noqa: SLF001


def test_remove_cuts_only_entries_that_own_their_lines(tmp_path: Path) -> None:
    path = tmp_path / "table.py"
    path.write_text(
        "from esolangs.tools.gone import gone\n"
        "from esolangs.tools.gone import PAIR\n"
        'T = {\n    "kept": PAIR,\n    # gone\'s note\n    "gone": 1,\n}\n'
        'L = ["gone", "kept"]\n'
        'run_gone = _runner("gone")\n'
    )
    modules = {"esolangs.tools.gone"}
    assert remove_language._drop_entries(path, {"gone"}, modules) == 3  # noqa: SLF001
    # The import another entry still uses stays.
    assert path.read_text() == (
        "from esolangs.tools.gone import PAIR\n"
        'T = {\n    "kept": PAIR,\n}\nL = ["gone", "kept"]\n'
    )


def test_remove_drops_the_whole_limitations_bullet(tmp_path: Path) -> None:
    path = tmp_path / "limitations.md"
    path.write_text("- Gone reads\n  past EOF.\n- Gonero stays.\n  Kept.\n")
    remove_language._drop_bullets(path, "Gone")  # noqa: SLF001
    assert path.read_text() == "- Gonero stays.\n  Kept.\n"


def test_remove_drops_a_catalogue_entry(tmp_path: Path) -> None:
    """A per-language ``"Name" = "reason"`` row goes, its neighbours stay."""
    path = tmp_path / "catalogue.toml"
    path.write_text('[local]\n"Gone" = "its mechanism"\n"Kept" = "another"\n')
    remove_language._drop_toml(path, "Gone")  # noqa: SLF001
    assert path.read_text() == '[local]\n"Kept" = "another"\n'


def test_remove_drops_a_link_bullet(tmp_path: Path) -> None:
    """A ``- [Name](url): ...`` curation bullet goes, its neighbour stays."""
    path = tmp_path / "limitations.md"
    path.write_text(
        "- [Gone](https://x/) (7): integrated.\n  continued.\n"
        "- [Kept](https://y/): stays.\n"
    )
    remove_language._drop_bullets(path, "Gone")  # noqa: SLF001
    assert path.read_text() == "- [Kept](https://y/): stays.\n"


def test_check_flags_a_leftover_placeholder_test(root: Path) -> None:
    new_language.scaffold("Tiny", "other", generator=False)
    fixtures = root / "tests/support/fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "curation.toml").write_text("[languages]\n")
    gaps = new_language._common_gaps("Tiny", "tiny")  # noqa: SLF001
    assert (
        "src/esolangs/languages/tiny/tests/test_tiny.py",
        "replace the placeholder test",
    ) in {(gap.where, gap.fix) for gap in gaps}


def test_finish_still_runs_the_gate_past_open_steps(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures = root / "tests/support/fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "curation.toml").write_text(
        '[languages]\nTiny = { route = "unassessed" }\n'
    )
    gap = new_language.Gap("somewhere", "do it")
    monkeypatch.setattr(new_language, "check", lambda _: [gap])
    ran = []
    monkeypatch.setattr(new_language, "_gate", lambda: ran.append(1) or 0)
    assert new_language.finish("Tiny") == 1
    assert ran == [1]
    assert "curation unassessed" in capsys.readouterr().out


def test_check_with_open_steps_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import types

    # main imports ``from docs.generate import update_exports``; shadow that
    # module, not a bare ``generate``, or the real writer runs against ROOT
    # and rewrites src/esolangs/languages/generators.py in the working tree.
    fake = types.ModuleType("docs.generate")
    fake.update_exports = lambda *_: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docs.generate", fake)
    gap = new_language.Gap("somewhere", "do it")
    monkeypatch.setattr(new_language, "check", lambda _: [gap])
    assert new_language.main(["check", "Tiny"]) == 0
    assert "1 step(s) left" in capsys.readouterr().out


@pytest.mark.usefixtures("root")
@pytest.mark.parametrize("interpreter_only", [False, True])
def test_start_prints_the_matching_contributor_workflow(
    *, interpreter_only: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["start", "Tiny Lang", "--category", new_language.CATEGORIES[0]]
    if interpreter_only:
        args.append("--interpreter-only")
    assert new_language.main(args) == 0
    output = capsys.readouterr().out
    next_step = next(line for line in output.splitlines() if line.startswith("next:"))
    assert ("generator" in next_step) is not interpreter_only
    assert "then: just check-language 'Tiny Lang'" in output


def test_gap_report_prints_a_shell_safe_followup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import shlex

    name = "Tiny's $Lang"
    new_language._report(  # noqa: SLF001
        name, [new_language.Gap("source", "implement the interpreter")]
    )
    command = capsys.readouterr().out.split("after fixing these: ")[1].strip()
    assert shlex.split(command) == ["just", "check-language", name]


def test_remove_refuses_the_reference_language() -> None:
    """``brainfuck`` is spelled out by shared tests and generate.py."""
    with pytest.raises(ValueError, match="reference language"):
        remove_language.remove(REFERENCE)


def test_mention_edit_labels_the_edit_each_path_needs() -> None:
    """The report says what to do, not just where the mention is."""
    label = remove_language._mention_edit  # noqa: SLF001
    assert label("src/esolangs/cli/help.py:171:  Gone 0110").startswith("example")
    assert label("docs/limitations.md:253:... Gone ...").startswith("prose")
    assert label("tests/generators/test_wrap.py:66:# ... Gone ...").startswith(
        "comment"
    )
    assert label(".pre-commit-config.yaml:6:# ... Gone ...").startswith("comment")


def test_owner_id_prefers_the_longest_id() -> None:
    ids = {"piet", "piet_plus_plus", "line", "back"}
    owner = remove_language._owner_id  # noqa: SLF001
    assert owner("piet_plus_plus.toml", ids) == "piet_plus_plus"
    assert owner("piet.toml", ids) == "piet"
    assert owner("back_routes.py", ids) == "back"
    # ``linearity`` is not ``line``'s: the id must end at a name boundary.
    assert owner("linearity.py", ids) is None


def test_stale_timing_matches_any_parametrize_component() -> None:
    names = {"Line", "line", "Piet"}
    gone = {"src/esolangs/languages/line/tests/test_boolean_line.py"}
    stale = remove_language._stale_timing  # noqa: SLF001
    assert stale("x.py::t[1-Line]", names, gone)
    assert stale("x.py::t[Line-2]", names, gone)
    assert stale("x.py::t[a-Line-b]", names, gone)
    assert stale("x.py::t[Line]", names, gone)
    assert stale(
        "src/esolangs/languages/line/tests/test_boolean_line.py::t", names, gone
    )
    # ``Piet++`` is another language: only a whole ``-``-delimited part counts.
    assert not stale("x.py::t[Piet++-5]", names, gone)
    assert not stale("x.py::t[Piet++]", names, gone)
    assert not stale("x.py::t", names, gone)


@pytest.mark.parametrize(
    "test_root", ["tests/generators", "src/esolangs/languages/tiny/tests"]
)
def test_dead_test_files_catch_a_submodule_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_root: str
) -> None:
    pkg = tmp_path / "src/esolangs/tools/pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "sub.py").write_text("thing = 1\n")
    tests = tmp_path / test_root
    tests.mkdir(parents=True)
    (tests / "test_sub.py").write_text("from esolangs.tools.pkg.sub import thing\n")
    (tests / "test_shared.py").write_text(
        "import esolangs.tools.pkg.sub\nimport esolangs\n"
    )
    monkeypatch.setattr(remove_language, "ROOT", tmp_path)
    doomed = {pkg}
    gone = remove_language._gone_modules(doomed)  # noqa: SLF001
    users = {
        "esolangs.tools.pkg.sub": {
            f"{test_root}/test_sub.py",
            f"{test_root}/test_shared.py",
        }
    }
    assert remove_language._dead_test_files(doomed, gone, users) == {  # noqa: SLF001
        tests / "test_sub.py"
    }


def test_orphans_drop_a_helper_only_the_language_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "src/esolangs/tools"
    tools.mkdir(parents=True)
    (tools / "gone.py").write_text("from esolangs.tools.helper import h\n")
    (tools / "helper.py").write_text("h = 1\n")
    monkeypatch.setattr(remove_language, "ROOT", tmp_path)
    doomed = {tools / "gone.py"}
    private = {"esolangs.tools.helper": {"src/esolangs/tools/gone.py"}}
    assert remove_language._orphans(doomed, private) == {  # noqa: SLF001
        tools / "helper.py"
    }
    shared = {
        "esolangs.tools.helper": {
            "src/esolangs/tools/gone.py",
            "src/esolangs/tools/keeper.py",
        }
    }
    assert remove_language._orphans(doomed, shared) == set()  # noqa: SLF001


def test_drop_dead_code_keeps_live_and_cuts_dead(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text(
        "_OPS = {1: 2}\n"
        "_OPS |= {3: 4}\n"
        "def used() -> int:\n"
        "    return _OPS[1]\n"
        "def dead() -> int:\n"
        "    return _GONE[1]\n"
        "_GONE = {5: 6}\n"
    )
    assert remove_language._drop_dead_code(path, {"used"}) == 2  # noqa: SLF001
    text = path.read_text()
    # ``_OPS`` is read by a live function and by its own ``|=``: kept.
    assert "_OPS" in text
    assert "def used" in text
    assert "def dead" not in text
    assert "_GONE" not in text


def test_drop_name_items_cuts_set_and_dict_keys(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text(
        "def a() -> None: ...\n"
        "def b() -> None: ...\n"
        "S = frozenset({a, b})\n"
        "D = {a: 1, b: 2}\n"
    )
    remove_language._drop_name_items(path, {"a"})  # noqa: SLF001
    text = path.read_text()
    assert "frozenset({b})" in text
    assert "{b: 2}" in text


@pytest.mark.usefixtures("root")
def test_scaffold_reports_the_canonical_generator() -> None:
    new_language.scaffold("Tiny", "other")
    (gap,) = new_language._unregistered("Tiny", "tiny")  # noqa: SLF001
    assert gap.where == "src/esolangs/languages/tiny/generator.py"


def test_scaffold_collision_is_atomic(root: Path) -> None:
    package = root / "src/esolangs/languages/tiny"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")
    assert not (package / "interpreter.py").exists()
    assert not (root / "src/esolangs/interpreters/tiny.py").exists()
    assert (package / "__init__.py").read_text() == "owned"


@pytest.mark.medium
@pytest.mark.parametrize("generator", [False, True])
def test_remove_cleans_language_package(
    root: Path, monkeypatch: pytest.MonkeyPatch, *, generator: bool
) -> None:
    import subprocess
    import types

    from esolangs import registry
    from esolangs.registry import Language

    created = new_language.scaffold("Tiny", "other", generator=generator)
    namespace = root / "src/esolangs/languages/__init__.py"
    owned = set(created) - {namespace}
    for relative in remove_language._EDITED:  # noqa: SLF001
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    for relative in (
        "tests/support/fixtures/curation.toml",
        "src/esolangs/proof_status.toml",
        "tests/support/fixtures/sharing_catalogue.toml",
        "tests/support/fixtures/canonical_folding_catalogue.toml",
        "tests/support/fixtures/deep_arities.toml",
        "docs/limitations.md",
        "docs/proofs/index.md",
        "src/esolangs/tools/wrap.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    (root / "tests/support/fixtures/generator_sizes.json").write_text("{\n}\n")
    for relative in (
        "src/esolangs/languages/tiny/tests/fixtures/wiki_examples/tiny.toml",
        "src/esolangs/languages/tiny/tests/proofs/helper.py",
        "src/esolangs/languages/tiny/examples/tiny.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
        owned.add(path)

    def tiny(truth_table: str) -> str:
        return truth_table

    tiny.__module__ = "esolangs.languages.tiny.generator"
    lang = Language(
        "Tiny", "tiny", category="other", boolean=tiny if generator else None
    )
    monkeypatch.setitem(registry.LANGUAGES, "Tiny", lang)
    if generator:
        module = types.ModuleType(tiny.__module__)
        module.LANGUAGE = lang
        monkeypatch.setitem(sys.modules, tiny.__module__, module)
    monkeypatch.setattr(remove_language, "ROOT", root)
    real_run = subprocess.run
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "seed fixture",
        ],
    ):
        real_run(command, cwd=root, check=True, capture_output=True)

    def run(command, **kwargs):
        if command[0] == "git":
            return real_run(command, **kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    remove_language.remove("Tiny")
    assert not any(path.exists() for path in owned)
    assert namespace.exists()
    assert not (root / "src/esolangs/languages/tiny").exists()


def test_eval_source_listing_includes_its_canonical_generator():
    assert "src/esolangs/languages/eval/generator.py" in new_language.sources("Eval")


def test_eval_removal_owns_its_canonical_generator():
    from esolangs.registry import LANGUAGES

    modules, paths = remove_language._owned_module_paths(LANGUAGES["Eval"])  # noqa: SLF001
    assert "esolangs.languages.eval.generator" in modules
    assert remove_language.ROOT / "src/esolangs/languages/eval/generator.py" in paths
