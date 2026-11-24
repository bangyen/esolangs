"""Reject malformed worker records without losing legitimate row deadlines."""

import json
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest

from esolangs.registry import LANGUAGES
from scripts.benchmark import MAX_RECORD_CHARS, Worker
from tests.support.pick import one_where


@pytest.mark.parametrize(
    "records",
    [
        [{"phase": "execution", "index": 0}],
        [{"phase": "generation"}, {"phase": "generation"}],
        [
            {"phase": "generation"},
            {"phase": "execution", "index": 0},
            {"phase": "execution", "index": 0},
        ],
        [{"phase": "generation"}, {"phase": "execution", "index": 1}],
        [
            {"phase": "generation"},
            {"phase": "execution", "index": 0},
            {"execution": {"row": 1}},
        ],
        [
            {"phase": "generation"},
            {"phase": "execution", "index": 0},
            {"execution": {"row": 0}},
            {"phase": "execution", "index": 1},
            {"result": {}},
        ],
        [{"result": {}}],
        [[]],
        [{"error": {"message": "bad"}}],
    ],
)
def test_invalid_protocol_reaps_worker(records) -> None:
    command = (
        "import sys,time; "
        + "; ".join(f"print({json.dumps(record)!r}, flush=True)" for record in records)
        + "; time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError):
        worker.measure({"timeout": 1, "table": "01", "all_rows": True}, {}, 1)
    assert worker.process is None


def test_oversized_record_is_bounded() -> None:
    command = (
        f"import sys,time; sys.stdout.write('x'*{MAX_RECORD_CHARS + 1}); "
        "sys.stdout.flush(); time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError, match="exceeds limit"):
        worker.measure({"timeout": 1}, {}, 2)
    assert worker.process is None


@pytest.mark.parametrize("phase", ["generation", "execution"])
def test_benchmark_deadline_reports_phase_and_log(monkeypatch, capsys, phase) -> None:
    import esolangs
    from scripts import benchmark

    def expired(*_args, **_kwargs):
        error = esolangs.ExecutionTimeoutError(
            f"benchmark {phase} deadline exceeded (1s)"
        )
        error.add_note("[log] notes/benchmarks/worker.log\nworker diagnostics")
        raise error

    monkeypatch.setattr(benchmark, "measure", expired)
    assert benchmark.main(["brainfuck", "01"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.splitlines() == [
        f"benchmark {phase} deadline exceeded (1s)",
        "[log] notes/benchmarks/worker.log",
    ]


def test_valid_multiline_protocol_runs_all_rows(monkeypatch, capsys) -> None:
    from scripts import benchmark

    record = benchmark.measure(
        "Brainfuck", "01", repeat=1, row=0, step_cap=100000, all_rows=True
    )
    assert [entry["row"] for entry in record["executions"]] == [0, 1]
    assert all(
        entry["actual_answer"] == entry["expected_answer"]
        for entry in record["executions"]
    )
    monkeypatch.setattr(benchmark, "measure", lambda *_, **__: record)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert benchmark.main(["Brainfuck", "01", "--all-rows"]) == 0
    assert json.loads(capsys.readouterr().out) == record
    record["executions"][0] |= {"matches": False, "actual_answer": "1"}
    record["peak_stack_items"] = 3
    assert benchmark.main(["Brainfuck", "01", "--all-rows"]) == 1
    assert json.loads(capsys.readouterr().out) == record
    with monkeypatch.context() as patch:
        patch.delattr(signal, "SIGALRM", raising=False)
        _check_store_sampling(patch)


def test_benchmark_runs_selected_rows_in_request_order(capsys) -> None:
    from scripts import benchmark

    assert (
        benchmark.main(
            [
                "brainfuck",
                "0110",
                "--repeat",
                "1",
                "--row",
                "3",
                "--row",
                "1",
                "--row",
                "0",
            ]
        )
        == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert [entry["row"] for entry in record["executions"]] == [3, 1, 0]
    assert all(entry["matches"] for entry in record["executions"])
    assert record["row"] == 0
    assert record["all_rows"] is False


def test_measure_prepares_once_and_records_first_sample(
    monkeypatch,
) -> None:
    import esolangs
    from scripts import benchmark

    encode_inputs = esolangs.encode_inputs
    prepare = esolangs.prepare
    encoded = []
    prepared = []

    def encode(language, bits, *, truth_table=None):
        assert truth_table is None
        encoded.append(bits)
        return encode_inputs(language, bits)

    def prepare_source(language, program):
        prepared.append(program)
        return prepare(language, program)

    ticks = iter((10, 40, 100, 110, 200, 220))
    with benchmark.evidence_session(), monkeypatch.context() as patch:
        patch.setattr(
            benchmark, "time", SimpleNamespace(perf_counter_ns=ticks.__next__)
        )
        patch.setattr(esolangs, "encode_inputs", encode)
        patch.setattr(esolangs, "prepare", prepare_source)
        record = benchmark._measure(
            "Brainfuck", "0110", repeat=3, row=3, step_cap=1000, all_rows=True
        )
    assert encoded == [[0, 0], [0, 1], [1, 0], [1, 1]]
    assert len(prepared) == 1
    assert all(entry["matches"] for entry in record["executions"])
    assert record["generation_ns_first"] == 30
    assert record["generation_ns_best"] == 10
    assert record["generation_ns_median"] == 20


def test_benchmark_rejects_changed_artifact_across_repeats(monkeypatch) -> None:
    import esolangs
    from scripts import benchmark

    first = esolangs.generate("brainfuck", "0000")
    second = esolangs.generate("brainfuck", "0110")
    programs = iter([first, second])
    monkeypatch.setattr(esolangs, "generate", lambda *_args, **_kw: next(programs))
    with pytest.raises(esolangs.ProgramError, match="generation repeat 2 differs"):
        benchmark._measure("brainfuck", "0110", repeat=2, row=1, step_cap=500)


@pytest.mark.medium
def test_benchmark_reads_large_truth_table_from_stdin() -> None:
    from scripts import benchmark

    table = "0" * (1 << 20)
    completed = subprocess.run(
        [
            sys.executable,
            benchmark.__file__,
            "brainfuck",
            "-",
            "--row",
            "0",
            "--repeat",
            "1",
        ],
        input=f"\ufeff \t{table}\r\n".encode(),
        capture_output=True,
        timeout=15,
        check=True,
    )
    record = json.loads(completed.stdout)
    assert record["truth_table"] == table
    assert record["row"] == 0
    assert record["matches"] is True


@pytest.mark.medium
def test_all_rows_can_exceed_one_worker_record() -> None:
    from scripts import benchmark

    table = "0" * 4096
    record = benchmark.measure(
        "brainfuck", table, repeat=1, row=2047, step_cap=500, all_rows=True
    )
    rows = record["executions"]
    assert record["truth_table"] == table
    assert [entry["row"] for entry in rows] == list(range(len(table)))
    assert all(entry["matches"] for entry in rows)
    assert record["row"] == 2047
    assert record["commands"] == rows[2047]["commands"]
    assert len(json.dumps({"result": record})) > MAX_RECORD_CHARS


@pytest.mark.parametrize(
    "name", one_where(lambda facts: "rotation" in facts.dialect_settings)
)
def test_benchmark_applies_cli_dialect_overrides_in_worker(name, capsys) -> None:
    import esolangs
    from scripts import benchmark

    language = esolangs.Language(name)
    program = language.generate("0110", settings=language.settings(rotation="forward"))
    assert (
        benchmark.main(
            [
                name,
                "0110",
                "--all-rows",
                "--repeat",
                "1",
                "-s",
                '{"rotation":"backward"}',
                "--set",
                "rotation=forward",
            ]
        )
        == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert record["settings"] == {"rotation": "forward"}
    assert (
        record["provenance"]["generated_record_sha256"]
        == benchmark.artifact_digests(program)[1]
    )
    assert "".join(row["actual_answer"] for row in record["executions"]) == "0110"


@pytest.mark.parametrize(
    "language",
    one_where(
        lambda facts: LANGUAGES[facts.name].runtime.capabilities.supports_scale,
        boolean_generator=True,
        source_kind="raster",
        width_effect="layout",
    ),
)
@pytest.mark.parametrize(
    ("options", "flags"),
    [
        ({"balance": True}, ["--balance"]),
        ({"width": 10, "scale": 3}, ["--width", "10", "--scale", "3"]),
    ],
)
def test_benchmark_cli_measures_requested_raster(
    language, options, flags, capsys
) -> None:
    import esolangs
    from scripts import benchmark

    program = esolangs.generate(language, "0110", **options)
    assert isinstance(program.source, esolangs.Raster)
    assert isinstance(program, esolangs.ProgramArtifact)
    assert (
        benchmark.main([language, "0110", "--repeat", "1", "--all-rows", *flags]) == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert record["generation_options"] == {
        "width": None,
        "balance": False,
        "scale": None,
        **options,
    }
    assert record["raster"] == {
        "height": len(program.source.rows),
        "width": len(program.source.rows[0]),
        "scale": program.scale,
    }
    assert record["provenance"]["generated_artifact_sha256"] == benchmark.artifact_hash(
        program.source
    )
    assert all(entry["matches"] for entry in record["executions"])


@pytest.mark.medium
@pytest.mark.parametrize("directory", [".", "notes/ci"])
def test_timing_journal_is_scratch_but_source_edits_change_identity(
    tmp_path, monkeypatch, directory
) -> None:
    import subprocess

    from scripts import benchmark
    from scripts.ci.shard import Recorder

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    (tmp_path / ".gitignore").write_text("notes/\n")
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    git("add", ".")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-qm",
        "fixture",
    )
    monkeypatch.setattr(benchmark, "__file__", str(tmp_path / "scripts/benchmark.py"))
    recorder = Recorder(tmp_path / directory / "test-durations.json")
    before = benchmark.source_identity()
    recorder.pytest_runtest_logreport(
        SimpleNamespace(
            when="teardown",
            nodeid="test_example.py::test_value",
            duration=0.01,
            failed=False,
        )
    )
    during = benchmark.source_identity()
    if directory == ".":
        assert before["untracked_sha256"] != during["untracked_sha256"]
    else:
        assert during == before
        recorder.pytest_sessionfinish(0)
        assert benchmark.source_identity() == before
    source.write_text("value = 2\n")
    assert (
        benchmark.source_identity()["tracked_diff_sha256"]
        != before["tracked_diff_sha256"]
    )


def test_pytest_cache_staging_dir_is_not_checkout_state(tmp_path, monkeypatch):
    """pytest's atomic cache-dir staging must not move the identity.

    _make_cachedir stages .pytest_cache as pytest-cache-files-* next to
    its target (the repo root) and the loser of a concurrent creation
    race deletes it; if git lists the staging files, source_identity
    crashes reading the vanished ones (weekly run 45266426182).
    """
    import subprocess
    from pathlib import Path

    from scripts import benchmark

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    repo_root = Path(__file__).resolve().parents[2]
    (tmp_path / ".gitignore").write_text((repo_root / ".gitignore").read_text())
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    git("add", ".")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-qm",
        "fixture",
    )
    monkeypatch.setattr(benchmark, "__file__", str(tmp_path / "scripts/benchmark.py"))
    before = benchmark.source_identity()
    # Only README.md: the window in _make_cachedir after the first file
    # is written but before its .gitignore (containing "*") lands — or
    # during the loser's rmtree after .gitignore is deleted first. Once
    # the .gitignore exists the dir self-ignores and git lists nothing,
    # so a fixture with all three files cannot reproduce the failure.
    staging = tmp_path / "pytest-cache-files-qm6epucl"
    staging.mkdir()
    (staging / "README.md").write_text("# pytest cache directory #\n")
    assert benchmark.source_identity() == before
    scratch = tmp_path / "scratch.txt"
    scratch.write_text("not staging\n")
    assert benchmark.source_identity() != before
    scratch.unlink()
    assert benchmark.source_identity() == before


def _check_store_sampling(monkeypatch) -> None:
    import esolangs
    from esolangs.registry import LANGUAGES
    from esolangs.vm import _capture_workspace, complete_vm, make_vm
    from scripts import benchmark

    cohort = [
        name
        for name, language in LANGUAGES.items()
        if language.backend is not None
        and esolangs.describe(name).dumps_on_the_post_halt_step
        and esolangs.describe(name).steppable_to_answer
        and esolangs.describe(name).answer_mode != "termination"
    ]
    assert len(cohort) == 7
    completion_gains = active_gains = 0
    for name in cohort:
        program = esolangs.generate(name, "01")
        source = (
            esolangs.instantiate(name, program, (0,))
            if isinstance(program, esolangs.TemplateArtifact)
            else program
        )
        vm = make_vm(
            name,
            source,
            stdin=""
            if isinstance(program, esolangs.TemplateArtifact)
            else esolangs.encode_inputs(name, [0], truth_table="01"),
        )
        assert not vm.halted
        written = benchmark.WrittenState(_capture_workspace(vm))
        commands = 0
        while not vm.halted:
            vm.step()
            commands += 1
            assert commands < 10000
            written.sample(_capture_workspace(vm))
            if commands == 1:
                active_peak = written.bits
        peak = written.bits
        output = complete_vm(vm, max_steps=0)
        written.sample(_capture_workspace(vm))
        assert esolangs.read_answer(name, output) == "0"
        completion_gains += written.bits == peak + 1
        active_gains += active_peak > 0
        for phase in ("complete", "refuse-complete", "refuse-active"):
            with monkeypatch.context() as patch:

                def finish(machine, max_steps, phase=phase):
                    result = complete_vm(machine, max_steps=max_steps)
                    if phase == "refuse-complete":
                        raise TimeoutError("completion already changed workspace")
                    return result

                def refusing_factory(*args, **kwargs):
                    actual = make_vm(*args, **kwargs)
                    real_step = actual.step

                    def refuse_after_step():
                        real_step()
                        raise TimeoutError("active step already changed workspace")

                    patch.setattr(actual, "step", refuse_after_step)
                    return actual

                patch.setattr(benchmark, "complete_vm", finish)
                if phase == "refuse-active":
                    patch.setattr(benchmark.debugger_api, "make_vm", refusing_factory)
                record = benchmark._execute(
                    # Like the supervised worker, rely on the outer deadline;
                    # an inner alarm is POSIX-only. The step cap remains live.
                    name,
                    program,
                    "01",
                    0,
                    10000,
                    None,
                    track_store=True,
                )
            assert record["peak_written_bits"] == (
                active_peak if phase == "refuse-active" else written.bits
            )
            assert record["commands"] == (
                None if phase == "refuse-active" else commands
            )
            assert record["execution_status"] == (
                "halted" if phase == "complete" else "step_cap"
            )
            assert record["actual_answer"] == ("0" if phase == "complete" else None)
    assert completion_gains > 0
    assert active_gains > 0
