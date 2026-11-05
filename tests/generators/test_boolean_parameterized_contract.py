"""Shared contracts for generators that embed their inputs."""

import importlib
import itertools
import re

import pytest

import esolangs
from esolangs.generation.helpers import runs
from esolangs.registry import LANGUAGES
from tests.support.pick import languages


def _parameterized_generators():
    """Return every registered backend declaring embedded inputs."""
    from esolangs.registry import LANGUAGES, parameterized_ids

    ids = parameterized_ids()
    return [
        (language.id, language.backend.generate)
        for language in LANGUAGES.values()
        if language.id in ids and language.backend is not None
    ]


@pytest.mark.parametrize(("language", "gen"), _parameterized_generators())
def test_generators_spell_their_own_runs(language: str, gen) -> None:
    """The generator emits the public runs itself: no ``{Xi}`` anywhere."""
    for table in ("01", "0110", "01101001"):
        raw = gen(table)
        assert "{X" not in raw, (language, table)
        template = esolangs.generate(language, table)
        assert str(template) == raw, (language, table)
        assert template.count(template.char) == sum(len(z) for z, _ in template.setters)
        assert template.inputs == len(table).bit_length() - 1


@pytest.mark.slow  # ~3s: builds every generator, up to n=4
def test_parameterized_generators_embed_each_input_once() -> None:
    """Every no-input generator embeds each input exactly once."""

    checked = 0
    for name, gen in _parameterized_generators():
        for n in (1, 2, 3, 4):
            table = format(0, f"0{2**n}b")
            try:
                template = gen(table)
            except ValueError:
                # A generator need not cover every arity.  The invariant here is about
                # the templates a generator *does* emit, so an uncovered arity
                # is skipped rather than failed; the count below keeps that
                # from quietly emptying the sweep.
                continue
            checked += 1
            spec = LANGUAGES[esolangs.resolve(name)].backend.template
            assert spec is not None
            spans = runs(template, spec.char, spec.bindings(template, n))
            cs = re.findall(r"\{C(\d+)\}", template)
            assert len(spans) == n, (name, n, spans)
            assert not cs, (name, n, cs)
    # Guard the skip above: every generator covers at least n == 2, so a run
    # that checked far fewer templates than that means the sweep stopped
    # exercising the generators rather than the generators getting stricter.
    assert checked >= len(_parameterized_generators()), checked


@pytest.mark.slow  # 2.6s: every fill of every parameterized generator
def test_fills_embed_a_zero_and_a_one_at_equal_width() -> None:
    """No fill may spell a 0 shorter than a 1, or the length leaks the input."""

    from esolangs.generation import examples as ex

    fills = [
        (name, getattr(ex, name))
        for name in dir(ex)
        if name.startswith("_fill_") and callable(getattr(ex, name))
    ]
    assert fills, "no _fill_* functions found"

    for name, fill in fills:
        gen_name = name.removeprefix("_fill_")
        gen = getattr(ex, gen_name, None) or getattr(
            importlib.import_module("esolangs.generation"), gen_name, None
        )
        if gen is None:  # pragma: no cover - fill without a same-named generator
            continue
        for n in (1, 2):
            template = gen(format(0, f"0{2**n}b"))
            lengths = {
                len(fill(template, list(bits)))
                for bits in itertools.product((0, 1), repeat=n)
            }
            assert len(lengths) == 1, (
                f"{name} embeds bits at unequal width for n={n}: {sorted(lengths)}"
            )


class TestGeneratorEdgePaths:
    @pytest.mark.parametrize("name", languages(parameterized=True)[:2])
    def test_parameterized_validation(self, name: str) -> None:
        """A template generator rejects malformed truth tables."""
        generate = LANGUAGES[name].backend.generate
        assert generate is not None
        with pytest.raises(ValueError, match="power-of-two"):
            generate("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            generate("0123")
