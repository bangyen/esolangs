"""Tests for the Pointless interpreter."""

import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.pointless.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

#: The wiki's Hello world, comments included.
HELLO = (
    '"setup"                       Call the setup function\n'
    "+++++++++++++++++++++++++++++++  Change the current cell to 32\n"
    "[\n>+\n>++>++>+++>+++>+++>+++<<<<<<<-\n]\n"
    ">-\n>+++++++.\n>++++++++++++++++++++++\n>++++.\n>+++++++++++..\n"
    ">++++++++++++++.\n<<<<<.>>.>>>.>+++++++++++++++++.<<.<-.<<<+.\n"
    '"setup"                       This is the declaration of setup\n'
    "{\n!\n>+\n" + ">+" * 120 + ">\n:-\n" + ">" * 114 + "\n}\n"
)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _finish(code: str, stdin: str = "") -> _Machine:
    machine = _Machine(code, ScriptedIO(stdin))
    while not machine.halted:
        machine.step()
    return machine


def test_wiki_hello_world() -> None:
    # The heading says "Hello, World!", but no cell the program builds is 44.
    assert _run(HELLO) == "Hello World!"


def test_wiki_hello_world_cells_after_its_loop() -> None:
    # The wiki's comment: 0->0; 1 to 113->1; 114->0; 115->33; 116, 117->65;
    # 118 to 121->97; 122 and up->0.
    code = HELLO.replace(">-\n>+++++++.", "", 1).split("\n>++++++++++++++++++++++")[0]
    code += HELLO[HELLO.index('"setup"                       This') :]
    tape = _finish(code).memory + [0] * 8
    assert tape[:122] == [0] + [1] * 113 + [0, 33, 65, 65] + [97] * 4
    assert not any(tape[122:])


def _smallfuck(code: str, width: int = 10) -> list[int] | None:
    """A direct Smallfuck run, or None if it leaves the tape or runs long."""
    match: dict[int, int] = {}
    opens: list[int] = []
    for i, c in enumerate(code):
        if c == "[":
            opens.append(i)
        elif c == "]":
            j = opens.pop()
            match[i], match[j] = j, i
    tape, p, i = [0] * width, 0, 0
    for _ in range(2000):
        if i >= len(code):
            return tape
        c = code[i]
        if c == "*":
            tape[p] ^= 1
        elif c in "<>":
            p += 1 if c == ">" else -1
            if not 0 <= p < width:
                return None
        elif (c == "[") != bool(tape[p]) and c in "[]":
            i = match[i]
        i += 1
    return None


def test_wiki_smallfuck_translation() -> None:
    # * -> =, [ -> =[=, ] -> =]=, after !>> : the wiki's completeness proof.
    rng = random.Random(1)
    checked = 0
    for _ in range(2000):
        code = "".join(rng.choice("*<>>[]") for _ in range(12))
        depth = 0
        if any((depth := depth + (c == "[") - (c == "]")) < 0 for c in code) or depth:
            continue
        want = _smallfuck(code)
        if want is None:
            continue
        pointless = "!>>" + code.replace("*", "=").replace("[", "=[=").replace(
            "]", "=]="
        )
        assert (_finish(pointless).memory + [0] * 12)[2:12] == want, code
        checked += 1
    assert checked > 50


def test_indirect_commands() -> None:
    # Cell 0 = 1 after !; cell 1 then gains tape[0], so 1 too.
    machine = _finish("!>+>+:=")
    assert machine.memory[:3] == [1, 1, 1]
    assert machine.pointer == 1
    assert _finish("!>+-").memory[1] == 0


def test_bang_runs_once() -> None:
    with pytest.raises(HaltError):
        _run("!>!")
    with pytest.raises(HaltError):
        _run('"f"{!}"f""f"')


def test_moving_left_of_cell_zero_halts() -> None:
    with pytest.raises(HaltError):
        _run("<")


def test_functions_are_hoisted_and_global() -> None:
    assert _run('"g" "g"{"h"}  "h"{,.}', "ab") == "a"
    assert _run('"o"{"i"{,.}}"i"', "z") == "z"


def test_name_then_comment_then_brace_declares() -> None:
    assert _run('"f" hi there {,.} "f"', "q") == "q"
    assert _run(',"f" then . "f"{.}', "A") == "AA"


def test_input_is_taken_modulo_256() -> None:
    assert _finish(",", "Ł").memory[0] == 0x41


@pytest.mark.parametrize(
    "code", ["[", "]", "{", "}", '"f', '"f"', '"f"{}"f"{}', '"f"{[}]']
)
def test_malformed_programs_raise(code: str) -> None:
    with pytest.raises(ValueError, match="Pointless"):
        run(code, ScriptedIO())
