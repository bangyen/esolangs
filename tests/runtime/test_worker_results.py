"""Worker results retain counters and immutable periodic evidence."""

import copy
import json

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.results import ExecutionResult
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime._isolated import _decode
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._result_wire import decode_result, encode_result
from esolangs.vm import make_vm
from tests.support.reference import REFERENCE


def test_immutable_cycle_state_survives_json():
    def record_at(value):
        pending = [value]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if "record" in node:
                    return node["record"]
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
    zero = result._replace(
        completion=CompletionReport(Completion.PERIODIC, BoundaryCycle(state, 0, 1, 0)),
        steps=0,
    )
    assert (
        decode_result(zero.output, json.loads(json.dumps(encode_result(zero)))) == zero
    )

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
                result._replace(completion=CompletionReport(Completion.PERIODIC, cycle))
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
    record = record_at(metadata)
    for key in (*record, "obsolete"):
        broken = copy.deepcopy(metadata)
        changed = record_at(broken)
        if key == "obsolete":
            changed[key] = True
        else:
            del changed[key]
        refuses(broken, "snapshot record")


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
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs._run_result(REFERENCE, "+[.]", max_steps=4, isolated=isolated)
    assert caught.value.execution == ExecutionResult("\x01", 0, 0, 0, steps=4)
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
        _isolated.run_isolated_result(REFERENCE, "+.")
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
    native = esolangs._run_result(language, source, stdin=stdin, seed=7)
    worker = esolangs._run_result(
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
        "error": "ExecutionTimeoutError",
        "args": ["deadline"],
        "execution": None,
        "notes": ["row 1"],
        "output_limit": False,
        "bound": "max_steps",
    }
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.bound == "max_steps"
    assert caught.value.__notes__ == ["row 1"]
    assert caught.value.execution is None
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
    ):
        with pytest.raises(esolangs.InterpreterLimitError, match="invalid isolated"):
            _decode(json.dumps({**payload, field: value}), expired=False)
    for kind, valid, malformed in (
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
        with pytest.raises(getattr(esolangs, kind)):
            _decode(json.dumps(envelope), expired=False)
        for args in malformed:
            with pytest.raises(
                esolangs.InterpreterLimitError, match="invalid isolated"
            ):
                _decode(json.dumps({**envelope, "args": args}), expired=False)
