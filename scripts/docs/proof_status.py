"""Load proof status and render its committed documentation tables."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .anchors import anchors
from .fragments import AggregateKey, cached, fingerprint
from .writing import write_if_changed as _write_if_changed

ROOT = Path(__file__).resolve().parents[2]

#: Fragments are discovered in this checkout, even when ``ROOT`` is
#: redirected to a scratch tree for evidence checks.
_CHECKOUT = Path(__file__).resolve().parents[2]
PACKAGES = _CHECKOUT / "src" / "esolangs" / "languages"
FRAGMENT = "language.toml"

_LEDGER_KEYS = frozenset(
    {
        "labels",
        "qualification",
        "scaling",
        "execution",
        "workspace",
        "evidence",
        "definitions",
    }
)
_AUDIT_KEYS = frozenset({"totality", "generation_time", "output_size", "evidence"})


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


#: A ledger row's evidence unless it names its own proof.
LEDGER_EVIDENCE = "docs/proofs/index.md#generator-ledger"


def _text(row: dict[str, object], key: str) -> str:
    """Return a required nonempty text field."""
    value = row[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid proof status field: {key}")
    return value


def _check_evidence(reference: str, *, precise: bool) -> None:
    """Check a local heading or explicit anchor; audits must name one."""
    relative, separator, anchor = reference.partition("#")
    target = (ROOT / relative).resolve()
    if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
        raise ValueError(f"missing evidence: {reference}")
    if precise and (not separator or not anchor):
        raise ValueError(f"invalid audit evidence: {reference}")
    if separator and anchor not in anchors(target.read_text(encoding="utf-8")):
        raise ValueError(f"missing evidence anchor: {reference}")


def _fragment_row(
    path: Path, row: dict[str, Any], keys: frozenset[str], group: str
) -> dict[str, Any]:
    """Return one fragment row after checking its keys and field types."""
    unknown = set(row) - keys
    if unknown:
        raise ValueError(f"{path}: unknown proof_status {group} keys {sorted(unknown)}")
    for key, value in row.items():
        if key in {"labels", "definitions"}:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{path}: proof_status {group} {key} must be text")
    return dict(row)


#: Aggregates by (packages, generators, fragment fingerprint), and
#: validated loads by (source, fingerprint).  The new-language check
#: loads the full status once per registered language; uncached, each
#: load re-parsed every fragment and re-checked every evidence anchor.
_LoadKey = tuple[str, tuple[tuple[str, int, int], ...]]
_AGGREGATES: dict[AggregateKey, dict[str, list[dict[str, Any]]]] = {}
_LOADS: dict[_LoadKey, tuple[tuple[ProofRow, ...], tuple[ScalingRow, ...]]] = {}


def aggregate_fragments(
    packages: Path, generators: list[tuple[str, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Merge every package's proof_status section into ledger/audit rows.

    ``generators`` is ``(name, package id)`` pairs in registry order, and
    the rows come back in that order; a section in an unregistered package
    raises ``ValueError``.
    """
    key = (packages, tuple(generators), fingerprint(packages))
    return cached(_AGGREGATES, key, lambda: _aggregate_fragments(packages, generators))


def _aggregate_fragments(
    packages: Path, generators: list[tuple[str, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Merge the proof_status sections, uncached; see :func:`aggregate_fragments`."""
    data: dict[str, list[dict[str, Any]]] = {"ledger": [], "audit": []}
    known = set()
    for name, slug in generators:
        known.add(slug)
        path = packages / slug / FRAGMENT
        if not path.is_file():
            continue
        section = tomllib.loads(path.read_text(encoding="utf-8")).get("proof_status")
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ValueError(f"{path}: [proof_status] must be a table")
        parts = {
            "ledger": {k: v for k, v in section.items() if k != "audit"},
            "audit": section.get("audit"),
        }
        for group, keys in (("ledger", _LEDGER_KEYS), ("audit", _AUDIT_KEYS)):
            raw = parts[group]
            if raw is None or raw == {}:
                continue
            if not isinstance(raw, dict):
                raise ValueError(f"{path}: [proof_status] {group} must be a table")
            row = _fragment_row(path, raw, keys, group)
            data[group].append(row | {"generator": name})
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name in known:
                continue
            parsed = tomllib.loads(path.read_text(encoding="utf-8"))
            if "proof_status" in parsed:
                raise ValueError(
                    f"{path}: package {path.parent.name!r} is not registered"
                )
    return data


def _generators() -> list[tuple[str, str]]:
    """Return ``(name, package id)`` for each Boolean generator, registry order."""
    from esolangs.languages.generators import BOOLEAN
    from esolangs.registry import LANGUAGES

    return [(name, lang.id) for name, lang in LANGUAGES.items() if name in BOOLEAN]


def load_data(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return the raw ledger/audit rows, aggregated from the fragments.

    ``path`` may name a root to aggregate instead of this checkout, or a
    single TOML file in the former global shape.
    """
    if path is not None and path.is_file():
        return tomllib.loads(path.read_text(encoding="utf-8"))
    root = _CHECKOUT if path is None else path
    return aggregate_fragments(root / "src/esolangs/languages", _generators())


def load(
    path: Path | None = None,
) -> tuple[tuple[ProofRow, ...], tuple[ScalingRow, ...]]:
    """Return validated proof and audit rows from the package fragments.

    Cached per process against the fragment fingerprint (or the single
    file's stamp): the validated rows are immutable, and any fragment
    added, removed, or edited changes the key, so a process that
    mutates the tree never reads a stale load.
    """
    key: _LoadKey
    if path is not None and path.is_file():
        stat = path.stat()
        key = (str(path), ((path.name, stat.st_mtime_ns, stat.st_size),))
    else:
        root = _CHECKOUT if path is None else path
        key = (str(root), fingerprint(root / "src/esolangs/languages"))
    return cached(_LOADS, key, lambda: validate(load_data(path)))


def _registry_ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return ``rows`` sorted by their generator's registry position.

    Generators outside the registry sort last, keeping their input order:
    fragments carry no sequence of their own, so the registry is the one
    canonical order every render shares.
    """
    position = {name: index for index, (name, _) in enumerate(_generators())}

    def key(row: dict[str, Any]) -> int:
        name = row.get("generator")
        if not isinstance(name, str):
            return len(position)
        return position.get(name, len(position))

    return sorted(rows, key=key)


def validate(
    data: dict[str, Any],
) -> tuple[tuple[ProofRow, ...], tuple[ScalingRow, ...]]:
    """Return proof and audit rows from parsed manifest ``data``."""
    proofs = []
    audits = []
    for row in _registry_ordered(data["ledger"]):
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
        if row.get("evidence") == LEDGER_EVIDENCE:
            raise ValueError(f"{row['generator']}: omit the default evidence")
        proofs.append(
            ProofRow(
                _text(row, "generator"),
                tuple(labels),
                _text(row, "qualification"),
                _text(row, "scaling"),
                _text(row, "execution"),
                _text(row, "workspace"),
                _text({"evidence": LEDGER_EVIDENCE} | row, "evidence"),
                tuple(definitions),
            )
        )
    for row in _registry_ordered(data["audit"]):
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
        names = [item.generator for item in rows]
        if len(names) != len(set(names)):
            raise ValueError("duplicate proof status generator")
        for item in rows:
            _check_evidence(item.evidence, precise=isinstance(item, ScalingRow))
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


def splice(text: str, name: str, body: str) -> str:
    """Replace the block ``name`` marks in ``text``, keeping the markers."""
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    block = start + "\n\n" + body + "\n\n" + end
    return text[: text.index(start)] + block + text[text.index(end) + len(end) :]


def update_docs(root: Path = ROOT) -> bool:
    """Render the status tables and totals without changing surrounding prose."""
    proofs, audits = load()
    tables = (
        (
            "PROOF-STATUS",
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
        ("PROOF-TOTALS", [render_totals(proofs)]),
        (
            "SCALING-STATUS",
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
    path = root / "docs/proofs/index.md"
    text = path.read_text(encoding="utf-8")
    for marker, lines in tables:
        text = splice(text, marker, "\n".join(lines))
    return _write_if_changed(path, text, encoding="utf-8")
