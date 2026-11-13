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
from functools import cache
from typing import Any, Protocol, cast, runtime_checkable

import esolangs._cycles as _cycles
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
from esolangs.exceptions import ArgumentError, steps_exhausted
from esolangs.exceptions import EsolangError as _EsolangError
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._capabilities import IpShape as _IpShape
from esolangs.runtime._drive import PeriodicMachine, drive_periodic, finalize
from esolangs.runtime._execution import (
    check_seed_for,
    interpreter_errors,
    interpreter_module,
)
from esolangs.runtime._input import InputSource
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._prepared import PreparedProgram, prepare_program
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime._traits import trait, traits
from esolangs.runtime._validate import check_seed, check_whole
from esolangs.runtime._vm_protocol import VM as _VM
from esolangs.runtime._vm_views import machine_views
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings


def complete_vm(vm: _VM, max_steps: int | None = 100_000) -> str:
    """Return finalized raw output after a proved halt, including a final dump.

    Raises on exhausted steps or an active machine that never self-halts. Repeated
    completion is safe: the post-halt step is idempotent by the VM contract.
    """
    if max_steps is not None:
        check_whole(max_steps, "max_steps")
    if not vm.self_halts and not vm.halted:
        raise ArgumentError("completion requires a machine that self-halts")
    if not run_until_halt(vm, max_steps):
        # The class and bound ``run`` raises for the same cap.
        raise steps_exhausted("VM completion exhausted max_steps")
    # Public VMs declare the boolean trait; other attributes are caller-owned.
    finalize(
        vm,
        policy=Completion.POST_HALT
        if vm.dumps_on_the_post_halt_step
        else Completion.HALTED,
    )
    return vm.output


@runtime_checkable
class _PassMachine(PeriodicMachine, Protocol):
    """A machine that declares its cycle-checkpoint stride."""

    @property
    def commands_per_pass(self) -> int: ...


class _DelegatingVM:
    """Wrap a registered interpreter, copying its exposed memory and stack."""

    _machine: _cycles._StepMachine

    def __init__(
        self,
        language: str,
        program: PreparedProgram,
        stdin: InputSource = "",
        *,
        seed: int | None = None,
        catalog: Catalog | None = None,
        io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    ) -> None:
        from esolangs.registry._catalog import get_catalog

        catalog = get_catalog(catalog)
        self.language = language
        self._io = io_factory(stdin)
        self._capabilities = catalog.languages[language].runtime.capabilities
        try:
            self._machine = program._factory(seed=seed)(self._io)  # noqa: SLF001
        except Exception as error:
            # Initializers can print/read before construction fails.
            # Refusals with no observed IO keep their unavailable observation.
            if isinstance(error, _EsolangError) and error.observation is not None:
                raise
            observed = _DelegatingVM._result(self, None)
            if (
                observed.output
                or observed.input_position
                or observed.input_reads
                or observed.input_past_end
            ):
                with interpreter_errors(
                    f"the {language} interpreter recursed deeper than CPython's stack "
                    "limit allows while loading this program",
                    self._io,
                    language=language,
                ):
                    raise
            raise

    @property
    def output(self) -> str:
        return self._io.getvalue()

    def _result(self, report: CompletionReport | None) -> ExecutionResult:
        """Capture public output with this VM's owned input counters."""
        return ExecutionResult(
            self.output,
            self._io.position(),
            self._io.reads,
            self._io.past_end,
            report,
        )

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        """Execute one instruction, translating what the interpreter raises.

        The same promise as :func:`esolangs.run`: a bare ``ValueError``
        becomes :class:`~esolangs.exceptions.ProgramError`, a
        ``RecursionError`` :class:`~esolangs.exceptions.InterpreterLimitError`.
        """
        try:
            self._machine.step()
        except Exception:
            # Translation is needed only on failure; a context per instruction
            # dominated the wrapper cost in the generator-size sweep.
            with interpreter_errors(
                f"the {self.language} interpreter recursed deeper than "
                "CPython's stack limit allows on this program",
                self._io,
                language=self.language,
            ):
                raise

    def _complete_periodic(self, step: Callable[[], None]) -> CompletionReport:
        """Finalize at the same pass boundary as the native driver."""
        machine = self._machine
        if not isinstance(machine, _PassMachine):
            raise ArgumentError("periodic execution requires a declared pass stride")
        with interpreter_errors(
            f"the {self.language} interpreter recursed deeper than "
            "CPython's stack limit allows on this program",
            self._io,
            language=self.language,
        ):
            cycle = drive_periodic(
                machine,
                machine.commands_per_pass,
                policy=Completion.PERIODIC,
                step=step,
            )
        return CompletionReport(Completion.PERIODIC, cycle)

    def snapshot(self) -> Hashable:
        """Return the underlying machine's complete state."""
        return self._machine.snapshot()

    # The views come off the machine by ``getattr`` too, so a language
    # with no stack or no addressable cells says nothing, and one whose
    # position is a plain ``ind`` need not repeat it as ``ip``.

    def _view(self, name: str, default: object) -> Any:
        """Read the declared debug attribute, or the absent-view default."""
        debug = self._capabilities.debug
        attribute = getattr(debug, name) if debug is not None else None
        return getattr(self._machine, attribute) if attribute is not None else default

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The declared current code position, or ``None``."""
        return cast("int | tuple[int, ...] | None", self._view("ip", None))

    @property
    def memory(self) -> list[int]:
        """The addressable integer cells, or empty where there is no such store.

        Empty too where the store is not integer cells (Caballo's mapping,
        Crement's instructions, B-tapemark's grids): they leaked through as
        ``list[int]``, and ``break_on_cell`` could not name a value.
        """
        cells = list(self._view("memory", ()))
        if all(type(cell) is int for cell in cells):
            return cells
        return []

    @property
    def ptr(self) -> int | None:
        value = self._view("ptr", None)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def stack(self) -> list[object]:
        """The stack, or empty where the language has none."""
        return list(self._view("stack", ()))

    @property
    def self_halts(self) -> bool:
        return trait(self._capabilities, "self_halts")

    @property
    def ip_shape(self) -> _IpShape:
        debug = self._capabilities.debug
        return debug.ip_shape if debug is not None else "offset"

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        debug = self._capabilities.debug
        return machine_views(self._machine, debug.views if debug is not None else ())

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        return trait(self._capabilities, "dumps_on_the_post_halt_step")

    @property
    def steppable_to_answer(self) -> bool:
        return trait(self._capabilities, "steppable_to_answer")

    @property
    def eof_is_a_value(self) -> bool:
        return trait(self._capabilities, "eof_is_a_value")


def _capture_result(vm: _VM) -> ExecutionResult:
    """Capture a finalized, halted VM without taking another step."""
    if not vm.halted:
        raise ArgumentError("execution result requires a halted VM")
    report = CompletionReport(
        Completion.POST_HALT if vm.dumps_on_the_post_halt_step else Completion.HALTED
    )
    return _capture_observation(vm, report)


def _capture_observation(
    vm: _VM, report: CompletionReport | None = None
) -> ExecutionResult:
    """Capture live IO without stepping or claiming output finalization."""
    if isinstance(vm, _DelegatingVM):
        # Use owned code; unrelated instance attributes remain caller-owned.
        return _DelegatingVM._result(vm, report)  # noqa: SLF001
    return ExecutionResult(vm.output, None, None, None, report)


def _capture_workspace(vm: _VM) -> WorkspaceSnapshot:
    """Require a registered interpreter's declared semantic accounting model."""
    if not isinstance(vm, _DelegatingVM):
        raise TypeError("workspace accounting requires a registered VM")
    machine = vm._machine  # noqa: SLF001 - owned adapter
    capture = getattr(type(machine), "workspace_snapshot", None)
    if not callable(capture):
        raise TypeError("workspace accounting requires workspace_snapshot")
    state = capture(machine)
    if not isinstance(state, WorkspaceSnapshot):
        raise TypeError("workspace_snapshot must return a WorkspaceSnapshot")
    return state


@cache
def machine_traits(language: str, *, catalog: Catalog | None = None) -> dict[str, bool]:
    """Return the language's declared driving traits without loading execution."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    return traits(catalog.languages[name].runtime.capabilities)


@runtime_checkable
class SnapshotVM(_VM, Protocol):
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
    prepared: PreparedProgram | None = None,
) -> _VM:
    """Prepare a scoped VM with an invocation-owned input/output factory."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.runtime._input import check_input

    name = catalog.resolve(language)
    check_seed(seed)
    check_seed_for(name, seed, catalog=catalog)
    check_input(stdin)
    if prepared is None:
        prepared = prepare_program(
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
) -> _VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    ``stdin`` is consumed verbatim using the language's input unit. The name
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
