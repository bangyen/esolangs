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
    headline = esolangs.describe(first).spec.splitlines()[0]
    names = _names(["--grep", re.escape(headline.upper())], capsys)
    assert first in names
    assert names == [
        name
        for name in esolangs.list_languages()
        if headline.lower() in esolangs.describe(name).spec.lower()
    ]
    assert _names(["--grep", "zzz-no-spec-says-this"], capsys) == []


def test_invalid_filters_are_usage_errors(capsys) -> None:
    cases = [
        (["--generator", "--interpreter-only"], "cannot be combined"),
        (["--grep", "("], "--grep is not a valid regular expression"),
        (["--grep"], "--grep needs a value"),
        (["--grep", "a", "--grep", "b"], "--grep given more than once"),
        (["--source-kind", "grid"], "--source-kind must be one of"),
        (["--answer-mode", "printed"], "--answer-mode must be one of"),
        (["--input-shape", "bits"], "--input-shape must be one of"),
        (["--inputs", "-1"], "--inputs must be a non-negative integer"),
        (["--inputs", "1.5"], "--inputs must be a non-negative integer"),
        (["--inputs"], "--inputs needs a value"),
        (["--source-kind", "text", "--source-kind", "raster"], "given more than once"),
        (["--", "--generator"], "unexpected argument"),
    ]
    for args, message in cases:
        with pytest.raises(SystemExit) as caught:
            call_both(["list", *args], capsys)
        assert caught.value.code == 2, args
        assert message in capsys.readouterr().err, args


#: The classes ``list --help`` sends to ``jq``: each must be in the records.
_DETAILED = {
    "source_kind",
    "state_model",
    "generator_shape",
    "answer_mode",
    "input_shape",
    "random",
    "width_effect",
    "boolean_generator",
    "parameterized",
    "generator_max_inputs",
    "generator_restrictions",
    "generator_scaling",
}


def test_details_records_carry_every_class(capsys) -> None:
    rows = _names(["--details"], capsys)
    for row in rows:
        if row["boolean_generator"]:
            assert row["generator_scaling"]
        else:
            assert row["generator_scaling"] is None
        assert "proof_status" not in row
        facts = esolangs.describe(row["name"])
        shape = "template" if facts.parameterized else facts.input_shape
        assert {field: row[field] for field in _DETAILED} == {
            field: getattr(facts, field) for field in _DETAILED
        } | {"input_shape": shape}


def test_metadata_filters_have_positive_matches(capsys):
    for option, field, value in (
        ("--source-kind", "source_kind", "raster"),
        ("--answer-mode", "answer_mode", "termination"),
        ("--input-shape", "input_shape", "char_stream"),
    ):
        names = _names([option, value], capsys)
        assert names, option
        assert names == [
            name
            for name in esolangs.list_languages()
            if getattr(esolangs.describe(name), field) == value
        ], option


def test_templates_and_combined_filters(capsys):
    templates = _names(["--input-shape", "template"], capsys)
    assert templates == languages(parameterized=True)
    assert templates
    filters = ["--source-kind", "text", "--answer-mode", "output", "--inputs", "8"]
    names = _names(filters, capsys)
    assert names
    for name in names:
        facts = esolangs.describe(name)
        assert facts.source_kind == "text"
        assert facts.answer_mode == "output"
        assert facts.boolean_generator
        assert facts.generator_max_inputs is None or facts.generator_max_inputs >= 8
    assert _names(["--interpreter-only", "--inputs", "0"], capsys) == []
    rows = _names([*filters, "--details"], capsys)
    assert [row["name"] for row in rows] == names
    text, error = call_both(["list", *filters], capsys)
    assert (text.splitlines(), error) == (names, "")

    capped = next(
        (name, esolangs.describe(name).generator_max_inputs)
        for name in esolangs.list_languages()
        if esolangs.describe(name).generator_max_inputs is not None
    )
    name, cap = capped
    assert name in _names(["--inputs", str(cap)], capsys)
    assert name not in _names(["--inputs", str(cap + 1)], capsys)
