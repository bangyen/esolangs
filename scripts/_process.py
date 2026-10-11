"""Bound verification subprocesses and reap their workers."""

from __future__ import annotations

import codecs
import ctypes
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, cast
from weakref import WeakKeyDictionary

EXCERPT_BYTES = 32 * 1024


@dataclass
class Log:
    path: Path
    reader: threading.Thread | None = None
    overflow: bool = False


_LOGS: WeakKeyDictionary[subprocess.Popen[str], Log] = WeakKeyDictionary()


@dataclass
class Cleanup:
    lock: threading.Lock = field(default_factory=threading.Lock)
    complete: bool = False


_CLEANUPS: WeakKeyDictionary[
    subprocess.Popen[str] | subprocess.Popen[bytes], Cleanup
] = WeakKeyDictionary()
_CLEANUP_LOCK = threading.Lock()


def start_logged(
    cmd: list[str], name: str, env: dict[str, str], root: Path, *, stream: bool
) -> subprocess.Popen[str]:
    """Spool complete step output to a unique ignored file; optionally tee it."""
    directory = root / "notes" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:48] + "-"
    fd, filename = tempfile.mkstemp(prefix=prefix, suffix=".log", dir=directory)
    log = Log(Path(filename))
    os.close(fd)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name == "posix",
    )

    def copy() -> None:
        assert proc.stdout is not None
        reader = cast("io.BufferedReader", cast("io.TextIOWrapper", proc.stdout).buffer)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def tee(raw: bytes) -> None:
            with suppress(BrokenPipeError):
                sys.stdout.write(decoder.decode(raw))
                sys.stdout.flush()

        def stop() -> None:
            log.overflow = True
            stop_process_tree(proc)

        spool(reader, log.path, MAX_LOG_BYTES, stop, tee if stream else None)
        if stream:
            with suppress(BrokenPipeError):
                sys.stdout.write(decoder.decode(b"", final=True))
                sys.stdout.flush()

    log.reader = threading.Thread(target=copy, daemon=True)
    log.reader.start()
    _LOGS[proc] = log
    return proc


def excerpt(proc: subprocess.Popen[str]) -> str:
    """Return a bounded tail and the path to its persistent complete log."""
    log = _LOGS[proc]
    if log.reader is not None:
        log.reader.join(5)
    with log.path.open("rb") as output:
        output.seek(max(0, log.path.stat().st_size - EXCERPT_BYTES))
        tail = output.read(EXCERPT_BYTES).decode("utf-8", errors="replace")
    return f"[log] {log.path}\n" + tail


def stop_process_tree(proc: subprocess.Popen[str] | subprocess.Popen[bytes]) -> None:
    """Kill the step's process tree and reap its direct child."""
    with _CLEANUP_LOCK:
        cleanup = _CLEANUPS.setdefault(proc, Cleanup())
    with cleanup.lock:
        if cleanup.complete:
            return
        if os.name == "posix":
            if proc.poll() is None:
                descendants = []
                pending = [proc.pid]
                while pending:
                    parent = pending.pop()
                    children = child_pids(parent)
                    descendants.extend(children)
                    pending.extend(children)
                # Nested benchmark/reference workers own sessions; kill leaves first.
                for pid in reversed(descendants):
                    with suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)
            # Reap exited leaders before signalling; Darwin rejects zombie groups.
            proc.poll()
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
        else:
            # Discard taskkill's output rather than capturing it: a killed
            # descendant can inherit the stdout pipe's write end and keep it
            # open, so ``capture_output``'s reader thread blocks in join()
            # until the whole test times out.  A timeout guarantees cleanup
            # cannot hang even if taskkill does.
            with suppress(subprocess.TimeoutExpired):
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=30,
                )
            if proc.poll() is None:
                proc.kill()
        proc.wait()
        # Overflow logging and the caller can discover the same exit concurrently.
        cleanup.complete = True


def wait_with_heartbeat(
    proc: subprocess.Popen[str], name: str, start: float, limit: float, heartbeat: float
) -> tuple[str, int]:
    """Collect output until the step's deadline; kill descendants on timeout."""
    deadline = start + limit
    try:
        while True:
            remaining = deadline - time.monotonic()
            try:
                wait = max(0.0, min(heartbeat, remaining))
                if proc in _LOGS:
                    proc.wait(timeout=wait)
                    output = excerpt(proc)
                    return output, 125 if _LOGS[proc].overflow else proc.returncode
                output, _ = proc.communicate(timeout=wait)
                return output or "", proc.returncode
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    stop_process_tree(proc)
                    if proc in _LOGS:
                        output = excerpt(proc)
                    else:
                        output, _ = proc.communicate()
                    return (
                        output or ""
                    ) + f"\n{name}: deadline exceeded ({limit:g}s)\n", 124
                print(
                    f"[....] {name} still running "
                    f"({time.monotonic() - start:.0f}s elapsed)"
                )
    except BaseException:
        stop_process_tree(proc)
        raise


def run_bounded(
    cmd: list[str],
    *,
    timeout: float = 60,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    text: bool = True,
    check: bool = False,
    stdout: int | None = None,
    stderr: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run preflight probes with the same descendant cleanup as check steps."""
    with subprocess.Popen(
        cmd,
        start_new_session=os.name == "posix",
        cwd=cwd,
        env=env,
        text=text,
        stdout=subprocess.PIPE if capture_output else stdout,
        stderr=subprocess.PIPE if capture_output else stderr,
    ) as proc:
        try:
            output, error = proc.communicate(timeout=timeout)
        except BaseException:
            stop_process_tree(proc)
            raise
        result = subprocess.CompletedProcess(cmd, proc.returncode, output, error)
        if check:
            result.check_returncode()
        return result


def write_text(path: Path, text: str) -> None:
    """Flush a sibling temporary file and replace the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # newline="" keeps the bytes exactly as written: on Windows the
        # default text mode translates "\n" to "\r\n", which would make a
        # content hash (durations_sha256) disagree with the file it names.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


MAX_LOG_BYTES = 8 * 1024 * 1024
MARKER = b"\n[diagnostic byte limit exceeded]\n"


def spool(
    stream: BinaryIO,
    path: Path,
    limit: int,
    stop: Callable[[], None],
    tee: Callable[[bytes], None] | None = None,
) -> None:
    """Keep a bounded prefix and overflow excerpt, then stop the process tree."""
    written = 0
    with path.open("wb") as output:
        while chunk := cast(bytes, getattr(stream, "read1", stream.read)(8192)):
            if written + len(chunk) > limit - len(MARKER):
                available = max(0, limit - written - len(MARKER))
                excerpt = chunk[-available:] if available else b""
                output.write(excerpt)
                output.write(MARKER)
                output.flush()
                if tee is not None:
                    tee(MARKER)
                stop()
                return
            output.write(chunk)
            output.flush()
            written += len(chunk)
            if tee is not None:
                tee(chunk)


def child_pids(pid: int) -> list[int]:
    """Return direct child PIDs; refuse truncated or unreadable process evidence."""
    platform = sys.platform
    if platform == "darwin":
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        list_children = library.proc_listchildpids
        list_children.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        list_children.restype = ctypes.c_int
        capacity = 65536
        buffer = (ctypes.c_int * capacity)()
        count = list_children(pid, buffer, ctypes.sizeof(buffer))
        if count < 0:
            raise OSError(ctypes.get_errno(), "cannot enumerate child processes")
        if count >= capacity:
            raise RuntimeError("child process enumeration exceeds capacity")
        return [value for value in buffer[:count] if value > 0]
    if platform.startswith("linux"):
        try:
            tasks = list(Path(f"/proc/{pid}/task").iterdir())
        except FileNotFoundError:
            return []
        found: set[int] = set()
        for task in tasks:
            try:
                found.update(
                    int(value) for value in (task / "children").read_text().split()
                )
            except FileNotFoundError:
                continue
        return sorted(found)
    raise RuntimeError("child process enumeration is unavailable on this platform")
