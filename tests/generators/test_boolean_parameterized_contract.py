"""Shared contracts for generators that embed their inputs."""

import re

import pytest

import esolangs
from esolangs._bindings import runs
from esolangs.registry import LANGUAGES, resolve
from tests.support.generator_support import generator_for
from tests.support.pick import languages

_PARAMETERIZED = [
    (language.id, generator_for(language.name))
    for language in LANGUAGES.values()
    if language.parameterized and language.backend is not None
]


@pytest.mark.parametrize(("language", "gen"), _PARAMETERIZED)
def test_generators_spell_their_own_runs(language: str, gen) -> None:
    """The generator emits the public runs itself: no ``{Xi}`` anywhere."""
    for table in ("01", "0110", "01101001"):
        raw = gen(table)
        assert "{X" not in raw, (language, table)
        template = esolangs.generate(language, table)
        assert isinstance(template, esolangs.TemplateArtifact)
        assert template.source == raw, (language, table)
        assert template.source.count(template.bindings.char) == sum(
            len(z) for z, _ in template.bindings.setters
        )
        assert template.bindings.inputs == len(table).bit_length() - 1


@pytest.mark.parametrize(("language", "gen"), _PARAMETERIZED)
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_parameterized_generators_embed_each_input_once(language, gen, n) -> None:
    table = "0" * (1 << n)
    template = gen(table)
    spec = LANGUAGES[resolve(language)].backend.template
    assert spec is not None
    spans = runs(template, spec.char, spec.bindings(template, n))
    assert len(spans) == n, (language, n, spans)
    assert not re.findall(r"\{C(\d+)\}", template), (language, n)


@pytest.mark.parametrize("language", [name for name, _gen in _PARAMETERIZED])
def test_span_contract_rejects_complete_refusal(language) -> None:
    def refuse(_table):
        raise ValueError("span-control refusal")

    for n in (1, 2, 3, 4):
        with pytest.raises(ValueError, match="span-control refusal"):
            test_parameterized_generators_embed_each_input_once(language, refuse, n)


class TestGeneratorEdgePaths:
    @pytest.mark.parametrize("name", languages(parameterized=True)[:2])
    def test_parameterized_validation(self, name: str) -> None:
        """A template generator rejects malformed truth tables."""
        generate = generator_for(name)
        assert generate is not None
        with pytest.raises(ValueError, match="power-of-two"):
            generate("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            generate("0123")
