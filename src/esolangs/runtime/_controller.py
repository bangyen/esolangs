"""Execution accounting, cooperative bounds and finalization below debugging."""

from __future__ import annotations

from dataclasses import replace
from time import monotonic
from typing import Literal

from esolangs.exceptions import ArgumentError, EsolangError, steps_exhausted
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome, _failed_outcome
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime._validate import _argument_repr
from esolangs.runtime._vm_protocol import VM
from esolangs.vm import (
    _capture_observation,
    _capture_result,
    _DelegatingVM,
    complete_vm,
    run_until_halt,
)

StopReason = Literal["halted", "breakpoint", "max_steps", "execution_timeout"]


class ExecutionController:
    """Drive a VM with shared bounds, completion and execution observations."""

    def __init__(self, vm: VM) -> None:
        if isinstance(vm, type) or not callable(getattr(vm, "step", None)):
            raise ArgumentError(f"vm must be a VM, got {_argument_repr(vm)}")
        self.vm = vm
        self._timed_out = False
        self._dumped = False
        self._steps = 0
        self._faulted = False

    def _record(self) -> None:
        """Observe a completed step; debugger subclasses record watches."""

    def _stop_requested(self) -> bool:
        """Whether an observer asks to stop before the next step."""
        return False

    def _accept_stop(self) -> bool:
        """Acknowledge an observer stop after a run boundary."""
        return False

    @property
    def halted(self) -> bool:
        """Whether the wrapped VM has finished executing."""
        return self.vm.halted

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
        report = None
        if (
            self.halted
            and not self._faulted
            and self.steppable_to_answer
            and (not self.dumps_on_the_post_halt_step or self._dumped)
        ):
            report = CompletionReport(
                Completion.POST_HALT
                if self.dumps_on_the_post_halt_step
                else Completion.HALTED
            )
        return replace(_capture_observation(self.vm, report), steps=self._steps)

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
        active = not self.vm.halted
        try:
            self.vm.step()
        except EsolangError as exc:
            self._faulted = True
            exc.partial_output = self.output
            exc.observation = replace(self.observation, completion=None)
            raise
        if active:
            self._faulted = False
            self._steps += 1
        elif self.dumps_on_the_post_halt_step:
            self._faulted = False
            self._dumped = True
        self._record()

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
        The deadline is checked with the breakpoints, so no main thread is
        needed.  Drives the controller so observer hooks see every successful step.

        Raises:
            ArgumentError: ``limits`` is not ExecutionLimits, or sets a bound
                other than ``max_steps`` or ``execution_timeout``: the rest
                need an isolated worker, and a debugger steps in-process.
        """
        selected = ExecutionLimits() if limits is None else limits
        if not isinstance(selected, ExecutionLimits):
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
        deadline = None if timeout is None else monotonic() + timeout
        self._timed_out = False
        halted = run_until_halt(self, max_steps, stop=lambda: self._stop(deadline))
        if halted:
            # Breakpoints are checked before each step, so one the final
            # step makes true was never seen (``break_on_output`` on a
            # program ending in ``.``).  Checked both before and after the
            # dump step below, because the dump changes ``output``:
            # after-only lost ``vm.halted and vm.output == ""`` on the
            # dumping languages, before-only puts the dumped text out of reach.
            if self._accept_stop():
                return "breakpoint"
            if self.dumps_on_the_post_halt_step and not self._dumped:
                # Cross the halt for the dumping languages, or ``run``
                # ends with the answer one un-taken step away (the CLI
                # printed ``output: ''`` on a correct program).  Once per
                # debugger, not per run: it lands in every watch history,
                # and three idle ``run()`` calls on a halted machine
                # grew ``watch_cell`` by three.
                try:
                    complete_vm(self.vm, max_steps=0)
                    self._dumped = True
                    self._faulted = False
                except EsolangError as exc:
                    self._faulted = True
                    exc.partial_output = self.output
                    exc.observation = replace(self.observation, completion=None)
                    raise
                self._record()
                if self._accept_stop():
                    return "breakpoint"
            return "halted"
        if self._timed_out:
            return "execution_timeout"
        if self._accept_stop():
            return "breakpoint"
        return "max_steps"

    def _periodic_execution(
        self, vm: _DelegatingVM, max_steps: int
    ) -> ExecutionOutcome:
        def step() -> None:
            if self._steps >= max_steps:
                raise steps_exhausted("execution stopped at the max_steps bound")
            self.step()

        report = vm._complete_periodic(step)  # noqa: SLF001
        result = replace(_capture_observation(vm, report), steps=self._steps)
        return ExecutionOutcome("completed", result)

    def _execute(self, *, max_steps: int) -> ExecutionOutcome:
        """Finish a non-interactive invocation, retaining faults and bound stops."""
        try:
            if isinstance(self.vm, _DelegatingVM) and not self.steppable_to_answer:
                return self._periodic_execution(self.vm, max_steps)
            reason = self._run(max_steps, None)
        except EsolangError as fault:
            fault.partial_output = self.output
            observation = fault.observation or _capture_observation(self.vm)
            fault.observation = replace(observation, steps=self._steps)
            return _failed_outcome(fault)
        if reason == "halted":
            return ExecutionOutcome(
                "completed", replace(_capture_result(self.vm), steps=self._steps)
            )
        if reason == "breakpoint":
            raise ArgumentError("invocation execution cannot stop at a breakpoint")
        error = steps_exhausted(f"execution stopped at the {reason} bound")
        error.partial_output = self.output
        error.observation = replace(_capture_observation(self.vm), steps=self._steps)
        return _failed_outcome(error)

    def _stop(self, deadline: float | None) -> bool:
        """Whether to stop before the next step: a breakpoint, or the clock."""
        if deadline is not None and monotonic() > deadline:
            self._timed_out = True
            return True
        return self._stop_requested()
