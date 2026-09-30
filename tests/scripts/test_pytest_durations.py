"""Recorded timing weights contain all phases, with one controller writer."""

import json
from types import SimpleNamespace

from scripts.pytest_durations import Recorder, pytest_configure


def test_report_phases_are_added(tmp_path):
    path = tmp_path / "nested" / "durations.json"
    recorder = Recorder(path)
    for seconds in (0.1, 0.5, 0.2):
        recorder.pytest_runtest_logreport(
            SimpleNamespace(nodeid="test_a", duration=seconds)
        )
    recorder.pytest_runtest_logreport(SimpleNamespace(nodeid="test_b", duration=0))
    recorder.pytest_sessionfinish()
    assert json.loads(path.read_text()) == {"test_a": 0.8}


def test_workers_do_not_register_writers(tmp_path):
    registered = []
    config = SimpleNamespace(
        getoption=lambda _name: tmp_path / "timings.json",
        pluginmanager=SimpleNamespace(register=registered.append),
        workerinput={},
    )
    pytest_configure(config)
    assert registered == []
    del config.workerinput
    pytest_configure(config)
    assert len(registered) == 1
