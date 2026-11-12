"""Shared test oracles retain ordering, record boundaries and transient state."""

import pytest

import esolangs
from esolangs.runtime.io import ScriptedIO
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    assert_every_row,
    evaluate_generated,
    measure_run,
)
from tests.support.pick import languages
from tests.support.samples import _generated
from tests.support.vm_support import _row


@pytest.mark.medium
def test_every_row_checks_the_supplied_program_without_regenerating(monkeypatch):
    table = "00010111"
    program = esolangs.generate("Brainfuck", table)
    wrong = esolangs.generate("Brainfuck", "11101000")
    assert_every_row("Brainfuck", table)

    def reject_generation(*_args, **_kwargs):
        raise AssertionError("supplied programs must not be regenerated")

    monkeypatch.setattr(esolangs, "generate", reject_generation)
    assert_every_row("Brainfuck", table, program=program)
    with pytest.raises(AssertionError) as failure:
        assert_every_row("Brainfuck", table, program=wrong)
    assert failure.value.args == ((table, 0),)


@pytest.mark.parametrize("language", languages(boolean_generator=True))
@pytest.mark.usefixtures("retired_source_adapters")
def test_verification_helpers_retain_artifacts(language):
    program, _stdin = _row(language, "01", [1])
    assert isinstance(program, esolangs.ProgramArtifact)
    assert program.language == esolangs.describe(language)["name"]
    sample, _sample_stdin = _generated(language)
    assert isinstance(sample, (str, esolangs.Raster, esolangs.CompressedText))
    assert evaluate_generated(language, "01") == "01"


def test_read_first_io_checks_even_empty_output():
    io = ReadFirstIO("17", expected=1)
    with pytest.raises(AssertionError):
        io.print_str("")
    assert io.input_char() == ord("1")
    io.print_str("")
    io.print_num(0)
    assert io.getvalue() == "0"
    assert io.input_char() == ord("7")


def test_constant_oracle_retains_the_next_record_and_rejects_wrong_output():
    def run(code, io):
        io.input_char()
        io.print_str(code)

    io = ReadFirstIO("17", expected=1)
    assert_constant_output(run, "0", io, "0", 1)
    assert io.reads == 1
    assert io.input_char() == ord("7")
    with pytest.raises(AssertionError):
        assert_constant_output(run, "1", ScriptedIO("17"), "0", 1)
    with pytest.raises(AssertionError):
        assert_constant_output(run, "0", ScriptedIO("17"), "0", 2)


def test_measurement_keeps_transient_workspace_and_the_existing_step_cutoff():
    from esolangs.runtime._state import WorkspaceModel

    model = WorkspaceModel("transient-test-v1", ("value",))

    class Machine:
        at = 0
        states = (0, 1 << 100, 0)

        @property
        def halted(self):
            return self.at == len(self.states) - 1

        def snapshot(self):
            raise AssertionError("cycle snapshot reached accounting")

        def workspace_snapshot(self):
            return model.capture(value=self.states[self.at])

        def step(self):
            self.at += 1

    machine = Machine()
    steps, written = measure_run(machine)
    assert steps == 2
    assert machine.halted
    assert written.bits >= 101
    machine = Machine()
    steps, written = measure_run(machine, limit=0)
    assert steps == 1
    assert not machine.halted
    assert written.bits >= 101
