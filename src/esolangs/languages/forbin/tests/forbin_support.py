"""The Forbin suites shared helper: run a program and return what it printed."""

import contextlib

from esolangs import ExecutionLimits
from esolangs.generation.helpers import _validate_truth_table, input_weights
from esolangs.languages.forbin.generator import _build_projected
from esolangs.languages.forbin.interpreter import run
from esolangs.runtime.io import ScriptedIO


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


def _build(truth_table: str, width: int | None, bits: int) -> str:
    """Build the program whose shift register addresses ``bits`` inputs."""
    weights, table = input_weights(truth_table, _validate_truth_table(truth_table))
    return _build_projected(weights, table, width, bits)


def check_constructor_error_observations() -> None:
    """Retain real constructor IO without inventing a failed VM's state."""
    from types import SimpleNamespace
    from unittest.mock import patch

    import pytest

    import esolangs
    from esolangs import vm as vm_api
    from esolangs.debugger import make_debugger
    from esolangs.exceptions import InputExhaustedError, ProgramError
    from esolangs.languages.forbin.interpreter import _execute
    from esolangs.results import Completion, CompletionReport, ExecutionResult
    from esolangs.vm import _capture_observation, complete_vm, make_vm

    halted = CompletionReport(Completion.HALTED)
    cases = (
        (
            "constructor-output-eof",
            "pr { out 0,1,0,0,0,0,0,1; return 0; }\nx = (pr 0);\ny = (in 0);\nmain { }",
            "A",
            True,
        ),
        (
            "constructor-output-positive",
            "pr { out 0,1,0,0,0,0,0,1; return 0; }\nx = (pr 0);\nmain { }",
            "A",
            False,
        ),
        ("constructor-eof-only", "x = (in 0);\nmain { }", "", True),
        (
            "step-output-eof",
            "pr { out 0,1,0,0,0,0,0,1; return (in 0); }\nmain { x = (pr 0); }",
            "A",
            True,
        ),
    )
    routes = (
        "native",
        "ordinary",
        "vm",
        "debug",
        "bounded",
        "isolated-ordinary",
        "isolated-bounded",
    )
    ports = []

    def execute(route, source):
        artifact = esolangs.ProgramArtifact(source, "Forbin")
        if route == "native":
            port = ScriptedIO("")
            ports.append(port)
            report = _execute(source, port)
            return ExecutionResult(
                port.getvalue(), port.position(), port.reads, port.past_end, report
            )
        if route == "vm":
            vm = make_vm("Forbin", artifact, stdin="")
            complete_vm(vm, max_steps=64)
            return _capture_observation(vm, halted)
        if route == "debug":
            debugger = make_debugger("Forbin", artifact, stdin="")
            assert debugger.run(limits=ExecutionLimits(max_steps=64)) == "halted"
            return debugger.observation
        isolated = route.startswith("isolated-")
        return esolangs.run(
            "Forbin",
            artifact,
            stdin="",
            limits=ExecutionLimits(
                max_steps=64 if route in ("bounded", "isolated-bounded") else None,
                execution_timeout=2.0 if isolated else None,
            ),
            isolated=isolated,
        )

    for name, source, output, fails in cases:
        for route in routes:
            counted = route in ("debug", "bounded", "isolated-bounded")
            if fails:
                with pytest.raises(InputExhaustedError) as caught:
                    execute(route, source)
                assert type(caught.value) is InputExhaustedError
                assert (
                    caught.value.reads,
                    caught.value.supplied,
                    caught.value.unit,
                ) == (0, 0, "character")
                if route == "native":
                    assert caught.value.partial_output == ""
                    assert caught.value.observation is None
                    assert (
                        ports[-1].getvalue(),
                        ports[-1].position(),
                        ports[-1].reads,
                        ports[-1].past_end,
                    ) == (output, 0, 0, 1)
                else:
                    steps = 0 if name == "step-output-eof" and counted else None
                    assert caught.value.partial_output == output
                    assert caught.value.observation == ExecutionResult(
                        output, 0, 0, 1, None, steps
                    )
            else:
                assert execute(route, source) == ExecutionResult(
                    "A", 0, 0, 0, halted, 1 if counted else None
                )
    # Parser refusals still have no machine or observed IO, unlike initializer EOF.
    for source in ("", "main {"):
        artifact = esolangs.ProgramArtifact(source, "Forbin")
        for create in (make_vm, make_debugger):
            with pytest.raises(ProgramError) as caught:
                create("Forbin", artifact, stdin="")
            assert type(caught.value) is ProgramError
            assert caught.value.partial_output == ""
            assert caught.value.observation is None
        with pytest.raises(ProgramError) as caught:
            esolangs.run("Forbin", artifact, limits=ExecutionLimits(max_steps=64))
        assert caught.value.partial_output == ""
        assert caught.value.observation is None
    # A successful IO-free construction still has no completion observation.
    artifact = esolangs.ProgramArtifact("main { }", "Forbin")
    vm = make_vm("Forbin", artifact, stdin="λ")
    assert not vm.halted
    assert _capture_observation(vm) == ExecutionResult("", 0, 0, 0)
    assert complete_vm(vm, max_steps=1) == ""
    assert _capture_observation(vm, halted) == ExecutionResult("", 0, 0, 0, halted)

    def refuse(_source, _options):
        raise ProgramError("preparation refusal")

    with patch.object(
        vm_api,
        "interpreter_module",
        return_value=SimpleNamespace(prepare_machine=refuse),
    ):
        with pytest.raises(ProgramError) as caught:
            make_vm("Forbin", artifact, stdin="λ")
        assert str(caught.value) == "preparation refusal"
        assert caught.value.partial_output == ""
        assert caught.value.observation is None
    # A factory's existing truthful observation must not be replaced either.
    declared = []

    def prepare_reported(_source, _options):
        def build(port):
            port.print_str("A")
            error = ProgramError("reported refusal")
            error.partial_output = port.getvalue()
            error.observation = ExecutionResult(
                port.getvalue(), port.position(), port.reads, port.past_end
            )
            declared.append(error.observation)
            raise error

        return build

    with patch.object(
        vm_api,
        "interpreter_module",
        return_value=SimpleNamespace(prepare_machine=prepare_reported),
    ):
        with pytest.raises(ProgramError) as caught:
            make_vm("Forbin", artifact)
        assert caught.value.partial_output == "A"
        assert caught.value.observation is declared[0]
