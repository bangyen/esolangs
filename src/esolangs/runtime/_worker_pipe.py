"""Bulk worker transport with one owner of the subprocess pipes."""

from __future__ import annotations

from collections.abc import Callable
from subprocess import Popen
from threading import Event, Thread

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
