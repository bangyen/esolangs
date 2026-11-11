"""The 2.0 defaults retain artifacts and execution observations."""

import inspect

import pytest

import esolangs
from esolangs.generation import wrap
from esolangs.registry import LANGUAGES
from tests.support.evaluation import _evaluate
from tests.support.pick import languages


@pytest.mark.medium
@pytest.mark.parametrize("language", languages(boolean_generator=True))
def test_default_records_execute_and_round_trip(language, monkeypatch):
    bound = esolangs.Language(language)
    backend = LANGUAGES[bound.name].backend
    targets = {id(backend.entrypoint), id(backend.generate)}
    if backend.balance is not None:
        targets.add(id(backend.balance))
    original = inspect.signature

    def forbidden(target, *args, **kwargs):
        if id(target) in targets:
            raise AssertionError("generator signature discovery reached")
        return original(target, *args, **kwargs)

    monkeypatch.setattr(inspect, "signature", forbidden)
    with pytest.raises(AssertionError, match="signature discovery"):
        inspect.signature(backend.entrypoint)
    assert not hasattr(wrap, "takes_width")
    assert not hasattr(esolangs, "_takes_width")
    for options in ({}, {"width": 1}, {"balance": True}):
        program = esolangs.generate(language, "01", **options)
        assert isinstance(
            program, (esolangs.ProgramArtifact, esolangs.TemplateArtifact)
        )
        assert program.language == bound.name
        document = esolangs.dump_program(language, program)
        restored = esolangs.load_program(language, document)
        assert type(restored) is type(program)
        assert esolangs.dump_program(language, restored) == document
        assert _evaluate(language, restored, inputs=1) == "01"
        if not options:
            for bit in (0, 1):
                result = bound.evaluate(restored, [bit])
                assert result.bit == str(bit)
                if bound.describe()["answer_mode"] == "termination":
                    assert result.termination is not None
                else:
                    assert result.observation.completion is not None
                if isinstance(restored, esolangs.TemplateArtifact):
                    assert result.observation.input_position == 0
                else:
                    assert result.observation.input_position > 0
        if isinstance(restored, esolangs.TemplateArtifact):
            with pytest.raises(esolangs.TemplateError):
                bound.run(restored, max_steps=10)
            filled = bound.instantiate(restored, [0])
            assert isinstance(filled, esolangs.ProgramArtifact)
            assert filled.language == language
        else:
            assert bound.load_program(document) == restored
            if not options:
                with pytest.raises(esolangs.ArgumentError, match="expects 1 bits"):
                    restored.evaluate([0, 1])
