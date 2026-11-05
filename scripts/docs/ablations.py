"""Typed audit records, with pinned historical payloads and executable replays."""

from __future__ import annotations

import math
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from esolangs.registry import LANGUAGES

from .ablation_replay import (
    AuditError,
    ReplayRecord,
    parse_replay,
    revision,
    verify_replay,
)

ROOT = Path(__file__).resolve().parents[2]
GROUPS = frozenset({"ablations", "interpreter_ablations"})
_RETIREMENT_GATE = date(2026, 10, 28)


@dataclass(frozen=True)
class Retirement:
    """An archived retirement date and a source span citing balanced evidence."""

    verb: str
    date: date
    balanced: tuple[int, int] | None


@dataclass(frozen=True)
class ArchiveRecord:
    """Historical values as recorded, without normalizing ratio direction or scope."""

    values: Mapping[str, Any]
    retirement: Retirement | None

    @property
    def verdict(self) -> str:
        """Return the archived audit text."""
        return cast(str, self.values["verdict"])


@dataclass(frozen=True)
class AuditFile:
    """One language's archives and replays, retaining its historical context."""

    language: str
    group: str
    archive_revision: str | None
    context: Mapping[str, Any]
    records: Mapping[str, ArchiveRecord | ReplayRecord]

    @property
    def path(self) -> Path:
        """Return the owning metadata path."""
        return (
            Path("src/esolangs/languages")
            / LANGUAGES[self.language].id
            / "language.toml"
        )

    @property
    def unrelated(self) -> tuple[str, ...]:
        """Return declared exceptions to the numeric repetition lint."""
        return cast(tuple[str, ...], self.context.get("unrelated", ()))


def _freeze(value: Any) -> Any:
    """Retain TOML values immutably and reject nonfinite measurements."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(v) for key, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("audit measurements must be finite")
    if value is None or type(value) in (str, int, float, bool, date):
        return value
    raise ValueError("unsupported archived audit value")


def _canonical(value: Any) -> Any:
    """Compare archived values without conflating booleans, integers and floats."""
    if isinstance(value, Mapping):
        return "table", tuple((k, _canonical(v)) for k, v in sorted(value.items()))
    if isinstance(value, (tuple, list)):
        return "list", tuple(_canonical(v) for v in value)
    if type(value) is float:
        return "float", value.hex()
    return type(value).__name__, value


def _retirement(value: Any, verdict: str) -> Retirement | None:
    """Validate the declared date and literal source anchors."""
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value) - {"balanced"} != {"verb", "date"}
        or not isinstance(value["verb"], str)
        or value["verb"] not in {"retired", "removed"}
        or type(value["date"]) is not date
    ):
        raise ValueError("invalid archived retirement")
    if not verdict.startswith(f"{value['verb']} {value['date'].isoformat()}"):
        raise ValueError("retirement source anchor differs")
    span = value.get("balanced")
    if span is not None and (
        not isinstance(span, list)
        or len(span) != 2
        or any(type(i) is not int for i in span)
        or not 0 <= span[0] < span[1] <= len(verdict)
        or verdict[span[0] : span[1]] != "balanced"
    ):
        raise ValueError("invalid balanced-evidence source anchor")
    if value["date"] >= _RETIREMENT_GATE and span is None:
        raise ValueError("retirement lacks balanced evidence")
    return Retirement(
        value["verb"], value["date"], tuple(span) if span is not None else None
    )


def parse_audits(language: str, group: str, data: dict[str, Any]) -> AuditFile:
    """Validate archival/replay kinds and retain pinned historical fields."""
    if (
        group not in GROUPS
        or not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
        or "archive_context" not in data
        or not isinstance(data["archive_context"], dict)
    ):
        raise ValueError("invalid audit schema")
    archive_revision = (
        revision(data["archive_revision"]) if "archive_revision" in data else None
    )
    records: dict[str, ArchiveRecord | ReplayRecord] = {}
    for key, raw in data.items():
        if key in {"version", "archive_revision", "archive_context"}:
            continue
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise ValueError("audit records need an explicit kind")
        if raw["kind"] in {"replay", "measurement"}:
            if group != "ablations":
                raise ValueError("generator replay belongs under ablations")
            records[key] = parse_replay(language, raw)
        elif raw["kind"] == "archive":
            if archive_revision is None:
                raise ValueError("archived audits need a pinned revision")
            verdict = raw.get("verdict")
            if not isinstance(verdict, str) or not verdict:
                raise ValueError("archived audit needs its verdict")
            values = {k: v for k, v in raw.items() if k not in {"kind", "retirement"}}
            records[key] = ArchiveRecord(
                _freeze(values), _retirement(raw.get("retirement"), verdict)
            )
        else:
            raise ValueError("unknown audit record kind")
    if not records:
        raise ValueError("audit dataset must contain records")
    if data["archive_context"] and archive_revision is None:
        raise ValueError("archived context needs a pinned revision")
    return AuditFile(
        language,
        group,
        archive_revision,
        _freeze(data["archive_context"]),
        MappingProxyType(records),
    )


def load(language: str, group: str = "ablations") -> AuditFile | None:
    """Read only the requested audit section from its owning language."""
    path = ROOT / "src/esolangs/languages" / LANGUAGES[language].id / "language.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return parse_audits(language, group, data[group]) if group in data else None


def verify_archive(audit: AuditFile) -> None:
    """Require every archived value and annotation to match its pinned source."""
    archives = {
        key: r for key, r in audit.records.items() if isinstance(r, ArchiveRecord)
    }
    if audit.archive_revision is None:
        return
    reference = f"{audit.archive_revision}:{audit.path.as_posix()}"
    try:
        result = subprocess.run(
            ["git", "show", reference],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        old = tomllib.loads(result.stdout)[audit.group]
    except (subprocess.SubprocessError, KeyError, tomllib.TOMLDecodeError) as error:
        raise AuditError(f"cannot read archived audit source {reference}") from error
    if type(old.get("version")) is not int or old["version"] != 1:
        raise AuditError(f"archive source must be structured: {reference}")
    context = old["archive_context"]
    if _canonical(audit.context) != _canonical(context):
        raise AuditError(f"archived audit context differs: {reference}")
    old_keys = set(old) - {"version", "archive_revision", "archive_context"}
    if not old_keys <= audit.records.keys():
        raise AuditError(f"archived audit records are missing: {reference}")
    for key, record in archives.items():
        values = dict(record.values) | {"kind": "archive"}
        retired = record.retirement
        if retired is not None:
            annotation: dict[str, Any] = {"verb": retired.verb, "date": retired.date}
            if retired.balanced is not None:
                annotation["balanced"] = retired.balanced
            values["retirement"] = annotation
        if (
            key not in old
            or old[key].get("kind") != "archive"
            or (_canonical(values) != _canonical(old[key]))
        ):
            raise AuditError(f"archived audit values differ: {reference}#{key}")


def verify(audit: AuditFile, scratch: Path) -> None:
    """Verify historical provenance and execute every declared new replay."""
    verify_archive(audit)
    for record in audit.records.values():
        if isinstance(record, ReplayRecord):
            verify_replay(audit.language, record, scratch)
