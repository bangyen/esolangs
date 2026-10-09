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
from tests.cli_support import call_both


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
