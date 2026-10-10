"""Sophie through the shared API, CLI and machinery."""

import difflib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import esolangs
from esolangs import vm
from esolangs.cli_hints import _did_you_mean
from esolangs.registry import _BY_ID, SUGGESTION_CUTOFF, canonical_id
from tests.cli.test_cli import call_main, run_cli


# Every test here spawns `python -m esolangs.cli`; 2.8s over nine tests.
@pytest.mark.medium
class TestSubprocess:
    def test_run(self, tmp_path: Path) -> None:
        program = tmp_path / "prog.soph"
        program.write_text(esolangs.generate("Sophie", "0110"))
        result = run_cli("run", "Sophie", str(program), stdin="01")
        assert result.returncode == 0
        assert result.stdout == "1"


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        import runpy

        with patch.object(sys, "argv", ["esolangs", "generate", "Sophie", "0110"]):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run("Sophie", out, stdin="01") == "1"


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "hint"),
    [
        ("run_until_halt_or_all_branches_cycle", "branching_successors"),
        ("run_until_halt_or_ancestor", "frame_entry_key"),
        ("run_until_halt_or_growth", "rightward-growing tape"),
        ("run_until_halt_or_value_growth", "unbounded affine values"),
    ],
)
def test_unsupported_detectors_name_the_needed_capability(detector, hint):
    with pytest.raises(TypeError) as caught:
        getattr(vm, detector)(vm.make_vm("Sophie", ""))
    assert type(caught.value) is TypeError
    assert str(caught.value).startswith("Sophie is not ")
    assert hint in caught.value.__notes__[0]


class TestWidthEffectSaysWhatWidthDoes:
    """One flag, three behaviours, and no way to tell them apart."""

    def test_layout_is_exactly_the_width_aware_generators(self) -> None:
        """The old field is the new field's `layout` case, and only that."""
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            assert (facts["width_effect"] == "layout") == facts["width_aware"], name

    @pytest.mark.slow
    def test_the_declaration_matches_what_width_actually_does(self) -> None:
        """The drift guard: `none` must really be a no-op."""
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["boolean_generator"]:
                continue
            plain = esolangs.generate(name, "0110")
            narrow = esolangs.generate(name, "0110", width=20)
            if facts["width_effect"] == "none" and plain != narrow:
                wrong.append(f"{name}: declared none but --width changed it")
            # `wrap` and `layout` may coincide on a program already narrower
            # than the width, so only the `none` direction is decidable here.
        assert not wrong, "\n".join(wrong)

    def test_a_wrapping_language_really_reflows(self) -> None:
        """The positive control for the check above, which only tests `none`."""
        wide = esolangs.generate("Sophie", "0110")
        narrow = esolangs.generate("Sophie", "0110", width=10)
        assert "\n" not in wide
        assert "\n" in narrow
        assert esolangs.describe("Sophie")["width_effect"] == "wrap"


@pytest.mark.medium
def test_worker_thread_loads_unicode_path(tmp_path: Path) -> None:
    source = tmp_path / "λ program.sophie"
    source.write_text("#λ,", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            esolangs.run, "Sophie", source, isolated=True, max_output=1
        )
        assert result.result(timeout=10) == "λ"


class TestArgumentHygiene:
    """A mistyped command is reported where the mistake is."""

    def test_a_file_named_like_an_option_is_still_reachable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Which is what the old permissiveness was protecting; `--` says so."""
        path = tmp_path / "--x"
        path.write_text("+.")
        out = call_main(["run", "--", "brainfuck", str(path)], capsys)
        assert out == "\x01"

    def test_a_bare_width_explains_the_argument_it_shifted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width abc Sophie 0110`` reported ``unknown language: abc``."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--width", "abc", "Sophie", "0110"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "unexpected argument: '0110'" in err
        # The message must name the word that was shifted, not just describe
        # the rule: the complaint was that it never said what 'abc' became.
        assert "'abc' was read as the language" in err

    def test_list_takes_no_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["list", "extra"], capsys)
        assert exc.value.code == 2


class TestASuggestionIsWorthLessThanSilence:
    """0.6 offers ``Nope.`` for ``snorey``."""

    #: Single-edit slips of a real name, as a person makes them.
    @staticmethod
    def _typos(name: str) -> list[str]:
        """Dropped and transposed characters, keeping only real misses."""
        out = [name[:-1], name[0] + name[2:], name[1:]]
        if len(name) > 4:
            out.append(name[:2] + name[3:])
            out.append(name[:2] + name[3] + name[2] + name[4:])
        return [
            typo
            for typo in dict.fromkeys(out)
            if typo and canonical_id(typo) not in _BY_ID
        ]

    _JUNK = ("snorey", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo")

    def _score(self, cutoff: float) -> tuple[int, int, int]:
        """Return (typos rescued, typos tried, junk words given a guess)."""
        rescued = tried = 0
        for name in esolangs.list_languages():
            for typo in self._typos(name):
                tried += 1
                close = difflib.get_close_matches(
                    canonical_id(typo), _BY_ID, n=2, cutoff=cutoff
                )
                rescued += name in [_BY_ID[c] for c in close]
        junk = sum(
            bool(difflib.get_close_matches(canonical_id(w), _BY_ID, n=2, cutoff=cutoff))
            for w in self._JUNK
        )
        return rescued, tried, junk

    def test_the_cutoff_is_the_best_available_number(self) -> None:
        """The trade, recomputed: 0.6 costs junk and 0.7 costs rescues."""
        shipped = self._score(SUGGESTION_CUTOFF)
        assert shipped[2] == 0, "the shipped cutoff offers a guess for junk"
        # Lower: the same rescues, but junk comes back.  This is the
        # positive control -- without it the cutoff could be doing nothing.
        assert self._score(0.6)[0] == shipped[0]
        # Which names draw junk at 0.6 moves with the registry, so the
        # control sits a step lower, where some always do.
        assert self._score(0.5)[2] > 0
        # Higher: no junk either, but it starts costing real rescues.
        assert self._score(0.7)[0] < shipped[0]

    def test_a_word_that_is_not_close_gets_no_guess(self) -> None:
        """It gets the command that lists them, which is the honest answer."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("snorey")
        assert "did you mean" not in str(caught.value)
        assert "`esolangs list` shows all of them" in str(caught.value)

    @pytest.mark.parametrize(
        ("typo", "wanted"),
        [
            ("Brainfck", "brainfuck"),
            ("Sofie", "Sophie"),
        ],
    )
    def test_a_real_typo_is_still_rescued(self, typo: str, wanted: str) -> None:
        """The half of the trade that raising a cutoff can quietly cost."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe(typo)
        assert wanted in str(caught.value)

    def test_the_cli_shares_the_number(self) -> None:
        """Its docstring promised the same cutoff while keeping its own copy."""
        assert _did_you_mean("snorey", esolangs.list_languages()) == ""
        assert "--width" in _did_you_mean("--wdith", ["--width", "--bits"])


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "options", "code", "output", "diagnostic"),
    [
        ("Sophie", "#λ,", [], 0, "λ", ""),
        ("Sophie", "#λ,,", ["--max-output", "1"], 1, "λ\n", "output limit"),
        # Sophie's ';' reads 0 at EOF, so the input error comes from brainfuck.
        ("brainfuck", ",", [], 1, "", "input"),
        ("Sophie", ";.", [], 0, "0", ""),
    ],
)
def test_cli_unicode_path_and_error(
    tmp_path: Path,
    language: str,
    source: str,
    options: list[str],
    code: int,
    output: str,
    diagnostic: str,
) -> None:
    path = tmp_path / "λ program.sophie"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "esolangs",
            "run",
            "--isolated",
            *options,
            language,
            str(path),
        ],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == code
    assert result.stdout == output
    assert diagnostic in result.stderr.lower()


@pytest.mark.medium
def test_output_limit_accepts_exact_length_and_unicode():
    assert esolangs.run("brainfuck", "", isolated=True, max_output=0) == ""
    assert esolangs.run("Sophie", "#λ,", isolated=True, max_output=1) == "λ"
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        esolangs.run("Sophie", "#λ,,", isolated=True, max_output=1)
    assert caught.value.partial_output == "λ"


def _bounds(profile: dict[str, Any]) -> None:
    """The construction bounds the resource audit holds this generator to."""
    units = profile["source_units"]
    commands = profile["worst_row_commands"]
    memory = profile["peak_memory_cells"]
    stack = profile["peak_stack_items"]
    # No loop opcode: each executed command advances the source cursor.
    assert commands <= units
    assert memory == 1
    assert stack == 0
    assert profile["peak_control_stack_items"] == 0
    assert profile["peak_machine_bits"] <= 8 + units.bit_length() + 2


@pytest.mark.medium
def test_resource_bounds() -> None:
    """The resource audit counts a UTF-8 byte per source unit."""
    from scripts.screens.resources import audit, corpus

    result = audit("Sophie", 3, corpus(3)["parity"], _bounds)
    assert result["source_utf8_bits"] == 8 * result["source_units"]
