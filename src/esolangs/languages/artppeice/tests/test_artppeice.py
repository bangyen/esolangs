"""Tests for the artppeice interpreter."""

import pytest

from esolangs.exceptions import HaltError, InputExhaustedError, ProgramError
from esolangs.languages.artppeice.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

# The page's examples, verbatim.
_XKCD = """00:00:00 -!- four has joined. (4)
00:00:01 -!- four has quit.
00:00:02 <four> chosen by fair dice roll. guaranteed to be random."""
_HELLO = """00:00:00 -!- hello has joined. (Hello, world!)
00:00:01 -!- hello has quit.
00:00:02 <hello> i am a ghost that haunts this channel"""
_CAT = """00:00:00 -!- cat has joined.
00:00:01 -!- cat has quit."""


def _log(*lines: str) -> str:
    return "\n".join("00:00:00 " + line for line in lines)


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_the_xkcd_random_number() -> None:
    assert _out(_XKCD) == "4"


def test_hello_world() -> None:
    assert _out(_HELLO) == "Hello, world!"


def test_the_cat_rereads_each_pass_until_eof() -> None:
    io = ScriptedIO("one  two\nthree\n")
    with pytest.raises(InputExhaustedError):
        run(_CAT, io)
    assert io.getvalue() == "one twothree"


def test_quit_retries_partial_output_before_advancing() -> None:
    class InterruptedOutput(ScriptedIO):
        def print_str(self, text: str) -> None:
            if not self.getvalue():
                super().print_str(text[:1])
                raise HaltError("output interrupted")
            super().print_str(text)

    io = InterruptedOutput()
    machine = _Machine(_HELLO, io)
    machine.step()
    with pytest.raises(HaltError, match="output interrupted"):
        machine.step()
    assert machine.ind == 1
    assert io.getvalue() == "H"
    machine.step()
    assert "hello" not in machine.queues
    machine.step()
    assert machine.halted
    assert io.getvalue() == "Hello, world!"


@pytest.mark.parametrize(
    ("bits", "rules"),
    [("1 1 0", ["1 0", "0", ""])],
)
def test_the_cyclic_tag_encoding(bits: str, rules: list[str]) -> None:
    # The page's joins verbatim; its ``0`` join has no parentheses, so it
    # reads a line.  Its rules read ``-!- <1> bits``, which no form matches;
    # ``<1> bits`` is the evident intent.
    heads = [f"-!- 1 has joined. ({bits})", "-!- 0 has joined."]
    with pytest.raises(ProgramError, match="cannot parse"):
        run(_log(*heads, f"-!- <1> {rules[0]}"), ScriptedIO("\n"))
    machine = _Machine(_log(*heads, *(f"<1> {r}" for r in rules)), ScriptedIO("\n"))
    data = bits.split()
    for _ in range(20):
        machine.step()
        machine.step()
        for rule in rules:
            machine.step()
            if not data:
                assert machine.halted
                return
            if data.pop(0) == "1":
                data += rule.split()
            assert list(machine.queues["1"]) == data
    raise AssertionError("the system did not halt in 20 passes")


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        # Rename moves the words; the old name is free again.
        (
            _log(
                "-!- a has joined. (x y)",
                "-!- a has changed nick to b.",
                "-!- a has quit.",
                "-!- b has quit.",
                "<a>",
            ),
            "",
            "x y",
        ),
        # Renaming to itself, a missing queue, and a comment are nothing.
        (
            _log(
                "-!- a has joined. (x)",
                "-!- a has changed nick to a.",
                "-!- z has changed nick to a.",
                "* a waves",
                "-!- a has quit.",
                "<a>",
            ),
            "",
            "x",
        ),
        # A join reads only when it creates; quit text prints as written.
        (
            _log(
                "-!- a has joined.",
                "-!- a has joined.",
                "-!- a has quit. (  spaced  out )",
                "-!- a has quit.",
                "<a>",
            ),
            "\t1   2 \n",
            "  spaced  out ",
        ),
        # The dequeued word names the target; an empty payload still moves it.
        (
            _log(
                "-!- s has joined. (t s)",
                "-!- t has joined. ()",
                "<s> 1 2",
                "<s>",
                "-!- t has quit.",
                "-!- s has quit.",
                "<s>",
            ),
            "",
            "1 2",
        ),
    ],
)
def test_rulings(code: str, stdin: str, expected: str) -> None:
    assert _out(code, stdin) == expected


@pytest.mark.parametrize(
    ("code", "steps"),
    [
        # The loop wraps: (q q) survives two dequeues and halts on the third.
        (_log("-!- q has joined. (q q)", "<q>"), 6),
        (_log("<q> w"), 1),  # missing source
    ],
)
def test_halts(code: str, steps: int) -> None:
    machine = _Machine(code, ScriptedIO())
    for _ in range(steps - 1):
        machine.step()
    assert not machine.halted
    machine.step()
    assert machine.halted


@pytest.mark.parametrize(
    ("code", "error", "message"),
    [
        ("", ProgramError, "no instructions"),
        ("0:00:00 <a> b", ProgramError, "cannot parse"),
        (
            _log(
                "-!- a has joined. ()",
                "-!- b has joined. ()",
                "-!- a has changed nick to b.",
            ),
            HaltError,
            "b already exists",
        ),
        (_log("-!- a has joined."), InputExhaustedError, None),
    ],
)
def test_errors(code: str, error: type[Exception], message: str | None) -> None:
    with pytest.raises(error, match=message):
        _out(code)
