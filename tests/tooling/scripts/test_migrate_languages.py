"""Migration safety and compatibility across generated aliases."""

import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from esolangs.registry import Language
from scripts import migrate_languages as migrate


def test_alias_preserves_private_exports_and_module_state(tmp_path, monkeypatch):
    package = tmp_path / "migration_fixture"
    package.mkdir()
    (package / "__init__.py").write_text("")
    source = package / "legacy.py"
    original = "import math\n_value = 7\ndef run():\n    return _value\n"
    source.write_text(original)
    target = package / "language/interpreter.py"
    migrate.apply(
        [
            migrate.Move(
                source,
                target,
                "migration_fixture.language.interpreter",
                interpreter=False,
            )
        ]
    )
    assert target.read_text() == original
    assert "_value as _value" in source.read_text()
    assert "import math as math" not in source.read_text()
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        old = importlib.import_module("migration_fixture.legacy")
        canonical = importlib.import_module("migration_fixture.language.interpreter")
        assert old is canonical
        assert old.run() == 7
        monkeypatch.setattr(old, "_value", 9)
        assert canonical.run() == 9
    finally:
        for name in tuple(sys.modules):
            if name.startswith("migration_fixture"):
                del sys.modules[name]


def test_collision_does_not_partially_migrate_a_batch(tmp_path):
    source = tmp_path / "first.py"
    source.write_text("value = 1\n")
    target = tmp_path / "first/generator.py"
    blocked = tmp_path / "second/generator.py"
    blocked.parent.mkdir()
    blocked.write_text("owned\n")
    with pytest.raises(FileExistsError):
        migrate.apply(
            [
                migrate.Move(source, target, "first.generator", interpreter=False),
                migrate.Move(
                    tmp_path / "second.py",
                    blocked,
                    "second.generator",
                    interpreter=False,
                ),
            ]
        )
    assert source.read_text() == "value = 1\n"
    assert not target.exists()
    assert blocked.read_text() == "owned\n"


def test_plan_uses_module_name_when_it_differs_from_language_id(tmp_path: Path):
    def boolean(table):
        return table

    boolean.__module__ = "esolangs.tools.different"
    source = tmp_path / "src/esolangs/tools/different.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 1\n")
    lang = Language("Fixture", category="other", boolean=boolean)
    status, moves = migrate.plan(lang, tmp_path)
    assert status == "flat"
    assert moves[0].source == source
    assert moves[0].target == tmp_path / "src/esolangs/languages/fixture/generator.py"


def test_package_selection_refuses_all_writes(monkeypatch, capsys):
    monkeypatch.setattr(migrate, "LANGUAGES", {"Fixture": object()})
    monkeypatch.setattr(migrate, "plan", lambda _: ("package", []))
    monkeypatch.setattr(migrate, "apply", lambda _: pytest.fail("must not write"))
    with pytest.raises(SystemExit, match="2"):
        migrate.main(["Fixture", "--apply"])
    assert "manual migration required" in capsys.readouterr().err


@pytest.mark.parametrize("layout", ["colocated", "package", "missing source"])
def test_plan_classifies_existing_layouts(tmp_path, layout):
    lang = Language("Fixture", "fixture", category="other")
    if layout == "colocated":
        (tmp_path / "src/esolangs/languages/fixture").mkdir(parents=True)
    elif layout == "package":
        package = tmp_path / "src/esolangs/interpreters/fixture"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("value = 1\n")
    status, moves = migrate.plan(lang, tmp_path)
    assert status == layout
    assert bool(moves) == (layout == "package")


def test_flat_selection_skips_packages(monkeypatch):
    lang = Language("Fixture", "fixture", category="other")
    monkeypatch.setattr(migrate, "LANGUAGES", {"Fixture": lang})
    monkeypatch.setattr(migrate, "plan", lambda _: ("package", []))
    applied = []
    monkeypatch.setattr(migrate, "apply", applied.append)
    assert migrate.main(["--flat", "--apply"]) == 0
    assert applied == [[]]


def test_unknown_selection_is_rejected(capsys):
    with pytest.raises(SystemExit, match="2"):
        migrate.main(["unknown migration fixture"])
    assert "unknown languages" in capsys.readouterr().err


def test_shared_source_is_rejected_before_writes(tmp_path):
    source = tmp_path / "shared.py"
    source.write_text("value = 1\n")
    with pytest.raises(ValueError, match="shared implementation"):
        migrate.apply(
            [
                migrate.Move(
                    source,
                    tmp_path / "first/generator.py",
                    "first.generator",
                    interpreter=False,
                ),
                migrate.Move(
                    source,
                    tmp_path / "second/generator.py",
                    "second.generator",
                    interpreter=False,
                ),
            ]
        )
    assert source.read_text() == "value = 1\n"
    assert not (tmp_path / "first").exists()


def test_empty_module_is_rejected(tmp_path):
    source = tmp_path / "empty.py"
    source.write_text('"""Empty."""\n')
    with pytest.raises(ValueError, match="no static exports"):
        migrate.apply(
            [
                migrate.Move(
                    source,
                    tmp_path / "new/generator.py",
                    "new.generator",
                    interpreter=False,
                )
            ]
        )
    assert not (tmp_path / "new").exists()


def test_builtin_export_keeps_its_legacy_name():
    source = migrate._compatibility_module("fixture.generator", ("eval",))  # noqa: SLF001
    assert "import eval as eval  # noqa: A004" in source
    compile(source, "compatibility.py", "exec")


def test_comprehension_temporaries_are_not_static_exports():
    source = "values = [name for name in range(3)]\n"
    assert migrate._exports(source) == ("values",)  # noqa: SLF001


def test_colocated_aliases_share_runtime_state(monkeypatch):
    root = Path(__file__).parents[3] / "src"
    marker = object()
    checked = 0
    for folder in ("interpreters", "tools"):
        for path in (root / "esolangs" / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    continue
                canonical = node.args[0].value
                if not canonical.startswith(
                    "esolangs.languages."
                ) or not canonical.endswith((".interpreter", ".generator")):
                    continue
                parts = path.relative_to(root).with_suffix("").parts
                legacy = ".".join(parts[:-1] if path.name == "__init__.py" else parts)
                old = importlib.import_module(legacy)
                new = importlib.import_module(canonical)
                assert old is new
                monkeypatch.setattr(old, "migration_probe", marker, raising=False)
                assert new.migration_probe is marker
                checked += 1
    assert checked > 0


def test_package_helpers_preserve_identity(tmp_path, monkeypatch):
    package = tmp_path / "package_fixture"
    legacy = package / "legacy"
    legacy.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (legacy / "__init__.py").write_text(
        "from package_fixture.legacy.core import run as run\n__all__ = ['run']\n"
    )
    (legacy / "core.py").write_text("def run(): return 7\n")
    target = package / "language/interpreter"
    migrate.apply(
        [
            migrate.Move(
                legacy,
                target,
                "package_fixture.language.interpreter",
                interpreter=False,
                legacy="package_fixture.legacy",
            )
        ]
    )
    assert not (legacy / "core.py").exists()
    assert (legacy / "core.pyi").exists()
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        old = importlib.import_module("package_fixture.legacy.core")
        new = importlib.import_module("package_fixture.language.interpreter.core")
        assert old is new
        assert old.run() == 7
        assert importlib.import_module("package_fixture.legacy").run is new.run
    finally:
        for name in tuple(sys.modules):
            if name.startswith("package_fixture"):
                del sys.modules[name]


def test_module_rewrites_leave_program_literals_and_comments():
    source = (
        "from old.package import core\n"
        "module = 'old.package.core'\n"
        "program = 'print old.package.core'\n"
        "# old.package.core remains explanatory text\n"
    )
    rewritten = migrate._rewrite_imports(source, {"old.package": "new.package"})  # noqa: SLF001
    assert "from new.package import core" in rewritten
    assert "module = 'new.package.core'" in rewritten
    assert "program = 'print old.package.core'" in rewritten
    assert "# old.package.core" in rewritten


def test_optional_import_fallback_is_not_an_implicit_reexport():
    source = (
        "try:\n    import optional as value\nexcept ImportError:\n    value = None\n"
    )
    assert migrate._exports(source) == ()  # noqa: SLF001
    assert migrate._exports(source + "__all__ = ['value']\n") == ("value",)  # noqa: SLF001


@pytest.mark.parametrize("shape", ["keep", "strip"])
def test_migrated_file_entry_preserves_line_shape(tmp_path, shape):
    package = tmp_path / "entry_fixture"
    package.mkdir()
    (package / "__init__.py").write_text("")
    source = package / "legacy.py"
    expected = ["hello\n"] if shape == "keep" else ["hello"]
    source.write_text(
        "from esolangs.interpreters._entry import script_main\n"
        f"def run(code, io): assert code == {expected!r}\n"
        f"if __name__ == '__main__': script_main(run, shape={shape!r})\n"
    )
    program = tmp_path / "program.txt"
    program.write_text("hello\n")
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    command = [sys.executable, str(source), str(program)]
    before = subprocess.run(
        command, env=env, capture_output=True, check=True, timeout=5
    )
    migrate.apply(
        [
            migrate.Move(
                source,
                package / "language/interpreter.py",
                "entry_fixture.language.interpreter",
                interpreter=True,
            )
        ]
    )
    after = subprocess.run(command, env=env, capture_output=True, check=True, timeout=5)
    assert after.stdout == before.stdout


def test_raster_loader_entry_is_preserved():
    source = "script_main(run, loader=load_source)\n"
    assert migrate._entry_keywords(source) == ", loader=_implementation.load_source"  # noqa: SLF001


def test_unknown_entry_option_aborts():
    with pytest.raises(ValueError, match="unsupported interpreter entry"):
        migrate._entry_keywords("script_main(run, shape=dynamic)\n")  # noqa: SLF001
