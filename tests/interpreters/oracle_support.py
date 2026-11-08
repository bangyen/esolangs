"""Observe production only; independent models supply their own expected traces."""

from esolangs.exceptions import ArgumentError, HaltError, InterpreterLimitError
from esolangs.runtime.io import ScriptedIO


def stalled(factory):
    """Return a fault that never steps."""

    class Fault(factory):
        def step(self):
            pass

    return Fault


def overread(factory):
    """Return a fault that consumes an extra character before every step."""

    class Fault(factory):
        def step(self):
            self.io.input_char()
            super().step()

    return Fault


def _error(error):
    if isinstance(error, ArgumentError):
        return "argument"
    if isinstance(error, EOFError):
        return "input"
    if isinstance(error, InterpreterLimitError):
        return "limit"
    if isinstance(error, HaltError):
        return "halt"
    return "syntax"


def stable_halt(view):
    """Wrap a view with the machine's post-halt snapshot-stability contract."""
    snapshots = []

    def state(machine):
        if machine.halted:
            snapshots.append(machine.snapshot())
            assert snapshots[-1] == snapshots[0]
        return view(machine)

    return state


def observed(factory, code, stdin, state, *, cap=64, post_halt=3):
    """Record state, halt, output and both input counters, including failed steps."""
    io = ScriptedIO(stdin)
    errors = (ArgumentError, EOFError, HaltError, ValueError)
    try:
        machine = factory(code, io)
    except errors as error:
        return _error(error), [
            (None, False, io.getvalue(), io.position(), io.progress())
        ]

    def view():
        return (
            state(machine),
            machine.halted,
            io.getvalue(),
            io.position(),
            io.progress(),
        )

    trace, failure = [view()], None
    for _ in range(cap):
        if machine.halted:
            break
        try:
            machine.step()
        except errors as error:
            failure = _error(error)
        trace.append(view())
        if failure:
            break
    if not failure and machine.halted:
        for _ in range(post_halt):
            try:
                machine.step()
            except errors as error:
                failure = _error(error)
            trace.append(view())
            if failure:
                break
    return failure, trace


def check_terminal(factory, code, stdin, view, expected, *, cap=64):
    """Compare a bounded run's terminal state/IO, with stable post-halt steps."""
    error, trace = observed(factory, code, stdin, stable_halt(view), cap=cap)
    assert error is None
    assert trace[-1] == expected


def checker(predict, state, *, cap=64):
    """Bind a full-trace predictor and native view to a fixed observation cap."""

    def check(factory, source, stdin):
        expected = predict(source, stdin)
        assert observed(factory, source, stdin, state, cap=cap) == expected, (
            source,
            stdin,
        )
        return expected

    return check


def decorate_io(factory, method, decorate):
    """Return a fault class decorating IO before positional source/IO init."""

    class Fault(factory):
        def __init__(self, source, io):
            original = getattr(io, method)
            setattr(io, method, decorate(original))
            super().__init__(source, io)

    return Fault
