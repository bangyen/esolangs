"""Worker results retain counters and immutable periodic evidence."""

import copy
import json
from dataclasses import replace
from decimal import DivisionByZero
from fractions import Fraction

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES
from esolangs.results import ExecutionResult
from esolangs.runtime import _snapshot_wire
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime._failure_wire import _failure_wire
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._proof import CycleDecision
from esolangs.runtime._request_wire import encode_request
from esolangs.runtime._result_wire import decode_result, encode_decision, encode_result
from esolangs.runtime._snapshot_wire import _state_from_wire, _state_wire
from esolangs.runtime._worker_main import _worker
from esolangs.vm import make_vm
from tests.support.execution import run_observed
from tests.support.reference import REFERENCE
from tests.support.worker_response import _decode


@pytest.fixture
def interpreter_only_samples():
    from tests.support.samples import SAMPLES

    return {
        name: SAMPLES[name] for name, spec in LANGUAGES.items() if spec.backend is None
    }


def _assert_catalog_snapshot_round_trips(result, interpreter_only_samples):
    assert set(interpreter_only_samples) == {
        name for name, spec in LANGUAGES.items() if spec.backend is None
    }
    for name, spec in LANGUAGES.items():
        if spec.backend is None:
            cases = [interpreter_only_samples[name]]
        else:
            artifact = esolangs.generate(name, "01")
            cases = [
                (
                    esolangs.instantiate(name, artifact, [row])
                    if spec.parameterized
                    else artifact,
                    "" if spec.parameterized else esolangs.encode_inputs(name, [row]),
                )
                for row in (0, 1)
            ]
        for source, stdin in cases:
            options = {"stdin": stdin, "seed": 7 if spec.runtime.random else None}
            vm, debugger = (
                make_vm(name, source, **options),
                make_debugger(name, source, **options),
            )
            retained = []
            for step in range(9):
                cycle = BoundaryCycle(vm.snapshot(), 0, 1, step)
                assert debugger.snapshot() == cycle.state
                assert debugger.output == vm.output
                observed = replace(
                    result, completion=CompletionReport(Completion.PERIODIC, cycle)
                )
                restored = decode_result(
                    observed.output, json.loads(json.dumps(encode_result(observed)))
                )
                assert restored == observed
                retained.append((cycle.state, restored.completion.cycle.state))
                assert all(
                    before == frozen and hash(before) == hash(frozen)
                    for before, frozen in retained
                )
                if vm.halted:
                    assert debugger.halted
                    break
                vm.step()
                debugger.step()


def test_snapshot_definitions_preserve_aliases_and_distinct_nodes(
    monkeypatch,
) -> None:
    from typing import NamedTuple

    from esolangs.runtime._worker_json import worker_dumps, worker_loads

    first = (8,)
    second = tuple(iter(first))
    assert first is not second
    legacy = {"tuple": [{"tuple": [8]}, {"tuple": [8]}]}
    with pytest.raises(ValueError, match="without snapshot definition"):
        _state_from_wire(legacy)
    distinct = _state_from_wire(_state_wire((first, second)))
    assert distinct == (first, second)
    assert distinct[0] is not distinct[1]

    state = (first, (first,), first)
    expected = {
        "define": [
            0,
            {
                "tuple": [
                    {"define": [1, {"tuple": [8]}]},
                    {"define": [2, {"tuple": [{"ref": 1}]}]},
                    {"ref": 1},
                ]
            },
        ]
    }
    wire = worker_dumps(_state_wire(state))
    assert wire == json.dumps(expected)
    restored = _state_from_wire(worker_loads(wire))
    assert restored == state
    assert hash(restored) == hash(state)
    assert restored[0] is restored[1][0] is restored[2]

    class Unowned(NamedTuple):
        value: int

    def refuse_import(_name):
        pytest.fail("unregistered snapshot named a module to import")

    monkeypatch.setattr(_snapshot_wire, "import_module", refuse_import)
    plain = {"define": [0, {"tuple": [8]}]}
    assert _state_wire(Unowned(8)) == plain
    assert type(_state_from_wire(plain)) is tuple
    forged = {
        "define": [0, {"owned": {"module": __name__, "name": "Unowned", "value": 8}}]
    }
    with pytest.raises(ValueError, match="unregistered snapshot codec module"):
        _state_from_wire(forged)


@pytest.mark.parametrize(
    "state",
    [
        {"ref": 0},
        {"ref": True},
        {"ref": -1},
        {"define": [0, 1]},
        {"define": [0, {"ref": 0}]},
        {"define": [False, {"tuple": [1]}]},
        {"define": [1, {"tuple": [1]}]},
        {"define": [0, {"tuple": [{"ref": 0}]}]},
        {"define": [0, {"tuple": [{"ref": 1}, {"define": [1, {"tuple": [1]}]}]}]},
        {
            "define": [
                0,
                {
                    "tuple": [
                        {"define": [1, {"tuple": [1]}]},
                        {"define": [1, {"tuple": [2]}]},
                        {"ref": 1},
                    ]
                },
            ]
        },
        {"define": [0, {"tuple": [{"define": [0, {"tuple": [1]}]}]}]},
        {"define": [0, {"tuple": [{"tuple": [1]}]}]},
    ],
)
def test_snapshot_references_reject_malformed_graphs_and_keep_output(state) -> None:
    with pytest.raises(ValueError, match=r"snapshot (reference|definition)"):
        _state_from_wire(state)
    cycle = BoundaryCycle((1,), 0, 1, 1)
    completed = ExecutionResult(
        "prefix", 0, 0, 0, completion=CompletionReport(Completion.PERIODIC, cycle)
    )
    metadata = encode_result(completed)
    metadata["completion"]["cycle"]["state"] = state
    response = (
        json.dumps({"output": "prefix"})
        + "\n"
        + json.dumps({"result": "prefix", "execution": metadata})
    )
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode(response, expired=False)
    assert caught.value.partial_output == "prefix"


@pytest.mark.medium
def test_immutable_cycle_state_survives_json(interpreter_only_samples):
    def record_at(value, tag="record"):
        pending = [value]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if tag in node:
                    return node[tag]
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
        raise AssertionError("snapshot corpus reached no declared record")

    name = next(
        name
        for name, language in LANGUAGES.items()
        if language.backend is not None
        and getattr(interpreter_module(name), "SNAPSHOT_RECORDS", ())
    )
    program = esolangs.generate(name, "01")
    if isinstance(program, esolangs.TemplateArtifact):
        program = esolangs.instantiate(name, program, [1])
    machine = make_vm(name, program)
    assert not machine.halted
    machine.step()
    state = (
        frozenset({((1, -2), 3), ((4, 5), 6)}),
        b"\x00\xff",
        1 << 15000,
        -(1 << 15000),
        Fraction(2, 3),
        Fraction(-(1 << 15000), 3),
        None,
        True,
        1.5,
        machine.snapshot(),
    )
    result = ExecutionResult(
        "output",
        2,
        1,
        3,
        completion=CompletionReport(Completion.PERIODIC, BoundaryCycle(state, 1, 3, 7)),
    )
    metadata = json.loads(json.dumps(encode_result(result)))
    assert decode_result(result.output, metadata) == result
    assert hash(decode_result(result.output, metadata).completion.cycle.state) == hash(
        state
    )
    zero = replace(
        result,
        completion=CompletionReport(Completion.PERIODIC, BoundaryCycle(state, 0, 1, 0)),
        steps=0,
    )
    assert (
        decode_result(zero.output, json.loads(json.dumps(encode_result(zero)))) == zero
    )

    _assert_catalog_snapshot_round_trips(result, interpreter_only_samples)

    def refuses(broken, match):
        with pytest.raises(ValueError, match=match):
            decode_result(result.output, broken)
        packet = json.dumps({"result": result.output, "execution": broken})
        with pytest.raises(
            esolangs.InterpreterLimitError, match="invalid isolated"
        ) as caught:
            _decode(
                json.dumps({"output": result.output}) + "\n" + packet, expired=False
            )
        assert caught.value.partial_output == result.output

    for field in ("first_pass", "repeat_pass", "commands_per_pass"):
        for invalid in (False, True, 0.0, 1.5, float("nan"), float("inf"), "1", None):
            broken = copy.deepcopy(metadata)
            broken["completion"]["cycle"][field] = invalid
            refuses(broken, "counter")
    for invalid in (float("nan"), float("inf"), float("-inf")):
        cycle = BoundaryCycle((invalid,), 1, 3, 7)
        with pytest.raises(ValueError, match="non-finite"):
            encode_result(
                replace(result, completion=CompletionReport(Completion.PERIODIC, cycle))
            )
        broken = copy.deepcopy(metadata)
        broken["completion"]["cycle"]["state"] = {"define": [0, {"tuple": [invalid]}]}
        refuses(broken, "non-finite")
    for state_tag in (
        *({"bytes": value} for value in ("AA", "aa bb", "00\n")),
        *({"int": value} for value in ("0x01", "0x0_1", "-0x0", "0xA", "0x1 ")),
        *(
            {"define": [0, {"frozenset": value}]}
            for value in ([1, 1], [1, True], [1, 1.0])
        ),
    ):
        broken = copy.deepcopy(metadata)
        broken["completion"]["cycle"]["state"] = state_tag
        refuses(broken, "noncanonical|duplicate")
    for fraction in (
        None,
        [],
        ["0x1"],
        [True, "0x1"],
        ["0x2", "0x4"],
        ["0x1", "0x0"],
        ["0x1", "-0x1"],
    ):
        broken = copy.deepcopy(metadata)
        broken["completion"]["cycle"]["state"] = {"fraction": fraction}
        refuses(broken, "snapshot|integer")
    owned = record_at(metadata, "owned")
    for key in (*owned, "obsolete"):
        broken = copy.deepcopy(metadata)
        changed = record_at(broken, "owned")
        if key == "obsolete":
            changed[key] = True
        else:
            del changed[key]
        refuses(broken, "owned snapshot")
    for key, invalid in (
        ("module", "fractions"),
        ("name", "_Machine"),
        ("value", None),
    ):
        broken = copy.deepcopy(metadata)
        record_at(broken, "owned")[key] = invalid
        refuses(broken, "snapshot|codec")
    record = record_at(metadata)
    for key in (*record, "obsolete"):
        broken = copy.deepcopy(metadata)
        changed = record_at(broken)
        if key == "obsolete":
            changed[key] = True
        else:
            del changed[key]
        refuses(broken, "snapshot record")

    from esolangs.runtime._worker_json import worker_dumps, worker_loads

    for malformed in (
        {"bytes": "AA"},
        {"int": "0xA"},
        {"fraction": ["0x2", "0x4"]},
        {"define": [1100, {"frozenset": [1, True]}]},
        {"define": [1100, {"frozenset": [1, 1.0]}]},
        float("nan"),
        {
            "define": [
                1100,
                {"record": {"module": "fractions", "name": "Fraction", "fields": {}}},
            ]
        },
        {
            "define": [
                1100,
                {"owned": {"module": "fractions", "name": "Fraction", "value": None}},
            ]
        },
    ):
        nested = malformed
        for reference in reversed(range(1100)):
            nested = {"define": [reference, {"tuple": [nested]}]}
        broken = copy.copy(metadata)
        broken["completion"] = copy.copy(metadata["completion"])
        broken["completion"]["cycle"] = copy.copy(metadata["completion"]["cycle"])
        broken["completion"]["cycle"]["state"] = nested
        with pytest.raises(
            ValueError, match=r"noncanonical|duplicate|non-finite|snapshot"
        ):
            decode_result(result.output, broken)
        message = worker_dumps({"result": result.output, "execution": broken})
        stream = worker_dumps({"output": result.output}) + "\n" + message + "\n"
        with pytest.raises(
            esolangs.InterpreterLimitError, match="invalid isolated"
        ) as caught:
            _decode(stream, expired=False)
        assert caught.value.partial_output == result.output
        parsed = worker_loads(message)
        assert type(parsed) is dict


@pytest.mark.parametrize("counter", [-1, True])
@pytest.mark.parametrize("failure", [False, True])
def test_worker_refuses_corrupt_counters_and_retains_output(counter, failure):
    metadata = encode_result(ExecutionResult("prefix", 0, 0, 0))
    metadata["input_reads"] = counter
    message = (
        {
            "error": "HaltError",
            "args": ["bad"],
            "notes": [],
            "cause": None,
            "suppress_context": False,
            "output_limit": False,
        }
        if failure
        else {"result": "prefix"}
    )
    text = (
        json.dumps({"output": "prefix"})
        + "\n"
        + json.dumps({**message, "execution": metadata})
    )
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode(text, expired=False)
    assert caught.value.partial_output == "prefix"


@pytest.mark.parametrize("isolated", [False, True])
def test_step_bound_retains_an_unfinished_observation(isolated):
    with pytest.raises(esolangs.ExecutionCapError) as caught:
        run_observed(REFERENCE, "+[.]", max_steps=4, isolated=isolated)
    assert caught.value.observation == ExecutionResult("\x01", 0, 0, 0, steps=4)
    assert caught.value.partial_output == "\x01"


def test_failed_worker_cannot_claim_completion():
    metadata = encode_result(
        ExecutionResult("", 0, 0, 0, completion=CompletionReport(Completion.HALTED))
    )
    text = json.dumps(
        {
            "error": "HaltError",
            "args": ["bad"],
            "notes": [],
            "cause": None,
            "suppress_context": False,
            "output_limit": False,
            "execution": metadata,
        }
    )
    with pytest.raises(esolangs.InterpreterLimitError, match="invalid isolated"):
        _decode(text, expired=False)


def test_periodic_wire_report_cannot_drop_its_evidence():
    metadata = encode_result(ExecutionResult("", 0, 0, 0))
    metadata["completion"] = {"kind": "periodic", "cycle": None}
    with pytest.raises(ValueError, match="requires cycle"):
        decode_result("", metadata)


def test_worker_refuses_partial_counters_and_wrong_periodic_steps() -> None:
    cycle = BoundaryCycle((0,), 0, 2, 6)
    completion = CompletionReport(Completion.PERIODIC, cycle)
    result = ExecutionResult("X", 0, 1, 0, completion=completion, steps=12)
    metadata = encode_result(result)
    assert decode_result(result.output, metadata) == result
    for corrupted in ({"input_reads": None}, {"steps": 1}):
        with pytest.raises(ValueError, match=r"counters|steps disagree"):
            decode_result(result.output, {**metadata, **corrupted})


def test_large_worker_counters_keep_completion_proof_and_failure() -> None:
    from esolangs.runtime._failure_wire import _failure_wire
    from esolangs.runtime._worker_json import worker_dumps

    count = 1 << 18000
    cycle = BoundaryCycle((count,), count - 1, count, 1)
    finished = ExecutionResult(
        "",
        count,
        count,
        0,
        completion=CompletionReport(Completion.PERIODIC, cycle),
        steps=count,
    )
    metadata = encode_result(finished)
    packet = worker_dumps({"result": "", "execution": metadata})
    assert _decode(packet, expired=False) == finished

    proof = CycleDecision(halts=False, commands=count, cycle=cycle)
    live = replace(finished, completion=None)
    packet = worker_dumps(
        {
            "result": "",
            "execution": encode_result(live),
            "termination": encode_decision(proof),
        }
    )
    decoded = _decode(packet, expired=False)
    assert decoded.observation == live
    assert decoded.decision == proof

    failure = esolangs.InputExhaustedError(count, count, unit="character")
    failure.observation = replace(live, input_past_end=1)
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        _decode(worker_dumps(_failure_wire(failure)), expired=False)
    assert (caught.value.reads, caught.value.supplied, caught.value.unit) == (
        count,
        count,
        "character",
    )
    assert caught.value.observation == failure.observation


def test_worker_integer_tag_is_lossless_and_canonical() -> None:
    from esolangs.runtime._worker_json import worker_dumps, worker_loads

    number = 1 << 18000
    literal = {"$python_integer": hex(number)}
    payload = {"values": [number, -number, True, 3], "literal": literal}
    assert worker_loads(worker_dumps(payload)) == payload
    assert worker_loads(json.dumps(literal)) == number
    for value in (None, 1, "0x1", "0X12", "-0x0", "0x0" + hex(number)[2:]):
        with pytest.raises(ValueError, match="worker integer"):
            worker_loads(json.dumps({"$python_integer": value}))


@pytest.mark.parametrize("termination", [None, CycleDecision(halts=True, commands=0)])
def test_successful_workers_must_report_known_input_counters(termination) -> None:
    from esolangs.runtime._worker_response import _decode_outcome

    report = CompletionReport(Completion.HALTED) if termination is None else None
    unknown = ExecutionResult("prefix", None, None, None, completion=report)
    packet = {"result": "prefix", "execution": encode_result(unknown)}
    if termination is not None:
        packet["termination"] = encode_decision(termination)
    prefix = '{"output":"prefix"}\n'
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode(prefix + json.dumps(packet), expired=False)
    assert caught.value.partial_output == "prefix"
    assert caught.value.observation is None
    known = replace(unknown, input_position=0, input_reads=0, input_past_end=0)
    packet["execution"] = encode_result(known)
    assert (
        _decode_outcome(prefix + json.dumps(packet), expired=False).observation == known
    )


def test_worker_budget_errors_preserve_the_named_bound() -> None:
    from esolangs.runtime import _worker_response

    unknown = esolangs.ExecutionBudgetError("no phase declared")
    assert (
        _worker_response._decode_outcome(
            json.dumps(_failure_wire(unknown)), expired=False
        ).bound
        is None
    )
    for error, bound in (
        (esolangs.ExecutionBudgetError("budget expired"), "max_steps"),
        (esolangs.ExecutionTimeoutError("preparation expired"), "preparation_timeout"),
    ):
        error.bound = bound
        outcome = _worker_response._decode_outcome(
            json.dumps(_failure_wire(error)), expired=False
        )
        assert type(outcome.error) is type(error)
        assert outcome.bound == bound


def test_normal_worker_cannot_omit_result_metadata(monkeypatch):
    from esolangs.runtime import _isolated

    monkeypatch.setattr(
        _isolated,
        "_launch",
        lambda *_args, **_kwargs: ExecutionResult("prefix", 0, 0, 0),
    )
    with pytest.raises(
        esolangs.InterpreterLimitError, match="omitted execution"
    ) as caught:
        _isolated.execute_isolated(REFERENCE, "+.").unwrap()
    assert caught.value.partial_output == "prefix"


@pytest.mark.parametrize(
    "language", [name for name, lang in LANGUAGES.items() if lang.runtime.random]
)
def test_seeded_worker_result_matches_native(language):
    template = esolangs.generate(language, "01")
    parameterized = LANGUAGES[language].parameterized
    source = (
        esolangs.instantiate(language, template, [1]) if parameterized else template
    )
    stdin = "" if parameterized else esolangs.encode_inputs(language, [1])
    native = run_observed(language, source, stdin=stdin, seed=7)
    worker = run_observed(
        language,
        source,
        stdin=stdin,
        seed=7,
        isolated=True,
        timeout=5,
        max_output=len(native.output),
    )
    assert worker == native
    assert esolangs.read_answer(language, worker.output) == "1"


@pytest.mark.parametrize("failure", [False, True])
def test_missing_worker_observations_are_rejected_with_the_prefix(failure):
    result = (
        {
            "error": "HaltError",
            "args": ["bad"],
            "notes": [],
            "cause": None,
            "suppress_context": False,
            "output_limit": False,
        }
        if failure
        else {"result": "prefix"}
    )
    text = json.dumps({"output": "prefix"}) + "\n" + json.dumps(result)
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode(text, expired=False)
    assert caught.value.partial_output == "prefix"
    if not failure:
        execution = encode_result(
            ExecutionResult(
                "prefix", 0, 0, 0, completion=CompletionReport(Completion.HALTED)
            )
        )
        success = {"result": "prefix", "execution": execution}
        streamed = json.dumps({"output": "prefix"}) + "\n"
        assert _decode(streamed + json.dumps(success), expired=False).output == "prefix"
        for malformed in (
            streamed + json.dumps({**success, "obsolete": True}),
            streamed + json.dumps({**success, "result": "different"}),
            streamed + json.dumps(success) + "\n" + json.dumps(success),
            streamed + json.dumps(success) + '\n{"output":"late"}',
            streamed + '{"output":"extra","obsolete":true}',
            streamed + '{"output":3}',
            streamed + json.dumps(success) + "\n{",
            streamed + "null",
            streamed + "[]",
            streamed + '{"output":"hidden","output":"prefix"}',
            streamed
            + json.dumps(success).replace(
                '"result":', '"result":"hidden","result":', 1
            ),
            streamed
            + json.dumps(success).replace(
                '"result":', r'"\u0072esult":"hidden","result":', 1
            ),
            streamed
            + json.dumps(success).replace('"steps": null', '"steps":0,"steps":null'),
            streamed
            + json.dumps(success).replace(
                '"kind": "halted"', '"kind":"periodic","kind":"halted"'
            ),
        ):
            with pytest.raises(
                esolangs.InterpreterLimitError, match="invalid isolated"
            ) as invalid:
                _decode(malformed, expired=False)
            assert invalid.value.partial_output == "prefix"


def test_worker_requires_the_complete_request(monkeypatch, capsys):
    import io
    import sys

    from esolangs.registry import SourceKind

    _check_request_serialization(monkeypatch)
    _check_raster_acquisition_deadline(monkeypatch)

    def serve(value):
        document = json.dumps(value) if isinstance(value, dict) else value
        monkeypatch.setattr(sys, "stdin", io.StringIO(document))
        _worker()
        return json.loads(capsys.readouterr().out.splitlines()[-1])["result"]

    request = encode_request(REFERENCE, "", "")
    for key in (*request, "obsolete"):
        broken = (
            {**request, "obsolete": None}
            if key == "obsolete"
            else {k: value for k, value in request.items() if k != key}
        )
        with pytest.raises(ValueError, match="invalid worker request fields"):
            serve(broken)
    encoded = json.dumps(request)
    for malformed in (
        encoded.replace('"language":', '"language":"ignored","language":', 1),
        json.dumps({**request, "settings": {"key": 1}}).replace(
            '"key": 1', '"key":1,"key":2'
        ),
    ):
        assert malformed != encoded
        with pytest.raises(ValueError, match="duplicate field"):
            serve(malformed)
    for source in (",.", esolangs.CompressedText.from_chunks((",.",))):
        valid = encode_request(REFERENCE, source, "A", max_steps=2, max_output=1)
        assert serve(valid) == "A"
    empty = encode_request(REFERENCE, esolangs.CompressedText.from_chunks(("",)), "")
    assert serve(empty) == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({**empty, "program": ""})))
    _worker()
    reply = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert reply["error"] == "ProgramError"
    assert reply["execution"] is None
    with pytest.raises(esolangs.ProgramError, match="no gzip member"):
        _decode(json.dumps(reply), expired=False)
    huge = 1 << 15000
    for predicate in (
        lambda lang: lang.runtime.random,
        lambda lang: lang.runtime.source_kind is SourceKind.RASTER,
    ):
        language = next(
            lang
            for lang in LANGUAGES.values()
            if lang.backend and not lang.parameterized and predicate(lang)
        )
        name = language.name
        valid = encode_request(
            name,
            esolangs.generate(name, "01").source,
            esolangs.encode_inputs(name, [1]),
            seed=-huge if language.runtime.random else None,
            max_steps=huge,
            max_output=huge,
        )
        assert esolangs.read_answer(name, serve(valid)) == "1"
    raster = valid
    invalid = {
        **{
            key: (0, 1, "", "false", None)
            for key, value in request.items()
            if type(value) is bool
        },
        **dict.fromkeys(("seed", "max_output", "max_steps"), (0, 1, "0x1")),
        "scale": (False, 0, -1, 1.0, "0x0", "-0x1", "0x01"),
        "max_memory": (False, 0, -1, 1.0),
        "language": (0,),
        "stdin": ([],),
        "program": ([],),
        "settings": ([],),
        "integer_settings": ({}, [1], ["missing"]),
    }
    patches = [{key: value} for key, values in invalid.items() for value in values]
    patches += [
        {"raster": True, "compressed": True},
        {"settings": {"cell_modulus": 256}},
        {
            "settings": {"cell_modulus": "0x100"},
            "integer_settings": ["cell_modulus", "cell_modulus"],
        },
        {"settings": {"cell_modulus": "256"}, "integer_settings": ["cell_modulus"]},
        *(
            {"settings": {"cell_modulus": value}, "integer_settings": ["cell_modulus"]}
            for value in ("0x0100", "0x1_00", "0x100 ")
        ),
        *(
            {key: value, f"integer_{key}": True}
            for key in ("seed", "max_output", "max_steps")
            for value in (None, 0, "1", "0x!", "0x01", "0x0_1", "-0x0", "0xA", "0x1 ")
        ),
        *({key: "-0x1", f"integer_{key}": True} for key in ("max_output", "max_steps")),
    ]
    for patch in patches:
        with pytest.raises(ValueError, match=r"worker|invalid literal"):
            serve({**request, **patch})
        assert capsys.readouterr().out == ""
    for runs in (
        {},
        [0],
        [[1, {}]],
        *([[count, []]] for count in (True, 0, -1)),
        [[1, [0]]],
        *([[1, [[count, [0, 0, 0]]]]] for count in (False, 0)),
        *(
            [[1, [[1, pixel]]]]
            for pixel in ([0, 0], [0, 0, 0, 0], [False, 0, 0], [256, 0, 0])
        ),
    ):
        with pytest.raises(ValueError, match="invalid worker raster"):
            serve({**raster, "program": runs})
        assert capsys.readouterr().out == ""


def _check_request_serialization(monkeypatch) -> None:
    from time import monotonic

    from esolangs.runtime import _isolated, _worker_json

    with monkeypatch.context() as patch:
        patch.setattr(_worker_json, "_WORKER_TEXT_BLOCK", 8)
        patch.setattr(_worker_json, "_WORKER_REQUEST_BLOCK", 128)
        source = esolangs.CompressedText.from_chunks(
            ("".join(map(chr, range(65, 126))),)
        )
        stdin = ('é\ud800\U000103ff\r\\"' * 64) + "a"
        plain = encode_request(REFERENCE, source, stdin)
        packed = encode_request(REFERENCE, source, stdin, chunked=True)
        parts = _worker_json.worker_request(packed, lambda: False)
        assert isinstance(parts, list)
        assert max(map(len, parts)) <= 128
        assert "".join(parts) == _worker_json.worker_dumps(plain)
        assert _worker_json.worker_loads("".join(parts)) == plain

        chunks = []
        encode = _worker_json.b64encode

        def stop_after_base64(block):
            chunks.append(block)
            return encode(block)

        patch.setattr(_worker_json, "b64encode", stop_after_base64)
        assert _worker_json.worker_request(packed, lambda: bool(chunks)) is None
        assert chunks == [source.to_gzip()[:24]]

    with monkeypatch.context() as patch:
        payload = "é" * 64
        clock = [monotonic()]
        chunks = []
        dumps = _worker_json.json.dumps

        def stop_after_escape(value):
            if isinstance(value, str) and value.startswith("é"):
                chunks.append(value)
                clock[0] += 2
            return dumps(value)

        def no_launch(*_args, **_kwargs):
            pytest.fail("expired request serialization launched a worker")

        patch.setattr(_worker_json, "_WORKER_TEXT_BLOCK", 8)
        patch.setattr(_worker_json.json, "dumps", stop_after_escape)
        patch.setattr(_isolated, "monotonic", lambda: clock[0])
        patch.setattr(_isolated, "_launch", no_launch)
        outcome = esolangs.run(
            REFERENCE,
            ",.",
            stdin=payload,
            limits=esolangs.ExecutionLimits(preparation_timeout=1, max_steps=2),
        )
        assert outcome.bound == "preparation_timeout"
        assert outcome.observation == ExecutionResult("", None, None, None)
        assert chunks == [payload[:8]]


def _check_raster_acquisition_deadline(monkeypatch) -> None:
    from io import StringIO
    from threading import Thread
    from time import monotonic

    from esolangs.raster import lazy_raster
    from esolangs.registry import SourceKind
    from esolangs.runtime import _acquire, _files, _isolated, _raster_wire

    spec = next(
        language
        for language in LANGUAGES.values()
        if language.runtime.source_kind is SourceKind.RASTER and language.backend
    )
    api = esolangs.Language(spec.name)
    artifact = api.generate("01")
    rows = artifact.source.rows
    clock = [monotonic()]
    threads = []
    blocks = []
    encode = _raster_wire._pixel_groups

    def spawn(*args, **kwargs):
        thread = Thread(*args, **kwargs)
        threads.append(thread)
        return thread

    def no_launch(*_args, **_kwargs):
        pytest.fail("expired raster acquisition launched a worker")

    def slow_render():
        clock[0] += 2
        return rows

    def slow_encode(row):
        blocks.append(row)
        clock[0] += 2
        yield from encode(row)

    # The same cutoff applies before consuming stdin at either raster stage.
    lazy = lazy_raster(slow_render)
    solid = esolangs.Raster((((255, 0, 0),) * 9,))
    with monkeypatch.context() as patch:
        patch.setattr(_acquire, "Thread", spawn)
        patch.setattr(_files, "monotonic", lambda: clock[0])
        patch.setattr(_isolated, "monotonic", lambda: clock[0])
        patch.setattr(_isolated, "_launch", no_launch)
        patch.setattr(_raster_wire, "_BLOCK", 2)
        patch.setattr(_raster_wire, "_pixel_groups", slow_encode)
        limits = esolangs.ExecutionLimits(preparation_timeout=1, max_steps=2)
        for image in (lazy, solid):
            stdin = StringIO("1")
            try:
                outcome = api.run(image, stdin=stdin, limits=limits)
            finally:
                for thread in threads:
                    thread.join(2)
                    assert not thread.is_alive()
                threads.clear()
            assert outcome.bound == "preparation_timeout"
            assert outcome.observation == ExecutionResult("", None, None, None)
            assert stdin.tell() == 0
        assert repr(lazy) == "Raster(unrendered)"
        assert blocks == [solid.rows[0][:2]]


def test_worker_error_requires_explicit_unavailable_observation_and_options():
    payload = {
        "error": "ExecutionCapError",
        "args": ["stopped"],
        "execution": None,
        "notes": ["row 1"],
        "cause": None,
        "suppress_context": False,
        "output_limit": False,
        "bound": "max_steps",
    }
    with pytest.raises(esolangs.ExecutionCapError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.bound == "max_steps"
    assert caught.value.__notes__ == ["row 1"]
    assert caught.value.observation is None
    for notes in (None, []):
        with pytest.raises(esolangs.ExecutionCapError) as caught:
            _decode(json.dumps({**payload, "notes": notes}), expired=False)
        assert getattr(caught.value, "__notes__", None) == notes
        assert hasattr(caught.value, "__notes__") == (notes is not None)
    for key in (
        "execution",
        "notes",
        "cause",
        "suppress_context",
        "output_limit",
        "bound",
        "obsolete",
    ):
        with pytest.raises(esolangs.InterpreterLimitError, match="invalid isolated"):
            _decode(
                json.dumps(
                    {**payload, "obsolete": None}
                    if key == "obsolete"
                    else {k: v for k, v in payload.items() if k != key}
                ),
                expired=False,
            )
    for field, value in (
        ("error", "ObsoleteError"),
        ("error", "__name__"),
        ("args", "deadline"),
        ("notes", "row 1"),
        ("notes", [1]),
        ("cause", ["ValueError"]),
        (
            "cause",
            [
                {
                    "kind": "os.system",
                    "args": [],
                    "notes": None,
                    "suppress_context": False,
                }
            ],
        ),
        ("suppress_context", 1),
        ("bound", "unknown"),
        ("output_limit", 1),
        ("output_limit", True),
    ):
        with pytest.raises(esolangs.InterpreterLimitError, match="invalid isolated"):
            _decode(json.dumps({**payload, field: value}), expired=False)
    for kind, valid, malformed in (
        (
            "InterpreterLimitError",
            ["other limit"],
            [],
        ),
        (
            "UnknownLanguageError",
            ["missing", ["Brainfuck"]],
            [[], ["missing"], [3, []], ["missing", [3]], ["missing", [], "extra"]],
        ),
        (
            "InputExhaustedError",
            [0, 0, "line"],
            [
                [],
                [0, 0],
                [-1, 0, "line"],
                [True, 0, "line"],
                [0, 0, 3],
                [0, 0, "line", "extra"],
            ],
        ),
    ):
        envelope = {key: value for key, value in payload.items() if key != "bound"}
        envelope.update(error=kind, args=valid)
        with pytest.raises(getattr(esolangs, kind)) as caught:
            _decode(json.dumps(envelope), expired=False)
        assert caught.value.__notes__ == ["row 1"]
        for args in malformed:
            with pytest.raises(
                esolangs.InterpreterLimitError, match="invalid isolated"
            ):
                _decode(json.dumps({**envelope, "args": args}), expired=False)
    cap = {**payload, "error": "ExecutionCapError", "bound": "max_memory"}
    with pytest.raises(esolangs.ExecutionCapError) as capped:
        _decode(json.dumps(cap), expired=False)
    assert capped.value.bound == "max_memory"
    # The bound must agree with the output marker, and be a cap's.
    for change in (
        {"bound": "max_output"},
        {"bound": "execution_timeout"},
        {"args": ["isolated output limit exceeded"]},
    ):
        with pytest.raises(esolangs.InterpreterLimitError, match="invalid isolated"):
            _decode(json.dumps({**cap, **change}), expired=False)
    _check_worker_explicit_causes()


def _check_worker_explicit_causes() -> None:
    from esolangs.runtime._failure_wire import _failure_wire
    from esolangs.runtime._worker_json import worker_dumps

    causes = (
        ValueError(1),
        ValueError("x" * 70_000, 1 << 600),
        ZeroDivisionError(),
        OverflowError(34, "Result too large"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        UnicodeEncodeError("latin-1", "😀", 0, 1, "ordinal not in range"),
        DivisionByZero([DivisionByZero]),
    )
    for inner in causes:
        inner.add_note("inner note")
        middle = ValueError("nested parse error")
        middle.__cause__ = inner
        outer = esolangs.HaltError("top-level error")
        outer.__cause__ = middle
        outer.__suppress_context__ = False
        with pytest.raises(esolangs.HaltError, match="top-level error") as caught:
            _decode(worker_dumps(_failure_wire(outer)), expired=False)
        assert not caught.value.__suppress_context__
        received = caught.value.__cause__
        assert type(received) is ValueError
        assert received.args == middle.args
        assert received.__suppress_context__
        restored = received.__cause__
        assert type(restored) is type(inner)
        assert restored.args == inner.args
        assert restored.__notes__ == ["inner note"]

    unsupported = esolangs.HaltError("unsupported inner error")
    unsupported.__cause__ = RuntimeWarning("unsupported cause class")
    with pytest.raises(esolangs.HaltError, match="unsupported inner error") as caught:
        _decode(worker_dumps(_failure_wire(unsupported)), expired=False)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__

    cycle = ValueError("cyclic cause")
    cycle.__cause__ = cycle
    outer = esolangs.HaltError("cyclic inner error")
    outer.__cause__ = cycle
    with pytest.raises(esolangs.HaltError, match="cyclic inner error") as caught:
        _decode(worker_dumps(_failure_wire(outer)), expired=False)
    restored = caught.value.__cause__
    assert type(restored) is ValueError
    assert restored.args == cycle.args
    assert restored.__cause__ is None
