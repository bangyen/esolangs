"""Proof status records and consistency."""

from pathlib import Path

import pytest

from scripts.docs import proof_status as status


def test_rendering_preserves_committed_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proofs, audits = status.load()
    files = {row.evidence.split("#", 1)[0] for row in (*proofs, *audits)}
    files.add("docs/proofs/index.md")
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((status.ROOT / relative).read_bytes())
    monkeypatch.setattr(status, "ROOT", tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.md")}
    # In-sync tables are not rewritten, and update_docs reports no change.
    assert status.update_docs(tmp_path) is False
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
def test_invalid_status_cannot_grant_an_exemption(case: str) -> None:
    data = status.load_data()
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
    with pytest.raises(ValueError, match=r"invalid|unknown|duplicate|missing"):
        status.validate(data)


def test_heading_targets_ignore_code_and_number_duplicates(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(status, "ROOT", tmp_path)
    (tmp_path / "proof.md").write_text(
        "# A `proof`: bound\n\n```\n## False target\n```\n## A proof: bound\n"
    )
    data = status.load_data()
    data["ledger"] = []
    data["audit"] = [data["audit"][0]]
    for anchor in ("a-proof-bound", "a-proof-bound-1", "false-target"):
        data["audit"][0]["evidence"] = f"proof.md#{anchor}"
        if anchor == "false-target":
            with pytest.raises(ValueError, match="missing evidence anchor"):
                status.validate(data)
        else:
            status.validate(data)


def test_ledger_evidence_can_name_a_whole_file() -> None:
    data = status.load_data()
    data["ledger"][0]["evidence"] = "docs/proofs/index.md"
    status.validate(data)


def test_ledger_evidence_defaults_and_is_not_restated() -> None:
    data = status.load_data()
    assert "evidence" not in data["ledger"][0]
    assert status.validate(data)[0][0].evidence == status.LEDGER_EVIDENCE
    data["ledger"][0]["evidence"] = status.LEDGER_EVIDENCE
    with pytest.raises(ValueError, match="omit the default evidence"):
        status.validate(data)


def test_owned_evidence_anchor_is_required(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(status, "ROOT", tmp_path)
    document = tmp_path / "proof.md"
    document.write_text(
        '# Bounds\n\n- Example: <a id="example-bound"></a> finite construction.\n'
        '\n```html\n<a id="code-only"></a>\n```\n'
    )
    data = status.load_data()
    data["ledger"] = []
    data["audit"] = [data["audit"][0]]
    data["audit"][0]["evidence"] = "proof.md#example-bound"
    status.validate(data)
    document.write_text('# Bounds\n\n```html\n<a id="example-bound"></a>\n```\n')
    with pytest.raises(ValueError, match="missing evidence anchor"):
        status.validate(data)
