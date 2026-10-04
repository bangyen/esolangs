import json
from pathlib import Path

import pytest

from esolangs.tools import _proof_status as status


def test_rendering_preserves_committed_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proofs, audits = status.load()
    files = {row.evidence.split("#", 1)[0] for row in (*proofs, *audits)}
    files.update({"docs/proofs/index.md", "docs/roadmap.md"})
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((status.ROOT / relative).read_bytes())
    monkeypatch.setattr(status, "ROOT", tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.md")}
    status.update_docs()
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize(
    "case",
    [
        "verdict",
        "totality",
        "duplicate",
        "evidence",
        "anchor",
        "imprecise",
        "labels",
        "text",
    ],
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
    elif case == "anchor":
        data["audit"][0]["evidence"] = "docs/proofs/index.md#missing-heading"
    elif case == "imprecise":
        data["audit"][0]["evidence"] = "docs/proofs/index.md"
    elif case == "labels":
        data["ledger"][0]["labels"] = []
    else:
        data["ledger"][0]["scaling"] = False
    path = tmp_path / "status.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=r"invalid|unknown|duplicate|missing"):
        status.load(path)


def test_heading_targets_ignore_code_and_number_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(status, "ROOT", tmp_path)
    (tmp_path / "proof.md").write_text(
        "# A `proof`: bound\n\n```\n## False target\n```\n## A proof: bound\n"
    )
    data = json.loads(status.MANIFEST.read_text())
    data["ledger"] = []
    data["audit"] = [data["audit"][0]]
    manifest = tmp_path / "status.json"
    for anchor in ("a-proof-bound", "a-proof-bound-1", "false-target"):
        data["audit"][0]["evidence"] = f"proof.md#{anchor}"
        manifest.write_text(json.dumps(data))
        if anchor == "false-target":
            with pytest.raises(ValueError, match="missing evidence anchor"):
                status.load(manifest)
        else:
            status.load(manifest)


def test_ledger_evidence_can_name_a_whole_file(tmp_path):
    data = json.loads(status.MANIFEST.read_text())
    data["ledger"][0]["evidence"] = "docs/proofs/index.md"
    manifest = tmp_path / "status.json"
    manifest.write_text(json.dumps(data))
    status.load(manifest)
