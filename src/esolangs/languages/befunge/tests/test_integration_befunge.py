"""Befunge through the shared API, CLI and machinery."""

import io
import os
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import esolangs
from esolangs import run
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES, _table
from tests.proofs._ledger import load
from tests.support.cli_support import _failure, call_both, run_cli
from tests.support.input_convention import assert_reads_tokens_on_one_line

_RANDOM_BRANCH = "?.@\n. @\n@ @"


def test_generator_and_runtime_hints_reach_cli(capsys, tmp_path, monkeypatch) -> None:
    _, err = _failure(["generate", "Befunge", "0010" * (1 << 12)], capsys)
    assert "fixed 80x25 grid" in err
    assert err.count("hint:") == 1

    name = "--Scoped Befunge"
    identifier = "scoped_befunge"
    declaration = replace(LANGUAGES["Befunge"], name=name, id=identifier)
    catalog = esolangs.Catalog([declaration])
    api = catalog.bind(name)
    monkeypatch.setattr(_table, "CATALOG", catalog)
    path = tmp_path / "source.bf"
    path.write_text("Ā", encoding="utf-8")
    result = api.execute(path)
    assert result.status == "rejected"
    assert isinstance(result.error, esolangs.ProgramError)
    hint = result.error.__notes__[0]
    copied = shlex.split(hint.split(" with ", 1)[1])
    assert copied == ["esolangs", "describe", "--spec", "--", name]
    command = ["run", identifier, str(path)]
    assert _failure(command, capsys) == ("", f"{result.error}\n{hint}\n")
    assert call_both(copied[1:], capsys) == (api.describe().spec + "\n", "")
    path.write_text('"A",@')
    assert call_both(command, capsys) == ("A", "")

    path.write_text("Ā", encoding="utf-8")
    name = "É Befunge"

    class AsciiDiagnostic(io.StringIO):
        @property
        def encoding(self):
            return "ascii"

        def write(self, value):
            value.encode("ascii")
            return super().write(value)

    for identifier in ("scoped_befunge", "é_befunge"):
        declaration = replace(
            LANGUAGES["Befunge"], name=name, id=identifier, aliases=()
        )
        catalog = esolangs.Catalog([declaration])
        api = catalog.bind(name)
        outcome = api.execute(path)
        assert outcome.error is not None
        assert outcome.error.__notes__ == [
            "hint: check the language syntax with esolangs describe --spec 'É Befunge'"
        ]
        diagnostic = AsciiDiagnostic()
        with monkeypatch.context() as patch:
            patch.setattr(_table, "CATALOG", catalog)
            patch.setattr(sys, "stderr", diagnostic)
            assert _failure(["run", identifier, str(path)], capsys) == ("", "")
            if identifier.isascii():
                hint = diagnostic.getvalue().splitlines()[-1]
                copied = shlex.split(hint.split(" with ", 1)[1])
                assert copied == ["esolangs", "describe", "--spec", identifier]
                assert call_both(copied[1:], capsys) == (api.describe().spec + "\n", "")
            else:
                assert diagnostic.getvalue().splitlines()[-1] == (
                    "hint: check the operands and input against the language's syntax"
                )


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

    source = _RANDOM_BRANCH
    observed = {}
    for seed in range(8):
        native = run("Befunge", source, seed=seed).output
        machine = make_vm("Befunge", source, seed=seed)
        debugger = make_debugger("Befunge", source, seed=seed)
        complete_vm(machine)
        assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=100)) == "halted"
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
            "--execution-timeout",
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


@pytest.mark.medium
def test_cli_large_decimal_seed_matches_python(tmp_path: Path) -> None:
    path = tmp_path / "draw.bf"
    path.write_text(_RANDOM_BRANCH, encoding="utf-8")
    limits = esolangs.ExecutionLimits(max_steps=100)
    magnitude = 10**4401 + 1
    above_cap = "0" * 4400 + "1"
    cases = [
        ("0", 0),
        ("1", 1),
        (f"1{above_cap}", magnitude),
        (f" \u00a0-1_{above_cap}\t", -magnitude),
    ]
    outputs = []
    for operand, seed in cases:
        expected = run("Befunge", _RANDOM_BRANCH, seed=seed, limits=limits).output
        shell = subprocess.run(
            [
                sys.executable,
                "-m",
                "esolangs",
                "run",
                "--isolated",
                "--max-steps=100",
                f"--seed={operand}",
                "Befunge",
                str(path),
            ],
            env={**os.environ, "PYTHONINTMAXSTRDIGITS": "4300"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert (shell.returncode, shell.stdout, shell.stderr) == (
            0,
            expected.encode(),
            b"",
        )
        outputs.append(expected)
    assert outputs[0] != outputs[1]

    original = LANGUAGES["Befunge"]

    class Counterfeit:
        @property
        def __class__(self) -> type:
            raise AssertionError("use the seed's backing type")

    for invalid in (None, 1.5, False, "7", Counterfeit()):
        with pytest.raises(
            esolangs.ArgumentError, match="reproducible_seed must be an integer"
        ):
            replace(original.runtime, reproducible_seed=invalid)

    class Seed(int):
        def __int__(self) -> int:
            raise AssertionError("use the seed's backing integer")

    previous_limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)
    try:
        for (_, seed), expected in zip(cases, outputs, strict=True):
            runtime = replace(original.runtime, reproducible_seed=Seed(seed))
            assert type(runtime.reproducible_seed) is int
            assert runtime.reproducible_seed == seed
            declaration = replace(original, runtime=runtime)
            shown = repr(seed) if seed in (0, 1) else hex(seed)
            assert f"reproducible_seed={shown}," in repr(runtime)
            assert repr(runtime) in repr(declaration)

            scoped = esolangs.Catalog([declaration]).bind(declaration.name)
            for _ in range(2):
                debugger = scoped.make_debugger(_RANDOM_BRANCH)
                assert debugger.run(limits=limits) == "halted"
                assert debugger.output == expected
    finally:
        sys.set_int_max_str_digits(previous_limit)
