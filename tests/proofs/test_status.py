import json
from pathlib import Path

import pytest

from esolangs.tools import _proof_status as status


def test_rendering_preserves_committed_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proofs, audits = status.load()
    files = {row.evidence.split("#", 1)[0] for row in (*proofs, *audits)}
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((status.ROOT / relative).read_bytes())
    monkeypatch.setattr(status, "ROOT", tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.md")}
    status.update_docs()
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize(
    "case", ["verdict", "totality", "duplicate", "evidence", "labels", "text"]
)
def test_invalid_status_cannot_grant_an_exemption(tmp_path: Path, case: str) -> None:
    data = json.loads(status.MANIFEST.read_text())
    if case == "verdict":
        data["audit"][0]["output_size"] = "Linera"
    elif case == "totality":
        data["audit"][0]["totality"] = "Unknown"
    elif case == "duplicate":
        data["ledger"].append(data["ledger"][0])
    elif case == "evidence":
        data["ledger"][0]["evidence"] = "docs/missing.md"
    elif case == "labels":
        data["ledger"][0]["labels"] = []
    else:
        data["ledger"][0]["scaling"] = False
    path = tmp_path / "status.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=r"invalid|unknown|duplicate|missing"):
        status.load(path)
