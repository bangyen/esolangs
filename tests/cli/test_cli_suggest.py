"""Typo suggestions and repair previews in CLI errors."""

import pytest

import esolangs
from esolangs.cli_suggest import (
    _bitdeque_corrections,
    _brainif_corrections,
    _collatz_corrections,
    _grapheme_corrections,
    _modulous_corrections,
    _packlang_corrections,
)
from esolangs.registry import LANGUAGES, SourceKind
from tests.cli_support import call_both


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


@pytest.mark.parametrize(
    "source",
    [
        "[POT]",  # POP and PRT are both one substitution away.
        '[PSH STR "[PRTT INT]"][PRT][END]',
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


def repaired(source, edits):
    for edit in reversed(edits):
        source = source[: edit.start] + edit.after + source[edit.end :]
    return source


@pytest.mark.parametrize(
    ("language", "handler", "source", "output"),
    [
        ("BrainIf", _brainif_corrections, "IF 0 incremnt\nif 1 ouput", "\x01"),
        ("BrainIf", _brainif_corrections, "if 0 move rihgt\nif 0 output", "\x00"),
        ("Grapheme", _grapheme_corrections, "FAFy", "1"),
        ("Collatz Multiverse", _collatz_corrections, "a = b x + c, do PRNIT.", "\x00"),
    ],
)
def test_repairs_execute(language, handler, source, output, tmp_path, capsys):
    edits = handler(source)
    assert edits
    assert esolangs.run(language, repaired(source, edits), timeout=1) == output
    path = tmp_path / "program"
    path.write_text(source, encoding="utf-8")
    before = path.read_bytes()
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert "->" in out
    assert not err
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("source", "output"),
    [
        ("EaE", ""),
        ("eabey", "AB"),
    ],
)
def test_grapheme_case_corrections_include_literals(source, output, tmp_path, capsys):
    edits = _grapheme_corrections(source)
    assert repaired(source, edits) == source.upper()
    assert all(edit.after == edit.before.upper() for edit in edits)
    assert esolangs.run("Grapheme", repaired(source, edits), timeout=1) == output
    path = tmp_path / "program"
    path.write_text(source)
    out, err = call_both(["suggest", "Grapheme", str(path)], capsys)
    assert "->" in out
    assert not err
    assert path.read_text() == source


def test_grapheme_case_preview_preserves_other_characters():
    source = "Eé1?E\naY"
    assert repaired(source, _grapheme_corrections(source)) == "Eé1?E\nAY"
    assert not _grapheme_corrections("EABEYFAFY")


def test_collatz_identifiers_are_untouched():
    source = "print = do x + not, do PRNIT."
    result = repaired(source, _collatz_corrections(source))
    assert result == "print = do x + not, DO PRINT."


@pytest.mark.parametrize(
    "source", ["a = 3 x + 1, do PRINT.", "do PRNIT.", "a = b x + c, DO PRINT."]
)
def test_collatz_invalid_prefix_or_valid_source_has_no_edits(source):
    assert not _collatz_corrections(source)


@pytest.mark.parametrize(
    "source", ["if 0 goto ouput", "if ouput increment", "if 0 output junk"]
)
def test_brainif_invalid_operands_are_not_repaired(source):
    with pytest.raises(ValueError, match=r"invalid literal|malformed BrainIf"):
        _brainif_corrections(source)


def test_brainif_unicode_line_locations(tmp_path, capsys):
    path = tmp_path / "program"
    source = "\n\tIF 0 incremnt\r\nif 1 ouput"
    path.write_bytes(source.encode())
    out, err = call_both(["suggest", "BrainIf", str(path)], capsys)
    assert ":2:2: 'IF' -> 'if'" in out
    assert ":3:6: 'ouput' -> 'output'" in out
    assert not err
    assert path.read_bytes() == source.encode()


@pytest.mark.parametrize(
    ("source", "message", "hint"),
    [
        ("X", "unknown Underload command", "use () strings"),
        ("(", "unmatched Underload", "close the string"),
    ],
)
def test_underload_errors_have_the_right_hint(source, message, hint):
    with pytest.raises(esolangs.HaltError, match=message) as caught:
        esolangs.run("Underload", source, timeout=1)
    assert any(hint in note for note in caught.value.__notes__)


def test_underload_literal_text_is_preserved():
    assert esolangs.run("Underload", "(X)S", timeout=1) == "X"


def test_collatz_ambiguous_keyword_is_untouched():
    assert not _collatz_corrections("a = b x + c, DOT PRINT.")


@pytest.mark.parametrize("language", ["Befunge", "Piet"])
def test_other_languages_offer_explicit_no_edit_result(language, tmp_path, capsys):
    from PIL import Image

    path = tmp_path / "program"
    if LANGUAGES[language].source_kind == SourceKind.RASTER:
        Image.new("RGB", (1, 1), "white").save(path, format="PNG")
        reason = "raster source has no command spellings"
    else:
        path.write_text("pussh arbitrary identifiers", encoding="utf-8")
        reason = "no safe keyword correction rules"
    before = path.read_bytes()
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert reason in out
    assert "not validated" in out
    assert "->" not in out
    assert not err
    assert path.read_bytes() == before


def _repaired(source, corrections):
    for correction in reversed(corrections):
        assert source[correction.start : correction.end] == correction.before
        source = (
            source[: correction.start] + correction.after + source[correction.end :]
        )
    return source


@pytest.mark.parametrize(
    ("source", "output"),
    [
        ("inverT pussh", "1"),
        ("INVERT PUSH INVERT INJEC", "0 1"),
    ],
)
def test_bitdeque_proposed_repairs_execute(source, output):
    corrections = _bitdeque_corrections(source)
    assert corrections
    assert esolangs.run("Bitdeque", _repaired(source, corrections), timeout=5) == output


@pytest.mark.parametrize("source", ["IJECT", "PUSH 12", ""])
def test_bitdeque_ambiguous_words_and_jump_operands_receive_no_edit(source):
    assert _bitdeque_corrections(source) == ()


@pytest.mark.parametrize(
    "source",
    [
        "package : IO { integer main { charPut(65); } } app;",
        "Package : IO { Integer main { If 1 Thne { charPut(65); } } } app;",
        "Dependncy { Integer f { 65; } } d; "
        "Package : IO, d { Integer main { charPut(f()); } } app;",
    ],
)
def test_packlang_required_keyword_repairs_execute(source):
    corrections = _packlang_corrections(source)
    assert corrections
    assert esolangs.run("Packlang", _repaired(source, corrections), timeout=5) == "A"


@pytest.mark.parametrize(
    "source",
    [
        "Package : IO { Integer Integre; "
        "Integer main { INIT Integre; charPut(65); } } app;",
        "Package : IO { Integer charPutt { 65; } "
        "Integer main { charPut(charPutt()); } } app;",
        "% Pacakge Integre\nPackage { Integer main { 0; } } app;",
    ],
)
def test_packlang_identifiers_calls_and_comments_receive_no_edit(source):
    assert _packlang_corrections(source) == ()


def test_packlang_comment_mask_preserves_exact_locations_and_source(tmp_path, capsys):
    source = (
        "%$ Pacakge é\r\n Integre %\r\npackage : IO {\r\n"
        "  integer main { charPut(65); }\r\n} app;\r\n"
    )
    path = tmp_path / "program.pack"
    original = source.encode()
    path.write_bytes(original)
    out, err = call_both(["suggest", "Packlang", str(path)], capsys)
    assert err == ""
    assert out == (
        f"{path}:3:1: 'package' -> 'Package'; keyword spelling is case-sensitive\n"
        f"{path}:4:3: 'integer' -> 'Integer'; keyword spelling is case-sensitive\n"
    )
    assert path.read_bytes() == original


def test_bitdeque_multiline_cli_preview_preserves_target_and_file(tmp_path, capsys):
    path = tmp_path / "program.bd"
    source = "inverT\r\nGOT 2\r\n  pussh\r\n"
    path.write_bytes(source.encode())
    out, err = call_both(["suggest", "Bitdeque", str(path)], capsys)
    assert err == ""
    assert f"{path}:1:1: 'inverT' -> 'INVERT'" in out
    assert f"{path}:2:1: 'GOT' -> 'GOTO'" in out
    assert f"{path}:3:3: 'pussh' -> 'PUSH'" in out
    assert "'2' ->" not in out
    assert path.read_bytes() == source.encode()


@pytest.mark.parametrize("language", ["Bitdeque", "Packlang"])
def test_new_previews_do_not_execute_or_read_stdin(
    language, tmp_path, capsys, monkeypatch
):
    from esolangs.interpreters.other.packlang import _Machine as PacklangMachine
    from esolangs.interpreters.queue_based.bitdeque import _Machine as BitdequeMachine
    from tests.cli.test_cli import _FakeStdin

    def forbidden(*_args, **_kwargs):
        pytest.fail("preview executed or read stdin")

    monkeypatch.setattr(PacklangMachine, "step", forbidden)
    monkeypatch.setattr(BitdequeMachine, "step", forbidden)
    monkeypatch.setattr(_FakeStdin, "read", forbidden)
    source = (
        "INVERT GOTO 2"
        if language == "Bitdeque"
        else "Package : IO { Integer main { While 1 Do { charPut(65); } } } app;"
    )
    path = tmp_path / "loop.txt"
    path.write_text(source)
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert err == ""
    assert "no unambiguous command corrections" in out


def test_packlang_deep_preview_reports_parser_limit(tmp_path, capsys):
    path = tmp_path / "deep.pack"
    path.write_text("Package { " + "Pointer(" * 2000 + "Integer" + ")" * 2000 + " x; }")
    with pytest.raises(SystemExit) as caught:
        call_both(["suggest", "Packlang", str(path)], capsys)
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "source preview exceeds parser recursion depth" in captured.err
    assert "reduce expression nesting" in captured.err
