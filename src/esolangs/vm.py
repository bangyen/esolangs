"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps a registered interpreter in a
:class:`~esolangs.runtime._vm_protocol.VM` exposing the run state;
``ip``/``memory``/``stack`` are language-shaped.

Three conventions defeat ``while not vm.halted: vm.step()``, so the VM
reports them: ``self_halts`` (``halted`` never becomes true),
``dumps_on_the_post_halt_step`` (output lands one step after the halt),
and ``steppable_to_answer`` (use :func:`esolangs.run` where it is false).

The five hang detectors -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, :func:`run_until_halt_or_growth`,
:func:`run_until_halt_or_value_growth` -- take a
:class:`~esolangs.runtime._vm_protocol.VM` or the state it wraps, and raise
:class:`TypeError` for a language lacking their
sub-protocol.  :func:`run_until_halt` proves nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import replace
from typing import Protocol, runtime_checkable

from esolangs._cycles import _check_driver, _check_driver_fields, _drive_until_halt
from esolangs._cycles import (
    run_until_halt as run_until_halt,
)
from esolangs._cycles import (
    run_until_halt_or_all_branches_cycle as run_until_halt_or_all_branches_cycle,
)
from esolangs._cycles import (
    run_until_halt_or_ancestor as run_until_halt_or_ancestor,
)
from esolangs._cycles import (
    run_until_halt_or_cycle as run_until_halt_or_cycle,
)
from esolangs._cycles import (
    run_until_halt_or_growth as run_until_halt_or_growth,
)
from esolangs._cycles import (
    run_until_halt_or_value_growth as run_until_halt_or_value_growth,
)
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    steps_exhausted,
)
from esolangs.registry._catalog import Catalog
from esolangs.runtime._drive import (
    _checked_halted,
    finalize,
)
from esolangs.runtime._execution import (
    check_seed_for,
    interpreter_errors,
    interpreter_module,
)
from esolangs.runtime._input import CheckedInput, InputSource, check_input
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._prepared import (
    _check_source_options,
    _prepare_checked_program,
    _PreparedRuntime,
    _runtime_reads_stdin,
)
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._traits import traits
from esolangs.runtime._validate import check_seed, check_whole
from esolangs.runtime._vm_adapter import (
    _capture_observation,
    _DelegatingVM,
    _post_halt_dumped,
    _raise_halt_fault,
    _retain_fault_steps,
)
from esolangs.runtime._vm_protocol import VM
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings


def complete_vm(vm: VM, max_steps: int | None = 100_000) -> str:
    """Return finalized raw output after a proved halt, including a final dump.

    An exhausted step budget retains the unfinished IO observation. Faults
    observed by this VM include the commands completed during this call.
    An active machine must be able to self-halt. Repeated completion is safe:
    the post-halt step is idempotent by the VM contract.
    """
    if max_steps is not None:
        max_steps = check_whole(max_steps, "max_steps")
    _check_driver(vm, "vm", "self_halts")
    steps = 0

    def retain(error: EsolangError, completed: int) -> None:
        _retain_fault_steps(vm, error, steps + completed)

    while True:
        _require_self_halt(vm)
        remaining = None if max_steps is None else max_steps - steps
        completed = _drive_until_halt(
            vm,
            remaining,
            on_fault=retain,
            check_active=_completion_receiver_guard(vm),
        )
        if completed is None:
            _check_driver_fields(vm, "vm", "output")
            error = steps_exhausted("VM completion exhausted max_steps")
            # Without a stop predicate, an active return has used the full budget.
            error.observation = replace(_capture_observation(vm), steps=max_steps)
            error.partial_output = error.observation.output
            raise error
        steps += completed
        if _finalize_halted_vm(vm, steps):
            _check_driver_fields(vm, "vm", "output")
            return vm.output


def _require_self_halt(vm: VM) -> None:
    if not vm.self_halts and not _checked_halted(vm.halted):
        raise ArgumentError("completion requires a machine that self-halts")


def _completion_receiver_guard(vm: VM) -> Callable[[], None] | None:
    """Check the active completion contract when a controller changes routes."""
    from esolangs.runtime._controller import (
        ExecutionController,
        _receiver_matches,
        _receiver_tail,
    )

    if not isinstance(vm, ExecutionController):
        return None
    wrapped = vm.vm
    tail = _receiver_tail(wrapped)

    def check_active() -> None:
        nonlocal wrapped, tail
        if vm.vm is wrapped and (tail is None or _receiver_matches(vm, wrapped, tail)):
            return
        _require_self_halt(vm)
        wrapped = vm.vm
        tail = _receiver_tail(wrapped)

    return check_active


def _finalize_halted_vm(vm: VM, steps: int) -> bool:
    """Finalize the halted VM and report whether its receiver stayed fixed."""
    _check_driver_fields(vm, "vm", "dumps_on_the_post_halt_step")
    dump_pending = vm.dumps_on_the_post_halt_step and not _post_halt_dumped(vm)
    receiver = None
    if dump_pending:
        from esolangs.runtime._controller import (
            ExecutionController,
            _receiver_matches,
            _receiver_tail,
        )

        if isinstance(vm, ExecutionController):
            wrapped = vm.vm
            receiver = (vm, wrapped, _receiver_tail(wrapped))
    try:
        finalize(vm, policy=Completion.POST_HALT if dump_pending else Completion.HALTED)
    except EsolangError as error:
        _retain_fault_steps(vm, error, steps)
        raise
    if dump_pending:
        _raise_halt_fault(vm)
    return receiver is None or _receiver_matches(*receiver)


def machine_traits(language: str, *, catalog: Catalog | None = None) -> dict[str, bool]:
    """Return a fresh dictionary of declared traits without loading execution."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    return traits(catalog.languages[name].runtime.capabilities)


@runtime_checkable
class SnapshotVM(VM, Protocol):
    """A VM with the state cycle detection compares; internal.

    Out of the public protocol (2.0): users reach it as
    :meth:`~esolangs.debugger.Debugger.snapshot`.
    """

    def snapshot(self) -> Hashable:
        """Return the internal state cycle detection compares, hashable.

        For deterministic machines with the same program and input, equal live
        snapshots imply the same future transitions. Output history is excluded.
        Thue captures its rewrite relation; external draws are excluded.
        Random-machine cycle proofs require the branching protocol.

        The post-halt dump (``dumps_on_the_post_halt_step``) writes output without
        changing most snapshots (Cyclic tag records the dump in its snapshot).
        """


def _make_vm(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    seed: int | None = None,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    prepared: _PreparedRuntime | None = None,
) -> VM:
    """Prepare a scoped VM with an invocation-owned input/output factory."""
    from esolangs.registry._catalog import get_catalog
    from esolangs.runtime._source import anchor_program_source

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if prepared is None:
        settings, scale = _check_source_options(
            name, program, settings, scale, catalog=catalog
        )
    seed = check_seed(seed)
    check_seed_for(name, seed, catalog=catalog)
    return _make_checked_vm(
        name,
        program,
        stdin=check_input(stdin)
        if _runtime_reads_stdin(catalog.languages[name].runtime)
        else "",
        settings=settings,
        scale=scale,
        seed=seed,
        catalog=catalog,
        io_factory=io_factory,
        prepared=prepared,
    )


def _make_checked_vm(
    name: str,
    program: ProgramSource,
    *,
    stdin: CheckedInput,
    seed: int | None,
    settings: DialectSettings | None,
    scale: int | None,
    catalog: Catalog,
    io_factory: Callable[[InputSource], ScriptedIO],
    prepared: _PreparedRuntime | None,
    reproducible: bool = True,
) -> VM:
    """Load a step machine after validating invocation choices and input shape."""
    if prepared is None:
        prepared = _prepare_checked_program(
            _PreparedRuntime,
            name,
            program,
            settings=settings,
            scale=scale,
            catalog=catalog,
            module_loader=interpreter_module,
        )
    with interpreter_errors(
        f"the {name} interpreter recursed deeper than CPython's stack "
        "limit allows while loading this program",
        language=name,
    ):
        return _DelegatingVM(
            name,
            prepared,
            stdin,
            seed=seed,
            reproducible=reproducible,
            catalog=catalog,
            io_factory=io_factory,
        )


def make_vm(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    seed: int | None = None,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
) -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    ``stdin`` is consumed verbatim using the language's input unit when the
    runtime can read stdin. The name
    resolves case-insensitively via
    :func:`~esolangs.registry.resolve`. Text and raster use the same step
    interface. TemplateArtifact must be filled first;
    literal text is interpreted without template guessing. A seed overrides
    reproducible stepping's language default;
    the checked value is what reaches the interpreter.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ProgramError: The program does not load, as for :func:`esolangs.run`.
        TemplateError: ``program`` is an unfilled template.
        ArgumentError: ``stdin``, ``seed``, ``scale`` or ``settings`` is
            invalid, as :func:`esolangs.run` checks them.
    """
    return _make_vm(
        language,
        program,
        stdin=stdin,
        scale=scale,
        settings=settings,
        seed=seed,
        catalog=catalog,
    )
