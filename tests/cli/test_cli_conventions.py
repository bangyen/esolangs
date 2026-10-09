"""What the CLI makes discoverable: examples, specs, usage and templates."""

import pathlib
import re
from importlib.resources import files
from pathlib import Path

import pytest

import esolangs
from esolangs.cli import HELP, USAGE
from tests.cli.test_cli import call_main


class TestExamplesShipWithThePackage:
    """They lived at the repository root, which left them out of the wheel."""

    def test_every_language_reports_one(self) -> None:
        """Every implemented language reports a committed program."""
        populated = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["examples"]
        ]
        assert set(populated) == {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["boolean_generator"]
        }

    def test_every_reported_path_exists(self) -> None:
        """A path reported and absent is worse than none reported."""
        for name in esolangs.list_languages():
            for path in esolangs.describe(name)["examples"]:
                assert not pathlib.Path(path).is_absolute(), (name, path)
                assert (files("esolangs") / path).is_file(), (name, path)

    def test_the_packaging_declares_them(self) -> None:
        """The other half: inside the package *and* listed as data."""
        config = (pathlib.Path(__file__).parents[2] / "pyproject.toml").read_text()
        declared = re.search(r"^esolangs = \[(.+?)\]", config, re.M)
        assert declared, "no package-data entry for esolangs"
        patterns = declared.group(1)
        directory = pathlib.Path(esolangs.__file__).resolve().parent / "examples"
        for suffix in {path.suffix for path in directory.iterdir()}:
            assert f"examples/*{suffix}" in patterns
        assert "examples/*/*.txt" not in patterns


class TestWikiUrlsAreUsable:
    """The wiki slug must escape what a path cannot carry."""

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
        """Parentheses and ``*`` are legal in a path and all answer 200."""
        assert esolangs.describe(name)["wiki_url"] == (
            f"https://esolangs.org/wiki/{expected}"
        )

    def test_every_url_is_a_valid_path(self) -> None:
        """No unescaped ``%`` or ``^`` anywhere in the language, which is the rule."""
        for name in esolangs.list_languages():
            url = str(esolangs.describe(name)["wiki_url"])
            slug = url.removeprefix("https://esolangs.org/wiki/")
            assert "^" not in slug, name
            assert re.fullmatch(r"[^%]*(%[0-9A-Fa-f]{2}[^%]*)*", slug), (name, slug)
            assert slug.isascii(), name

    def test_the_readme_uses_the_same_builder(self) -> None:
        """The second copy of the slug logic is what made this ship twice."""
        readme = (Path(__file__).parents[2] / "README.md").read_text()
        assert "https://esolangs.org/wiki/For%C3%BE" in readme
        assert "https://esolangs.org/wiki/Forþ" not in readme


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
        for command in HELP:
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
        assert caller < USAGE.index("debug ") < adapters
        assert adapters < USAGE.index("encode ") < catalog
        assert adapters < USAGE.index("read-answer ") < catalog
        assert catalog < USAGE.index("list ")
        assert catalog < USAGE.index("describe ")
        assert "Boolean measurement" not in USAGE

    @pytest.mark.parametrize("command", sorted(HELP))
    def test_every_documented_flag_is_summarised(self, command: str) -> None:
        """Read off each subcommand's own usage line, so it cannot drift."""
        head = HELP[command].split("\n\n")[0]
        if "[options]" in head:
            return
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
