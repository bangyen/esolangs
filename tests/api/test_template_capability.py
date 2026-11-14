"""Backend input bindings are independent of committed examples."""

import subprocess
import sys
from dataclasses import replace

import pytest

import esolangs
from esolangs.registry import CATALOG, LANGUAGES
from esolangs.registry._backend import TemplateSpec
from esolangs.registry._language import Example
from tests.support.pick import languages, one
from tests.support.reference import REFERENCE


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "exactly one"),
        ({"pair": ("a", "b"), "setters": lambda _text, _n: ()}, "exactly one"),
        ({"pair": ("a", "bb")}, "differ in width"),
        ({"pair": ("a", "b"), "char": ""}, "one character"),
        ({"pair": ("a", "b"), "char": "$$"}, "one character"),
    ],
)
def test_template_declaration_refuses_ambiguous_or_invalid_bindings(kwargs, message):
    with pytest.raises(ValueError, match=message):
        TemplateSpec(**kwargs)


@pytest.mark.parametrize("language", languages(parameterized=True))
def test_changing_an_example_cannot_change_generated_bindings(language):
    original = LANGUAGES[language]
    before = esolangs.to_json(language, esolangs.generate(language, "0110"))
    catalog = CATALOG.with_language(
        replace(original, example=Example(table="01", bits=(1,), expected="other"))
    )
    assert catalog.languages[language].parameterized
    after = esolangs.to_json(
        language, esolangs.generate(language, "0110", catalog=catalog), catalog=catalog
    )
    assert before == after


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", [REFERENCE, *one(parameterized=True, answer_mode="output")]
)
def test_execution_and_portable_bindings_do_not_import_examples(language):
    code = f"""
import importlib
import sys
import esolangs
from esolangs.registry import CATALOG, LANGUAGES
sys.modules['esolangs.generation.examples'] = None
language = {language!r}
source = esolangs.generate(language, '0110', balance=True)
source = esolangs.from_json(language, esolangs.to_json(language, source))
if LANGUAGES[language].parameterized:
    source = esolangs.instantiate(language, source, [0, 1])
    stdin = ''
else:
    stdin = esolangs.encode_inputs(language, [0, 1])
output = esolangs.run(language, source, stdin=stdin).output
assert esolangs.read_answer(language, output) == '1'
try:
    importlib.import_module('esolangs.generation.examples')
except ModuleNotFoundError:
    pass
else:
    raise AssertionError('import barrier did not fire')
"""
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)
