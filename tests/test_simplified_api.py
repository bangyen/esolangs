"""One execution entry point and consistent source arguments."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs import debugger


@pytest.mark.parametrize(
    "name",
    ["check_runnable", "run_bounded", "run_isolated", "spec", *debugger.__all__],
)
def test_removed_root_exports(name):
    assert name not in esolangs.__all__
    assert not hasattr(esolangs, name)


def test_debugger_exports_are_available():
    for name in debugger.__all__:
        assert hasattr(debugger, name)
    assert debugger.make_vm("brainfuck", "+.").ip == 0
    assert debugger.make_debugger("brainfuck", "+.").run() == "halted"


@pytest.mark.parametrize("language", ["brainfuck", "Minifuck", "Piet"])
def test_evaluate_loads_source_once_from_path(language, tmp_path):
    program = esolangs.generate(language, "0110")
    path = tmp_path / "program"
    if isinstance(program, esolangs.Raster):
        path.write_bytes(program.to_png())
    else:
        path.write_text(program + "\n", encoding="utf-8")
    assert esolangs.evaluate(language, path, inputs=2) == "0110"


def test_isolated_execution_loads_a_path_in_worker_thread(tmp_path):
    path = tmp_path / "program.bf"
    path.write_text("++.")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(esolangs.run, "brainfuck", path, isolated=True)
        assert result.result(timeout=5) == "\x02"


@pytest.mark.parametrize(
    "options",
    [
        {"isolated": True, "max_steps": 2},
        {"isolated": True, "timeout": None},
        {"max_steps": 2, "seed": 1},
    ],
)
def test_unsupported_execution_options_are_refused(options):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("brainfuck", "+.", **options)


def test_isolated_seed_is_forwarded(monkeypatch):
    seen = []

    def execute(language, program, stdin, timeout, *, seed):
        seen.append((language, program, stdin, timeout, seed))
        return "result"

    monkeypatch.setattr(esolangs, "_run_isolated", execute)
    assert esolangs.run("brainfuck", "+.", isolated=True, seed=7) == "result"
    assert seen == [("brainfuck", "+.", "", 30.0, 7)]
