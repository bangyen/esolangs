"""The workspace proof reads named addresses and checks the emitted operands."""

import pytest

import esolangs
from esolangs.generation import packed_decoder as packed
from esolangs.languages.subleq.proof_formulas import workspace_terms


def test_relocated_named_cells_execute_and_corrupt_load_is_rejected(monkeypatch):
    table = "0110"
    values = packed._cell_values

    def relocated(n, *, direct):
        return dict(reversed(values(n, direct=direct).items()))

    monkeypatch.setattr(packed, "_cell_values", relocated)
    source = packed.packed_decoder(table, direct=True)
    cells = list(map(int, source.split()))
    regions = packed.read_direct_layout(cells, 2)
    assert regions.cells["ZERO"] > regions.cells["OUT"]
    assert workspace_terms(2, source)["M"] == 2
    for row, bit in enumerate(table):
        assert esolangs.run("Subleq", source, stdin=f"{row:02b}").unwrap().output == bit
    cells[regions.chunk_load] += 1
    with pytest.raises(ValueError, match="packed"):
        workspace_terms(2, " ".join(map(str, cells)))
