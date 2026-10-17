"""Catalog filters preserve capability limits across output formats."""

import json
import re

import pytest

import esolangs
from tests.support.cli_support import call_both
from tests.support.pick import languages


def _names(args, capsys):
    output, error = call_both(["list", "--json", *args], capsys)
    assert error == ""
    return json.loads(output)


def test_generator_and_interpreter_only_partition_catalog(capsys) -> None:
    generators = _names(["--generator"], capsys)
    interpreters = _names(["--interpreter-only"], capsys)
    assert interpreters == languages(boolean_generator=False)
    assert set(generators).isdisjoint(interpreters)
    assert sorted([*generators, *interpreters]) == esolangs.list_languages()


def test_filters_match_in_every_output_format(capsys) -> None:
    filters = ["--interpreter-only", "--grep", "."]
    names = _names(filters, capsys)
    assert names == languages(boolean_generator=False)
    text, error = call_both(["list", *filters], capsys)
    assert (text.splitlines(), error) == (names, "")
    text, error = call_both(["list", *filters, "--details"], capsys)
    rows = _names([*filters, "--details"], capsys)
    assert len(text.splitlines()) == 1 + len(rows)
    for row, line in zip(rows, text.splitlines()[1:], strict=True):
        assert line.startswith(row["name"])
        assert "int" in line.split()


def test_grep_searches_the_spec_case_insensitively(capsys) -> None:
    # Positive control: a spec's own headline, upper-cased, finds that spec.
    first = esolangs.list_languages()[0]
    headline = esolangs.describe(first)["spec"].splitlines()[0]
    names = _names(["--grep", re.escape(headline.upper())], capsys)
    assert first in names
    assert names == [
        name
        for name in esolangs.list_languages()
        if headline.lower() in esolangs.describe(name)["spec"].lower()
    ]
    assert _names(["--grep", "zzz-no-spec-says-this"], capsys) == []


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--generator", "--interpreter-only"], "cannot be combined"),
        (["--grep", "("], "--grep is not a valid regular expression"),
        (["--grep"], "--grep needs a value"),
        (["--grep", "a", "--grep", "b"], "--grep given more than once"),
        (["--shape", "tree"], "--shape"),
        (["--", "--generator"], "unexpected argument"),
    ],
)
def test_invalid_filters_are_usage_errors(capsys, args, message) -> None:
    with pytest.raises(SystemExit) as caught:
        call_both(["list", *args], capsys)
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


#: The classes ``list --help`` sends to ``jq``: each must be in the records.
_DETAILED = {
    "source_kind",
    "state_model",
    "shape",
    "answer_mode",
    "input_shape",
    "random",
    "width_effect",
    "boolean_generator",
    "parameterized",
    "generator_max_inputs",
    "generator_restrictions",
}


def test_details_records_carry_every_class(capsys) -> None:
    rows = _names(["--details"], capsys)
    for row in rows:
        facts = esolangs.describe(row["name"])
        assert {field: row[field] for field in _DETAILED} == {
            field: facts[field] for field in _DETAILED
        }
