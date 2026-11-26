"""Observe outcomes through a raising adapter with caller-supplied test IO."""

import signal
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

from esolangs import Catalog, ExecutionLimits, Language
from esolangs.exceptions import ArgumentError, ExecutionTimeoutError
from esolangs.operations.execution import _execute_invocation
from esolangs.results import ExecutionResult
from esolangs.runtime._proof import TerminationResult
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._termination import _termination_result
from esolangs.runtime.io import ScriptedIO

#: The shortest bound the ``SIGALRM`` guard can service.  Measured: below
#: about a millisecond the alarm lands inside the guard's own teardown -- 19
#: of 20 processes hammering a 100-microsecond bound were killed outright,
#: none at a millisecond or above (4000 runs each).
TIMEOUT_FLOOR = 0.001


def run_under_alarm[T](
    run_fn: Callable[..., T],
    program: object,
    io_obj: ScriptedIO,
    timeout: float,
) -> T:
    """Return the call's result under a ``SIGALRM`` guard (main thread only)."""
    if timeout < TIMEOUT_FLOOR:
        raise ArgumentError(
            f"timeout must be at least {TIMEOUT_FLOOR} seconds, got {timeout!r}"
        )
    # The handler fires between any two bytecodes, including the cleanup's;
    # raising into its own teardown left the timer armed and the default
    # SIGALRM disposition killed one run in three.  Clearing this is one store.
    armed = True
    old = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    pending, interval = signal.getitimer(signal.ITIMER_REAL)
    caller_deadline = started + pending if pending else None
    deadline = started + timeout

    def _timeout_handler(_signum: int, _frame: object) -> None:
        nonlocal caller_deadline
        # coverage cannot trace a raise inside a signal handler
        if not armed:  # pragma: no cover - a late alarm, not an overrun
            return
        now = time.monotonic()
        if caller_deadline is not None and now >= caller_deadline:
            caller_deadline = (
                caller_deadline
                + (int((now - caller_deadline) // interval) + 1) * interval
                if interval
                else None
            )
            if callable(old):
                old(_signum, cast("Any", _frame))
            elif old == signal.SIG_DFL:
                signal.signal(signal.SIGALRM, old)
                signal.raise_signal(signal.SIGALRM)
            now = time.monotonic()
            if now < deadline:
                next_deadline = (
                    min(deadline, caller_deadline)
                    if caller_deadline is not None
                    else deadline
                )
                signal.setitimer(
                    signal.ITIMER_REAL, max(0.000001, next_deadline - time.monotonic())
                )
                return
        raise ExecutionTimeoutError(
            f"execution exceeded the {timeout}-second timeout"
        )  # pragma: no cover

    # Dispatch the earlier deadline: replacing a caller's timer let a nested
    # 0.05-second guard return successfully after 0.159 seconds.
    signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        # Armed inside the ``try``: a 1 ms alarm can fire before it is entered.
        signal.setitimer(
            signal.ITIMER_REAL, min(timeout, pending) if pending else timeout
        )
        return run_fn(program, io_obj)
    finally:
        armed = False
        # Ignore first, then disarm, then restore: an alarm in flight after
        # ``old`` (the default disposition) is restored terminates the
        # process -- exit 142, one run in ten.  ``SIG_IGN`` is C-level.
        # An alarm between ``run_fn`` returning and here still raises a
        # timeout; closing that needs a flag read from a handler, not worth it.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        if caller_deadline is not None:
            signal.setitimer(
                signal.ITIMER_REAL,
                max(0.000001, caller_deadline - time.monotonic()),
                interval,
            )


def run_guard[T](
    run_fn: Callable[..., T],
    program: object,
    io_obj: ScriptedIO,
    timeout: float | None,
) -> T:
    """Return ``run_fn``'s result, applying the wall-clock guard when set."""
    if timeout is None:
        return run_fn(program, io_obj)
    return run_under_alarm(run_fn, program, io_obj, timeout)


def run_observed(
    language: str, program: ProgramSource, **options: Any
) -> ExecutionResult:
    timeout = options.pop("timeout", None)
    if options.get("isolated"):
        return _execute_invocation(
            language, program, timeout=timeout, **options
        ).unwrap()
    return run_guard(
        lambda *_args: _execute_invocation(language, program, **options).unwrap(),
        "",
        ScriptedIO(""),
        timeout,
    )


def termination_observed(
    name: str, program: Any, stdin: str, timeout: float | None, **options: Any
) -> TerminationResult:
    """Return an in-process termination proof, alarm-guarded when timed."""
    return run_guard(
        lambda *_args: _termination_result(name, program, stdin, **options),
        "",
        ScriptedIO(""),
        timeout,
    )


def assert_branch_proof_replays(
    name: str, source: str, output: str, *, halts: bool = True
) -> None:
    """Replay the exact named states retained by a real worker."""
    from esolangs.runtime._isolated import termination_result_isolated
    from esolangs.runtime._vm_adapter import _DelegatingVM
    from esolangs.runtime._vm_protocol import _BranchingStepMachine
    from esolangs.vm import make_vm
    from tests.support.certification_barrier import guarded_worker

    local = termination_observed(name, source, "", 5)
    assert local.decision.halts is halts
    assert local.observation.output == output
    with guarded_worker():
        worker = termination_result_isolated(name, source, "", 5)
    assert worker == local
    local_proof = local.decision.branches
    proof = worker.decision.branches
    assert local_proof is not None
    assert proof is not None
    state_type = type(local_proof.root)
    assert hasattr(state_type, "_fields")
    assert type(proof.root) is state_type
    vm = make_vm(name, source)
    assert isinstance(vm, _DelegatingVM)
    model = vm._machine
    assert isinstance(model, _BranchingStepMachine)
    assert proof.root == model.branching_snapshot()
    assert proof.transitions
    for state, successors in proof.transitions:
        assert type(state) is state_type
        assert all(type(target) is state_type for target in successors)
        assert not model.branching_halted(state)
        assert model.branching_successors(state, 10_000) == successors
    if halts:
        assert type(proof.terminal) is state_type
        assert model.branching_halted(proof.terminal)
    else:
        assert proof.terminal is None


def assert_cycle_proof_replays(
    name: str, halting: str, cycling: str, output: str
) -> None:
    """Compare public cycle results and replay the worker's named state."""
    from tests.support.certification_barrier import guarded_worker

    api = Language(name)
    record = api.catalog.languages[api.name]
    contract = replace(
        record.contract, answer_mode="termination", answer_values=("halts", "diverges")
    )
    scoped = Catalog([replace(record, contract=contract)]).bind(api.name)
    local = ExecutionLimits(max_steps=50)
    isolated = replace(local, total_timeout=5)
    bits = [1]
    with guarded_worker(expected=2):
        for source, answer in ((halting, "0"), (cycling, "1")):
            artifact = scoped.from_source(source)
            observed = scoped.evaluate(artifact, bits, limits=local)
            worker = scoped.evaluate(artifact, bits, limits=isolated)
            assert worker == observed
            assert worker.answer == answer
            assert worker.observation.output == output
            assert worker.termination is not None
            cycle = worker.termination.cycle
            if answer == "0":
                assert cycle is None
                continue
            assert cycle is not None
            assert worker.termination.commands == cycle.repeat_pass
            machine = scoped.make_debugger(artifact, stdin=scoped.encode_inputs(bits))
            for _ in range(cycle.first_pass):
                machine.step()
            entry = machine.snapshot()
            assert isinstance(entry, tuple)
            assert isinstance(cycle.state, tuple)
            assert cycle.state == entry
            state_type = type(entry[0])
            assert hasattr(state_type, "_fields")
            assert type(cycle.state[0]) is state_type
            for _ in range(cycle.repeat_pass - cycle.first_pass):
                machine.step()
            assert machine.snapshot() == entry
            assert machine.output == output


def assert_digit_cap_independent(
    name: str, source: ProgramSource, stdin: str, output: str
) -> None:
    """Run a wide decimal witness locally and in an isolated worker."""
    api = Language(name)
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        native = api.run(source, stdin=stdin)
        assert native.output == output
        assert api.run(source, stdin=stdin, isolated=True) == native
    finally:
        sys.set_int_max_str_digits(previous)
