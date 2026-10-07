"""Catalog filters preserve capability limits across output formats."""

import json

import pytest

import esolangs
from tests.cli_support import call_both


def _names(args, capsys):
    output, error = call_both(["list", "--json", *args], capsys)
    assert error == ""
    return json.loads(output)


def test_generator_and_interpreter_only_partition_catalog(capsys):
    generators = _names(["--generator"], capsys)
    interpreters = _names(["--interpreter-only"], capsys)
    assert interpreters == ["Deadfish", "HQ9+", "Nope.", "Unary"]
    assert set(generators).isdisjoint(interpreters)
    assert sorted([*generators, *interpreters]) == esolangs.list_languages()


def test_raster_filter_has_a_positive_control(capsys):
    assert _names(["--source=raster"], capsys) == ["Line", "Piet"]
    assert _names(["--source", "text", "--interpreter-only"], capsys) == [
        "Deadfish",
        "HQ9+",
        "Nope.",
        "Unary",
    ]


@pytest.mark.medium
@pytest.mark.parametrize("mode", ["output", "dump", "termination"])
def test_answer_filter_agrees_with_describe(capsys, mode):
    names = _names(["--answer", mode], capsys)
    assert names
    assert names == [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["answer_mode"] == mode
    ]


@pytest.mark.medium
def test_input_filter_respects_caps_without_hiding_table_limits(capsys):
    for name in ("Befunge", "Malbolge"):
        cap = esolangs.describe(name)["generator_max_inputs"]
        assert name in _names(["--inputs", str(cap)], capsys)
        assert name not in _names(["--inputs", str(cap + 1)], capsys)
    rows = _names(["--inputs=17", "--details"], capsys)
    assert all(row["boolean_generator"] for row in rows)
    polynomial = next(row for row in rows if row["name"] == "Polynomial")
    assert (
        polynomial["generator_restrictions"]
        == esolangs.describe("Polynomial")["generator_restrictions"]
    )
    assert polynomial["generator_restrictions"]


def test_combined_filters_match_in_every_output_format(capsys):
    filters = [
        "--generator",
        "--source",
        "raster",
        "--answer",
        "output",
        "--inputs",
        "4",
    ]
    names = _names(filters, capsys)
    assert names == ["Line", "Piet"]
    text, error = call_both(["list", *filters], capsys)
    assert text.splitlines() == names
    assert error == ""
    rows = _names([*filters, "--details"], capsys)
    text, error = call_both(["list", *filters, "--details"], capsys)
    assert len(text.splitlines()) == 3
    for row, line in zip(rows, text.splitlines()[1:], strict=True):
        assert line.startswith(row["name"])
        assert row["source_kind"] == "raster"
        assert row["answer_mode"] == "output"
        assert "gen" in line.split()
    assert error == ""


def test_no_matches_is_an_empty_catalog(capsys):
    filters = ["--source", "raster", "--interpreter-only"]
    assert _names(filters, capsys) == []
    text, error = call_both(["list", *filters], capsys)
    assert (text, error) == ("", "")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--generator", "--interpreter-only"], "cannot be combined"),
        (["--inputs", "4", "--interpreter-only"], "requires a generator"),
        (["--source", "binary"], "--source must be one of text, raster"),
        (["--answer", "halts"], "--answer must be one of output, dump, termination"),
        (["--inputs", "0"], "--inputs must be a positive integer"),
        (["--inputs", "-1"], "--inputs must be a positive integer"),
        (["--inputs", "1.5"], "--inputs must be a positive integer"),
        (["--inputs", ""], "--inputs must be a positive integer"),
        (["--source"], "--source needs a value"),
        (["--source", "-p"], "--source must be one of text, raster"),
        (["--source", "text", "--source", "raster"], "--source given more than once"),
        (["--sorce", "text"], "did you mean --source"),
        (["--", "--generator"], "unexpected argument"),
    ],
)
def test_invalid_filters_are_usage_errors(capsys, args, message):
    with pytest.raises(SystemExit) as caught:
        call_both(["list", *args], capsys)
    assert caught.value.code == 2
    assert message in capsys.readouterr().err
