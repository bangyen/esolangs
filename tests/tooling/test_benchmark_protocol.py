"""Reject malformed worker records without losing legitimate row deadlines."""

import json
import signal
import sys

import pytest

from scripts.benchmark import MAX_RECORD_CHARS, Worker


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


@pytest.mark.medium
@pytest.mark.parametrize("directory", [".", "notes/ci"])
def test_timing_journal_is_scratch_but_source_edits_change_identity(
    tmp_path, monkeypatch, directory
) -> None:
    import subprocess
    from types import SimpleNamespace

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
    assert len(cohort) == 9
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
