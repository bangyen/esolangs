"""A debugger on top of the step-and-inspect VM.

:class:`Debugger` wraps a :class:`esolangs.debugger.VM` with breakpoints (stop
before the step that would change the condition) and watches (a per-step
history of a cell or stack slot).  Breakpoints are checked *before* each
step, so ``break_at`` on the initial position fires without executing it.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from inspect import signature
from typing import cast, get_args

from esolangs.exceptions import ArgumentError
from esolangs.registry._catalog import Catalog
from esolangs.runtime._capabilities import IpShape
from esolangs.runtime._controller import ExecutionController as _ExecutionController
from esolangs.runtime._controller import StopReason as StopReason
from esolangs.runtime._input import InputSource
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._validate import _argument_repr, check_whole
from esolangs.runtime._vm_protocol import VM
from esolangs.settings import DialectSettings
from esolangs.vm import SnapshotVM, make_vm

__all__ = [
    "STOP_REASONS",
    "VM",
    "Debugger",
    "StopReason",
    "make_debugger",
    "make_vm",
]

#: :data:`StopReason`'s members as iterable data: what :meth:`Debugger.run`
#: returns.  A fault raises instead.
STOP_REASONS: tuple[StopReason, ...] = get_args(StopReason)


def _value_at[T](
    values: Sequence[T], index: int, *, from_top: bool = False
) -> T | None:
    """Read a cell or stack slot, returning None when it is absent."""
    return values[-1 - index if from_top else index] if index < len(values) else None


def _watch[T](histories: dict[int, list[T]], index: int, name: str) -> list[T]:
    """Register a validated slot and return its live history."""
    check_whole(index, name)
    return histories.setdefault(index, [])


class Debugger(_ExecutionController):
    """Breakpoints and watches over a :class:`VM`.

    ``step()`` advances one command; ``run()`` until a halt or breakpoint --
    **pass ``limits``** (``max_steps`` or ``execution_timeout``) unless the
    program is known to halt.  The VM's properties and traits are mirrored so
    a driving caller never needs ``self.vm``; ``watch_cell``/``watch_stack``
    accumulate history.
    """

    def __init__(self, vm: VM) -> None:
        """Wrap ``vm`` with an empty breakpoint and watch set."""
        super().__init__(vm)
        self._breakpoints: list[Callable[[VM], bool]] = []
        self._cell_history: dict[int, list[int | None]] = {}
        self._stack_history: dict[int, list[object]] = {}
        self._suppressed: set[int] = set()
        self._hits: set[int] = set()

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The wrapped VM's current position.

        An ``int``, a tuple, or ``None``, not stable in kind or arity within a
        run; :attr:`~esolangs.debugger.VM.ip` has the rules :meth:`break_at` depends on.
        """
        return self.vm.ip

    @property
    def ip_shape(self) -> IpShape:
        """How the wrapped VM's ``ip`` reads as a place in the source."""
        return self.vm.ip_shape

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The wrapped VM's machine-specific named state."""
        return self.vm.views

    @property
    def memory(self) -> list[int]:
        """The wrapped VM's addressable cells."""
        return self.vm.memory

    @property
    def ptr(self) -> int | None:
        """The wrapped VM's tape pointer, or ``None`` where it has none."""
        return self.vm.ptr

    @property
    def stack(self) -> list[object]:
        """The wrapped VM's stack."""
        return self.vm.stack

    def snapshot(self) -> Hashable:
        """Return the wrapped machine's complete *internal* state, hashable.

        For deterministic machines with the same program and input, a repeated
        live snapshot proves a loop. Output history is excluded. Thue captures
        its rewrite relation, excluding an external provider's future draws;
        random-machine cycle proofs require the branching protocol.

        The post-halt dump writes output without changing most snapshots
        (Cyclic tag records the dump in its snapshot).  Every ``make_vm``
        machine has one; a hand-written VM needs ``snapshot()`` for this.
        """
        return cast(SnapshotVM, self.vm).snapshot()

    def break_at(self, ip: int | tuple[int, ...]) -> None:
        """Stop when the program counter reaches ``ip``.

        An ``int``, or a tuple for a coordinate ``ip``; anything else, or the
        wrong kind for this language, is refused rather than stored as a
        breakpoint that never fires.  Kind only, not arity (not constant within
        a run; see :attr:`~esolangs.debugger.VM.ip`).  ``None`` is refused although
        some languages reach it (``///`` from its first step): use
        ``break_when(lambda vm: vm.ip is None)``.
        A position never reached is accepted (the protocol has no ``len``).
        """
        if isinstance(ip, int) and not isinstance(ip, bool):
            pass  # Any int: AddSubJump and Subleq halt at -8 and -1.
        elif not (
            isinstance(ip, tuple)
            and ip
            and all(isinstance(part, int) and not isinstance(part, bool) for part in ip)
        ):
            raise ArgumentError(
                f"ip must be an integer or a tuple of them, got {_argument_repr(ip)}"
            )
        here = self.vm.ip
        if here is not None and here != ():
            kind = "a coordinate tuple" if isinstance(here, tuple) else "an index"
            if isinstance(here, tuple) != isinstance(ip, tuple):
                raise ArgumentError(
                    f"this language's ip is {kind} (currently {here!r}), so a "
                    f"breakpoint on {_argument_repr(ip)} could never fire"
                )
        self._breakpoints.append(lambda vm: vm.ip == ip)

    def break_on_cell(self, index: int, value: int) -> None:
        """Stop when ``memory[index]`` holds ``value``.

        A non-``int`` ``value`` raises ``ArgumentError``.
        """
        check_whole(index, "index")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentError(
                f"value must be an integer, got {_argument_repr(value)}"
            )
        self._breakpoints.append(lambda vm: _value_at(vm.memory, index) == value)

    def break_on_stack(self, slot: int, value: object) -> None:
        """Stop when the ``slot``-th stack value from the top holds ``value``.

        ``value`` is unchecked: a slot holds whatever its language pushes.
        """
        check_whole(slot, "slot")
        self._breakpoints.append(
            lambda vm: (
                slot < len(vm.stack)
                and _value_at(vm.stack, slot, from_top=True) == value
            )
        )

    def break_on_output(self, text: str) -> None:
        """Stop once ``text`` has been written so far.

        A non-string or empty ``text`` is refused here, not from inside the run
        loop; an empty one would stop before the first step.
        """
        if not isinstance(text, str):
            raise ArgumentError(f"text must be a string, got {type(text).__name__}")
        if not text:
            raise ArgumentError("text must be a non-empty string")
        self._breakpoints.append(lambda vm: text in vm.output)

    def break_when(self, predicate: Callable[[VM], bool]) -> None:
        """Stop when ``predicate(vm)`` holds; a catch-all for the rest.

        Callability and arity are checked here, not from inside the run loop.
        """
        if not callable(predicate):
            raise ArgumentError(
                f"predicate must be callable, got {type(predicate).__name__}"
            )
        try:
            signature(predicate).bind(self.vm)
        except TypeError as exc:
            raise ArgumentError(
                f"predicate must take one argument, the VM; "
                f"{_argument_repr(predicate)} does not: {exc}"
            ) from exc
        except ValueError as exc:
            # No inspectable signature (``max``, ``int``): bare ValueError.
            raise ArgumentError(
                f"cannot check that predicate takes the VM ({exc}); wrap it in a lambda"
            ) from exc
        self._breakpoints.append(predicate)

    def clear_breakpoints(self) -> None:
        """Drop every breakpoint, leaving the watches and the run intact.

        Resuming already suppresses the last hit until its condition goes false.
        """
        self._breakpoints.clear()
        self._suppressed.clear()
        self._hits.clear()

    def watch_cell(self, index: int) -> list[int | None]:
        """Record ``memory[index]`` each step, returning the history.

        A missing cell records ``None``, and memory *shrinks* on some languages
        (a cell count drops mid-run).  Recording starts here; the list is live.
        """
        return _watch(self._cell_history, index, "index")

    def watch_stack(self, slot: int) -> list[object]:
        """Record the ``slot``-th stack value from the top each step.

        A language with no stack records one ``None`` per step, not an empty
        history: ``stack`` is ``[]`` there, and the protocol draws no line.
        ``describe(...)["state_model"]`` is the fact to consult first.
        """
        return _watch(self._stack_history, slot, "slot")

    def _record(self) -> None:
        # Read only when watched: ``vm.memory`` copies the tape, so reading it
        # unconditionally made every step O(tape) (``+[>+]``: 80k steps 8.3 s).
        if self._cell_history:
            memory = self.vm.memory
            for index, cell_history in self._cell_history.items():
                cell_history.append(_value_at(memory, index))
        if self._stack_history:
            stack = self.vm.stack
            for slot, stack_history in self._stack_history.items():
                stack_history.append(_value_at(stack, slot, from_top=True))

    def _accept_stop(self) -> bool:
        """Whether a breakpoint holds; if so, suppress it until it changes."""
        if not self._stop_requested():
            return False
        self._suppressed = set(self._hits)
        return True

    def _stop_requested(self) -> bool:
        """Whether a breakpoint fires now: one that holds and did not already.

        Suppressed until its condition goes false again, per condition.
        Invisible for position and value breakpoints; the whole story for
        :meth:`break_on_output`, whose ``text in vm.output`` is true forever.
        """
        hits = {i for i, cond in enumerate(self._breakpoints) if cond(self.vm)}
        self._suppressed &= hits
        self._hits = hits
        return bool(hits - self._suppressed)


def make_debugger(
    language: str,
    program: ProgramSource,
    *,
    stdin: InputSource = "",
    seed: int | None = None,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
) -> Debugger:
    """Return a :class:`Debugger` over a fresh :class:`VM` for ``language``.

    ``stdin`` is consumed using the language's input unit.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ProgramError: The program is malformed.
        InputExhaustedError: A language that reads its whole input while the
            machine is built got too little; here, not at :meth:`Debugger.run`.
        ArgumentError: ``scale``, ``seed`` or ``settings`` is invalid, as
            :func:`esolangs.run` checks them.
    """
    return Debugger(
        make_vm(
            language,
            program,
            stdin=stdin,
            scale=scale,
            settings=settings,
            seed=seed,
            catalog=catalog,
        )
    )
