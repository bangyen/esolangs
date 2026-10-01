"""Tests for the public benchmark command."""

import esolangs
from scripts.benchmark import measure


def test_measure_reports_deterministic_costs() -> None:
    result = measure("brainfuck", "0110", repeat=1, row=1, step_cap=10_000)
    assert result["language"] == "brainfuck"
    assert result["inputs"] == 2
    assert result["source_units"] > 0
    assert result["commands"] is not None
    assert result["generation_ns_best"] >= 0


def test_measure_counts_commands_for_a_parameterized_language() -> None:
    """A parameterized language embeds its inputs and reads no stdin.

    ``encode_inputs`` raises for one rather than returning an empty string,
    so calling it before the parameterized branch made every parameterized
    language raise ``ArgumentError``.  Only brainfuck was ever measured, so
    the break went unseen until a sweep ran the whole registry.
    """
    name = next(
        lang
        for lang in esolangs.list_languages()
        if esolangs.describe(lang)["parameterized"]
    )
    result = measure(name, "0110", repeat=1, row=3, step_cap=10_000)
    assert result["source_units"] > 0


def test_measure_checks_every_row_of_the_same_artifact(monkeypatch) -> None:
    original = esolangs.generate
    calls = []

    def generate(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(esolangs, "generate", generate)
    result = measure(
        "brainfuck", "0110", repeat=1, row=1, step_cap=10_000, all_rows=True
    )
    assert len(calls) == 1
    assert [item["actual_answer"] for item in result["executions"]] == list("0110")
    assert all(item["matches"] for item in result["executions"])


def test_measure_reports_wrong_output(monkeypatch) -> None:
    monkeypatch.setattr(esolangs, "generate", lambda *_args: "+" * 48 + ".")
    result = measure("brainfuck", "0110", repeat=1, row=1, step_cap=10_000)
    assert result["expected_answer"] == "1"
    assert result["actual_answer"] == "0"
    assert result["matches"] is False


def test_step_cap_is_not_unsupported() -> None:
    result = measure("brainfuck", "0110", repeat=1, row=1, step_cap=1)
    assert result["stepping_status"] == "supported"
    assert result["execution_status"] == "step_cap"
    assert result["commands"] is None
    assert result["actual_answer"] is None
    assert result["matches"] is None


def test_raster_is_executed_without_stepping() -> None:
    result = measure("Piet", "0110", repeat=1, row=1, step_cap=1, all_rows=True)
    assert result["stepping_status"] == "unsupported"
    assert result["execution_status"] == "halted"
    assert result["commands"] is None
    assert all(item["matches"] for item in result["executions"])


def test_cycle_is_proven_without_waiting() -> None:
    result = measure("123", "01", repeat=1, row=1, step_cap=10_000, all_rows=True)
    assert [item["actual_answer"] for item in result["executions"]] == list("01")
    assert result["execution_status"] == "cycle"


def test_timeout_is_undecided(monkeypatch) -> None:
    def expired(*_args):
        raise esolangs.ExecutionTimeoutError("forced timeout")

    monkeypatch.setattr(esolangs, "_run", expired)
    result = measure("brainfuck", "0110", repeat=1, row=1, step_cap=10_000)
    assert result["execution_status"] == "timeout"
    assert result["actual_answer"] is None
    assert result["matches"] is None


def test_command_exits_unsuccessfully_for_undecided_row(capsys) -> None:
    from scripts.benchmark import main

    assert main(["brainfuck", "0110", "--step-cap", "1"]) == 1
    assert '"execution_status": "step_cap"' in capsys.readouterr().out


def test_post_halt_dump_is_checked_without_changing_command_count() -> None:
    result = measure("Back", "0110", repeat=1, row=1, step_cap=10_000)
    assert result["actual_answer"] == "1"
    assert result["matches"] is True
    assert result["commands"] > 0


def test_command_exits_unsuccessfully_for_wrong_answer(monkeypatch, capsys) -> None:
    from scripts.benchmark import main

    monkeypatch.setattr(esolangs, "generate", lambda *_args: "+" * 48 + ".")
    assert main(["brainfuck", "0110", "--row", "1"]) == 1
    assert '"matches": false' in capsys.readouterr().out


def test_command_positive_control(capsys) -> None:
    from scripts.benchmark import main

    assert main(["brainfuck", "0110", "--all-rows"]) == 0
    assert '"matches": true' in capsys.readouterr().out


def test_termination_step_cap_is_not_a_divergence_proof() -> None:
    result = measure("123", "01", repeat=1, row=1, step_cap=1)
    assert result["execution_status"] == "step_cap"
    assert result["actual_answer"] is None
    assert result["matches"] is None


def test_command_can_disable_signal_timeout(monkeypatch, capsys) -> None:
    from scripts import benchmark

    monkeypatch.delattr(benchmark.signal, "SIGALRM")
    assert benchmark.main(["brainfuck", "0110", "--all-rows", "--no-timeout"]) == 0
    assert '"timeout": null' in capsys.readouterr().out


def test_store_profile_and_worst_row() -> None:
    result = measure(
        "BFStack",
        "0110",
        repeat=1,
        row=0,
        step_cap=10_000,
        all_rows=True,
        track_store=True,
        timeout=None,
    )
    assert all(item["matches"] for item in result["executions"])
    assert result["worst_row_commands"] == max(
        item["commands"] for item in result["executions"]
    )
    assert all(item["peak_memory_cells"] == 0 for item in result["executions"])
    assert max(item["peak_stack_items"] for item in result["executions"]) == 3


def test_partial_rows_do_not_claim_a_worst_row() -> None:
    result = measure(
        "Sophie",
        "0110",
        repeat=1,
        row=0,
        step_cap=10_000,
        track_store=True,
        timeout=None,
    )
    assert result["worst_row_commands"] is None
    assert result["peak_memory_cells"] == 1
    assert result["peak_stack_items"] == 0


def test_capped_profile_does_not_claim_a_worst_row() -> None:
    result = measure(
        "BFStack",
        "0110",
        repeat=1,
        row=0,
        step_cap=1,
        all_rows=True,
        track_store=True,
        timeout=None,
    )
    assert result["worst_row_commands"] is None
    assert all(item["execution_status"] == "step_cap" for item in result["executions"])
