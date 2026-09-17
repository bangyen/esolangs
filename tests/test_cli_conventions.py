"""What the CLI makes discoverable: examples, specs, usage and templates.

The rest of the second blind pass moved to siblings: test_cli_timeouts,
test_cli_io, test_cli_messages and test_cli_commands.  What is left is the
part that is about *finding* things rather than running them -- the committed
examples, the wiki links, the spec, and the usage text that indexes them.
"""

import importlib
import json
import pathlib
import re
from pathlib import Path

import pytest

import esolangs
from esolangs.cli import HELP, USAGE
from tests.cli_support import call_both
from tests.test_cli import call_main


class TestExamplesShipWithThePackage:
    """They lived at the repository root, which left them out of the wheel.

    ``describe(...)["examples"]`` was populated from a checkout and empty
    from an install, with nothing to say which you had -- and the README
    pointed every reader at a ``MANIFEST.md`` no installed copy carried.
    They live inside the package now, with a symlink at the root so the
    repository still reads the way it did.
    """

    def test_every_language_reports_one(self) -> None:
        """Every implemented language reports a committed program."""
        populated = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["examples"]
        ]
        assert len(populated) == 63

    def test_every_reported_path_exists(self) -> None:
        """A path reported and absent is worse than none reported."""
        for name in esolangs.list_languages():
            for path in esolangs.describe(name)["examples"]:
                assert pathlib.Path(path).is_file(), (name, path)

    def test_they_live_inside_the_package(self) -> None:
        """Which is the property that puts them in the wheel.

        Not a proxy for it -- setuptools ships ``package-data`` from
        inside the package directory and cannot reach outside it, so a
        path under here is a path that gets built in.
        """
        root = pathlib.Path(esolangs.__file__).resolve().parent
        for name in esolangs.list_languages():
            for path in esolangs.describe(name)["examples"]:
                assert pathlib.Path(path).resolve().is_relative_to(root), (name, path)

    def test_the_packaging_declares_them(self) -> None:
        """The other half: inside the package *and* listed as data.

        Being in the directory is not enough -- setuptools ships only what
        ``package-data`` names, so a glob that stopped matching would
        silently empty the wheel again.
        """
        config = (pathlib.Path(__file__).parents[1] / "pyproject.toml").read_text()
        declared = re.search(r"^esolangs = \[(.+?)\]", config, re.M)
        assert declared, "no package-data entry for esolangs"
        patterns = declared.group(1)
        assert "examples/*.txt" in patterns
        assert "examples/*/*.txt" not in patterns

    def test_the_manifest_is_beside_them(self) -> None:
        """It is what says which table each program computes."""
        root = pathlib.Path(esolangs.__file__).resolve().parent
        assert (root / "examples" / "MANIFEST.md").is_file()

    def test_the_root_symlink_still_resolves(self) -> None:
        """The repository reads the way it always did.

        The README links to ``examples/`` and a reader browsing the repo
        expects it there; the symlink keeps that true without a second
        copy to drift.
        """
        link = pathlib.Path(__file__).parents[1] / "examples"
        assert link.is_dir()
        assert (link / "brainfuck.txt").is_file()
        assert (
            link.resolve()
            == pathlib.Path(esolangs.__file__).resolve().parent / "examples"
        )


class TestTheSpecIsReachable:
    """The best documentation here was reachable only by guessing.

    Every one of the 65 interpreters carries a module docstring with the
    command table and, more usefully, where this implementation differs
    from the wiki page.  Nothing pointed at them: ``docs/`` has a
    capability matrix and two per-language notes, neither a spec, and
    ``describe`` reported ``interpreter: stack_based.unsquare`` -- an
    import path with no hint that importing it was the point.  A reader who
    arrived with a program rather than a truth table found it by reaching
    for ``importlib``.
    """

    def test_every_language_has_one(self) -> None:
        """The claim the feature rests on: there is something to show."""
        for name in esolangs.list_languages():
            assert len(esolangs.spec(name)) > 200, name

    def test_it_is_the_interpreter_that_is_read(self) -> None:
        """Read, not stored, so it cannot drift from what it describes."""
        module = importlib.import_module(
            "esolangs.interpreters." + str(esolangs.describe("Unsquare")["interpreter"])
        )
        assert esolangs.spec("Unsquare") == (module.__doc__ or "").strip()

    def test_it_resolves_a_name_like_everything_else(self) -> None:
        """A spelling that works everywhere else has to work here."""
        assert esolangs.spec("BRAINFUCK") == esolangs.spec("brainfuck")
        assert esolangs.spec(" Unsquare ") == esolangs.spec("Unsquare")
        with pytest.raises(esolangs.UnknownLanguageError):
            esolangs.spec("nosuchlang")

    def test_the_cli_prints_it(self, capsys: pytest.CaptureFixture[str]) -> None:
        """And prints the text, not a record with the text in it."""
        out, _err = call_both(["describe", "--spec", "Unsquare"], capsys)
        assert out.strip() == esolangs.spec("Unsquare")

    def test_json_and_spec_together_give_a_field(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A caller scripting it wants the record *and* the prose."""
        out, _err = call_both(["describe", "--json", "--spec", "brainfuck"], capsys)
        payload = json.loads(out)
        assert payload["spec"] == esolangs.spec("brainfuck")
        assert payload["name"] == "brainfuck"

    def test_the_plain_output_points_at_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A flag nobody can find is a flag nobody has."""
        out, _err = call_both(["describe", "brainfuck"], capsys)
        assert "esolangs describe --spec brainfuck" in out

    def test_the_pointer_names_the_resolved_name(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Copying the line has to work, which means the canonical spelling."""
        out, _err = call_both(["describe", "BRAINFUCK"], capsys)
        assert "--spec brainfuck" in out

    def test_it_still_refuses_an_unknown_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The flag must not become a way past the error path."""
        with pytest.raises(SystemExit):
            call_main(["describe", "--spec", "nosuchlang"], capsys)
        assert "nosuchlang" in capsys.readouterr().err


class TestWikiUrlsAreUsable:
    """``describe('%^2^-1')`` handed back a URL that answers 400.

    ``%^2`` is not a percent-escape, so the link was broken for the one
    language whose name starts with the escape character.  The same URL was
    a markdown link in README.md, built by a *second* copy of the slug
    logic in ``scripts/generate.py docs`` -- so fixing either alone
    would have left the other wrong.
    """

    def test_the_broken_one_is_escaped(self) -> None:
        """Escaped, and specifically the two characters a path cannot carry."""
        assert esolangs.describe("%^2^-1")["wiki_url"] == (
            "https://esolangs.org/wiki/%25%5E2%5E-1"
        )

    def test_non_ascii_is_escaped(self) -> None:
        """Raw bytes work in a browser and are refused by a strict client."""
        assert esolangs.describe("Forþ")["wiki_url"] == (
            "https://esolangs.org/wiki/For%C3%BE"
        )

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("CV(N)(C)", "CV(N)(C)"),
            ("S*bleq", "S*bleq"),
            ("bit~", "bit~"),
            ("SLOW ACV MAMMALIAN", "SLOW_ACV_MAMMALIAN"),
        ],
    )
    def test_the_readable_ones_stay_readable(self, name: str, expected: str) -> None:
        """Parentheses and ``*`` are legal in a path and all answer 200.

        Escaping them too would have been easier and would have turned five
        working links into unreadable ones for no gain.
        """
        assert esolangs.describe(name)["wiki_url"] == (
            f"https://esolangs.org/wiki/{expected}"
        )

    def test_every_url_is_a_valid_path(self) -> None:
        """No unescaped ``%`` or ``^`` anywhere in the 65, which is the rule."""
        for name in esolangs.list_languages():
            url = str(esolangs.describe(name)["wiki_url"])
            slug = url.removeprefix("https://esolangs.org/wiki/")
            assert "^" not in slug, name
            assert re.fullmatch(r"[^%]*(%[0-9A-Fa-f]{2}[^%]*)*", slug), (name, slug)
            assert slug.isascii(), name

    def test_the_readme_uses_the_same_builder(self) -> None:
        """The second copy of the slug logic is what made this ship twice."""
        readme = (Path(__file__).parents[1] / "README.md").read_text()
        assert "https://esolangs.org/wiki/%25%5E2%5E-1" in readme
        assert "https://esolangs.org/wiki/%^2^-1" not in readme


class TestPrintedCommandsCanBePasted:
    """The tool emitted commands it cannot itself parse.

    Twelve of the 65 names contain a space, and ``describe`` ends with
    ``esolangs describe --spec A Painter Ant`` while the template hint
    offers ``esolangs generate --bits <bits> A Painter Ant <table>``.
    Copy-pasting either gives ``unexpected argument: 'Painter'``.
    """

    SPACED = "A Painter Ant"

    def test_the_spec_line_is_quoted(self, capsys: pytest.CaptureFixture[str]) -> None:
        """And unspaced names stay unquoted, since quoting them is noise."""
        out, _err = call_both(["describe", self.SPACED], capsys)
        assert f'--spec "{self.SPACED}"' in out
        plain, _err = call_both(["describe", "brainfuck"], capsys)
        assert "--spec brainfuck" in plain

    def test_the_quoted_command_actually_runs(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The point of quoting it, and the thing a test can check."""
        out, _err = call_both(["describe", "--spec", self.SPACED], capsys)
        assert out.startswith("Interpreter for A Painter Ant")

    def test_the_template_hint_is_quoted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``encode`` on a template language points at ``generate --bits``."""
        with pytest.raises(SystemExit):
            call_main(["encode", self.SPACED, "10"], capsys)
        assert f'"{self.SPACED}"' in capsys.readouterr().err

    def test_every_spaced_name_is_quoted_in_its_describe(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All nine, since one unquoted survivor is the whole bug again."""
        spaced = [n for n in esolangs.list_languages() if " " in n]
        assert len(spaced) == 9
        for name in spaced:
            out, _err = call_both(["describe", name], capsys)
            assert f'--spec "{name}"' in out, name


class TestTheTopLevelUsageKeepsUp:
    """It had fallen behind five subcommands, in both directions.

    Missing from ``esolangs --help``: ``list --json``, ``describe --json``,
    ``describe --spec``, ``run --seed``, and ``--timeout``/``--width`` on
    ``answer``, ``verify`` and ``evaluate``.  The ``--timeout`` omission is
    the one that costs a reader something: it is the flag the three
    diverging languages need, and its absence reads as "cannot be bounded".

    Drifting the other way too -- the top level advertised ``run --table``
    while ``run``'s own usage line did not.
    """

    @staticmethod
    def _entry(command: str) -> str:
        """The usage block's lines for ``command``, joined."""
        lines = USAGE.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(command + " ") or line.strip() == command:
                return " ".join(lines[i : i + 2])
        raise AssertionError(f"{command} is not in the usage block at all")

    def test_every_command_is_listed(self) -> None:
        """A command absent from the summary is a command nobody finds."""
        for command in HELP:
            assert self._entry(command)

    @pytest.mark.parametrize("command", sorted(HELP))
    def test_every_documented_flag_is_summarised(self, command: str) -> None:
        """Read off each subcommand's own usage line, so it cannot drift.

        ``debug`` is exempt: its usage line says ``[options]`` on purpose,
        which is a summary rather than an omission.
        """
        head = HELP[command].split("\n\n")[0]
        if "[options]" in head:
            return
        flags = sorted(set(re.findall(r"--[a-z-]+", head)))
        entry = self._entry(command)
        missing = [flag for flag in flags if flag not in entry]
        assert not missing, f"{command} usage omits {missing}"


class TestTemplatesAreReachableFromTheCli:
    """Seventeen languages a CLI-only user could not finish."""

    def test_bits_completes_every_row(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal pointed at ``esolangs.instantiate``, a Python call."""
        got = ""
        for a in (0, 1):
            for b in (0, 1):
                program = call_main(
                    ["generate", "--bits", f"{a}{b}", "Minifuck", "0110"], capsys
                )
                path = tmp_path / "m.txt"
                path.write_text(program.rstrip("\n"))
                got += call_main(["run", "Minifuck", str(path)], capsys)
        assert got == "0110"

    def test_bits_rejects_a_non_binary_string(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "2x", "Minifuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "must be a string of 0s and 1s" in capsys.readouterr().err

    def test_bits_on_a_reader_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "01", "brainfuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "reads its inputs" in capsys.readouterr().err


class TestDescribeHidesInputFieldsWithNoInput:
    """An input shape for a language that reads no stdin is noise."""

    def test_a_template_language_hides_them(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And names the flag that supplies the bits instead."""
        out = call_main(["describe", "Minifuck"], capsys)
        assert "input_shape" not in out
        assert "generate --bits" in out

    def test_a_reading_language_still_shows_them(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The fields are the point for the languages that have them."""
        out = call_main(["describe", "Fargo"], capsys)
        assert "input_shape" in out
        assert "row_index" in out

    def test_the_api_keeps_every_key(self) -> None:
        """Uniform keys are what a zero-branch caller iterates."""
        keys = {frozenset(esolangs.describe(n)) for n in esolangs.list_languages()}
        assert len(keys) == 1


class TestVersion:
    def test_version_is_a_flag_not_an_unknown_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["--version"], capsys)
        assert exc.value.code == 0
        assert esolangs.__version__ in capsys.readouterr().out
