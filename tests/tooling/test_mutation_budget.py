"""Mutation baselines and probes cannot overrun the remaining sweep budget."""

from scripts import mutants


def test_sweep_budget_clips_probes_and_restores_source(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mutants,
        "_run",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected run")),
    )
    assert mutants.sweep(["test"], tmp_path / "out.jsonl", 1, 0) == 0

    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    mutant = {"file": "source.py", "line": 1, "col": 8, "old": "1", "new": "2"}
    clock = iter([0, 0, 0, 1, 2])
    monkeypatch.setattr(mutants.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(mutants, "ROOT", tmp_path)
    monkeypatch.setattr(mutants, "_pytest", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(mutants, "_clear_bytecode", lambda: None)
    monkeypatch.setattr(mutants, "candidates", lambda *_args: [mutant])
    limits = []

    def run(_command, timeout):
        limits.append(timeout)
        return ("survived", "baseline") if len(limits) == 1 else ("timeout", "")

    monkeypatch.setattr(mutants, "_run", run)
    assert mutants.sweep(["test"], tmp_path / "out.jsonl", 1, 10) == 0
    assert limits == [10, 8]
    assert source.read_text() == "value = 1\n"
    assert (tmp_path / "out-test-baseline.log").read_text() == "baseline"
