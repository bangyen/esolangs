"""Grammar-aware previews preserve operands and user-defined identifiers."""

import pytest

import esolangs
from esolangs.cli_suggest import _bitdeque_corrections, _packlang_corrections
from tests.cli_support import call_both


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
        ("INVRET PUSH", "1"),
        ("INVERT GOT 2 pussh", "1"),
        ("INVERT PUSH INVERT INJEC", "0 1"),
        ("INVERT PUSH EJEC PUSH", "1"),
    ],
)
def test_bitdeque_proposed_repairs_execute(source, output):
    corrections = _bitdeque_corrections(source)
    assert corrections
    assert esolangs.run("Bitdeque", _repaired(source, corrections), timeout=5) == output


@pytest.mark.parametrize("source", ["IJECT", "GOTO pussh", "PUSH 12", "INVERTPUSH", ""])
def test_bitdeque_ambiguous_words_and_jump_operands_receive_no_edit(source):
    assert _bitdeque_corrections(source) == ()


@pytest.mark.parametrize(
    "source",
    [
        "package : IO { integer main { charPut(65); } } app;",
        "Pacakge : IO { Integre main { charPut(65); } } app;",
        "Package : IO { Array(Chra, 2) a; Integer main { charPut(65); } } app;",
        "Package : IO { Integer main { If 1 Thne { charPut(65); } } } app;",
        "Package : IO { Integer main { While 0 do { 0; } charPut(65); } } app;",
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
        "Package { Integer main { Array(Integre,4); } } app;",
        "% Pacakge Integre\nPackage { Integer main { 0; } } app;",
        "%$ Pacakge\nIntegre % Package { Integer main { 0; } } app;",
        "Package { Integer main { 0; } } app; %$ unterminated Pacakge",
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
    from tests.test_cli import _FakeStdin

    def forbidden(*_args, **_kwargs):
        pytest.fail("preview executed or read stdin")

    monkeypatch.setattr(PacklangMachine, "step", forbidden)
    monkeypatch.setattr(BitdequeMachine, "step", forbidden)
    monkeypatch.setattr(_FakeStdin, "read", forbidden)
    source = (
        "INVERT GOTO 0"
        if language == "Bitdeque"
        else "Package : IO { Integer main { While 1 Do { charPut(65); } } } app;"
    )
    path = tmp_path / "loop.txt"
    path.write_text(source)
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert err == ""
    assert "no unambiguous command corrections" in out


@pytest.mark.parametrize(
    "source",
    [
        "",
        "Packxxxxx {} app;",
        "Package { Pointer(",
        "Package { Integer main { If 1",
        "Package { ZZZ main { 0; } } app;",
        "Package { Integer main { @; } } app;",
    ],
)
def test_packlang_preview_refuses_unsupported_syntax_before_output(
    source, tmp_path, capsys
):
    path = tmp_path / "bad.pack"
    path.write_text(source)
    with pytest.raises(SystemExit) as caught:
        call_both(["suggest", "Packlang", str(path)], capsys)
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "hint:" in captured.err


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
