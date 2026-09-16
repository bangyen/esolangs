"""What the CLI suites share: the examples directory, a bound, and both streams.

Split out of test_cli_conventions when that file became five, so the five do
not each carry a copy of the wait a non-terminating program is given or the
one read that returns stdout and stderr together.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from esolangs.cli import main
from tests.test_cli import _FakeStdin

EXAMPLES = Path(__file__).parents[1] / "examples"


#: The bound a test gives a program it expects to *not finish*.  These
#: assert an exit code or a message, never an elapsed time, so the value is
#: only how long the suite sits still waiting for the alarm -- the runs it
#: is used on (`+[]`, and 123 on a row it answers by looping) are already
#: looping when the clock starts.  The floor is the slowest *halting* run,
#: which would be misread as a loop if cut short; measured across this
#: suite's corpus that is 0.296s, and these programs do not halt at all.
_LOOPS = "0.5"


def call_both(
    args: list[str], capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> tuple[str, str]:
    """Run ``main`` and return both streams.

    ``call_main`` reads ``capsys`` itself and hands back only stdout, so a
    test that then reached for ``.err`` found an empty string and passed
    while asserting nothing.  These tests are *about* stderr, so they need
    the one read to return both.
    """
    with (
        patch.object(sys, "argv", ["esolangs", *args]),
        patch.object(sys, "stdin", _FakeStdin(stdin)),
    ):
        main()
    captured = capsys.readouterr()
    return str(captured.out), str(captured.err)
