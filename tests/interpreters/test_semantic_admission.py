"""Every admitted language executes its bounded checks and detects a live fault."""

import copy
from dataclasses import replace

import pytest

from esolangs.registry import LANGUAGES
from scripts.docs import semantic
from scripts.docs.fragments import section


@pytest.mark.medium
@pytest.mark.parametrize("name", LANGUAGES)
def test_semantic_evidence(name, tmp_path, monkeypatch):
    passed, caught = semantic.verify(name, tmp_path)
    assert passed
    assert caught
    if name == next(iter(LANGUAGES)):
        record = semantic.load(name)
        path = (
            semantic.ROOT
            / "src/esolangs/languages"
            / LANGUAGES[name].id
            / "language.toml"
        )
        data = section(path, "semantic_evidence")
        for update in (
            {"version": True},
            {"kind": "unknown"},
            {"tests": []},
            {"contract": "../interpreter.py"},
            {"tests": ["tests/api/test_api.py::test_run"]},
            {"tests": [*record.tests, record.tests[0]]},
        ):
            bad = copy.deepcopy(data) | update
            with pytest.raises(ValueError, match="semantic"):
                semantic.parse(name, bad)

        # A passing assertion that never enters the shell cannot certify it.
        path = tmp_path / "test_inert.py"
        path.write_text("def test_inert():\n    assert 1 + 1 == 2\n")
        inert = replace(record, tests=(f"{path}::test_inert",))
        monkeypatch.setattr(semantic, "load", lambda _: inert)
        with pytest.raises(AssertionError, match="undetected output fault"):
            semantic.verify(name, tmp_path / "inert")
