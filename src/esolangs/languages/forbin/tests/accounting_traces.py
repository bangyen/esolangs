"""Root-only complete declared finite Forbin cohort, not all-owner modeling."""

import re
from copy import deepcopy
from unittest.mock import patch

from esolangs.exceptions import HaltError, InputExhaustedError

from . import accounting_core as core
from .accounting_cycle import Observer
from .accounting_data import RECORDS
from .accounting_grammar import Reader
from .accounting_model import Machine, ModelHalt, Port

_KEYS = ("source", "stdin", "output", "error", "match")
_FLIP = "flip bit { return !bit; }"
#: Reads a byte and prints its bits reversed and negated, via a helper call.
_BYTE = (
    _FLIP
    + " main { a,b,c,d,e,f,g,h = (in 0); out "
    + ",".join(f"(flip {bit})" for bit in "hgfedcba")
    + "; }"
)


def cases():
    """The saved records, every byte through ``_BYTE``, then a loop tail."""
    rows = [*RECORDS]
    rows += [
        (_BYTE, chr(value) + "unused", chr(255 - int(f"{value:08b}"[::-1], 2)))
        for value in range(256)
    ]
    rows.append(("main { for i:0..1 { x = 0; } }", "", ""))
    records = [
        dict(zip(_KEYS, row + (None,) * (5 - len(row)), strict=True)) for row in rows
    ]
    assert len(records) == 343
    return records


def predict(record):
    """Predict all constructed rows first; no native parser or state supplies facts."""
    port, program = Port(record["stdin"]), None
    try:
        program = Reader(record["source"]).program()
    except ValueError:
        rows = [core.Row(None, deepcopy(port), "ValueError")]
    else:
        try:
            machine = Machine(program, port)
        except (EOFError, ModelHalt) as error:
            kind = "EOFError" if type(error) is EOFError else "HaltError"
            rows = [core.Row(None, deepcopy(port), kind)]
        else:
            rows = [core.Row(deepcopy(machine), deepcopy(port), None)]
            for _ in range(200):
                if machine.halted:
                    break
                try:
                    machine.step()
                except (EOFError, ModelHalt) as error:
                    kind = "EOFError" if type(error) is EOFError else "HaltError"
                    rows.append(core.Row(deepcopy(machine), deepcopy(port), kind))
                    break
                rows.append(core.Row(deepcopy(machine), deepcopy(port), None))
            else:
                raise AssertionError(("unproved finite cohort", record))
            if machine.halted:
                for _ in range(3):
                    machine.step()
                    rows.append(core.Row(deepcopy(machine), deepcopy(port), None))
    core.exact(port.output, record["output"])
    core.exact(rows[-1].error, record["error"])
    return program, rows


def transport_capture(capture, variant):
    """Lossless schema/typed-parts envelope, not an undeclared native record codec."""
    from esolangs.runtime._json import worker_dumps, worker_loads
    from esolangs.runtime._result_wire import _state_from_wire, _state_wire

    def freeze(value):
        if type(value) is variant:
            return ("variant", value.kind, tuple(freeze(v) for v in value.values))
        if type(value) is tuple:
            return ("tuple", tuple(freeze(v) for v in value))
        if type(value) is frozenset:
            return ("frozenset", frozenset(freeze(v) for v in value))
        assert type(value) in (int, bool, str, type(None))
        return value

    canonical = (
        capture.model.name,
        capture.model.components,
        tuple(freeze(part) for part in capture.parts),
    )
    restored = _state_from_wire(worker_loads(worker_dumps(_state_wire(canonical))))
    core.exact(restored, canonical)
    assert hash(restored) == hash(canonical)


_ERRORS = {
    "EOFError": InputExhaustedError,
    "HaltError": HaltError,
    "ValueError": ValueError,
}


def check_error(error, record, row):
    assert type(error) is _ERRORS[row.error]
    if row.error == "EOFError":
        core.exact(
            (error.reads, error.supplied, error.unit),
            (row.port.position, len(record["stdin"]), "character"),
        )
    if record["match"] is not None:
        assert re.search(record["match"], str(error)) is not None


def construct(record, context):
    """Retain real caller IO even when the constructor does not return."""
    ports = []
    original = context.native._Machine.__init__

    def observed(raw, source, port):
        ports.append(port)
        return original(raw, source, port)

    machine = failure = None
    with patch.object(context.native._Machine, "__init__", observed):
        try:
            machine = context.native._Machine(
                record["source"], context.scripted_io(record["stdin"])
            )
        except (ValueError, HaltError, InputExhaustedError) as error:
            failure = error
    assert len(ports) == 1
    return machine, ports[0], failure


def trace(record, context):
    """Check every predicted row against the native machine, step by step."""
    program, rows = predict(record)
    machine, port, failure = construct(record, context)
    if rows[0].machine is None:
        assert machine is None
        assert failure is not None
        core.check_io(port, rows[0].port)
        check_error(failure, record, rows[0])
        return
    assert failure is None
    assert machine is not None
    assert machine.io is port
    observer = Observer(program, context)
    for index, row in enumerate(rows):
        failure = None
        if index:
            try:
                machine.step()
            except (ValueError, HaltError, InputExhaustedError) as error:
                failure = error
        if row.error is None:
            assert failure is None
        else:
            assert failure is not None
            check_error(failure, record, row)
        observer.observe(machine, row)
        transport_capture(observer.captures[-1].capture, context.variant)
