"""Every audit retains its historical evidence or executes a measured replay."""

import copy
import tempfile
import time
import tomllib
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

import esolangs
from esolangs.generation.helpers import grid_area
from esolangs.registry import LANGUAGES
from scripts.docs import ablation_replay, ablations
from tests.support.reference import REFERENCE

_PILOTS = {
    next(name for name, lang in LANGUAGES.items() if lang.backend and predicate(lang))
    for predicate in (
        lambda lang: lang.runtime.source_kind == "raster",
        lambda lang: lang.parameterized and lang.contract.answer_mode == "output",
        lambda lang: lang.contract.answer_mode == "termination",
        lambda lang: lang.runtime.random and lang.contract.answer_mode == "output",
        lambda lang: lang.runtime.compressed_source,
    )
}


def _cases():
    for name in sorted(LANGUAGES):
        bands = [
            record.band
            for group in ablations.GROUPS
            if (audit := ablations.load(name, group)) is not None
            for record in audit.records.values()
            if isinstance(record, ablation_replay.ReplayRecord)
        ]
        marks = pytest.mark.slow if "slow" in bands else pytest.mark.medium
        yield pytest.param(name, marks=marks)


@pytest.mark.parametrize("language", list(_cases()))
def test_audit_evidence(language: str, tmp_path: Path, monkeypatch) -> None:
    for group in ablations.GROUPS:
        audit = ablations.load(language, group)
        if group == "ablations" and LANGUAGES[language].backend is not None:
            assert audit is not None
            assert audit.context.get("audited") or any(
                isinstance(r, ablation_replay.ReplayRecord)
                for r in audit.records.values()
            )
        if audit is not None:
            ablations.verify(audit, tmp_path)
    if language in _PILOTS:
        _pilot(language, tmp_path)
    if language == REFERENCE:
        _controls(tmp_path, monkeypatch)


def _controls(tmp_path, monkeypatch):
    archive = ablations.load(REFERENCE)
    assert archive is not None
    data = tomllib.loads((ablations.ROOT / archive.path).read_text())["ablations"]
    key = next(iter(archive.records))
    broken = copy.deepcopy(data)
    broken[key]["verdict"] += " changed"
    with pytest.raises(ablation_replay.AuditError, match="values differ"):
        ablations.verify_archive(ablations.parse_audits(REFERENCE, "ablations", broken))
    for update in ({"version": True}, {"archive_revision": "main"}):
        with pytest.raises(ValueError, match="audit"):
            ablations.parse_audits(REFERENCE, "ablations", data | update)
    broken = copy.deepcopy(data)
    broken[key]["kind"] = "unverified"
    with pytest.raises(ValueError, match="kind"):
        ablations.parse_audits(REFERENCE, "ablations", broken)
    retired = {
        "version": 1,
        "archive_revision": data["archive_revision"],
        "archive_context": {},
        "control": {
            "kind": "archive",
            "verdict": "retired 2026-11-05: balanced area unchanged",
            "retirement": {"verb": "retired", "date": date(2026, 11, 5)},
        },
    }
    with pytest.raises(ValueError, match="balanced"):
        ablations.parse_audits(REFERENCE, "ablations", retired)
    retired["control"]["retirement"]["balanced"] = [20, 28]
    ablations.parse_audits(REFERENCE, "ablations", retired)
    retired["control"]["retirement"]["balanced"] = [0, 8]
    with pytest.raises(ValueError, match="source anchor"):
        ablations.parse_audits(REFERENCE, "ablations", retired)
    revision = "aecd35024334b3c9f83c6703d83f4c7d6a366a5f"
    source = esolangs.generate(REFERENCE, "0110")
    balanced = esolangs.generate(REFERENCE, "0110", balance=True)
    generate = LANGUAGES[REFERENCE].backend.generate
    raw = {
        "kind": "replay",
        "construction": f"{generate.__module__}:{generate.__name__}",
        "audited": date(2026, 11, 5),
        "witness": {"arity": 2, "rule": "parity"},
        "baseline_revision": revision,
        "source": {"unit": "chars", "before": 186, "after": len(source)},
        "balanced": {
            "unit": "cells",
            "before": 190,
            "after": grid_area(balanced),
        },
        "scale": 1,
        "budget": 5,
        "band": "medium",
    }
    record = ablation_replay.parse_replay(REFERENCE, raw)
    ablation_replay.verify_replay(REFERENCE, record, tmp_path)
    initial = copy.deepcopy(raw)
    initial["kind"] = "measurement"
    del initial["baseline_revision"]
    initial["source"] = {"unit": "chars", "value": len(source)}
    initial["balanced"] = {"unit": "cells", "value": grid_area(balanced)}
    ablation_replay.verify_replay(
        REFERENCE, ablation_replay.parse_replay(REFERENCE, initial), tmp_path
    )
    for change in (
        {"budget": True},
        {"budget": 61},
        {"scale": 2},
        {"rows": []},
        {"rows": [4]},
        {"seed": 0},
        {"witness": {"arity": 2, "rule": "random"}},
        {"witness": {"arity": 21, "rule": "parity"}},
    ):
        with pytest.raises(ValueError, match=r"replay|audit|witness"):
            ablation_replay.parse_replay(REFERENCE, raw | change)
    with pytest.raises(ablation_replay.AuditError, match="source size"):
        ablation_replay.verify_replay(
            REFERENCE,
            replace(
                record, source=replace(record.source, after=record.source.after + 1)
            ),
            tmp_path,
        )
    monkeypatch.setattr(esolangs, "generate", lambda *_args, **_kwargs: ".")
    with pytest.raises(ablation_replay.AuditError, match=r"answer|execution|input"):
        ablation_replay.verify_replay(REFERENCE, record, tmp_path)
    skipped = copy.deepcopy(initial)
    skipped["witness"] = {"arity": 1, "rule": "zero"}
    skipped["source"] = {"unit": "chars", "value": 49}
    del skipped["balanced"]
    monkeypatch.setattr(esolangs, "generate", lambda *_args, **_kwargs: "+" * 48 + ".")
    with pytest.raises(ablation_replay.AuditError, match="input-consumption"):
        ablation_replay.verify_replay(
            REFERENCE, ablation_replay.parse_replay(REFERENCE, skipped), tmp_path
        )


def _pilot(language, tmp_path):
    lang = LANGUAGES[language]
    generate = lang.backend.generate
    candidate = esolangs.generate(language, "01")
    unit = (
        "codels"
        if lang.runtime.source_kind == "raster"
        else ("cells" if lang.backend.grid else "chars")
    )
    raw = {
        "kind": "replay",
        "audited": date(2026, 11, 5),
        "construction": f"{generate.__module__}:{generate.__name__}",
        "witness": {"arity": 1, "rule": "parity"},
        "baseline_revision": "aecd35024334b3c9f83c6703d83f4c7d6a366a5f",
        "source": {"unit": unit, "before": 1, "after": _units(candidate, unit)},
        "scale": 1,
        "budget": 5,
        "band": "medium",
    }
    if lang.runtime.random and lang.contract.answer_mode != "termination":
        raw["seed"] = 0
    draft = ablation_replay.parse_replay(language, raw)
    with tempfile.TemporaryDirectory(dir=tmp_path) as folder:
        baseline = ablation_replay._baseline(
            language, draft, "01", Path(folder), time.monotonic() + 5, balanced=False
        )
        raw["source"]["before"] = _units(baseline, unit)
    ablation_replay.verify_replay(
        language, ablation_replay.parse_replay(language, raw), tmp_path
    )


def _units(program, unit):
    if isinstance(program, esolangs.Raster):
        return len(program.rows) * len(program.rows[0])
    if unit == "chars":
        return len(program)
    return grid_area(program)
