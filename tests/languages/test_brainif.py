"""BrainIf through the shared API, CLI and machinery."""

import pytest

from esolangs.interpreters.tape_based.brainif import (
    suggest_corrections as _brainif_corrections,
)
from tests.cli_support import assert_repair_runs, call_both


def test_brainif_unicode_line_locations(tmp_path, capsys):
    path = tmp_path / "program"
    source = "\n\tIF 0 incremnt\r\nif 1 ouput"
    path.write_bytes(source.encode())
    out, err = call_both(["suggest", "BrainIf", str(path)], capsys)
    assert ":2:2: 'IF' -> 'if'" in out
    assert ":3:6: 'ouput' -> 'output'" in out
    assert not err
    assert path.read_bytes() == source.encode()


@pytest.mark.medium
@pytest.mark.parametrize("guard", [0, 1])
def test_brainif_unknown_command_is_a_cli_source_error(guard, tmp_path, capsys):
    path = tmp_path / "bad.brainif"
    path.write_text(f"if {guard} incremnt", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        call_both(["run", "BrainIf", str(path)], capsys)
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "unknown BrainIf command" in captured.err
    assert "did you mean 'increment'" in captured.err


@pytest.mark.parametrize(
    ("source", "output"),
    [("IF 0 incremnt\nif 1 ouput", "\x01"), ("if 0 move rihgt\nif 0 output", "\x00")],
)
def test_brainif_repairs_execute(source, output, tmp_path, capsys):
    assert_repair_runs("BrainIf", source, output, tmp_path, capsys)


@pytest.mark.parametrize(
    "source", ["if 0 goto ouput", "if ouput increment", "if 0 output junk"]
)
def test_brainif_invalid_operands_are_not_repaired(source):
    with pytest.raises(ValueError, match=r"invalid literal|malformed BrainIf"):
        _brainif_corrections(source)
