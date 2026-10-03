"""Spelling previews propose executable edits without running or writing source."""

import pytest

import esolangs
from esolangs.cli_suggest import _modulous_corrections
from tests.cli_support import call_both


@pytest.mark.parametrize(
    "source",
    [
        "[PSHH INT 1][PRTT INT][END]",
        "[PHS INT 1][PRT INT][END]",
        "[PH INT 1][PRT INT][END]",
        "[pSh INT 1][prt INT][end]",
        "[PSX INT 1][PRT INT][END]",
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


@pytest.mark.parametrize(
    "source",
    [
        "[POT]",  # POP and PRT are both one substitution away.
        "[PND]",  # END and RND are both one substitution away.
        "[PRTINT]",  # More than one spelling edit; could need an operand.
        '[PSH STR "[PRTT INT]"][PRT][END]',
        "[VAR1+1][VAR2-1][PSH VAR1][PRT VAR2][END]",
        "[PSH INT nope][PRT INT]",
        "[][JMP B 1]",
        "",
    ],
)
def test_ambiguous_spellings_and_noncommand_text_receive_no_edit(source):
    assert _modulous_corrections(source) == ()


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
    from tests.test_cli import _FakeStdin

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


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["Modulous"], "missing <program-file>"),
        (["brainfuck", "missing"], "support Modulous, Bitdeque and Packlang"),
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
