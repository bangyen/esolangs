"""The 2.0 defaults retain artifacts and execution observations."""

import inspect

import pytest

import esolangs
from esolangs.generation import wrap
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from tests.support.evaluation import _evaluate
from tests.support.generator_support import assert_saved_rows
from tests.support.pick import languages


@pytest.mark.medium
@pytest.mark.parametrize("language", languages(boolean_generator=True))
def test_default_records_execute_and_round_trip(language, monkeypatch):
    bound = esolangs.Language(language)
    declaration = LANGUAGES[bound.name]
    backend = declaration.backend
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
    if bound.describe()["parameterized"]:

        def rediscovered(*_args):
            raise AssertionError("catalog generation rediscovered input slots")

        monkeypatch.setattr("esolangs.artifacts.runs", rediscovered)
    controls = load_certification(declaration).benchmark_tables
    # The three coordinates have distinct effects. A language with a proved
    # cap supplies its own admitted benchmark controls.
    table = max(controls, key=len) if controls else "00110110"
    for options in ({}, {"width": 1}, {"balance": True}):
        assert_saved_rows(
            bound, bound.generate(table, **options), table, range(len(table))
        )
        for bit in "01":
            constant = bit * len(table)
            assert_saved_rows(
                bound,
                bound.generate(constant, **options),
                constant,
                (0, len(constant) - 1),
            )
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
