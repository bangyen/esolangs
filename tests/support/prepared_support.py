"""Check retained parse reuse without sharing invocation state."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.vm import complete_vm


def check_image_reuse(
    language,
    code,
    module,
    parser_name,
    monkeypatch,
    *,
    cases=(("A", "A"), ("Z", "Z"), ("Q", "Q")),
    settings=None,
):
    calls = []
    parse = getattr(module, parser_name)

    def counted(source, **options):
        calls.append(source)
        return parse(source, **options)

    with monkeypatch.context() as patch:
        patch.setattr(module, parser_name, counted)
        api = esolangs.Language(language)
        runtime = api.catalog.languages[api.name].runtime
        source = code.splitlines() if runtime.split else code
        prepared = api.prepare(code, settings=settings)
        assert calls == [source]
        (first_in, first_out), (second_in, second_out), (third_in, third_out) = cases
        first, second = (
            prepared.make_vm(stdin=first_in),
            prepared.make_vm(stdin=second_in),
        )
        before = second.snapshot()
        first.step()
        assert second.snapshot() == before
        assert complete_vm(first) == first_out
        assert complete_vm(second) == second_out
        assert prepared.run(stdin=first_in).unwrap().output == first_out
        assert (
            prepared.run(
                stdin=second_in, limits=esolangs.ExecutionLimits(max_steps=100)
            )
            .unwrap()
            .output
            == second_out
        )
        assert prepared.run(stdin=third_in).unwrap().output == third_out
        assert calls == [source]


def check_random_plan_reuse(language, code, module, parser_name, monkeypatch):
    """Reuse a finite witness while each invocation owns its random draws."""
    from esolangs.runtime import _prepared as preparation
    from esolangs.runtime import randomness

    api = esolangs.Language(language)
    default_seed = api.catalog.languages[api.name].runtime.reproducible_seed
    default_output = api.run(code, seed=default_seed).unwrap().output
    expected = {seed: api.run(code, seed=seed).unwrap() for seed in range(16)}
    assert len({result.output for result in expected.values()}) > 1
    calls = []
    parse = getattr(module, parser_name)

    def counted(source):
        calls.append(source)
        return parse(source)

    shape_calls = []
    shape = preparation.prepare_call

    def counted_shape(name, source, context, **options):
        shaped, runtime_options = shape(name, source, context, **options)
        shape_calls.append(shaped)
        return shaped, runtime_options

    with monkeypatch.context() as patch:
        patch.setattr(module, parser_name, counted)
        patch.setattr(preparation, "prepare_call", counted_shape)
        prepared = api.prepare(api.from_source(code))
        split = api.catalog.languages[api.name].runtime.split
        shaped = code.splitlines() if split else code
        assert calls == [shaped]
        assert shape_calls == [shaped]
        real_draws = []
        choice = 0

        def controlled(upper):
            real_draws.append(upper)
            return min(choice, upper - 1)

        patch.setattr(randomness.secrets, "randbelow", controlled)
        first_unseeded = prepared.run().unwrap().output
        choice = 1
        second_unseeded = prepared.run().unwrap().output
        assert first_unseeded != second_unseeded
        assert real_draws
        drawn = len(real_draws)
        assert complete_vm(prepared.make_vm()) == default_output
        assert complete_vm(prepared.make_vm()) == default_output
        assert len(real_draws) == drawn
        for seed, want in expected.items():
            assert prepared.run(seed=seed).unwrap() == want
            assert prepared.run(seed=seed).unwrap() == want
            stepped = prepared.run(
                seed=seed, limits=esolangs.ExecutionLimits(max_steps=1000)
            ).unwrap()
            assert replace(stepped, steps=None) == want
            first, second = prepared.make_vm(seed=seed), prepared.make_vm(seed=seed)
            initial = second.snapshot()
            first.step()
            assert second.snapshot() == initial
            assert complete_vm(first) == complete_vm(second) == want.output
        assert calls == [shaped]
        assert shape_calls == [shaped]


def check_split_factory_rejections(prepare, source):
    with pytest.raises(TypeError, match="split text source"):
        prepare("\n".join(source), {"unexpected": True})
    with pytest.raises(TypeError, match="no runtime options"):
        prepare(source, {"unexpected": True})
