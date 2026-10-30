"""Qrain queue, output-bitstream and loop semantics, each output derived by hand."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.qrain.interpreter import run
from esolangs.runtime.io import ScriptedIO


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        (",.", "A", "A"),
        (",.", "", "\x00"),
        # The second '.' moves nothing from an empty queue.
        (",..", "A", "A"),
        (",.,.", "AB", "AB"),
        # '[-]' pops A's low bit 1; the rest of A is never printed.
        (",[-]>,.", "AB", "B"),
        # '[' on an empty queue (front 0) skips its body, so '-' never raises.
        ("[-]", "", ""),
        # '+' on an empty queue enqueues 1: one bit, short of a byte.
        ("+.", "", ""),
        # A's last seven bits (0,0,0,0,0,1,0) then B's first (0): 0x20.
        (",-.>,.", "AB", " "),
        # Output [1] pending makes '+' copy the front bit: 1,1,0,... = 3, then
        # the copy 1 and eight 0 bits leave 0,1,0,... = 2.
        ("+.>,+..>,.", "\x01\x00", "\x03\x02"),
        # ']' re-tests: 0x0b = 1,1,0,1,... pops two bits, six remain (0,1,0,...)
        # and with eight more zero bits give 0,1,0,0,0,0,0,0 = 2.
        (",[-].>,.", "\x0b\x00", "\x02"),
        ("ignored text", "", ""),
    ],
)
def test_semantics(code: str, stdin: str, expected: str) -> None:
    assert _run(code, stdin) == expected


def test_dequeue_of_empty_queue_raises() -> None:
    with pytest.raises(HaltError):
        _run("<-")
