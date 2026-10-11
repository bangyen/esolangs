"""FALSE through the shared API, CLI and machinery."""

import contextlib

import pytest

import esolangs.debugger as debugger_api
from tests.reference import REFERENCE
from tests.support.duration_policy import limits
from tests.support.samples import SAMPLES


@pytest.mark.parametrize("value", ["", "0", "false"])
def test_an_unset_or_falsey_ci_keeps_the_local_ceiling(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CI", value)
    assert limits() == (1.0, 5.0)


def test_memory_and_stack_are_copies_not_the_live_store() -> None:
    """A caller must not be able to write into a running machine.

    ``_DelegatingVM`` makes the copy once for every interpreter, so a tape
    language and FALSE (non-empty memory and stack) cover it.
    """
    for name in (REFERENCE, "FALSE"):
        program, stdin = SAMPLES[name]
        vm = debugger_api.make_vm(name, program, stdin=stdin)
        with contextlib.suppress(Exception):
            vm.step()
        before_mem, before_stk = list(vm.memory), list(vm.stack)
        vm.memory.append(12345)
        vm.stack.append("scribble")
        assert list(vm.memory) == before_mem, f"{name}: memory is live"
        assert list(vm.stack) == before_stk, f"{name}: stack is live"
