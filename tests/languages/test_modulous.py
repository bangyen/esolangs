"""Modulous through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from esolangs import vm
from esolangs.exceptions import HaltError
from esolangs.interpreters.stack_based.modulous import (
    suggest_corrections as _modulous_corrections,
)
from esolangs.vm import make_vm
from tests.cli.test_cli import call_main
from tests.cli_support import _failure, call_both
from tests.test_vm import assert_random_steps_reproduce


class TestModulousSaysWhatWentWrong:
    """Four halts raised ``HaltError`` with the empty string as a message."""

    @pytest.mark.parametrize(
        ("program", "expected"),
        [
            ("[POP][END]", "stack is empty"),
            ('[PSH STR "x"][SWP][END]', "SWP needs two values"),
            ("[PRT VAR9][END]", "not a defined variable"),
            ("[RND 0][END]", "at least 1"),
        ],
    )
    def test_each_halt_names_its_cause(self, program: str, expected: str) -> None:
        """Not the class, the sentence: an empty message helps nobody."""
        with pytest.raises(esolangs.HaltError, match=expected):
            esolangs.run("Modulous", program, stdin="")


@pytest.mark.parametrize(
    "source",
    [
        "[PSHH INT 1][PRTT INT][END]",
        "[pSh INT 1][prt INT][end]",
    ],
)
def test_proposed_command_edits_execute(source):
    corrections = _modulous_corrections(source)
    assert corrections
    for correction in reversed(corrections):
        assert source[correction.start : correction.end] == correction.before
        source = (
            source[: correction.start] + correction.after + source[correction.end :]
        )
    assert esolangs.run("Modulous", source) == "1"


def test_preview_reports_unicode_line_and_column_and_keeps_file(tmp_path, capsys):
    source = '[PSH STR "é"]\r\n[ PRRT INT]\r\n[ENDD]\r\n'
    path = tmp_path / "program.mod"
    original = source.encode()
    path.write_bytes(original)
    out, err = call_both(["suggest", "modulous", str(path)], capsys)
    assert err == ""
    assert out == (
        f"{path}:2:3: 'PRRT' -> 'PRT'; "
        "one spelling edit from a unique command keyword\n"
        f"{path}:3:2: 'ENDD' -> 'END'; "
        "one spelling edit from a unique command keyword\n"
    )
    assert path.read_bytes() == original
    repaired = source.replace("PRRT", "PRT").replace("ENDD", "END")
    assert esolangs.run("Modulous", repaired) == "233"


def test_preview_does_not_execute_even_a_loop_or_read_input(
    tmp_path, capsys, monkeypatch
):
    from esolangs.interpreters.stack_based.modulous import _Machine
    from tests.cli.test_cli import _FakeStdin

    def forbidden(*_args, **_kwargs):
        pytest.fail("preview executed a program")

    monkeypatch.setattr(_Machine, "step", forbidden)
    monkeypatch.setattr(_FakeStdin, "read", forbidden)
    path = tmp_path / "loop.mod"
    path.write_text("[INP][JMP B 1]")
    out, err = call_both(["suggest", "Modulous", str(path)], capsys)
    assert err == ""
    assert "no unambiguous command corrections found" in out
    assert "not validated" in out


@pytest.mark.parametrize("content", [b"[PSHH INT 1", b"\xff"])
def test_malformed_source_is_refused_before_preview(content, tmp_path, capsys):
    path = tmp_path / "bad.mod"
    path.write_bytes(content)
    with pytest.raises(SystemExit) as caught:
        call_both(["suggest", "Modulous", str(path)], capsys)
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "hint:" in captured.err
    assert path.read_bytes() == content


def test_same_line_case_and_typo_previews_have_exact_columns(tmp_path, capsys):
    path = tmp_path / "program.mod"
    path.write_text("[pSh INT 1][PRTT INT]")
    out, err = call_both(["suggest", "Modulous", str(path)], capsys)
    assert err == ""
    assert out == (
        f"{path}:1:2: 'pSh' -> 'PSH'; command keywords are uppercase\n"
        f"{path}:1:13: 'PRTT' -> 'PRT'; "
        "one spelling edit from a unique command keyword\n"
    )


@pytest.mark.medium
def test_vm_runtime_error_keeps_its_hint():
    vm = make_vm("Modulous", "[JMP F]", stdin="")
    with pytest.raises(esolangs.ProgramError, match="missing operand") as caught:
        vm.step()
    assert "required operand" in caught.value.__notes__[0]


@pytest.mark.medium
@pytest.mark.parametrize("command", ["run", "debug"])
def test_cli_prints_runtime_hints(command, tmp_path: Path, capsys):
    source = tmp_path / "bad.mod"
    source.write_text("[JMP F]", encoding="utf-8")
    args = [command, "--timeout", "1", "Modulous", str(source)]
    with pytest.raises(SystemExit):
        call_both(args, capsys)
    streams = capsys.readouterr()
    text = streams.out + streams.err
    assert "missing operand in JMP F" in text
    assert "hint: supply the required operand" in text


@pytest.mark.medium
def test_tui_displays_a_runtime_hint():
    from esolangs.tui import render, replay

    frame = replay("Modulous", "[JMP F]", "", step=1)
    assert "hint: supply the required operand" in render(frame, width=120)


@pytest.mark.medium
def test_hints_do_not_discard_partial_output():
    with pytest.raises(esolangs.ProgramError, match="missing operand") as caught:
        esolangs.run("Modulous", "[PSH INT 65][PRT][JMP F]", timeout=1)
    assert caught.value.partial_output == "A"
    assert "hint:" in caught.value.__notes__[0]
    assert "printed 'A'" in caught.value.__notes__[1]


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.medium
def test_runtime_error_keeps_partial_output_and_one_hint(isolated):
    with pytest.raises(HaltError) as caught:
        esolangs.run("Modulous", "[PSH INT 65][PRT][SWP]", isolated=isolated)
    assert str(caught.value) == "SWP needs two values on the stack and there are 0"
    assert caught.value.partial_output == "A"
    assert caught.value.__notes__[0] == "hint: push two values before SWP"
    assert sum(note.startswith("hint:") for note in caught.value.__notes__) == 1


@pytest.mark.medium
def test_vm_and_tui_display_runtime_hints():
    from esolangs.tui import render, replay

    machine = make_vm("Modulous", "[SWP]", stdin="")
    with pytest.raises(HaltError) as caught:
        machine.step()
    assert caught.value.__notes__ == ["hint: push two values before SWP"]
    assert "hint: push two values" in render(replay("Modulous", "[SWP]", "", step=1))


@pytest.mark.medium
def test_cli_displays_runtime_hints(tmp_path, capsys):
    source = tmp_path / "runtime.mod"
    source.write_text("[SWP]")
    with pytest.raises(SystemExit):
        call_both(["run", "Modulous", str(source)], capsys)
    assert "hint: push two values before SWP" in capsys.readouterr().err


@pytest.mark.medium
def test_fixed_input_does_not_make_branch_input_forkable():
    source = "[INP INT][PRT INT][END]"
    with pytest.raises(TimeoutError) as caught:
        vm.run_until_halt_or_all_branches_cycle(
            vm.make_vm("Modulous", source, stdin="42\n")
        )
    assert str(caught.value) == (
        "undecided: a branching transition needs input that cannot be safely forked"
    )
    assert "seeded single-path run" in caught.value.__notes__[0]
    assert "does not decide all random paths" in caught.value.__notes__[0]
    assert esolangs.run("Modulous", source, stdin="42\n", seed=1, timeout=1) == "42"


# 2.0s over 21 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 2.0s over 21 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 2.0s over 21 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestOutputSurvivesAFailure:
    """A run that failed emitted nothing at all, and it had the bytes."""

    PRINTS_THEN_FAILS = '[PSH STR "Hi"][PRT STR][PRT STR][POP][END]'
    LOOPS_PRINTING = "[PSH INT 9][PRT INT][JMP B 2][END]"

    def test_a_halt_carries_what_was_printed(self) -> None:
        """The attribute, which is what the CLI reads."""
        with pytest.raises(esolangs.HaltError) as caught:
            esolangs.run("Modulous", self.PRINTS_THEN_FAILS, stdin="")
        assert caught.value.partial_output == "Hi"

    def test_it_is_in_the_traceback_too(self) -> None:
        """The note, for anyone who only sees the traceback."""
        with pytest.raises(esolangs.HaltError) as caught:
            esolangs.run("Modulous", self.PRINTS_THEN_FAILS, stdin="")
        assert "printed 'Hi'" in "\n".join(getattr(caught.value, "__notes__", []))

    def test_a_timeout_carries_it(self) -> None:
        """The case that matters most: a loop you meant to be finite."""
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            esolangs.run("Modulous", self.LOOPS_PRINTING, stdin="", timeout=0.01)
        assert caught.value.partial_output.startswith("999")

    def test_an_error_before_the_run_carries_nothing(self) -> None:
        """Empty is the honest answer when the program never started."""
        with pytest.raises(esolangs.UnknownLanguageError) as unknown:
            esolangs.run("nosuchlang", "+", stdin="")
        assert unknown.value.partial_output == ""
        with pytest.raises(esolangs.ProgramError) as bad:
            esolangs.run("brainfuck", "[[[", stdin="")
        assert bad.value.partial_output == ""

    def test_a_successful_run_is_unchanged(self) -> None:
        """The attribute is for failures; success returns as it always did."""
        assert esolangs.run("brainfuck", "+++.", stdin="") == "\x03"

    def test_the_cli_prints_it_before_the_error(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """On stdout, where a successful run puts it, so a pipe sees the same."""
        path = tmp_path / "m.txt"
        path.write_text(self.PRINTS_THEN_FAILS)
        with pytest.raises(SystemExit) as exit_code:
            call_main(["run", "--timeout", "5", "Modulous", str(path)], capsys)
        captured = capsys.readouterr()
        assert captured.out.startswith("Hi")
        assert "stack is empty" in captured.err
        assert exit_code.value.code == 1

    def test_the_cli_says_nothing_extra_when_there_was_nothing(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """A program that printed nothing must not gain a blank line."""
        path = tmp_path / "m.txt"
        path.write_text("[POP][END]")
        with pytest.raises(SystemExit):
            call_main(["run", "--timeout", "5", "Modulous", str(path)], capsys)
        assert capsys.readouterr().out == ""


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source", "hint", "code", "output"),
    [
        ("brainfuck", "[", "close this '[' with ']'", 2, ""),
        ("Modulous", "[PSH INT 65][PRT][SWP]", "push two values before SWP", 1, "A\n"),
        ("brainfuck", "+.,", "at least 1 input character", 1, "\x01\n"),
    ],
)
def test_isolated_cli_preserves_error_hint_and_partial_output(
    language, source, hint, code, output, tmp_path: Path, capsys
):
    path = tmp_path / "program.txt"
    path.write_text(source)
    direct = _failure(["run", language, str(path)], capsys, code)
    isolated = _failure(["run", "--isolated", language, str(path)], capsys, code)
    assert direct == isolated
    assert direct[0] == output
    assert hint in direct[1]
    assert direct[1].count("hint:") == 1


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["Modulous"], "missing <program-file>"),
        (["brainfuck", "missing"], "cannot read"),
        (["unknown", "missing"], "unknown language"),
        (["Modulous", "missing"], "cannot read"),
        (["--apply", "Modulous", "missing"], "unknown option"),
    ],
)
def test_suggest_usage_errors(args, message, capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(["suggest", *args], capsys)
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err


@pytest.mark.medium
def test_halt_and_cycle_verdicts_are_unchanged():
    assert vm.run_until_halt_or_cycle(vm.make_vm("brainfuck", "+."), limit=10) is True
    assert vm.run_until_halt_or_cycle(vm.make_vm("brainfuck", "+[]"), limit=10) is False
    assert (
        vm.run_until_halt_or_growth(vm.make_vm("brainfuck", "+[>+]"), limit=100)
        is False
    )
    assert (
        vm.run_until_halt_or_all_branches_cycle(vm.make_vm("Modulous", "[END]")) is True
    )


@pytest.mark.parametrize(
    "source",
    [
        "[POT]",  # POP and PRT are both one substitution away.
        '[PSH STR "[PRTT INT]"][PRT][END]',
        "",
        "[123][END]",
        '["x"][END]',
    ],
)
def test_ambiguous_spellings_and_noncommand_text_receive_no_edit(source):
    assert _modulous_corrections(source) == ()


def test_stepping_through_the_random_instruction_is_reproducible() -> None:
    """Its random instruction steps the same way twice under one seed."""
    assert_random_steps_reproduce("Modulous", "[RND 9][PRT INT]")
