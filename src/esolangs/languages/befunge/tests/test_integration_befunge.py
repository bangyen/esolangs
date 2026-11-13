"""Befunge through the shared API, CLI and machinery."""

import io
from typing import Any

import pytest

import esolangs
from esolangs import run
from esolangs.debugger import make_debugger
from tests.proofs._ledger import load
from tests.support.cli_support import _failure, run_cli
from tests.support.input_convention import assert_reads_tokens_on_one_line


def test_generator_cap_hint_reaches_cli(capsys) -> None:
    _, err = _failure(["generate", "Befunge", "0010" * (1 << 12)], capsys)
    assert "fixed 80x25 grid" in err
    assert err.count("hint:") == 1


def test_generator_cap_hint() -> None:
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        esolangs.generate("Befunge", "0010" * (1 << 12))
    assert "fixed 80x25 grid" in caught.value.__notes__[0]


# Isolated cases spawn a worker: the medium band, like test_run_isolated.
@pytest.mark.parametrize(
    "mode", ["normal", "steps", pytest.param("isolated", marks=pytest.mark.medium)]
)
def test_invalid_numeric_input_is_not_mislabeled_as_a_program_error(mode: str) -> None:
    bounds: dict[str, Any] = {}
    if mode == "steps":
        bounds["limits"] = esolangs.ExecutionLimits(max_steps=100)
    elif mode == "isolated":
        bounds["isolated"] = True
    assert run("Befunge", "&.@", stdin=b"-12345", **bounds).output == "-12345 "
    with pytest.raises(
        esolangs.ArgumentError, match="input must be an integer"
    ) as error:
        run("Befunge", '"A",&.@', stdin=io.StringIO("invalid"), **bounds)
    assert error.value.partial_output == "A"


def test_befunge_grid_refusal_is_catchable() -> None:
    with pytest.raises(esolangs.GeneratorCapError, match="80x25"):
        esolangs.generate("Befunge", "0010" * (1 << 12))


@pytest.mark.parametrize("wrapped", ["vm", "machine", "debugger"])
def test_random_snapshot_cannot_prove_a_cycle(wrapped) -> None:
    from esolangs.vm import make_vm, run_until_halt, run_until_halt_or_cycle

    source = "v \n?@"
    vm = make_vm("Befunge", source)
    machine = (
        vm
        if wrapped == "vm"
        else (vm._machine if wrapped == "machine" else make_debugger("Befunge", source))
    )
    with pytest.raises(TypeError, match="random machines"):
        run_until_halt_or_cycle(machine, limit=1000)
    run_until_halt(vm, limit=1000)
    assert vm.halted
    assert (
        run(
            "Befunge",
            source,
            seed=0,
            limits=esolangs.ExecutionLimits(execution_timeout=1),
        ).output
        == ""
    )
    assert run_until_halt_or_cycle(vm, limit=1000) is True


def test_it_reads_numeric_tokens_on_the_same_line() -> None:
    assert_reads_tokens_on_one_line("Befunge")


def test_befunge_refusal_is_an_explicit_totality_exception() -> None:
    """The fixed-torus refusal must not disappear from the totality audit."""
    with pytest.raises(esolangs.GeneratorCapError, match="at most thirteen inputs"):
        esolangs.generate("Befunge", "01" * 8192)
    assert "exception" in load().by_name()["Befunge"].labels


@pytest.mark.medium
def test_seeded_steps_debuggers_and_combined_worker_budgets_agree(tmp_path):
    from esolangs.vm import complete_vm, make_vm

    source = "?.@\n. @\n@ @"
    observed = {}
    for seed in range(8):
        native = run("Befunge", source, seed=seed).output
        machine = make_vm("Befunge", source, seed=seed)
        debugger = make_debugger("Befunge", source, seed=seed)
        complete_vm(machine)
        assert debugger.run(max_steps=100) == "halted"
        assert machine.output == debugger.output == native
        assert machine.snapshot() == debugger.snapshot()
        assert (
            run(
                "Befunge",
                source,
                seed=seed,
                limits=esolangs.ExecutionLimits(max_steps=100),
            ).output
            == native
        )
        observed.setdefault(native, seed)
    assert len(observed) > 1  # Positive control: the program actually drew.

    path = tmp_path / "draw.bf"
    path.write_text(source)
    for output, seed in observed.items():
        assert (
            run(
                "Befunge",
                source,
                seed=seed,
                isolated=True,
                limits=esolangs.ExecutionLimits(
                    execution_timeout=5, max_steps=100, max_output=len(output)
                ),
            ).output
            == output
        )
        shell = run_cli(
            "run",
            "--isolated",
            "--timeout",
            "5",
            "--seed",
            str(seed),
            "--max-steps",
            "100",
            "--max-output",
            str(len(output)),
            "Befunge",
            str(path),
        )
        assert shell.returncode == 0, shell.stderr
        assert shell.stdout == output
