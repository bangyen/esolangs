"""Canonical generator ownership survives the public alias."""

from scripts import new_language, remove_language


def test_eval_source_listing_includes_its_canonical_generator():
    assert "src/esolangs/languages/eval/generator.py" in new_language.sources("Eval")


def test_eval_removal_owns_its_canonical_generator():
    from esolangs.registry import LANGUAGES

    modules, paths = remove_language._owned_module_paths(LANGUAGES["Eval"])  # noqa: SLF001
    assert "esolangs.languages.eval.generator" in modules
    assert remove_language.ROOT / "src/esolangs/languages/eval/generator.py" in paths
