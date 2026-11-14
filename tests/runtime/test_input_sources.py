"""Execution snapshots caller-owned stdin before starting the interpreter."""

import io
import os
import select
from threading import Event, Thread

import pytest

import esolangs
from tests.support.reference import REFERENCE


@pytest.fixture
def nonblocking_pipe():
    if not hasattr(select, "poll"):
        pytest.skip("raw nonblocking pipes require poll")
    read_fd, write_fd = os.pipe()
    with io.FileIO(read_fd, "rb") as raw, io.FileIO(write_fd, "wb") as writer:
        os.set_blocking(read_fd, False)
        yield raw, writer


@pytest.mark.parametrize("budget", [{}, {"max_steps": 2}, {"total_timeout": 5}])
@pytest.mark.parametrize("buffered", [False, True])
def test_nonblocking_binary_stdin_waits_for_complete_utf8(
    nonblocking_pipe, budget, buffered
):
    raw, writer = nonblocking_pipe
    would_block = Event()
    resumed = Event()

    class ObservedFile(io.FileIO):
        def read(self, *args):
            chunk = super().read(*args)
            if chunk is None:
                would_block.set()
            return chunk

        def readinto(self, *args):
            count = super().readinto(*args)
            if count is None:
                would_block.set()
            return count

    def supply_rest() -> None:
        if would_block.wait(3):
            writer.write(b"\xa9")
            resumed.set()
        writer.close()

    writer.write(b"\xc3")
    feeder = Thread(target=supply_rest)
    feeder.start()
    try:
        observed = ObservedFile(raw.fileno(), "rb", closefd=False)
        with io.BufferedReader(observed) if buffered else observed as source:
            if buffered:
                assert source.peek(1) == b"\xc3"
            result = esolangs.run(
                REFERENCE, ",.", stdin=source, limits=esolangs.ExecutionLimits(**budget)
            )
            assert not source.closed
            assert not os.get_blocking(source.fileno())
    finally:
        would_block.set()
        feeder.join(4)
    assert resumed.is_set()
    assert result.output == "é"
    assert result.input_position == result.input_reads == 1


def test_nonblocking_text_stdin_does_not_execute_a_partial_input(nonblocking_pipe):
    raw, writer = nonblocking_pipe
    writer.write(b"A")
    with io.TextIOWrapper(io.BufferedReader(raw)) as source:
        outcome = esolangs.execute(REFERENCE, ",.", stdin=source)
        assert isinstance(outcome.error, esolangs.ArgumentError)
        assert "cannot detect EOF" in str(outcome.error)
        assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
        assert not source.closed
        writer.close()
        os.set_blocking(raw.fileno(), True)
        assert esolangs.run(REFERENCE, ",.", stdin=source).output == "A"


@pytest.mark.parametrize("budget", [{}, {"max_steps": 2}, {"total_timeout": 5}])
def test_stdin_read_access_and_managed_errors_preserve_the_boundary(budget):
    class NoReader:
        @property
        def read(self):
            raise OSError("descriptor unavailable")

    class WouldBlock:
        def read(self):
            return None

    failure = esolangs.ExecutionTimeoutError("stdin provider stopped")
    failure.bound = "preparation_timeout"

    class Managed:
        def read(self):
            raise failure

    api = esolangs.Language(REFERENCE)
    limits = esolangs.ExecutionLimits(**budget)
    program = io.StringIO(",.")
    result = api.execute(program, stdin=NoReader(), limits=limits)
    assert isinstance(result.error, esolangs.ArgumentError)
    assert "descriptor unavailable" in str(result.error)
    assert program.tell() == 0
    result = api.execute(program, stdin=WouldBlock(), limits=limits)
    assert isinstance(result.error, esolangs.ArgumentError)
    assert "stream would block" in str(result.error)
    assert result.error.observation is None
    result = api.execute(",.", stdin=Managed(), limits=limits)
    assert result.error is failure
    assert result.bound == "preparation_timeout"


@pytest.mark.parametrize(
    "bound", ["execution_timeout", "preparation_timeout", "total_timeout"]
)
def test_nonblocking_stdin_prefix_does_not_complete_acquisition(
    nonblocking_pipe, bound
):
    raw, writer = nonblocking_pipe
    writer.write(b"A")
    outcome = esolangs.execute(
        REFERENCE, ",.", stdin=raw, limits=esolangs.ExecutionLimits(**{bound: 0.2})
    )
    assert isinstance(outcome.error, esolangs.ExecutionTimeoutError)
    assert outcome.bound == bound
    assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
    writer.write(b"B")
    writer.close()
    assert esolangs.run(REFERENCE, ",.", stdin=raw).output == "B"


@pytest.mark.parametrize("block", ["program", "stdin"])
def test_expired_acquisition_does_not_start_another_read(monkeypatch, block):
    from esolangs.runtime import _isolated

    started, release = Event(), Event()
    threads, input_reads = [], []

    def capture_thread(*args, **kwargs):
        thread = Thread(*args, **kwargs)
        threads.append(thread)
        return thread

    class Program(io.StringIO):
        def read(self, *args):
            if block == "program":
                wait()
            return super().read(*args)

    def wait():
        started.set()
        release.wait(3)

    class Input:
        @property
        def read(self):
            if block == "stdin":
                wait()
            return self._read

        def _read(self):
            input_reads.append(True)
            return "A"

    monkeypatch.setattr(_isolated, "Thread", capture_thread)
    program = Program(",.")
    try:
        outcome = esolangs.execute(
            REFERENCE,
            program,
            stdin=Input(),
            limits=esolangs.ExecutionLimits(total_timeout=0.2),
        )
        assert started.is_set()
        assert outcome.bound == "total_timeout"
    finally:
        release.set()
        for thread in threads:
            thread.join(4)
    assert all(not thread.is_alive() for thread in threads)
    assert not input_reads
    assert program.tell() == (2 if block == "program" else 0)
