"""Check retained parse reuse without sharing invocation state."""

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
        assert prepared.run(stdin=first_in).output == first_out
        assert (
            prepared.run(
                stdin=second_in, limits=esolangs.ExecutionLimits(max_steps=100)
            ).output
            == second_out
        )
        assert prepared.execute(stdin=third_in).unwrap().output == third_out
        assert calls == [source]


def check_random_plan_reuse(language, code, module, parser_name, monkeypatch):
    """Reuse a finite witness while each invocation owns its random draws."""
    from esolangs.runtime import randomness

    api = esolangs.Language(language)
    default_seed = api.catalog.languages[api.name].runtime.reproducible_seed
    default_output = api.run(code, seed=default_seed).output
    expected = {seed: api.run(code, seed=seed) for seed in range(16)}
    assert len({result.output for result in expected.values()}) > 1
    calls = []
    parse = getattr(module, parser_name)

    def counted(source):
        calls.append(source)
        return parse(source)

    shape_calls = []

    class Source(str):
        def splitlines(self, *args, **kwargs):
            shape_calls.append(True)
            return super().splitlines(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(module, parser_name, counted)
        prepared = api.prepare(api.from_source(Source(code)))
        assert len(calls) == 1
        shaped = len(shape_calls)
        assert shaped == int(api.catalog.languages[api.name].runtime.split)
        real_draws = []
        choice = 0

        def controlled(upper):
            real_draws.append(upper)
            return min(choice, upper - 1)

        patch.setattr(randomness.secrets, "randbelow", controlled)
        first_unseeded = prepared.run().output
        choice = 1
        second_unseeded = prepared.run().output
        assert first_unseeded != second_unseeded
        assert real_draws
        drawn = len(real_draws)
        assert complete_vm(prepared.make_vm()) == default_output
        assert complete_vm(prepared.make_vm()) == default_output
        assert len(real_draws) == drawn
        for seed, want in expected.items():
            assert prepared.run(seed=seed) == want
            assert prepared.run(seed=seed) == want
            stepped = prepared.run(
                seed=seed, limits=esolangs.ExecutionLimits(max_steps=1000)
            )
            assert stepped._replace(steps=None) == want
            first, second = prepared.make_vm(seed=seed), prepared.make_vm(seed=seed)
            initial = second.snapshot()
            first.step()
            assert second.snapshot() == initial
            assert complete_vm(first) == complete_vm(second) == want.output
        assert len(calls) == 1
        assert len(shape_calls) == shaped
