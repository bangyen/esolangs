"""Load proof status and render its committed documentation tables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs" / "proofs" / "status.json"


@dataclass(frozen=True)
class ProofRow:
    """One generator's proof and scaling status."""

    generator: str
    labels: tuple[str, ...]
    qualification: str
    scaling: str
    evidence: str


@dataclass(frozen=True)
class ScalingRow:
    """The four independent axes of an unresolved generator."""

    generator: str
    totality: str
    generation_time: str
    output_size: str
    execution_time: str
    evidence: str


def _text(row: dict[str, object], key: str) -> str:
    """Return a required nonempty text field."""
    value = row[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid proof status field: {key}")
    return value


def load(path: Path = MANIFEST) -> tuple[tuple[ProofRow, ...], tuple[ScalingRow, ...]]:
    """Return validated proof and audit rows from the manifest."""
    data = json.loads(path.read_text(encoding="utf-8"))
    proofs = []
    audits = []
    for row in data["ledger"]:
        labels = row["labels"]
        if (
            not isinstance(labels, list)
            or not labels
            or not all(isinstance(label, str) and label for label in labels)
        ):
            raise ValueError("invalid proof labels")
        proofs.append(
            ProofRow(
                _text(row, "generator"),
                tuple(labels),
                _text(row, "qualification"),
                _text(row, "scaling"),
                _text(row, "evidence"),
            )
        )
    for row in data["audit"]:
        totality = _text(row, "totality")
        costs = tuple(
            _text(row, key)
            for key in (
                "generation_time",
                "output_size",
                "execution_time",
            )
        )
        if totality not in {"Total", "Cap", "Exception"} or any(
            cost not in {"Linear", "O(T)", "Open", "Language lower bound"}
            for cost in costs
        ):
            raise ValueError("unknown scaling verdict")
        audits.append(
            ScalingRow(
                _text(row, "generator"),
                totality,
                costs[0],
                costs[1],
                costs[2],
                _text(row, "evidence"),
            )
        )
    for rows in (proofs, audits):
        names = [row.generator for row in rows]
        if len(names) != len(set(names)):
            raise ValueError("duplicate proof status generator")
        for row in rows:
            if not (ROOT / row.evidence.split("#", 1)[0]).is_file():
                raise ValueError(f"missing evidence: {row.evidence}")
    return tuple(proofs), tuple(audits)


def update_docs() -> None:
    """Render both status tables without changing surrounding prose."""
    proofs, audits = load()
    tables = (
        (
            ROOT / "docs/proofs/index.md",
            "PROOF-STATUS",
            "",
            [
                "| Generator | Proof | Qualification | Scaling |",
                "| --- | --- | --- | --- |",
                *[
                    f"| {r.generator} | {', '.join(r.labels)} | "
                    f"{r.qualification} | {r.scaling} |"
                    for r in proofs
                ],
            ],
        ),
        (
            ROOT / "docs/roadmap.md",
            "SCALING-STATUS",
            "  ",
            [
                "| Language | Totality | Generation time | Output size | "
                "Execution time |",
                "| --- | --- | --- | --- | --- |",
                *[
                    f"| {r.generator} | {r.totality} | {r.generation_time} | "
                    f"{r.output_size} | {r.execution_time} |"
                    for r in audits
                ],
            ],
        ),
    )
    for path, marker, indent, lines in tables:
        text = path.read_text(encoding="utf-8")
        start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
        before, rest = text.split(start, 1)
        _, after = rest.split(end, 1)
        body = "\n".join(indent + line for line in lines)
        path.write_text(
            before + start + "\n\n" + body + "\n\n" + indent + end + after,
            encoding="utf-8",
        )
