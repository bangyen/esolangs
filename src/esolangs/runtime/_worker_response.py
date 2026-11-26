"""Collect and decode isolated interpreter responses."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from contextlib import suppress
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
from typing import Any, TextIO, cast

from esolangs import exceptions
from esolangs.outcomes import ExecutionOutcome, _failed_outcome
from esolangs.runtime._acquire import preparation_expired
from esolangs.runtime._failure_wire import _error_from_wire
from esolangs.runtime._json import worker_loads
from esolangs.runtime._proof import TerminationResult
from esolangs.runtime._result_wire import decode_result, decode_termination
from esolangs.runtime._wait import wait_slice

type _WorkerResponse = ExecutionOutcome | TerminationResult


def _decode_outcome(text: str, *, expired: bool) -> _WorkerResponse:
    error: exceptions.EsolangError
    output: list[str] = []
    result: dict[str, Any] | None = None
    malformed = False
    for line in text.splitlines():
        try:
            message = worker_loads(line)
        except ValueError:
            malformed = True
            break  # A killed write may leave only part of its last JSON record.
        if not isinstance(message, dict) or result is not None:
            malformed = True
            break
        if "output" in message:
            if set(message) != {"output"} or not isinstance(message["output"], str):
                malformed = True
                break
            output.append(message["output"])
        else:
            result = message
    partial = "".join(output)
    if expired:
        error = exceptions.ExecutionTimeoutError(
            "isolated execution exceeded its deadline"
        )
        error.partial_output = partial
        return _failed_outcome(error)
    if result is None and not malformed:
        error = exceptions.InterpreterLimitError(
            "isolated interpreter exited without a result",
            hint="check the worker exit status and available system resources",
        )
        error.partial_output = partial
        return _failed_outcome(error)
    try:
        if malformed or result is None:
            raise ValueError("invalid isolated stream")
        if "error" in result:
            error = _error_from_wire(result, partial)
        else:
            fields = {"result", "execution"}
            if "termination" in result:
                fields.add("termination")
            if set(result) != fields or result["result"] != partial:
                raise ValueError("invalid isolated result fields or output")
            if "termination" in result:
                termination = decode_termination(
                    result["result"], result["execution"], result["termination"]
                )
                if termination.observation.input_position is None:
                    raise ValueError("worker omitted input counters")
                return termination
            execution = decode_result(result["result"], result["execution"])
            if execution.input_position is None:
                raise ValueError("worker omitted input counters")
            if execution.completion is None:
                raise ValueError("worker omitted output completion")
            return ExecutionOutcome("completed", execution)
    except (TypeError, ValueError, KeyError) as cause:
        error = exceptions.InterpreterLimitError("invalid isolated execution result")
        error.partial_output = partial
        error.__cause__ = cause
        return _failed_outcome(error)
    return _failed_outcome(error)


def _bounded_output(
    child: subprocess.Popen[str],
    request: Sequence[str],
    deadline: float,
    *,
    preparation_deadline: float | None = None,
    execution_timeout: float | None = None,
) -> _WorkerResponse:
    """Read bounded worker records; kill and reap on an output limit or deadline."""
    records: Queue[str | BaseException | None] = Queue(maxsize=16)
    stopped = Event()

    def publish(record: str | BaseException | None) -> bool:
        while not stopped.is_set():
            try:
                records.put(record, timeout=0.05)
                return True
            except Full:
                pass
        return False

    def transfer() -> None:
        try:
            # _launch always opens both streams with PIPE.
            stdin = cast("TextIO", child.stdin)
            stdout = cast("TextIO", child.stdout)
            # Like communicate(), keep reading if the child closed its input.
            with suppress(BrokenPipeError), stdin:
                if isinstance(request, str):
                    stdin.write(request)
                else:
                    stdin.writelines(request)
            for line in stdout:
                if not publish(line):
                    return
        except Exception as error:
            publish(error)
        finally:
            publish(None)

    reader = Thread(target=transfer, daemon=True)
    try:
        reader.start()
        return _read_worker_output(
            child, records, deadline, preparation_deadline, execution_timeout
        )
    finally:
        stopped.set()
        child.kill()
        child.wait()
        if reader.ident is not None:
            reader.join()


def _prepared_record(message: object) -> bool:
    return (
        isinstance(message, dict)
        and message.keys() == {"prepared"}
        and message["prepared"] is True
    )


def _queued_output(
    records: Queue[str | BaseException | None], *, awaiting_prepared: bool
) -> Iterator[str]:
    """Retain complete output already queued when a deadline elapsed."""
    # This is the sole consumer. Limit the drain to the current queue length.
    for _ in range(records.qsize()):
        record = records.get_nowait()
        if not isinstance(record, str):
            break
        try:
            message = worker_loads(record)
        except ValueError:
            break
        if awaiting_prepared and _prepared_record(message):
            awaiting_prepared = False
            continue
        if not isinstance(message, dict) or message.keys() != {"output"}:
            break
        yield record


def _read_worker_output(
    child: subprocess.Popen[str],
    records: Queue[str | BaseException | None],
    deadline: float,
    preparation_deadline: float | None,
    execution_timeout: float | None,
) -> _WorkerResponse:
    """Read the worker stream under the active phase deadline."""
    output: list[str] = []
    expired = False
    limited = False
    execution_deadline = None
    awaiting_prepared = (
        preparation_deadline is not None or execution_timeout is not None
    )

    while True:
        active_deadline = min(
            phase
            for phase in (deadline, preparation_deadline, execution_deadline)
            if phase is not None
        )
        waited = wait_slice(active_deadline, monotonic())
        if not waited:
            expired = True
            output.extend(_queued_output(records, awaiting_prepared=awaiting_prepared))
            break
        try:
            record = records.get(timeout=waited)
        except Empty:
            continue
        if record is None:
            break
        if isinstance(record, BaseException):
            raise record
        try:
            message = worker_loads(record)
        except ValueError:
            output.append(record)
            break
        if awaiting_prepared and _prepared_record(message):
            awaiting_prepared = False
            preparation_deadline = None
            if execution_timeout is not None:
                execution_deadline = monotonic() + execution_timeout
            continue
        output.append(record)
        limited = isinstance(message, dict) and message.get("output_limit") is True
        if limited:
            break
    # A complete verdict must still leave the worker within its deadline.
    while not expired and not limited:
        waited = wait_slice(active_deadline, monotonic())
        try:
            child.wait(timeout=waited)
        except subprocess.TimeoutExpired:
            expired = not waited
        else:
            break
    result = _decode_outcome("".join(output), expired=expired)
    if expired and preparation_deadline is not None and preparation_deadline < deadline:
        raise preparation_expired(partial_output=result.observation.output)
    if (
        expired
        and execution_deadline is not None
        and execution_deadline < deadline
        and isinstance(result, ExecutionOutcome)
        and isinstance(result.error, exceptions.ExecutionTimeoutError)
    ):
        result.error.bound = "execution_timeout"
        result.error.args = (
            f"execution exceeded the {execution_timeout}-second timeout",
        )
    return result
