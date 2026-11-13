"""Worker results retain counters and immutable periodic evidence."""

import copy
import json
from dataclasses import replace
from fractions import Fraction

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES
from esolangs.results import ExecutionResult
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._result_wire import decode_result, encode_result
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
        CompletionReport(Completion.PERIODIC, BoundaryCycle(state, 1, 3, 7)),
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
        broken["completion"]["cycle"]["state"] = {"tuple": [invalid]}
        refuses(broken, "non-finite")
    for state_tag in (
        *({"bytes": value} for value in ("AA", "aa bb", "00\n")),
        *({"int": value} for value in ("0x01", "0x0_1", "-0x0", "0xA", "0x1 ")),
        *({"frozenset": value} for value in ([1, 1], [1, True], [1, 1.0])),
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
        ("value", {"tuple": []}),
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

    from esolangs.runtime._json import worker_dumps, worker_loads

    for malformed in (
        {"bytes": "AA"},
        {"int": "0xA"},
        {"fraction": ["0x2", "0x4"]},
        {"frozenset": [1, True]},
        {"frozenset": [1, 1.0]},
        float("nan"),
        {"record": {"module": "fractions", "name": "Fraction", "fields": {}}},
        {"owned": {"module": "fractions", "name": "Fraction", "value": {"tuple": []}}},
    ):
        nested = malformed
        for _ in range(1100):
            nested = {"tuple": [nested]}
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
        {"error": "HaltError", "args": ["bad"], "notes": [], "output_limit": False}
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
        ExecutionResult("", 0, 0, 0, CompletionReport(Completion.HALTED))
    )
    text = json.dumps(
        {
            "error": "HaltError",
            "args": ["bad"],
            "notes": [],
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
        {"error": "HaltError", "args": ["bad"], "notes": [], "output_limit": False}
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
            ExecutionResult("prefix", 0, 0, 0, CompletionReport(Completion.HALTED))
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
    from esolangs.runtime import _isolated

    def serve(value):
        document = json.dumps(value) if isinstance(value, dict) else value
        monkeypatch.setattr(sys, "stdin", io.StringIO(document))
        _isolated._worker()
        return json.loads(capsys.readouterr().out.splitlines()[-1])["result"]

    request = _isolated._request_wire(REFERENCE, "", "")
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
        valid = _isolated._request_wire(
            REFERENCE, source, "A", max_steps=2, max_output=1
        )
        assert serve(valid) == "A"
    empty = _isolated._request_wire(
        REFERENCE, esolangs.CompressedText.from_chunks(("",)), ""
    )
    assert serve(empty) == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({**empty, "program": ""})))
    _isolated._worker()
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
        valid = _isolated._request_wire(
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
        **dict.fromkeys(("scale", "max_memory"), (False, 0, -1, 1.0)),
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


def test_worker_error_requires_explicit_unavailable_observation_and_options():
    payload = {
        "error": "ExecutionCapError",
        "args": ["stopped"],
        "execution": None,
        "notes": ["row 1"],
        "output_limit": False,
        "bound": "max_steps",
    }
    with pytest.raises(esolangs.ExecutionCapError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.bound == "max_steps"
    assert caught.value.__notes__ == ["row 1"]
    assert caught.value.observation is None
    for key in ("execution", "notes", "output_limit", "bound", "obsolete"):
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
