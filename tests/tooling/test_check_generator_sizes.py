"""Tests for the emitted-size and step-count baseline gate."""

import hashlib
import json
import os
from dataclasses import replace
from typing import Any

import pytest

import esolangs
from checks.check_generator_sizes import (
    BOUNDARIES,
    SCHEMA,
    TABLES,
    baseline,
    boundary_tables,
    control_tables,
    differences,
    recorded_baseline,
)
from esolangs.registry._certification import load as load_certification
from scripts import benchmark as b
from tests.support.pick import first, one_where, spread
from tests.support.reference import REFERENCE

RECORD = {
    "language": REFERENCE,
    "truth_table": TABLES[0],
    "source_units": 205,
    "commands": 179,
    "generation_ns_best": 1234,
    "generation_ns_median": 5678,
}


def _measured() -> dict[str, Any]:
    return baseline([dict(RECORD)])


class TestProjection:
    """A sweep is reduced to exactly the fields that repeat run to run."""

    def test_timings_are_dropped(self) -> None:
        rows = _measured()["records"][REFERENCE][TABLES[0]]
        assert rows == {"source_units": 205, "commands": 179}

    def test_the_header_carries_only_the_schema_and_cap(self) -> None:
        """The corpus is the record keys; a header copy of it could disagree."""
        assert set(_measured()) == {"schema", "step_cap", "records"}


class TestDifferences:
    """Every way the measurement can disagree with the baseline is reported."""

    def test_an_identical_baseline_is_silent(self) -> None:
        assert differences(_measured(), _measured()) == []

    def test_a_size_change_is_reported(self) -> None:
        changed = baseline([{**RECORD, "source_units": 206}])
        assert differences(_measured(), changed) == [
            f"brainfuck [{TABLES[0]}] source_units: 205 -> 206"
        ]

    def test_a_step_count_change_is_reported(self) -> None:
        changed = baseline([{**RECORD, "commands": 180}])
        assert differences(_measured(), changed) == [
            f"brainfuck [{TABLES[0]}] commands: 179 -> 180"
        ]

    def test_a_win_fails_too(self) -> None:
        """A smaller program is still a diff the baseline has to record."""
        smaller = baseline([{**RECORD, "source_units": 12}])
        assert differences(_measured(), smaller) != []

    def test_a_new_language_is_reported(self) -> None:
        added = baseline([dict(RECORD), {**RECORD, "language": "Newcomer"}])
        assert differences(_measured(), added) == [
            "Newcomer: not in the baseline (new language?)"
        ]

    def test_a_dropped_language_is_reported(self) -> None:
        empty = baseline([])
        assert differences(_measured(), empty) == [
            "brainfuck: in the baseline but not in the registry"
        ]

    def test_a_stale_schema_short_circuits(self) -> None:
        stale = {**_measured(), "schema": SCHEMA - 1}
        assert differences(stale, _measured()) == [
            f"baseline schema {SCHEMA - 1!r}, expected {SCHEMA}"
        ]

    def test_corpus_drift_does_not_mask_changes_to_shared_witnesses(self) -> None:
        other = {**RECORD, "language": "Other"}
        stale = baseline([RECORD, {**RECORD, "truth_table": "1001"}, other])
        measured = baseline(
            [{**RECORD, "commands": 180}, {**other, "source_units": 206}]
        )
        assert differences(stale, measured) == [
            f"baseline corpus changed for {REFERENCE}; re-record it",
            f"Other [{TABLES[0]}] source_units: 205 -> 206",
            f"{REFERENCE} [{TABLES[0]}] commands: 179 -> 180",
        ]


class TestCommittedBaseline:
    """The fragments in the tree are the corpus this gate claims to cover."""

    def test_it_covers_every_language_and_table(self) -> None:
        recorded = recorded_baseline()
        assert recorded["schema"] == SCHEMA
        assert recorded["records"]
        for name, rows in recorded["records"].items():
            assert sorted(rows) == sorted(
                {*control_tables(name), *boundary_tables(name)}
            ), name
            for table, fields in rows.items():
                assert fields["source_units"] > 0, (name, table)


@pytest.mark.parametrize(
    "target_kind",
    [
        "directory",
        "baseline",
        "missing-baseline",
        pytest.param(
            "baseline-alias",
            marks=pytest.mark.skipif(os.name != "posix", reason="POSIX symlink"),
        ),
    ],
)
def test_timing_destination_is_checked_before_the_sweep(
    tmp_path,
    monkeypatch,
    capsys,
    target_kind,
) -> None:
    from checks import check_generator_sizes as sizes

    packages = tmp_path / "packages"
    monkeypatch.setattr(sizes.generator_sizes, "PACKAGES", packages)
    fragment = packages / sizes.LANGUAGES[REFERENCE].id / "language.toml"
    target = tmp_path if target_kind == "directory" else fragment
    if target_kind in {"baseline", "baseline-alias"}:
        fragment.parent.mkdir(parents=True)
        fragment.write_bytes(b"[generator_sizes]\n")
    if target_kind == "baseline-alias":
        target = tmp_path / "timings.json"
        target.symlink_to(fragment)
    monkeypatch.setattr(
        sizes, "sweep", lambda **_kwargs: pytest.fail("invalid output started a sweep")
    )
    with pytest.raises(SystemExit) as caught:
        sizes.main(["--timings", str(target)])
    assert caught.value.code == 2
    diagnostic = capsys.readouterr().err
    assert str(target) in diagnostic
    if target_kind == "directory":
        assert "directory" in diagnostic
    else:
        assert "would replace a language baseline" in diagnostic
    if target_kind in {"baseline", "baseline-alias"}:
        assert fragment.read_bytes() == b"[generator_sizes]\n"
    else:
        assert not fragment.exists()


def test_timing_publication_preserves_existing_report_on_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    from checks import check_generator_sizes as sizes
    from esolangs.runtime import _files

    report = tmp_path / "timings.json"
    original = b'["previous sweep"]\n'
    report.write_bytes(original)

    def sweep(**_kwargs):
        assert list(tmp_path.iterdir()) == [report]
        return [RECORD]

    def refuse_replace(*_args, **_kwargs):
        raise PermissionError("cannot replace timing report")

    monkeypatch.setattr(sizes, "sweep", sweep)
    monkeypatch.setattr(sizes, "recorded_baseline", _measured)
    command = ["--timings", str(report)]
    with monkeypatch.context() as scoped:
        scoped.setattr(_files.os, "replace", refuse_replace)
        with pytest.raises(SystemExit) as caught:
            sizes.main(command)
    assert caught.value.code == 2
    assert "cannot replace timing report" in capsys.readouterr().err
    assert report.read_bytes() == original
    assert list(tmp_path.iterdir()) == [report]

    assert sizes.main(command) == 0
    assert json.loads(report.read_text()) == [RECORD]
    assert list(tmp_path.iterdir()) == [report]


def test_update_does_not_rewrite_an_unchanged_baseline(
    tmp_path, monkeypatch, capsys
) -> None:
    """``--update`` on an in-sync baseline reports it instead of rewriting it."""
    from checks import check_generator_sizes as sizes

    lang = sizes.LANGUAGES[REFERENCE]
    packages = tmp_path / "packages"
    (packages / lang.id).mkdir(parents=True)
    fragment = packages / lang.id / "language.toml"
    monkeypatch.setattr(sizes.generator_sizes, "PACKAGES", packages)
    monkeypatch.setattr(sizes, "LANGUAGES", {REFERENCE: lang})
    record = {
        **RECORD,
        "commands": None,
        "executions": [{"row": 0, "commands": 179}, {"row": 3, "commands": None}],
    }
    monkeypatch.setattr(sizes, "sweep", lambda **_kwargs: [record])
    assert sizes.main(["--update"]) == 0
    assert "wrote the package-fragment baseline" in capsys.readouterr().out
    assert "commands =" not in fragment.read_text()
    assert sizes.recorded_baseline() == baseline([record])
    before = (fragment.read_bytes(), fragment.stat().st_mtime_ns)
    assert sizes.main(["--update"]) == 0
    out = capsys.readouterr().out
    assert "baseline unchanged: 1 generator measurements already recorded" in out
    assert "wrote" not in out
    assert (fragment.read_bytes(), fragment.stat().st_mtime_ns) == before


def test_update_preflights_later_fragments_before_writing(tmp_path) -> None:
    from checks.check_generator_sizes import LANGUAGES
    from checks.generator_sizes import write_fragments

    first = LANGUAGES[REFERENCE]
    second = replace(first, id="second", name="Second")
    path = tmp_path / first.id / "language.toml"
    path.parent.mkdir()
    original = '[reference]\nmarker = "keep"\n'
    path.write_text(original, encoding="utf-8")
    bad = tmp_path / second.id / "language.toml"
    bad.parent.mkdir()
    invalid = '[generator_sizes]\n# move this comment\n"01" = {}\n'
    bad.write_text(invalid, encoding="utf-8")
    row = {"source_units": 4, "commands": 2, "commands_by_row": {"0": 1, "1": 2}}
    records = {first.name: {"01": row}, second.name: {"01": row}}

    with pytest.raises(ValueError, match="comment inside"):
        write_fragments(tmp_path, [first, second], records)
    assert path.read_text(encoding="utf-8") == original
    assert bad.read_text(encoding="utf-8") == invalid

    bad.write_text(invalid.replace("# move this comment\n", ""), encoding="utf-8")
    assert write_fragments(tmp_path, [first, second], records)
    assert path.read_text(encoding="utf-8").startswith(original)
    assert not write_fragments(tmp_path, [first, second], records)


@pytest.mark.parametrize("matches", [False, None])
def test_sweep_refuses_incorrect_or_undecided_rows(monkeypatch, matches) -> None:
    from checks import check_generator_sizes as sizes

    monkeypatch.setattr(sizes.esolangs, "list_languages", lambda: [REFERENCE])
    monkeypatch.setattr(sizes, "BOUNDARIES", {})
    monkeypatch.setattr(sizes, "STEP_CAP", 1)
    measured = []

    def measure(name, table, **_kwargs):
        measured.append((name, table))
        return {
            **RECORD,
            "row": 0,
            "matches": matches,
            "execution_status": "step_cap",
            "expected_answer": "1",
            "actual_answer": None,
        }

    monkeypatch.setattr(sizes, "measure", measure)
    with pytest.raises(ValueError, match="expected 1, got None") as caught:
        sizes.sweep(repeat=2)
    assert "--row 0 --step-cap 1 --repeat 2" in str(caught.value)
    assert measured == [(REFERENCE, TABLES[0])]


def test_boundary_rows_are_pinned_and_corpus_drift_fails() -> None:
    name = next(iter(BOUNDARIES))
    table = boundary_tables(name)[0]
    measured = baseline(
        [
            {
                **RECORD,
                "language": name,
                "truth_table": table,
                "executions": [{"row": 0, "commands": 2}, {"row": 1, "commands": 3}],
            }
        ]
    )
    assert measured["records"][name][table]["commands_by_row"] == {
        "0": 2,
        "1": 3,
    }
    stale = {**measured, "records": {name: {}}}
    assert differences(stale, measured) == [
        f"baseline corpus changed for {name}; re-record it"
    ]


def test_sweep_checks_and_pins_every_small_table_row(monkeypatch) -> None:
    from checks import check_generator_sizes as sizes

    monkeypatch.setattr(sizes.esolangs, "list_languages", lambda: [REFERENCE])
    monkeypatch.setattr(sizes, "BOUNDARIES", {})
    records = sizes.sweep()
    pinned = sizes.baseline(records)["records"][REFERENCE]
    assert len(records) == 8
    for record in records:
        table = record["truth_table"]
        executions = record["executions"]
        assert [row["row"] for row in executions] == list(range(len(table)))
        assert all(row["matches"] is True for row in executions)
        assert len(pinned[table]["commands_by_row"]) == len(table)


def test_executed_artifact_and_provenance() -> None:
    r = b.measure("Brainfuck", "01", repeat=1, row=1, step_cap=10000, all_rows=True)
    program = esolangs.generate("Brainfuck", "01")
    p = program.source
    _, record_digest = b.artifact_digests(program)
    assert all(row["matches"] for row in r["executions"])
    assert r["schema"] == 6
    assert r["provenance"]["generated_artifact_sha256"] == b.artifact_hash(p)
    assert all(row["artifact_sha256"] == b.artifact_hash(p) for row in r["executions"])
    assert r["provenance"]["generated_record_sha256"] == record_digest
    assert all(row["record_sha256"] == record_digest for row in r["executions"])
    assert len(r["provenance"]["commit"]) == 40
    assert isinstance(r["provenance"]["dirty"], bool)
    # Matches timings across runners that share a platform() string.
    assert r["provenance"]["cpu"] == b.cpu_model() != ""
    assert b.artifact_hash("é") == hashlib.sha256(b"text\0" + "é".encode()).hexdigest()
    pixel = (0, 0, 0)
    assert b.artifact_hash(esolangs.Raster(((pixel, pixel),))) != b.artifact_hash(
        esolangs.Raster(((pixel,), (pixel,)))
    )


@pytest.mark.parametrize("replay", [False, True])
def test_benchmark_replays_only_halts_without_proof_counts(monkeypatch, replay) -> None:
    name = first(answer_mode="termination", parameterized=False)
    facts = esolangs.describe(name)
    halt = str(facts.answer_encoding.index("halts"))
    pinned = recorded_baseline()["records"][name]
    table = next(table for table in pinned if halt in table)
    row = table.index(halt)
    expected = pinned[table]["commands_by_row"][str(row)]
    make_vm = b.debugger_api.make_vm
    constructions = 0

    def counted(*args, **kwargs):
        nonlocal constructions
        constructions += 1
        return make_vm(*args, **kwargs)

    monkeypatch.setattr(b.debugger_api, "make_vm", counted)
    if replay:
        prove = b._halt_or_cycle_result

        def without_count(*args, **kwargs):
            return prove(*args, **kwargs)._replace(commands=None)

        monkeypatch.setattr(b, "_halt_or_cycle_result", without_count)
    record = b._execute(name, esolangs.generate(name, table), table, row, 10000, 5.0)
    assert record["matches"] is True
    assert record["execution_status"] == "halted"
    assert record["commands"] == expected
    assert constructions == 1 + replay


def test_raster_artifact_hash_preserves_canonical_rows() -> None:
    raster = esolangs.Raster(
        (((0, 1, 2), (10, 20, 30)), ((4, 5, 6), (0, 0, 0)))
    ).upscaled(3)
    payload = json.dumps(raster.rows, separators=(",", ":")).encode()
    assert b.artifact_hash(raster) == hashlib.sha256(b"rgb\0" + payload).hexdigest()


def test_artifact_digests_distinguish_execution_metadata() -> None:
    def distinct_records(before, after):
        first_source, first_record = b.artifact_digests(before)
        second_source, second_record = b.artifact_digests(after)
        assert first_source == second_source
        assert first_record != second_record

    (name,) = one_where(lambda facts: "rotation" in facts.dialect_settings)
    language = esolangs.Language(name)
    source = "+,"
    forward = language.from_source(
        source, settings=language.settings(rotation="forward")
    )
    backward = language.from_source(
        source, settings=language.settings(rotation="backward")
    )
    distinct_records(forward, backward)
    assert language.run(forward).output == "\x01"
    assert language.run(backward).output == ""

    raster = esolangs.generate(
        first(source_kind="raster", boolean_generator=True), "01"
    )
    assert isinstance(raster, esolangs.ProgramArtifact)
    distinct_records(raster, replace(raster, scale=2))
    distinct_records(raster, replace(raster, input_arity=2))

    template = esolangs.generate(first(parameterized=True), "01")
    assert isinstance(template, esolangs.TemplateArtifact)
    ((zero, one),) = template.bindings.setters
    bindings = replace(template.bindings, setters=((one, zero),))
    distinct_records(template, replace(template, bindings=bindings))


# One language per artifact route: the measurement path branches on these
# facts, not the language, and CI's size baseline measures every generator.
@pytest.mark.parametrize(
    "language",
    spread(
        "source_kind",
        "parameterized",
        "answer_mode",
        "input_shape",
        boolean_generator=True,
    ),
)
@pytest.mark.usefixtures("retired_source_adapters")
def test_benchmark_uses_artifacts_without_source_facades(language):
    generated = esolangs.generate(language, "01")
    filled = (
        generated.fill([1])
        if isinstance(generated, esolangs.TemplateArtifact)
        else generated
    )

    with b.evidence_session():
        record = b._measure(
            language, "01", repeat=1, row=1, step_cap=200000, all_rows=True
        )
    assert all(row["matches"] for row in record["executions"])
    assert record["artifact_sha256"] == b.artifact_hash(filled.source)
    assert record["provenance"]["generated_artifact_sha256"] == b.artifact_hash(
        generated.source
    )
    assert (
        record["provenance"]["generated_record_sha256"]
        == b.artifact_digests(generated)[1]
    )
    assert record["record_sha256"] == b.artifact_digests(filled)[1]
    source = generated.source
    if isinstance(source, esolangs.Raster):
        assert isinstance(generated, esolangs.ProgramArtifact)
        width, height = len(source.rows[0]), len(source.rows)
        assert record["source_unit"] == "pixels"
        assert record["source_units"] == width * height
        assert record["source_utf8_bits"] is None
        assert record["raster"] == {
            "width": width,
            "height": height,
            "scale": generated.scale,
        }
    else:
        assert record["source_unit"] == "characters"
        assert record["source_units"] == len(source)
        assert record["raster"] is None


def test_checkout_change_invalidates_benchmark(monkeypatch) -> None:
    identities = iter([{"commit": "before"}, {"commit": "after"}])
    monkeypatch.setattr(b, "source_identity", lambda **_: next(identities))
    with pytest.raises(RuntimeError, match="checkout changed"):
        b.measure("Brainfuck", "01", repeat=1, row=1, step_cap=100)


def test_benchmark_cli_reports_checkout_change_without_results(monkeypatch, capsys):
    identities = iter([{"commit": "before"}, {"commit": "after"}])
    monkeypatch.setattr(b, "source_identity", lambda **_: next(identities))
    assert b.main(["Brainfuck", "01", "--repeat", "1", "--all-rows"]) == 1
    output, error = capsys.readouterr()
    assert not output
    assert error.splitlines()[-1] == (
        "checkout changed during benchmark. Rerun once the checkout is stable."
    )


@pytest.mark.parametrize(
    "phase",
    [
        "generation",
        pytest.param("execution", marks=pytest.mark.medium),
        pytest.param("preparation", marks=pytest.mark.medium),
        "startup",
    ],
)
def test_benchmark_deadline_reaps_workers_with_positive_control(
    tmp_path, monkeypatch, phase
) -> None:
    import sys
    import time
    from pathlib import Path

    factory = b.Worker
    marker = tmp_path / "worker"
    child = f"""
import time
from pathlib import Path
p = Path({str(marker)!r})
while True:
    p.write_text(str(time.monotonic()))
    time.sleep(0.01)
"""
    # The grandchild is spawned first, and the worker is started and the
    # marker awaited before ``measure`` starts the clock: the generation
    # deadline counts from spawn, so on a slow macOS runner 1s once ran out
    # during interpreter startup and ``import benchmark``, killing the tree
    # before the grandchild existed and leaving no marker to check.
    setup = f"""
import sys, subprocess, time
subprocess.Popen([sys.executable, '-c', {child!r}])
"""
    if phase == "startup":
        setup += "time.sleep(30)"
    else:
        target = {
            "generation": "esolangs.generate",
            "preparation": "esolangs.prepare",
            "execution": "_execute",
        }[phase]
        setup += f"""
sys.path.insert(0, {str(Path(__file__).resolve().parents[2] / "scripts")!r})
import benchmark
def hang(*args, **kwargs):
    time.sleep(30)
benchmark.{target} = hang
benchmark._worker_main()
"""

    def started() -> b.Worker:
        worker = factory([sys.executable, "-c", setup])
        worker.start()
        waited = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < waited:
            time.sleep(0.01)
        assert marker.exists(), "the grandchild never started"
        return worker

    monkeypatch.setattr(b, "Worker", started)
    start = time.monotonic()
    expected = "execution" if phase in {"execution", "preparation"} else "generation"
    with pytest.raises(esolangs.ExecutionTimeoutError, match=f"{expected} deadline"):
        b.measure(
            "Brainfuck",
            "0" * 131072 if phase == "startup" else "01",
            repeat=1,
            row=1,
            step_cap=10000,
            timeout=1,
            generation_timeout=1,
            all_rows=phase == "preparation",
        )
    # The worker sleeps 30s, so the 1s deadline ending the call well before
    # that is the fact under test.  The bound stays loose because an xdist
    # sibling or a shared CI runner can deschedule this process for seconds;
    # at 4s it failed a clean run under load.
    assert time.monotonic() - start < 15
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before
    monkeypatch.setattr(b, "Worker", factory)
    record = b.measure(
        "Brainfuck", "01", repeat=1, row=1, step_cap=10000, all_rows=True
    )
    assert all(row["matches"] for row in record["executions"])


@pytest.mark.parametrize(
    "verdict", [None, ("Total", "Language lower bound"), ("Cap", "Linear")]
)
def test_custom_corpus_cannot_hide_an_unproved_scaling_failure(
    monkeypatch, verdict
) -> None:
    from dataclasses import replace
    from types import SimpleNamespace

    from checks import check_generator_sizes as sizes
    from docs import proof_status

    record = replace(
        load_certification(sizes.LANGUAGES[REFERENCE]), benchmark_tables=("01",)
    )
    monkeypatch.setattr(sizes, "load_certification", lambda _lang: record)
    rows = (
        ()
        if verdict is None
        else (
            SimpleNamespace(
                generator=REFERENCE, totality=verdict[0], output_size=verdict[1]
            ),
        )
    )
    monkeypatch.setattr(proof_status, "load", lambda: ((), rows))
    with pytest.raises(ValueError, match="proved resource cap"):
        sizes.control_tables(REFERENCE)
