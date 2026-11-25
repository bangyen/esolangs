"""Shard evidence proves successful, exactly-once execution of fresh collection."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from shutil import copytree

import pytest

from checks.check_shard_manifests import check
from scripts.ci.shard import Recorder, load_durations, load_run, refresh, refresh_main


def evidence(tmp_path):
    paths = []
    for index, selected in enumerate((["a"], ["b"])):
        directory = tmp_path / str(index)
        directory.mkdir()
        path = directory / "tests.shard.json"
        recorder = Recorder(directory / "test-durations.json")
        recorder.collected.update(selected + (["serial"] if index == 0 else []))
        recorder.finished.update(recorder.collected)
        recorder.durations.update(dict.fromkeys(recorder.collected, 1))
        recorder.pytest_sessionfinish(0)
        # Mirror pytest_shard: the manifest carries the same run identity the
        # Recorder stamps from GITHUB_* (and platform) into its sidecar.  A
        # null identity here would disagree with the sidecar in CI, where
        # those variables are set, and check() would fail closed on the
        # identity before ever reaching the injected fault.
        run = json.loads((directory / "test-durations.json.meta.json").read_text())[
            "run"
        ]
        path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "shard": index,
                    "shards": 2,
                    "marker": "slow",
                    "collected": ["a", "b", "serial"],
                    "selected": selected,
                    "excluded": ["serial"],
                    "run": {key: run[key] for key in ("id", "attempt", "commit")},
                }
            )
        )
        paths.append(path)
    return paths


@pytest.mark.parametrize("duplicate", ["directory", "ID"])
def test_timing_refresh_rejects_duplicate_runs(
    tmp_path, monkeypatch, duplicate
) -> None:
    directories = []
    for index, seconds in enumerate((1, 4, 16)):
        directory = tmp_path / str(index)
        if duplicate == "directory":
            monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
            monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
        else:
            monkeypatch.setenv("GITHUB_RUN_ID", str(index // 2))
            monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(1 + index % 2))
        recorder = Recorder(directory / "timings.json")
        recorder.collected.add("a")
        recorder.finished.add("a")
        recorder.durations["a"] = seconds
        recorder.pytest_sessionfinish(0)
        directories.append(directory)

    destination = tmp_path / "snapshot.json"
    refresh(directories, ["a"], destination)
    assert load_durations(destination)["a"] == pytest.approx(4)
    unchanged = destination.read_bytes()

    repeated = directories[0]
    if duplicate == "ID":
        repeated = copytree(repeated, tmp_path / "copy")
    with pytest.raises(ValueError, match=f"duplicate timing run {duplicate}"):
        refresh([*directories, repeated], ["a"], destination)
    assert destination.read_bytes() == unchanged


def test_complete_shards_include_serial_exclusion(tmp_path) -> None:
    paths = evidence(tmp_path)
    check(paths, ["a", "b", "serial"], "slow", 2)


def test_shard_completion_must_match_the_verifiers_python(tmp_path) -> None:
    paths = evidence(tmp_path)
    sidecar = paths[1].parent / "test-durations.json.meta.json"
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
    metadata["run"]["python"] = f"{python}.99"
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    check(paths, ["a", "b", "serial"], "slow", 2)

    metadata["run"]["python"] = (
        f"{sys.version_info.major}.{sys.version_info.minor + 1}.0"
    )
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match=r"completion Python.*verifier") as error:
        check(paths, ["a", "b", "serial"], "slow", 2)
    assert str(sidecar) in str(error.value)


def test_empty_shards_validate_completion_evidence_when_present(tmp_path) -> None:
    paths = evidence(tmp_path)
    corpus = ["a", "serial"]
    for path in paths:
        manifest = json.loads(path.read_text())
        manifest["collected"] = corpus
        if path == paths[1]:
            manifest["selected"] = []
        path.write_text(json.dumps(manifest))
    recorder = Recorder(paths[1].parent / "test-durations.json")
    sidecar = recorder.path.with_suffix(".json.meta.json")
    recorder.pytest_sessionfinish(0)
    check(paths, corpus, "slow", 2)

    recorder.pytest_sessionfinish(1)
    with pytest.raises(ValueError, match="failed, incomplete, or altered") as error:
        check(paths, corpus, "slow", 2)
    assert str(sidecar) in str(error.value)

    sidecar.unlink()
    check(paths, corpus, "slow", 2)


def test_duplicate_manifest_fields_cannot_replace_a_shard_selection(tmp_path) -> None:
    paths = evidence(tmp_path)
    manifest = paths[0]
    original = manifest.read_text(encoding="utf-8")
    manifest.write_text('{"selected":["other"],' + original[1:], encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate field: selected") as error:
        check(paths, ["a", "b", "serial"], "slow", 2)
    assert str(manifest) in str(error.value)


def test_timing_refresh_preserves_census_dates(tmp_path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    evidence(run)
    destination = tmp_path / "snapshot.json"
    collected = {"curation": "2026-10-06", "bf_derivatives": "2026-10-15"}
    destination.write_text(json.dumps({"collected": collected, "durations": {}}))
    refresh([run], ["a", "b", "serial"], destination)
    observed = json.loads(destination.read_text())["collected"]
    assert observed.pop("durations")
    assert observed == collected


def test_unroundable_timing_names_the_sample_and_preserves_the_snapshot(
    tmp_path, monkeypatch, capsys
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    timings = run / "timings.json"
    recorder = Recorder(timings)
    recorder.collected.add("test_example")
    recorder.finished.add("test_example")
    recorder.durations["test_example"] = sys.float_info.max
    recorder.pytest_sessionfinish(0)
    artifact = json.loads(timings.with_suffix(".json.meta.json").read_text())[
        "durations_file"
    ]
    output = tmp_path / "snapshot.json"
    previous = b'{"collected": {"curation": "2026-10-06"}, "durations": {}}\n'
    output.write_bytes(previous)
    monkeypatch.setattr("scripts.ci.shard.collect_ids", lambda _: ["test_example"])

    with pytest.raises(SystemExit) as caught:
        refresh_main([str(run), "--output", str(output)])
    assert caught.value.code == 2
    message = capsys.readouterr().err
    assert str(run / artifact) in message
    assert "duration for 'test_example' cannot be rounded" in message
    assert output.read_bytes() == previous


@pytest.mark.parametrize(
    "malformed",
    [
        '{"collected": {"curation": "2026-10-06"},',
        '{"collected":{"curation": null}}',
        '{"collected":{"curation":"2026-10-06","curation":"2026-10-07"}}',
    ],
)
def test_timing_refresh_reports_and_preserves_invalid_snapshot(
    tmp_path, monkeypatch, capsys, malformed
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    evidence(run)
    destination = tmp_path / "snapshot.json"
    destination.write_text(malformed, encoding="utf-8")
    monkeypatch.setattr(
        "scripts.ci.shard.collect_ids", lambda _marker: ["a", "b", "serial"]
    )
    with pytest.raises(SystemExit) as error:
        refresh_main([str(run), "--output", str(destination)])
    assert error.value.code == 2
    assert str(destination) in capsys.readouterr().err
    assert destination.read_text(encoding="utf-8") == malformed


@pytest.mark.parametrize("kind", ["duration", "completion"])
def test_duplicate_timing_fields_report_the_file_and_leave_the_snapshot(
    tmp_path, kind
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    paths = evidence(run)
    output = tmp_path / "snapshot.json"
    nodes = ["a", "b", "serial"]
    refresh([run], nodes, output)
    previous = output.read_bytes()
    sidecar = paths[0].parent / "test-durations.json.meta.json"
    complete = sidecar.read_text(encoding="utf-8")
    if kind == "duration":
        metadata = json.loads(complete)
        path = sidecar.parent / metadata["durations_file"]
        key = "a"
        data = b'{"a": -1, "a": 1, "serial": 1}'
        path.write_bytes(data)
        metadata["durations_sha256"] = hashlib.sha256(data).hexdigest()
        sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    else:
        path = sidecar
        key = "python"
        path.write_text(
            complete.replace('"run": {', '"run": {"python": "other", ', 1),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match=f"duplicate field: {key}") as error:
        refresh([run], nodes, output)
    assert str(path) in str(error.value)
    assert output.read_bytes() == previous
    with pytest.raises(ValueError, match=f"duplicate field: {key}"):
        check(paths, nodes, "slow", 2)


def test_timing_load_parses_the_snapshot_it_hashed(tmp_path, monkeypatch) -> None:
    directory = evidence(tmp_path)[0].parent
    metadata = json.loads((directory / "test-durations.json.meta.json").read_text())
    snapshot = directory / metadata["durations_file"]
    replacement = tmp_path / "replacement.json"
    replacement.write_text('{"a": 900, "serial": 1}')
    read_bytes = Path.read_bytes

    def read_and_replace(path):
        data = read_bytes(path)
        if path == snapshot:
            replacement.replace(snapshot)
        return data

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "read_bytes", read_and_replace)
        assert load_run(directory, {"a", "serial"}) == {"a": 1, "serial": 1}
    with pytest.raises(ValueError, match="altered timing run"):
        load_run(directory, {"a", "serial"})


@pytest.mark.parametrize("variable", ["GITHUB_RUN_ID", "GITHUB_SHA"])
def test_shard_evidence_must_match_active_ci_run(tmp_path, monkeypatch, variable):
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    paths = evidence(tmp_path)
    check(paths, ["a", "b", "serial"], "slow", 2)

    monkeypatch.setenv(variable, "101" if variable == "GITHUB_RUN_ID" else "b" * 40)
    with pytest.raises(ValueError, match="differs from the active CI run"):
        check(paths, ["a", "b", "serial"], "slow", 2)
    monkeypatch.delenv("GITHUB_RUN_ID")
    monkeypatch.delenv("GITHUB_SHA")
    check(paths, ["a", "b", "serial"], "slow", 2)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run", None),
        ("collected", [{}]),
        ("collected", ["b", "b"]),
        ("schema", True),
        ("schema", 1.0),
        ("exitstatus", False),
        ("exitstatus", 0.0),
    ],
)
def test_bad_completion_fields_name_the_sidecar(tmp_path, field, value) -> None:
    paths = evidence(tmp_path)
    sidecar = paths[1].parent / "test-durations.json.meta.json"
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata[field] = value
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(
        ValueError, match=f"invalid completion field '{field}'"
    ) as error:
        check(paths, ["a", "b", "serial"], "slow", 2)
    assert str(sidecar) in str(error.value)
    with pytest.raises(ValueError, match=f"invalid completion field '{field}'"):
        load_run(paths[1].parent, {"b"})


@pytest.mark.parametrize(
    ("key", "value"), [("python", []), ("attempt", {}), ("harness", False)]
)
def test_refresh_names_invalid_identity_values_before_replacing_snapshot(
    tmp_path, monkeypatch, capsys, key, value
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    paths = evidence(run)
    sidecar = paths[1].parent / "test-durations.json.meta.json"
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata["run"][key] = value
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    previous = b'{"collected":{},"durations":{}}\n'
    snapshot.write_bytes(previous)
    monkeypatch.setattr("scripts.ci.shard.collect_ids", lambda _: ["a", "b", "serial"])
    with pytest.raises(SystemExit) as error:
        refresh_main([str(run), "--output", str(snapshot)])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert str(sidecar) in message
    assert f"invalid completion field 'run.{key}'" in message
    assert snapshot.read_bytes() == previous


def test_refresh_names_all_stale_serial_node_ids(tmp_path, monkeypatch, capsys) -> None:
    snapshot = tmp_path / "snapshot.json"
    previous = b'{"collected":{},"durations":{}}\n'
    snapshot.write_bytes(previous)
    existing = "test_example.py::test_kept"
    unknown = ["test_example.py::test_deleted", "test_example.py::test_typo"]
    monkeypatch.setattr("scripts.ci.shard.collect_ids", lambda _: [existing])
    with pytest.raises(SystemExit) as error:
        refresh_main(
            [
                str(tmp_path),
                "--output",
                str(snapshot),
                *(f"--serial-node={node}" for node in [*reversed(unknown), existing]),
            ]
        )
    assert error.value.code == 2
    message = capsys.readouterr().err.splitlines()[-1]
    assert message.endswith(
        "--serial-node: not in the collected corpus: " + ", ".join(map(repr, unknown))
    )
    assert snapshot.read_bytes() == previous


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "index",
        "overlap",
        "omission",
        "corpus",
        "identity",
        "failed",
        "unfinished",
        "altered",
    ],
)
def test_bad_shard_evidence_fails_closed(tmp_path, fault) -> None:
    paths = evidence(tmp_path)
    manifest = json.loads(paths[1].read_text())
    if fault == "missing":
        paths.pop()
    elif fault == "index":
        manifest["shard"] = 0
    elif fault == "overlap":
        manifest["selected"] = ["a"]
    elif fault == "omission":
        manifest["selected"] = []
    elif fault == "corpus":
        manifest["collected"] = ["b"]
    elif fault == "identity":
        manifest["run"]["commit"] = "different"
    else:
        sidecar = paths[1].parent / "test-durations.json.meta.json"
        metadata = json.loads(sidecar.read_text())
        if fault == "failed":
            metadata["exitstatus"] = 1
        elif fault == "unfinished":
            metadata["finished"] = []
        else:
            (sidecar.parent / metadata["durations_file"]).write_text("{}")
        sidecar.write_text(json.dumps(metadata))
    if fault != "missing":
        paths[1].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=r"shard|test|run|timing"):
        check(paths, ["a", "b", "serial"], "slow", 2)


@pytest.mark.medium
def test_real_shards_publish_complete_execution_evidence(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from scripts.ci import shard as pytest_shard

    (tmp_path / "test_example.py").write_text(
        "def test_one():\n    assert 1 + 1 == 2\n\n"
        "def test_two():\n    assert 2 + 2 == 4\n"
        "def test_serial():\n    assert 3 + 3 == 6\n"
    )
    monkeypatch.setattr(pytest_shard, "ROOT", tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k 'test_one or test_serial'")
    paths = []
    for index in range(2):
        directory = tmp_path / str(index)
        path = directory / "test.shard.json"
        assert (
            pytest_shard.shard_main(
                [
                    "--marker",
                    "not slow",
                    "--shard",
                    str(index),
                    "--shards",
                    "2",
                    "--manifest",
                    str(path),
                    "--exclude-node",
                    "test_example.py::test_serial",
                    "--",
                    "-q",
                    "-p",
                    "scripts.ci.shard",
                    "--duration-output",
                    str(directory / "durations.json"),
                ]
            )
            == 0
        )
        paths.append(path)
    corpus = pytest_shard.collect_ids("not slow")
    assert corpus == [
        "test_example.py::test_one",
        "test_example.py::test_serial",
        "test_example.py::test_two",
    ]
    with pytest.raises(ValueError, match="omit"):
        check(paths, corpus, "not slow", 2)
    monkeypatch.delenv("PYTEST_ADDOPTS")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "scripts.ci.shard",
            "--duration-output",
            str(paths[0].parent / "serial.json"),
            "test_example.py::test_serial",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=30,
    )
    check(paths, corpus, "not slow", 2)
