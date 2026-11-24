"""Execution snapshots caller-owned stdin before starting the interpreter."""

import io
import os
import select
from contextvars import ContextVar
from dataclasses import replace
from threading import Event, Thread
from time import monotonic

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import complete_vm
from tests.support.reference import REFERENCE


@pytest.mark.parametrize("shape", ["char_stream", "line_per_bit"])
@pytest.mark.parametrize("route", ["native", "stepped", "prepared", "isolated"])
def test_framed_binary_input_accepts_bom_and_leaves_the_next_row(shape, route):
    name = next(
        name
        for name, language in LANGUAGES.items()
        if language.contract.frame_stdin and language.contract.input_shape == shape
    )
    api = esolangs.Language(name)
    artifact = api.generate("01")
    leading = b"\xef\xbb\xbf" + api.encode_inputs([1]).encode()
    following = api.encode_inputs([0]).encode()
    if route == "prepared":
        prepared = api.prepare(artifact)

        def run(stdin):
            return prepared.run(
                stdin=stdin, limits=esolangs.ExecutionLimits(preparation_timeout=2)
            )
    else:

        def run(stdin):
            limits = (
                esolangs.ExecutionLimits(max_steps=100_000)
                if route == "stepped"
                else None
            )
            return api.run(
                artifact, stdin=stdin, limits=limits, isolated=route == "isolated"
            )

    assert api.read_answer(run(leading + following).output) == "1"
    stream = io.BytesIO(leading + following + b"\xff")
    assert api.read_answer(run(stream).output) == "1"
    assert stream.tell() == len(leading)
    assert api.read_answer(run(stream).output) == "0"
    assert stream.read() == b"\xff"


def test_framing_consumes_only_one_binary_bom():
    from esolangs.runtime._input import InputFrame, read_input

    frame = InputFrame(1, lines=False)
    bom = b"\xef\xbb\xbf"
    assert read_input(bom + b"x", frame=frame) == "x"
    assert read_input(bom + b"x") == "\ufeffx"
    assert read_input("\ufeffx", frame=frame) == "\ufeff"
    stream = io.BytesIO(bom + bom + b"x")
    assert read_input(stream, frame=frame) == "\ufeff"
    assert stream.read() == b"x"


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("route", ["native", "bounded", "isolated", "vm", "debugger"])
def test_invocation_uses_the_first_managed_input_reader(prepared, route) -> None:
    events = []

    class Program:
        def read(self):
            events.append("source")
            return ",."

    class Input:
        def readable(self):
            pytest.fail("a user provider's readability is not a stream mode")

        @property
        def read(self):
            events.append("lookup")
            value = b"A" if events.count("lookup") == 1 else b"B"

            def consume():
                events.append("read")
                return value

            return consume

    api = esolangs.Language(REFERENCE)
    target = api.prepare(Program()) if prepared else api
    arguments = () if prepared else (Program(),)
    stdin = Input()
    if route == "vm":
        output = complete_vm(target.make_vm(*arguments, stdin=stdin))
    elif route == "debugger":
        debugger = target.make_debugger(*arguments, stdin=stdin)
        assert debugger.run() == "halted"
        output = debugger.output
    else:
        limits = esolangs.ExecutionLimits(max_steps=2) if route == "bounded" else None
        result = target.run(
            *arguments, stdin=stdin, limits=limits, isolated=route == "isolated"
        )
        output = result.output
        assert result.input_position == result.input_reads == 1

    assert output == "A"
    ordered = ["source", "lookup"] if prepared else ["lookup", "source"]
    assert events == [*ordered, "read"]
    _check_no_stdin_invocation(prepared, route)


def _check_no_stdin_invocation(prepared, route) -> None:
    class Untouched:
        @property
        def read(self):
            pytest.fail("a no-stdin runtime looked up the input reader")

    declaration = next(
        lang
        for lang in LANGUAGES.values()
        if not lang.runtime.reads_stdin
        and lang.parameterized
        and lang.contract.answer_mode == "output"
    )
    api = esolangs.Language(declaration.name)
    program = api.instantiate(api.generate("01"), [1])
    target = api.prepare(program) if prepared else api
    arguments = () if prepared else (program,)
    stdin = Untouched()
    if route == "vm":
        output = complete_vm(target.make_vm(*arguments, stdin=stdin))
    elif route == "debugger":
        debugger = target.make_debugger(*arguments, stdin=stdin)
        assert debugger.run() == "halted"
        output = debugger.output
    else:
        limits = esolangs.ExecutionLimits(
            max_steps=100 if route == "bounded" else None,
            preparation_timeout=1 if prepared else None,
        )
        result = target.run(
            *arguments, stdin=stdin, limits=limits, isolated=route == "isolated"
        )
        output = result.output
        assert result.input_position == result.input_reads == 0
    assert api.read_answer(output) == "1"

    if not prepared and route == "native":
        reference = LANGUAGES[REFERENCE]
        without_stdin = replace(
            reference, runtime=replace(reference.runtime, reads_stdin=False)
        )
        scoped = esolangs.Catalog([without_stdin]).bind(REFERENCE)
        assert scoped.run("+.", stdin=stdin).output == "\x01"
        with pytest.raises(esolangs.ArgumentError, match="runtime declared"):
            scoped.run("+.", stdin=stdin, isolated=True)


@pytest.mark.parametrize("route", ["native", "bounded", "isolated", "vm", "debugger"])
@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"scale": 1}, "scale is only supported"),
        ({"settings": object()}, "settings must be a DialectSettings"),
        ({"seed": 1}, "seed"),
    ],
)
def test_invocation_rejects_options_before_accessing_streams(route, options, message):
    class Untouched:
        @property
        def read(self):
            pytest.fail("invalid options accessed a stream")

    api = esolangs.Language(REFERENCE)
    if route == "vm":
        invoke = api.make_vm
    elif route == "debugger":
        invoke = api.make_debugger
    else:
        invoke = api.run
        options = options | {"isolated": route == "isolated"}
        if route == "bounded":
            options["limits"] = esolangs.ExecutionLimits(max_steps=2)

    with pytest.raises(esolangs.ArgumentError, match=message):
        invoke(Untouched(), stdin=Untouched(), **options)
    if "scale" in options:
        with pytest.raises(esolangs.ArgumentError, match=message):
            invoke(Untouched(), stdin=Untouched(), seed=1, **options)


def test_managed_input_binding_and_binary_chunks(monkeypatch) -> None:
    class Input:
        calls = 0

        @property
        def read(self):
            self.calls += 1
            return lambda: "A" if self.calls == 1 else "B"

    stdin = Input()
    assert ScriptedIO(stdin).input_char() == ord("A")
    assert stdin.calls == 1

    class FalseBytes(bytes):
        def __len__(self):
            return 0

        def __bytes__(self) -> bytes:
            return b"not the backing"

        def __getitem__(self, _key):
            raise AssertionError("binary decoding dispatched to a subclass")

    class ChunkedPair(io.BufferedRWPair):
        def __init__(self, *chunks):
            super().__init__(io.BytesIO(), io.BytesIO())
            self.chunks = iter(chunks)

        def read(self, size=-1):
            assert size > 0
            return next(self.chunks, b"")

    api = esolangs.Language(REFERENCE)
    for packet in (bytes, FalseBytes):
        with ChunkedPair(packet(b","), packet(b".")) as program:
            prepared = api.prepare(program)
        assert prepared.artifact.source == ",."
        with ChunkedPair(packet(b"A")) as managed_input:
            assert prepared.run(stdin=managed_input).output == "A"
        with ChunkedPair(packet(b",.")) as program:
            portable = api.from_json(api.to_json(program))
        assert portable.source == ",."
        assert api.run(portable, stdin="A").output == "A"

    for invalid, message in (
        (None, "stream would block"),
        ([65], "binary stream read must return bytes"),
    ):
        with (
            ChunkedPair(b",", invalid) as program,
            pytest.raises(esolangs.ProgramError, match=message),
        ):
            api.prepare(program)
        with (
            ChunkedPair(b"A", invalid) as managed_input,
            pytest.raises(esolangs.ArgumentError, match=message),
        ):
            api.run(",.", stdin=managed_input)

    from esolangs.runtime import _files

    monkeypatch.setattr(_files, "_BLOCK", 8)
    text = "a" * 7 + "é😀bc\nZ"
    with _files.stream_read_deadline(monotonic() + 2):
        for packet in (bytes, FalseBytes):
            encoded = packet(text.encode())
            for source in (encoded, io.BytesIO(encoded)):
                assert ScriptedIO(source).input_all() == text
        for invalid in (b"\xe2\x82", b"\xe0\x80\x80", b"\xf0\x90\x80!", b"\xc0\xaf"):
            encoded = b"a" * 15 + invalid
            with pytest.raises(UnicodeDecodeError) as expected:
                encoded.decode("utf-8")
            for source in (encoded, io.BytesIO(encoded)):
                with pytest.raises(
                    esolangs.ArgumentError, match="invalid UTF-8 at byte 15"
                ) as caught:
                    ScriptedIO(source)
                actual = caught.value.__cause__
                assert isinstance(actual, UnicodeDecodeError)
                assert actual.args == expected.value.args
                assert str(actual) == str(expected.value)


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


@pytest.mark.parametrize("blocking", [False, True])
def test_buffered_read_write_pair_reads_through_eof(nonblocking_pipe, blocking):
    raw, writer = nonblocking_pipe
    os.set_blocking(raw.fileno(), blocking)
    with io.FileIO(os.devnull, "wb") as sink, io.BufferedRWPair(raw, sink) as source:
        writer.write(b"AB")
        writer.close()
        assert source.read(1) == b"A"
        assert esolangs.run(REFERENCE, ",.", stdin=source).output == "B"
        assert not source.closed
        assert os.get_blocking(raw.fileno()) is blocking


@pytest.mark.parametrize("budget", [{}, {"total_timeout": 5}])
def test_buffered_read_write_pair_refuses_partial_input(nonblocking_pipe, budget):
    raw, writer = nonblocking_pipe
    limits = esolangs.ExecutionLimits(**budget)
    with io.FileIO(os.devnull, "wb") as sink, io.BufferedRWPair(raw, sink) as source:
        writer.write(b"A")
        outcome = esolangs.execute(REFERENCE, ",.,.", stdin=source, limits=limits)
        assert isinstance(outcome.error, esolangs.ArgumentError)
        assert "stream would block" in str(outcome.error)
        assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
        writer.write(b"B")
        writer.close()
        assert esolangs.run(REFERENCE, ",.", stdin=source, limits=limits).output == "B"
        assert not source.closed
        assert not os.get_blocking(raw.fileno())


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


@pytest.mark.parametrize("budget", [{}, {"max_steps": 2}, {"total_timeout": 5}])
@pytest.mark.parametrize("channel", ["source", "stdin"])
def test_acquisition_failure_keeps_the_nested_error_and_its_completed_result(
    budget, channel
) -> None:
    api = esolangs.Language(REFERENCE)
    inner = api.from_source(",+.")
    expected = api.run(inner, stdin="1")
    assert expected.output == "2"
    assert expected.completion is not None
    failures = []

    class Reader:
        def read(self):
            try:
                return api.evaluate(inner, [1]).answer
            except esolangs.ProgramError as failure:
                failures.append(failure)
                raise

    reader = Reader()
    source, stdin = (reader, "A") if channel == "source" else (",.", reader)
    result = api.execute(source, stdin=stdin, limits=esolangs.ExecutionLimits(**budget))
    assert len(failures) == 1
    assert result.status == "rejected"
    assert result.error is failures[0]
    assert result.observation == esolangs.ExecutionResult("", None, None, None)
    with pytest.raises(esolangs.ProgramError, match="no answer") as caught:
        result.unwrap()
    assert caught.value is failures[0]
    assert caught.value.observation == expected
    assert caught.value.partial_output == expected.output


@pytest.mark.parametrize("budget", [{}, {"max_steps": 2}, {"total_timeout": 5}])
@pytest.mark.parametrize(
    ("channel", "bind_failure"),
    [
        ("path", False),
        ("source", False),
        ("source", True),
        ("stdin", False),
        ("stdin", True),
        ("prepared_stdin", False),
        ("prepared_stdin", True),
    ],
)
def test_acquisition_failure_keeps_partial_evidence_on_the_nested_error(
    budget, channel, bind_failure
) -> None:
    api = esolangs.Language(REFERENCE)
    failures = []

    def read():
        try:
            return api.run(
                ",.,", stdin="A", limits=esolangs.ExecutionLimits(max_steps=3)
            ).output
        except esolangs.InputExhaustedError as failure:
            failures.append(failure)
            raise

    class Reader:
        @property
        def read(self):
            return read() if bind_failure else read

    class CallbackPath:
        def __fspath__(self):
            return read()

    limits = esolangs.ExecutionLimits(**budget)
    if channel == "path":
        result = api.execute(CallbackPath(), limits=limits)
    elif channel == "prepared_stdin":
        result = api.prepare(",.").execute(stdin=Reader(), limits=limits)
    else:
        source, stdin = (Reader(), "A") if channel == "source" else (",.", Reader())
        result = api.execute(source, stdin=stdin, limits=limits)
    assert result.status == "input_exhausted"
    assert len(failures) == 1
    assert result.error is failures[0]
    assert result.observation == esolangs.ExecutionResult("", None, None, None)
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        result.unwrap()
    assert caught.value is failures[0]
    assert caught.value.observation == esolangs.ExecutionResult("A", 1, 1, 1, steps=2)
    assert caught.value.partial_output == "A"


@pytest.mark.parametrize("budget", [{}, {"max_steps": 2}, {"total_timeout": 5}])
def test_source_and_stdin_providers_see_caller_context(budget):
    source_text = ContextVar("source_text", default="+.")
    input_text = ContextVar("input_text", default="B")

    class Stream:
        def __init__(self, value):
            self.value = value

        def read(self):
            return self.value.get()

    source_token = source_text.set(",.")
    input_token = input_text.set("A")
    try:
        result = esolangs.run(
            REFERENCE,
            Stream(source_text),
            stdin=Stream(input_text),
            limits=esolangs.ExecutionLimits(**budget),
        )
    finally:
        input_text.reset(input_token)
        source_text.reset(source_token)
    assert result.output == "A"
    assert result.input_position == result.input_reads == 1


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
    from esolangs.runtime import _acquire

    started, release = Event(), Event()
    threads, input_reads = [], []
    read_context = ContextVar("read_context", default=False)

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
        assert read_context.get()
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

    monkeypatch.setattr(_acquire, "Thread", capture_thread)
    program = Program(",.")
    token = read_context.set(True)
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
        read_context.reset(token)
        release.set()
        for thread in threads:
            thread.join(4)
    assert all(not thread.is_alive() for thread in threads)
    assert not input_reads
    assert program.tell() == (2 if block == "program" else 0)


@pytest.mark.parametrize("route", ["native", "bounded", "isolated", "vm", "debugger"])
def test_invalid_stdin_leaves_program_stream_at_its_original_offset(route, tmp_path):
    api = esolangs.Language(REFERENCE)
    source = io.BytesIO(b"skip,.")
    source.seek(4)
    if route in ("vm", "debugger"):
        invoke = api.make_vm if route == "vm" else api.make_debugger
        options = {}
    else:
        invoke = api.run
        options = {"isolated": route == "isolated"}
        if route == "bounded":
            options["limits"] = esolangs.ExecutionLimits(max_steps=2)

    class InheritedReader(io.BytesIO):
        @property
        def closed(self):
            pytest.fail("stdin preflight dispatched a custom closed property")

        def readable(self):
            pytest.fail("stdin preflight dispatched a custom readability check")

    closed = io.BytesIO()
    closed.close()
    inherited_closed = InheritedReader()
    inherited_closed.close()
    with (tmp_path / "write-only").open("wb") as write_only:
        for stdin, cause in (
            (b"\xff", UnicodeDecodeError),
            (closed, ValueError),
            (inherited_closed, ValueError),
            (write_only, io.UnsupportedOperation),
        ):
            with pytest.raises(
                esolangs.ArgumentError, match="cannot read stdin"
            ) as caught:
                invoke(source, stdin=stdin, **options)
            assert type(caught.value.__cause__) is cause
            assert source.tell() == 4
        assert not write_only.closed

    read_sizes = []

    class OverrideReader(InheritedReader):
        def read(self, size=-1):
            read_sizes.append(size)
            assert size != 0
            return "é".encode()

    overridden = OverrideReader()
    overridden.close()
    for stdin in ("é".encode(), InheritedReader("é".encode()), overridden):
        source.seek(4)
        result = invoke(source, stdin=stdin, **options)
        if route == "vm":
            assert complete_vm(result, max_steps=2) == "é"
        elif route == "debugger":
            assert result.run() == "halted"
        assert result.output == "é"
    assert read_sizes == [-1]
