"""BrainIf through the shared API, CLI and machinery."""

import pytest

from tests.support.cli_support import call_both


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
