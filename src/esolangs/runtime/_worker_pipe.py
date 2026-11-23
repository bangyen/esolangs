"""Bulk worker transport with one owner of the subprocess pipes."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from contextlib import nullcontext, suppress
from subprocess import Popen
from threading import Event, Thread
from typing import TextIO

from esolangs.runtime._json import worker_loads
from esolangs.runtime._wait import wait_for_event


def communicate(
    child: Popen[str], request: str, deadline: float, *, clock: Callable[[], float]
) -> tuple[str, bool]:
    """Collect stdout and indicate expiry, killing and reaping on interruption."""
    box: list[tuple[str, float] | BaseException] = []
    finished = Event()

    def transfer() -> None:
        try:
            output, _stderr = child.communicate(request)
            box.append((output, clock()))
        except BaseException as error:
            box.append(error)
        finally:
            finished.set()

    reader = Thread(target=transfer, daemon=True)
    try:
        reader.start()
        expired = not wait_for_event(finished, deadline, clock=clock)
        if expired:
            child.kill()
            wait_for_event(finished)
        result = box[0]
        if isinstance(result, BaseException):
            raise result
    except BaseException:
        child.kill()
        if reader.ident is not None:
            wait_for_event(finished)
        child.wait()
        raise
    output, completed_at = result
    return output, expired or completed_at >= deadline


def spawn_worker(*, streaming: bool, deferred: bool) -> Popen[str]:
    """Start the fixed interpreter worker with the parent's effective policy."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not (sys.flags.ignore_environment and name.startswith("PYTHON"))
    }
    env.pop("PYTHONPATH", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONINTMAXSTRDIGITS"] = str(sys.get_int_max_str_digits())
    # Use the running interpreter's effective cache policy, which may have
    # come from command-line flags or changed since startup.
    for name, value in (
        ("PYTHONDONTWRITEBYTECODE", "1" if sys.dont_write_bytecode else None),
        ("PYTHONPYCACHEPREFIX", sys.pycache_prefix),
        ("PYTHONOPTIMIZE", str(sys.flags.optimize) if sys.flags.optimize else None),
    ):
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    # Match the importer's string-only search without embedding custom reprs.
    search_path = [str.__str__(path) for path in sys.path if isinstance(path, str)]
    # Site hooks run before the worker can restore the parent's search path.
    startup_flags = ["-P"]
    if sys.flags.no_site:
        startup_flags.append("-S")
    if sys.flags.no_user_site:
        startup_flags.append("-s")
    entry = "_worker(deferred=True)" if deferred else "_worker()"
    return subprocess.Popen(  # fixed executable and code, no shell.
        [
            sys.executable,
            *startup_flags,
            "-c",
            f"import sys; sys.path[:] = {search_path!r}; "
            "from esolangs.runtime._isolated import _worker; "
            f"sys.setrecursionlimit({sys.getrecursionlimit()}); {entry}",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if streaming else subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )


def write_request(
    stream: TextIO, request: Sequence[str], *, keep_open: bool = False
) -> None:
    """Write JSON, leaving a line boundary before a deferred input document."""
    with suppress(BrokenPipeError), nullcontext(stream) if keep_open else stream:
        if isinstance(request, str):
            stream.write(request)
        else:
            stream.writelines(request)
        if keep_open:
            stream.write("\n")
            stream.flush()


def read_deferred_input(stream: TextIO) -> str:
    """Read the input snapshot sent after preparation reaches the barrier."""
    value = worker_loads(stream.read())
    if not isinstance(value, str):
        raise ValueError("invalid deferred stdin")
    return value
