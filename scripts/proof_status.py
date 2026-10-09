"""Load proof status and render its committed documentation tables."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "esolangs" / "proof_status.toml"


@dataclass(frozen=True)
class ProofRow:
    """One generator's proof and scaling status."""

    generator: str
    labels: tuple[str, ...]
    qualification: str
    scaling: str
    execution: str
    workspace: str
    evidence: str
    #: ``"S = ..."`` symbols a formula cell uses, rendered under the table
    #: so the cell itself stays short.
    definitions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScalingRow:
    """The three independent axes of an unresolved generator."""

    generator: str
    totality: str
    generation_time: str
    output_size: str
    evidence: str


def _text(row: dict[str, object], key: str) -> str:
    """Return a required nonempty text field."""
    value = row[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid proof status field: {key}")
    return value


def _check_evidence(reference: str, *, precise: bool) -> None:
    """Check a local Markdown heading; audit evidence must name one."""
    relative, separator, anchor = reference.partition("#")
    target = (ROOT / relative).resolve()
    if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
        raise ValueError(f"missing evidence: {reference}")
    if precise and (not separator or not anchor):
        raise ValueError(f"invalid audit evidence: {reference}")
    if separator:
        anchors = set()
        counts: dict[str, int] = {}
        fenced = False
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.startswith(("```", "~~~")):
                fenced = not fenced
            if fenced:
                continue
            heading = re.match(r"^#{1,6} +(.+?)(?: +#+)?$", line)
            if heading:
                slug = re.sub(r"[^\w\- ]", "", heading[1].lower()).replace(" ", "-")
                count = counts.get(slug, 0)
                counts[slug] = count + 1
                anchors.add(f"{slug}-{count}" if count else slug)
        if anchor not in anchors:
            raise ValueError(f"missing evidence anchor: {reference}")


def load(path: Path = MANIFEST) -> tuple[tuple[ProofRow, ...], tuple[ScalingRow, ...]]:
    """Return validated proof and audit rows from the manifest."""
    return validate(tomllib.loads(path.read_text(encoding="utf-8")))


def validate(
    data: dict[str, Any],
) -> tuple[tuple[ProofRow, ...], tuple[ScalingRow, ...]]:
    """Return proof and audit rows from parsed manifest ``data``."""
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
        definitions = row.get("definitions", [])
        if not isinstance(definitions, list) or not all(
            isinstance(item, str) and " = " in item for item in definitions
        ):
            raise ValueError("invalid proof definitions")
        proofs.append(
            ProofRow(
                _text(row, "generator"),
                tuple(labels),
                _text(row, "qualification"),
                _text(row, "scaling"),
                _text(row, "execution"),
                _text(row, "workspace"),
                _text(row, "evidence"),
                tuple(definitions),
            )
        )
    for row in data["audit"]:
        totality = _text(row, "totality")
        costs = tuple(_text(row, key) for key in ("generation_time", "output_size"))
        if totality not in {"Total", "Cap", "Exception"} or any(
            cost not in {"Linear", "O(T)", "Measured", "Open", "Language lower bound"}
            for cost in costs
        ):
            raise ValueError("unknown scaling verdict")
        audits.append(
            ScalingRow(
                _text(row, "generator"),
                totality,
                costs[0],
                costs[1],
                _text(row, "evidence"),
            )
        )
    for rows in (proofs, audits):
        names = [row.generator for row in rows]
        if len(names) != len(set(names)):
            raise ValueError("duplicate proof status generator")
        for row in rows:
            _check_evidence(row.evidence, precise=isinstance(row, ScalingRow))
    return tuple(proofs), tuple(audits)


#: Small counts read as words in the totals sentence, as the prose around it does.
_WORDS = ("no", "one", "two", "three", "four", "five")


def render_totals(proofs: tuple[ProofRow, ...]) -> str:
    """Return the ledger's closing totals sentence: arguments and exceptions."""
    exceptions = sum("exception" in row.labels for row in proofs)
    count = _WORDS[exceptions] if exceptions < len(_WORDS) else str(exceptions)
    noun = "exception" if exceptions == 1 else "exceptions"
    return (
        f"Accordingly, this ledger records {len(proofs) - exceptions} theoretical"
        f" totality arguments and\n{count} {noun} under the source-embedded"
        " contract."
    )


def update_docs(root: Path = ROOT) -> None:
    """Render the status tables and totals without changing surrounding prose."""
    proofs, audits = load()
    tables = (
        (
            root / "docs/proofs/index.md",
            "PROOF-STATUS",
            "",
            [
                "| Generator | Proof | Qualification | Scaling | Execution | "
                "Workspace |",
                "| --- | --- | --- | --- | --- | --- |",
                *[
                    f"| {r.generator} | {', '.join(r.labels)} | "
                    f"{r.qualification} | {r.scaling} | {r.execution} | "
                    f"{r.workspace} |"
                    for r in proofs
                ],
                "",
                "Symbols the formula cells use:",
                "",
                *[
                    f"- **{r.generator}:** {'; '.join(r.definitions)}."
                    for r in proofs
                    if r.definitions
                ],
            ],
        ),
        (root / "docs/proofs/index.md", "PROOF-TOTALS", "", [render_totals(proofs)]),
        (
            root / "docs/roadmap.md",
            "SCALING-STATUS",
            "  ",
            [
                "| Language | Totality | Generation time | Output size |",
                "| --- | --- | --- | --- |",
                *[
                    f"| {r.generator} | {r.totality} | {r.generation_time} | "
                    f"{r.output_size} |"
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
