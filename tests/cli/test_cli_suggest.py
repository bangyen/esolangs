"""Typo suggestions and repair previews in CLI errors."""

import pytest

import esolangs
from esolangs.interpreters.other.packlang import (
    suggest_corrections as _packlang_corrections,
)
from esolangs.interpreters.queue_based.bitdeque import (
    suggest_corrections as _bitdeque_corrections,
)
from esolangs.interpreters.register_based.collatz_multiverse import (
    suggest_corrections as _collatz_corrections,
)
from esolangs.interpreters.stack_based.grapheme import (
    suggest_corrections as _grapheme_corrections,
)
from esolangs.interpreters.stack_based.modulous import (
    suggest_corrections as _modulous_corrections,
)
from esolangs.interpreters.tape_based.brainif import (
    suggest_corrections as _brainif_corrections,
)
from esolangs.registry import LANGUAGES, SourceKind
from tests.cli_support import call_both


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


@pytest.mark.parametrize("source", ["IJECT", "PUSH 12", ""])
def test_bitdeque_ambiguous_words_and_jump_operands_receive_no_edit(source):
    assert _bitdeque_corrections(source) == ()


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


@pytest.mark.parametrize(
    "source",
    [
        # Speculative parsing of a declaration rewrites nothing in it.
        "Package : IO { Integer main { Array(Integer, 2) a; charPut(65); } } app;",
        "Package : IO { Integer main { While 0 Do { charPut(65); } "
        "charPut(65); } } app;",
    ],
)
def test_packlang_speculation_and_spelled_keywords_receive_no_edit(source):
    assert _packlang_corrections(source) == ()


@pytest.mark.parametrize("source", ["[123][END]", '["x"][END]'])
def test_modulous_tokens_without_a_keyword_receive_no_edit(source):
    assert _modulous_corrections(source) == ()
