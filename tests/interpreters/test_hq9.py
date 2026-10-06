"""HQ9+ output, accumulator and quine dialect controls."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.hq9 import _Machine, run
from tests.interpreters.runner import run_program


@pytest.mark.parametrize("code", ["H", "h"])
def test_greeting(code: str) -> None:
    assert run_program(run, code) == "Hello, world!\n"


@pytest.mark.parametrize("code", ["Q", "q", " Q\n☃", "qQ"])
def test_quine_preserves_source(code: str) -> None:
    assert run_program(run, code) == code * sum(char in "Qq" for char in code)


def test_execution_order_and_silent_accumulator() -> None:
    io = ScriptedIO("unused")
    machine = _Machine("h++qH", io)
    while not machine.halted:
        machine.step()
    assert io.getvalue() == "Hello, world!\nh++qHHello, world!\n"
    assert machine.memory == [2]
    assert io.position() == 0


@pytest.mark.parametrize("code", ["", "xyz☃\n", "+++", "\u210e\uff28\uff31"])
def test_other_characters_are_ignored(code: str) -> None:
    assert run_program(run, code) == ""


def test_song_covers_every_verse_and_singular_boundary() -> None:
    verses = run_program(run, "9").rstrip("\n").split("\n\n")
    assert len(verses) == 100
    for count, verse in zip(range(99, 0, -1), verses[:-1], strict=True):
        first, second = verse.splitlines()
        noun = "bottle" if count == 1 else "bottles"
        assert first == f"{count} {noun} of beer on the wall, {count} {noun} of beer."
        remaining = (
            "no more bottles"
            if count == 1
            else "1 bottle"
            if count == 2
            else f"{count - 1} bottles"
        )
        assert (
            second
            == f"Take one down and pass it around, {remaining} of beer on the wall."
        )
    assert verses[-1] == (
        "No more bottles of beer on the wall, no more bottles of beer.\n"
        "Go to the store and buy some more, 99 bottles of beer on the wall."
    )
    assert run_program(run, "99") == run_program(run, "9") * 2
