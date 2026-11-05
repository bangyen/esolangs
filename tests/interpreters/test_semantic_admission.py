"""Every admitted language executes its bounded checks and detects a live fault."""

import copy
from dataclasses import replace

import pytest

from esolangs.registry import LANGUAGES
from scripts.docs import semantic
from scripts.docs.fragments import section


def _check_trace_diagnostics(tmp_path, monkeypatch):
    path = tmp_path / "test_trace_control.py"
    path.write_text(
        "import pytest\n"
        "from esolangs.languages.brainfuck.interpreter import run\n"
        "from esolangs.runtime.io import ScriptedIO\n"
        "def test_control():\n"
        "    with pytest.raises(AssertionError):\n"
        "        assert [(0,) * 20] * 64 == [(0,) * 19 + (1,)] * 64\n"
        "    io = ScriptedIO('')\n"
        "    run('.', io)\n"
        "    assert io.getvalue() == '\\x00'\n"
    )
    record = semantic.Evidence("examples", "interpreter.py", (f"{path}::test_control",))
    with monkeypatch.context() as patch:
        patch.setattr(semantic, "load", lambda _: record)
        assert semantic.verify("brainfuck", tmp_path / "probe") == (1, 1)


@pytest.mark.medium
@pytest.mark.parametrize("name", LANGUAGES)
def test_semantic_evidence(name, tmp_path, monkeypatch):
    passed, caught = semantic.verify(name, tmp_path)
    assert passed
    assert caught
    if name == next(iter(LANGUAGES)):
        _check_trace_diagnostics(tmp_path, monkeypatch)
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
