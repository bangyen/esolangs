"""Every native driver and worker retain the declared completion report."""

from contextlib import nullcontext

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion, CompletionReport
from tests.support.certification_barrier import guarded_worker
from tests.support.generator_support import probe_table
from tests.support.samples import SAMPLES


def _check_completion_worker(language, source, options, expected) -> None:
    with guarded_worker():
        assert (
            esolangs.run(language, source, isolated=True, **options).unwrap()
            == expected
        )


@pytest.mark.parametrize("language", LANGUAGES)
def test_native_driver_reports_completion(language):
    lang = LANGUAGES[language]
    sample, sample_stdin = SAMPLES[language]
    if lang.backend is None:
        source, stdin = sample, sample_stdin
    else:
        table = (
            "00"
            if lang.contract.answer_mode == "termination"
            else probe_table(language, "01")
        )
        row = (
            table.index("0")
            if lang.contract.answer_mode == "termination"
            else table.index("1")
        )
        n = len(table).bit_length() - 1
        bits = [int(char) for char in f"{row:0{n}b}"]
        template = esolangs.generate(language, table)
        source = (
            esolangs.Language(language).instantiate(template, bits)
            if lang.parameterized
            else template
        )
        stdin = (
            ""
            if lang.parameterized
            else esolangs.encode_inputs(language, bits, truth_table=table)
        )
    options = {
        "stdin": stdin,
        "seed": 7 if lang.runtime.random else None,
    }
    result = esolangs.run(language, source, **options).unwrap()
    _check_completion_worker(language, source, options, result)
    caps = lang.runtime.capabilities
    if (
        caps is not None
        and caps.completion is Completion.HALTED
        and caps.self_halts
        and isinstance(source, esolangs.ProgramArtifact)
        and (
            # Ordinary text reaches the same worker route in either form.
            # Retain distinct wire encodings and raw calls with other options.
            not isinstance(sample, str)
            or not isinstance(source.source, str)
            or source.settings is not None
            or source.scale is not None
            or lang.runtime.random
        )
    ):
        raw_options = {
            "stdin": sample_stdin,
            "seed": lang.runtime.reproducible_seed if lang.runtime.random else None,
        }
        native_sample = esolangs.run(language, sample, **raw_options).unwrap()
        assert native_sample.completion.kind is Completion.HALTED
        _check_completion_worker(language, sample, raw_options, native_sample)
    assert isinstance(result.completion, CompletionReport)
    if result.completion.kind is Completion.PERIODIC:
        assert result.completion.cycle is not None
    else:
        expected = (
            Completion.POST_HALT
            if esolangs.describe(language).dumps_on_the_post_halt_step
            else Completion.HALTED
        )
        assert result.completion.kind is expected

    debugger = make_debugger(language, source, **options)
    reason = debugger.run(limits=esolangs.ExecutionLimits(max_steps=1))
    expected = debugger.observation
    for isolated in (False, True):
        with guarded_worker() if isolated else nullcontext():
            if reason == "halted":
                assert (
                    esolangs.run(
                        language,
                        source,
                        limits=esolangs.ExecutionLimits(max_steps=1),
                        isolated=isolated,
                        **options,
                    ).unwrap()
                    == expected
                )
            else:
                with pytest.raises(esolangs.ExecutionCapError) as caught:
                    esolangs.run(
                        language,
                        source,
                        limits=esolangs.ExecutionLimits(max_steps=1),
                        isolated=isolated,
                        **options,
                    ).unwrap()
                assert caught.value.bound == "max_steps"
                assert caught.value.observation == expected
                assert expected.completion is None
                assert caught.value.partial_output == expected.output
