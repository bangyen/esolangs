"""Revision-pinned published programs, independent of this repo's generators."""

import pytest

import esolangs
from esolangs.debugger import complete_vm, make_vm

# CC0 examples. Expected values come from the cited page, not local execution.
_BRAINFUCK = "https://esolangs.org/w/index.php?title=Brainfuck&oldid=196617"
_DEADFISH = "https://esolangs.org/w/index.php?title=Deadfish&oldid=196539"
_CASES = [
    pytest.param(
        "brainfuck",
        "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]"
        ">>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++.",
        "Hello World!\n",
        _BRAINFUCK,
        id="brainfuck-nested-hello",
    ),
    pytest.param(
        "brainfuck",
        "+++++++++++[>++++++>+++++++++>++++++++>++++>+++>+<<<<<<-]>+++"
        "+++.>++.+++++++..+++.>>.>-.<<-.<.+++.------.--------.>>>+.>-.",
        "Hello, World!\n",
        _BRAINFUCK,
        id="brainfuck-six-cell-hello",
    ),
    pytest.param("Deadfish", "iissso", "0\n", _DEADFISH, id="deadfish-exact-trap"),
    pytest.param("Deadfish", "diissisdo", "288\n", _DEADFISH, id="deadfish-past-trap"),
    pytest.param(
        "Deadfish",
        "iissisdddddddddddddddddddddddddddddddddo",
        "0\n",
        _DEADFISH,
        id="deadfish-underflow",
    ),
]


@pytest.mark.parametrize(("language", "source", "expected", "citation"), _CASES)
def test_published_programs(language, source, expected, citation):
    assert esolangs.run(language, source, timeout=2) == expected, citation
    vm = make_vm(language, source)
    assert complete_vm(vm, max_steps=10_000) == expected, citation
    assert complete_vm(vm, max_steps=0) == expected, citation
