"""Execution accounting, cooperative bounds and finalization below debugging."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from inspect import getattr_static
from time import monotonic
from typing import Literal

from esolangs.exceptions import ArgumentError, EsolangError, steps_exhausted
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome, _failed_outcome
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime._drive import _checked_halted
from esolangs.runtime._validate import _argument_repr, _has_backing_type
from esolangs.runtime._vm_protocol import VM
from esolangs.vm import (
    _capture_observation,
    _capture_result,
    _controller_vm,
    _DelegatingVM,
    _halt_faulted,
    _post_halt_dumped,
    _raise_halt_fault,
    _record_vm_fault,
)

StopReason = Literal["halted", "breakpoint", "max_steps", "execution_timeout"]
type _StopRequest = (
    Literal["active", "halted", "breakpoint", "replaced", "execution_timeout"] | None
)

_DRIVER_FIELDS = (
    "halted",
    "output",
    "steppable_to_answer",
    "dumps_on_the_post_halt_step",
)
_MISSING = object()


def _expired(deadline: float | None) -> bool:
    return deadline is not None and monotonic() >= deadline


@dataclass(slots=True)
class _StepDispatch:
    """Track which boundary accounted for a run's overridden step."""

    delegated: bool = False
    completed: tuple[VM, bool] | None = None


class ExecutionController:
    """Drive a VM with shared bounds, completion and execution observations."""

    def __init__(self, vm: VM) -> None:
        if isinstance(vm, type) or not callable(getattr(vm, "step", None)):
            raise ArgumentError(f"vm must be a VM, got {_argument_repr(vm)}")
        if not isinstance(vm, _DelegatingVM):
            for name in _DRIVER_FIELDS:
                # Leave properties unevaluated, but accept a forwarding proxy.
                if getattr_static(vm, name, _MISSING) is _MISSING and not hasattr(
                    vm, name
                ):
                    raise ArgumentError(f"vm must be a VM with a {name} attribute")
        self.vm = vm
        self._dumped: VM | None = None
        self._steps = 0
        self._step_dispatch: _StepDispatch | None = None
        self._faulted_owner: VM | None = None
        self._active_fault: tuple[VM, EsolangError] | None = None
        self._observer_fault: tuple[EsolangError, bool] | None = None

    def _record(self) -> None:
        """Observe a completed step; debugger subclasses record watches."""

    def _stop_requested(self, deadline: float | None) -> _StopRequest:
        """Check the budget before accepting a stop or taking another step."""
        return "execution_timeout" if _expired(deadline) else None

    @property
    def halted(self) -> bool:
        """Whether the wrapped VM has finished executing."""
        wrapped = self.vm
        try:
            return _checked_halted(wrapped.halted)
        except EsolangError as error:
            self._observe_inspection_fault(wrapped, error)
            raise

    @property
    def output(self) -> str:
        """Everything the wrapped VM has written so far."""
        return self.vm.output

    @property
    def observation(self) -> ExecutionResult:
        """Current output and input usage, with completion only after finalization.

        Steps count successful calls through this controller while active;
        completion dump calls are excluded. Caller-owned IO counters stay None.
        """
        while True:
            receiver = self.vm
            tail = _receiver_tail(receiver)
            report = None
            if self.halted and self.steppable_to_answer and not _halt_faulted(self):
                faulted = self._faulted_owner is not None and (
                    _controller_vm(self.vm) is self._faulted_owner
                )
                if self.dumps_on_the_post_halt_step:
                    if self._has_dumped() and not faulted:
                        report = CompletionReport(Completion.POST_HALT)
                elif not faulted:
                    report = CompletionReport(Completion.HALTED)
            # An inspection callback can replace any link in the chain.
            if not _receiver_matches(self, receiver, tail):
                continue
            observation = _capture_observation(receiver, report)
            if _receiver_matches(self, receiver, tail):
                return replace(observation, steps=self._steps)

    @property
    def self_halts(self) -> bool:
        """Whether a program in this language can reach a halt of its own.

        See :attr:`~esolangs.debugger.VM.self_halts`; copies drifted once.
        """
        return self.vm.self_halts

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output lands on the step *after* ``halted`` goes true.

        A :meth:`run` returning ``"halted"`` has taken it; one returning
        ``"breakpoint"`` may not have, so where this is true the stop reason, not
        ``halted``, says whether the answer is written.
        """
        return self.vm.dumps_on_the_post_halt_step

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        See :attr:`~esolangs.debugger.VM.steppable_to_answer`.
        """
        return self.vm.steppable_to_answer

    @property
    def eof_is_a_value(self) -> bool:
        """Whether a read past the end of the input yields a value here.

        See :attr:`~esolangs.debugger.VM.eof_is_a_value`.
        """
        return self.vm.eof_is_a_value

    def step(self) -> None:
        """Execute one command, recording any watches.

        Delegates past the halt: the post-halt-dump languages keep their answer
        there, and returning early cost a debugger-driven verifier 58/65.
        A fault raises with ``partial_output`` set, as :func:`esolangs.run`'s does.
        """
        dispatch = self._step_dispatch
        if dispatch is not None:
            dispatch.delegated = True
            dispatch.completed = None
        self._take_step()

    def _run_stepper(self) -> Callable[[], None]:
        """Select the step driver for this run."""
        return self._take_step

    def _run_overridden_step(self) -> None:
        """Account for overrides that may drive the VM directly."""
        previous = self._step_dispatch
        self._step_dispatch = _StepDispatch()
        try:
            self._take_step(self.step)
        finally:
            self._step_dispatch = previous

    def _observe_fault(self, vm: VM, error: EsolangError) -> None:
        observation = replace(_capture_observation(vm), steps=self._steps)
        _record_vm_fault(vm, error, observation)

    def _observe_inspection_fault(self, vm: VM, error: EsolangError) -> None:
        owner = _controller_vm(vm)
        if isinstance(owner, _DelegatingVM):
            self._observe_fault(owner, error)
        elif error.observation is None and not error.partial_output:
            try:
                self._observe_fault(owner, error)
            except Exception:
                # Reading caller-owned output cannot replace the original fault.
                return

    def _take_step(self, override: Callable[[], None] | None = None) -> None:
        """Drive a command or finalization step, accounting for its effects."""
        dispatch = self._step_dispatch
        self._observer_fault = None
        wrapped = self.vm
        try:
            active = not _checked_halted(wrapped.halted)
        except EsolangError as error:
            self._observe_inspection_fault(wrapped, error)
            raise
        controller = wrapped if isinstance(wrapped, ExecutionController) else None
        owner = _controller_vm(controller) if controller is not None else wrapped
        if controller is not None:
            controller._observer_fault = None  # noqa: SLF001
        observer_fault = None
        try:
            if override is None:
                wrapped.step()
            else:
                override()
        except EsolangError as exc:
            if override is not None:
                assert dispatch is not None
                if dispatch.delegated:
                    if dispatch.completed is not None:
                        owner, active = dispatch.completed
                        self._observer_fault = (exc, active)
                        self._observe_inspection_fault(owner, exc)
                    raise
                current = self.vm
                if (
                    isinstance(current, _DelegatingVM)
                    and exc.observation is not None
                    and exc.observation is current._fault_observation  # noqa: SLF001
                ):
                    owner = current
            nested_fault = (
                controller._observer_fault  # noqa: SLF001 - same controller protocol
                if controller is not None
                else None
            )
            if nested_fault is not None and nested_fault[0] is exc:
                # This controller also saw the command complete.
                observer_fault = exc
            else:
                self._faulted_owner = (
                    None if isinstance(owner, _DelegatingVM) else owner
                )
                if active and self._faulted_owner is not None:
                    self._active_fault = (owner, exc)
                self._observe_fault(owner, exc)
                raise
        if override is not None and dispatch is not None and dispatch.delegated:
            return
        if active:
            self._faulted_owner = None
            self._active_fault = None
            if self._dumped is owner:
                self._dumped = None
            self._steps += 1
        elif owner.dumps_on_the_post_halt_step:
            self._faulted_owner = None
            if not isinstance(owner, _DelegatingVM):
                self._dumped = owner
        try:
            if observer_fault is not None:
                raise observer_fault
            self._record()
        except EsolangError as error:
            self._observer_fault = (error, active)
            self._observe_inspection_fault(owner, error)
            raise
        if dispatch is not None:
            dispatch.completed = (owner, active)

    def _has_dumped(self) -> bool:
        """Read registered finalization or a dump observed for the current raw VM."""
        wrapped = self.vm
        owner = _controller_vm(wrapped)
        if isinstance(owner, _DelegatingVM):
            return _post_halt_dumped(owner)
        if self._faulted_owner is owner:
            return False
        return self._dumped is owner or _post_halt_dumped(wrapped)

    def run(self, *, limits: ExecutionLimits | None = None) -> StopReason:
        """Execute until the machine halts, a breakpoint fires, or a bound ends it.

        Returns why: ``"halted"``, ``"breakpoint"``, ``"max_steps"`` or
        ``"execution_timeout"``, the last two naming the ``limits`` field that
        ended it.  A breakpoint that stopped the last run is suppressed
        until its condition goes false.  It is checked again after the halt, and
        on the post-halt-dump languages before *and* after the dump, so
        ``"breakpoint"`` can come back with ``halted`` true and ``output`` empty
        -- another ``step()`` takes the dump, which is outside ``max_steps``.
        Bounds return rather than raise (``None`` unbounded); a fault still
        raises, with ``partial_output`` set.
        The deadline is checked between steps and breakpoint callbacks,
        including at halt and after a dump. A callback or command already
        started can finish and its effects remain observable.

        Raises:
            ArgumentError: ``limits`` is not ExecutionLimits, or sets a bound
                other than ``max_steps`` or ``execution_timeout``: the rest
                need an isolated worker, and a debugger steps in-process.
        """
        selected = ExecutionLimits() if limits is None else limits
        if not _has_backing_type(selected, ExecutionLimits):
            raise ArgumentError("limits must be ExecutionLimits or None")
        for name in (
            "preparation_timeout",
            "total_timeout",
            "max_output",
            "max_memory",
        ):
            if getattr(selected, name) is not None:
                raise ArgumentError(
                    f"a debugger steps in-process and cannot enforce {name}; "
                    "it takes max_steps and execution_timeout"
                )
        return self._run(selected.max_steps, selected.execution_timeout)

    def _run(self, max_steps: int | None, timeout: float | None) -> StopReason:
        """Drive to a halt, breakpoint or bound; the limits are already checked."""
        _raise_halt_fault(self)
        deadline = None if timeout is None else monotonic() + timeout
        start = self._steps
        step = self._run_stepper()
        while True:
            while not self.halted:
                requested = self._stop_requested(deadline)
                if requested == "breakpoint" or requested == "execution_timeout":
                    return requested
                if requested == "replaced":
                    continue
                if requested == "halted":
                    break
                if max_steps is not None and self._steps - start >= max_steps:
                    return "max_steps"
                step()

            _raise_halt_fault(self)
            # The final command and the dump can each trigger a breakpoint.
            requested = self._stop_requested(deadline)
            if requested == "breakpoint" or requested == "execution_timeout":
                return requested
            if requested in ("active", "replaced"):
                continue
            if self.dumps_on_the_post_halt_step and not self._has_dumped():
                receiver = self.vm
                tail = _receiver_tail(receiver)
                if _expired(deadline):
                    return "execution_timeout"
                step()
                requested = self._stop_requested(deadline)
                if requested == "breakpoint" or requested == "execution_timeout":
                    return requested
                if requested in ("active", "replaced") or not _receiver_matches(
                    self, receiver, tail
                ):
                    # A new receiver gets its own command and dump boundaries.
                    _raise_halt_fault(self)
                    continue
            return "execution_timeout" if _expired(deadline) else "halted"

    def _repeat_execution(
        self, vm: _DelegatingVM, max_steps: int
    ) -> ExecutionOutcome | None:
        def step() -> None:
            if self._steps >= max_steps:
                raise steps_exhausted("execution stopped at the max_steps bound")
            self.step()

        report = vm._complete_repeating(step)  # noqa: SLF001
        if report is None:
            return None
        result = replace(_capture_observation(vm, report), steps=self._steps)
        return ExecutionOutcome("completed", result)

    def _execute(self, *, max_steps: int) -> ExecutionOutcome:
        """Finish a non-interactive invocation, retaining faults and bound stops."""
        try:
            if isinstance(self.vm, _DelegatingVM):
                completed = self._repeat_execution(self.vm, max_steps)
                if completed is not None:
                    return completed
            reason = self._run(max_steps, None)
            if reason == "halted":
                return ExecutionOutcome(
                    "completed", replace(_capture_result(self.vm), steps=self._steps)
                )
        except EsolangError as fault:
            observation = replace(_capture_observation(self.vm), steps=self._steps)
            _record_vm_fault(self.vm, fault, observation)
            return _failed_outcome(fault, observation=observation)
        if reason == "breakpoint":
            raise ArgumentError("invocation execution cannot stop at a breakpoint")
        error = steps_exhausted(f"execution stopped at the {reason} bound")
        error.partial_output = self.output
        error.observation = replace(_capture_observation(self.vm), steps=self._steps)
        return _failed_outcome(error)


def _receiver_tail(first: VM) -> tuple[VM, ...] | None:
    """Capture nested links without allocating for a direct receiver."""
    if not isinstance(first, ExecutionController):
        return None
    tail: list[VM] = []
    seen = {id(first)}
    current = first.vm
    while isinstance(current, ExecutionController):
        if id(current) in seen:
            raise TypeError("debugger VM chain contains a cycle")
        seen.add(id(current))
        tail.append(current)
        current = current.vm
    tail.append(current)
    return tuple(tail)


def _receiver_matches(
    controller: ExecutionController, first: VM, tail: tuple[VM, ...] | None
) -> bool:
    """Keep each dispatch link pinned by identity."""
    if controller.vm is not first:
        return False
    if tail is not None:
        for receiver in tail:
            if not isinstance(first, ExecutionController) or first.vm is not receiver:
                return False
            first = receiver
    return True
