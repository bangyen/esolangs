"""Declared dialect defaults avoid constructor and signature discovery."""

import inspect
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from esolangs import DialectSettings, HaltError, settings, vm
from esolangs.languages.nq.interpreter import _Machine, prepare_machine
from esolangs.registry import LANGUAGES


def test_nq_metadata_stays_lazy():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from esolangs.settings import dialect_choices
module = 'esolangs.languages.nq.interpreter'
assert module not in sys.modules
choices = dialect_choices('NQ')
assert choices == {'guard_binding': {
    'default': 'opcode', 'choices': ('opcode', 'recursive')}}
assert module not in sys.modules
from esolangs.vm import make_vm
make_vm('NQ', 'H')
assert module in sys.modules, 'loading control did not fire'
""",
        ],
        check=True,
        timeout=10,
    )


def test_nq_declared_defaults_match_constructor_and_refuse_invalid_metadata():
    runtime = LANGUAGES["NQ"].runtime
    assert runtime.dialect_defaults == {
        "guard_binding": inspect.signature(_Machine).parameters["guard_binding"].default
    }
    for defaults in ({}, {"other": "opcode"}, {"guard_binding": "bogus"}):
        with pytest.raises(ValueError, match="dialect"):
            replace(runtime, dialect_defaults=defaults)


@pytest.mark.parametrize("binding", ["opcode", "recursive"])
def test_nq_declared_construction_preserves_guard_readings(monkeypatch, binding):
    def forbidden(*_args):
        raise AssertionError("signature discovery reached")

    monkeypatch.setattr(settings, "_dialect_keys", forbidden)
    monkeypatch.setattr(
        vm,
        "interpreter_module",
        lambda _name: SimpleNamespace(prepare_machine=prepare_machine),
    )
    assert settings.dialect_choices("NQ")["guard_binding"]["default"] == "opcode"
    machine = vm.make_vm(
        "NQ", "+0->1>0+2WH", settings=DialectSettings(guard_binding=binding)
    )
    if binding == "recursive":
        with pytest.raises(HaltError):
            vm.run_until_halt(machine, limit=20)
    else:
        assert vm.run_until_halt(machine, limit=20)
        assert machine.output == "#"
