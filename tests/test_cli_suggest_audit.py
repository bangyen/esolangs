"""Audit-driven previews preserve data and execute only after manual repair."""

import pytest

import esolangs
from esolangs.cli_suggest import (
    _brainif_corrections,
    _collatz_corrections,
    _grapheme_corrections,
)
from tests.cli_support import call_both


def repaired(source, edits):
    for edit in reversed(edits):
        source = source[: edit.start] + edit.after + source[edit.end :]
    return source


@pytest.mark.parametrize(
    ("language", "handler", "source", "output"),
    [
        ("BrainIf", _brainif_corrections, "IF 0 incremnt\nif 1 ouput", "\x01"),
        ("BrainIf", _brainif_corrections, "if 0 mov right\nif 0 output", "\x00"),
        ("BrainIf", _brainif_corrections, "if 0 move rihgt\nif 0 output", "\x00"),
        ("Grapheme", _grapheme_corrections, "FAFy", "1"),
        ("Collatz Multiverse", _collatz_corrections, "a = b x + c, do PRNIT.", "\x00"),
        ("Collatz Multiverse", _collatz_corrections, "a = b x + c, NTO PRINT.", ""),
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
        ("FaF", ""),
        ("HyH", ""),
        ("eabey", "AB"),
        ("fabfy", "12"),
        ("fafhyhi", "1"),
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
        (")", "unmatched Underload", "open the string"),
        ("!", "stack underflow", "leave enough stack entries"),
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


@pytest.mark.parametrize(
    ("language", "module", "source"),
    [
        ("BrainIf", "tape_based.brainif", "IF 0 goto 1"),
        ("Grapheme", "stack_based.grapheme", "FAFy"),
        (
            "Collatz Multiverse",
            "register_based.collatz_multiverse",
            "a = b x + c, do PRINT.",
        ),
    ],
)
def test_new_previews_do_not_step_machines(
    language, module, source, tmp_path, capsys, monkeypatch
):
    import importlib

    machine = vars(importlib.import_module(f"esolangs.interpreters.{module}"))[
        "_Machine"
    ]

    def forbidden(*_args):
        raise AssertionError("preview executed the program")

    monkeypatch.setattr(machine, "step", forbidden)
    path = tmp_path / "program"
    path.write_text(source)
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert "->" in out
    assert not err
