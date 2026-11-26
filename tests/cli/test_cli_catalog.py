"""Catalog filters preserve capability limits across output formats."""

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES, Catalog, _table
from tests.support.cli_support import _failure, _program, call_both
from tests.support.pick import languages, one_where
from tests.support.reference import REFERENCE


def _python_cli(
    args: list[str], *, strip_docstrings: bool
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            sys.executable,
            *(["-OO"] if strip_docstrings else []),
            "-m",
            "esolangs",
            *args,
        ],
        env={**os.environ, "PYTHONOPTIMIZE": "0"},
        capture_output=True,
        check=False,
        timeout=15,
    )


def test_active_catalog_lists_in_every_format(monkeypatch, capsys, tmp_path) -> None:
    scope = Catalog([])
    monkeypatch.setattr(_table, "CATALOG", scope)
    assert esolangs.list_languages(catalog=scope) == []
    assert call_both(["list"], capsys) == ("", "")
    for flags in (["--json"], ["--json", "--details"]):
        assert call_both(["list", *flags], capsys) == ("[]\n", "")
    text, error = call_both(["list", "--details"], capsys)
    assert not error
    assert text.startswith("language  gen=generator")
    assert len(text.splitlines()) == 1

    original = LANGUAGES[REFERENCE]
    name = "Scoped catalog"
    renamed = replace(original, name=name, id="scoped_catalog")
    scoped = Catalog([renamed, replace(original, backend=None)])
    monkeypatch.setattr(_table, "CATALOG", scoped)
    assert call_both(
        ["list", "--generator", "--source-kind", "text", "--grep", "."], capsys
    ) == (
        name + "\n",
        "",
    )
    text, error = call_both(["list", "--details"], capsys)
    assert not error
    assert name in text
    assert REFERENCE in text
    listing, _ = call_both(
        ["list", "--json", "--details", "--interpreter-only"], capsys
    )
    (record,) = json.loads(listing)
    description, _ = call_both(["describe", "--json", REFERENCE], capsys)
    for facts in (record, json.loads(description)):
        assert facts["name"] == REFERENCE
        assert not facts["boolean_generator"]
        assert facts["generator_scaling"] is None
        assert facts["examples"] == []

    lf_name, cr_name, unreachable = "Scoped\nCatalog", "Scoped\rCatalog", "No\r\nAlias"
    # This name is reachable and must not become the spelling of a different row.
    escaped_name = r"Scoped\nCatalog"
    option_name, option_only = "--help", "--version"
    terminal_name = "clear\x1b[2Jscreen"
    restrictions = "first line\nsecond line\x1b[2J"
    escaped_restrictions = repr(restrictions)[1:-1]
    scope = Catalog(
        [
            replace(original, name=lf_name, id="scoped_lf", aliases=()),
            replace(
                original,
                name=cr_name,
                id="unsafe\rid",
                aliases=("scoped_cr",),
                backend=replace(original.backend, restrictions=restrictions),
                contract=replace(original.contract, note=restrictions),
            ),
            replace(original, name=escaped_name, id="escaped", aliases=()),
            replace(original, name=unreachable, id="unsafe\nid", aliases=()),
            replace(original, name=option_name, id="--help_id", aliases=("help_name",)),
            replace(original, name=option_only, id="--version_id", aliases=()),
            replace(original, name=terminal_name, id="terminal_name", aliases=()),
        ]
    )
    monkeypatch.setattr(_table, "CATALOG", scope)
    expected = {
        lf_name: "scoped_lf",
        cr_name: "scoped_cr",
        escaped_name: escaped_name,
        unreachable: f"{unreachable!r} (see --json)",
        option_name: "help_name",
        option_only: f"{option_only!r} (see --json)",
        terminal_name: "terminal_name",
    }
    canonical = esolangs.list_languages(catalog=scope)
    labels = [expected[name] for name in canonical]
    plain, error = call_both(["list"], capsys)
    assert (plain.splitlines(), error) == (labels, "")
    text, error = call_both(["list", "--details"], capsys)
    rows = text.splitlines()[1:]
    assert not error
    assert len(rows) == len(labels)
    width = max(map(len, labels))
    assert [row[:width].rstrip() for row in rows] == labels
    assert f"({escaped_restrictions})" in text

    output, _ = call_both(["list", "--json"], capsys)
    assert json.loads(output) == canonical
    output, _ = call_both(["list", "--json", "--details"], capsys)
    records = json.loads(output)
    assert [record["name"] for record in records] == canonical
    assert records[canonical.index(cr_name)]["generator_restrictions"] == restrictions

    path = _program(tmp_path, "+.")
    for name in (lf_name, cr_name, escaped_name, option_name, terminal_name):
        spelling = expected[name]
        assert scope.resolve(spelling) == name
        assert call_both(["run", spelling, path], capsys) == ("\x01", "")

    for name in (lf_name, cr_name, option_name, terminal_name):
        spelling = expected[name]
        details, error = call_both(["describe", spelling], capsys)
        lines = details.splitlines()
        assert not error
        assert lines[0] == (name if name.isprintable() else repr(name)[1:-1])
        if name == cr_name:
            assert lines[2].endswith(escaped_restrictions)
            assert lines[3].endswith(escaped_restrictions)
            assert "\x1b" not in details
            raw, _ = call_both(["describe", "--json", spelling], capsys)
            assert json.loads(raw)["answer_convention"] == restrictions
        spec = next(line for line in lines if line.startswith("spec: "))
        tool, *command = shlex.split(spec.removeprefix("spec: "))
        assert tool == "esolangs"
        operands = ["--", "--help_id"] if name == option_name else [spelling]
        assert command == ["describe", "--spec", *operands]
        assert call_both(command, capsys) == (
            scope.bind(name).describe().spec + "\n",
            "",
        )

    with pytest.raises(esolangs.UnknownLanguageError) as unknown:
        scope.resolve("terminal_nam")
    assert unknown.value.language == "terminal_nam"
    assert unknown.value.suggestions == (terminal_name,)
    assert _failure(["describe", "terminal_nam"], capsys) == (
        "",
        r"unknown language: terminal_nam (did you mean clear\x1b[2Jscreen?)" + "\n",
    )


@pytest.mark.medium
@pytest.mark.parametrize(
    "language",
    one_where(
        lambda d: not d.name.isascii(),
        boolean_generator=True,
        parameterized=False,
        answer_mode="output",
        random=False,
    ),
)
def test_catalog_commands_are_copyable_with_ascii_stdout(
    language: str, tmp_path: Path
) -> None:
    def call(*args: str, stdin: bytes | None = None) -> bytes:
        return subprocess.run(
            [sys.executable, "-m", "esolangs", *args],
            input=stdin,
            capture_output=True,
            timeout=10,
            check=True,
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
        ).stdout

    api = esolangs.Language(language)
    report = call("describe", language).decode("ascii")
    line = next(line for line in report.splitlines() if line.startswith("spec: "))
    command = shlex.split(line.removeprefix("spec: "))
    assert command[-1] == api.describe().id
    spec = call(*command[1:])
    assert spec == call("describe", "--spec", language)

    # The text listing shows the well-known languages first.
    names = sorted(
        esolangs.list_languages(), key=lambda n: not esolangs.describe(n).well_known
    )
    index = names.index(api.name)
    selector = call("list").decode("ascii").splitlines()[index]
    assert selector == api.describe().id
    details = call("list", "--details").decode("ascii").splitlines()
    assert details[index + 1].split()[0] == selector
    assert json.loads(call("list", "--json")) == esolangs.list_languages()

    program = api.generate("01")
    path = tmp_path / "program"
    api.to_file(program, path, normalize=True)
    stdin = api.encode_inputs([1])
    assert api.run(program, stdin=stdin).unwrap().output == "1"
    assert call("run", selector, str(path), stdin=stdin.encode()) == b"1"


@pytest.mark.medium
@pytest.mark.parametrize(
    "args",
    [
        ["list", "--details"],
        ["list", "--json", "--details"],
        ["list", "--input-shape", "template"],
        ["list", "--inputs", "8"],
        ["generate", "--width", "2", REFERENCE, "01"],
        ["generate", "--balance", REFERENCE, "01"],
    ],
)
def test_metadata_commands_work_without_docstrings(args: list[str]) -> None:
    ordinary = _python_cli(args, strip_docstrings=False)
    stripped = _python_cli(args, strip_docstrings=True)
    assert ordinary.returncode == stripped.returncode == 0, stripped.stderr
    assert ordinary.stdout == stripped.stdout
    assert ordinary.stderr == stripped.stderr


@pytest.mark.medium
def test_grep_skips_specs_excluded_by_capabilities() -> None:
    result = _python_cli(
        ["list", "--json", "--interpreter-only", "--inputs", "1", "--grep", "."],
        strip_docstrings=True,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"[]\n", b"")


@pytest.mark.medium
@pytest.mark.parametrize(
    "args",
    [
        ["list", "--grep", "."],
        ["list", "--source-kind", "text", "--inputs", "1", "--grep", "."],
        ["describe", "--spec", REFERENCE],
    ],
)
def test_spec_queries_explain_missing_docstrings(args: list[str]) -> None:
    result = _python_cli(args, strip_docstrings=True)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"docstring" in result.stderr
    assert b"-OO" in result.stderr


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


@pytest.mark.medium
def test_large_input_count_uses_declared_generator_bounds() -> None:
    count = 10**4401 + 1
    expected = [
        name
        for name in esolangs.list_languages()
        if (facts := esolangs.describe(name)).boolean_generator
        and (facts.generator_max_inputs is None or count <= facts.generator_max_inputs)
    ]
    assert expected
    operand = "1" + "0" * 4400 + "1"
    result = subprocess.run(
        [sys.executable, "-m", "esolangs", "list", "--json", f"--inputs={operand}"],
        env={**os.environ, "PYTHONINTMAXSTRDIGITS": "4300"},
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (result.returncode, result.stderr) == (0, b"")
    assert json.loads(result.stdout) == expected


def test_filters_match_in_every_output_format(capsys) -> None:
    filters = ["--interpreter-only", "--source-kind", "text", "--grep", "."]
    names = _names(filters, capsys)
    assert names == languages(boolean_generator=False, source_kind="text")
    text, error = call_both(["list", *filters], capsys)
    shown = sorted(names, key=lambda n: not esolangs.describe(n).well_known)
    assert (text.splitlines(), error) == (shown, "")
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


@pytest.mark.parametrize("pattern", ["--help", "-h", "--version", "-V", "--set", "-s"])
def test_grep_keeps_option_shaped_values(capsys, pattern: str) -> None:
    expected = _names([f"--grep={pattern}"], capsys)
    assert _names(["--grep", pattern], capsys) == expected


def test_invalid_filters_are_usage_errors(capsys) -> None:
    cases = [
        (["--generator", "--interpreter-only"], "cannot be combined"),
        (["--grep", "("], "--grep is not a valid regular expression"),
        (
            ["--grep", "a{999999999999999999999999999}"],
            "--grep is not a valid regular expression",
        ),
        (["--grep", "(" * 1_000 + "x" + ")" * 1_000], "--grep is not a valid"),
        (["--grep"], "--grep needs a value"),
        (["--grep", "--", "--json"], "--grep needs a value"),
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
    "well_known",
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
    shown = sorted(names, key=lambda n: not esolangs.describe(n).well_known)
    assert (text.splitlines(), error) == (shown, "")

    capped = next(
        (name, esolangs.describe(name).generator_max_inputs)
        for name in esolangs.list_languages()
        if esolangs.describe(name).generator_max_inputs is not None
    )
    name, cap = capped
    assert name in _names(["--inputs", str(cap)], capsys)
    assert name not in _names(["--inputs", str(cap + 1)], capsys)


def test_text_list_shows_the_well_known_languages_first(capsys) -> None:
    output, error = call_both(["list"], capsys)
    assert error == ""
    shown = [esolangs.describe(line).name for line in output.splitlines()]
    known = [name for name in shown if esolangs.describe(name).well_known]
    assert 0 < len(known) < len(shown)
    assert shown[: len(known)] == known
    assert sorted(shown) == sorted(_names([], capsys))
