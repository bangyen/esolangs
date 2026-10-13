"""Native regression for packed join-landing spacing."""

import pytest

from esolangs.languages.line.generator.forward import packed_streaming_canvas
from esolangs.languages.line.tests import test_boolean_line_forward as controls
from esolangs.languages.line.tests.test_boolean_line_forward import _check

# 0xFAC748EF: a landing adjacent to a foreign rail, where the rejected
# one-unit pitch read row 01010 as 1 instead of 0.
_LANDING_TABLE = "11111010110001110100100011101111"


@pytest.fixture
def packed_check(monkeypatch):
    """Run ``_check`` against the shipped packed streaming layout."""
    monkeypatch.setattr(controls, "forward_canvas", packed_streaming_canvas)
    return _check


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2], ids=["scale1", "scale2"])
def test_landing_table_executes_every_row(packed_check, tmp_path, scale) -> None:
    """Execute all rows with command, workspace, and admission checks."""
    packed_check(_LANDING_TABLE, tmp_path, scale=scale)
