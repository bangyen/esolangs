"""Independent HQ9+ engine from the wiki (HQ9+ revision 197022).

The wiki leaves the exact texts open: H prints "hello, world" there but
"Hello, world!" in Biffle's original page, and the lyrics page (99 bottles of
beer revision 195895) admits "several variations".  The model pins the
shipped variant: Biffle's greeting plus newline, and the two-line
99-bottles-of-beer.net verses ending in the store verse.
"""

import itertools
import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.hq9 import _Machine, run
from tests.interpreters.views import view as vm_view


def bottles(count):
    if count == 0:
        return "no more bottles"
    return "1 bottle" if count == 1 else f"{count} bottles"


def song():
    verses = [
        f"{bottles(n)} of beer on the wall, {bottles(n)} of beer.\n"
        f"Take one down and pass it around, {bottles(n - 1)} of beer on the wall.\n"
        for n in range(99, 0, -1)
    ]
    verses.append(
        "No more bottles of beer on the wall, no more bottles of beer.\n"
        "Go to the store and buy some more, 99 bottles of beer on the wall.\n"
    )
    return "\n".join(verses)


SONG = song()


def reference(code, cap):
    accumulator = cursor = 0
    output = []
    for char in code[:cap]:
        # Only ASCII letters fold: the wiki infers case-insensitivity from
        # Biffle's lowercase "qqqq" example.
        if char in "Hh":
            output.append("Hello, world!\n")
        elif char in "Qq":
            output.append(code)
        elif char == "9":
            output.append(SONG)
        elif char == "+":
            accumulator += 1
        cursor += 1
    return "".join(output), cursor, accumulator, cursor == len(code)


def corpus():
    yield from (
        "".join(commands)
        for length in range(5)
        for commands in itertools.product("Hq9+x", repeat=length)
    )
    yield from [
        "hQ",
        "qqqq\n",
        "+" * 300,
        "\uff48\uff51\uff19\uff0b",
        "\u0130\u0131\u017fK",
        "h\x00Q\n9",
        "Hello, world!",
        "99",
        "+Q+",
    ]


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert vm_view(machine, "stack") == []
    assert len(vm_view(machine, "memory")) == 1
    assert io.position() == 0
    result = (
        io.getvalue(),
        vm_view(machine, "ip"),
        vm_view(machine, "memory")[0],
        machine.halted,
    )
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == snapshot
        assert io.getvalue() == result[0]
    return result


@pytest.mark.parametrize("cap", [0, 1, 2, 3, 400])
def test_bounded_states_match_independent_engine(cap):
    for code in corpus():
        assert observe(code, cap) == reference(code, cap), (code, cap)


def test_run_matches_independent_engine():
    for code in corpus():
        io = ScriptedIO("unused")
        run(code, io)
        assert io.getvalue() == reference(code, len(code))[0], code
        assert io.position() == 0


def test_song_matches_wiki_canonical_shape():
    verses = SONG.split("\n\n")
    assert len(verses) == 100
    assert verses[0].startswith("99 bottles of beer on the wall, 99 bottles of beer.")
    assert "1 bottle of beer on the wall, 1 bottle of beer." in verses[98]
    assert not re.search(r"\b1 bottles", SONG)
    assert verses[-1].endswith("99 bottles of beer on the wall.\n")
    assert SONG.endswith(".\n")
    assert not SONG.endswith("\n\n")


@pytest.mark.parametrize(
    ("code", "output", "accumulator"),
    [
        # Biffle's own example: the file "qqqq" (with its final newline)
        # prints four copies of itself, one per line.
        ("qqqq\n", "qqqq\n" * 4, 0),
        ("H", "Hello, world!\n", 0),
        ("h", "Hello, world!\n", 0),
        ("Q", "Q", 0),
        ("9", SONG, 0),
        ("+++", "", 3),
        ("\uff48\uff51", "", 0),
        ("Hx+Q", "Hello, world!\nHx+Q", 1),
        ("", "", 0),
    ],
)
def test_reference_positive_controls(code, output, accumulator):
    expected = reference(code, len(code))
    assert expected[0] == output
    assert expected[2] == accumulator
    assert expected[3]
    assert observe(code, len(code)) == expected
