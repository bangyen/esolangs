"""Fresh workers reject certification imports before operational loading."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from sys import getrecursionlimit
from typing import Any
from unittest.mock import patch

WORKER_GUARD = """
import importlib.abc
import json
import os
import sys
class Barrier(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.blocked = []
        self.fatal = False
    def find_spec(self, fullname, path, target=None):
        if fullname.endswith(('._certification', '.certification', '.proof_formulas')):
            if self.fatal:
                os._exit(86)
            self.blocked.append(fullname)
            raise ImportError('certification is not operational')
barrier = Barrier()
sys.meta_path.insert(0, barrier)

for module in ('esolangs.registry._certification',
               'esolangs.languages.brainfuck.proof_formulas'):
    try:
        __import__(module)
    except ImportError as error:
        assert str(error) == 'certification is not operational'
    else:
        raise AssertionError('worker import barrier did not fire')
assert len(barrier.blocked) == 2
barrier.blocked.clear()
# Exit immediately: a caught ImportError must not permit a successful wire result.
barrier.fatal = True
"""


@contextmanager
def guarded_worker(*, expected: int = 1) -> Iterator[None]:
    """Require every expected worker with live import controls."""
    original = subprocess.Popen
    launched = []

    def guarded(command: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        assert command[1:3] == ["-P", "-c"], command
        assert command[-1].endswith(
            "from esolangs.runtime._worker_main import _worker; "
            f"sys.setrecursionlimit({getrecursionlimit()}); _worker()"
        )
        launched.append(command)
        return original([*command[:-1], WORKER_GUARD + command[-1]], **kwargs)

    with patch.object(subprocess, "Popen", guarded):
        yield
    assert len(launched) == expected, launched
