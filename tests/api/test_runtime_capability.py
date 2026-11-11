"""Runtime declarations have one owner and no compiler dependencies."""

import ast
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec


def test_runtime_facts_are_owned_only_by_the_runtime_record():
    from esolangs.runtime._definition import (
        CompressedSourcePolicy,
        LineSourcePolicy,
        RasterSourcePolicy,
        TextSourcePolicy,
        VerbatimSourcePolicy,
    )

    policies = (
        TextSourcePolicy(),
        LineSourcePolicy(),
        VerbatimSourcePolicy(),
        CompressedSourcePolicy(),
        RasterSourcePolicy(),
    )
    for policy in policies:
        with pytest.raises((FrozenInstanceError, TypeError)):
            policy.split = not policy.split
        with pytest.raises(TypeError):
            type(policy)(source_kind="raster")
    assert LineSourcePolicy().split
    assert not VerbatimSourcePolicy().file_newline
    assert CompressedSourcePolicy().compressed
    assert RasterSourcePolicy().kind == RasterSourcePolicy().loader == "raster"
    with pytest.raises(TypeError):
        TextSourcePolicy(path_like=True)
    runtime_fields = {field.name for field in fields(RuntimeSpec)}
    assert runtime_fields.isdisjoint(
        {
            "split",
            "path_like_source",
            "source_kind",
            "compressed_source",
            "source_loader",
            "file_newline",
        }
    )
    assert runtime_fields.isdisjoint(field.name for field in fields(Language))
    for lang in LANGUAGES.values():
        assert isinstance(lang.runtime, RuntimeSpec)
        assert lang.runtime.interpreter is not None


@pytest.mark.medium
def test_backend_and_example_changes_preserve_the_runtime_definition():
    _check_runtime_catalog_without_synthesis()
    for lang in LANGUAGES.values():
        changed = replace(lang, backend=None, example=Example())
        assert changed.runtime is lang.runtime
        assert changed.source_suffix == lang.source_suffix


@pytest.mark.medium
@pytest.mark.parametrize(
    ("relative", "class_name"),
    [
        ("runtime/_definition.py", "RuntimeSpec"),
        ("runtime/_context.py", "ExecutionContext"),
        ("registry/_certification.py", "CertificationSpec"),
    ],
)
def test_capability_schema_loads_with_all_package_imports_blocked(relative, class_name):
    path = Path(esolangs.__file__).parent / relative
    code = """
import importlib
import importlib.abc
import runpy
import sys
from dataclasses import is_dataclass, fields, FrozenInstanceError

class Barrier(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'esolangs' or fullname.startswith('esolangs.'):
            raise ImportError('blocked package import')

sys.meta_path.insert(0, Barrier())
schema = runpy.run_path(sys.argv[1])
options = {}
if sys.argv[2] == 'RuntimeSpec':
    options = dict(machine_preparation='prepare_machine',
                   completion_entrypoint='_execute', capabilities=object())
record = schema[sys.argv[2]](**options)
assert is_dataclass(record)
field = fields(record)[0]
try:
    setattr(record, field.name, getattr(record, field.name))
except FrozenInstanceError:
    pass
else:
    raise AssertionError('schema record is mutable')
try:
    importlib.import_module('esolangs')
except ImportError as error:
    assert str(error) == 'blocked package import'
else:
    raise AssertionError('import barrier did not fire')
"""
    subprocess.run(
        [sys.executable, "-c", code, str(path), class_name], check=True, timeout=10
    )


# This runs within the existing runtime declaration contract, rather than
# adding another near-identical import smoke test.
def _check_runtime_catalog_without_synthesis():
    root = Path(esolangs.__file__).parent / "runtime"
    forbidden = ("esolangs.generation", "esolangs.registry._backend")
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            imports = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            assert not any(name.startswith(forbidden) for name in imports), path
    barrier = """
import importlib.abc
import sys

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith('esolangs.generation')
                or fullname == 'esolangs.registry._backend'):
            raise ImportError('runtime imported synthesis')
sys.meta_path.insert(0, Block())
"""
    code = r"""
import importlib
import sys
from dataclasses import replace
from pathlib import Path
import subprocess

import esolangs
from esolangs.languages.deadfish.descriptor import LANGUAGE
from esolangs.raster import Raster
from esolangs.runtime._isolated import termination_result_isolated
from esolangs.runtime._termination import _termination_result
from esolangs.vm import complete_vm

installed = esolangs.Language(LANGUAGE.name)
assert installed.run('$io').output == '1\n'
assert installed.read_answer('1\n') == '1'
assert installed.prepare('$io').run(isolated=True).output == '1\n'
path = Path(sys.argv[1]) / 'program.txt'
path.write_text('$io')
for options in ([], ['--isolated'], ['--max-steps', '20']):
    cli = subprocess.run(
        [sys.executable, '-m', 'esolangs', 'run', *options, LANGUAGE.name, str(path)],
        input='', capture_output=True, text=True, check=True, timeout=5,
    )
    assert cli.stdout == '1\n' and cli.stderr == ''
cli = subprocess.run(
    [sys.executable, '-m', 'esolangs', 'read-answer', LANGUAGE.name],
    input='1\n', capture_output=True, text=True, check=True, timeout=5,
)
assert cli.stdout == '1\n' and cli.stderr == ''

for steps in (None, 20):
    scoped = esolangs.Catalog([LANGUAGE]).bind(LANGUAGE.name)
    limits = esolangs.ExecutionLimits(max_steps=steps)
    assert scoped.execute('$io', isolated=True, limits=limits).unwrap().output == '1\n'

contract = replace(LANGUAGE.contract, note='local')
record = replace(LANGUAGE, backend=None, contract=contract)
catalog = esolangs.Catalog([record])
assert _termination_result(record.name, '$io', '', 5, catalog=catalog) == (
    termination_result_isolated(record.name, '$io', '', 5, catalog=catalog)
)

piet = esolangs.Language('Piet')
loop = Raster((((255, 192, 192), (255, 0, 0)),))
black = Raster((((0, 0, 0), (255, 0, 0)),))
prepared = piet.prepare(loop)
limits = esolangs.ExecutionLimits(max_steps=20)
for isolated in (False, True):
    assert piet.prepare(black).run(isolated=isolated).output == ''
    outcome = prepared.execute(isolated=isolated, limits=limits)
    assert outcome.status == 'limit' and outcome.observation.steps == 20

for name, source, halts in (('Piet', loop, False), (LANGUAGE.name, '$io', True)):
    local = _termination_result(name, source, '', 5)
    worker = termination_result_isolated(name, source, '', 5)
    assert local == worker
    assert worker.decision.halts is halts and worker.decision.commands > 0
    if not halts:
        assert worker.decision.cycle is not None

class BackendTrap:
    @property
    def template(self):
        raise AssertionError('runtime inspected a Boolean backend')

class Unread:
    def read(self):
        raise AssertionError('template rejection consumed input')

for backend in (None, BackendTrap()):
    record = replace(LANGUAGE, backend=backend)
    api = esolangs.Catalog([record]).bind(record.name)
    assert api.prepare('$io').run().output == '1\n'
    for options in ({}, {'limits': esolangs.ExecutionLimits(max_steps=20)}):
        assert api.execute('$io', **options).unwrap().output == '1\n'
    assert complete_vm(api.prepare('$io').make_vm()) == '1\n'
    template = esolangs.TemplateArtifact('$', record.name,
        esolangs.TemplateBindings(setters=(('i', 's'),)))
    outcome = api.execute(template, stdin=Unread())
    assert outcome.status == 'rejected'
    assert isinstance(outcome.error, esolangs.TemplateError)
    assert outcome.observation.input_reads is None
    try:
        api.prepare(template)
    except esolangs.TemplateError:
        pass
    else:
        raise AssertionError('an explicit template ran without filling')
assert not any(name.startswith('esolangs.generation') for name in sys.modules)
try:
    importlib.import_module('esolangs.generation')
except ImportError:
    pass
else:
    raise AssertionError('import barrier did not fire')
try:
    BackendTrap().template
except AssertionError:
    pass
else:
    raise AssertionError('backend trap did not fire')
"""
    with TemporaryDirectory() as temporary:
        # The worker starts a fresh interpreter and installs the same barrier.
        (Path(temporary) / "sitecustomize.py").write_text(barrier)
        pythonpath = os.pathsep.join(
            filter(None, (temporary, os.environ.get("PYTHONPATH")))
        )
        result = subprocess.run(
            [sys.executable, "-c", code, temporary],
            env={**os.environ, "PYTHONPATH": pythonpath},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr
