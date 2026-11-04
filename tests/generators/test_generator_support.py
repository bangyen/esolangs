"""Shared test oracles retain ordering, record boundaries and transient state."""

import pytest

from esolangs.runtime.io import ScriptedIO
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_constant_output, measure_run


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
    class Machine:
        at = 0
        states = (0, 1 << 100, 0)

        @property
        def halted(self):
            return self.at == len(self.states) - 1

        def snapshot(self):
            return (self.states[self.at],)

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
