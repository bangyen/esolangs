"""Serve isolated execution requests inside the worker process."""

from __future__ import annotations

import base64
import os
import sys
from contextlib import suppress
from threading import Thread
from time import sleep
from typing import Any

from esolangs import exceptions
from esolangs.artifacts import ProgramArtifact
from esolangs.compressed import CompressedText
from esolangs.raster import Raster
from esolangs.registry._catalog import Catalog
from esolangs.runtime._error_causes import cause_chain
from esolangs.runtime._failure_wire import (
    _OUTPUT_LIMIT,
    _failure_text,
)
from esolangs.runtime._input import InputSource
from esolangs.runtime._interpreter_errors import interpreter_errors
from esolangs.runtime._raster_wire import _raster_rows
from esolangs.runtime._request_wire import read_request
from esolangs.runtime._result_wire import (
    encode_decision,
    encode_result,
)
from esolangs.runtime._worker_json import worker_dumps
from esolangs.settings import _settings_for


def _limit_memory(max_memory: int) -> None:
    """Lower the worker's virtual address-space ceiling without raising a hard cap."""
    import resource

    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    ceiling = max_memory if hard == resource.RLIM_INFINITY else min(max_memory, hard)
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, hard))


def _exit_with_parent() -> None:
    """End this worker once its parent is gone.

    A SIGTERM or SIGHUP to the parent skips its kill-and-reap, and the
    orphan (reparented to 1) ran a looping program for hours.
    """
    parent = os.getppid()
    if sys.platform == "linux":
        # The kernel delivers it, with no thread: a watcher's stack counted
        # against max_memory's RLIMIT_AS and tight budgets failed in CI.
        import ctypes
        import signal

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) == 0:  # PR_SET_PDEATHSIG
            if os.getppid() != parent:  # Died before the request took.
                os._exit(1)
            return

    def watch() -> None:
        while os.getppid() == parent:
            sleep(0.25)
        os._exit(1)

    Thread(target=watch, daemon=True).start()


def _worker(*, catalog: Catalog | None = None) -> None:
    """Serve one request with invocation-owned streaming I/O."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    _serve_request(catalog=catalog)


def _serve_request(*, catalog: Catalog | None = None) -> None:
    """Stream live output and validated execution or termination metadata."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    import esolangs.operations.execution as _execution_operations
    from esolangs.runtime.io import ScriptedIO, _output_text

    request = read_request(sys.stdin)
    _exit_with_parent()

    def send(message: dict[str, Any]) -> None:
        print(worker_dumps(message), flush=True)

    class StreamingIO(ScriptedIO):
        def __init__(self, stdin: InputSource = "") -> None:
            super().__init__(stdin)
            self.written = 0

        def _write(self, value: object) -> None:
            text = _output_text(value)
            limit = request["max_output"]
            accepted = text if limit is None else text[: max(0, limit - self.written)]
            super()._write(accepted)
            self.written += len(accepted)
            # One write may contain an entire dump; keep protocol records bounded.
            for at in range(0, len(accepted), 4096):
                send({"output": accepted[at : at + 4096]})
            if len(accepted) != len(text):
                raise exceptions.ExecutionCapError(
                    _OUTPUT_LIMIT,
                    hint="reduce output or raise max_output if the output is needed",
                )

    # Release a small reserve before reporting allocation failure under RLIMIT_AS.
    reserve = bytearray(65_536)

    def send_failure(error: BaseException) -> None:
        reserve.clear()
        # ``run`` translates an in-process MemoryError; here it is the cap.
        if any(isinstance(cause, MemoryError) for cause in cause_chain(error)):
            # Without max_memory the machine ran out, not a caller's budget.
            capped = request["max_memory"] is not None
            if not capped and isinstance(error, exceptions.InterpreterLimitError):
                with suppress(MemoryError):
                    print(_failure_text(error), flush=True)
                    return
            send(
                {
                    "error": "ExecutionCapError" if capped else "InterpreterLimitError",
                    "args": [
                        "isolated memory limit exceeded"
                        if capped
                        else "isolated worker ran out of memory"
                    ],
                    "notes": None,
                    "cause": None,
                    "suppress_context": False,
                    "execution": None,
                    **({"bound": "max_memory"} if capped else {}),
                    "output_limit": False,
                }
            )
            return
        print(_failure_text(error), flush=True)

    try:
        if request["max_memory"] is not None:
            try:
                _limit_memory(request["max_memory"])
            except (OSError, OverflowError, ValueError) as error:
                raise exceptions.InterpreterLimitError(
                    f"cannot enforce memory limit: {error}"
                ) from error
        program = request["program"]
        if request["compressed"]:
            program = CompressedText(base64.b64decode(program, validate=True))
        if request["raster"]:
            program = Raster(_raster_rows(program))
        settings = _settings_for(
            request["language"],
            {
                key: int(value, 16) if key in request["integer_settings"] else value
                for key, value in request["settings"].items()
            },
            catalog=catalog,
        )
        # The parent already decoded and checked runnable source.
        program = ProgramArtifact(
            program,
            request["language"],
            settings=settings,
            scale=request["scale"] if request["termination"] else None,
        )
        prepared = None
        if request["report_prepared"]:
            from esolangs.runtime._prepared import _PreparedRuntime, prepare_program

            name = request["language"]
            with interpreter_errors(
                f"the {name} interpreter exceeded the recursion limit while preparing",
                language=name,
                input_acquired=True,
            ):
                prepared = prepare_program(
                    _PreparedRuntime,
                    name,
                    program,
                    settings=settings,
                    scale=request["scale"],
                    catalog=catalog,
                    bind_machine=True,
                )
            send({"prepared": True})
        if request["termination"]:
            from esolangs.runtime._termination import _termination_result

            proved = _termination_result(
                request["language"],
                program,
                request["stdin"],
                max_steps=request["max_steps"],
                settings=settings,
                catalog=catalog,
                io_factory=StreamingIO,
                prepared=prepared,
            )
            result = proved.observation
        else:
            outcome = _execution_operations._execute_invocation(  # noqa: SLF001 - same outcome route as public execute
                request["language"],
                program,
                stdin=request["stdin"],
                seed=int(request["seed"], 16)
                if request["integer_seed"]
                else request["seed"],
                scale=request["scale"],
                settings=settings,
                max_steps=request["max_steps"],
                catalog=catalog,
                io_factory=StreamingIO,
                prepared=prepared,
            )
            if outcome.error is not None:
                send_failure(outcome.error)
                return
            result = outcome.observation
        try:
            message = {"result": result.output, "execution": encode_result(result)}
            if request["termination"]:
                message["termination"] = encode_decision(proved.decision)
            send(message)
        except (TypeError, ValueError) as encoding_error:
            raise exceptions.InterpreterLimitError(
                "cannot transport execution evidence"
            ) from encoding_error
    except (MemoryError, exceptions.EsolangError) as error:
        send_failure(error)


if __name__ == "__main__":
    _worker()
