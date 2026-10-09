"""Packlang through the shared API, CLI and machinery."""

import pytest

import esolangs
from esolangs.interpreters.other.packlang import (
    suggest_corrections as _packlang_corrections,
)
from tests.cli.test_cli_suggest import _repaired
from tests.cli_support import call_both


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
