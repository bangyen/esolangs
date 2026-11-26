"""What the CLI makes discoverable: examples, specs, usage and templates."""

import json
import pathlib
import re
import shlex
import sys
from dataclasses import replace
from importlib.resources import files
from io import StringIO
from pathlib import Path

import pytest

import esolangs
from esolangs import cli, serialization
from esolangs._dialect import DialectSchema
from esolangs.cli.help import COMMANDS, USAGE, help_text
from esolangs.registry import LANGUAGES, Catalog, _table, wiki_url
from esolangs.registry._backend import BooleanBackend
from esolangs.runtime._capabilities import MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec, VerbatimSourcePolicy
from esolangs.runtime.memory import format_integer, parse_integer
from tests.support.cli_support import _failure, call_both, call_main
from tests.support.pick import first, one_where
from tests.support.reference import REFERENCE


def test_help_examples_follow_remaining_capabilities(monkeypatch, capsys) -> None:
    from esolangs.cli import help as help_module
    from esolangs.registry import LanguageDeclaration
    from esolangs.registry._backend import TemplateSpec
    from esolangs.registry._language import DeferredBackend

    def build(table):
        return table

    languages = {
        "Template Choice": LanguageDeclaration(
            "Template Choice",
            RuntimeSpec(
                "template_choice",
                machine_preparation="prepare_machine",
                completion_entrypoint="_execute",
                capabilities=MachineCapabilities(),
            ),
            backend=BooleanBackend(
                entrypoint=build, template=TemplateSpec(pair=("0", "1"))
            ),
        ),
        "Dialect Choice": LanguageDeclaration(
            "Dialect Choice",
            RuntimeSpec(
                "dialect_choice",
                machine_preparation="prepare_machine",
                completion_entrypoint="_execute",
                capabilities=MachineCapabilities(),
                dialect=lambda mode="plain": mode,
                dialect_schema=DialectSchema(
                    "Dialect Choice",
                    {"mode": ("plain", "é with spaces")},
                    {"mode": "plain"},
                ),
            ),
            backend=BooleanBackend(entrypoint=build),
        ),
    }

    def examples() -> tuple[str, str]:
        return help_module._capability_examples(Catalog(languages.values()))

    template, dialect = examples()
    assert shlex.split(template)[-2:] == ["Template Choice", "0110"]
    commands = dialect.replace("\\\n", "").splitlines()  # Shell-joined.
    assert shlex.split(commands[1])[3] == "mode=é with spaces"
    _, ascii_dialect = help_module._capability_examples(
        Catalog(languages.values()), encoding="ascii"
    )
    assert ascii_dialect == commands[0]
    assert json.loads(shlex.split(ascii_dialect)[3]) == {"mode": "é with spaces"}

    declaration = languages["Dialect Choice"]
    nul_value = "raw\0value"
    schema = DialectSchema(
        declaration.name, {"mode": ("plain", nul_value)}, {"mode": "plain"}
    )
    runtime = replace(declaration.runtime, dialect_schema=schema)
    nul_scope = Catalog([replace(declaration, runtime=runtime)])
    _, nul_example = help_module._capability_examples(nul_scope)
    assert "\0" not in nul_example
    assert len(nul_example.splitlines()) == 1
    assert json.loads(shlex.split(nul_example)[3]) == {"mode": nul_value}

    unreachable = replace(
        languages["Template Choice"], name="Raw\0Template", id="raw\0template"
    )
    assert help_module._capability_examples(Catalog([unreachable])) == ("", "")

    name = "A {_DIALECT_EXAMPLES} Compiler"
    original = LANGUAGES[
        first(parameterized=True, source_kind="text", answer_mode="output")
    ]
    scoped = Catalog([replace(original, name=name, id="scoped_template"), declaration])
    with monkeypatch.context() as active:
        active.setattr(_table, "CATALOG", scoped)
        for invocation in (["generate", "--help"], ["help", "generate"]):
            page, diagnostic = _failure(invocation, capsys, code=0)
            assert not diagnostic
            assert dialect in page
            command = shlex.split(
                next(
                    line
                    for line in page.splitlines()
                    if line.startswith("  esolangs generate --bits ")
                )
            )
            assert command == ["esolangs", "generate", "--bits", "10", name, "0110"]
            program = call_main(command[1:], capsys)
            bound = scoped.bind(name)
            assert bound.read_answer(bound.run(program).unwrap().output) == "1"

    error = esolangs.ArgumentError("scoped generator backend is disabled")
    error.add_note("hint: enable its provider")

    def unavailable():
        raise error

    broken = replace(
        languages["Template Choice"],
        name="zzz Disabled",
        id="zzz_disabled",
        backend=DeferredBackend(unavailable),
    )
    with monkeypatch.context() as active:
        active.setattr(_table, "CATALOG", Catalog([*languages.values(), broken]))
        for invocation in (["generate", "--help"], ["help", "generate"]):
            with pytest.raises(SystemExit) as exited:
                call_main(invocation, capsys)
            assert exited.value.code == 0
            output = capsys.readouterr()
            assert not output.err
            assert template in output.out
            assert dialect in output.out
        assert broken.name in json.loads(call_main(["list", "--json"], capsys))
        expected = "", "\n".join((str(error), *error.__notes__, ""))
        for flags in ([], ["--json"]):
            assert _failure(["list", "--details", *flags], capsys) == expected

        active.setattr(_table, "CATALOG", Catalog([broken]))
        for invocation in (["generate", "--help"], ["help", "generate"]):
            assert _failure(invocation, capsys) == expected
        output, diagnostic = _failure(["generate", broken.name], capsys)
        assert not output
        assert diagnostic.startswith("usage: esolangs generate ")
        assert diagnostic.endswith("missing <truth-table>\n")

    del languages["Template Choice"]
    assert examples()[0] == ""
    # A cap below two inputs is not a runnable example.
    languages.clear()
    languages["Capped"] = LanguageDeclaration(
        "Capped",
        RuntimeSpec(
            "capped",
            machine_preparation="prepare_machine",
            completion_entrypoint="_execute",
            capabilities=MachineCapabilities(),
        ),
        backend=BooleanBackend(entrypoint=build, max_inputs=1),
    )
    assert examples() == ("", "")
    languages.clear()
    assert examples() == ("", "")


def test_catalog_displays_and_help_keep_large_integer_settings(
    monkeypatch, capsys
) -> None:
    from esolangs.cli import help as help_module
    from esolangs.cli.args import _settings_arguments, _settings_of

    threshold = sys.int_info.str_digits_check_threshold
    previous_limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(threshold)
    try:
        large = 1 << (threshold * 4)
        original = LANGUAGES[REFERENCE]
        scope = Catalog(
            [
                replace(
                    original,
                    backend=replace(original.backend, max_inputs=large),
                    runtime=replace(
                        original.runtime,
                        dialect=lambda mode=large: mode,
                        dialect_schema=DialectSchema(
                            REFERENCE, {"mode": (1, large)}, {"mode": large}
                        ),
                    ),
                )
            ]
        )
        monkeypatch.setattr(_table, "CATALOG", scope)

        description = call_main(["describe", REFERENCE], capsys)
        summary = f"<integer with {large.bit_length()} bits>"
        assert f"mode={summary}" in description
        assert f"max-inputs={summary}" in call_main(["list", "--details"], capsys)
        details = json.loads(
            call_main(["describe", "--json", REFERENCE], capsys),
            parse_int=parse_integer,
        )
        assert details["dialect_settings"]["mode"]["default"] == large
        rows = json.loads(
            call_main(["list", "--json", "--details"], capsys), parse_int=parse_integer
        )
        assert rows[0]["generator_max_inputs"] == large

        help_commands = help_module._capability_examples()[1].splitlines()
        json_option = shlex.split(help_commands[0])[3]
        pair = shlex.split(help_commands[1])[3]
        assert pair.startswith("mode=0x")
        decimal = format_integer(large)
        for settings in (
            _settings_of(
                _settings_arguments({"--settings": json_option}, []),
                language=REFERENCE,
            ),
            _settings_of(_settings_arguments({}, [pair]), language=REFERENCE),
            _settings_of(
                _settings_arguments({}, [f"mode= +{decimal} "]), language=REFERENCE
            ),
        ):
            assert settings is not None
            assert settings.options()["mode"] == large
        for invalid in ("012", f"0{decimal}", f"-\u0660{decimal}"):
            _, error = _failure(
                ["generate", "--set", f"mode={invalid}", REFERENCE, "01"], capsys
            )
            assert error.startswith("--set mode needs an integer")
        _, error = _failure(
            ["generate", "--set", "mode=" + "0" * len(decimal), REFERENCE, "01"], capsys
        )
        assert error.startswith("invalid value for dialect setting mode: 0")
    finally:
        sys.set_int_max_str_digits(previous_limit)


def test_set_accepts_null_as_a_declared_string_choice(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    native = esolangs.generate(REFERENCE, "01").source
    original = LANGUAGES[REFERENCE]
    observed = []

    def build(request):
        observed.append(request.options.text("mode"))
        return native

    runtime = replace(
        original.runtime,
        source_policy=VerbatimSourcePolicy(),
        dialect=lambda mode="plain": mode,
        dialect_schema=DialectSchema(
            REFERENCE, {"mode": ("plain", "null")}, {"mode": "plain"}
        ),
    )
    scope = Catalog(
        [replace(original, runtime=runtime, backend=BooleanBackend(entrypoint=build))]
    )
    monkeypatch.setattr(_table, "CATALOG", scope)
    command = ["generate", REFERENCE, "01"]
    set_source = call_main([*command, "--set", "mode=null"], capsys)
    json_source = call_main([*command, "--settings", '{"mode":"null"}'], capsys)
    assert set_source == json_source == native
    path = tmp_path / "program"
    serialization.to_file(REFERENCE, set_source, path, normalize=True, catalog=scope)
    assert path.read_bytes() == set_source.encode()
    assert observed == ["null", "null"]
    _, error = _failure([*command, "--settings", '{"mode":null}'], capsys)
    assert "invalid value for dialect setting mode: None" in error

    bad_key = "oops\x1b[2J\nfield"
    bad_label = r"oops\x1b[2J\nfield"
    key_json = json.dumps(bad_key)
    for flags in (
        ["--set", f"{bad_key}=null"],
        ["--settings", json.dumps({bad_key: "null"})],
    ):
        _, error = _failure([*command, *flags], capsys)
        assert error == (
            f"unknown dialect setting for {REFERENCE}: {bad_label}; "
            "known settings: mode\n"
        )
    _, error = _failure(
        [*command, "--settings", f"{{{key_json}: 1, {key_json}: 2}}"], capsys
    )
    assert error == (
        f"--settings is not valid JSON (duplicate field: {bad_label}); "
        "pass a JSON object\n"
    )

    settings = [
        '--settings={"mode":"plain"}',
        "--set=mode=ignored value",
        "--set=mode=null",
    ]
    _, error = _failure(["generate", *settings, "01", REFERENCE], capsys)
    repaired = shlex.split(error.split("first: ", 1)[1])
    assert repaired == ["esolangs", "generate", *settings, REFERENCE, "01"]
    assert call_main(repaired[1:], capsys) == native
    assert observed == ["null", "null", "null"]
    _, error = _failure(["generate", "--settings={", "01", REFERENCE], capsys)
    assert "--settings is not valid JSON" in error
    assert "looks like a truth table" not in error

    result = esolangs.run(REFERENCE, set_source, stdin="1").unwrap()
    assert esolangs.read_answer(REFERENCE, result.output) == "1"


class TestExamplesShipWithThePackage:
    """They lived at the repository root, which left them out of the wheel."""

    def test_every_language_reports_one(self) -> None:
        """Every implemented language reports a committed program."""
        populated = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name).examples
        ]
        assert set(populated) == {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name).boolean_generator
        }

    def test_every_reported_path_exists(self) -> None:
        """A path reported and absent is worse than none reported."""
        for name in esolangs.list_languages():
            for path in esolangs.describe(name).examples:
                assert not pathlib.Path(path).is_absolute(), (name, path)
                assert (files("esolangs") / path).is_file(), (name, path)

    def test_the_packaging_declares_them(self) -> None:
        """The other half: inside the package *and* listed as data."""
        config = (pathlib.Path(__file__).parents[2] / "pyproject.toml").read_text()
        declared = re.search(r"^esolangs = \[(.+?)\]", config, re.MULTILINE)
        assert declared, "no package-data entry for esolangs"
        patterns = declared.group(1)
        directory = pathlib.Path(esolangs.__file__).resolve().parent / "languages"
        for suffix in {
            path.suffix
            for path in directory.glob("*/*")
            if path.suffix in {".txt", ".png", ".gz"}
        }:
            assert f"languages/*/*{suffix}" in patterns
        assert "languages/EXAMPLES.md" in patterns


class TestWikiUrlsAreUsable:
    """The wiki slug must escape what a path cannot carry."""

    def test_non_ascii_is_escaped(self) -> None:
        """Raw bytes work in a browser and are refused by a strict client."""
        slug = wiki_url("Þorn").rsplit("/", 1)[1]
        assert slug == "%C3%9Eorn"
        for name in esolangs.list_languages():
            assert esolangs.describe(name).wiki_url == wiki_url(name)

    @pytest.mark.parametrize(
        "name", [n for n in esolangs.list_languages() if set(n) & set("()*~ ")]
    )
    def test_the_readable_ones_stay_readable(self, name: str) -> None:
        """Parentheses and ``*`` are legal in a path and all answer 200."""
        assert esolangs.describe(name).wiki_url == (
            f"https://esolangs.org/wiki/{name.replace(' ', '_')}"
        )

    def test_every_url_is_a_valid_path(self) -> None:
        """No unescaped ``%`` or ``^`` anywhere in the language, which is the rule."""
        for name in esolangs.list_languages():
            url = str(esolangs.describe(name).wiki_url)
            slug = url.removeprefix("https://esolangs.org/wiki/")
            assert "^" not in slug, name
            assert re.fullmatch(r"[^%]*(%[0-9A-Fa-f]{2}[^%]*)*", slug), (name, slug)
            assert slug.isascii(), name

    def test_the_catalog_uses_the_same_builder(self) -> None:
        """The second copy of the slug logic is what made this ship twice."""
        catalog = (Path(__file__).parents[2] / "docs" / "languages.md").read_text()
        for name in esolangs.list_languages():
            assert f"({wiki_url(name)})" in catalog, name
            raw = f"https://esolangs.org/wiki/{name.replace(' ', '_')}"
            assert raw == wiki_url(name) or f"({raw})" not in catalog, name


class TestTheTopLevelUsageKeepsUp:
    """It had fallen behind five subcommands, in both directions."""

    @staticmethod
    def _entry(command: str) -> str:
        """The usage block's lines for ``command``, joined."""
        lines = USAGE.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(command + " ") or line.strip() == command:
                block = [line]
                for continuation in lines[i + 1 :]:
                    if not continuation.strip().startswith(("[", "<")):
                        break
                    block.append(continuation)
                return " ".join(block)
        raise AssertionError(f"{command} is not in the usage block at all")

    def test_every_command_is_listed(self) -> None:
        """A command absent from the summary is a command nobody finds."""
        assert not hasattr(cli, "HELP")
        for command in COMMANDS:
            assert self._entry(command)

    def test_commands_are_grouped_by_who_supplies_the_program(self) -> None:
        """The first-touch split, not a docs-only taxonomy."""
        generator = USAGE.index("Generator-made")
        caller = USAGE.index("Caller-supplied")
        adapters = USAGE.index("Contract adapters")
        catalog = USAGE.index("Catalog:")
        assert generator < caller < adapters < catalog
        assert generator < USAGE.index("generate ") < caller
        assert caller < USAGE.index("run ") < adapters
        assert adapters < USAGE.index("encode-inputs ") < catalog
        assert adapters < USAGE.index("read-answer ") < catalog
        assert catalog < USAGE.index("list ")
        assert catalog < USAGE.index("describe ")
        assert "Boolean measurement" not in USAGE

    def test_every_documented_flag_is_summarised(
        self, subtests: pytest.Subtests
    ) -> None:
        """Read off each subcommand's own usage line, so it cannot drift."""
        for command in sorted(COMMANDS):
            with subtests.test(command=command):
                head = help_text(command).split("\n\n")[0]
                if "[options]" in head:
                    continue
                flags = sorted(set(re.findall(r"--[a-z-]+", head)))
                entry = self._entry(command)
                missing = [flag for flag in flags if flag not in entry]
                assert not missing, f"{command} usage omits {missing}"


class TestDescribeHidesInputFieldsWithNoInput:
    """An input shape for a language that reads no stdin is noise."""

    def test_a_template_language_hides_them(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And names the flag that supplies the bits instead."""
        out = call_main(["describe", first(parameterized=True)], capsys)
        assert "input_shape" not in out
        assert "generated programs embed the bits in source" in out
        assert "generate --bits" in out

    def test_a_reading_language_still_shows_them(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The fields are the point for the languages that have them."""
        out = call_main(["describe", first(input_shape="row_index")], capsys)
        assert "input_shape" in out
        assert "row_index" in out


@pytest.mark.parametrize(
    "language", one_where(lambda facts: bool(re.search(r"[*()]", facts.name)))
)
def test_describe_quotes_shell_metacharacters_in_its_spec_command(
    capsys, monkeypatch, tmp_path, language: str
) -> None:
    report = call_main(["describe", language], capsys)
    command = next(
        line.removeprefix("spec: ")
        for line in report.splitlines()
        if line.startswith("spec: ")
    )
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tool, *args = lexer
    assert tool == "esolangs"
    assert args == ["describe", "--spec", language]
    assert call_main(args, capsys).strip() == esolangs.describe(language).spec.strip()

    class Writer:
        def __init__(self, codec) -> None:
            self.codec = codec
            self.sink = StringIO()

        def write(self, data):
            data.encode(self.codec)
            return self.sink.write(data)

        def flush(self):
            self.sink.flush()

    class Unspecified(Writer):
        encoding = None

    class AsciiStdout(Writer):
        encoding = "ascii"

    class Utf8Stdout(Writer):
        encoding = "utf-8"

    original = LANGUAGES[
        first(parameterized=True, source_kind="text", answer_mode="output")
    ]
    for name, id_, aliases in (
        ("-Scoped name", "scoped_name", ()),
        ("É Scoped name", "e_scoped_name", ()),
        ("--Scoped name", "--scoped_name", ()),
        ("Raw\0Scoped name", "raw_scoped_name", ()),
        ("Raw\0Scoped name", "raw\0id", ("raw_scoped_alias",)),
    ):
        local = replace(original, name=name, id=id_, aliases=aliases)
        if not name.isascii():
            schema = DialectSchema(name, {"mode": ("plain", "é")}, {"mode": "plain"})
            local = replace(
                local,
                runtime=replace(
                    local.runtime,
                    dialect=lambda mode="plain": mode,
                    dialect_schema=schema,
                ),
            )
        scope = Catalog([local])
        bound = scope.bind(name)
        spelling = aliases[0] if aliases else id_
        with monkeypatch.context() as active:
            active.setattr(_table, "CATALOG", scope)
            if "\0" in name:
                text = call_main(["describe", spelling], capsys)
            elif name.isascii():
                text = call_main(["describe", "--", name], capsys)
            else:

                def copy_example(page):
                    return shlex.split(
                        next(
                            line
                            for line in page.splitlines()
                            if line.startswith("  esolangs generate --bits ")
                        )
                    )

                assert copy_example(help_text("generate", catalog=scope))[-2] == name
                for adapter, codec, expected in (
                    (AsciiStdout, "ascii", id_),
                    (Writer, "ascii", id_),
                    (Unspecified, "ascii", id_),
                    (Utf8Stdout, "utf-8", name),
                    (Writer, "utf-8", id_),
                ):
                    with active.context() as capture:
                        stdout = adapter(codec)
                        capture.setattr(sys, "stdout", stdout)
                        call_main(["describe", name], capsys)
                    text = stdout.sink.getvalue()
                    title, *lines = text.splitlines()
                    assert title == name.encode(codec, "backslashreplace").decode(codec)
                    spec = next(
                        line.removeprefix("spec: ")
                        for line in lines
                        if line.startswith("spec: ")
                    )
                    assert shlex.split(spec) == [
                        "esolangs",
                        "describe",
                        "--spec",
                        expected,
                    ]
                    assert (
                        call_main(shlex.split(spec)[1:], capsys).strip()
                        == bound.describe().spec
                    )
                    for invocation in (["generate", "--help"], ["help", "generate"]):
                        with active.context() as capture:
                            stdout = adapter(codec)
                            capture.setattr(sys, "stdout", stdout)
                            with pytest.raises(SystemExit) as caught:
                                call_main(invocation, capsys)
                        assert caught.value.code == 0
                        page = stdout.sink.getvalue()
                        example = copy_example(page)
                        assert example == [
                            "esolangs",
                            "generate",
                            "--bits",
                            "10",
                            expected,
                            "0110",
                        ]
                        program = call_main(example[1:], capsys)
                        assert (
                            bound.read_answer(bound.run(program).unwrap().output) == "1"
                        )
                        json_line = next(
                            line
                            for line in page.splitlines()
                            if line.startswith("  esolangs generate --settings ")
                        )
                        command = shlex.split(json_line)
                        assert json.loads(command[3]) == {"mode": "é"}
                        assert command[-2] == expected
                        assert ("  esolangs generate --set " in page) == (
                            expected == name
                        )
            command = next(
                line for line in text.splitlines() if line.startswith("spec: ")
            )
            tool, *args = shlex.split(command.removeprefix("spec: "))
            assert tool == "esolangs"
            operand = ["--", spelling] if spelling.startswith("-") else [spelling]
            assert args == ["describe", "--spec", *operand]
            assert call_main(args, capsys).strip() == bound.describe().spec

            advice = next(
                line for line in text.splitlines() if line.startswith("input: ")
            )
            fill = advice[advice.index("esolangs generate ") :]
            tool, *args = shlex.split(
                fill.replace("<bits>", "1").replace("<table>", "01")
            )
            assert tool == "esolangs"
            assert args == ["generate", "--bits", "1", *operand, "01"]
            program = call_main(args, capsys)
            assert bound.read_answer(bound.run(program).unwrap().output) == "1"

            if aliases:
                _, empty = _failure(["read-answer", spelling], capsys, code=1)
                tokens = shlex.split(empty.split("output in: ", 1)[1])
                assert tokens == [
                    "esolangs",
                    "run",
                    spelling,
                    "prog.txt",
                    "|",
                    "esolangs",
                    "read-answer",
                    spelling,
                ]
                path = tmp_path / tokens[3]
                path.write_text(program)
                answer = call_main([*tokens[1:3], str(path)], capsys)
                assert call_main(tokens[6:], capsys, stdin=answer) == "1\n"

            if id_.startswith("-"):
                _, error = _failure(
                    ["generate", "--bits", "1", "--", "01", name], capsys
                )
                repair = shlex.split(error.split("first: ", 1)[1])
                assert repair == [tool, "generate", "--bits=1", *operand, "01"]
                assert call_main(repair[1:], capsys) == program
                _, split = _failure(["generate", "--", *name.split(), "01"], capsys)
                assert shlex.split(split.split("pass it as ", 1)[1]) == operand

    name = "Raw\0Scoped name"
    scope = Catalog([replace(original, name=name, id="raw\0id", aliases=())])
    monkeypatch.setattr(_table, "CATALOG", scope)
    text = call_main(["describe", name], capsys)
    assert "\0" not in text
    assert "esolangs describe --spec" not in text
    assert "Fill them with instantiate() in Python" in text
    assert json.loads(call_main(["describe", "--json", name], capsys))["name"] == name

    _, empty = _failure(["read-answer", name], capsys, code=1)
    assert (
        empty
        == "nothing on stdin to read an answer out of; pipe a program's output in\n"
    )
    for args in (
        ["describe", *name.split()],
        ["encode-inputs", name, "1"],
        ["generate", "01", name],
    ):
        _, diagnostic = _failure(args, capsys)
        assert "\0" not in diagnostic
        assert "esolangs generate" not in diagnostic
    _, advice = call_both(["generate", name, "01"], capsys)
    assert "fill them with instantiate() in Python" in advice

    bound = scope.bind(name)
    output = bound.run(bound.generate("01").fill([1])).unwrap().output
    assert call_main(["read-answer", name], capsys, stdin=output) == "1\n"


class TestVersion:
    def test_version_is_a_flag_not_an_unknown_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["--version"], capsys)
        assert exc.value.code == 0
        assert esolangs.__version__ in capsys.readouterr().out
