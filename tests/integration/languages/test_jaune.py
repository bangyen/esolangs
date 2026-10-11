"""Public integration for the language."""

import importlib

import pytest


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("esolangs.interpreters.jaune", "esolangs.languages.jaune.interpreter"),
        ("esolangs.tools.jaune", "esolangs.languages.jaune.generator"),
    ],
)
def test_compatibility_imports_share_module_state(legacy, canonical, monkeypatch):
    old = importlib.import_module(legacy)
    new = importlib.import_module(canonical)
    assert old is new
    marker = object()
    monkeypatch.setattr(old, "compatibility_probe", marker, raising=False)
    assert new.compatibility_probe is marker
