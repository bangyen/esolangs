"""Check parsed-image reuse without sharing self-modifying machine state."""

import esolangs
from esolangs.vm import complete_vm


def check_image_reuse(language, code, module, parser_name, monkeypatch):
    calls = []
    parse = getattr(module, parser_name)

    def counted(source):
        calls.append(source)
        return parse(source)

    with monkeypatch.context() as patch:
        patch.setattr(module, parser_name, counted)
        prepared = esolangs.Language(language).prepare(code)
        assert calls == [code]
        first, second = prepared.make_vm(stdin="A"), prepared.make_vm(stdin="Z")
        before = second.snapshot()
        first.step()
        assert second.snapshot() == before
        assert complete_vm(first) == "A"
        assert complete_vm(second) == "Z"
        assert prepared.run(stdin="A").output == "A"
        assert prepared.run(stdin="Z", max_steps=100).output == "Z"
        assert prepared.execute(stdin="Q").unwrap().output == "Q"
        assert calls == [code]
