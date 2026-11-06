"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps a registered interpreter in a :class:`VM` exposing the
run state between commands; ``ip``/``memory``/``stack`` are language-shaped.

Three conventions defeat ``while not vm.halted: vm.step()``, so the VM
reports them: ``self_halts`` (``halted`` never becomes true),
``dumps_on_the_post_halt_step`` (output lands one step after the halt),
and ``steppable_to_answer`` (use :func:`esolangs.run` where it is false).

The five hang detectors -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, :func:`run_until_halt_or_growth`,
:func:`run_until_halt_or_value_growth` -- take a :class:`VM` or the state
it wraps, and raise :class:`TypeError` for a language lacking their
sub-protocol.  :func:`run_until_halt` proves nothing.
"""

from __future__ import annotations

from collections.abc import Hashable
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
from esolangs.artifacts import ProgramArtifact
from esolangs.exceptions import ArgumentError, InterpreterLimitError
from esolangs.registry import LANGUAGES, resolve
from esolangs.results import ExecutionResult
from esolangs.runtime._capabilities import IpShape as IpShape
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._drive import finalize
from esolangs.runtime._execution import (
    check_seed_for,
    interpreter_errors,
    interpreter_module,
    prepare_call,
)
from esolangs.runtime._input import InputSource
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._machine import MachinePreparation
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource, check_scale_for, effective_scale
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime._traits import trait, traits
from esolangs.runtime._validate import check_seed, check_whole
from esolangs.runtime._vm_views import machine_views
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options, effective_settings


def complete_vm(vm: VM, max_steps: int | None = 100_000) -> str:
    """Return finalized raw output after a proved halt, including a final dump.

    Raises on exhausted steps or an active machine that never self-halts. Repeated
    completion is safe: the post-halt step is idempotent by the VM contract.
    """
    if max_steps is not None:
        check_whole(max_steps, "max_steps")
    if not vm.self_halts and not vm.halted:
        raise ArgumentError("completion requires a machine that self-halts")
    if not run_until_halt(vm, max_steps):
        raise InterpreterLimitError("VM completion exhausted max_steps")
    # Public VMs declare the boolean trait; other attributes are caller-owned.
    finalize(
        vm,
        policy=Completion.POST_HALT
        if vm.dumps_on_the_post_halt_step
        else Completion.HALTED,
    )
    return vm.output


@runtime_checkable
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        """Everything the machine has written so far."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position, language-shaped.

        An index, a coordinate tuple, or ``None`` once the agent is
        consumed.  Tuple arity is unstable within a run (a language may
        change shape to ``None`` or ``()``, or grow and shrink), so size
        nothing to the initial arity;
        :meth:`~esolangs.debugger.Debugger.break_at` checks kind, not arity.
        For grid languages the leading components are row then column, never
        x then y; others report a tuple without being grids, and
        ``describe(...)["state_model"]`` separates them.
        """

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def ptr(self) -> int | None:
        """The tape pointer, where the machine has one.

        ``None`` where there is no such thing to point with: a stack, a
        grid, a register file.  Not every tape machine spells it the same
        way (a property here, a plain attribute there), so the adapter
        reads it by ``getattr`` and the protocol only promises the read.
        """

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""

    @property
    def ip_shape(self) -> IpShape:
        """How to read :attr:`ip` as a place in the source, if at all.

        ``"offset"`` (default) counts characters; ``"grid"`` is row, column,
        then heading; ``"line"`` starts with a line number; ``"opaque"`` is
        a real position that is not a place in the source.  Every tuple
        ``ip`` declares one of the last three
        (``test_a_positional_ip_says_what_it_counts``): a frame stack or
        a depth and cursor all look like ``(row, col)``.
        """

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The machine's own named state, as ``(name, text)`` pairs.

        Derived from its public property descriptors, so it cannot drift.
        """

    @property
    def self_halts(self) -> bool:
        """Whether the program can reach a halt of its own.

        ``False`` where the *language* has no halt: bound the run.  It
        does not promise a program runs forever -- a read can run out of
        input and end the program, and another language runs forever.
        No tally of carriers here; ``[n for n in
        list_languages() if describe(n)["self_halts"]]`` cannot drift.
        """

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output arrives on the step *after* the halt.

        A caller stopping at ``halted`` holds ``""``; one more ``step()``
        writes what ``run`` writes.
        """

    @property
    def eof_is_a_value(self) -> bool:
        """Whether a read past the end of the input yields a value here.

        The norm raises :class:`~esolangs.exceptions.InputExhaustedError`;
        ``True`` marks the languages that take a value instead, so an
        underfed program answers a different row.  Some are neither: a
        flag may be ``True`` yet the run halts on the read; another may be
        ``False`` yet the read *ends* the program.  A cyclic reader
        (``input_shape`` ``char_stream_cyclic``, Clockwise) never reaches an
        end to underfeed.  Every other language reading stdin, swept one line
        short, matches its flag.
        """

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        ``False`` where ``describe(n)["steppable_to_answer"]`` is false:
        the answer is the render after the walk is proven periodic (three
        million steps leave ``output`` empty).  Distinct from
        ``self_halts``, which a language carries while still writing its
        answer.  Use :func:`esolangs.run`.
        """


class _DelegatingVM:
    """Wrap a registered interpreter, copying its exposed memory and stack."""

    _machine: _cycles._StepMachine

    def __init__(
        self,
        language: str,
        program: Program,
        stdin: InputSource = "",
        *,
        scale: int | None = None,
        settings: DialectSettings | None = None,
        seed: int | None = None,
    ) -> None:
        self.language = language
        self._io = ScriptedIO(stdin)
        self._capabilities = LANGUAGES[language].runtime.capabilities
        module = interpreter_module(language)
        code, options = prepare_call(
            language,
            program,
            ExecutionContext(
                scale=scale, seed=seed, reproducible=True, settings=settings
            ),
        )
        preparation = LANGUAGES[language].runtime.machine_preparation
        prepare = cast(MachinePreparation, getattr(module, preparation))
        self._machine = prepare(code, options)(self._io)

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
    def ip_shape(self) -> IpShape:
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


def _capture_result(vm: VM) -> ExecutionResult:
    """Capture a finalized, halted VM without taking another step."""
    if not vm.halted:
        raise ArgumentError("execution result requires a halted VM")
    report = CompletionReport(
        Completion.POST_HALT if vm.dumps_on_the_post_halt_step else Completion.HALTED
    )
    return _capture_observation(vm, report)


def _capture_observation(
    vm: VM, report: CompletionReport | None = None
) -> ExecutionResult:
    """Capture live IO without stepping or claiming output finalization."""
    if isinstance(vm, _DelegatingVM):
        # Use owned code; unrelated instance attributes remain caller-owned.
        return _DelegatingVM._result(vm, report)  # noqa: SLF001
    return ExecutionResult(vm.output, None, None, None, report)


def _capture_workspace(vm: VM) -> WorkspaceSnapshot:
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
def machine_traits(language: str) -> dict[str, bool]:
    """Return the language's declared driving traits without loading execution."""
    name = resolve(language)
    return traits(LANGUAGES[name].runtime.capabilities)


@runtime_checkable
class SnapshotVM(VM, Protocol):
    """A :class:`VM` with the state cycle detection compares; internal.

    Out of the public protocol (2.0): users reach it as
    :meth:`~esolangs.debugger.Debugger.snapshot`.
    """

    def snapshot(self) -> Hashable:
        """Return the internal state cycle detection compares, hashable.

        ``output`` is excluded, so equal internal state means the same future
        computation.  The post-halt dump (``dumps_on_the_post_halt_step``)
        writes output without changing the snapshot on most such languages
        (Cyclic tag records the dump, so its snapshot changes).
        """


def make_vm(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    scale: int | None = None,
    settings: DialectSettings | None = None,
    seed: int | None = None,
) -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    ``stdin`` is consumed verbatim using the language's input unit. The name
    resolves case-insensitively via
    :func:`~esolangs.registry.resolve`.  A name outside the registry raises
    :class:`UnknownLanguageError`. Text and raster use the same step interface. The
    program and ``stdin`` are checked as :func:`esolangs.run` checks them (an
    unfilled template otherwise runs to a confident ``'0'``), as are ``scale``
    and ``settings``. A seed overrides reproducible stepping's language default;
    the checked value is what reaches the interpreter.
    """
    from esolangs import _check_program

    name = resolve(language)
    check_seed(seed)
    check_seed_for(name, seed)
    record = isinstance(program, ProgramArtifact)
    settings = effective_settings(name, program, settings)
    dialect_options(name, settings)
    scale = effective_scale(name, program, scale)
    source = _check_program(name, program, stdin)
    if not record:
        settings = effective_settings(name, source, settings)
    scale = effective_scale(name, source, scale)
    check_scale_for(name, scale)
    with interpreter_errors(
        f"the {name} interpreter recursed deeper than CPython's stack "
        "limit allows while loading this program",
        language=name,
    ):
        return _DelegatingVM(
            name, source, stdin, scale=scale, settings=settings, seed=seed
        )
