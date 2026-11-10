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
):
    calls = []
    parse = getattr(module, parser_name)

    def counted(source):
        calls.append(source)
        return parse(source)

    with monkeypatch.context() as patch:
        patch.setattr(module, parser_name, counted)
        prepared = esolangs.Language(language).prepare(code)
        assert calls == [code]
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
        assert prepared.run(stdin=second_in, max_steps=100).output == second_out
        assert prepared.execute(stdin=third_in).unwrap().output == third_out
        assert calls == [code]
