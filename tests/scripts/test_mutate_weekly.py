"""Mutation rotation and process budgets retain honest evidence."""

import datetime
import json
import signal
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import mutate_weekly


def test_rotation_visits_every_pair_and_repeats_after_four_weeks() -> None:
    date = datetime.date(2026, 12, 21)
    pairs = {
        mutate_weekly.targets_for(date + datetime.timedelta(weeks=i)) for i in range(4)
    }
    assert pairs == set(mutate_weekly.TARGETS)
    assert mutate_weekly.targets_for(date) == mutate_weekly.targets_for(
        date + datetime.timedelta(weeks=4)
    )


@pytest.mark.parametrize("kind", ["interpreter", "generator"])
@pytest.mark.parametrize("outcome", ["complete", "failed", "timeout", "missing-score"])
def test_run_records_outcome_and_kills_the_timed_out_process_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    kind: str,
) -> None:
    output = tmp_path / "evidence"
    output.mkdir()
    score = output / "score.json"
    score.write_text("stale")
    process = Mock(pid=12345)
    process.wait.side_effect = (
        [subprocess.TimeoutExpired("mutmut", 240), -9]
        if outcome == "timeout"
        else [1 if outcome == "failed" else 0]
    )

    def launch(command: list[str], **kwargs: object) -> Mock:
        assert not score.exists()
        assert command[command.index("--report") + 1] == str(score)
        assert ("--focused" in command) == (kind == "generator")
        assert kwargs["start_new_session"] is True
        assert command[command.index("--jobs") + 1] == "2"
        if outcome == "complete":
            score.write_text(json.dumps({"survivors": ["one"]}))
        return process

    monkeypatch.setattr(mutate_weekly.subprocess, "Popen", launch)
    kill = Mock()
    monkeypatch.setattr(mutate_weekly.os, "killpg", kill)
    assert mutate_weekly.run_target(kind, "Qoibl", output) == (outcome == "complete")
    status = json.loads((output / "status.json").read_text())
    assert status["status"] == ("failed" if outcome == "missing-score" else outcome)
    if outcome == "timeout":
        kill.assert_called_once_with(12345, signal.SIGKILL)
        assert process.wait.call_count == 2
    else:
        kill.assert_not_called()
    assert (output / "run.log").exists()


def test_main_runs_both_targets_even_when_the_first_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(side_effect=[False, True])
    monkeypatch.setattr(mutate_weekly, "run_target", run)
    monkeypatch.setattr(
        mutate_weekly.sys, "argv", ["mutate_weekly", "--output", str(tmp_path)]
    )
    assert mutate_weekly.main() == 1
    assert [call.args[0] for call in run.call_args_list] == ["interpreter", "generator"]
