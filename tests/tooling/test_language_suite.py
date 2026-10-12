"""Uniform entry points preserve case globals and pytest declarations."""

from types import ModuleType
from typing import Any

import pytest

from tests.support import language_suite


@pytest.mark.parametrize("kind", ["interpreter", "generator"])
def test_cases_keep_their_globals_and_entry_point_identity(monkeypatch, kind) -> None:
    cases = ModuleType("cases")
    exec("value = 7\ndef test_value():\n    assert value == 7\n", vars(cases))
    marker = pytest.mark.medium
    fixture = pytest.fixture(lambda: 7)
    cases.pytestmark = marker
    vars(cases)["_fixture"] = fixture
    imported = []

    def import_cases(name: str) -> ModuleType:
        imported.append(name)
        return cases

    monkeypatch.setattr(language_suite, "import_module", import_cases)
    namespace: dict[str, Any] = {"__name__": "entry", "__file__": "entry.py"}
    language_suite.load_suite(namespace, "example", kind)
    assert imported == [f"esolangs.languages.example.tests.{kind}_cases"]
    assert namespace["__name__"] == "entry"
    assert namespace["__file__"] == "entry.py"
    assert namespace["pytestmark"] is marker
    assert namespace["_fixture"] is fixture
    assert namespace["test_value"] is cases.test_value
    namespace["value"] = 9
    namespace["test_value"]()


def test_unknown_suite_kind_is_rejected_before_import(monkeypatch) -> None:
    def refuse_import(_name: str) -> ModuleType:
        raise AssertionError("invalid configuration imported a module")

    monkeypatch.setattr(language_suite, "import_module", refuse_import)
    with pytest.raises(ValueError, match="unknown suite kind"):
        language_suite.load_suite({}, "example", "invalid")


def test_case_assertions_are_registered_before_collection(
    tmp_path, monkeypatch
) -> None:
    folder = tmp_path / "example/tests"
    folder.mkdir(parents=True)
    (folder / "interpreter_cases.py").touch()
    (folder / "generator_cases.py").touch()
    (folder / "test_example.py").touch()
    registered = []
    monkeypatch.setattr(language_suite, "LANGUAGES", tmp_path)
    monkeypatch.setattr(
        language_suite.pytest,
        "register_assert_rewrite",
        lambda *names: registered.extend(names),
    )
    language_suite.register_case_assertions()
    assert registered == [
        "esolangs.languages.example.tests.generator_cases",
        "esolangs.languages.example.tests.interpreter_cases",
    ]
