"""Logical workspace survives backing-store and cycle-snapshot regrouping."""

from types import SimpleNamespace

import pytest

from esolangs import run
from esolangs import vm as vm_api
from esolangs.exceptions import EsolangError
from esolangs.languages.whitespace.interpreter import (
    _WORKSPACE_MODEL,
    _Machine,
    prepare_machine,
)
from esolangs.languages.whitespace.tests.oracle_checks import _assemble, _check
from esolangs.results import Completion
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, make_vm
from scripts.benchmark import WrittenState


class _RepackedMachine(_Machine):
    @property
    def state(self):
        data = self._packed
        return (
            data["control"][0],
            tuple(data["stack"][: data["used"]]),
            tuple(sorted(data["heap"].items())),
            tuple(data["control"][2]),
            data["control"][1],
        )

    @state.setter
    def state(self, state):
        pc, stack, heap, calls, ended = state
        self._packed = {
            "control": (pc, ended, list(calls)),
            "stack": [*stack, *([0] * 8)],
            "used": len(stack),
            "heap": dict(heap),
            "cache": "not logical state",
        }

    def snapshot(self):
        pc, stack, heap, calls, ended = self.state
        return ((pc, ended), (stack, heap, calls), self.io.progress())


@pytest.mark.parametrize(
    ("program", "stdin"),
    [
        ((("push", 7),), ""),
        (
            (
                ("push", -17),
                ("push", 65),
                ("store",),
                ("push", -17),
                ("retrieve",),
                ("out_char",),
                ("end",),
            ),
            "",
        ),
        (
            (
                ("push", 0),
                ("read_num",),
                ("push", 0),
                ("retrieve",),
                ("out_num",),
                ("push", 1),
                ("read_char",),
                ("push", 1),
                ("retrieve",),
                ("out_char",),
                ("end",),
            ),
            "12\né",
        ),
        (
            (
                ("call", "0"),
                ("push", 9),
                ("out_num",),
                ("end",),
                ("mark", "0"),
                ("push", 65),
                ("out_char",),
                ("return",),
            ),
            "",
        ),
        ((("push", 0), ("read_char",)), ""),
        ((("push", 0), ("read_num",)), "\n7\n"),
    ],
)
def test_repacked_storage_retains_semantic_workspace(monkeypatch, program, stdin):
    _check(_RepackedMachine, program, stdin)
    source, _ = _assemble(program)
    vm = make_vm("Whitespace", source, stdin=stdin)
    assert _capture_workspace(vm).model is _WORKSPACE_MODEL
    machines = [
        _Machine(source, ScriptedIO(stdin)),
        _RepackedMachine(source, ScriptedIO(stdin)),
    ]
    semantic = [WrittenState(m.workspace_snapshot()) for m in machines]
    legacy = WrittenState(machines[0].snapshot())
    regrouped = WrittenState(machines[1].snapshot())
    errors = []
    for _ in range(48):
        captures = [m.workspace_snapshot() for m in machines]
        assert captures[0] == captures[1]
        for machine, capture, written in zip(machines, captures, semantic, strict=True):
            assert capture.parts == (*machine.state, machine.io.progress())
            written.sample(capture)
        legacy.sample(machines[0].snapshot())
        regrouped.sample(machines[1].snapshot())
        assert semantic[0].bits == semantic[1].bits == legacy.bits
        assert machines[0].io.getvalue() == machines[1].io.getvalue()
        if errors:
            assert len(errors) == 2
            assert errors[0] is errors[1]
        if machines[0].halted or errors:
            break
        for machine in machines:
            try:
                machine.step()
            except (EsolangError, EOFError) as error:
                errors.append(type(error))
    else:
        raise AssertionError("workspace witness exceeded its step budget")
    if program == (("push", 7),):
        assert semantic[0].bits == 4
        assert regrouped.bits == 5
        monkeypatch.setattr(_Machine, "completion", Completion.POST_HALT, raising=False)
        monkeypatch.setattr(_Machine, "ip_shape", "opaque")
        monkeypatch.setattr(_Machine, "memory", [999], raising=False)
        monkeypatch.setattr(
            _Machine, "surprise", property(lambda _self: 99), raising=False
        )
        monkeypatch.setattr(
            vm_api,
            "interpreter_module",
            lambda _name: SimpleNamespace(prepare_machine=prepare_machine),
        )
        declared = make_vm("Whitespace", source)
        assert declared.ip_shape == "offset"
        assert not declared.dumps_on_the_post_halt_step
        declared.step()
        assert declared.halted
        assert declared.ip is None
        assert declared.stack == [7]
        assert declared.memory == []
        assert declared.views == ()
        assert run("Whitespace", source).completion.kind is Completion.HALTED
