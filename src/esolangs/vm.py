r"""A step-and-inspect interface for the interpreter suite."""

from __future__ import annotations

import os
from collections.abc import Callable, Hashable, Sequence
from functools import cache
from typing import Any, Protocol, cast, runtime_checkable

from esolangs.exceptions import (
    InterpreterLimitError,
    ProgramError,
    UnknownLanguageError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import RUNNERS, resolve


@runtime_checkable
class _StepMachine(Protocol):
    r"""The minimal step-capable surface the hang detector steps on."""

    def step(self) -> None:
        r"""Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        r"""Whether the machine has finished executing."""

    def snapshot(self) -> Hashable:
        r"""Return the complete internal state, hashable for cycle detection."""


@runtime_checkable
class _StepMachineWithShape(_StepMachine, Protocol):
    r"""A step-capable machine that also describes its own VM shape."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        r"""The current code/instruction position."""

    @property
    def memory(self) -> Sequence[int]:
        r"""The addressable cells, or empty where there is no such store."""

    @property
    def stack(self) -> Sequence[object]:
        r"""The stack, or empty where the language has none."""


@runtime_checkable
class _BranchingStepMachine(Protocol):
    r"""A machine whose next random choice can be enumerated exactly."""

    def branching_snapshot(self) -> Hashable:
        r"""Return the initial complete state for a branching search."""

    def branching_halted(self, state: Hashable) -> bool:
        r"""Whether ``state`` has halted."""

    def branching_successors(
        self, state: Hashable, limit: int
    ) -> Sequence[Hashable] | None:
        r"""Return every next state, or ``None`` when it cannot be forked."""


def _unwrap(machine: object, protocol: type[Any], role: str) -> object:
    r"""Return ``machine``, or the interpreter state a :class:`VM` wraps."""
    if isinstance(machine, protocol):
        return machine
    inner = getattr(machine, "_machine", None)
    if isinstance(inner, protocol):
        return inner
    raise TypeError(
        f"{type(machine).__name__} is not {role}: neither it nor any machine "
        "it wraps provides the required members"
    )


def run_until_halt_or_cycle(machine: _StepMachine | VM) -> bool:
    r"""Step ``machine`` until it halts or revisits an exact state."""
    machine = cast(
        _StepMachine, _unwrap(machine, _StepMachine, "steppable with a snapshot")
    )
    tortoise = machine.snapshot()
    power = 1
    length = 0
    while not machine.halted:
        machine.step()
        length += 1
        # mypy narrows `machine.halted`.
        # and won't re-widen it across.
        halted: bool = machine.halted
        if halted:
            return True
        if machine.snapshot() == tortoise:
            return False
        if length == power:
            tortoise = machine.snapshot()
            power *= 2
            length = 0
    return True


def run_until_halt_or_all_branches_cycle(
    machine: _BranchingStepMachine | VM, limit: int = 10_000
) -> bool:
    r"""Explore random outcomes until one halts or every path is cyclic."""
    machine = cast(
        _BranchingStepMachine,
        _unwrap(machine, _BranchingStepMachine, "branch-enumerable"),
    )
    pending = [machine.branching_snapshot()]
    seen: set[Hashable] = set()
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        if len(seen) == limit:
            raise TimeoutError(
                f"undecided after {limit} branching states: the reachable "
                "graph may be unbounded"
            )
        seen.add(state)
        if machine.branching_halted(state):
            return True
        successors = machine.branching_successors(state, limit - len(seen))
        if successors is None:
            raise TimeoutError(
                "undecided: a branching transition needs input that cannot "
                "be safely forked"
            )
        pending.extend(successors)
    return False


@runtime_checkable
class _FramedMachine(Protocol):
    r"""A :class:`_StepMachine` that also exposes its call stack."""

    def step(self) -> None:
        r"""Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        r"""Whether the machine has finished executing."""

    @property
    def frames(self) -> Sequence[object]:
        r"""The live call stack, outermost frame first."""

    def frame_entry_key(self, frame: object) -> Hashable:
        r"""Return ``frame``'s entry state, hashable and comparable."""


def run_until_halt_or_ancestor(machine: _FramedMachine | VM, limit: int = 64) -> bool:
    r"""Step ``machine`` until it halts or a call provably replays an."""
    machine = cast(_FramedMachine, _unwrap(machine, _FramedMachine, "framed"))
    keys: dict[int, Hashable] = {}
    pushes = 0
    while pushes < limit:
        if machine.halted:
            return True
        depth_before = len(machine.frames)
        machine.step()
        if len(machine.frames) <= depth_before:
            continue
        pushes += 1
        depth = len(machine.frames) - 1
        # A shallower frame at this.
        # returned, so drop it rather.
        keys = {d: k for d, k in keys.items() if d < depth}
        keys[depth] = machine.frame_entry_key(machine.frames[-1])
        if keys[depth] in [k for d, k in keys.items() if d < depth]:
            return False
    raise TimeoutError(
        f"undecided after {limit} pushed frames: neither halted nor repeated "
        "an ancestor's entry state"
    )


@runtime_checkable
class _TapeMachine(Protocol):
    r"""A :class:`_StepMachine` on a rightward-growing tape of cells."""

    def step(self) -> None:
        r"""Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        r"""Whether the machine has finished executing."""

    @property
    def ip(self) -> Hashable:
        r"""The current code position, hashable and compared by equality."""

    @property
    def ptr(self) -> int:
        r"""The current cell pointer."""

    @property
    def tape(self) -> tuple[int, ...]:
        r"""The committed cells, index 0 leftmost."""

    def input_position(self) -> int:
        r"""Return the input cursor, so a reading loop is not a repeat."""


def run_until_halt_or_growth(machine: _TapeMachine | VM, limit: int = 100_000) -> bool:
    r"""Step ``machine`` until it halts or provably grows without bound."""
    machine = cast(_TapeMachine, _unwrap(machine, _TapeMachine, "a tape machine"))
    # The last visit keeps the.
    # proves a steady wave after.
    # Brent's O(1)-per-position.
    # transient.
    # is invalid if the period ever.
    last: dict[Hashable, tuple[int, tuple[int, ...], int]] = {}
    lowest: dict[Hashable, int] = {}
    origins: dict[Hashable, tuple[tuple[int, tuple[int, ...], int], int]] = {}
    waves: dict[Hashable, tuple[tuple[int, tuple[int, ...], int], int, int, int]] = {}
    for _ in range(limit):
        if machine.halted:
            return True
        ip, ptr, tape = machine.ip, machine.ptr, machine.tape
        for position in lowest:
            lowest[position] = min(lowest[position], ptr)
        for position, (before, low) in origins.items():
            origins[position] = (before, min(low, ptr))
        for position, (before, low, power, length) in waves.items():
            waves[position] = (before, min(low, ptr), power, length)
        cursor = machine.input_position()
        current = (ptr, tape, cursor)
        previous = last.get(ip)
        if previous is not None and _grows_forever(previous, current, lowest[ip]):
            return False
        last[ip] = current
        lowest[ip] = ptr

        origin = origins.get(ip)
        if origin is None:
            origins[ip] = (current, ptr)
        else:
            before, low = origin
            if _grows_forever(before, current, low):
                return False

        checkpoint = waves.get(ip)
        if checkpoint is None:
            waves[ip] = (current, ptr, 1, 0)
        else:
            before, low, power, length = checkpoint
            # The backstop for a drifting.
            # return, and the reason is.
            # claimed: measured by.
            # every growth program in the.
            # three disabled every one goes.
            # pipeline but three.
            # .
            # That is also why a mutation.
            # alive: mutating one arm's.
            # the other two reach anyway.
            # redundancy, not a missing.
            # the corpus is a handful of.
            # idle on all of them may still.
            # shape nobody has written down.
            if _grows_forever(before, current, low):  # pragma: no cover - see above
                return False
            length += 1
            if length == power:
                waves[ip] = (current, ptr, power * 2, 0)
            else:
                waves[ip] = (before, low, power, length)
        machine.step()
    raise TimeoutError(
        f"undecided after {limit} steps: neither halted nor grew by a "
        "provable translation"
    )


def _grows_forever(
    before: tuple[int, tuple[int, ...], int],
    after: tuple[int, tuple[int, ...], int],
    lowest: int,
) -> bool:
    r"""Whether ``after`` is ``before`` translated right by the growth."""
    ptr_before, tape_before, input_before = before
    ptr_after, tape_after, input_after = after
    displacement = ptr_after - ptr_before
    return (
        input_after == input_before
        and displacement > 0
        and len(tape_after) == len(tape_before) + displacement
        and lowest >= 1
        and all(
            tape_after[i + displacement] == tape_before[i]
            for i in range(lowest, len(tape_before))
        )
    )


@runtime_checkable
class _AffineMachine(Protocol):
    r"""A machine whose cells grow in *value* on a tape that does not grow."""

    def step(self) -> None:
        r"""Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        r"""Whether the machine has finished executing."""

    @property
    def key(self) -> Hashable:
        r"""The state compared by equality: code position, pointer, width."""

    @property
    def values(self) -> tuple[int, ...]:
        r"""The unbounded values, compared by subtraction, in a fixed order."""

    @property
    def clamp_slack(self) -> int | None:
        r"""The pending step's clamped quantity, or ``None`` if it clamps none."""

    def input_position(self) -> int:
        r"""Return the input cursor, so a reading loop is not a repeat."""


def run_until_halt_or_value_growth(
    machine: _AffineMachine | VM, limit: int = 20_000
) -> bool:
    r"""Step ``machine`` until it halts or provably grows in value forever."""
    machine = cast(
        _AffineMachine, _unwrap(machine, _AffineMachine, "an affine machine")
    )
    # One slack per step, in a.
    # that visited it.
    # of its own: collecting the.
    # once for every key still.
    # whose key never repeats --.
    # widening the tape, and would.
    # it.
    # visit is ever sliced out of.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[tuple[int, tuple[int, ...], int]]] = {}
    for index in range(limit):
        # Suffolk is the only affine.
        # halts -- its `halted` is a.
        # this return.
        if machine.halted:  # pragma: no cover - see above
            return True
        slacks.append(machine.clamp_slack)
        key = machine.key
        seen = visits.setdefault(key, [])
        seen.append((index, machine.values, machine.input_position()))
        del seen[:-3]
        if len(seen) == 3 and _climbs_forever(seen, slacks):
            return False
        machine.step()
    raise TimeoutError(
        f"undecided after {limit} steps: neither halted nor climbed by a "
        "provable affine step"
    )


def _climbs_forever(
    visits: list[tuple[int, tuple[int, ...], int]],
    slacks: list[int | None],
) -> bool:
    r"""Whether three visits advance affinely with every clamp holding."""
    (start, first, cursor), (split, second, middle), (end, third, last) = visits
    if cursor != middle or middle != last:
        return False
    if not len(first) == len(second) == len(third):
        return False
    step = tuple(b - a for a, b in zip(first, second, strict=True))
    if step != tuple(c - b for b, c in zip(second, third, strict=True)):
        return False
    if not any(step) or any(delta < 0 for delta in step):
        return False
    return _clamps_hold(slacks[start:split], slacks[split:end])


def _clamps_hold(before: list[int | None], after: list[int | None]) -> bool:
    r"""Whether two laps clamped alike, with no slack drifting toward a."""
    if len(before) != len(after):
        return False
    for previous, current in zip(before, after, strict=True):
        if (previous is None) != (current is None):
            return False
        if previous is None or current is None:
            continue
        if (previous >= 0) != (current >= 0):
            return False
        if previous >= 0 and current < previous:
            return False
        if previous < 0 and current > previous:
            return False
    return True


@runtime_checkable
class _SteppableMachine(Protocol):
    r"""The bare step-and-ask-if-halted surface a bounded drive needs."""

    def step(self) -> None:
        r"""Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        r"""Whether the machine has finished executing."""


def run_until_halt(
    machine: _SteppableMachine | VM,
    limit: int | None = None,
    *,
    stop: Callable[[], bool] | None = None,
) -> bool:
    r"""Step ``machine`` until it halts, or the budget or ``stop`` ends it."""
    steps = 0
    while not machine.halted:
        if stop is not None and stop():
            return False
        if limit is not None and steps == limit:
            return False
        machine.step()
        steps += 1
    return True


@runtime_checkable
class VM(Protocol):
    r"""A step-capable interpreter wrapper."""

    def step(self) -> None:
        r"""Execute one command, advancing the machine."""

    def snapshot(self) -> Hashable:
        r"""Return the complete state used by cycle detection."""

    @property
    def halted(self) -> bool:
        r"""Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        r"""Everything the machine has written so far."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        r"""The current code/instruction position, language-shaped."""

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells, or ``[]`` where there is no such store."""

    @property
    def stack(self) -> list[object]:
        r"""The stack, or ``[]`` where the language has none."""

    @property
    def ip_shape(self) -> str:
        r"""How to read :attr:`ip` as a place in the source, if at all."""

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        r"""The machine's own named state, as ``(name, text)`` pairs."""

    @property
    def self_halts(self) -> bool:
        r"""Whether the program can reach a halt of its own."""

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        r"""Whether the output arrives on the step *after* the halt."""

    @property
    def eof_is_a_value(self) -> bool:
        r"""Whether a read past the end of the input yields a value here."""

    @property
    def steppable_to_answer(self) -> bool:
        r"""Whether stepping this language ever reaches the answer."""


# : The names a caller already.
# : as "the machine's own".
# : rest are machinery -- the.
# : traits below.
# : it chose to name, which is.
_NOT_A_VIEW = frozenset(
    {
        "ip",
        "memory",
        "stack",
        "output",
        "halted",
        "snapshot",
        "branching_snapshot",
        "branching_halted",
        "branching_successors",
        "frame_entry_key",
        "self_halts",
        "steppable_to_answer",
        "dumps_on_the_post_halt_step",
        "eof_is_a_value",
        "ip_shape",
        "reproducible_seed",
    }
)

# : How many items of a.
# : tape can be thousands of.
# : cost more than running the.
_VIEW_ITEMS = 8


def _read_view(machine: object, name: str) -> str | None:
    r"""Return ``machine.name`` as short text, or ``None`` if it cannot be."""
    try:
        value = getattr(machine, name)
    except Exception:
        return None
    return _abbreviate(value)


def _abbreviate(value: object) -> str:
    r"""Render ``value`` short enough to sit on one row."""
    if isinstance(value, (list, tuple)) and len(value) > _VIEW_ITEMS:
        return f"{type(value)(value[:_VIEW_ITEMS])!r} +{len(value) - _VIEW_ITEMS} more"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


class _DelegatingVM:
    r"""A VM for an interpreter that describes its own shape."""

    _machine: _StepMachineWithShape

    def __init__(self, stdin: str = "") -> None:
        r"""Create the input stream every subclass's machine reads from."""
        self._io = ScriptedIO(stdin)

    @property
    def output(self) -> str:
        return self._io.getvalue()

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        r"""Execute one instruction, translating what the interpreter raises."""
        try:
            self._machine.step()
        except RecursionError as exc:
            raise InterpreterLimitError(
                f"the {type(self).__name__} interpreter recursed deeper than "
                f"CPython's stack limit allows on this program"
            ) from exc
        except ProgramError:
            raise
        except ValueError as exc:
            raise ProgramError(str(exc)) from exc

    def snapshot(self) -> Hashable:
        r"""Return the underlying machine's complete state."""
        return self._machine.snapshot()

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return list(self._machine.memory)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)

    # The two language conventions.
    # itself: that a language never.
    # step past the halt.
    # way ``reproducible_seed``.
    # facts about the language, so.
    # that follow the common shape.
    # .
    # The defaults are the common.
    # positively on the machines.
    # nothing self-halts and writes.

    @property
    def self_halts(self) -> bool:
        return bool(getattr(self._machine, "self_halts", True))

    @property
    def ip_shape(self) -> str:
        return str(getattr(self._machine, "ip_shape", "offset"))

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        machine = self._machine
        found = []
        for name, attribute in sorted(vars(type(machine)).items()):
            if name.startswith("_") or name in _NOT_A_VIEW:
                continue
            if not isinstance(attribute, property):
                continue
            text = _read_view(machine, name)
            if text is not None:
                found.append((name, text))
        return tuple(found)

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        return bool(getattr(self._machine, "dumps_on_the_post_halt_step", False))

    @property
    def steppable_to_answer(self) -> bool:
        return bool(getattr(self._machine, "steppable_to_answer", True))

    @property
    def eof_is_a_value(self) -> bool:
        return bool(getattr(self._machine, "eof_is_a_value", False))


def _derived_adapter(language: str) -> Callable[[str, str], _DelegatingVM]:
    r"""Build the adapter for a language whose wrapper is pure boilerplate."""
    module_path, split = RUNNERS[language]
    # Bound to another name first:.
    # function's ``language`` while.
    display_name = language

    class _Derived(_DelegatingVM):
        # : The registry's display name.
        # :.
        # : Only the derived class can.
        # : from a program and a stdin.
        # : debugger needs it to ask.
        # : of input is a value for.
        # : between a wrong answer and.
        language = display_name

        def __init__(self, program: str, stdin: str = "") -> None:
            super().__init__(stdin)
            import importlib
            import inspect

            from esolangs.interpreters.randomness import Seeded

            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            code = program.splitlines() if split else program
            # ``_Machine`` is private to.
            # this whole file is built.
            # import it by name for the.
            state = getattr(module, "_Machine")  # noqa: B009
            # A language with a random.
            # and a stepped VM has to be.
            # wherever it is accepted.
            # is: the interpreter falls.
            # .
            # The seed comes from the.
            # wants to start from is a fact.
            # own junction example goes.
            # written for a laser heading.
            # so, rather than every caller.
            if "rng" in inspect.signature(state).parameters:
                seed = getattr(state, "reproducible_seed", 0)
                self._machine = state(code, self._io, rng=Seeded(seed))
            else:
                self._machine = state(code, self._io)

    _Derived.__name__ = _Derived.__qualname__ = f"_{language}VM"
    _Derived.__doc__ = f"Adapter for {language}; the interpreter describes its shape."
    return _Derived


# Language name -> VM adapter.
# so every one gets a derived.
# thing that raises.
# rather than listed again.
# second thing to keep in step,.
# existed only to catch the two.
# retired it.
# interpreter is imported.
# stays as lazy as the.
# Typed as what it is used as.
# -- rather than as the base.
# ``_DelegatingVM`` itself.
# at that level, since each.
# machine in the shape that.
_VM_ADAPTERS: dict[str, Callable[[str, str], _DelegatingVM]] = {
    name: _derived_adapter(name) for name in RUNNERS
}


@cache
def machine_traits(language: str) -> dict[str, bool]:
    r"""Return ``language``'s three driving traits without running anything."""
    import importlib

    # No membership check beyond.
    # the registry, and the.
    # so a second guard here would.
    name = resolve(language)
    module = importlib.import_module(f"esolangs.interpreters.{RUNNERS[name][0]}")
    state = getattr(module, "_Machine")  # noqa: B009
    return {
        "self_halts": bool(getattr(state, "self_halts", True)),
        "dumps_on_the_post_halt_step": bool(
            getattr(state, "dumps_on_the_post_halt_step", False)
        ),
        "steppable_to_answer": bool(getattr(state, "steppable_to_answer", True)),
        "eof_is_a_value": bool(getattr(state, "eof_is_a_value", False)),
    }


def make_vm(language: str, program: str | os.PathLike[str], stdin: str = "") -> VM:
    r"""Return a step-and-inspect wrapper around ``language``'s interpreter."""
    from esolangs import check_program

    name = resolve(language)
    if name not in _VM_ADAPTERS:
        raise UnknownLanguageError(language)
    source = check_program(name, program, stdin)
    try:
        return _VM_ADAPTERS[name](source, stdin)
    except RecursionError as exc:
        raise InterpreterLimitError(
            f"the {name} interpreter recursed deeper than CPython's stack "
            f"limit allows while loading this program "
            f"({len(source)} characters)"
        ) from exc
    except ProgramError:
        raise
    except ValueError as exc:
        # Most interpreters parse in.
        # malformed program with a.
        # re-raises those as.
        # ``make_vm("brainfuck", "]")``.
        raise ProgramError(str(exc)) from exc
