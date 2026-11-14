"""Certification policy cannot change backend operation."""

import ast
import importlib
import inspect
import subprocess
import sys
from dataclasses import fields

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._certification import load as load_certification
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec
from tests.support.pick import languages


def test_certification_facts_have_one_owner(monkeypatch):
    names = {field.name for field in fields(CertificationSpec)}
    assert names.isdisjoint(field.name for field in fields(Language))
    assert names.isdisjoint(field.name for field in fields(RuntimeSpec))
    assert "certification" not in {field.name for field in fields(Language)}
    for lang in LANGUAGES.values():
        record = load_certification(lang)
        assert isinstance(record, CertificationSpec)
        if record.payload is not None:
            assert (
                record.payload.__module__
                == f"esolangs.languages.{lang.id}.certification"
            )

    from types import SimpleNamespace

    from esolangs.registry import _certification
    from tests.support.reference import REFERENCE

    monkeypatch.setattr(
        _certification,
        "import_module",
        lambda _name: SimpleNamespace(CERTIFICATION=None),
    )
    with pytest.raises(TypeError, match="CertificationSpec"):
        load_certification(LANGUAGES[REFERENCE])

    def broken(_name):
        raise ModuleNotFoundError(
            "missing evidence dependency", name="evidence_dependency"
        )

    monkeypatch.setattr(_certification, "import_module", broken)
    with pytest.raises(ModuleNotFoundError, match="missing evidence dependency"):
        load_certification(LANGUAGES[REFERENCE])


@pytest.mark.parametrize("language", languages(boolean_generator=True))
def test_clearing_certification_preserves_generated_source(language, monkeypatch):
    original = LANGUAGES[language]
    module = importlib.import_module(original.backend.generate.__module__)
    assert not hasattr(module, "LANGUAGE")
    tree = ast.parse(inspect.getsource(module))
    reads = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    metadata = {
        "esolangs.registry._backend",
        "esolangs.registry._contracts",
        "esolangs.registry._language",
        "esolangs.runtime._definition",
    }
    assert not {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module in metadata or node.module.endswith(".descriptor"))
        for alias in node.names
        if (alias.asname or alias.name) not in reads
    }
    assert not {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith(".proof_formulas")
    }
    before = esolangs.to_json(language, esolangs.generate(language, "01"))
    path = f"esolangs.languages.{original.id}.certification"
    load_certification(original)
    if path in sys.modules:
        monkeypatch.setattr(sys.modules[path], "CERTIFICATION", CertificationSpec())
    after = esolangs.to_json(language, esolangs.generate(language, "01"))
    assert after == before


@pytest.mark.medium
def test_operational_catalog_and_execution_do_not_import_certification():
    import json

    from tests.support.certification_barrier import WORKER_GUARD
    from tests.support.reference import REFERENCE
    from tests.support.samples import SAMPLES

    code = """
import importlib.abc
import json
import os
import sys
class Barrier(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.blocked = []
        self.fatal = False
    def find_spec(self, fullname, path, target=None):
        if fullname.endswith(('._certification', '.certification', '.proof_formulas')):
            if self.fatal:
                os._exit(86)
            self.blocked.append(fullname)
            raise ImportError('certification is not operational')
barrier = Barrier()
sys.meta_path.insert(0, barrier)
import esolangs
from unittest.mock import patch
from esolangs.registry import LANGUAGES
from dataclasses import replace
from esolangs.debugger import make_debugger
samples = json.loads(sys.argv[2])
assert set(samples) == {n for n, l in LANGUAGES.items() if l.backend is None}
generated = 0
executed = set()
stepped = periodic = 0
for name in esolangs.list_languages():
    info = esolangs.describe(name)
    language = LANGUAGES[name]
    if language.backend is None:
        program, stdin = samples[name]
    else:
        termination = language.contract.answer_mode == 'termination'
        table, bit = ('00', 0) if termination else ('01', 1)
        artifact = esolangs.generate(name, table)
        restored = esolangs.from_json(name, esolangs.to_json(name, artifact))
        assert restored == artifact, name
        if language.parameterized:
            program = esolangs.instantiate(name, restored, [bit])
            stdin = ''
        else:
            program = restored
            stdin = esolangs.encode_inputs(name, [bit], truth_table=table)
        generated += 1
    seed = language.runtime.reproducible_seed if language.runtime.random else None
    result = esolangs.run(name, program, stdin=stdin, seed=seed)
    assert result.completion is not None, name
    assert language.runtime.capabilities.accepts_native(result.completion.kind), name
    assert result.input_position is not None and result.input_reads is not None, name
    if language.backend is not None and language.contract.answer_mode != 'termination':
        assert esolangs.read_answer(name, result.output) == str(bit), name
    debugger = make_debugger(name, program, stdin=stdin, seed=seed)
    if debugger.steppable_to_answer:
        limits = esolangs.ExecutionLimits(max_steps=100_000)
        assert debugger.run(limits=limits) == 'halted', name
        stepped += 1
        observed = debugger.observation
        assert observed.steps > 0, name
        assert observed == replace(result, steps=observed.steps), (
            name, observed, result)
        debugger.step()
        assert debugger.observation == observed, name
    else:
        periodic += 1
        cycle = result.completion.cycle
        assert cycle is not None, name
        steps = cycle.repeat_pass * cycle.commands_per_pass
        for _ in range(steps):
            debugger.step()
        assert debugger.snapshot() == cycle.state, name
        assert debugger.observation.completion is None, name
    executed.add(name)
assert generated == sum(lang.backend is not None for lang in LANGUAGES.values()) > 0
assert executed == set(LANGUAGES)
assert periodic == 1 and stepped == len(LANGUAGES) - 1, (stepped, periodic)
assert not barrier.blocked, barrier.blocked

# Workers start fresh interpreters; install the guard before their first import.
from esolangs.runtime import _isolated
original_popen = _isolated.subprocess.Popen
worker_guard = sys.argv[3]
launched = []
def guarded_popen(command, **kwargs):
    assert command[:2] == [sys.executable, '-c'], command
    assert command[2] == 'from esolangs.runtime._isolated import _worker; _worker()'
    launched.append(command)
    return original_popen(command[:2] + [worker_guard + command[2]], **kwargs)
with patch.object(_isolated.subprocess, 'Popen', guarded_popen):
    assert esolangs.run(sys.argv[1], '+.') == esolangs.run(
        sys.argv[1], '+.', isolated=True)
    steps = {'limits': esolangs.ExecutionLimits(max_steps=4)}
    for isolated in (False, True):
        for source, options, error_type, expected in (
            ('+[.]', steps, esolangs.ExecutionCapError,
             esolangs.ExecutionResult('\\x01', 0, 0, 0, steps=4)),
            (',.,', {'stdin': 'é'} | steps, esolangs.InputExhaustedError,
             esolangs.ExecutionResult('é', 1, 1, 1, steps=2)),
        ):
            try:
                esolangs.run(sys.argv[1], source, isolated=isolated, **options)
            except error_type as error:
                assert error.observation == expected, (isolated, error.observation)
                assert error.partial_output == expected.output
            else:
                raise AssertionError('failure witness completed')
assert len(launched) == 3, len(launched)
assert not barrier.blocked, barrier.blocked
try:
    import esolangs.registry._certification
except ImportError as error:
    assert str(error) == 'certification is not operational'
else:
    raise AssertionError('import barrier did not fire')
try:
    importlib.import_module(f'esolangs.languages.{LANGUAGES[sys.argv[1]].id}.proof_formulas')
except ImportError as error:
    assert str(error) == 'certification is not operational'
else:
    raise AssertionError('proof import barrier did not fire')
assert len(barrier.blocked) == 2, barrier.blocked
"""
    samples = {
        name: SAMPLES[name] for name, lang in LANGUAGES.items() if lang.backend is None
    }
    subprocess.run(
        [sys.executable, "-c", code, REFERENCE, json.dumps(samples), WORKER_GUARD],
        check=True,
        timeout=10,
    )
