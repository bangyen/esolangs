"""Tests for the HQ9+ with headers interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.hq9_with_headers.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

_HQ = """==== HEADER ====
COMMAND FLOW
    2,1,3
CHARACTER SEMANTICS
    H
        p("Hello, World!")
    Q
        p({{CODE}})
    9
        p({{99BOB}})
    +
        a++
STARTUP
    a = 0
    placeholders = ["CODE", "99BOB"]
CHECKSUM
    277
==== END HEADER ====
QHQ
"""
_TRUTH = """==== HEADER ====
COMMAND FLOW
    1,'JZtruth#3,2,'J_2,3
CHARACTER SEMANTICS
    i
        [>>. truth]
    1
        p("1")
    0
        p("0")
STARTUP
    p()
CHECKSUM
    245
==== END HEADER ====
i10
"""
_LOOP = """==== HEADER ====
COMMAND FLOW
    1,'J_1
CHARACTER SEMANTICS
    N
        p()
STARTUP
    p()
CHECKSUM
    121
==== END HEADER ====
N
"""


def _source(
    flow: str, commands: dict[str, list[str]], startup: list[str], program: str
) -> str:
    """A source with the right checksum."""
    lines = ["==== HEADER ====", "COMMAND FLOW", "    " + flow, "CHARACTER SEMANTICS"]
    for name, body in commands.items():
        lines += ["    " + name, *("        " + line for line in body)]
    lines += ["STARTUP", *("    " + line for line in startup), "CHECKSUM"]
    lines += [
        f"    {sum(map(ord, program)) % 1024 + 43}",
        "==== END HEADER ====",
        program,
    ]
    return "\n".join(lines)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _steps(code: str, stdin: str, count: int) -> _Machine:
    machine = _Machine(code, ScriptedIO(stdin))
    for _ in range(count):
        machine.step()
    return machine


def test_wiki_hq9_example_prints_its_title() -> None:
    # Labelled 'Print "Hello, World!QHQQHQ"': flow 2,1,3 runs H, Q, Q.
    assert _run(_HQ) == "Hello, World!QHQQHQ"


def test_wiki_truth_machine_jumps_to_command_numbers() -> None:
    # ``'JZtruth#3`` reaches command 3 at flow position 5, not position 3.
    assert _run(_TRUTH, "0\n") == "0"
    machine = _steps(_TRUTH, "1\n", 100)
    assert not machine.halted
    assert set(machine.io.getvalue()) == {"1"}


def test_wiki_infinite_loop_never_halts() -> None:
    assert not _steps(_LOOP, "", 100).halted


def test_decimal_read_stops_at_and_consumes_a_non_digit() -> None:
    code = _source(
        "1,2,3", {"n": ["[>>. v]", "p(Vv)"], "c": ["[>>, v]", "p(Vv)"]}, [], "nnc"
    )
    assert _run(code, "12x34\n7") == "123455"
    # EOF: the assumed 0, and 0 for a character.
    assert _run(code, "") == "000"


def test_arithmetic_is_unbounded_and_div_floors() -> None:
    body = ["[SUB z t d]", "[DIV d s q]", "p(Vq)", "[MUL t t t]", "p(Vt)"]
    code = _source(
        "1", {"x": body}, ["z = 0", "t = 7", "s = 2", "t = 99999999999"], "x"
    )
    assert _run(code) == "-50000000000" + str(99999999999**2)


def test_conditional_runs_hex_encoded_commands() -> None:
    then, other = (s.encode().hex().upper() for s in ('p("big")', 'p("@41@0A")'))
    code = _source("1", {"x": [f"[~:: a b {then} {other}]"]}, ["a = 2", "b = 3"], "x")
    assert _run(code) == "A\n"
    assert _run(code.replace("a = 2", "a = 4")) == "big"


def test_fork_cannot_fork_and_jumps() -> None:
    code = _source("'Fv#2,1,2", {"a": ['p("a")'], "b": ['p("b")']}, ["v = 5"], "ab")
    assert _run(code) == "b"


def test_halt_comments_and_a_continued_line() -> None:
    code = _source("/skip,1,'H,2", {"a": ['p("a\\', 'b")'], "b": ['p("c")']}, [], "ab")
    assert _run(code) == "a        b"


def test_program_spans_lines_and_code_prints_it_joined() -> None:
    code = _source("1,2", {"a": ["p({{CODE}})"]}, [], "aa").replace("\naa", "\na\na")
    assert _run(code) == "aaaa"


def test_ninety_nine_bob_prints_the_song() -> None:
    out = _run(_source("1", {"9": ["p({{99BOB}})"]}, [], "9"))
    assert out.startswith("99 bottles of beer on the wall, 99 bottles of beer.\n")


@pytest.mark.parametrize(
    "code",
    [
        _HQ.replace("277", "278"),
        _HQ.replace("2,1,3", "2,1"),
        _HQ.replace("2,1,3", "2,1,1,3"),
        _HQ.replace("    a = 0", "   a = 0"),
        _HQ.replace("QHQ\n", "QHX\n"),
        _HQ + "==== HEADER ====\n",
        _HQ.replace("CHECKSUM\n    277\n", ""),
        _TRUTH.replace("'J_2", "'J_9"),
        _TRUTH.replace("'J_2", "'X"),
        _HQ.replace("a++", "a+++"),
        _HQ.replace("a = 0", "placeholders++"),
    ],
)
def test_malformed_sources_are_rejected(code: str) -> None:
    with pytest.raises(ValueError, match="HQ9\\+ with headers"):
        run(code, ScriptedIO(""))


def test_runtime_errors() -> None:
    with pytest.raises(HaltError, match="before being set"):
        _run(_source("1", {"x": ["p(Vq)"]}, [], "x"))
    with pytest.raises(HaltError, match="DIV by 0"):
        _run(_source("1", {"x": ["[DIV a b c]"]}, ["a = 1", "b = 0"], "x"))
