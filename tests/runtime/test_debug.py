"""Tests for the breakpoint/watch debugger over the VM."""

from functools import lru_cache, wraps

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.vm import complete_vm, run_until_halt, run_until_halt_or_cycle
from tests.support.pick import one
from tests.support.reference import REFERENCE


class _PretendsToBe:
    def __init__(self, kind: type) -> None:
        self.kind = kind

    @property
    def __class__(self) -> type:
        return self.kind


class TestRun:
    def test_run_to_completion_matches_interpreter(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+++[>+++<-]>.")
        dbg.run()
        assert dbg.halted
        assert dbg.output == esolangs.run(REFERENCE, "+++[>+++<-]>.").output

        _check_overridden_step_dispatch()
        _check_replacement_during_halt_inspection()

    def test_max_steps_bounds_runaway(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+[]")
        dbg.run(limits=esolangs.ExecutionLimits(max_steps=10))
        assert not dbg.halted

    def test_step_guards_on_halt(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+")
        dbg.run()
        dbg.step()  # must not raise
        assert dbg.halted


def _check_replacement_during_halt_inspection() -> None:
    class Forwarder:
        def __init__(self, vm, *, malformed=False):
            self.vm = vm
            self.inspect = None
            self.malformed = malformed

        def __getattr__(self, name):
            return getattr(self.vm, name)

        @property
        def halted(self):
            if self.inspect is not None:
                inspect, self.inspect = self.inspect, None
                inspect()
            return 1 if self.malformed else self.vm.halted

    def wrap(nested, *, old_source="", malformed=False):
        old = debugger_api.make_vm(REFERENCE, old_source)
        new = debugger_api.make_vm(REFERENCE, "+.")
        forwarding = Forwarder(old, malformed=malformed)
        inner = debugger_api.Debugger(forwarding)
        live = debugger_api.Debugger(inner) if nested else inner
        forwarding.inspect = lambda: setattr(inner, "vm", new)
        return live, old, new

    zero = esolangs.ExecutionLimits(max_steps=0)
    two = esolangs.ExecutionLimits(max_steps=2)
    for nested in (False, True):
        live, old, new = wrap(nested)
        assert live.run(limits=zero) == "max_steps"
        assert old.halted
        assert not new.halted
        assert live.observation.steps == 0
        assert live.run(limits=two) == "halted"
        assert live.output == "\x01"
        assert live.observation.steps == 2

        live, _, new = wrap(nested)
        assert not run_until_halt(live, limit=0)
        assert new.ip == 0
        assert run_until_halt(live, limit=2)
        assert live.output == "\x01"

        live, _, _ = wrap(nested)
        with pytest.raises(esolangs.ExecutionCapError) as caught:
            complete_vm(live, max_steps=0)
        assert caught.value.observation == esolangs.ExecutionResult(
            "", 0, 0, 0, steps=0
        )
        live, _, _ = wrap(nested)
        assert complete_vm(live, max_steps=2) == "\x01"

        for malformed in (False, True):
            live, old, new = wrap(nested, old_source="-.", malformed=malformed)
            live.step()
            assert old.ip == 0
            assert new.ip == 1
            assert live.observation.steps == 1

        live, _, new = wrap(nested)
        with pytest.raises(TypeError, match="debugger VM changed during proof"):
            run_until_halt_or_cycle(live, limit=2)
        assert new.ip == 0
        assert run_until_halt_or_cycle(live, limit=2)

    forwarding = Forwarder(debugger_api.make_vm(REFERENCE, ""))
    live = debugger_api.Debugger(forwarding)
    forwarding.inspect = lambda: setattr(live, "vm", debugger_api.Debugger(forwarding))
    with pytest.raises(TypeError, match="debugger VM changed during proof"):
        run_until_halt_or_cycle(live, limit=0)
    assert run_until_halt_or_cycle(live, limit=0)


def _check_overridden_step_dispatch() -> None:
    class Rewrite(debugger_api.Debugger):
        def __init__(self, *, direct: bool) -> None:
            super().__init__(debugger_api.make_vm(REFERENCE, "+."))
            self.replacement = debugger_api.make_vm(REFERENCE, "++.")
            self.direct = direct
            self.calls = 0

        def step(self) -> None:
            if not self.calls:
                self.vm = self.replacement
            self.calls += 1
            if self.direct:
                self.vm.step()
            else:
                super().step()

    one, two = (esolangs.ExecutionLimits(max_steps=n) for n in (1, 2))
    for direct in (False, True):
        root = Rewrite(direct=direct)
        for live in (root, debugger_api.Debugger(Rewrite(direct=direct))):
            history = live.watch_cell(0)
            assert live.run(limits=one) == "max_steps"
            assert live.observation.steps == live.ip == 1
            assert live.run(limits=two) == "halted"
            assert live.observation.steps == 3
            assert live.output == "\x02"
            assert history == [1, 2, 2]

    class Fail(debugger_api.Debugger):
        def __init__(self, *, late: bool) -> None:
            super().__init__(debugger_api.make_vm(REFERENCE, "+."))
            self.late = late
            self.error = esolangs.HaltError("step override failed")

        def step(self) -> None:
            if self.late:
                super().step()
            raise self.error

    for late in (False, True):
        live = Fail(late=late)
        with pytest.raises(esolangs.HaltError, match="step override failed") as caught:
            live.run(limits=one)
        assert caught.value is live.error
        assert live.ip == live.observation.steps == int(late)
        assert caught.value.observation == live.observation

    class Direct(debugger_api.Debugger):
        def step(self) -> None:
            self.vm.step()

    live = Direct(debugger_api.make_vm(REFERENCE, ".,"))
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        live.run(limits=two)
    assert caught.value.observation == live.observation
    assert live.observation.steps == 1
    assert live.output == "\x00"

    class SwitchToFault(debugger_api.Debugger):
        def step(self) -> None:
            self.vm = replacement
            self.vm.step()

    replacement = debugger_api.make_vm(REFERENCE, ".,")
    replacement.step()
    live = SwitchToFault(debugger_api.make_vm(REFERENCE, "+."))
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        live.run(limits=one)
    assert caught.value.observation == live.observation
    assert live.observation == esolangs.ExecutionResult("\x00", 0, 0, 1, steps=0)


def test_breakpoint_predicate_is_checked_once_at_a_stop() -> None:
    dbg = debugger_api.make_debugger(REFERENCE, "+++.")
    positions = []

    def first_check(vm):
        positions.append(vm.ip)
        return len(positions) == 1

    dbg.break_when(first_check)
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "breakpoint"
    assert positions == [0]
    assert dbg.observation.steps == 0
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=4)) == "halted"

    @wraps(first_check)
    def needs_extra(vm, flag):
        return flag and first_check(vm)

    def two_args(vm, flag):
        return flag and vm.ip == 0

    @wraps(two_args)
    def takes_only_vm(vm):
        return vm.ip == 0

    @wraps(takes_only_vm)
    def forwards(*args, **kwargs):
        return takes_only_vm(*args, **kwargs)

    cached = lru_cache(takes_only_vm)
    for predicate in (takes_only_vm, forwards, cached, lru_cache(cached)):
        dbg = debugger_api.make_debugger(REFERENCE, "+.")
        with pytest.raises(esolangs.ArgumentError, match="predicate must take one"):
            dbg.break_when(needs_extra)
        dbg.break_when(predicate)
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=2)) == "breakpoint"
        assert dbg.observation.steps == 0

    class DelegatingDebugger(debugger_api.Debugger):
        def step(self) -> None:
            super().step()

    dbg = DelegatingDebugger(debugger_api.make_vm(REFERENCE, "++."))
    positions = []

    def always(vm):
        positions.append(vm.ip)
        return True

    dbg.break_when(always)
    limits = esolangs.ExecutionLimits(max_steps=3)
    assert dbg.run(limits=limits) == "breakpoint"
    assert dbg.run(limits=limits) == "halted"
    assert positions == [0, 0, 1, 2, 3]

    class ChangingStack:
        def __init__(self, first):
            self.machine = debugger_api.make_vm(REFERENCE, "+.")
            self.reads = 0
            self.first = first

        def __getattr__(self, name):
            return getattr(self.machine, name)

        @property
        def stack(self):
            self.reads += 1
            return self.first if self.reads == 1 else []

    for stack, expected, reason in (
        ([42], None, "max_steps"),
        ([42], 42, "breakpoint"),
        ([None], None, "breakpoint"),
        ([], None, "max_steps"),
    ):
        vm = ChangingStack(stack)
        dbg = debugger_api.Debugger(vm)
        dbg.break_on_stack(0, expected)
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=0)) == reason
        assert vm.reads == 1


def test_breakpoint_callback_cannot_start_a_command_after_deadline(monkeypatch) -> None:
    now = [0.0]
    monkeypatch.setattr("esolangs.runtime._controller.monotonic", lambda: now[0])

    def check_case(check_halt, hit):
        now[0] = 0.0
        dbg = debugger_api.make_debugger(REFERENCE, "+.")
        checks = []
        followed = []

        def slow(vm):
            if vm.halted == check_halt:
                checks.append(vm.ip)
                now[0] += 2.0
                return hit
            return False

        def later(vm):
            if vm.halted == check_halt:
                followed.append(vm.ip)
            return False

        dbg.break_when(slow)
        dbg.break_when(later)
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(execution_timeout=1))
            == "execution_timeout"
        )
        assert len(checks) == 1
        assert followed == []
        assert dbg.observation.steps == (2 if check_halt else 0)
        assert dbg.output == ("\x01" if check_halt else "")
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=2)) == (
            "breakpoint" if hit else "halted"
        )
        dbg.clear_breakpoints()
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=2)) == "halted"
        assert dbg.output == "\x01"

    for check_halt in (False, True):
        for hit in (False, True):
            check_case(check_halt, hit)


def test_manual_steps_rearm_a_breakpoint_after_leaving_it() -> None:
    dbg = debugger_api.make_debugger(REFERENCE, "+[+]")
    dbg.break_at(2)
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "breakpoint"
    dbg.step()
    assert dbg.ip == 3
    dbg.step()
    assert dbg.ip == 2
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "breakpoint"

    zero = esolangs.ExecutionLimits(max_steps=0)
    dbg = debugger_api.make_debugger(REFERENCE, "+.")
    dbg.break_when(lambda _vm: True)
    assert dbg.run(limits=zero) == "breakpoint"
    dbg.vm = debugger_api.make_vm(REFERENCE, "+.")
    dbg.step()
    assert dbg.ip == 1
    assert dbg.run(limits=zero) == "breakpoint"


@pytest.mark.parametrize("replace_breakpoint", [False, True])
def test_breakpoint_callback_can_clear_the_breakpoint_it_hits(
    *,
    replace_breakpoint: bool,
) -> None:
    dbg = debugger_api.make_debugger(REFERENCE, "+.")
    limits = esolangs.ExecutionLimits(max_steps=2)

    def clear(vm):
        dbg.clear_breakpoints()
        if replace_breakpoint:
            dbg.break_at(vm.ip)
        return True

    dbg.break_when(clear)
    assert dbg.run(limits=limits) == "breakpoint"
    if replace_breakpoint:
        assert dbg.run(limits=limits) == "breakpoint"
        assert dbg.ip == 0
    dbg.step()
    assert dbg.run(limits=limits) == "halted"
    assert dbg.output == "\x01"

    dbg = debugger_api.make_debugger(REFERENCE, "")
    replacement = debugger_api.make_vm(REFERENCE, "+.")
    checked = []

    def replace_at_halt(vm):
        checked.append((vm.halted, vm.output))
        if vm is not replacement:
            dbg.vm = replacement
        return False

    dbg.break_when(replace_at_halt)
    assert dbg.run(limits=limits) == "halted"
    assert checked == [(True, ""), (False, ""), (False, ""), (True, "\x01")]
    assert dbg.observation.steps == 2
    assert dbg.output == "\x01"
    _check_breakpoint_receiver_replacements()


def _check_breakpoint_receiver_replacements():
    zero = esolangs.ExecutionLimits(max_steps=0)
    one = esolangs.ExecutionLimits(max_steps=1)
    for nested in (False, True):
        receiver = debugger_api.make_debugger(REFERENCE, "+.")
        live = debugger_api.Debugger(receiver) if nested else receiver
        live.break_at(0)
        assert live.run(limits=zero) == "breakpoint"
        receiver.vm = debugger_api.make_vm(REFERENCE, "+.")
        assert live.run(limits=one) == "breakpoint"
        assert live.ip == 0
        assert live.observation.steps == 0
        assert live.run(limits=one) == "max_steps"
        assert live.ip == 1

        receiver = debugger_api.make_debugger(REFERENCE, "+.")
        live = debugger_api.Debugger(receiver) if nested else receiver
        replacement = debugger_api.make_vm(REFERENCE, "+.")
        replacement.step()
        live.break_at(0)

        def replace_without_hit(_vm, receiver=receiver, replacement=replacement):
            receiver.vm = replacement
            return False

        live.break_when(replace_without_hit)
        assert live.run(limits=one) == "halted"
        assert live.output == "\x01"
        assert live.observation.steps == 1

    for stop in (False, True):
        live = debugger_api.make_debugger(REFERENCE, "+.")
        replacement = debugger_api.make_vm(REFERENCE, "+.")

        def replace_at_zero(
            _vm, receiver=live, replacement=replacement, requested=stop
        ):
            if receiver.vm is replacement:
                return False
            receiver.vm = replacement
            return requested

        live.break_when(replace_at_zero)
        live.break_at(0)
        assert live.run(limits=zero) == "breakpoint"
        assert live.ip == 0
        assert live.run(limits=zero) == ("breakpoint" if stop else "max_steps")


def test_breakpoint_hits_do_not_survive_rewrapping() -> None:
    owner = esolangs.Language(REFERENCE).prepare("+.").make_vm()
    old, new = debugger_api.Debugger(owner), debugger_api.Debugger(owner)
    middle = debugger_api.Debugger(old)
    outer = debugger_api.Debugger(middle)

    def replace_without_hit(vm):
        vm.vm = new
        return False

    outer.break_when(lambda vm: vm.vm is old)
    outer.break_when(replace_without_hit)
    assert outer.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "max_steps"
    assert middle.vm is new
    assert outer.observation.steps == 0

    api = esolangs.Language(REFERENCE)
    halted = api.make_vm("+.")
    halted.step()
    halted.step()

    class RewrapOnInspection:
        def __getattr__(self, name):
            return getattr(halted, name)

        @property
        def halted(self):
            nested.vm = replacement
            return halted.halted

    for already_halted in (False, True):
        replacement = api.make_vm("++.")
        if already_halted:
            for _ in range(3):
                replacement.step()
        nested = debugger_api.Debugger(RewrapOnInspection())
        outer = debugger_api.Debugger(nested)
        observation = outer.observation
        assert observation.output == ("\x02" if already_halted else "")
        assert (observation.completion is not None) is already_halted
        assert observation.steps == 0


def test_manual_step_does_not_recheck_a_suppressed_breakpoint_after_rewrapping():
    owner = esolangs.Language(REFERENCE).prepare("++.").make_vm()
    old, new = debugger_api.Debugger(owner), debugger_api.Debugger(owner)
    middle = debugger_api.Debugger(old)
    outer = debugger_api.Debugger(middle)
    checks = []

    def stop(vm):
        checks.append((vm.vm, vm.ip))
        return True

    outer.break_when(stop)
    zero = esolangs.ExecutionLimits(max_steps=0)
    assert outer.run(limits=zero) == "breakpoint"
    middle.vm = new
    outer.step()
    assert checks == [(old, 0)]
    assert outer.run(limits=zero) == "breakpoint"
    assert checks == [(old, 0), (new, 1)]


def test_manual_step_can_clear_a_suppressed_breakpoint() -> None:
    dbg = debugger_api.make_debugger(REFERENCE, "+.")
    limits = esolangs.ExecutionLimits(max_steps=2)

    def replace_after_step(vm):
        if vm.ip == 1:
            dbg.clear_breakpoints()
            dbg.break_at(1)
        return True

    dbg.break_when(replace_after_step)
    assert dbg.run(limits=limits) == "breakpoint"
    dbg.step()
    assert dbg.run(limits=limits) == "breakpoint"
    assert dbg.observation.steps == 1
    assert dbg.run(limits=limits) == "halted"


def test_debugger_breakpoint_and_watch_counts_use_integer_storage() -> None:
    class Index(int):
        def __hash__(self):
            raise AssertionError("subclass hashing must not affect a watch")

        def __eq__(self, _other):
            raise AssertionError("subclass equality must not affect a breakpoint")

    class Position(tuple):
        def __iter__(self):
            raise AssertionError("breakpoint iterated the position wrapper")

    dbg = debugger_api.make_debugger(REFERENCE, "+.")
    for bad in (_PretendsToBe(int), _PretendsToBe(tuple), (_PretendsToBe(int),)):
        with pytest.raises(esolangs.ArgumentError, match="ip must be an integer"):
            dbg.break_at(bad)
    with pytest.raises(esolangs.ArgumentError, match="this language's ip is an index"):
        dbg.break_at(Position((Index(0),)))
    with pytest.raises(esolangs.ArgumentError, match="value must be an integer"):
        dbg.break_on_cell(0, _PretendsToBe(int))
    watch = dbg.watch_cell(Index(0))
    dbg.break_at(Index(0))
    dbg.break_on_cell(Index(0), Index(1))
    limits = esolangs.ExecutionLimits(max_steps=2)
    assert dbg.run(limits=limits) == "breakpoint"
    assert dbg.observation.steps == 0
    assert dbg.run(limits=limits) == "breakpoint"
    assert dbg.observation.steps == 1
    assert watch == [1]
    assert dbg.run(limits=limits) == "halted"
    assert dbg.output == "\x01"


def test_output_breakpoints_use_the_string_contents() -> None:
    class Text(str):
        def __bool__(self):
            return not str.__len__(self)

        def __str__(self):
            raise AssertionError("subclass rendering must not affect a breakpoint")

    dbg = debugger_api.make_debugger(REFERENCE, ",.", stdin="A")
    with pytest.raises(esolangs.ArgumentError, match="text must be a string"):
        dbg.break_on_output(_PretendsToBe(str))
    with pytest.raises(esolangs.ArgumentError, match="non-empty string"):
        dbg.break_on_output(Text(""))
    dbg.break_on_output(Text("A"))
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=2)) == "breakpoint"
    assert dbg.observation.steps == 2
    assert dbg.output == "A"


#: Two of the nine dump-on-post-halt languages, one reader and one template:
#: the dump step is the debugger's shared code, and test_vm_protocol already
#: checks every language's flag against its behaviour.
_DUMPERS = [
    name
    for template in (False, True)
    for name in one(dumps_on_the_post_halt_step=True, parameterized=template)
]


def _runnable(name: str, table: str = "0110") -> tuple[esolangs.ProgramArtifact, str]:
    """Return a filled program and the stdin to drive it with."""
    program = esolangs.generate(name, table)
    if esolangs.describe(name).parameterized:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0])


class TestABreakpointAtTheHaltIsReported:
    """``run`` reported ``"halted"`` over a watch that had fired."""

    def test_an_output_watch_on_the_last_step_fires(self) -> None:
        """The case it was reported for, on the flagship language."""
        dbg = debugger_api.make_debugger(
            REFERENCE, esolangs.generate(REFERENCE, "0110"), stdin="10"
        )
        dbg.break_on_output("1")
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=100_000)) == "breakpoint"
        )
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=100_000)) == "halted"
        assert dbg.halted

    @pytest.mark.parametrize("name", _DUMPERS)
    def test_the_answer_is_never_stranded_by_that_stop(self, name: str) -> None:
        """A stop before the dump must not cost the caller the answer."""
        assert esolangs.describe(name).dumps_on_the_post_halt_step
        program, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, program, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted and vm.output == "")
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000)) == "breakpoint"
        )
        assert dbg.output == ""
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000)) == "halted"
        assert (
            dbg.output
            == esolangs.run(
                name,
                program,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=30),
            ).output
        )

    @pytest.mark.parametrize("name", _DUMPERS)
    def test_the_dump_step_is_taken_once_not_once_per_run(self, name: str) -> None:
        """Three idle runs grew a watch history by three."""
        program, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, program, stdin=stdin)
        history = dbg.watch_cell(0)
        dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000))
        after_one = len(history)
        for _ in range(4):
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000))
        assert len(history) == after_one

    def test_an_expired_deadline_leaves_the_pending_dump_unfinished(
        self, monkeypatch
    ) -> None:
        name = _DUMPERS[0]
        source, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, source, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted)
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(max_steps=300_000)) == "breakpoint"
        )
        assert dbg.halted
        assert dbg.observation.completion is None
        dbg.clear_breakpoints()
        times = iter((0.0, 1.0))
        monkeypatch.setattr(
            "esolangs.runtime._controller.monotonic", lambda: next(times)
        )
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(execution_timeout=0.5))
            == "execution_timeout"
        )
        assert dbg.observation.completion is None
        now = [0.0]
        monkeypatch.setattr("esolangs.runtime._controller.monotonic", lambda: now[0])
        dump = dbg.step

        def slow_dump():
            dump()
            now[0] += 1.0

        monkeypatch.setattr(dbg, "step", slow_dump)
        assert (
            dbg.run(limits=esolangs.ExecutionLimits(execution_timeout=0.5))
            == "execution_timeout"
        )
        assert dbg.observation.completion is not None
        assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
        assert dbg.observation.completion is not None


class TestPointerFallback:
    """A tape machine that names no state still shows where it points."""

    def test_the_debugger_mirrors_the_pointer(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, ">>,", stdin="")
        assert dbg.ptr == 0
        dbg.step()
        assert dbg.ptr == 1


def test_nested_watch_uses_wrapper_indexed_view():
    class Sparse(debugger_api.Debugger):
        @property
        def memory(self):
            raise AssertionError("materialized sparse memory")

        def read_cell(self, index):
            return 42 if index == 10**9 else None

    sparse = Sparse(debugger_api.make_vm(REFERENCE, "+"))
    outer = debugger_api.Debugger(debugger_api.Debugger(sparse))
    history = outer.watch_cell(10**9)
    outer.step()
    assert history == [42]
    assert outer.read_cell(10**9 + 1) is None
