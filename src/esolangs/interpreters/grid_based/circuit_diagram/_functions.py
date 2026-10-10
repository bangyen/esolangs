"""Atomic function evaluation and clock replay for Circuit Diagram."""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
from threading import Lock
from typing import TYPE_CHECKING

from esolangs.interpreters.grid_based.circuit_diagram._hints import Hint
from esolangs.interpreters.io import ScriptedIO

if TYPE_CHECKING:
    from esolangs.interpreters.grid_based.circuit_diagram._parse import _Gate


class _ClockStream:
    """Count runtime clock reads so a changing clock cannot fake a cycle."""

    def __init__(self) -> None:
        self.position = 0

    def read(self) -> int:
        self.position += 1
        from esolangs.interpreters.grid_based.circuit_diagram import _seconds_since_2000

        return _seconds_since_2000()


type _WidthKey = tuple[
    tuple[tuple[str, tuple[str, ...]], ...],
    str,
    tuple[str, ...] | None,
    tuple[int, ...],
]
_FUNCTION_WIDTHS: OrderedDict[_WidthKey, int] = OrderedDict()
_FUNCTION_WIDTH_LOCK = Lock()


def _cached_width(key: _WidthKey) -> int | None:
    with _FUNCTION_WIDTH_LOCK:
        return _FUNCTION_WIDTHS.get(key)


def _remember_width(key: _WidthKey, width: int) -> None:
    with _FUNCTION_WIDTH_LOCK:
        _FUNCTION_WIDTHS[key] = width
        _FUNCTION_WIDTHS.move_to_end(key)
        if len(_FUNCTION_WIDTHS) > 256:
            _FUNCTION_WIDTHS.popitem(last=False)


def _width_key(gate: _Gate, inputs: tuple[tuple[int, ...], ...]) -> _WidthKey:
    return (
        tuple(sorted(gate.definitions.items())),
        gate.kind,
        gate.body,
        tuple(map(len, inputs)),
    )


class _TypeClock(_ClockStream):
    """Width analysis depends on arrival presence, not clock data."""

    def read(self) -> int:
        self.position += 1
        return 0


class _ReplayClock(_ClockStream):
    """Replay a suspended atomic call's reads without reading the clock twice."""

    def __init__(self, parent: _ClockStream) -> None:
        self.parent = parent
        self.values: list[int] = []
        self.cursor = 0
        self.position = parent.position

    def read(self) -> int:
        pending: list[_ReplayClock] = []
        current: _ClockStream = self
        while isinstance(current, _ReplayClock):
            if current.cursor < len(current.values):
                value = current.values[current.cursor]
                current.cursor += 1
                current.position = current.parent.position
                break
            pending.append(current)
            current = current.parent
        else:
            value = current.read()
        for recorder in reversed(pending):
            recorder.values.append(value)
            recorder.cursor += 1
            recorder.position = current.position
        return value

    def skip(self, count: int) -> None:
        self.cursor += count
        if self.cursor > len(self.values):
            raise RuntimeError("clock replay exceeds recorded prefix")
        self.position = self.parent.position


class _NeedFunctionError(Exception):
    """Suspend a body until an atomic dependency has been evaluated."""

    def __init__(
        self,
        gate: _Gate,
        inputs: tuple[tuple[int, ...], ...],
        clock: _ClockStream | None,
        *,
        type_only: bool,
        slot: int | None = None,
        start: int = 0,
    ) -> None:
        super().__init__(gate.kind)
        self.gate = gate
        self.inputs = inputs
        self.clock = clock
        self.type_only = type_only
        self.slot = slot
        self.start = start
        self.key = _width_key(gate, inputs)


class _FunctionFrame:
    """One suspended body and the results of its ordered nested calls."""

    def __init__(self, request: _NeedFunctionError) -> None:
        self.request = request
        parent = _TypeClock() if request.type_only else request.clock
        self.clock = _ReplayClock(parent if parent is not None else _ClockStream())
        self.results: dict[
            int, tuple[_WidthKey, tuple[tuple[int, ...], ...], tuple[int, ...], int]
        ] = {}
        self.next_call = 0


class _FunctionEvaluation:
    """Evaluate dependencies on a heap, with no recursive Python calls."""

    def __init__(self, request: _NeedFunctionError) -> None:
        self.frames = [_FunctionFrame(request)]
        self.widths: dict[_WidthKey, int] = {}

    def resolve(
        self,
        gate: _Gate,
        inputs: tuple[tuple[int, ...], ...],
        clock: _ClockStream | None,
        *,
        type_only: bool,
    ) -> tuple[int, ...]:
        frame = self.frames[-1]
        type_only = type_only or frame.request.type_only
        key = _width_key(gate, inputs)
        if type_only:
            width = self.widths.get(key, _cached_width(key))
            if width is not None:
                return (0,) * width
            slot = None
            start = 0
        else:
            slot = frame.next_call
            frame.next_call += 1
            if slot in frame.results:
                old_key, old_inputs, output, reads = frame.results[slot]
                if (key, inputs) != (old_key, old_inputs):
                    raise RuntimeError("function replay changed its request")
                frame.clock.skip(reads)
                return output
            clock = frame.clock
            start = frame.clock.cursor
        if any(old.request.gate.kind == gate.kind for old in self.frames):
            raise ValueError(f"function {gate.kind!r} recursively depends on itself")
        raise _NeedFunctionError(
            gate, inputs, clock, type_only=type_only, slot=slot, start=start
        )

    def run(self) -> tuple[int, ...]:
        while True:
            frame = self.frames[-1]
            frame.next_call = 0
            frame.clock.cursor = 0
            inputs = frame.request.inputs
            if frame.request.type_only:
                inputs = tuple((0,) * len(value) for value in inputs)
            try:
                output = _evaluate_function_body(
                    frame.request.gate, inputs, frame.clock
                )
            except _NeedFunctionError as dependency:
                dependency.__traceback__ = None
                self.frames.append(_FunctionFrame(dependency))
                continue
            self.frames.pop()
            request = frame.request
            if request.type_only:
                width = len(output)
                self.widths[request.key] = width
                _remember_width(request.key, width)
                output = (0,) * width
            if not self.frames:
                return output
            if request.slot is not None:
                parent = self.frames[-1]
                reads = parent.clock.cursor - request.start
                parent.results[request.slot] = (
                    request.key,
                    request.inputs,
                    output,
                    reads,
                )


_FUNCTION_WORK: ContextVar[_FunctionEvaluation | None] = ContextVar(
    "circuit_function_work", default=None
)


def _evaluate_function(
    gate: _Gate,
    inputs: tuple[tuple[int, ...], ...],
    clock: _ClockStream | None = None,
    *,
    type_only: bool = False,
) -> tuple[int, ...]:
    """Evaluate an atomic gate on a heap; width analysis caches only lengths."""
    active = _FUNCTION_WORK.get()
    if active is not None:
        return active.resolve(gate, inputs, clock, type_only=type_only)
    key = _width_key(gate, inputs)
    cached = _cached_width(key) if type_only else None
    if cached is not None:
        return (0,) * cached
    work = _FunctionEvaluation(
        _NeedFunctionError(gate, inputs, clock, type_only=type_only)
    )
    token = _FUNCTION_WORK.set(work)
    try:
        return work.run()
    finally:
        _FUNCTION_WORK.reset(token)


def _evaluate_function_body(
    gate: _Gate, inputs: tuple[tuple[int, ...], ...], clock: _ClockStream | None
) -> tuple[int, ...]:
    """Evaluate one custom gate atomically for ``inputs``."""
    from esolangs.interpreters.grid_based.circuit_diagram import _emitted, _Machine
    from esolangs.interpreters.grid_based.circuit_diagram._parse import (
        _LABEL_RUN,
        _WIRES,
        _width_integer,
    )

    if gate.body is None:  # pragma: no cover - callers select custom gates
        raise Hint.FUNCTION_BODY.error(f"{gate.kind!r} has no function body")
    bindings: dict[str, int] = {}
    input_rows = [line for line in gate.body if line.lstrip().startswith("-")]
    if len(input_rows) != len(inputs):  # pragma: no cover - arity checked earlier
        raise Hint.FUNCTION_ARITY.error(
            f"function {gate.kind!r} input count changed while running"
        )
    for line, value in zip(input_rows, inputs, strict=True):
        labels = [
            match
            for match in _LABEL_RUN.finditer(line)
            if match.group() not in gate.definitions
            if match.start() > 0
            and line[match.start() - 1] in _WIRES
            and match.end() < len(line)
            and line[match.end()] in _WIRES
        ]
        if not labels:
            if len(value) != 1:
                raise Hint.SINGLE_INPUT_WIRE.error(
                    f"function {gate.kind!r} expects a one-wire input, "
                    f"received {len(value)}"
                )
            continue
        terms = labels[0].group().split("+")
        if all(term.isdigit() for term in terms):
            expected = sum(_width_integer(term) for term in terms)
            if expected != len(value):
                raise Hint.INPUT_WIDTH.error(
                    f"function {gate.kind!r} expects {expected} input wires, "
                    f"received {len(value)}"
                )
        elif len(terms) == 1 and terms[0].isalpha():
            old = bindings.setdefault(terms[0], len(value))
            if old != len(value):
                raise Hint.BOUND_WIDTH.error(
                    f"function {gate.kind!r} binds {terms[0]!r} "
                    f"to both {old} and {len(value)}"
                )
        else:
            raise Hint.INPUT_LABEL.error(
                f"function {gate.kind!r} input label must be a number or one name"
            )

    expanded = []
    for line in gate.body:
        pieces: list[str] = []
        end = 0
        for match in _LABEL_RUN.finditer(line):
            if match.group() in gate.definitions:
                continue
            if not (
                match.start() > 0
                and line[match.start() - 1] in _WIRES
                and match.end() < len(line)
                and line[match.end()] in _WIRES
            ):
                continue
            pieces.append(line[end : match.start()])
            terms = match.group().split("+")
            pieces.append("+".join(str(bindings.get(term, term)) for term in terms))
            end = match.end()
        pieces.append(line[end:])
        expanded.append("".join(pieces))

    declarations = [
        line
        for name, body in gate.definitions.items()
        for line in (f"{{{name}", *body, "}")
    ]
    stdin = "".join(f"{bit}\n" for value in inputs for bit in value)
    io = ScriptedIO(stdin)
    machine = _Machine(declarations + expanded, io, clock=clock)
    seen: set[tuple[object, ...]] = set()
    emitted: list[str] = []
    while not machine.halted:
        # Signal presence and filled latches alone determine future firing;
        # clock data may change, but cannot make an activity cycle settle.
        snapshot = (
            tuple(value is not None for value in machine.values),
            tuple(
                tuple(slot is not None for slot in slots) for slots in machine.latches
            ),
        )
        if snapshot in seen:
            raise Hint.SETTLED_FUNCTION.error(f"function {gate.kind!r} does not settle")
        seen.add(snapshot)
        emitted.extend(
            _emitted((machine.values, machine.latches), machine.gates, machine.index)
        )
        machine.step()
    output = "".join(emitted)
    if not output or set(output) - {"0", "1"}:
        raise Hint.RETURN_BITS.error(f"function {gate.kind!r} did not return bits")
    return tuple(int(bit) for bit in output)
