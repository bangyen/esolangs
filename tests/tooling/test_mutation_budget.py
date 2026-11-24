"""Mutation baselines and probes cannot overrun the remaining sweep budget."""

import json
from types import SimpleNamespace

import pytest

from scripts import mutants


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf")])
def test_invalid_budget_is_rejected_before_opening_output(tmp_path, capsys, budget):
    out = tmp_path / "out.jsonl"
    with pytest.raises(ValueError, match="--budget must be positive and finite"):
        mutants.sweep(["test"], out, 1, budget)
    with pytest.raises(SystemExit) as caught:
        mutants.main(["test", "--out", str(out), "--budget", str(budget)])
    assert caught.value.code == 2
    assert "--budget must be positive and finite" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("cutoff", ["probe", "global", "streak"])
def test_sweep_budget_clips_probes_and_restores_source(
    tmp_path, monkeypatch, capsys, cutoff
):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    mutant = {"file": "source.py", "line": 1, "col": 8, "old": "1", "new": "2"}
    clock = iter(
        [0, 0, 0, 1, 2, 11] if cutoff == "global" else [0, 0, 0, 1, 2, 2, 2, 2]
    )
    monkeypatch.setattr(mutants, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(mutants, "ROOT", tmp_path)
    monkeypatch.setattr(mutants, "_pytest", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(mutants, "_clear_bytecode", lambda: None)
    count = {"probe": 1, "global": 2, "streak": 4}[cutoff]
    monkeypatch.setattr(mutants, "candidates", lambda *_args: [mutant] * count)
    limits = []

    def run(_command, timeout):
        limits.append(timeout)
        if len(limits) == 1:
            return "survived", "baseline"
        assert source.read_text() == "value = 2\n"
        return ("survived", "") if cutoff == "global" else ("timeout", "")

    monkeypatch.setattr(mutants, "_run", run)
    out = tmp_path / "out.jsonl"
    assert mutants.sweep(["test"], out, count, 10) == 124
    assert "mutation sweep incomplete" in capsys.readouterr().err
    completed = 3 if cutoff == "streak" else 1
    assert limits == [10, *([8] * completed)]
    status = "survived" if cutoff == "global" else "timeout"
    assert [json.loads(row)["status"] for row in out.read_text().splitlines()] == [
        status
    ] * completed
    assert source.read_text() == "value = 1\n"
    assert (tmp_path / "out-test-baseline.log").read_text() == "baseline"
