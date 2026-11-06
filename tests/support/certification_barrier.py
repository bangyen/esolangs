"""Fresh workers reject certification imports before operational loading."""

from contextlib import contextmanager
from unittest.mock import patch

from esolangs.runtime import _isolated

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
def guarded_worker():
    """Require one real worker with live import controls."""
    original = _isolated.subprocess.Popen
    launched = []

    def guarded(command, **kwargs):
        assert command[1] == "-c", command
        assert command[2] == (
            "from esolangs.runtime._isolated import _worker; _worker()"
        )
        launched.append(command)
        return original([*command[:2], WORKER_GUARD + command[2]], **kwargs)

    with patch.object(_isolated.subprocess, "Popen", guarded):
        yield
    assert len(launched) == 1, launched
