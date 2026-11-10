"""Root-only complete declared finite Forbin cohort, not all-owner modeling."""

# ruff: noqa: N806
import re
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import esolangs
from esolangs.debugger import make_debugger
from esolangs.exceptions import HaltError, InputExhaustedError, ProgramError
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.vm import _capture_observation, _capture_workspace, make_vm

from . import accounting_bytes as byte_family
from . import accounting_core as core
from .accounting_cycle import Observer, same
from .accounting_grammar import Reader
from .accounting_model import Closure, Machine, ModelHalt, Port

ROOT = Path(__file__).resolve().parent
HALTED = CompletionReport(Completion.HALTED)


def cases():
    """Preserve each earlier cohort once, then the literal old loop tail."""
    from .accounting_data import BASE69, ERRORS17

    records = [dict(record) for record in BASE69]
    records += byte_family.cases()
    records += [dict(record) for record in ERRORS17]
    records.append(
        {
            "name": "original-same-value-loop-tail",
            "source": "main { for i:0..1 { x = 0; } }",
            "stdin": "",
            "output": "",
        }
    )
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
    if "name" in record:
        core.exact(rows[-1].error, record.get("error"))
    return program, rows


def result(row, completion=None, steps=None):
    return ExecutionResult(
        row.port.output,
        row.port.position,
        row.port.reads,
        row.port.past_end,
        completion,
        steps,
    )


def exact_result(actual, expected):
    assert type(actual) is ExecutionResult
    assert type(expected) is ExecutionResult
    core.exact(tuple(actual[:4]), tuple(expected[:4]))
    core.exact(actual.steps, expected.steps)
    if expected.completion is None:
        assert actual.completion is None
    else:
        assert type(actual.completion) is CompletionReport
        assert actual.completion.kind is expected.completion.kind
        assert actual.completion.cycle is None
        assert expected.completion.cycle is None


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


def kind_class(kind, route):
    if kind == "EOFError":
        return InputExhaustedError
    if kind == "HaltError":
        return HaltError
    assert kind == "ValueError"
    return ValueError if route in ("raw", "prepare") else ProgramError


def check_error(error, record, row, route, *, constructor, successful):
    assert type(error) is kind_class(row.error, route)
    if row.error == "EOFError":
        core.exact(
            (error.reads, error.supplied, error.unit),
            (row.port.position, len(record["stdin"]), "character"),
        )
    if "match" in record:
        assert re.search(record["match"], str(error)) is not None
    if route in ("raw", "prepare"):
        return
    assert error.partial_output == row.port.output
    observed = bool(
        row.port.output or row.port.position or row.port.reads or row.port.past_end
    )
    if constructor and not observed:
        assert error.execution is None
    else:
        exact_result(
            error.execution,
            result(row, steps=None if constructor or route != "debug" else successful),
        )


def construct(record, route, context):
    """Retain real caller IO even when a wrapper's constructor does not return."""
    ports = []
    original = context.native._Machine.__init__

    def observed(raw, source, port):
        ports.append(port)
        return original(raw, source, port)

    machine = failure = None
    with patch.object(context.native._Machine, "__init__", observed):
        try:
            if route in ("raw", "prepare"):
                port = context.scripted_io(record["stdin"])
                machine = (
                    context.native._Machine(record["source"], port)
                    if route == "raw"
                    else context.native.prepare_machine(record["source"], {})(port)
                )
            else:
                create = make_vm if route == "vm" else make_debugger
                machine = create(
                    "Forbin",
                    esolangs.ProgramArtifact(record["source"], "Forbin"),
                    stdin=record["stdin"],
                )
        except (ValueError, HaltError, InputExhaustedError) as error:
            failure = error
    assert len(ports) == 1
    return machine, ports[0], failure


def raw_of(machine, route):
    return (
        machine
        if route in ("raw", "prepare")
        else (machine._machine if route == "vm" else machine.vm._machine)
    )


def frame_view(frame, observer):
    """Use only opaque address/id sidecars after the full independent graph check."""
    actual_fn = observer.code.by_site[frame.function.site]
    function = (
        "<esolangs.languages.forbin.interpreter._parse._Function object at "
        + hex(id(actual_fn))
        + ">"
    )

    def value(item):
        if type(item) is Closure:
            scope = observer.bijection.native_for_model[item.environment]
            return f"<{item.function.name or 'literal'}@{scope}>"
        assert type(item) in (int, str)
        return repr(item)

    def tuple_text(items):
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"

    rows = (
        "None"
        if frame.rows is None
        else tuple_text(
            [tuple_text([value(item) for item in row]) for row in frame.rows]
        )
    )
    scope = observer.bijection.native_for_model[frame.environment]
    return (
        f"_Frame(fn={function}, scope={scope}, pos={frame.position}, for_rows={rows}, "
        f"for_names={frame.names!r}, for_ind={frame.index}, "
        f"for_started={frame.started!r}, "
        f"for_body_pos={frame.body_position})"
    )


def expected_views(row, observer):
    frames = row.machine.state.frames
    text = "[" + ", ".join(frame_view(frame, observer) for frame in frames[:8]) + "]"
    if len(frames) > 8:
        text += f" +{len(frames) - 8} more"
    elif len(text) > 60:
        text = text[:57] + "..."
    return (("frames", text),)


def wrapper_observe(machine, route, row, observer, successful):
    vm = machine if route == "vm" else machine.vm
    capture = _capture_workspace(vm)
    _, _, Variant, Snapshot, Model, _, _, _ = observer.context
    assert type(capture) is Snapshot
    assert type(capture.model) is Model
    core.exact(
        (capture.model.name, capture.model.components),
        (
            "forbin-v1",
            ("frames", "scopes", "input_cursor", "buffered_bits", "input_reads"),
        ),
    )
    core.check_parts(
        capture.parts, core.expected_parts(row.machine.parts(), Variant), Variant
    )
    exact_result(_capture_observation(vm), result(row))
    core.exact(machine.halted, row.machine.halted)
    core.exact(
        vm.ip,
        tuple(frame.position for frame in row.machine.state.frames)
        or (len(observer.program.source),),
    )
    memory = (
        []
        if row.machine.halted
        else [
            v
            for v in row.machine.state.environments[
                row.machine.state.frames[-1].environment
            ].values.values()
            if type(v) is int
        ]
    )
    core.exact(vm.memory, memory)
    core.exact(vm.stack, [])
    assert vm.ptr is None
    assert vm.self_halts is True
    assert vm.steppable_to_answer is True
    assert vm.eof_is_a_value is False
    assert vm.dumps_on_the_post_halt_step is False
    core.exact(vm.ip_shape, "opaque")
    core.exact(vm.views, expected_views(row, observer))
    wanted_key = observer.schedule.snapshot(row.machine)
    same(observer.bijection.normalize(machine.snapshot()), wanted_key)
    observer.check_cache(raw_of(machine, route))
    if route == "debug":
        completion = HALTED if row.machine.halted and row.error is None else None
        exact_result(machine.result, result(row, completion, successful))


def trace(record, route, context):
    program, rows = predict(record)
    machine, port, failure = construct(record, route, context)
    if rows[0].machine is None:
        assert machine is None
        assert failure is not None
        core.check_io(port, rows[0].port)
        check_error(failure, record, rows[0], route, constructor=True, successful=0)
        return {"boundaries": 0, "constructor_error": rows[0].error}
    assert failure is None
    assert machine is not None
    raw = raw_of(machine, route)
    assert raw.io is port
    observer, successful = Observer(program, context), 0
    for index, row in enumerate(rows):
        failure = None
        if index:
            try:
                machine.step()
            except (ValueError, HaltError, InputExhaustedError) as error:
                failure = error
            else:
                successful += not rows[index - 1].machine.halted
        if row.error is None:
            assert failure is None
        else:
            assert failure is not None
            check_error(
                failure, record, row, route, constructor=False, successful=successful
            )
        observer.observe(raw, row)
        transport_capture(observer.captures[-1].capture, context.variant)
        if route in ("vm", "debug"):
            wrapper_observe(machine, route, row, observer, successful)
    return {
        "boundaries": len(rows),
        "successful": successful,
        "error": rows[-1].error,
        "peak_bits": observer.oracle.bits,
        "written": observer.oracle.written,
    }


def endpoint(record):
    _, rows = predict(record)
    if rows[0].machine is None:
        return rows[0], None, True
    successful = 0
    for index, row in enumerate(rows[1:], 1):
        if row.error is not None:
            return row, successful, False
        successful += not rows[index - 1].machine.halted
        if row.machine.halted:
            return row, successful, False
    raise AssertionError("uncertified ordinary endpoint")


def public(record, *, bounded, isolated=False):
    row, successful, constructor = endpoint(record)
    kwargs = {"max_steps": 200} if bounded else {}
    failure = actual = None
    try:
        actual = esolangs.run(
            "Forbin",
            esolangs.ProgramArtifact(record["source"], "Forbin"),
            stdin=record["stdin"],
            timeout=2.0,
            isolated=isolated,
            **kwargs,
        )
    except (ValueError, HaltError, InputExhaustedError) as error:
        failure = error
    steps = successful if bounded and not constructor else None
    if row.error is not None:
        assert failure is not None
        assert actual is None
        assert type(failure) is kind_class(row.error, "public")
        if "match" in record:
            assert re.search(record["match"], str(failure)) is not None
        if row.error == "EOFError":
            core.exact(
                (failure.reads, failure.supplied, failure.unit),
                (row.port.position, len(record["stdin"]), "character"),
            )
        assert failure.partial_output == row.port.output
        observed = bool(
            row.port.output or row.port.position or row.port.reads or row.port.past_end
        )
        if bounded and constructor and not observed:
            assert failure.execution is None
        else:
            exact_result(failure.execution, result(row, steps=steps))
        return {
            "error": type(failure).__name__,
            "constructor": constructor,
            "steps": steps,
        }
    assert failure is None
    exact_result(actual, result(row, HALTED, steps))
    return {"error": None, "steps": steps}
