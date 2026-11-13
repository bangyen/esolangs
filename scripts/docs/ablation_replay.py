"""Execute explicitly scoped generator audit witnesses and measure their source."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import esolangs
from esolangs.artifacts import Artifact
from esolangs.generation.helpers import grid_area
from esolangs.portable import decode_settings
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, template_char
from esolangs.results import ExecutionResult
from esolangs.runtime._source import text_source
from esolangs.runtime.io import ScriptedIO
from tests.support.execution import run_guard as _run
from tests.support.execution import termination_observed

from .evidence import TableWitness

ROOT = Path(__file__).resolve().parents[2]
_REVISION = re.compile(r"[0-9a-f]{40}\Z")


class AuditError(ValueError):
    """An audit lacks its declared execution or measurement evidence."""


@dataclass(frozen=True)
class Measurement:
    """Observed baseline/candidate counts in an explicitly named unit."""

    unit: str
    before: int | None
    after: int

    @property
    def saving(self) -> Fraction | None:
        """Return the candidate's percentage saving, or None for a zero baseline."""
        return (
            Fraction(100 * (self.before - self.after), self.before)
            if self.before
            else None
        )


@dataclass(frozen=True)
class ReplayRecord:
    """A bounded, reproducible comparison against a pinned generator revision."""

    witness: TableWitness
    audited: date
    baseline: str | None
    source: Measurement
    balanced: Measurement | None
    retired: date | None
    rows: tuple[int, ...] | None
    seed: int | None
    budget: int
    band: str
    notes: str

    @property
    def verdict(self) -> str:
        """Render measured figures without interpreting notes."""
        saving = self.source.saving
        ratio = f" ({float(saving):.2f}%)" if saving is not None else ""
        counts = (
            f"{self.source.before:,}->{self.source.after:,}"
            if self.source.before is not None
            else f"{self.source.after:,}"
        )
        prefix = (
            f"retired {self.retired}: " if self.retired is not None else "measured: "
        )
        return f"{prefix}{counts} {self.source.unit}{ratio}" + (
            f"; {self.notes}" if self.notes else ""
        )


def revision(value: object) -> str:
    """Require a full immutable commit identifier."""
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise ValueError("audit revision must be a full commit hash")
    return value


def _measurement(value: object, unit: str, *, comparison: bool) -> Measurement:
    """Validate nonnegative counts, with a baseline only for comparisons."""
    fields = {"before", "after"} if comparison else {"value"}
    if (
        not isinstance(value, dict)
        or set(value) != fields | {"unit"}
        or value["unit"] != unit
        or any(type(value[k]) is not int or value[k] < 0 for k in fields)
    ):
        raise ValueError("invalid audit measurement")
    return Measurement(
        unit, value.get("before"), value["after"] if comparison else value["value"]
    )


def parse_replay(language: str, data: dict[str, Any]) -> ReplayRecord:
    """Validate explicit scope, source units, runtime seed and resource budget."""
    required = {
        "kind",
        "witness",
        "source",
        "budget",
        "band",
        "scale",
        "audited",
        "construction",
    }
    if isinstance(data, dict) and data.get("kind") == "replay":
        required.add("baseline_revision")
    if (
        not isinstance(data, dict)
        or not required <= data.keys()
        or set(data)
        - required
        - {
            "balanced",
            "retired",
            "rows",
            "seed",
            "notes",
        }
    ):
        raise ValueError("invalid replay fields")
    backend = LANGUAGES[language].backend
    if backend is None or data["kind"] not in {"replay", "measurement"}:
        raise ValueError("generator replay requires a Boolean generator")
    generate = backend.generate
    if data["construction"] != f"{generate.__module__}:{generate.__name__}":
        raise ValueError("audit construction does not match its backend")
    witness = data["witness"]
    if not isinstance(witness, dict) or set(witness) - {"seed"} != {"arity", "rule"}:
        raise ValueError("invalid replay witness")
    table = TableWitness(witness["arity"], witness["rule"], witness.get("seed"))
    # Match the evaluation harness's one-Mi-row verification budget.
    if table.arity > 20:
        raise ValueError("replay witness exceeds the one-Mi-row verification budget")
    if type(data["scale"]) is not int or data["scale"] != 1:
        raise ValueError("audit source is measured at explicit scale one")
    unit = (
        "codels"
        if LANGUAGES[language].runtime.source_kind == "raster"
        else ("cells" if backend.grid else "chars")
    )
    comparison = data["kind"] == "replay"
    source = _measurement(data["source"], unit, comparison=comparison)
    if (comparison and not source.before) or not source.after:
        raise ValueError("audit source must be nonempty")
    balanced = (
        _measurement(
            data["balanced"],
            "codels" if unit == "codels" else "cells",
            comparison=comparison,
        )
        if "balanced" in data
        else None
    )
    retired = data.get("retired")
    if type(data["audited"]) is not date:
        raise ValueError("audit replay needs a date")
    if retired is not None and (
        not comparison or type(retired) is not date or balanced is None
    ):
        raise ValueError("a retirement needs a date and balanced-area measurements")
    rows = data.get("rows")
    if rows is not None and (
        not isinstance(rows, list)
        or not rows
        or any(type(n) is not int or not 0 <= n < 1 << table.arity for n in rows)
        or len(set(rows)) != len(rows)
    ):
        raise ValueError("replay rows must be distinct admitted indices")
    seed = data.get("seed")
    if (
        LANGUAGES[language].runtime.random
        and LANGUAGES[language].contract.answer_mode != "termination"
    ):
        if type(seed) is not int:
            raise ValueError("random execution needs an explicit replay seed")
    elif seed is not None:
        raise ValueError("a deterministic replay takes no runtime seed")
    if type(data["budget"]) is not int or not 1 <= data["budget"] <= 60:
        raise ValueError("replay budget must be 1..60 seconds")
    if not isinstance(data["band"], str) or data["band"] not in {
        "fast",
        "medium",
        "slow",
    }:
        raise ValueError("invalid replay cost band")
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("audit notes must be text")
    return ReplayRecord(
        table,
        data["audited"],
        revision(data["baseline_revision"]) if comparison else None,
        source,
        balanced,
        retired,
        tuple(rows) if rows is not None else None,
        seed,
        data["budget"],
        data["band"],
        notes,
    )


def _input_usage(result: ExecutionResult) -> tuple[int | None, ...]:
    return result.input_position, result.input_reads, result.input_past_end


def _remaining(deadline: float) -> float:
    """Fail the declared budget instead of treating an unfinished run as evidence."""
    remaining = deadline - time.monotonic()
    if remaining < 0.01:
        raise AuditError("audit replay exhausted its budget")
    return remaining


def _baseline(
    language: str,
    record: ReplayRecord,
    table: str,
    scratch: Path,
    deadline: float,
    *,
    balanced: bool,
) -> Artifact:
    """Acquire and generate from the baseline within the same replay deadline."""
    archive = subprocess.run(
        ["git", "archive", revision(record.baseline), "src"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=_remaining(deadline),
    )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as bundle:
        bundle.extractall(scratch, filter="data")
    code = (
        "import esolangs,json,sys; r=json.load(sys.stdin); "
        "p=esolangs.generate(r['language'],r['table'],balance=r['balanced']); "
        "d=json.loads(esolangs.dump_program(r['language'],p)); "
        "fields=('format','version','language','settings',"
        "'kind','source','char','setters'); "
        "print(json.dumps({k:d[k] for k in fields} if d['kind']=='template' else d))"
    )
    import os

    generated = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"language": language, "table": table, "balanced": balanced}),
        env=dict(os.environ, PYTHONPATH=str(scratch / "src")),
        cwd=scratch,
        capture_output=True,
        text=True,
        check=True,
        timeout=_remaining(deadline),
    )
    document = json.loads(generated.stdout)
    if document["kind"] == "template":
        fields = {
            "format",
            "version",
            "language",
            "settings",
            "kind",
            "source",
            "char",
            "setters",
        }
        pairs = document["setters"]
        if (
            set(document) != fields
            or document["format"] != "esolangs.program"
            or type(document["version"]) is not int
            or document["version"] != 1
            or document["language"] != language
            or document["char"] != template_char(LANGUAGES[language].id)
            or not isinstance(pairs, list)
            or any(
                not isinstance(pair, list)
                or len(pair) != 2
                or any(not isinstance(item, str) for item in pair)
                for pair in pairs
            )
        ):
            raise AuditError("invalid baseline template")
        try:
            json.dumps(document, ensure_ascii=False).encode("utf-8")
        except UnicodeEncodeError as error:
            raise AuditError("baseline template is not UTF-8") from error
        bindings = esolangs.TemplateBindings(
            document["char"], tuple(tuple(pair) for pair in pairs)
        )
        return esolangs.TemplateArtifact(
            document["source"],
            language,
            bindings,
            decode_settings(document["settings"], language),
        )
    return esolangs.load_program(language, generated.stdout)


def _source_size(artifact: Artifact, unit: str) -> int:
    """Measure emitted characters or rectangular cell/codel area at scale one."""
    program = artifact.source
    if isinstance(program, Raster):
        assert isinstance(artifact, esolangs.ProgramArtifact)
        if artifact.scale != 1:
            raise AuditError("audit raster scale differs from explicit scale one")
        return len(program.rows) * max(map(len, program.rows))
    if unit == "chars":
        return len(program)
    return grid_area(text_source(program))


def _observe(
    language: str,
    program: Artifact,
    bits: list[int],
    table: str,
    record: ReplayRecord,
    deadline: float,
) -> tuple[str, ExecutionResult]:
    """Run a row, retaining input counters and sound termination evidence."""
    lang = LANGUAGES[language]
    if lang.parameterized:
        if not isinstance(program, esolangs.TemplateArtifact):
            raise AuditError("input bindings require a TemplateArtifact")
        program, stdin = esolangs.instantiate(language, program, bits), ""
    else:
        stdin = esolangs.encode_inputs(language, bits, truth_table=table)
    bound = min(5.0, _remaining(deadline))
    if lang.contract.answer_mode == "termination":
        proof = termination_observed(language, program, stdin, bound)
        result = proof.observation
        answer = str(
            lang.contract.answer_values.index(
                "halts" if proof.decision.halts else "diverges"
            )
        )
    else:
        # The in-process guard: a timed public run would start a worker per row.
        result = _run(
            lambda *_args: esolangs.run(
                language, program, stdin=stdin, seed=record.seed
            ),
            "",
            ScriptedIO(""),
            bound,
        )
        answer = esolangs.read_answer(language, result.output)
    positions = {len(stdin)}
    # Numeric token reads leave their final framing LF unread (IO.input_token).
    # Character-stream LFs are payload; empty line encodings also need their LF.
    if (
        stdin.endswith("\n")
        and lang.contract.input_shape in {"line_per_bit", "row_index", "row_number"}
        and all(lang.contract.alphabet)
        and result.input_reads is not None
        and result.input_reads > 0
    ):
        positions.add(len(stdin) - 1)
    if (
        result.input_position not in positions
        or result.input_past_end is None
        or result.input_past_end > 1
    ):
        raise AuditError("audit program violated its input-consumption contract")
    return answer, result


def verify_replay(language: str, record: ReplayRecord, scratch: Path) -> None:
    """Execute declared rows before accepting any measured source figures."""
    deadline = time.monotonic() + record.budget
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        table = _run(
            lambda *_args: record.witness.table(),
            "",
            ScriptedIO(""),
            _remaining(deadline),
        )
        rows = record.rows if record.rows is not None else range(len(table))
        for balanced, measurement in ((False, record.source), (True, record.balanced)):
            if measurement is None:
                continue
            baseline = None
            if record.baseline is not None:
                with tempfile.TemporaryDirectory(
                    dir=scratch, prefix="audit-"
                ) as folder:
                    baseline = _baseline(
                        language,
                        record,
                        table,
                        Path(folder),
                        deadline,
                        balanced=balanced,
                    )
            candidate = _run(
                lambda *_args, balanced=balanced: esolangs.generate(
                    language, table, balance=balanced
                ),
                "",
                ScriptedIO(""),
                _remaining(deadline),
            )
            for row in rows:
                bits = [int(c) for c in f"{row:0{record.witness.arity}b}"]
                answer, after = _observe(
                    language, candidate, bits, table, record, deadline
                )
                if answer != table[row]:
                    raise AuditError(f"audit answer differs at row {row}")
                if baseline is not None:
                    answer, before = _observe(
                        language, baseline, bits, table, record, deadline
                    )
                    if answer != table[row]:
                        raise AuditError(f"baseline answer differs at row {row}")
                    if _input_usage(before) != _input_usage(after):
                        raise AuditError(f"audit input usage differs at row {row}")
            measured = (
                _source_size(baseline, measurement.unit)
                if baseline is not None
                else None,
                _source_size(candidate, measurement.unit),
            )
            if measured != (measurement.before, measurement.after):
                raise AuditError(
                    f"audit source size {measured} != "
                    f"{(measurement.before, measurement.after)}"
                )
            _remaining(deadline)
    except (esolangs.EsolangError, subprocess.SubprocessError) as error:
        raise AuditError(f"audit execution failed: {error}") from error
