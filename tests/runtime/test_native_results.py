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


@pytest.mark.parametrize("language", LANGUAGES)
def test_native_driver_reports_completion(language):
    lang = LANGUAGES[language]
    if lang.backend is None:
        source, stdin = SAMPLES[language]
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
            esolangs.instantiate(language, template, bits)
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
        "seed": 7 if LANGUAGES[language].runtime.random else None,
    }
    result = esolangs.run(language, source, **options)
    with guarded_worker():
        assert esolangs.run(language, source, isolated=True, **options) == result
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
    reason = debugger.run(max_steps=1)
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
                    )
                    == expected
                )
            else:
                with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
                    esolangs.run(
                        language,
                        source,
                        limits=esolangs.ExecutionLimits(max_steps=1),
                        isolated=isolated,
                        **options,
                    )
                assert caught.value.bound == "max_steps"
                assert caught.value.observation == expected
                assert expected.completion is None
                assert caught.value.partial_output == expected.output
