"""Tests for the Fackward interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.fackward.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_wiki_hello_world() -> None:
    code = "72 101 108 108 111 44 32 119 111 114 108 100 33 10 H"
    assert _run(code) == "Hello, world!\n"


def test_wiki_infinite_loop_duplicates_a_function() -> None:
    # ``:`` copies the other ``:`` every pass, so no pass is quiet or reads.
    machine = _Machine("::", ScriptedIO(""))
    for _ in range(1000):
        machine.step()
    assert not machine.halted


def test_the_null_program_is_a_cat_that_reads_in_pairs() -> None:
    # Every quiet pass reads, so two characters arrive before one prints;
    # the read paired with an odd last one meets EOF and halts first.
    assert _run("", "abcd") == "abcd"
    assert _run("", "abc") == "ab"
    assert _run("") == ""


def test_results_are_pushed_in_written_order() -> None:
    # ``~`` pushes 66 then 65, and the next pass reads 65 first; the other
    # order would push what moving 65 and 66 does, printing "BA".
    assert _run(")[H]~65 66") == "AB"


def test_a_function_runs_only_on_the_values_behind_it() -> None:
    # Pass 1 moves ``[H 48]`` past the trailing ``)``; pass 2 reads backwards.
    assert _run("[H 48])") == "0"
    assert _run(")[H]-/0 1") == "\x00"  # ``-`` sees ``/`` and waits


def test_arithmetic() -> None:
    assert _run(")[H]/100 3") == "!"  # 33
    assert _run(")[H]+30 3*3 11") == "!!"
    assert _run(")[H 33]%5") == "\x00!"


def test_blocks_wrap_and_append() -> None:
    assert _run(")[H](65") == ""  # ``[65]`` is never spilled
    assert _run("[H 66]<[65]))") == "AB"


def test_errors() -> None:
    with pytest.raises(HaltError, match="no code point"):
        _run("-5")
    with pytest.raises(HaltError, match="by 0"):
        _run("/1 0")
    with pytest.raises(HaltError, match="negative count"):
        _run(")[5]-1$")
    with pytest.raises(ValueError, match="unmatched"):
        _run("[")
    with pytest.raises(ValueError, match="is not Fackward"):
        _run("x")


def test_the_printable_range_is_the_scalar_values() -> None:
    assert _run("1114111") == chr(0x10FFFF)
    assert _run("55295") == chr(0xD7FF)
    assert _run("57344") == chr(0xE000)
    for bad in ("1114112", "55296", "57343"):
        with pytest.raises(HaltError, match="no code point"):
            _run(bad)


def test_a_count_past_sys_maxsize_is_a_limit() -> None:
    """``[x] * count`` raised a bare OverflowError (CLI exit 70)."""
    import esolangs
    from esolangs.exceptions import InterpreterLimitError

    with pytest.raises(InterpreterLimitError, match="index-sized"):
        esolangs.run("Fackward", "$ 99999999999999999999 1", timeout=2)
