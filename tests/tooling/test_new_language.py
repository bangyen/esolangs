"""Tests for the new-language scaffolder."""

import sys
from pathlib import Path

import pytest

from scripts import new_language
from tests.support.reference import REFERENCE


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    template = tmp_path / "src/esolangs/runtime/_template.py"
    template.parent.mkdir(parents=True)
    real = Path(__file__).parents[2] / "src/esolangs/runtime/_template.py"
    template.write_text(real.read_text())
    monkeypatch.setattr(new_language, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.usefixtures("root")
def test_scaffold_creates_source_generator_and_tests() -> None:
    source, test, descriptor, generator, *packages = new_language.scaffold(
        "Tiny Lang", "other"
    )
    assert (source.name, generator.name) == ("interpreter.py", "generator.py")
    assert (
        source.parent
        == generator.parent
        == new_language.ROOT / "src/esolangs/languages/tiny_lang"
    )
    assert {path.name for path in packages} == {"__init__.py", "language.toml"}
    assert descriptor.name == "descriptor.py"
    assert descriptor.parent == source.parent
    assert "OperationRef" in descriptor.read_text()
    assert test.parent == source.parent / "tests"
    assert test.name == "test_tiny_lang.py"
    assert not (test.parent / "test_boolean_tiny_lang.py").exists()
    stub = source.read_text()
    assert stub.startswith('"""Interpreter for Tiny Lang.')
    assert "<Language>" not in stub
    declaration, implementation = {}, {}
    exec(compile(descriptor.read_text(), str(descriptor), "exec"), declaration)
    exec(compile(stub, str(source), "exec"), implementation)
    runtime = declaration["LANGUAGE"].runtime
    from esolangs.runtime.io import ScriptedIO

    factory = implementation[runtime.machine_preparation]("+.", {})
    first_io, second_io = ScriptedIO(), ScriptedIO()
    first, second = factory(first_io), factory(second_io)
    retained = second.snapshot()
    first.step()
    first.step()
    assert first_io.getvalue() == "\x01"
    assert second.snapshot() == retained
    assert second_io.getvalue() == ""
    native_io = ScriptedIO()
    report = implementation[runtime.completion_entrypoint]("+.", native_io)
    assert runtime.capabilities.accepts_native(report.kind)
    assert native_io.getvalue() == first_io.getvalue()
    assert new_language.PLACEHOLDER in stub
    assert "def tiny_lang(truth_table: str) -> str:" in generator.read_text()
    assert "LANGUAGE" not in generator.read_text()


@pytest.mark.usefixtures("root")
def test_an_interpreter_only_language_gets_no_generator() -> None:
    paths = new_language.scaffold("Tiny", "other", generator=False)
    assert [path.name for path in paths[:2]] == ["interpreter.py", "test_tiny.py"]
    assert paths[1].parent == paths[0].parent / "tests"
    assert any(path.name == "descriptor.py" for path in paths)
    assert not any(path.name == "generator.py" for path in paths)
    assert not (new_language.ROOT / "src/esolangs/generation/tiny.py").exists()


@pytest.mark.usefixtures("root")
@pytest.mark.parametrize("generator", [False, True])
def test_scaffold_compiles_and_registers_a_quoted_name(*, generator: bool) -> None:
    name = 'Tïny """Probe""" \\ lab'
    files = new_language.scaffold(name, "other", generator=generator)
    for path in files:
        if path.suffix != ".py":
            continue
        code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
        if path.name == "descriptor.py":
            namespace = {}
            exec(code, namespace)
            declaration = namespace["LANGUAGE"]
            assert declaration.name == name
            assert declaration.has_backend is generator


def test_scaffold_records_the_language_as_unassessed(root: Path) -> None:
    new_language.scaffold("Tiny Lang", "other", generator=False)
    fragment = root / "src/esolangs/languages/tiny_lang/language.toml"
    assert fragment.read_text().endswith("[curation]\nunassessed = true\n")


def test_scaffold_refuses_overwrite(root: Path) -> None:
    target = root / "src/esolangs/languages/tiny/interpreter.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")
    # A removed language is refused too: readmission reverses a ruling.
    (root / "docs").mkdir()
    (root / "docs/limitations.md").write_text(
        "### Removed languages\n\n| Ground | Languages |\n|---|---|\n"
        "| spec | Gone (a note), Other; deferred: Later |\n\nMore.\n"
    )
    for name in ("Gone", "later"):
        with pytest.raises(ValueError, match="removed on 'spec' grounds"):
            new_language.scaffold(name, "other")


def test_scaffold_refuses_an_existing_namespace_module(root: Path) -> None:
    target = root / "src/esolangs/languages/fixture.py"
    target.parent.mkdir(parents=True)
    target.write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Fixture", "other")
    assert target.read_text() == "owned"
    assert not target.with_suffix("").exists()


@pytest.mark.parametrize("argv", [[], ["Tiny", "--category", "other"]])
def test_start_requires_an_explicit_command(root: Path, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        new_language.main(argv)
    assert caught.value.code == 2
    assert not (root / "src/esolangs/languages").exists()


def test_registration_ignores_old_generator_locations(root: Path) -> None:
    old = root / "src/esolangs/generation/tiny.py"
    old.parent.mkdir(parents=True)
    old.write_text("owned")
    (gap,) = new_language._unregistered("Tiny", "tiny")
    assert gap.where == "src/esolangs/languages/tiny/descriptor.py"


def test_the_slug_is_the_registry_id() -> None:
    """Registry ids cover numeric names and punctuation without slug collisions."""
    from esolangs.registry import LANGUAGES

    for name, lang in LANGUAGES.items():
        assert new_language._slug(name) == lang.id, name
    with pytest.raises(ValueError, match="keyword"):
        new_language._slug("class")


def test_check_flags_a_leftover_placeholder_test(root: Path) -> None:
    new_language.scaffold("Tiny", "other", generator=False)
    assert (root / "src/esolangs/languages/tiny/language.toml").is_file()
    gaps = new_language._common_gaps("Tiny", "tiny")
    assert (
        "src/esolangs/languages/tiny/tests/test_tiny.py",
        "replace the placeholder test",
    ) in {(gap.where, gap.fix) for gap in gaps}


def test_finish_still_runs_the_gate_past_open_steps(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fragment = root / "src/esolangs/languages/tiny/language.toml"
    fragment.parent.mkdir(parents=True)
    fragment.write_text("[curation]\nunassessed = true\n")
    gap = new_language.Gap("somewhere", "do it")
    monkeypatch.setattr(new_language, "check", lambda _: [gap])
    ran = []
    monkeypatch.setattr(new_language, "_gate", lambda: ran.append(1) or 0)
    assert new_language.finish("Tiny") == 1
    assert ran == [1]
    assert "curation unassessed" in capsys.readouterr().out


def test_bounds_generates_each_measured_table_once(monkeypatch: pytest.MonkeyPatch):
    import esolangs
    from tests.proofs.measurement import tables

    generate = esolangs.generate
    generated = []

    def observe(name, table, **options):
        generated.append(table)
        return generate(name, table, **options)

    monkeypatch.setattr(esolangs, "generate", observe)
    (result,) = new_language.bounds(REFERENCE, range(1, 2))
    assert generated == list(tables(REFERENCE, 1))
    assert result[0] == 1


def test_bounds_rejects_impossible_arity_before_measuring(monkeypatch, capsys):
    from esolangs.exceptions import GeneratorCapError
    from esolangs.registry import LANGUAGES

    declaration, cap = next(
        (lang, lang.backend.max_inputs)
        for lang in LANGUAGES.values()
        if lang.backend is not None and lang.backend.max_inputs is not None
    )
    assert declaration.backend is not None
    assert cap is not None
    with pytest.raises(GeneratorCapError) as limit:
        declaration.backend.check_arity(declaration.name, cap + 1)
    monkeypatch.setattr(new_language, "bounds", lambda *_a, **_kw: pytest.fail("sweep"))
    for max_n, error in [
        (0, "--max-n must be positive"),
        (cap + 1, str(limit.value)),
    ]:
        with pytest.raises(SystemExit) as caught:
            new_language.main(["bounds", declaration.name, "--max-n", str(max_n)])
        assert caught.value.code == 2
        assert error in capsys.readouterr().err


def test_bounds_announces_row_work_before_generation(monkeypatch, capsys):
    import esolangs

    generate = esolangs.generate
    reported = []

    def observe(name, table, **options):
        reported.append(capsys.readouterr().out)
        return generate(name, table, **options)

    monkeypatch.setattr(esolangs, "generate", observe)
    monkeypatch.setattr(new_language, "size_anchors", lambda _: [])
    assert new_language.main(["bounds", REFERENCE, "--max-n", "1"]) == 0
    assert "n=1: 4 witnesses, up to 8 row executions" in reported[0]


@pytest.mark.parametrize("gate_status", [0, 1])
def test_gate_runs_the_full_gate_not_a_scoped_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gate_status: int,
) -> None:
    import subprocess

    commands: list[list[str]] = []

    def run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        status = gate_status if "--full" in cmd else 0
        return subprocess.CompletedProcess(cmd, status)

    monkeypatch.setattr(subprocess, "run", run)
    assert new_language._gate() == gate_status
    assert commands[3] == [
        sys.executable,
        "scripts/verify/gate.py",
        "--full",
        "--quiet",
    ]
    assert len(commands) == (5 if gate_status == 0 else 4)
    if gate_status == 0:
        assert "dead definitions" in commands[-1][-1]
    assert "+ scripts/verify/gate.py --full --quiet" in capsys.readouterr().out


def test_check_with_open_steps_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "docs.generate", None)
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
    new_language._report(
        name, [new_language.Gap("source", "implement the interpreter")]
    )
    command = capsys.readouterr().out.split("after fixing these: ")[1].strip()
    assert shlex.split(command) == ["just", "check-language", name]


@pytest.mark.usefixtures("root")
def test_scaffold_reports_the_canonical_generator() -> None:
    new_language.scaffold("Tiny", "other")
    (gap,) = new_language._unregistered("Tiny", "tiny")
    assert gap.where == "src/esolangs/languages/tiny/descriptor.py"


def test_scaffold_collision_is_atomic(root: Path) -> None:
    package = root / "src/esolangs/languages/tiny"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")
    assert not (package / "interpreter.py").exists()
    assert not (root / "src/esolangs/runtime/tiny.py").exists()
    assert (package / "__init__.py").read_text() == "owned"
