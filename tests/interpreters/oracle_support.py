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
